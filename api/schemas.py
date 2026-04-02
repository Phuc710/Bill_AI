"""
Pydantic schemas — request / response models.
Updated to support the new structured invoice output schema.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProductItem(BaseModel):
    PRODUCT: str = ""
    NUM: float = 0
    VALUE: float = 0


class InvoiceResult(BaseModel):
    SELLER: str = ""
    ADDRESS: str = ""
    TIMESTAMP: str = ""
    PRODUCTS: List[ProductItem] = Field(default_factory=list)
    TOTAL_COST: float = 0


class StructuredItem(BaseModel):
    name: str = ""
    quantity: int = 0
    unit_price: int = 0
    total_price: int = 0


class StructuredInvoice(BaseModel):
    store_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    invoice_id: Optional[str] = None
    datetime_in: Optional[str] = None
    datetime_out: Optional[str] = None
    cashier: Optional[str] = None
    table: Optional[str] = None
    items: List[StructuredItem] = Field(default_factory=list)
    subtotal: Optional[int] = None
    total: int = 0
    cash_given: Optional[int] = None
    cash_change: Optional[int] = None
    payment_method: Optional[str] = None
    raw_text: Optional[str] = None


class PipelineResponse(BaseModel):
    request_id: str
    status: str
    message: str = ""
    has_bill: bool = False
    needs_review: bool = False

    # Legacy-compatible fields
    result: Optional[Dict[str, Any]] = None
    orig_image: Optional[str] = None

    # New fields
    structured: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    log_path: str = ""
    detect_image: Optional[str] = None
    proc_image: Optional[str] = None


class BatchProcessResponse(BaseModel):
    total: int
    success_count: int
    fail_count: int
    results: List[PipelineResponse] = Field(default_factory=list)


class ExportRequest(BaseModel):
    request_ids: List[str]
