"""
Invoice Pipeline — Production Flow (Clean).

Upload → OCR (VnCV, standard→aggressive fallback)
       → Normalize (Groq Llama 3.3 70B)
       → Validate (math check)
       → Save (Supabase invoices + invoice_items)
       → Respond (1 schema duy nhất cho app)

DB status transitions:
  uploaded → ocr_done → normalizing → completed
                                    → failed
"""
from __future__ import annotations

import io
import logging
import time
import traceback
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

from core.config import Config
from core.database import DatabaseService
from core.groq_extractor import GroqExtractor
from core.logger import PipelineTracker
from core.mapper import failed_api_response, internal_to_api_response, internal_to_db
from core.ocr import extract_text as ocr_extract_text
from core.storage import StorageService

log = logging.getLogger("billai.pipeline")


class InvoicePipeline:
    def __init__(self) -> None:
        self._extractor = GroqExtractor()

    # ── Main entry ────────────────────────────────────────────────────────────

    async def run(
        self,
        image_bytes: bytes,
        filename: str,
        user_id: str,
        bill_id: str,
        request_id: str = "",
    ) -> Dict[str, Any]:
        import asyncio
        tracker = PipelineTracker(request_id=request_id or bill_id[:12], user_id=user_id)
        t0 = time.perf_counter()
        log.info(f"[{tracker.request_id}] START bill={bill_id} file={filename}")

        # ── DB: tạo row ban đầu ───────────────────────────────────────────────
        try:
            await asyncio.to_thread(DatabaseService.create_invoice, bill_id, user_id)
        except Exception as exc:
            log.error(f"[{tracker.request_id}] DB init FAILED: {exc}")
            return failed_api_response(bill_id, "db_init", "DB error", t0=t0)

        orig_url: Optional[str] = None

        try:
            # ── Step 1: Load & validate image ─────────────────────────────────
            image = await asyncio.to_thread(self._load, image_bytes, filename)

            # ── Step 2 & 3: Upload & OCR song song (Parallel) ─────────────────
            async def _upload_task():
                # Set detecting trước khi upload
                await asyncio.to_thread(DatabaseService.update_status, bill_id, "detecting")
                return await asyncio.to_thread(StorageService.upload_image, image, bill_id, "Original")

            async def _ocr_task():
                tracker.start_step("ocr_ms")
                res = await asyncio.to_thread(ocr_extract_text, image)
                ocr_ms = tracker.end_step("ocr_ms")
                return res, ocr_ms

            log.info(f"[{tracker.request_id}] Upload + OCR → parallel start")
            upload_task = asyncio.create_task(_upload_task())
            ocr_task    = asyncio.create_task(_ocr_task())

            orig_url, (ocr, ocr_ms) = await asyncio.gather(upload_task, ocr_task)

            tracker.set_ocr(ocr.text_raw or "", ocr.confidence_avg, ocr.preprocess_mode)

            # Một lần update DB duy nhất sau khi cả 2 task xong
            await asyncio.to_thread(
                DatabaseService.update_status,
                bill_id, "ocr_done",
                ocr_raw_text=ocr.text_raw or "",
            )
            log.info(
                f"[{tracker.request_id}] OCR done "
                f"mode={ocr.preprocess_mode} chars={len(ocr.text_raw or '')} "
                f"conf={ocr.confidence_avg:.3f} | {ocr_ms:.0f}ms"
            )

            # Guard: không quét được chữ nào
            if not (ocr.text_raw or "").strip():
                await asyncio.to_thread(DatabaseService.mark_failed, bill_id, "ocr", "Không tìm thấy văn bản trên ảnh")
                log.warning(f"[{tracker.request_id}] OCR empty — pipeline aborted")
                return failed_api_response(
                    bill_id, "ocr",
                    "Không tìm thấy hóa đơn (None Text Detected)",
                    orig_url, t0,
                )

            # ── Step 4: Groq Llama 3.3 70B Normalize ─────────────────────────
            # Không update_status("normalizing") ở đây để tiết kiệm 1 DB round-trip
            tracker.start_step("llm_ms")
            extraction = await asyncio.to_thread(self._extractor.extract, ocr_text=ocr.text_raw)
            llm_ms = tracker.end_step("llm_ms")

            internal      = extraction.get("internal") or {}
            raw_response  = extraction.get("raw_response", "")
            error_type    = extraction.get("error_type")
            math_warnings = internal.pop("_math_warnings", None)

            tracker.set_llm(raw_response)
            log.info(
                f"[{tracker.request_id}] LLM done "
                f"total={internal.get('total')} err={error_type} | {llm_ms:.0f}ms"
            )

            # ── Step 5: Processing metrics (backend only) ─────────────────────
            processing_ms = (time.perf_counter() - t0) * 1000
            if error_type or math_warnings:
                log.warning(
                    f"[{tracker.request_id}] QUALITY WARNING "
                    f"conf={ocr.confidence_avg:.2f} total={internal.get('total')} "
                    f"err={error_type} math={bool(math_warnings)}"
                )

            # ── Step 6: Save to Supabase ──────────────────────────────────────
            items      = internal.get("items") or []
            db_payload = internal_to_db(internal)
            await asyncio.to_thread(
                DatabaseService.save_result,
                invoice_id     = bill_id,
                db_payload     = db_payload,
                items          = items,
                ocr_raw_text   = ocr.text_raw or "",
                llm_raw        = raw_response,
                orig_url       = orig_url,
                ocr_confidence = ocr.confidence_avg,
                processing_ms  = processing_ms,
            )

            log.info(
                f"[{tracker.request_id}] DONE "
                f"store='{internal.get('store_name')}' total={internal.get('total')} "
                f"| OCR: {ocr_ms:.0f}ms | LLM: {llm_ms:.0f}ms | TOTAL: {processing_ms:.0f}ms"
            )

            api_response = internal_to_api_response(
                internal = internal,
                bill_id  = bill_id,
                orig_url = orig_url,
            )
            tracker.set_result(api_response)
            tracker.set_status("completed", message=internal.get("summary", ""))
            return api_response

        except Exception as exc:
            stack = traceback.format_exc(limit=5)
            log.error(f"[{tracker.request_id}] UNCAUGHT: {exc}\n{stack}")
            try:
                await asyncio.to_thread(DatabaseService.mark_failed, bill_id, "unknown", str(exc)[:400])
            except Exception:
                pass
            return failed_api_response(bill_id, "unknown", str(exc)[:200], orig_url, t0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load(self, image_bytes: bytes, filename: str) -> Image.Image:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        if max(w, h) > Config.MAX_INPUT_SIDE:
            s   = Config.MAX_INPUT_SIDE / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
        return img
