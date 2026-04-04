"""
Invoice Pipeline — Production Flow.

  Upload → Detect (YOLO) → Crop → OCR (VnCV) → Groq Llama 3.3 70B → Save to Supabase

DB status transitions:
  uploaded → detecting → cropping → ocr_done → normalizing → completed
                                                            → failed
"""
from __future__ import annotations

import io
import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from core.config import Config
from core.database import DatabaseService
from core.groq_extractor import GroqExtractor
from core.ocr import OCREngine, OCRTextResult
from core.storage import StorageService

log = logging.getLogger("billai.pipeline")


class InvoicePipeline:
    def __init__(self) -> None:
        self._ocr          = OCREngine()
        self._extractor    = GroqExtractor()

    # ── Main entry ────────────────────────────────────────────────────────

    def run(
        self,
        image_bytes: bytes,
        filename: str,
        user_id: str,
        bill_id: str,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        log.info(f"[{bill_id}] Pipeline START | file={filename} user={user_id}")

        try:
            DatabaseService.create_invoice(bill_id, user_id)
        except Exception as exc:
            log.error(f"[{bill_id}] DB create failed, aborting: {exc}")
            return self._error_response(bill_id, "DB error", "db_init")

        orig_url: Optional[str] = None
        crop_url: Optional[str] = None

        try:
            # ── Step 1: Load & validate ────────────────────────────────────
            image, gray = self._load(image_bytes, filename)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # ── Step 2: Upload original to Storage ─────────────────────────
            DatabaseService.update_status(bill_id, "detecting")
            orig_url = StorageService.upload_image(image, bill_id, "Original")
            log.info(f"[{bill_id}] Original uploaded: {orig_url}")

            # ── Step 3: OCR Full Image (VnCV) ──────────────────────────────
            DatabaseService.update_status(bill_id, "ocr_done")
            ocr = self._ocr.extract_text(image)
            
            # Quét chữ OCR rồi lưu trạng thái nếu có
            DatabaseService.update_status(
                bill_id, "ocr_done",
                ocr_raw_text=ocr.text_raw or "",
            )
            log.info(
                f"[{bill_id}] OCR Full done | chars={len(ocr.text_raw or '')} "
                f"conf={ocr.confidence_avg:.3f}"
            )

            # ── Guard Clause: Không thấy chữ ───────────────────────────────
            if not (ocr.text_raw or "").strip():
                DatabaseService.mark_failed(bill_id, "ocr", "Không tìm thấy hóa đơn (None Text Detected)")
                log.warning(f"[{bill_id}] OCR empty — returning NOT FOUND status")
                return self._ocr_empty_response(bill_id, orig_url, t0)

            # ── Step 6: Groq Llama 3.3 70B ─────────────────────────────────────
            DatabaseService.update_status(bill_id, "normalizing")
            extraction = self._extractor.extract(ocr_text=ocr.text_raw)
            raw_response = extraction.get("raw_response", "")
            error_type = extraction.get("error_type")
            log.info(
                f"[{bill_id}] Groq done | error_type={error_type} | "
                f"raw_len={len(raw_response)}"
            )

            # ── Step 7: Persist to Supabase DB ─────────────────────────────
            structured = extraction.get("structured") or {}
            items: List[Dict[str, Any]] = structured.get("items") or []
            processing_ms = (time.perf_counter() - t0) * 1000
            needs_review = self._needs_review(structured, ocr.confidence_avg, error_type)

            DatabaseService.save_result(
                invoice_id=bill_id,
                structured=structured,
                items=items,
                ocr_raw_text=ocr.text_raw or "",
                llm_raw=raw_response,
                orig_url=orig_url,
                crop_url=orig_url,  # Giữ cho db/frontend ko bị lỗi khuyết cột
                detect_confidence=1.0, # Mặc định 1.0 vì bỏ detector
                ocr_confidence=ocr.confidence_avg,
                processing_ms=processing_ms,
                needs_review=needs_review,
            )
            log.info(
                f"[{bill_id}] COMPLETED | store={structured.get('store_name')} "
                f"total={structured.get('total')} ms={processing_ms:.0f}"
            )

            return self._success_response(
                bill_id=bill_id,
                structured=structured,
                items=items,
                orig_url=orig_url,
                processing_ms=processing_ms,
                needs_review=needs_review,
                llm_error=error_type,
            )

        except Exception as exc:
            stack = traceback.format_exc(limit=5)
            log.error(f"[{bill_id}] UNCAUGHT: {exc}\n{stack}")
            DatabaseService.mark_failed(bill_id, "unknown", str(exc)[:400])
            return self._error_response(bill_id, str(exc), "unknown", t0)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _load(self, image_bytes: bytes, filename: str) -> Tuple[Image.Image, np.ndarray]:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        if max(w, h) > Config.MAX_INPUT_SIDE:
            s   = Config.MAX_INPUT_SIDE / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        return img, gray



    @staticmethod
    def _needs_review(
        structured: Dict[str, Any],
        ocr_conf: float,
        llm_error: Optional[str],
    ) -> bool:
        if llm_error:
            return True
        if ocr_conf < Config.OCR_MIN_CONF:
            return True
        if int(structured.get("total") or 0) <= 0:
            return True
        return False

    # ── Response builders ─────────────────────────────────────────────────

    @staticmethod
    def _success_response(
        bill_id: str,
        structured: Dict[str, Any],
        items: List[Dict[str, Any]],
        orig_url: Optional[str],
        processing_ms: float,
        needs_review: bool,
        llm_error: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "bill_id": bill_id,
            "status": "completed",
            "original_image_url": orig_url,
            "cropped_image_url": orig_url,
            "data": {
                "store_name":     structured.get("store_name"),
                "address":        structured.get("address"),
                "phone":          structured.get("phone"),
                "invoice_id":     structured.get("invoice_id"),
                "datetime":       structured.get("datetime_in"),
                "total":          int(structured.get("total") or 0),
                "subtotal":       structured.get("subtotal"),
                "cash_given":     structured.get("cash_given"),
                "cash_change":    structured.get("cash_change"),
                "payment_method": structured.get("payment_method"),
                "category":       structured.get("category", "Khác"),
                "currency":       "VND",
            },
            "items": items,
            "meta": {
                "needs_review":       needs_review,
                "detect_confidence":  1.0,
                "processing_ms":      round(processing_ms, 1),
                "llm_error":          llm_error,
            },
        }

    @staticmethod
    def _not_found_response(
        bill_id: str, orig_url: Optional[str], t0: float
    ) -> Dict[str, Any]:
        return {
            "bill_id": bill_id,
            "status": "failed",
            "failed_step": "detect",
            "message": "Không phát hiện Bill trong ảnh",
            "original_image_url": orig_url,
            "cropped_image_url": None,
            "data": None,
            "items": [],
            "meta": {"processing_ms": round((time.perf_counter() - t0) * 1000, 1)},
        }

    @staticmethod
    def _ocr_empty_response(
        bill_id: str,
        orig_url: Optional[str],
        t0: float,
    ) -> Dict[str, Any]:
        return {
            "bill_id": bill_id,
            "status": "failed",
            "failed_step": "ocr",
            "message": "Không tìm thấy hóa đơn (None Text Detected)",
            "original_image_url": orig_url,
            "cropped_image_url": orig_url,
            "data": None,
            "items": [],
            "meta": {
                "detect_confidence": 1.0,
                "processing_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        }

    @staticmethod
    def _error_response(
        bill_id: str, message: str, step: str, t0: float = 0.0
    ) -> Dict[str, Any]:
        return {
            "bill_id": bill_id,
            "status": "failed",
            "failed_step": step,
            "message": message,
            "original_image_url": None,
            "cropped_image_url": None,
            "data": None,
            "items": [],
            "meta": {"processing_ms": round((time.perf_counter() - t0) * 1000, 1) if t0 else 0},
        }
