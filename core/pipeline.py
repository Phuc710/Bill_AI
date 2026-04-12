"""
Invoice Pipeline — Respond-First Architecture.

NEW FLOW (tối ưu tốc độ phản hồi user):
  1. Load image
  2. OCR (VnCV) — chạy song song với DB create row (nhẹ)
  3. Groq LLM extraction + math validate
  4. ★ RESPOND to user IMMEDIATELY ★
  5. [Background] Upload ảnh + Save full result vào Supabase

DB status transitions:
  processing → completed
             → failed
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
import traceback
from typing import Any, Dict, List, Optional

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
        tracker = PipelineTracker(request_id=request_id or bill_id[:12], user_id=user_id)
        t0 = time.perf_counter()
        log.info(f"[{tracker.request_id}] START bill={bill_id} file={filename}")

        try:
            # ── Step 1: Load & validate image ─────────────────────────────────
            image = await asyncio.to_thread(self._load, image_bytes, filename)

            # ── Step 2: OCR + DB create row song song (DB create là nhẹ) ──────
            async def _db_init_task():
                try:
                    await asyncio.to_thread(
                        DatabaseService.update_status_safe, bill_id, user_id, "processing"
                    )
                except Exception as exc:
                    log.warning(f"[{tracker.request_id}] DB init warning (non-fatal): {exc}")

            async def _ocr_task():
                tracker.start_step("ocr_ms")
                res = await asyncio.to_thread(ocr_extract_text, image)
                ocr_ms = tracker.end_step("ocr_ms")
                return res, ocr_ms

            log.info(f"[{tracker.request_id}] OCR + DB init → parallel start")
            ocr_result, _ = await asyncio.gather(
                _ocr_task(),
                _db_init_task(),
            )
            ocr, ocr_ms = ocr_result

            tracker.set_ocr(ocr.text_raw or "", ocr.confidence_avg, ocr.preprocess_mode)
            log.info(
                f"[{tracker.request_id}] OCR done "
                f"mode={ocr.preprocess_mode} chars={len(ocr.text_raw or '')} "
                f"conf={ocr.confidence_avg:.3f} | {ocr_ms:.0f}ms"
            )

            # Guard: không quét được chữ nào — respond failed ngay, bg update DB
            if not (ocr.text_raw or "").strip():
                log.warning(f"[{tracker.request_id}] OCR empty — aborting")
                asyncio.ensure_future(
                    asyncio.to_thread(
                        DatabaseService.mark_failed, bill_id, "ocr", "Không tìm thấy văn bản trên ảnh"
                    )
                )
                return failed_api_response(
                    bill_id, "ocr",
                    "Không tìm thấy hóa đơn (None Text Detected)",
                    None, t0,
                )

            # ── Step 3: Groq LLM ─────────────────────────────────────────────
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

            # ── Step 4: Build API response ────────────────────────────────────
            # ★ Dùng None cho orig_url vì upload chưa xong — app sẽ load từ DB sau ★
            api_response = internal_to_api_response(
                internal = internal,
                bill_id  = bill_id,
                orig_url = None,        # sẽ có sau khi bg upload xong
            )
            tracker.set_result(api_response)
            tracker.set_status("completed", message=internal.get("summary", ""))

            respond_ms = (time.perf_counter() - t0) * 1000
            log.info(
                f"[{tracker.request_id}] ★ RESPOND at {respond_ms:.0f}ms "
                f"| OCR: {ocr_ms:.0f}ms | LLM: {llm_ms:.0f}ms"
            )

            # ── Step 5: Fire-and-forget background save ───────────────────────
            asyncio.ensure_future(
                self._background_save(
                    bill_id       = bill_id,
                    image         = image,
                    internal      = internal,
                    ocr           = ocr,
                    raw_response  = raw_response,
                    math_warnings = math_warnings,
                    error_type    = error_type,
                    respond_ms    = respond_ms,
                    request_id    = tracker.request_id,
                )
            )

            return api_response

        except Exception as exc:
            stack = traceback.format_exc(limit=5)
            log.error(f"[{tracker.request_id}] UNCAUGHT: {exc}\n{stack}")
            asyncio.ensure_future(
                asyncio.to_thread(DatabaseService.mark_failed, bill_id, "unknown", str(exc)[:400])
            )
            return failed_api_response(bill_id, "unknown", str(exc)[:200], None, t0)

    # ── Background save (chạy sau khi đã respond user) ────────────────────────

    async def _background_save(
        self,
        bill_id: str,
        image: Image.Image,
        internal: Dict[str, Any],
        ocr: Any,
        raw_response: str,
        math_warnings: Optional[List[str]],
        error_type: Optional[str],
        respond_ms: float,
        request_id: str,
    ) -> None:
        """
        Chạy hoàn toàn sau khi đã respond cho user.
        Upload ảnh + lưu đầy đủ kết quả vào Supabase.
        """
        t_bg = time.perf_counter()
        try:
            # Upload ảnh lên Supabase Storage
            orig_url = await asyncio.to_thread(
                StorageService.upload_image, image, bill_id, "Original"
            )

            if error_type or math_warnings:
                log.warning(
                    f"[{request_id}] BG QUALITY WARNING "
                    f"conf={ocr.confidence_avg:.2f} total={internal.get('total')} "
                    f"err={error_type} math={bool(math_warnings)}"
                )

            items      = internal.get("items") or []
            db_payload = internal_to_db(internal)

            # Tính total processing time (từ đầu đến khi save xong)
            total_ms = respond_ms + (time.perf_counter() - t_bg) * 1000

            await asyncio.to_thread(
                DatabaseService.save_result,
                invoice_id     = bill_id,
                db_payload     = db_payload,
                items          = items,
                ocr_raw_text   = ocr.text_raw or "",
                llm_raw        = raw_response,
                orig_url       = orig_url,
                ocr_confidence = ocr.confidence_avg,
                processing_ms  = total_ms,
            )

            bg_ms = (time.perf_counter() - t_bg) * 1000
            log.info(
                f"[{request_id}] BG SAVE done "
                f"store='{internal.get('store_name')}' total={internal.get('total')} "
                f"url={'ok' if orig_url else 'skip'} | bg_save: {bg_ms:.0f}ms"
            )

        except Exception as exc:
            log.error(f"[{request_id}] BG SAVE FAILED: {exc}")
            try:
                await asyncio.to_thread(
                    DatabaseService.mark_failed, bill_id, "bg_save", str(exc)[:400]
                )
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load(self, image_bytes: bytes, filename: str) -> Image.Image:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        if max(w, h) > Config.MAX_INPUT_SIDE:
            s   = Config.MAX_INPUT_SIDE / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
        return img
