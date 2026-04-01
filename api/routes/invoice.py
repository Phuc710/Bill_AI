"""
Invoice API routes.

Endpoints:
  POST /api/process            — upload + extract in ONE call (primary)
  POST /api/upload-invoice     — legacy: upload only
  POST /api/extract-invoice    — legacy: extract from stored upload
  GET  /api/result/{id}        — fetch saved result by request_id
  POST /api/export-csv         — export results to CSV
  GET  /api/debug/{id}         — raw OCR + timing
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from api.schemas import ExportRequest, PipelineResponse, UploadResponse
from core.config import Config
from core.pipeline import InvoicePipeline

router = APIRouter(prefix="/api", tags=["invoice"])

# Single pipeline instance — models lazy-loaded on first request
_pipeline = InvoicePipeline()

# Legacy in-memory store for 2-step upload→extract flow
_image_store: Dict[str, Dict[str, Any]] = {}


# ── Validation helper ─────────────────────────────────────────────────────

def _validate_upload(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in Config.VALID_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIMARY ENDPOINT — single call, no intermediate state
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/process", response_model=PipelineResponse)
async def process_invoice(file: UploadFile = File(...)) -> PipelineResponse:
    """Upload an image and get extraction results in a single call."""
    _validate_upload(file)
    data = await file.read()
    if len(data) > Config.MAX_IMAGE_BYTES:
        raise HTTPException(413, "File too large (max 15 MB)")

    try:
        result = await run_in_threadpool(
            _pipeline.run, data, file.filename or "image.jpg",
        )
    except Exception as exc:
        raise HTTPException(500, f"Pipeline error: {exc}")

    return PipelineResponse(**result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY ENDPOINTS (kept for backward compatibility)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/upload-invoice", response_model=UploadResponse)
async def upload_invoice(file: UploadFile = File(...)) -> UploadResponse:
    _validate_upload(file)
    data = await file.read()
    if len(data) > Config.MAX_IMAGE_BYTES:
        raise HTTPException(413, "File too large (max 15 MB)")

    req_id = uuid.uuid4().hex[:12]
    _image_store[req_id] = {"data": data, "filename": file.filename or req_id}
    return UploadResponse(
        request_id=req_id,
        filename=file.filename or req_id,
        size_bytes=len(data),
        message="Upload OK. POST /api/extract-invoice to process.",
    )


@router.post("/extract-invoice", response_model=PipelineResponse)
async def extract_invoice(request_id: str) -> PipelineResponse:
    store = _image_store.pop(request_id, None)
    if store is None:
        raise HTTPException(404, f"request_id not found: {request_id}")
    try:
        result = await run_in_threadpool(
            _pipeline.run, store["data"], store["filename"],
        )
    except Exception as exc:
        raise HTTPException(500, f"Pipeline error: {exc}")
    return PipelineResponse(**result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESULT / EXPORT / DEBUG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/result/{request_id}", response_model=PipelineResponse)
async def get_result(request_id: str) -> PipelineResponse:
    log_path = Config.LOGS_DIR / f"{request_id}.json"
    if not log_path.exists():
        raise HTTPException(404, f"No log for: {request_id}")
    data = json.loads(log_path.read_text(encoding="utf-8"))
    return PipelineResponse(
        request_id=data.get("request_id", request_id),
        status=data.get("status", "unknown"),
        result=data.get("result"),
        orig_image=f"/outputs/{request_id}_orig.jpg",
        detect_image=f"/outputs/{request_id}_detect.jpg",
        ocr_image=f"/outputs/{request_id}_ocr.jpg",
        log_path=str(log_path),
    )


@router.post("/export-csv")
async def export_csv(body: ExportRequest) -> StreamingResponse:
    rows: list[dict] = []
    for req_id in body.request_ids:
        log_path = Config.LOGS_DIR / f"{req_id}.json"
        if not log_path.exists():
            continue
        log    = json.loads(log_path.read_text(encoding="utf-8"))
        result = log.get("result") or {}
        base = {
            "request_id": req_id,
            "status":     log.get("status"),
            "timestamp":  log.get("timestamp"),
            "SELLER":     result.get("SELLER", ""),
            "ADDRESS":    result.get("ADDRESS", ""),
            "DATETIME":   result.get("TIMESTAMP", ""),
            "TOTAL_COST": result.get("TOTAL_COST", ""),
        }
        products = result.get("PRODUCTS") or []
        if products:
            for p in products:
                row = dict(base)
                row["PRODUCT"] = p.get("PRODUCT", "")
                row["NUM"]     = p.get("NUM", "")
                row["VALUE"]   = p.get("VALUE", "")
                rows.append(row)
        else:
            rows.append(base)

    if not rows:
        raise HTTPException(404, "No valid request_ids found")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=invoice_results.csv"},
    )


@router.get("/debug/{request_id}")
async def debug_ocr(request_id: str) -> dict:
    log_path = Config.LOGS_DIR / f"{request_id}.json"
    if not log_path.exists():
        raise HTTPException(404, f"No log for: {request_id}")
    data = json.loads(log_path.read_text(encoding="utf-8"))
    return {
        "request_id":          request_id,
        "status":              data.get("status"),
        "timing_ms":           data.get("timing_ms"),
        "detector_confidence": data.get("detector_confidence"),
        "ocr_line_count":      len(data.get("ocr_raw") or []),
        "ocr_raw":             data.get("ocr_raw") or [],
    }
