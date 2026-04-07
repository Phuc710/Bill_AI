"""
Bills API routes — production endpoints cho Android client.

Endpoints:
  POST   /bills/extract          → Upload ảnh, pipeline xử lý, trả BillResponse
  GET    /bills                  → Danh sách bills của user (phân trang)
  GET    /bills/{bill_id}        → Chi tiết 1 bill (kèm items)
  DELETE /bills/{bill_id}        → Xóa bill + ảnh trên Storage
  GET    /bills/export           → Export danh sách bills theo khoảng ngày (CSV)
  GET    /bills/{bill_id}/export-csv  → Export 1 bill ra CSV

Response shape cho tất cả endpoints khớp với BillModels.kt Android.
Mapping nội bộ thực hiện bởi core.mapper — không map inline tại đây.
"""
from __future__ import annotations

import csv
import io
import uuid as uuid_lib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

import logging

from core.config import Config
from core.database import DatabaseService
from core.mapper import db_to_api_response
from core.pipeline import InvoicePipeline
from core.storage import StorageService

log = logging.getLogger("billai.routes")
router = APIRouter(prefix="/bills", tags=["Bills"])

# Singleton pipeline — OCR model warm-up sekali saja saat import
_pipeline = InvoicePipeline()


def _validate_file(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in Config.VALID_EXTENSIONS:
        raise HTTPException(
            400,
            f"Định dạng file không hỗ trợ: '{ext}'. "
            f"Cho phép: {sorted(Config.VALID_EXTENSIONS)}"
        )


# ── POST /bills/extract ────────────────────────────────────────────────────────

@router.post(
    "/extract",
    summary="Upload và xử lý hóa đơn",
    description=(
        "Upload ảnh hóa đơn. Backend chạy OCR (VnCV offline) → Groq Llama 3.3 70B → "
        "trích xuất JSON → lưu Supabase. Trả về BillResponse với đầy đủ thông tin."
    ),
)
async def extract_bill(
    request: Request,
    file:    UploadFile = File(..., description="Ảnh hóa đơn (jpg/png/webp, tối đa 10MB)"),
    user_id: str        = Form(default="", description="UUID người dùng từ Supabase Auth"),
) -> dict:
    _validate_file(file)
    data = await file.read()

    if len(data) > Config.MAX_IMAGE_BYTES:
        raise HTTPException(
            413,
            f"File quá lớn. Tối đa {Config.MAX_IMAGE_BYTES // 1024 // 1024}MB."
        )

    # Validate user_id phải là UUID hợp lệ (Supabase column type = UUID)
    if not user_id or not _is_valid_uuid(user_id):
        raise HTTPException(
            400,
            f"user_id không hợp lệ: '{user_id}'. "
            "Phải là UUID hợp lệ (ví dụ: 550e8400-e29b-41d4-a716-446655440000). "
            "Lấy UUID từ Supabase Auth sau khi đăng nhập."
        )

    bill_id = str(uuid_lib.uuid4())
    req_id  = getattr(request.state, "request_id", bill_id[:12])
    log.info(f"[{req_id}] extract_bill START | bill={bill_id} file={file.filename} user={user_id}")

    try:
        result = await _pipeline.run(
            data,
            file.filename or "image.jpg",
            user_id,
            bill_id,
        )
    except Exception as exc:
        log.error(f"[{req_id}] Pipeline exception: {exc}")
        raise HTTPException(500, f"Pipeline error: {exc}")

    log.info(f"[{req_id}] extract_bill DONE | bill={bill_id} status={result.get('status')}")
    return result


# ── GET /bills ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="Danh sách hóa đơn",
    description="Lấy danh sách hóa đơn của người dùng, sắp xếp mới nhất trước, có phân trang.",
)
async def list_bills(
    user_id: str          = Query(..., description="UUID người dùng"),
    page:    int          = Query(1,  ge=1),
    limit:   int          = Query(20, ge=1, le=100),
    status:  Optional[str] = Query(None, description="Lọc theo trạng thái pipeline"),
) -> dict:
    result = await run_in_threadpool(
        DatabaseService.list_invoices, user_id, page, limit, status
    )
    return result


