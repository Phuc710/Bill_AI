"""
ImageStandardizer — crop → resize → deskew → enhance.

Keeps processing lightweight: stays in numpy for the heavy steps,
only converts back to PIL at the end.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from core.config import Config

# Minimum pixel count on the longer side before we bother with deskew.
# Small images rarely need rotation and Otsu + minAreaRect is expensive.
_DESKEW_MIN_SIDE = 500


class ImageStandardizer:
    """Post-detection image normalisation pipeline."""

    def standardize(self, image: Image.Image, bbox: list[int]) -> Image.Image:
        """
        Crop → resize → (optional deskew) → gentle contrast boost.
        Returns a clean PIL Image ready for OCR.
        """
        arr = self._crop_to_array(image, bbox)
        arr = self._resize_array(arr)
        arr = self._deskew_array(arr)
        # Final PIL conversion + light enhance
        img = Image.fromarray(arr)
        return self._enhance(img)

    # ── Internal steps (numpy-native where possible) ──────────────────────

    @staticmethod
    def _crop_to_array(image: Image.Image, bbox: list[int]) -> np.ndarray:
        """Crop with 2 % padding, return as RGB numpy array."""
        x1, y1, x2, y2 = bbox
        w, h = image.size
        pad_x = int((x2 - x1) * 0.02)
        pad_y = int((y2 - y1) * 0.02)
        x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
        x2, y2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
        return np.array(image.crop((x1, y1, x2, y2)).convert("RGB"))

    @staticmethod
    def _resize_array(arr: np.ndarray) -> np.ndarray:
        """Resize longest side to MAX_IMG_SIDE if necessary."""
        h, w = arr.shape[:2]
        longest = max(w, h)
        if longest <= Config.MAX_IMG_SIDE:
            return arr
        scale = Config.MAX_IMG_SIDE / longest
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _deskew_array(arr: np.ndarray) -> np.ndarray:
        """Correct mild skew (1°–15°).  Skip for small images."""
        h, w = arr.shape[:2]
        if max(w, h) < _DESKEW_MIN_SIDE:
            return arr
        try:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 200:
                return arr
            angle = cv2.minAreaRect(coords)[-1]
            angle = -(90 + angle) if angle < -45 else -angle
            if abs(angle) < 1.0 or abs(angle) > 15.0:
                return arr
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            return cv2.warpAffine(
                arr, M, (w, h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255),
            )
        except Exception:
            return arr

    @staticmethod
    def _enhance(image: Image.Image) -> Image.Image:
        """Gentle contrast + sharpness.  No heavy denoise that kills text."""
        img = ImageOps.autocontrast(image, cutoff=0.5)
        img = ImageEnhance.Contrast(img).enhance(1.1)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        return img
