"""
InvoicePipeline — main orchestrator.

Flow:
  Image bytes → Load → Detect → Standardize → OCR → Gemini → Log → Return

Each .run() call is independent.  The Gemini call is blocking I/O so
the FastAPI route wraps it in run_in_threadpool.
"""
from __future__ import annotations

import io
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from core.config import Config
from core.detector import BillDetector, BillRegion, NoBillError, draw_detect_overlay
from core.gemini_extractor import GeminiExtractor
from core.logger import PipelineTracker
from core.ocr import OCREngine, OCRLine
from core.standardizer import ImageStandardizer


class InvoicePipeline:
    """
    Full pipeline: Image → Detect → Standardize → OCR → Gemini → Log.

    All heavy models are lazy-loaded on first use (see each module).
    """

    def __init__(self) -> None:
        self._detector     = BillDetector()
        self._standardizer = ImageStandardizer()
        self._ocr          = OCREngine()
        self._gemini       = GeminiExtractor()

    # ── Public entry point ────────────────────────────────────────────────

    def run(self, image_bytes: bytes, filename: str = "image.jpg") -> Dict[str, Any]:
        """
        Process one invoice image end-to-end.

        Returns dict with:
          request_id, status, result, orig_image, detect_image, ocr_image, log_path
        """
        tracker = PipelineTracker()
        rid = tracker.request_id

        # 1. Load ──────────────────────────────────────────────────────────
        tracker.start_step("load")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tracker.end_step("load")

        # Save original
        orig_url = _save(image, rid, "orig")

        # 2. Detect ────────────────────────────────────────────────────────
        tracker.start_step("detect")
        try:
            region = self._detector.detect(image)
        except NoBillError as exc:
            tracker.set_detection(None, None)
            tracker.set_status("no_bill_detected", str(exc))
            log_path = tracker.save()
            return _response(tracker, orig_url=orig_url, log_path=log_path)
        tracker.end_step("detect")
        tracker.set_detection(region.bbox, region.confidence)

        # Save detect overlay (optional)
        detect_url = None
        if Config.SAVE_DEBUG_IMAGES:
            overlay = draw_detect_overlay(image, region)
            detect_url = _save(overlay, rid, "detect")

        # 3. Standardize ───────────────────────────────────────────────────
        tracker.start_step("standardize")
        std_image = self._standardizer.standardize(image, region.bbox)
        tracker.end_step("standardize")
        tracker.set_images(orig_url, _save(std_image, rid, "proc"))

        # 4. OCR ───────────────────────────────────────────────────────────
        tracker.start_step("ocr")
        lines = self._ocr.extract(std_image)

        # Fallback: raw crop (no preprocessing)
        if not lines:
            x1, y1, x2, y2 = region.bbox
            lines = self._ocr.extract(image.crop((x1, y1, x2, y2)).convert("RGB"))
        tracker.end_step("ocr")
        tracker.set_ocr_raw([asdict(ln) for ln in lines])

        # Save OCR overlay
        ocr_url = _save_ocr_overlay(std_image, lines, rid)

        # 5. Gemini extraction ─────────────────────────────────────────────
        tracker.start_step("gemini")
        ocr_text = "\n".join(ln.text for ln in lines if ln.text.strip())
        result = self._gemini.extract(ocr_text)
        tracker.end_step("gemini")

        # 6. Finalise ──────────────────────────────────────────────────────
        tracker.set_result(result)
        tracker.set_status("success")
        log_path = tracker.save()

        return _response(
            tracker,
            status="success",
            result=result,
            orig_url=orig_url,
            detect_url=detect_url,
            ocr_url=ocr_url,
            log_path=log_path,
        )


# ── Helpers (module-level, stateless) ─────────────────────────────────────

def _response(
    tracker: PipelineTracker, *,
    status: str | None = None,
    result: Dict[str, Any] | None = None,
    orig_url: str | None = None,
    detect_url: str | None = None,
    ocr_url: str | None = None,
    log_path: Path | None = None,
) -> Dict[str, Any]:
    return {
        "request_id":   tracker.request_id,
        "status":       status or tracker._log["status"],
        "result":       result,
        "orig_image":   orig_url,
        "detect_image": detect_url,
        "ocr_image":    ocr_url,
        "log_path":     str(log_path) if log_path else "",
    }


def _save(image: Image.Image, rid: str, suffix: str) -> str:
    """Save image to outputs/ and return its URL path."""
    path = Config.OUTPUTS_DIR / f"{rid}_{suffix}.jpg"
    image.convert("RGB").save(path, format="JPEG", quality=85)
    return f"/outputs/{rid}_{suffix}.jpg"


def _save_ocr_overlay(image: Image.Image, lines: List[OCRLine], rid: str) -> str:
    """Draw green bboxes on the processed image and save."""
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    for ln in lines:
        x1, y1, x2, y2 = ln.bbox
        draw.rectangle([x1, y1, x2, y2], outline="#00ff88", width=2)
        label = ln.text[:18] + "…" if len(ln.text) > 18 else ln.text
        draw.text((x1, max(0, y1 - 14)), label, fill="#00ff88")
    return _save(overlay, rid, "ocr")