# ── GET /bills/export ──────────────────────────────────────────────────────────

@router.get(
    "/export",
    summary="Export CSV theo khoảng ngày",
    description="Xuất danh sách hóa đơn trong khoảng ngày ra file CSV.",
)
async def export_range_csv(
    user_id:   str = Query(...),
    from_date: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to_date:   str = Query(..., alias="to",   description="YYYY-MM-DD"),
) -> StreamingResponse:
    bills = await run_in_threadpool(
        DatabaseService.list_invoices_by_date, user_id, from_date, to_date
    )
    if not bills:
        raise HTTPException(404, "Không có hóa đơn nào trong khoảng thời gian này.")

    rows = [
        {
            "id":           b.get("id", ""),
            "store_name":   b.get("store_name", ""),
            "total_amount": b.get("total_amount", 0),
            "category":     b.get("category", ""),
            "status":       b.get("status", ""),
            "issued_at":    str(b.get("issued_at") or ""),
            "created_at":   str(b.get("created_at") or ""),
        }
        for b in bills
    ]
    return _make_csv(rows, filename=f"bills_{from_date}_{to_date}.csv")


# ── GET /bills/{bill_id} ───────────────────────────────────────────────────────

@router.get(
    "/{bill_id}",
    summary="Chi tiết hóa đơn",
    description="Lấy toàn bộ thông tin của 1 hóa đơn, bao gồm danh sách mặt hàng.",
)
async def get_bill(bill_id: str) -> dict:
    row = await run_in_threadpool(DatabaseService.get_invoice, bill_id)
    if not row:
        raise HTTPException(404, f"Không tìm thấy hóa đơn: {bill_id}")

    # mapper.db_to_api_response đảm bảo đúng format cho app
    items = row.pop("items", [])
    return db_to_api_response(row, items)


# ── DELETE /bills/{bill_id} ────────────────────────────────────────────────────

@router.delete(
    "/{bill_id}",
    summary="Xóa hóa đơn",
    description="Xóa hóa đơn khỏi database và ảnh liên quan trên Supabase Storage.",
)
async def delete_bill(bill_id: str) -> dict:
    await run_in_threadpool(StorageService.delete_images, bill_id)
    ok = await run_in_threadpool(DatabaseService.delete_invoice, bill_id)
    if not ok:
        raise HTTPException(500, "Xóa hóa đơn thất bại.")
    return {"success": True, "bill_id": bill_id}


# ── GET /bills/{bill_id}/export-csv ───────────────────────────────────────────

@router.get(
    "/{bill_id}/export-csv",
    summary="Export 1 hóa đơn ra CSV",
)
async def export_bill_csv(bill_id: str) -> StreamingResponse:
    row = await run_in_threadpool(DatabaseService.get_invoice, bill_id)
    if not row:
        raise HTTPException(404, f"Không tìm thấy hóa đơn: {bill_id}")

    items = row.get("items") or []
    rows = [
        {
            "store_name":   row.get("store_name", ""),
            "invoice_number": row.get("invoice_number", ""),
            "issued_at":    str(row.get("issued_at") or ""),
            "item_name":    item.get("item_name", ""),
            "quantity":     item.get("quantity", ""),
            "unit_price":   item.get("unit_price", ""),
            "total_price":  item.get("total_price", ""),
            "total_amount": row.get("total_amount", ""),
            "category":     row.get("category", ""),
        }
        for item in items
    ] or [
        {
            "store_name":     row.get("store_name", ""),
            "invoice_number": row.get("invoice_number", ""),
            "issued_at":      str(row.get("issued_at") or ""),
            "item_name":      "(no items)",
            "quantity":       "", "unit_price":   "",
            "total_price":    "", "total_amount": row.get("total_amount", ""),
            "category":       row.get("category", ""),
        }
    ]

    return _make_csv(rows, filename=f"bill_{bill_id[:8]}.csv")


# ── Helper ─────────────────────────────────────────────────────────────────────

def _is_valid_uuid(value: str) -> bool:
    """Kiểm tra chuỗi có phải UUID hợp lệ không."""
    try:
        uuid_lib.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _make_csv(rows: list, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
