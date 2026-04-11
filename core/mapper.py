"""
Schema Mapper — Tách 3 lớp schema rõ ràng, KHÔNG để lẫn.

  internal  (groq_extractor output)
      ↓
  api       (JSON trả về app Android — khớp BillModels.kt @SerializedName)
      ↓
  db        (column names trong Supabase invoices table)

Quy tắc:
  - App Android parse JSON bằng Gson + @SerializedName → field names phải khớp 100%.
  - DB layer đọc từ mapper.internal_to_db() thay vì tự map inline.
  - GET /bills/{id} dùng mapper.db_to_api_response() thay vì viết lại logic.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


# ── internal → API response ───────────────────────────────────────────────────

def internal_to_api_response(
    internal: Dict[str, Any],
    bill_id: str,
    orig_url: Optional[str],
) -> Dict[str, Any]:
    """
    Map internal extractor schema → API response (Android BillModels.kt).
    status luôn = "completed" nếu gọi hàm này.
    """
    items = [_item_internal_to_api(i) for i in (internal.get("items") or [])]
    return {
        "bill_id":            bill_id,
        "status":             "completed",
        "failed_step":        None,
        "message":            internal.get("summary"),
        "original_image_url": orig_url,
        "cropped_image_url":  orig_url,
        "data": {
            "store_name":     internal.get("store_name"),
            "store_address":  internal.get("address"),
            "store_phone":    internal.get("phone"),
            "invoice_number": internal.get("invoice_id"),
            "issued_at":      internal.get("datetime_in"),
            "total_amount":   int(internal.get("total") or 0),
            "subtotal":       internal.get("subtotal"),
            "cash_tendered":  internal.get("cash_given"),
            "cash_change":    internal.get("cash_change"),
            "payment_method": internal.get("payment_method"),
            "category":       internal.get("category") or "Khác",
            "currency":       "VND",
        },
        "items": items,
    }


def failed_api_response(
    bill_id: str,
    failed_step: str,
    message: str,
    orig_url: Optional[str] = None,
    t0: float = 0.0,
) -> Dict[str, Any]:
    """API response khi pipeline thất bại — app check status == 'failed'."""
    elapsed = round((time.perf_counter() - t0) * 1000, 1) if t0 else 0.0
    return {
        "bill_id":            bill_id,
        "status":             "failed",
        "failed_step":        failed_step,
        "message":            message,   # Mobile hiển thị này thông báo lỗi cho user
        "original_image_url": orig_url,
        "cropped_image_url":  orig_url,
        "data":               None,
        "items":              [],
    }


# ── internal → DB columns ─────────────────────────────────────────────────────

def internal_to_db(internal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map internal schema → Supabase invoices column names.
    Dùng để build payload cho DatabaseService.save_result().
    """
    payload: Dict[str, Any] = {
        "store_name":     internal.get("store_name"),
        "store_address":  internal.get("address"),
        "store_phone":    internal.get("phone"),
        "invoice_number": internal.get("invoice_id"),
        "category":       internal.get("category") or "Khác",
        "total_amount":   int(internal.get("total") or 0),
        "subtotal":       internal.get("subtotal"),
        "cash_tendered":  internal.get("cash_given"),
        "cash_change":    internal.get("cash_change"),
        "payment_method": internal.get("payment_method"),
        "summary":        internal.get("summary"),
    }
    dt = internal.get("datetime_in")
    if dt:
        payload["issued_at"] = dt
    return payload


# ── DB row → API response ─────────────────────────────────────────────────────

def db_to_api_response(
    db_row: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Map Supabase DB row → BillResponse shape.
    Dùng cho GET /bills/{bill_id} endpoint.
    items: list of invoice_items rows (item_name, quantity, unit_price, total_price).
    """
    api_items = [
        {
            "item_name":   i.get("item_name", ""),
            "quantity":    i.get("quantity", 1),
            "unit_price":  i.get("unit_price", 0),
            "total_price": i.get("total_price", 0),
        }
        for i in items
    ]

    issued_at = db_row.get("issued_at")
    if issued_at and hasattr(issued_at, "isoformat"):
        issued_at = issued_at.isoformat()

    return {
        "bill_id":            db_row.get("id"),
        "status":             db_row.get("status"),
        "failed_step":        db_row.get("failed_step"),
        "message":            db_row.get("summary") if db_row.get("status") == "completed" else db_row.get("error_message"),
        "original_image_url": db_row.get("original_image_url"),
        "cropped_image_url":  db_row.get("cropped_image_url"),
        "data": {
            "store_name":     db_row.get("store_name"),
            "store_address":  db_row.get("store_address"),
            "store_phone":    db_row.get("store_phone"),
            "invoice_number": db_row.get("invoice_number"),
            "issued_at":      str(issued_at) if issued_at else None,
            "total_amount":   int(db_row.get("total_amount") or 0),
            "subtotal":       db_row.get("subtotal"),
            "cash_tendered":  db_row.get("cash_tendered"),
            "cash_change":    db_row.get("cash_change"),
            "payment_method": db_row.get("payment_method"),
            "category":       db_row.get("category") or "Khác",
            "currency":       db_row.get("currency", "VND"),
        },
        "items": api_items,
        "meta": {
            "needs_review":      bool(db_row.get("needs_review", False)),
            "detect_confidence": float(db_row.get("detect_confidence") or 0.0),
            "processing_ms":     float(db_row.get("processing_time_ms") or 0.0),
            "llm_error":         db_row.get("error_message"),
        },
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _item_internal_to_api(item: Dict[str, Any]) -> Dict[str, Any]:
    """Internal item dict → API item (app expects item_name, quantity, unit_price, total_price)."""
    return {
        "item_name":   item.get("name", ""),
        "quantity":    item.get("quantity", 1),
        "unit_price":  item.get("unit_price", 0),
        "total_price": item.get("total_price", 0),
    }
