"""
text_cleaner.py — Minimal OCR post-processing.

Chỉ làm sạch ký tự điều khiển và khoảng trắng thừa.
KHÔNG normalize số tiền — để Gemini tự đọc context gốc (636,000 vs 1,000,000).
"""
from __future__ import annotations

import re
from datetime import datetime

_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_MULTI_SPACE_RE = re.compile(r" {2,}")


def clean_ocr_text(raw_text: str) -> str:
    """Strip control chars, normalize whitespace. Preserve all text and numbers as-is."""
    if not raw_text:
        return ""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CTRL_RE.sub(" ", text)
    lines = []
    for line in text.split("\n"):
        ln = _MULTI_SPACE_RE.sub(" ", line).strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def parse_datetime_safe(value: str) -> bool:
    """Return True if value matches a known Vietnamese date/time format."""
    if not value:
        return False
    v = re.sub(r"\s*(AM|PM)\s*$", "", value.strip(), flags=re.IGNORECASE).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y", "%Y-%m-%d",
    ):
        try:
            datetime.strptime(v, fmt)
            return True
        except ValueError:
            pass
    return False
