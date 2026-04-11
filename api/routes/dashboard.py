"""
Admin Dashboard routes — serve HTML page + JSON stats.

Endpoints:
  GET /dashboard          → HTML dashboard page (no auth needed)
  GET /dashboard/stats    → JSON stats for JS polling
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from core.config import Config
from core.database import DatabaseService

log = logging.getLogger("billai.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ── GET /dashboard ─────────────────────────────────────────────────────────────

@router.get("", include_in_schema=False)
async def dashboard_page(request: Request):
    """Serve the admin dashboard HTML page."""
    html_file = _STATIC_DIR / "dashboard.html"
    if not html_file.exists():
        raise HTTPException(503, "Dashboard HTML not found.")
    return FileResponse(html_file, media_type="text/html")


# ── GET /dashboard/stats ───────────────────────────────────────────────────────

@router.get("/stats")
async def dashboard_stats(request: Request):
    """JSON stats endpoint — polled by dashboard JS every 30s."""

    stats = await run_in_threadpool(DatabaseService.get_admin_stats)

    return JSONResponse({
        "ok":            True,
        "groq_model":    Config.GROQ_MODEL,
        "pipeline_ver":  Config.PIPELINE_VERSION,
        "supabase_ok":   bool(Config.SUPABASE_URL and Config.SUPABASE_SERVICE_KEY),
        "groq_ok":       bool(Config.GROQ_API_KEY),
        **stats,
    })


# ── GET /dashboard/export ──────────────────────────────────────────────────────

@router.get("/export")
async def dashboard_export(request: Request):
    """Xuất toàn bộ data hóa đơn ra file CSV hỗ trợ Excel (UTF-8 BOM)."""
    try:
        db = DatabaseService._db()
        # Lấy tất cả invoices
        res = db.table("invoices").select(
            "id, status, store_name, total_amount, category, processing_time_ms, ocr_confidence, created_at, error_message"
        ).order("created_at", desc=True).execute()
        
        rows = res.data or []
        
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        # Ghi BOM (Byte Order Mark) để Excel nhận dạng là UTF-8
        output.write('\ufeff')
        
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "ID", "Trạng Thái", "Cửa Hàng", "Tổng Tiền", 
            "Danh Mục", "Thời Gian Xử Lý (ms)", "Độ Tin Cậy (%)", "Lỗi", "Ngày Tạo"
        ])
        
        for r in rows:
            conf = r.get("ocr_confidence")
            conf_percent = f"{round(conf * 100, 1)}%" if conf else ""
            
            writer.writerow([
                r.get("id", ""),
                r.get("status", ""),
                r.get("store_name") or "",
                r.get("total_amount") or "",
                r.get("category") or "",
                r.get("processing_time_ms") or "",
                conf_percent,
                r.get("error_message") or "",
                r.get("created_at", "")
            ])
            
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=billai_export.csv"}
        )
    except Exception as exc:
        log.error(f"Export CSV failed: {exc}")
        raise HTTPException(500, "Lỗi khi xuất dữ liệu")
