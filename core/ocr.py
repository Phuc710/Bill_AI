"""
VnCV OCR wrapper — offline Vietnamese OCR using vncv (ONNX-based).

Optimizations:
  - Redirects all vncv stdout/stderr noise to suppress model-loading logs
  - Uses return_dict=True for confidence scores
  - Saves temp file as JPEG (quality=95) for best OCR accuracy vs size trade-off
  - Auto-cleanup temp files via finally block
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List

from PIL import Image
from vncv import extract_text


@dataclass(slots=True)
class OCRTextResult:
    text_raw: str
    confidence_avg: float


class OCREngine:
    def extract_text(self, image: Image.Image) -> OCRTextResult:
        """OCR ảnh bằng vncv (Offline). Tự xóa temp file sau khi xong."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image.convert("RGB").save(tmp, format="JPEG", quality=95)
            tmp_path = tmp.name

        try:
            # Suppress tất cả log noise của vncv khi load model
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                raw_items = extract_text(tmp_path, lang="vi", return_dict=True)

            lines, confs = self._parse(raw_items or [])
            return OCRTextResult(
                text_raw="\n".join(lines),
                confidence_avg=sum(confs) / len(confs) if confs else 0.0,
            )
        except Exception:
            return OCRTextResult(text_raw="", confidence_avg=0.0)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
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
