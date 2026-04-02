"""
Bill AI — FastAPI application entry point (Production).

Logging format:
  2026-04-02 14:00:00 | INFO     | billai.access | [abc123] POST /bills/extract | status=200 | 8200ms | ip=1.2.3.4 | user=uid
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import AuthLoggingMiddleware
from api.routes.bills import router as bills_router
from core.config import Config

# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # File handler — persistent logs
    Config.ensure_dirs()
    file_handler = logging.FileHandler(
        Config.LOGS_DIR / "api.log", encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    root.addHandler(file_handler)

    # Silence noisy libs
    for noisy in ("uvicorn.error", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger("billai.main")


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Bill AI Backend starting up")
    log.info(f"  Gemini model  : {Config.GEMINI_MODEL}")
    log.info(f"  Supabase URL  : {Config.SUPABASE_URL or '(not set)'}")
    log.info(f"  Bucket        : {Config.SUPABASE_BUCKET}")
    log.info(f"  API Key set   : {'YES' if Config.API_SECRET_KEY else 'NO — SERVER INSECURE'}")
    log.info("=" * 60)
    yield
    log.info("Bill AI Backend shutting down")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Bill AI — Invoice Extraction API",
    description="""
Hệ thống trích xuất hóa đơn thông minh dành cho Android client.

### Pipeline
`Upload → Detect (YOLO) → Crop → OCR (VnCV) → Normalize (Gemini) → Supabase`

### Authentication
Mọi request phải có header: `X-API-Key: <secret>`
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(AuthLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(bills_router)


@app.get("/health", tags=["System"])
async def health() -> dict:
    """Server health check — no auth required."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "model": Config.GEMINI_MODEL,
        "supabase_configured": bool(Config.SUPABASE_URL and Config.SUPABASE_SERVICE_KEY),
    }
