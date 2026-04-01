"""
OCREngine — EasyOCR primary, YOLO ocr.pt fallback.

Lazy-loads the chosen backend on first call.
PaddleOCR was removed: it's not in requirements.txt and the import always
failed, adding ~100 ms of dead try/except at init for no benefit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

from core.config import Config


@dataclass(slots=True)
class OCRLine:
    """A single recognised text line with position and confidence."""
    text: str
    bbox: List[int]       # [x1, y1, x2, y2]
    confidence: float


class OCREngine:
    """
    Backend priority:
      1. EasyOCR  (Vietnamese + English)
      2. YOLO ocr.pt  (last resort)

    Models are loaded on the first `.extract()` call, not at construction.
    """

    def __init__(self, model_path: Path = Config.OCR_MODEL) -> None:
        self._model_path = model_path
        self._backend: Optional[str] = None   # "easy" | "yolo"
        self._engine: object = None           # the loaded backend instance

    # ── Lazy loader ───────────────────────────────────────────────────────

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return

        print("[OCREngine] Loading backend …")

        # Try EasyOCR first
        try:
            import easyocr
            self._engine = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
            self._backend = "easy"
            print("[OCREngine] Ready (EasyOCR).")
            return
        except Exception:
            pass

        # Fallback: YOLO OCR
        try:
            from ultralytics import YOLO
            self._engine = YOLO(str(self._model_path))
            self._backend = "yolo"
            print("[OCREngine] Ready (YOLO fallback).")
            return
        except Exception:
            pass

        print("[OCREngine] WARNING — no OCR backend available!")

    # ── Public API ────────────────────────────────────────────────────────

    def extract(self, image: Image.Image) -> List[OCRLine]:
        """
        Read text from *image*.
        Returns lines sorted top-to-bottom, left-to-right.
        """
        self._ensure_engine()

        if self._backend == "easy":
            lines = self._run_easy(image)
        elif self._backend == "yolo":
            lines = self._run_yolo(image)
        else:
            return []

        # Filter low-confidence / empty, then sort spatially
        lines = [ln for ln in lines if ln.confidence >= Config.OCR_CONF and ln.text.strip()]
        lines.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))
        return lines

    # ── Backend runners ───────────────────────────────────────────────────

    def _run_easy(self, image: Image.Image) -> List[OCRLine]:
        try:
            arr = np.array(image.convert("RGB"))
            results = self._engine.readtext(arr, detail=1, paragraph=False)
            return [
                OCRLine(
                    text=(text or "").strip(),
                    bbox=[min(int(p[0]) for p in pts), min(int(p[1]) for p in pts),
                          max(int(p[0]) for p in pts), max(int(p[1]) for p in pts)],
                    confidence=float(conf),
                )
                for pts, text, conf in results
                if (text or "").strip()
            ]
        except Exception:
            return []

    def _run_yolo(self, image: Image.Image) -> List[OCRLine]:
        try:
            results = self._engine.predict(source=image.convert("RGB"), verbose=False)
            width, height = image.size
            lines: List[OCRLine] = []
            for result in results:
                if result.boxes is None:
                    continue
                for idx in range(len(result.boxes)):
                    conf = float(result.boxes.conf[idx])
                    x1, y1, x2, y2 = (max(0, int(v)) for v in result.boxes.xyxy[idx].tolist())
                    x2, y2 = min(width, x2), min(height, y2)
                    cls_id = int(result.boxes.cls[idx]) if result.boxes.cls is not None else -1
                    text = (result.names.get(cls_id, "") if hasattr(result, "names") else "").strip()
                    if text:
                        lines.append(OCRLine(text=text, bbox=[x1, y1, x2, y2], confidence=conf))
            return lines
        except Exception:
            return []
