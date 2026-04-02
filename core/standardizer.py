"""
Image standardizer: crop detected bill region, deskew, and enhance for OCR.
"""
from __future__ import annotations

from typing import List

import cv2
import numpy as np
from PIL import Image, ImageOps


class ImageStandardizer:
    """Crop, deskew, and lightly enhance the bill region."""

    def standardize(self, image: Image.Image, bbox: List[int]) -> Image.Image:
        """
        Crop to the bounding box with a small padding, deskew if tilted,
        and apply mild contrast enhancement for better OCR.
        """
        x1, y1, x2, y2 = bbox
        w_img, h_img = image.size

        # Add 2% padding around the detected region
        pad_x = int((x2 - x1) * 0.02)
        pad_y = int((y2 - y1) * 0.02)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w_img, x2 + pad_x)
        y2 = min(h_img, y2 + pad_y)

        cropped = image.crop((x1, y1, x2, y2)).convert("RGB")
        deskewed = self._deskew(cropped)
        enhanced = self._enhance(deskewed)
        return enhanced

    def _deskew(self, image: Image.Image) -> Image.Image:
        """Straighten slightly rotated images using Hough line detection."""
        try:
            gray = np.array(image.convert("L"))
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
            if lines is None:
                return image

            angles = []
            for line in lines[:20]:
                rho, theta = line[0]
                angle_deg = np.degrees(theta) - 90
                if abs(angle_deg) < 15:
                    angles.append(angle_deg)

            if not angles:
                return image

            median_angle = float(np.median(angles))
            if abs(median_angle) < 0.5:
                return image

            return image.rotate(-median_angle, expand=True, fillcolor=(255, 255, 255))
        except Exception:
            return image

    def _enhance(self, image: Image.Image) -> Image.Image:
        """Apply mild CLAHE contrast equalization for better OCR performance."""
        try:
            img_array = np.array(image)
            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l_channel, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)
            lab = cv2.merge([l_channel, a, b])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            return Image.fromarray(enhanced)
        except Exception:
            return image
