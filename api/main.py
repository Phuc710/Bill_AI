"""
Bill AI — FastAPI application entry point (Production).

Logging format (colored):
  2026-04-02 14:00:00 | INFO     | billai.access | [abc123] POST /bills/extract | status=200 | 8200ms
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from api.middleware import AuthLoggingMiddleware
from api.routes.bills import router as bills_router
from core.config import Config

# Header definition for Swagger UI
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ── Colored Logging ────────────────────────────────────────────────────────────

class _ColoredFormatter(logging.Formatter):
    """ANSI-colored log formatter for terminal output."""

    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"

    LEVEL_COLORS = {
        logging.DEBUG:    "\033[36m",          # Cyan
        logging.INFO:     "\033[32m",          # Green
        logging.WARNING:  "\033[33m",          # Yellow
        logging.ERROR:    "\033[31m",          # Red
        logging.CRITICAL: "\033[1m\033[31m",  # Bold Red
    }

    # Color per logger name prefix
    NAME_COLORS = {
        "billai.access":   "\033[34m",   # Blue
        "billai.routes":   "\033[35m",   # Magenta
        "billai.pipeline": "\033[36m",   # Cyan
        "billai.db":       "\033[33m",   # Yellow
        "billai.main":     "\033[32m",   # Green
    }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        name_color  = self.NAME_COLORS.get(record.name, "\033[37m")  # White fallback

        # Timestamp — dim grey
        ts  = self.formatTime(record, self.datefmt)
        dim = self.DIM
        rst = self.RESET

        # Level badge
        level_badge = f"{level_color}{self.BOLD}{record.levelname:<8}{rst}"

        # Logger name
        name_str = f"{name_color}{record.name}{rst}"

        # Message
        msg = record.getMessage()
        colored_msg = f"{level_color}{msg}{rst}"

        line = f"{dim}{ts}{rst} | {level_badge} | {name_str} | {colored_msg}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


def _setup_logging() -> None:
    datefmt = "%Y-%m-%d %H:%M:%S"
    plain_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # ── Console: colored output ──────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColoredFormatter(datefmt=datefmt))

    # ── File: plain text (no ANSI codes) ────────────────────────────────────
    Config.ensure_dirs()
    file_handler = logging.FileHandler(
        Config.LOGS_DIR / "api.log", encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(plain_fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)

    # Silence noisy libraries
    for noisy in ("uvicorn.error", "watchfiles", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger("billai.main")


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Bill AI Backend starting up")
    log.info(f"  Groq model    : {Config.GROQ_MODEL}")
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
`Upload → Detect (YOLO) → Crop → OCR (VnCV) → Normalize (Groq) → Supabase`

### Authentication
Mọi request phải có header: `X-API-Key: <secret>`
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(api_key_header)],
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
        "model": Config.GROQ_MODEL,
        "supabase_configured": bool(Config.SUPABASE_URL and Config.SUPABASE_SERVICE_KEY),
    }
