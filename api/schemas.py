"""
Pydantic schemas — API request / response models.

Thiết kế để khớp 100% với BillModels.kt bên Android (Gson @SerializedName).
Không expose field nội bộ (legacy, structured, raw_response, math_warnings).

Models:
  BillItem           → invoice_items row shape (item_name, quantity, unit_price, total_price)
  BillData           → data object trong response (store_name, store_address, ...)
  BillMeta           → meta object trong response (needs_review, processing_ms, llm_error)
  BillResponse       → shape của POST /bills/extract và GET /bills/{id}
  ListBillsResponse  → shape của GET /bills
  BillSummary        → 1 item trong danh sách (từ v_invoice_summary view)
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Item ─────────────────────────────────────────────────────────────────────

class BillItem(BaseModel):
    item_name:   str = ""
    quantity:    int = 1
    unit_price:  int = 0
    total_price: int = 0


# ── Data (thông tin hóa đơn) ─────────────────────────────────────────────────

class BillData(BaseModel):
    store_name:     Optional[str] = None
    store_address:  Optional[str] = None   # @SerializedName("store_address") → address
    store_phone:    Optional[str] = None   # @SerializedName("store_phone")   → phone
    invoice_number: Optional[str] = None   # @SerializedName("invoice_number")→ invoice_id
    issued_at:      Optional[str] = None   # @SerializedName("issued_at")     → datetime
    total_amount:   int           = 0      # @SerializedName("total_amount")  → total
    subtotal:       Optional[int] = None
    cash_tendered:  Optional[int] = None   # @SerializedName("cash_tendered") → cash_given
    cash_change:    Optional[int] = None
    payment_method: Optional[str] = None
    category:       str           = "Khác"
    currency:       str           = "VND"


# ── Meta ─────────────────────────────────────────────────────────────────────

class BillMeta(BaseModel):
    needs_review:      bool              = False
    detect_confidence: float             = 1.0
    processing_ms:     float             = 0.0
    llm_error:         Optional[str]     = None  # lỗi từ Groq Llama 3.3 hoặc OCR


# ── Main response ─────────────────────────────────────────────────────────────

class BillResponse(BaseModel):
    bill_id:            str
    status:             str                      # "completed" | "failed"
    failed_step:        Optional[str]  = None
    message:            Optional[str]  = None
    original_image_url: Optional[str]  = None
    cropped_image_url:  Optional[str]  = None
    data:               Optional[BillData] = None
    items:              List[BillItem] = Field(default_factory=list)
    meta:               Optional[BillMeta] = None


# ── List / Summary ────────────────────────────────────────────────────────────

class BillSummary(BaseModel):
    id:                 str
    user_id:            str
    status:             str
    failed_step:        Optional[str]  = None
    store_name:         Optional[str]  = None
    invoice_number:     Optional[str]  = None
    issued_at:          Optional[str]  = None
    total_amount:       Optional[int]  = None
    currency:           Optional[str]  = None
    category:           Optional[str]  = None
    cropped_image_url:  Optional[str]  = None
    needs_review:       bool           = False
    processing_time_ms: Optional[float] = None
    created_at:         str            = ""
    item_count:         Optional[int]  = None


class ListBillsResponse(BaseModel):
    data:  List[BillSummary] = Field(default_factory=list)
    page:  int = 1
    limit: int = 20
