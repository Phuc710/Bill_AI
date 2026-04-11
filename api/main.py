"""
BillAI — FastAPI Application Entry Point
"""
from __future__ import annotations

import os
# Suppress ONNX Runtime CUDA missing DLL warnings on CPU environments
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["ORT_LOGGING_LEVEL"]    = "4"

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.middleware import AuthLoggingMiddleware
from api.routes.bills import router as bills_router
from api.routes.dashboard import router as dashboard_router
from core.config import Config


# ── Colored Logging ────────────────────────────────────────────────────────────

class _ColoredFormatter(logging.Formatter):
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    LEVEL_COLORS = {
        logging.DEBUG:    "\033[36m",
        logging.INFO:     "\033[32m",
        logging.WARNING:  "\033[33m",
        logging.ERROR:    "\033[31m",
        logging.CRITICAL: "\033[1m\033[31m",
    }
    NAME_COLORS = {
        "billai.access":   "\033[34m",
        "billai.routes":   "\033[35m",
        "billai.pipeline": "\033[36m",
        "billai.db":       "\033[33m",
        "billai.main":     "\033[32m",
    }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        name_color  = self.NAME_COLORS.get(record.name, "\033[37m")
        ts          = self.formatTime(record, self.datefmt)
        level_badge = f"{level_color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        name_str    = f"{name_color}{record.name}{self.RESET}"
        colored_msg = f"{level_color}{record.getMessage()}{self.RESET}"
        line = f"{self.DIM}{ts}{self.RESET} | {level_badge} | {name_str} | {colored_msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def _setup_logging() -> None:
    datefmt   = "%Y-%m-%d %H:%M:%S"
    plain_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    console   = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColoredFormatter(datefmt=datefmt))
    Config.ensure_dirs()
    file_handler = logging.FileHandler(Config.LOGS_DIR / "api.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(plain_fmt, datefmt=datefmt))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
    for noisy in ("uvicorn.error", "watchfiles", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger("billai.main")


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("BillAI Backend starting up  (v1.0.0)")
    log.info(f"  Groq model   : {Config.GROQ_MODEL}")
    log.info(f"  Supabase URL : {Config.SUPABASE_URL or '(not set)'}")
    log.info(f"  API Key set  : {'YES' if Config.API_SECRET_KEY else 'NO — INSECURE'}")
    log.info("=" * 60)
    yield
    log.info("BillAI Backend shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "BillAI — Invoice Extraction API",
    version     = "1.0.0",
    description = """\
Hệ thống trích xuất & chuẩn hóa hóa đơn thông minh dành cho Android client.
## 📎 Lưu ý
- `user_id` phải là UUID hợp lệ từ Supabase Auth — ví dụ: `550e8400-e29b-41d4-a716-446655440000`
- Tất cả endpoint Bills đều cần header `X-API-Key`
- `/health` và `/dashboard` không cần key
""",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    openapi_tags = [
        {"name": "Bills",     "description": "📄 Upload, truy vấn, cập nhật & xóa hóa đơn"},
        {"name": "Dashboard", "description": "📊 Trang Admin dashboard"},
        {"name": "System",    "description": "⚙️ Health check & thông tin hệ thống"},
    ],
)


# ── Middleware ──────────────────────────────────────────────────────────────────

app.add_middleware(AuthLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── OpenAPI — Authorize button ─────────────────────────────────────────────────

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title       = app.title,
        version     = app.version,
        description = app.description,
        routes      = app.routes,
        tags        = app.openapi_tags,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "ApiKeyAuth": {
            "type":        "apiKey",
            "in":          "header",
            "name":        "X-API-Key",
            "description": "Dán API Secret Key vào đây.",
        }
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema

app.openapi = _custom_openapi


# ── Static files ───────────────────────────────────────────────────────────────

_static_dir = Config.BASE_DIR / "api" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(bills_router)
app.include_router(dashboard_router)


# ── Extra routes ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/dashboard")


@app.api_route("/health", methods=["GET", "HEAD"], tags=["System"],
               summary="Health check", description="Kiểm tra server đang hoạt động. Không cần API Key.")
async def health() -> dict:
    return {
        "status":               "ok",
        "version":              "1.0.0",
        "model":                Config.GROQ_MODEL,
        "supabase_configured":  bool(Config.SUPABASE_URL and Config.SUPABASE_SERVICE_KEY),
    }
