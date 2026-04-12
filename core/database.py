"""
Supabase Database service — invoices + invoice_items CRUD.
Backend dùng service_role key → bypass RLS hoàn toàn.

Schema:
  - invoices      : Thông tin chính của hóa đơn
  - invoice_items : Danh sách mặt hàng trong hóa đơn

Note:
  save_result() nhận db_payload đã được map sẵn bởi core.mapper.internal_to_db()
  thay vì tự map inline — tránh logic bị phân tán nhiều nơi.
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

    # ── Write operations ───────────────────────────────────────────────────────

    @classmethod
    def create_invoice(cls, invoice_id: str, user_id: str) -> None:
        """Tạo row khởi tạo với status=uploaded."""
        try:
            cls._db().table("invoices").insert({
                "id":      invoice_id,
                "user_id": user_id,
                "status":  "uploaded",
            }).execute()
            log.debug(f"DB create_invoice OK id={invoice_id}")
        except Exception as exc:
            log.error(f"DB create_invoice FAILED id={invoice_id}: {exc}")
            raise

    @classmethod
    def update_status(cls, invoice_id: str, status: str, **fields) -> None:
        """Cập nhật trạng thái pipeline + các trường bổ sung (tuỳ chọn)."""
        payload = {"status": status, **fields}
        try:
            cls._db().table("invoices").update(payload).eq("id", invoice_id).execute()
            log.debug(f"DB status → {status} id={invoice_id}")
        except Exception as exc:
            log.warning(f"DB update_status FAILED [{status}] id={invoice_id}: {exc}")

    @classmethod
    def update_status_safe(cls, invoice_id: str, user_id: str, status: str) -> None:
        """
        Upsert: tạo row mới hoặc update nếu đã tồn tại (1 roundtrip duy nhất).
        Dùng thay cho create_invoice + update_status riêng lẻ để giảm latency.
        """
        try:
            cls._db().table("invoices").upsert({
                "id":      invoice_id,
                "user_id": user_id,
                "status":  status,
            }, on_conflict="id").execute()
            log.debug(f"DB upsert_safe OK id={invoice_id} status={status}")
        except Exception as exc:
            log.warning(f"DB upsert_safe FAILED id={invoice_id}: {exc}")


    @classmethod
    def update_invoice_fields(cls, invoice_id: str, fields: Dict[str, Any]) -> bool:
        """Update các field cho phép từ màn hình edit bill."""
        allowed = {
            "store_name",
            "store_address",
            "store_phone",
            "invoice_number",
            "issued_at",
            "total_amount",
            "payment_method",
            "category",
            "note",
        }
        payload = {k: v for k, v in fields.items() if k in allowed}
        if not payload:
            return True

        # Nếu user đã chỉnh tay thì coi như bill đã hoàn thiện.
        payload["status"] = "completed"
        payload["failed_step"] = None
        payload["error_message"] = None

        try:
            cls._db().table("invoices").update(payload).eq("id", invoice_id).execute()
            log.info(f"DB update_invoice_fields OK id={invoice_id} fields={sorted(payload.keys())}")
            return True
        except Exception as exc:
            log.error(f"DB update_invoice_fields FAILED id={invoice_id}: {exc}")
            return False

    @classmethod
    def save_result(
        cls,
        invoice_id: str,
        db_payload: Dict[str, Any],     # pre-mapped bởi mapper.internal_to_db()
        items: List[Dict[str, Any]],    # internal items (name, quantity, unit_price, total_price)
        ocr_raw_text: str,
        llm_raw: str,
        orig_url: Optional[str],
        ocr_confidence: float,
        processing_ms: float,
    ) -> None:
        """Lưu toàn bộ kết quả trích xuất: cập nhật invoices + insert invoice_items."""
        invoice_update = {
            **db_payload,
            "status":               "completed",
            "original_image_url":   orig_url,
            "cropped_image_url":    orig_url,   # giữ để frontend không bị lỗi khuyết cột
            "ocr_raw_text":         ocr_raw_text,
            "summary":              db_payload.get("summary"),
            "detect_confidence":    1.0,         # không còn YOLO detector, mặc định 1.0
            "ocr_confidence":       ocr_confidence,
            "processing_time_ms":   processing_ms,
        }

        try:
            cls._db().table("invoices").update(invoice_update).eq("id", invoice_id).execute()
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

    # ── Read operations ────────────────────────────────────────────────────────

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
                    "category, cropped_image_url, note, summary, error_message, "
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
                .select("id, store_name, total_amount, category, status, issued_at, created_at")
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

    # ── Aliases (backward compat) ──────────────────────────────────────────
    create_bill        = create_invoice
    get_bill           = get_invoice
    list_bills         = list_invoices
    delete_bill        = delete_invoice
    list_bills_by_date = list_invoices_by_date

    # ── Admin / Dashboard ──────────────────────────────────────────────────

    @classmethod
    def get_admin_stats(cls) -> dict:
        """Stats tổng hợp cho admin dashboard — không filter theo user_id."""
        try:
            db = cls._db()

            # ── All-time totals ──────────────────────────────────────────
            all_res = (
                db.table("invoices")
                .select("id, status, processing_time_ms, ocr_confidence, created_at, category")
                .execute()
            )
            all_rows = all_res.data or []
            total       = len(all_rows)
            completed   = sum(1 for r in all_rows if r.get("status") == "completed")
            failed      = sum(1 for r in all_rows if r.get("status") == "failed")
            
            avg_ms_list = [r.get("processing_time_ms") or 0 for r in all_rows if r.get("processing_time_ms")]
            avg_ms      = round(sum(avg_ms_list) / len(avg_ms_list), 1) if avg_ms_list else 0.0
            
            conf_list   = [r.get("ocr_confidence") or 0 for r in all_rows if r.get("ocr_confidence")]
            avg_conf    = round((sum(conf_list) / len(conf_list)) * 100, 1) if conf_list else 0.0

            # ── Đếm category cho biểu đồ ──────────────────────────────
            cat_counts = {}
            for r in all_rows:
                c = r.get("category") or "Khác"
                cat_counts[c] = cat_counts.get(c, 0) + 1

            # ── Today (UTC) ──────────────────────────────────────────────
            from datetime import datetime, timezone
            today_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_res  = (
                db.table("invoices")
                .select("id, status")
                .gte("created_at", f"{today_str}T00:00:00Z")
                .execute()
            )
            today_rows      = today_res.data or []
            today_total     = len(today_rows)
            today_completed = sum(1 for r in today_rows if r.get("status") == "completed")

            # ── 50 bills mới nhất để vẽ bảng + trend chart ─────────────────
            recent_res = (
                db.table("invoices")
                .select(
                    "id, user_id, status, failed_step, store_name, "
                    "total_amount, category, cropped_image_url, ocr_raw_text, summary, "
                    "processing_time_ms, ocr_confidence, created_at, error_message"
                )
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            recent_rows = recent_res.data or []

            # Serialize datetime objects
            for r in recent_rows:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()

            success_rate = round(completed / total * 100, 1) if total > 0 else 0.0

            return {
                "total":           total,
                "completed":       completed,
                "failed":          failed,
                "success_rate":    success_rate,
                "avg_ms":          avg_ms,
                "avg_conf":        avg_conf,
                "cat_counts":      cat_counts,
                "today_total":     today_total,
                "today_completed": today_completed,
                "recent":          recent_rows,
            }
        except Exception as exc:
            log.error(f"DB get_admin_stats FAILED: {exc}")
            return {
                "total": 0, "completed": 0, "failed": 0,
                "success_rate": 0.0, "avg_ms": 0.0, "avg_conf": 0.0,
                "cat_counts": {}, "today_total": 0, "today_completed": 0,
                "recent": [],
            }
