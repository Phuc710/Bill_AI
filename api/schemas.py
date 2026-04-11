"""
Pydantic schemas — API request / response models.

Thiết kế để khớp 100% với BillModels.kt bên Android (Gson @SerializedName).

status: "completed" | "failed"
Mobile chỉ đọc field status — XONG.
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


# ── Main response ─────────────────────────────────────────────────────────────
# status: "completed" | "failed"
# Mobile chỉ cần đọc field này để định tuyến UI. XONG.

class BillResponse(BaseModel):
    bill_id:            str
    status:             str                    # "completed" | "failed"
    failed_step:        Optional[str]  = None  # null nếu OK
    message:            Optional[str]  = None  # Note AI tạo sẵn hoặc error msg
    note:               Optional[str]  = None  # Ghi chú user chỉnh tay
    original_image_url: Optional[str]  = None
    cropped_image_url:  Optional[str]  = None
    data:               Optional[BillData] = None
    items:              List[BillItem] = Field(default_factory=list)


# ── List / Summary ────────────────────────────────────────────────────────────

class BillSummary(BaseModel):
    id:                str
    user_id:           str
    status:            str
    failed_step:       Optional[str] = None
    store_name:        Optional[str] = None
    invoice_number:    Optional[str] = None
    issued_at:         Optional[str] = None
    total_amount:      Optional[int] = None
    currency:          Optional[str] = None
    category:          Optional[str] = None
    cropped_image_url: Optional[str] = None
    note:              Optional[str] = None
    summary:           Optional[str] = None
    error_message:     Optional[str] = None
    created_at:        str           = ""
    item_count:        Optional[int] = None


class ListBillsResponse(BaseModel):
    data:  List[BillSummary] = Field(default_factory=list)
    page:  int = 1
    limit: int = 20


class BillUpdateRequest(BaseModel):
    store_name:     Optional[str] = None
    store_address:  Optional[str] = None
    store_phone:    Optional[str] = None
    invoice_number: Optional[str] = None
    issued_at:      Optional[str] = None
    total_amount:   Optional[int] = None
    payment_method: Optional[str] = None
    category:       Optional[str] = None
    note:           Optional[str] = None
