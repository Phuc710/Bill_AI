"""
BillDetector — YOLOv8-based receipt region finder.

Lazy-loads the model on first call.  Scores candidates with geometric
heuristics so a generic COCO model still picks the receipt over cups/bottles.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from core.config import Config


class NoBillError(Exception):
    """No receipt-like region found in the image."""


class BillRegion:
    """Lightweight container for a detected bill bounding box."""
    __slots__ = ("bbox", "confidence")

    def __init__(self, bbox: List[int], confidence: float) -> None:
        self.bbox = bbox          # [x1, y1, x2, y2]
        self.confidence = confidence


# ── Scoring bonuses for COCO class labels that often overlap receipts ─────
_CLASS_BONUS = {
    "bottle": 0.18, "book": 0.15, "cell phone": 0.12,
    "laptop": 0.10, "remote": 0.08, "cup": 0.06, "wine glass": 0.05,
}

# Score above which we short-circuit (clearly a receipt)
_FAST_EXIT_SCORE = 0.90


class BillDetector:
    """Detects the bounding box of a bill / receipt in an image."""

    def __init__(self, model_path: Path = Config.DETEC_MODEL) -> None:
        self._model_path = model_path
        self._model = None                    # lazy-loaded

    # ── Lazy loader ───────────────────────────────────────────────────────

    def _ensure_model(self):
        if self._model is None:
            from ultralytics import YOLO
            print(f"[BillDetector] Loading {self._model_path.name} …")
            self._model = YOLO(str(self._model_path))
            print("[BillDetector] Ready.")

    # ── Public API ────────────────────────────────────────────────────────

    def detect(self, image: Image.Image) -> BillRegion:
        """Find the best bill candidate.  Raises NoBillError if none found."""
        self._ensure_model()

        results = self._model.predict(
            source=image.convert("RGB"),
            conf=Config.DETEC_CONF,
            verbose=False,
        )

        img_w, img_h = image.size
        best_score = -1.0
        best_bbox: Optional[List[int]] = None
        best_conf = 0.0

        for result in results:
            if result.boxes is None:
                continue
            for idx in range(len(result.boxes)):
                conf = float(result.boxes.conf[idx])
                bbox = [int(v) for v in result.boxes.xyxy[idx].tolist()]
                cls_id = int(result.boxes.cls[idx]) if result.boxes.cls is not None else -1
                label = result.names.get(cls_id, "") if hasattr(result, "names") else ""

                score = _score_candidate(img_w, img_h, bbox, conf, label)

                if score > best_score:
                    best_score, best_bbox, best_conf = score, bbox, conf
                    if score >= _FAST_EXIT_SCORE:   # short-circuit
                        break
            if best_score >= _FAST_EXIT_SCORE:
                break

        if best_bbox is None or best_score < Config.DETEC_MIN_SCORE:
            raise NoBillError("Khong tim thay hoa don trong anh.")

        return BillRegion(best_bbox, best_conf)


# ── Overlay helper (called by pipeline, not by detector — SRP) ────────────

def draw_detect_overlay(image: Image.Image, region: BillRegion) -> Image.Image:
    """Return a copy of *image* with a red bbox + confidence label."""
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(region.bbox, outline="red", width=5)
    draw.text(
        (region.bbox[0], max(0, region.bbox[1] - 15)),
        f"Bill {region.confidence:.2f}",
        fill="red",
    )
    return overlay


# ── Scoring function (module-level, stateless) ───────────────────────────

def _score_candidate(
    img_w: int, img_h: int,
    bbox: List[int], confidence: float, label: str,
) -> float:
    """
    Score a YOLO box by how much it resembles a receipt.

    Favors centred, tall, medium-area boxes and de-ranks boxes that
    touch multiple image edges (full-frame detections).
    """
    x1, y1, x2, y2 = bbox
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)

    area_ratio = (box_w * box_h) / float(img_w * img_h)
    aspect_ratio = max(box_w, box_h) / max(1.0, min(box_w, box_h))

    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    center_dist = math.hypot(cx - 0.5, cy - 0.5) / 0.7071

    center_bonus   = max(0.0, 1.0 - center_dist) * 0.12
    rect_bonus     = max(0.0, 1.0 - abs(aspect_ratio - 1.65) / 1.25) * 0.22
    area_bonus     = max(0.0, 1.0 - abs(area_ratio - 0.55) / 0.35) * 0.22
    portrait_bonus = 0.08 if box_h >= box_w else 0.0
    class_bonus    = _CLASS_BONUS.get(label, 0.0)

    mx = img_w * 0.02
    my = img_h * 0.02
    edge_touches = (x1 <= mx) + (y1 <= my) + (x2 >= img_w - mx) + (y2 >= img_h - my)
    edge_penalty = max(0, edge_touches - 1) * 0.08

    return (
        confidence * 0.3
        + center_bonus + rect_bonus + area_bonus
        + portrait_bonus + class_bonus
        - edge_penalty
    )
