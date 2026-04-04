"""
Invoice API routes.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from api.schemas import BatchProcessResponse, ExportRequest, PipelineResponse
from core.config import Config
from core.pipeline import InvoicePipeline

router = APIRouter(prefix="/api", tags=["invoice"])
_pipeline = InvoicePipeline()


def _validate_upload(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in Config.VALID_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")


def _safe_json_loads(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


@router.post(
    "/process",
    response_model=PipelineResponse,
    summary="Xử lý 1 hóa đơn",
    description="Upload 1 ảnh hóa đơn, hệ thống sẽ chạy qua pipeline Detection -> Standardize -> OCR -> Groq Llama.",
)
async def process_invoice(
    file: UploadFile = File(...),
    user_id: str = Form(default=""),
    request_id: str = Form(default=""),
    metadata: str = Form(default=""),
) -> PipelineResponse:
    _validate_upload(file)
    data = await file.read()

    if len(data) > Config.MAX_IMAGE_BYTES:
        raise HTTPException(413, f"File too large. Max={Config.MAX_IMAGE_BYTES} bytes")

    meta_obj = _safe_json_loads(metadata)

    try:
        result = await run_in_threadpool(
            _pipeline.run,
            data,
            file.filename or "image.jpg",
            user_id,
            request_id,
            meta_obj,
        )
    except Exception as exc:
        raise HTTPException(500, f"Pipeline error: {exc}")

    return PipelineResponse(**result)


@router.post(
    "/process-batch",
    response_model=BatchProcessResponse,
    summary="Xử lý hàng loạt",
    description="Upload nhiều ảnh cùng lúc, hệ thống sẽ xử lý song song để tối ưu tốc độ.",
)
async def process_batch(
    files: list[UploadFile] = File(...),
    user_id: str = Form(default=""),
    metadata: str = Form(default=""),
) -> BatchProcessResponse:
    if not files:
        raise HTTPException(400, "No files uploaded")

    if len(files) > Config.BATCH_MAX_FILES:
        raise HTTPException(400, f"Too many files. Max={Config.BATCH_MAX_FILES}")

    meta_obj = _safe_json_loads(metadata)
    sem = asyncio.Semaphore(max(1, Config.BATCH_CONCURRENCY))

    async def _run_one(upload: UploadFile) -> PipelineResponse:
        _validate_upload(upload)
        data = await upload.read()
        if len(data) > Config.MAX_IMAGE_BYTES:
            raise HTTPException(413, f"File {upload.filename} too large")

        async with sem:
            payload = await run_in_threadpool(
                _pipeline.run,
                data,
                upload.filename or "image.jpg",
                user_id,
                "",
                meta_obj,
            )
            return PipelineResponse(**payload)

    tasks = [_run_one(file) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses: list[PipelineResponse] = []
    success_count = 0
    fail_count = 0

    for item in results:
        if isinstance(item, Exception):
            fail_count += 1
            responses.append(
                PipelineResponse(
                    request_id="",
                    status="fail",
                    message=str(item),
                    has_bill=False,
                    needs_review=True,
                    result=None,
                    structured=None,
                    raw=None,
                    meta=None,
                    orig_image=None,
                    detect_image=None,
                    proc_image=None,
                    log_path="",
                )
            )
            continue

        responses.append(item)
        if item.status == "success":
            success_count += 1
        else:
            fail_count += 1

    return BatchProcessResponse(
        total=len(files),
        success_count=success_count,
        fail_count=fail_count,
        results=responses,
    )


@router.get(
    "/result/{request_id}",
    response_model=PipelineResponse,
    summary="Xem kết quả cũ",
    description="Tra cứu lại thông tin hóa đơn đã xử lý dựa trên Request ID (lấy từ log hệ thống).",
)
async def get_result(request_id: str) -> PipelineResponse:
    log_path = Config.LOGS_DIR / f"{request_id}.json"
    if not log_path.exists():
        raise HTTPException(404, "Not found")

    data = json.loads(log_path.read_text(encoding="utf-8"))
    payload = {
        "request_id": request_id,
        "status": data.get("status", "unknown"),
        "message": data.get("message", ""),
        "has_bill": bool(data.get("status") == "success"),
        "needs_review": bool((data.get("validation") or {}).get("needs_review", False)),
        "result": data.get("result"),
        "structured": data.get("structured"),
        "raw": data.get("raw"),
        "meta": data.get("meta"),
        "orig_image": data.get("orig_image"),
        "detect_image": data.get("detector_image"),
        "proc_image": data.get("proc_image"),
        "log_path": str(log_path),
    }
    return PipelineResponse(**payload)


@router.post(
    "/export-csv",
    summary="Xuất CSV",
    description="Nhận danh sách Request ID và trả về file CSV chứa thông tin tổng hợp.",
)
async def export_csv(body: ExportRequest) -> StreamingResponse:
    rows: list[dict] = []
    for req_id in body.request_ids:
        log_path = Config.LOGS_DIR / f"{req_id}.json"
        if not log_path.exists():
            continue

        log = json.loads(log_path.read_text(encoding="utf-8"))
        result = log.get("result") or {}
        rows.append(
            {
                "id": req_id,
                "seller": result.get("SELLER", ""),
                "total": result.get("TOTAL_COST", ""),
                "status": log.get("status", ""),
                "needs_review": bool((log.get("validation") or {}).get("needs_review", False)),
            }
        )

    if not rows:
        raise HTTPException(404, "No results")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
