"""
Image standardization — Crop only.

Flow: Detect → Crop (bbox + small padding) → OCR
No deskew, no enhance. Clean and fast.
"""
from __future__ import annotations

from typing import List

import numpy as np
from PIL import Image


class ImageStandardizer:
    """Crop the detected bill region with a small safety padding."""

    def standardize(self, image: Image.Image, bbox: List[int]) -> Image.Image:
        x1, y1, x2, y2 = bbox
        w, h = image.size

        pad_x = int((x2 - x1) * 0.02)
        pad_y = int((y2 - y1) * 0.02)

        left   = max(0, x1 - pad_x)
        top    = max(0, y1 - pad_y)
        right  = min(w, x2 + pad_x)
        bottom = min(h, y2 + pad_y)

        return image.crop((left, top, right, bottom)).convert("RGB")
