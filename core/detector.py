"""
YOLOv8-based bill detector.
Raises NoBillError if no bill is found — pipeline must call this FIRST.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PIL import Image, ImageDraw

from core.config import Config


class NoBillError(Exception):
    """Raised when no bill is found in the image."""

@dataclass(slots=True)
class DetectionRegion:
    bbox: List[int]          # [x1, y1, x2, y2] in original image coords
    confidence: float
    bill_count: int


class BillDetector:
    """Lazy-load YOLOv8 and detect bill region."""

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
        """
        Run detection on the image.
        Returns the highest-confidence bounding box.
        Raises NoBillError if confidence < threshold or no box found.
        """
        self._load()
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
                    best_conf = conf
                    xyxy = box.xyxy[0].tolist()
                    best_box = [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]

        if best_box is None:
            raise NoBillError("Không phát hiện Bill trong ảnh")

        return DetectionRegion(bbox=best_box, confidence=best_conf, bill_count=total_count)


def draw_detect_overlay(image: Image.Image, region: DetectionRegion) -> Image.Image:
    """Draw red bounding box and confidence label on the image for debug."""
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = region.bbox
    draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
    label = f"BILL {region.confidence:.2f}"
    draw.text((x1 + 4, max(0, y1 - 18)), label, fill="red")
    return overlay
