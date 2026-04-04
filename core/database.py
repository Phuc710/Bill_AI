"""
Supabase Database service — invoices + invoice_items CRUD.
Backend dùng service_role key → bypass RLS hoàn toàn.

Schema:
  - invoices      : Thông tin chính của hóa đơn
  - invoice_items : Danh sách mặt hàng trong hóa đơn
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.config import Config

log = logging.getLogger("billai.db")


def _get_client():
    from supabase import create_client  # type: ignore
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)


class DatabaseService:
    _client = None

    @classmethod
    def _db(cls):
        if cls._client is None:
            cls._client = _get_client()
        return cls._client

    # ── Write operations ───────────────────────────────────────────────────

    @classmethod
    def create_invoice(cls, invoice_id: str, user_id: str) -> None:
        """Tạo row khởi tạo với status=uploaded."""
        try:
            cls._db().table("invoices").insert({
                "id":      invoice_id,
                "user_id": user_id,
                "status":  "uploaded",
            }).execute()
            log.debug(f"DB create_invoice OK id={invoice_id} user={user_id}")
        except Exception as exc:
            log.error(f"DB create_invoice FAILED id={invoice_id}: {exc}")
            raise

    @classmethod
    def update_status(cls, invoice_id: str, status: str, **fields) -> None:
        """Cập nhật trạng thái pipeline + các trường bổ sung (nếu có)."""
        payload = {"status": status, **fields}
        try:
            cls._db().table("invoices").update(payload).eq("id", invoice_id).execute()
            log.debug(f"DB status → {status} id={invoice_id}")
        except Exception as exc:
            log.warning(f"DB update_status FAILED [{status}] id={invoice_id}: {exc}")

    @classmethod
    def save_result(
        cls,
        invoice_id: str,
        structured: Dict[str, Any],
        items: List[Dict[str, Any]],
        ocr_raw_text: str,
        gemini_raw: str,
        orig_url: Optional[str],
        crop_url: Optional[str],
        detect_confidence: float,
        ocr_confidence: float,
        processing_ms: float,
        needs_review: bool,
    ) -> None:
        """Lưu toàn bộ kết quả trích xuất: cập nhật invoices + insert invoice_items."""
        invoice_payload: Dict[str, Any] = {
            "status":               "completed",
            "original_image_url":   orig_url,
            "cropped_image_url":    crop_url,
            "ocr_raw_text":         ocr_raw_text,
            "gemini_raw_response":  gemini_raw,
            # Thông tin cửa hàng
            "store_name":           structured.get("store_name"),
            "store_address":        structured.get("address"),
            "store_phone":          structured.get("phone"),
            # Thông tin hóa đơn
            "invoice_number":       structured.get("invoice_id"),
            "cashier_name":         structured.get("cashier"),
            "table_number":         structured.get("table"),
            "payment_method":       structured.get("payment_method"),
            # Danh mục chi tiêu (AI phân loại)
            "category":             structured.get("category", "Khác"),
            # Tiền tệ
            "total_amount":         int(structured.get("total") or 0),
            "subtotal":             structured.get("subtotal"),
            "cash_tendered":        structured.get("cash_given"),
            "cash_change":          structured.get("cash_change"),
            # Pipeline metrics
            "detect_confidence":    detect_confidence,
            "ocr_confidence":       ocr_confidence,
            "processing_time_ms":   processing_ms,
            "needs_review":         needs_review,
        }
        if structured.get("datetime_in"):
            invoice_payload["issued_at"] = structured["datetime_in"]

        try:
            cls._db().table("invoices").update(invoice_payload).eq("id", invoice_id).execute()
            log.debug(f"DB save_result invoices OK id={invoice_id}")
        except Exception as exc:
            log.error(f"DB save_result invoices FAILED id={invoice_id}: {exc}")
            raise

        if items:
            rows = [
                {
                    "invoice_id":  invoice_id,
                    "item_name":   item.get("name", ""),
                    "quantity":    max(1, int(item.get("quantity") or 1)),
                    "unit_price":  max(0, int(item.get("unit_price") or 0)),
                    "total_price": max(0, int(item.get("total_price") or 0)),
                    "sort_order":  idx,
                }
                for idx, item in enumerate(items)
            ]
            try:
                cls._db().table("invoice_items").insert(rows).execute()
                log.debug(f"DB invoice_items inserted {len(rows)} rows id={invoice_id}")
            except Exception as exc:
                log.warning(f"DB invoice_items insert FAILED id={invoice_id}: {exc}")

    @classmethod
    def mark_failed(
        cls, invoice_id: str, failed_step: str, error_message: str
    ) -> None:
        """Đánh dấu hóa đơn thất bại tại bước cụ thể."""
        cls.update_status(
            invoice_id, "failed",
            failed_step=failed_step,
            error_message=error_message[:500],
        )

    # ── Read operations ────────────────────────────────────────────────────

    @classmethod
    def get_invoice(cls, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Lấy đầy đủ thông tin 1 hóa đơn kèm danh sách mặt hàng."""
        try:
            res = (
                cls._db().table("invoices")
                .select("*")
                .eq("id", invoice_id)
                .single()
                .execute()
            )
            invoice = res.data
            if not invoice:
                return None
            items_res = (
                cls._db().table("invoice_items")
                .select("item_name, quantity, unit_price, total_price, sort_order")
                .eq("invoice_id", invoice_id)
                .order("sort_order")
                .execute()
            )
            invoice["items"] = items_res.data or []
            return invoice
        except Exception as exc:
            log.error(f"DB get_invoice FAILED id={invoice_id}: {exc}")
            return None

    @classmethod
    def list_invoices(
        cls,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Danh sách hóa đơn của user, có phân trang."""
        try:
            query = (
                cls._db().table("invoices")
                .select(
                    "id, user_id, status, store_name, total_amount, currency, "
                    "payment_method, category, cropped_image_url, needs_review, "
                    "created_at, failed_step, issued_at"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )
            if status:
                query = query.eq("status", status)

            offset = (page - 1) * limit
            res = query.range(offset, offset + limit - 1).execute()
            return {"data": res.data or [], "page": page, "limit": limit}
        except Exception as exc:
            log.error(f"DB list_invoices FAILED user={user_id}: {exc}")
            return {"data": [], "page": page, "limit": limit}

    @classmethod
    def delete_invoice(cls, invoice_id: str) -> bool:
        """Xóa hóa đơn (invoice_items tự xóa theo ON DELETE CASCADE)."""
        try:
            cls._db().table("invoices").delete().eq("id", invoice_id).execute()
            log.info(f"DB delete_invoice OK id={invoice_id}")
            return True
        except Exception as exc:
            log.error(f"DB delete_invoice FAILED id={invoice_id}: {exc}")
            return False

    @classmethod
    def list_invoices_by_date(
        cls, user_id: str, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Lấy tất cả hóa đơn trong khoảng ngày để xuất CSV."""
        try:
            res = (
                cls._db().table("invoices")
                .select("id, store_name, total_amount, payment_method, category, status, issued_at, created_at")
                .eq("user_id", user_id)
                .gte("created_at", f"{from_date}T00:00:00Z")
                .lte("created_at", f"{to_date}T23:59:59Z")
                .order("created_at")
                .execute()
            )
            return res.data or []
        except Exception as exc:
            log.error(f"DB list_invoices_by_date FAILED user={user_id}: {exc}")
            return []

    # ── Backward-compatible aliases (giữ để không vỡ code cũ nếu có) ──────
    create_bill         = create_invoice
    get_bill            = get_invoice
    list_bills          = list_invoices
    delete_bill         = delete_invoice
    list_bills_by_date  = list_invoices_by_date
