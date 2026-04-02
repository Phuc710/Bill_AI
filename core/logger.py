"""
Per-request pipeline logging and timing.
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
    """Tracks one invoice-processing request end-to-end."""

    __slots__ = ("request_id", "_t0", "_log", "_steps")

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        rid = (request_id or "").strip() or uuid.uuid4().hex[:12]
        self.request_id: str = rid
        self._t0: float = time.perf_counter()
        self._steps: Dict[str, float] = {}

        self._log: Dict[str, Any] = {
            "request_id": self.request_id,
            "user_id": user_id or "",
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "message": "",
            "timing_ms": {},
            "orig_image": None,
            "detector_image": None,
            "proc_image": None,
            "detector_bbox": None,
            "detector_confidence": None,
            "detector_source": None,
            "bill_count": 0,
            "ocr_raw_text": "",
            "ocr_confidence_avg": 0.0,
            "gemini_raw": "",
            "result": None,
            "structured": None,
            "validation": {},
            "raw": None,
            "meta": None,
            "error": None,
            "input": {},
            "precheck": {},
        }

    def start_step(self, name: str) -> None:
        self._steps[name] = time.perf_counter()

    def end_step(self, name: str) -> float:
        elapsed_ms = (time.perf_counter() - self._steps.get(name, self._t0)) * 1000.0
        self._log["timing_ms"][name] = round(elapsed_ms, 1)
        return elapsed_ms

    def set_input(self, payload: Dict[str, Any]) -> None:
        self._log["input"] = payload

    def set_precheck(self, payload: Dict[str, Any]) -> None:
        self._log["precheck"] = payload

    def set_orig_image(self, url: Optional[str]) -> None:
        self._log["orig_image"] = url

    def set_detect_image(self, url: Optional[str]) -> None:
        self._log["detector_image"] = url

    def set_proc_image(self, url: Optional[str]) -> None:
        self._log["proc_image"] = url

    def set_detection(
        self,
        bbox: Optional[List[int]],
        confidence: Optional[float],
        bill_count: int,
        source: Optional[str] = None,
    ) -> None:
        self._log["detector_bbox"] = bbox
        self._log["detector_confidence"] = confidence
        self._log["detector_source"] = source
        self._log["bill_count"] = bill_count

    def set_ocr(self, raw_text: str, confidence_avg: float) -> None:
        self._log["ocr_raw_text"] = raw_text
        self._log["ocr_confidence_avg"] = round(float(confidence_avg), 4)

    def set_gemini(self, raw_response: str) -> None:
        self._log["gemini_raw"] = raw_response

    def set_result(
        self,
        legacy_result: Dict[str, Any],
        structured_result: Dict[str, Any],
    ) -> None:
        self._log["result"] = legacy_result
        self._log["structured"] = structured_result

    def set_validation(self, payload: Dict[str, Any]) -> None:
        self._log["validation"] = payload

    def set_response_layers(self, raw: Dict[str, Any], meta: Dict[str, Any]) -> None:
        self._log["raw"] = raw
        self._log["meta"] = meta

    def set_status(
        self,
        status: str,
        message: str = "",
        error: Optional[str] = None,
    ) -> None:
        self._log["status"] = status
        self._log["message"] = message
        if error:
            self._log["error"] = error
        self._log["timing_ms"]["total"] = round(
            (time.perf_counter() - self._t0) * 1000.0,
            1,
        )

    def total_ms(self) -> float:
        return float(self._log["timing_ms"].get("total", 0.0))

    def save(self) -> Path:
        Config.ensure_dirs()
        path = Config.LOGS_DIR / f"{self.request_id}.json"
        path.write_text(
            json.dumps(self._log, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._log)
