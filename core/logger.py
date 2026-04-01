"""
PipelineTracker — per-request timing + structured log.

Writes one JSON file per request to logs/.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import Config


class PipelineTracker:
    """Tracks a single invoice-extraction request end-to-end."""

    __slots__ = ("request_id", "_t0", "_log", "_steps")

    def __init__(self) -> None:
        self.request_id: str = uuid.uuid4().hex[:12]   # shorter, still unique enough
        self._t0: float = time.perf_counter()
        self._steps: Dict[str, float] = {}
        self._log: Dict[str, Any] = {
            "request_id":          self.request_id,
            "timestamp":           datetime.now(timezone.utc).isoformat(),
            "status":              "running",
            "timing_ms":           {},
            "original_image":      None,
            "processed_image":     None,
            "detector_bbox":       None,
            "detector_confidence": None,
            "ocr_raw":             [],
            "result":              None,
            "error":               None,
        }

    # ── Step timing ───────────────────────────────────────────────────────

    def start_step(self, name: str) -> None:
        self._steps[name] = time.perf_counter()

    def end_step(self, name: str) -> float:
        elapsed_ms = (time.perf_counter() - self._steps.get(name, self._t0)) * 1000
        self._log["timing_ms"][name] = round(elapsed_ms, 1)
        return elapsed_ms

    # ── Data setters ──────────────────────────────────────────────────────

    def set_images(self, original: Optional[str], processed: Optional[str]) -> None:
        self._log["original_image"]  = original
        self._log["processed_image"] = processed

    def set_detection(self, bbox: Optional[List[int]], confidence: Optional[float]) -> None:
        self._log["detector_bbox"]       = bbox
        self._log["detector_confidence"] = confidence

    def set_ocr_raw(self, lines: List[Dict]) -> None:
        self._log["ocr_raw"] = lines

    def set_result(self, result: Dict[str, Any]) -> None:
        self._log["result"] = result

    def set_status(self, status: str, error: Optional[str] = None) -> None:
        self._log["status"] = status
        if error:
            self._log["error"] = error
        self._log["timing_ms"]["total"] = round(
            (time.perf_counter() - self._t0) * 1000, 1,
        )

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> Path:
        path = Config.LOGS_DIR / f"{self.request_id}.json"
        path.write_text(
            json.dumps(self._log, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._log)
