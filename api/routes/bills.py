"""
Bills API routes — production endpoints for Android client.

POST   /bills/extract           → Process image, return bill JSON
GET    /bills                   → List bills for a user
GET    /bills/{bill_id}         → Get single bill detail
DELETE /bills/{bill_id}         → Delete bill + images
GET    /bills/{bill_id}/export-csv  → Export single bill as CSV
GET    /bills/export            → Export bills by date range as CSV
"""
from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from core.config import Config
from core.database import DatabaseService
from core.pipeline import InvoicePipeline
from core.storage import StorageService

import logging

log = logging.getLogger("billai.routes")
router = APIRouter(prefix="/bills", tags=["Bills"])
_pipeline = InvoicePipeline()


def _validate_file(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in Config.VALID_EXTENSIONS:
        raise HTTPException(400, f"File type not supported: '{ext}'. Allowed: {Config.VALID_EXTENSIONS}")


# ── POST /bills/extract ────────────────────────────────────────────────────────

@router.post(
    "/extract",
    summary="Tạo và xử lý hóa đơn",
    description="Upload ảnh hóa đơn. Nhận kết quả JSON sau khi pipeline hoàn tất.",
)
async def extract_bill(
    request: Request,
    file: UploadFile = File(..., description="Ảnh hóa đơn (jpg/png/webp, max 10MB)"),
    user_id: str = Form(default="", description="ID người dùng từ app"),
) -> dict:
    _validate_file(file)
    data = await file.read()

    if len(data) > Config.MAX_IMAGE_BYTES:
        raise HTTPException(413, f"File quá lớn. Tối đa {Config.MAX_IMAGE_BYTES // 1024 // 1024}MB.")

    bill_id = str(uuid.uuid4())
    req_id  = getattr(request.state, "request_id", bill_id[:12])
    log.info(f"[{req_id}] extract_bill | bill={bill_id} file={file.filename} user={user_id}")

    try:
        result = await run_in_threadpool(
            _pipeline.run,
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
    description="Lấy danh sách hóa đơn của người dùng, có phân trang.",
)
async def list_bills(
    user_id: str = Query(..., description="ID người dùng"),
    page: int    = Query(1, ge=1),
    limit: int   = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
) -> dict:
    result = await run_in_threadpool(
        DatabaseService.list_bills, user_id, page, limit, status
    )
    return result


# ── GET /bills/export ──────────────────────────────────────────────────────────

@router.get(
    "/export",
    summary="Export CSV theo khoảng thời gian",
    description="Xuất danh sách hóa đơn trong khoảng ngày ra file CSV.",
)
async def export_range_csv(
    user_id: str  = Query(...),
    from_date: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to_date: str   = Query(..., alias="to",   description="YYYY-MM-DD"),
) -> StreamingResponse:
    bills = await run_in_threadpool(
        DatabaseService.list_bills_by_date, user_id, from_date, to_date
    )
    if not bills:
        raise HTTPException(404, "Không có hóa đơn nào trong khoảng thời gian này.")
    return _make_csv(bills, filename=f"bills_{from_date}_{to_date}.csv")


# ── GET /bills/{bill_id} ───────────────────────────────────────────────────────

@router.get(
    "/{bill_id}",
    summary="Chi tiết hóa đơn",
    description="Lấy toàn bộ thông tin của 1 hóa đơn, bao gồm danh sách món.",
)
async def get_bill(bill_id: str) -> dict:
    bill = await run_in_threadpool(DatabaseService.get_bill, bill_id)
    if not bill:
        raise HTTPException(404, f"Không tìm thấy hóa đơn: {bill_id}")
    return _format_bill(bill)


# ── DELETE /bills/{bill_id} ────────────────────────────────────────────────────

@router.delete(
    "/{bill_id}",
    summary="Xóa hóa đơn",
    description="Xóa hóa đơn khỏi database và các ảnh liên quan trên Storage.",
)
async def delete_bill(bill_id: str) -> dict:
    # Try to delete images from storage first
    await run_in_threadpool(StorageService.delete_images, bill_id)
    ok = await run_in_threadpool(DatabaseService.delete_bill, bill_id)
    if not ok:
        raise HTTPException(500, "Xóa hóa đơn thất bại.")
    return {"success": True, "bill_id": bill_id}


# ── GET /bills/{bill_id}/export-csv ───────────────────────────────────────────

@router.get(
    "/{bill_id}/export-csv",
    summary="Export 1 hóa đơn ra CSV",
)
async def export_bill_csv(bill_id: str) -> StreamingResponse:
    bill = await run_in_threadpool(DatabaseService.get_bill, bill_id)
    if not bill:
        raise HTTPException(404, f"Không tìm thấy hóa đơn: {bill_id}")

    rows = []
    for item in bill.get("items") or []:
        rows.append({
            "store":        bill.get("store_name", ""),
            "invoice_id":   bill.get("invoice_code", ""),
            "date":         str(bill.get("datetime_in", "")),
            "item":         item.get("name", ""),
            "quantity":     item.get("quantity", ""),
            "unit_price":   item.get("unit_price", ""),
            "total_price":  item.get("total_price", ""),
            "bill_total":   bill.get("total", ""),
            "payment":      bill.get("payment_method", ""),
        })
    if not rows:
        rows = [{
            "store": bill.get("store_name", ""), "invoice_id": bill.get("invoice_code", ""),
            "date": str(bill.get("datetime_in", "")), "item": "(no items)",
            "quantity": "", "unit_price": "", "total_price": "",
            "bill_total": bill.get("total", ""), "payment": bill.get("payment_method", ""),
        }]

    return _make_csv(rows, filename=f"bill_{bill_id[:8]}.csv")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_bill(bill: dict) -> dict:
    """Map DB row to the standard API response format."""
    return {
        "bill_id": bill.get("id"),
        "status":  bill.get("status"),
        "original_image_url": bill.get("original_image_url"),
        "cropped_image_url":  bill.get("cropped_image_url"),
        "data": {
            "store_name":     bill.get("store_name"),
            "address":        bill.get("address"),
            "phone":          bill.get("phone"),
            "invoice_id":     bill.get("invoice_code"),
            "datetime":       str(bill.get("datetime_in") or ""),
            "total":          bill.get("total", 0),
            "subtotal":       bill.get("subtotal"),
            "cash_given":     bill.get("cash_given"),
            "cash_change":    bill.get("cash_change"),
            "payment_method": bill.get("payment_method"),
            "currency":       bill.get("currency", "VND"),
        },
        "items": [
            {
                "name":        i.get("name"),
                "quantity":    i.get("quantity"),
                "unit_price":  i.get("unit_price"),
                "total_price": i.get("total_price"),
            }
            for i in (bill.get("items") or [])
        ],
        "meta": {
            "needs_review":      bill.get("needs_review", False),
            "detect_confidence": bill.get("detect_confidence", 0),
            "ocr_confidence":    bill.get("ocr_confidence", 0),
            "processing_ms":     bill.get("processing_ms", 0),
            "created_at":        str(bill.get("created_at", "")),
            "failed_step":       bill.get("failed_step"),
        },
    }


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
