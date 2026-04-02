"""
Supabase Database service — bills + bill_items CRUD.
Backend uses service_role key, which bypasses RLS entirely.
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
    def create_bill(cls, bill_id: str, user_id: str) -> None:
        """Insert initial row with status=uploaded."""
        try:
            cls._db().table("bills").insert({
                "id": bill_id,
                "user_id": user_id,
                "status": "uploaded",
            }).execute()
            log.debug(f"DB create_bill OK bill={bill_id} user={user_id}")
        except Exception as exc:
            log.error(f"DB create_bill FAILED bill={bill_id}: {exc}")
            raise

    @classmethod
    def update_status(cls, bill_id: str, status: str, **fields) -> None:
        """Update bill status + any extra fields atomically."""
        payload = {"status": status, **fields}
        try:
            cls._db().table("bills").update(payload).eq("id", bill_id).execute()
            log.debug(f"DB status → {status} bill={bill_id}")
        except Exception as exc:
            log.warning(f"DB update_status FAILED [{status}] bill={bill_id}: {exc}")

    @classmethod
    def save_result(
        cls,
        bill_id: str,
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
        """Save final extraction results — bills row + bill_items rows."""
        bill_payload: Dict[str, Any] = {
            "status": "completed",
            "original_image_url": orig_url,
            "cropped_image_url": crop_url,
            "ocr_raw_text": ocr_raw_text,
            "gemini_raw_response": gemini_raw,
            "store_name": structured.get("store_name"),
            "address": structured.get("address"),
            "phone": structured.get("phone"),
            "invoice_code": structured.get("invoice_id"),
            "cashier": structured.get("cashier"),
            "table_num": structured.get("table"),
            "payment_method": structured.get("payment_method"),
            "total": int(structured.get("total") or 0),
            "subtotal": structured.get("subtotal"),
            "cash_given": structured.get("cash_given"),
            "cash_change": structured.get("cash_change"),
            "detect_confidence": detect_confidence,
            "ocr_confidence": ocr_confidence,
            "processing_ms": processing_ms,
            "needs_review": needs_review,
        }
        if structured.get("datetime_in"):
            bill_payload["datetime_in"] = structured["datetime_in"]

        try:
            cls._db().table("bills").update(bill_payload).eq("id", bill_id).execute()
        except Exception as exc:
            log.error(f"DB save_result bill FAILED bill={bill_id}: {exc}")
            raise

        if items:
            rows = [
                {
                    "bill_id": bill_id,
                    "name": item.get("name", ""),
                    "quantity": max(1, int(item.get("quantity") or 1)),
                    "unit_price": max(0, int(item.get("unit_price") or 0)),
                    "total_price": max(0, int(item.get("total_price") or 0)),
                    "sort_order": idx,
                }
                for idx, item in enumerate(items)
            ]
            try:
                cls._db().table("bill_items").insert(rows).execute()
                log.debug(f"DB bill_items inserted {len(rows)} rows bill={bill_id}")
            except Exception as exc:
                log.warning(f"DB bill_items insert FAILED bill={bill_id}: {exc}")

    @classmethod
    def mark_failed(
        cls, bill_id: str, failed_step: str, error_message: str
    ) -> None:
        """Mark a bill as failed with step info."""
        cls.update_status(
            bill_id, "failed",
            failed_step=failed_step,
            error_message=error_message[:500],
        )

    # ── Read operations ────────────────────────────────────────────────────

    @classmethod
    def get_bill(cls, bill_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full bill + its items."""
        try:
            res = cls._db().table("bills").select("*").eq("id", bill_id).single().execute()
            bill = res.data
            if not bill:
                return None
            items_res = (
                cls._db().table("bill_items")
                .select("name, quantity, unit_price, total_price, sort_order")
                .eq("bill_id", bill_id)
                .order("sort_order")
                .execute()
            )
            bill["items"] = items_res.data or []
            return bill
        except Exception as exc:
            log.error(f"DB get_bill FAILED bill={bill_id}: {exc}")
            return None

    @classmethod
    def list_bills(
        cls,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Paginated list of bills for a user."""
        try:
            query = (
                cls._db().table("bills")
                .select("id, user_id, status, store_name, total, currency, payment_method, cropped_image_url, needs_review, created_at, failed_step")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )
            if status:
                query = query.eq("status", status)

            offset = (page - 1) * limit
            res = query.range(offset, offset + limit - 1).execute()
            return {"data": res.data or [], "page": page, "limit": limit}
        except Exception as exc:
            log.error(f"DB list_bills FAILED user={user_id}: {exc}")
            return {"data": [], "page": page, "limit": limit}

    @classmethod
    def delete_bill(cls, bill_id: str) -> bool:
        """Delete bill (bill_items cascade via FK)."""
        try:
            cls._db().table("bills").delete().eq("id", bill_id).execute()
            log.info(f"DB delete_bill OK bill={bill_id}")
            return True
        except Exception as exc:
            log.error(f"DB delete_bill FAILED bill={bill_id}: {exc}")
            return False

    @classmethod
    def list_bills_by_date(
        cls, user_id: str, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """List all bills in a date range for CSV export."""
        try:
            res = (
                cls._db().table("bills")
                .select("id, store_name, total, payment_method, status, created_at")
                .eq("user_id", user_id)
                .gte("created_at", f"{from_date}T00:00:00Z")
                .lte("created_at", f"{to_date}T23:59:59Z")
                .order("created_at")
                .execute()
            )
            return res.data or []
        except Exception as exc:
            log.error(f"DB list_bills_by_date FAILED user={user_id}: {exc}")
            return []
