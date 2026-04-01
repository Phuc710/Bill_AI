"""
Pydantic schemas — request / response models.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Invoice data (mirrors Gemini output) ──────────────────────────────────

class ProductItem(BaseModel):
    PRODUCT: str = ""
    NUM:     float = 0
    VALUE:   float = 0


class InvoiceResult(BaseModel):
    SELLER:     str = ""
    ADDRESS:    str = ""
    TIMESTAMP:  str = ""
    PRODUCTS:   List[ProductItem] = []
    TOTAL_COST: float = 0


# ── API responses ─────────────────────────────────────────────────────────

class PipelineResponse(BaseModel):
    """Returned by /api/process, /api/extract-invoice, and /api/result."""
    request_id:   str
    status:       str                         # success | no_bill_detected | fail
    result:       Optional[Dict[str, Any]] = None
    orig_image:   Optional[str] = None
    detect_image: Optional[str] = None
    ocr_image:    Optional[str] = None
    log_path:     str = ""


class UploadResponse(BaseModel):
    """Returned by /api/upload-invoice (legacy)."""
    request_id: str
    filename:   str
    size_bytes: int
    message:    str


class ExportRequest(BaseModel):
    request_ids: List[str]
