"""
Hybrid bill detector.

Primary detector: YOLOv8
Fallback detector: contour-based document localization
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw

from core.config import Config


class NoBillError(Exception):
    """Raised when no bill is found in the image."""


@dataclass(slots=True)
class DetectionRegion:
    bbox: List[int]
    confidence: float
    bill_count: int
    source: str = "yolo"


class BillDetector:
    """Detect bill regions using YOLO first, then a contour-based fallback."""

    def __init__(self) -> None:
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO  # type: ignore

            self._model = YOLO(str(Config.DETECTOR_MODEL_PATH))
        except Exception as exc:
            raise RuntimeError(f"Không thể tải model YOLO: {exc}") from exc

    def detect(self, image: Image.Image) -> DetectionRegion:
        self._load()

        yolo_region = self._detect_with_yolo(image)
        if yolo_region is not None:
            return yolo_region

        fallback_region = self._detect_with_contours(image)
        if fallback_region is not None:
            return fallback_region

        raise NoBillError("Không phát hiện Bill trong ảnh")

    def _detect_with_yolo(self, image: Image.Image) -> Optional[DetectionRegion]:
        results = self._model(image, verbose=False)

        best_conf = 0.0
        best_box: Optional[List[int]] = None
        total_count = 0

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                conf = float(box.conf[0])
                if conf < Config.DETECTOR_CONF_THRESHOLD:
                    continue

                total_count += 1
                if conf > best_conf:
                    xyxy = box.xyxy[0].tolist()
                    best_conf = conf
                    best_box = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]

        if best_box is None:
            return None

        return DetectionRegion(
            bbox=best_box,
            confidence=best_conf,
            bill_count=total_count,
            source="yolo",
        )

    def _detect_with_contours(self, image: Image.Image) -> Optional[DetectionRegion]:
        rgb = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self._foreground_is_dark(gray, thresh):
            thresh = cv2.bitwise_not(thresh)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        image_area = gray.shape[0] * gray.shape[1]
        best_score = 0.0
        best_box: Optional[List[int]] = None

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < image_area * 0.10:
                continue

            x, y, width, height = cv2.boundingRect(contour)
            if width <= 0 or height <= 0:
                continue

            aspect_ratio = height / width
            if not 0.8 <= aspect_ratio <= 4.5:
                continue

            fill_ratio = area / float(width * height)
            if fill_ratio < 0.45:
                continue

            edge_penalty = self._edge_penalty(
                x=x,
                y=y,
                width=width,
                height=height,
                image_width=gray.shape[1],
                image_height=gray.shape[0],
            )
            score = fill_ratio * 0.6 + min(area / image_area, 1.0) * 0.4 - edge_penalty
            if score <= best_score:
                continue

            best_score = score
            best_box = [x, y, x + width, y + height]

        if best_box is None:
            return None

        confidence = max(0.25, min(0.79, best_score))
        return DetectionRegion(
            bbox=best_box,
            confidence=confidence,
            bill_count=1,
            source="contour",
        )

    @staticmethod
    def _foreground_is_dark(gray: np.ndarray, thresh: np.ndarray) -> bool:
        white_pixels = gray[thresh == 255]
        black_pixels = gray[thresh == 0]
        if len(white_pixels) == 0 or len(black_pixels) == 0:
            return False
        return float(np.mean(white_pixels)) < float(np.mean(black_pixels))

    @staticmethod
    def _edge_penalty(
        x: int,
        y: int,
        width: int,
        height: int,
        image_width: int,
        image_height: int,
    ) -> float:
        touches = 0
        margin_x = max(8, int(image_width * 0.01))
        margin_y = max(8, int(image_height * 0.01))

        if x <= margin_x:
            touches += 1
        if y <= margin_y:
            touches += 1
        if x + width >= image_width - margin_x:
            touches += 1
        if y + height >= image_height - margin_y:
            touches += 1

        return touches * 0.05


def draw_detect_overlay(image: Image.Image, region: DetectionRegion) -> Image.Image:
    """Draw red bounding box and confidence label on the image for debug."""
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = region.bbox
    draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
    label = f"{region.source.upper()} {region.confidence:.2f}"
    draw.text((x1 + 4, max(0, y1 - 18)), label, fill="red")
    return overlay
