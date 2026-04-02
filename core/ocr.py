"""
VnCV OCR wrapper for full-text extraction only (no bbox/coordinate outputs).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

import contextlib
import io
from PIL import Image
from vncv.ocr import extract_text

from core.config import Config


@dataclass(slots=True)
class OCRTextResult:
    text_raw: str
    confidence_avg: float


class OCREngine:
    def extract_text(self, image: Image.Image) -> OCRTextResult:
        """OCR full image and return only raw text + average confidence."""
        temp_path = Config.OUTPUTS_DIR / f"temp_ocr_{uuid.uuid4().hex}.jpg"
        image.convert("RGB").save(temp_path, format="JPEG", quality=95)

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                raw_items = extract_text(str(temp_path), lang="vi", return_dict=True)
            lines, confidences = self._parse_text_and_conf(raw_items)
            raw_text = "\n".join(lines)
            confidence_avg = self._avg_conf(confidences)
            return OCRTextResult(text_raw=raw_text, confidence_avg=confidence_avg)
        except Exception:
            return OCRTextResult(text_raw="", confidence_avg=0.0)
        finally:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    @staticmethod
    def _parse_text_and_conf(raw_items: List[Dict[str, Any]]) -> tuple[List[str], List[float]]:
        lines: List[str] = []
        confidences: List[float] = []

        for item in raw_items:
            text = str(item.get("text") or "").strip()
            if not text:
                continue

            lines.append(text)
            confidences.append(float(item.get("confidence", 0.0) or 0.0))

        return lines, confidences

    @staticmethod
    def _avg_conf(confidences: List[float]) -> float:
        if not confidences:
            return 0.0
        return float(sum(confidences) / len(confidences))
