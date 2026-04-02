"""
InvoicePipeline — Standardized flow for maximum accuracy and speed options.

Modes:
  1. FAST_MODE: Skip detection/standardize (saves ~7-10s). Original -> OCR -> Gemini.
  2. STANDARD_MODE: Detect -> Filter (Crop/Enhance) -> OCR -> Gemini. (Most Accurate)
"""
from __future__ import annotations

import io
import traceback
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from core.config import Config
from core.detector import BillDetector, NoBillError, draw_detect_overlay
from core.gemini_extractor import GeminiExtractor
from core.logger import PipelineTracker
from core.ocr import OCREngine, OCRTextResult
from core.standardizer import ImageStandardizer
from core.text_cleaner import clean_ocr_text, parse_datetime_safe


class InvoicePipeline:
    def __init__(self) -> None:
        self._detector = BillDetector()
        self._standardizer = ImageStandardizer()
        self._ocr = OCREngine()
        self._gemini = GeminiExtractor()

    def run(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
        user_id: str = "",
        request_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tracker = PipelineTracker(request_id=request_id, user_id=user_id, metadata=metadata or {})
        rid = tracker.request_id
        orig_url: Optional[str] = None

        try:
            # 1. Normalize
            tracker.start_step("input")
            image, input_meta = self._normalize(image_bytes, filename)
            tracker.end_step("input")
            tracker.set_input(input_meta)

            # 2. Precheck
            tracker.start_step("precheck")
            precheck = self._precheck(image, size_bytes=len(image_bytes))
            tracker.end_step("precheck")
            tracker.set_precheck(precheck)

            if not precheck["ok"]:
                return self._fail(tracker, precheck["message"], errors=[precheck["message"]])

            if Config.SAVE_DEBUG_IMAGES:
                orig_url = self._save(image, rid, "orig")
                tracker.set_orig_image(orig_url)

            # ── CORE STANDARDIZED PROCESSING ──
            region_conf = 0.0
            
            if Config.FAST_MODE:
                # [Optimization] Skip detection/standardization for speed
                tracker.start_step("detect")
                tracker.end_step("detect")
                tracker.start_step("standardize")
                tracker.end_step("standardize")
                bill = image
            else:
                # [Standard Flow] Detect -> Filter -> OCR -> Gemini
                tracker.start_step("detect")
                try:
                    region = self._detector.detect(image)
                    region_conf = region.confidence
                    tracker.set_detection(region.bbox, region.confidence, region.bill_count)
                    
                    # Generate the Bounding Box overlay image (Red BBox)
                    detect_img = draw_detect_overlay(image, region)
                    if Config.SAVE_DEBUG_IMAGES:
                        detect_url = self._save(detect_img, rid, "detect")
                        tracker._log["detector_image"] = detect_url
                    
                except NoBillError as exc:
                    tracker.end_step("detect")
                    return self._not_found(tracker, str(exc), orig_url=orig_url)
                tracker.end_step("detect")

                # Filter (Crop + Deskew + Enhance)
                tracker.start_step("standardize")
                bill = self._standardizer.standardize(image, region.bbox)
                tracker.end_step("standardize")
                
                if Config.SAVE_DEBUG_IMAGES:
                    proc_url = self._save(bill, rid, "proc")
                    tracker.set_proc_image(proc_url)

            # OCR — Use the bill (standardized image)
            tracker.start_step("ocr")
            ocr_raw = self._ocr.extract_text(bill)
            tracker.end_step("ocr")

            ocr_text = clean_ocr_text(ocr_raw.text_raw)
            tracker.set_ocr(
                raw_text=ocr_raw.text_raw,
                cleaned_text=ocr_text,
                confidence_avg=ocr_raw.confidence_avg,
            )

            # 6. Gemini — send raw OCR
            tracker.start_step("gemini")
            extraction = self._gemini.extract(ocr_text=ocr_text)
            tracker.end_step("gemini")
            tracker.set_gemini(extraction.get("raw_response", ""))

            legacy = extraction.get("legacy") or _empty_legacy()
            structured = extraction.get("structured") or {}
            tracker.set_result(legacy, structured)

            # 7. Validate
            validation = self._validate(
                legacy=legacy,
                structured=structured,
                detect_conf=region_conf,
                ocr_conf=ocr_raw.confidence_avg,
                has_text=bool(ocr_text.strip()),
            )

            needs_review = bool(validation["needs_review"])
            msg = "Xử lý thành công" if not needs_review else "Kết quả cần kiểm tra lại"

            return self._finalize(
                tracker=tracker,
                status="success",
                message=msg,
                has_bill=True,
                needs_review=needs_review,
                legacy=legacy,
                structured=structured,
                validation=validation,
                detect_conf=region_conf,
                orig_url=orig_url,
            )

        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            stack = traceback.format_exc(limit=5)
            return self._fail(tracker, "Lỗi xử lý pipeline", errors=[err], error_detail=f"{err}\n{stack}")

    def _finalize(self, tracker: PipelineTracker, status: str, message: str, has_bill: bool,
                  needs_review: bool, legacy: Dict[str, Any], structured: Dict[str, Any],
                  validation: Dict[str, Any], detect_conf: float, orig_url: Optional[str],
                  error: Optional[str] = None) -> Dict[str, Any]:
        tracker.set_validation(validation)
        tracker.set_result(legacy, structured)
        tracker.set_status(status=status, message=message, error=error)
        data = tracker.as_dict()
        timing = data.get("timing_ms", {})
        total_ms = float(timing.get("total", tracker.total_ms()))
        
        # Translate steps for tracking in UI
        step_names_vi = {
            "input": "Đọc ảnh",
            "precheck": "Kiểm tra sơ bộ",
            "detect": "Tìm vùng hóa đơn",
            "standardize": "Chuẩn hóa",
            "ocr": "ocr",
            "gemini": "Trích xuất",
            "total": "Tổng Pipeline"
        }
        translated_timing = {step_names_vi.get(k, k): v for k, v in timing.items()}

        meta = {
            "status": status,
            "pipeline_version": Config.PIPELINE_VERSION,
            "detect_confidence": round(float(detect_conf or 0.0), 4),
            "ocr_confidence_avg": round(float(data.get("ocr_confidence_avg", 0.0) or 0.0), 4),
            "needs_review": needs_review,
            "processing_time_ms": round(total_ms, 1),
            "validation": validation,
            "timing_ms": timing,
            "tracking_vi": translated_timing,
        }
        tracker.set_response_layers(raw={}, meta=meta)
        log_path = tracker.save()
        return {
            "request_id": tracker.request_id,
            "status": status,
            "message": message,
            "has_bill": has_bill,
            "needs_review": needs_review,
            "result": legacy,
            "structured": structured,
            "meta": meta,
            "orig_image": orig_url, 
            "detect_image": data.get("detector_image"),
            "proc_image": data.get("proc_image"),
            "log_path": str(log_path),
        }

    def _normalize(self, image_bytes: bytes, filename: str) -> tuple[Image.Image, Dict[str, Any]]:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        w, h = image.size
        if max(w, h) > Config.MAX_INPUT_SIDE:
            scale = Config.MAX_INPUT_SIDE / max(w, h)
            image = image.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
        return image, {"filename": filename, "width": image.size[0], "height": image.size[1]}

    def _precheck(self, image: Image.Image, size_bytes: int) -> Dict[str, Any]:
        gray = np.array(image.convert("L"))
        # Optimized blur check
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return {"ok": True, "message": "OK", "blur": round(blur, 1)}

    def _validate(self, legacy, structured, detect_conf, ocr_conf, has_text) -> Dict[str, Any]:
        warnings = []
        if not (legacy.get("SELLER") or "").strip(): warnings.append("Không tìm được tên cửa hàng")
        if float(legacy.get("TOTAL_COST") or 0) <= 0: warnings.append("Không tìm được tổng tiền")
        return {"errors": [], "warnings": warnings, "needs_review": bool(warnings), "ocr_status": "ok"}

    def _save(self, image: Image.Image, rid: str, suffix: str) -> str:
        Config.ensure_dirs()
        path = Config.OUTPUTS_DIR / f"{rid}_{suffix}.jpg"
        image.save(path, format="JPEG", quality=85)
        return f"/outputs/{rid}_{suffix}.jpg"

    def _fail(self, tracker, message, errors, error_detail=None):
        validation = {"errors": errors, "warnings": [], "needs_review": True, "ocr_status": "none"}
        return self._finalize(tracker, status="fail", message=message, has_bill=False, 
                              needs_review=True, legacy=_empty_legacy(), structured={}, 
                              validation=validation, detect_conf=0.0, orig_url=None, error=error_detail)

    def _not_found(self, tracker, message, orig_url=None):
        validation = {"errors": [message], "warnings": [], "needs_review": False, "ocr_status": "none"}
        return self._finalize(tracker, status="not_found", message=message, has_bill=False, 
                              needs_review=False, legacy=_empty_legacy(), structured={}, 
                              validation=validation, detect_conf=0.0, orig_url=orig_url)


def _empty_legacy() -> Dict[str, Any]:
    return {"SELLER": "", "ADDRESS": "", "TIMESTAMP": "", "PRODUCTS": [], "TOTAL_COST": 0.0}
