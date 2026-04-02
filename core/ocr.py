"""
VnCV OCR wrapper — stable file-based extraction.
Fixed: vncv.ocr.extract_text only reliably accepts string file paths.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List

from PIL import Image
from vncv.ocr import extract_text


@dataclass(slots=True)
class OCRTextResult:
    text_raw: str
    confidence_avg: float


class OCREngine:
    def extract_text(self, image: Image.Image) -> OCRTextResult:
        """OCR the image using a temporary file. Auto-deletes on context exit."""
        # Using a controlled temp file path to ensure high compatibility with vncv/opencv
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image.convert("RGB").save(tmp, format="JPEG", quality=95)
            tmp_path = tmp.name

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                # vncv requires a string path as 'filepath'
                raw_items = extract_text(tmp_path, lang="vi", return_dict=True)
            
            lines, confs = self._parse(raw_items or [])
            return OCRTextResult(
                text_raw="\n".join(lines),
                confidence_avg=sum(confs) / len(confs) if confs else 0.0,
            )
        except Exception:
            return OCRTextResult(text_raw="", confidence_avg=0.0)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @staticmethod
    def _parse(raw_items: List[Dict[str, Any]]) -> tuple[List[str], List[float]]:
        lines, confs = [], []
        for item in raw_items:
            text = str(item.get("text") or "").strip()
            if text:
                lines.append(text)
                confs.append(float(item.get("confidence") or 0.0))
        return lines, confs
