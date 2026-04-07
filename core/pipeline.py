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
    ) -> Dict[str, Any]:
        import asyncio
        t0 = time.perf_counter()
        log.info(f"[{bill_id}] Pipeline START | file={filename} user={user_id}")

        # ── DB: tạo row ban đầu ───────────────────────────────────────────────
        try:
            await asyncio.to_thread(DatabaseService.create_invoice, bill_id, user_id)
        except Exception as exc:
            log.error(f"[{bill_id}] DB create failed: {exc}")
            return failed_api_response(bill_id, "db_init", "DB error", t0=t0)

        orig_url: Optional[str] = None

        try:
            # ── Step 1: Load & validate image ─────────────────────────────────
            image = await asyncio.to_thread(self._load, image_bytes, filename)

            # ── Step 2 & 3: Upload & OCR song song (Parallel) ─────────────────
            async def _upload_task():
                await asyncio.to_thread(DatabaseService.update_status, bill_id, "detecting")
                return await asyncio.to_thread(StorageService.upload_image, image, bill_id, "Original")

            async def _ocr_task():
                # We do not set status to OCR done at the start of OCR task, we do it after.
                t_ocr = time.perf_counter()
                res = await asyncio.to_thread(ocr_extract_text, image)
                return res, (time.perf_counter() - t_ocr) * 1000

            log.info(f"[{bill_id}] Starting Upload & OCR concurrently")
            upload_task = asyncio.create_task(_upload_task())
            ocr_task = asyncio.create_task(_ocr_task())

            orig_url, (ocr, ocr_ms) = await asyncio.gather(upload_task, ocr_task)
            log.info(f"[{bill_id}] Uploaded original: {orig_url}")

            if ocr.error_type:
                log.warning(
                    f"[{bill_id}] OCR error | type={ocr.error_type} | {ocr.error_message}"
                )

            await asyncio.to_thread(
                DatabaseService.update_status,
                bill_id, "ocr_done",
                ocr_raw_text=ocr.text_raw or "",
            )
            log.info(
                f"[{bill_id}] OCR done | mode={ocr.preprocess_mode} | "
                f"chars={len(ocr.text_raw or '')} | conf={ocr.confidence_avg:.3f} | "
                f"time={ocr_ms:.0f}ms"
            )

            # Guard: không quét được chữ nào
            if not (ocr.text_raw or "").strip():
                await asyncio.to_thread(DatabaseService.mark_failed, bill_id, "ocr", "Không tìm thấy văn bản trên ảnh")
                log.warning(f"[{bill_id}] OCR empty — pipeline failed")
                return failed_api_response(
                    bill_id, "ocr",
                    "Không tìm thấy hóa đơn (None Text Detected)",
                    orig_url, t0,
                )

            # ── Step 4: Groq Llama 3.3 70B Normalize ─────────────────────────
            await asyncio.to_thread(DatabaseService.update_status, bill_id, "normalizing")
            t_llm = time.perf_counter()
            extraction = await asyncio.to_thread(self._extractor.extract, ocr_text=ocr.text_raw)
            llm_ms = (time.perf_counter() - t_llm) * 1000

            internal    = extraction.get("internal") or {}
            raw_response = extraction.get("raw_response", "")
            error_type   = extraction.get("error_type")
            math_warnings = internal.pop("_math_warnings", None)

            log.info(
                f"[{bill_id}] LLM done | error={error_type} | "
                f"total={internal.get('total')} | time={llm_ms:.0f}ms"
            )

            # ── Step 5: Validate & map ────────────────────────────────────────
            processing_ms = (time.perf_counter() - t0) * 1000
            needs_review  = self._needs_review(
                internal, ocr.confidence_avg, error_type, math_warnings
            )

            # ── Step 6: Save to Supabase ──────────────────────────────────────
            items: List[Dict[str, Any]] = internal.get("items") or []
            db_payload = internal_to_db(internal)

            await asyncio.to_thread(
                DatabaseService.save_result,
                invoice_id      = bill_id,
                db_payload      = db_payload,
                items           = items,
                ocr_raw_text    = ocr.text_raw or "",
                llm_raw         = raw_response,
                orig_url        = orig_url,
                ocr_confidence  = ocr.confidence_avg,
                processing_ms   = processing_ms,
                needs_review    = needs_review,
            )
            log.info(
                f"[{bill_id}] COMPLETED | store={internal.get('store_name')} | "
                f"total={internal.get('total')} | "
                f"ocr={ocr_ms:.0f}ms | llm={llm_ms:.0f}ms | total={processing_ms:.0f}ms"
            )

            # ── Step 7: Return clean API response ────────────────────────────
            return internal_to_api_response(
                internal      = internal,
                bill_id       = bill_id,
                orig_url      = orig_url,
                ocr_error     = ocr.error_type,
                llm_error     = error_type,
                processing_ms = processing_ms,
                needs_review  = needs_review,
            )

        except Exception as exc:
            stack = traceback.format_exc(limit=5)
            log.error(f"[{bill_id}] UNCAUGHT: {exc}\n{stack}")
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

    @staticmethod
    def _needs_review(
        internal: Dict[str, Any],
        ocr_conf: float,
        llm_error: Optional[str],
        math_warnings: Optional[List[str]] = None,
    ) -> bool:
        """
        Flag needs_review = True khi:
          - LLM gặp lỗi (quota, empty, v.v.)
          - OCR confidence quá thấp
          - Tổng tiền = 0 (không trích được total)
          - Có cảnh báo số học (qty × unit_price ≠ amount)
        """
        if llm_error:
            return True
        if ocr_conf < Config.OCR_MIN_CONF:
            return True
        if int(internal.get("total") or 0) <= 0:
            return True
        if math_warnings:
            return True
        return False
