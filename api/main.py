"""
FastAPI application — entry point.

Run:  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes.invoice import router
from core.config import Config

_BASE = Path(__file__).resolve().parent.parent
_FRONTEND = _BASE / "frontend"


# ── Startup ───────────────────────────────────────────────────────────────────

# Ensure necessary directories exist before mounting static files
Config.ensure_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ Bill AI ready — http://localhost:8000")
    yield
    # Shutdown: nothing to clean up


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Bill AI — Invoice Extraction",
    description="YOLOv8 + EasyOCR + Gemini Flash pipeline for Vietnamese invoices.",
    version="2.2.0",
    lifespan=lifespan,
)

# CORS — allow all during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────

app.include_router(router)

# Static mounts
app.mount("/outputs", StaticFiles(directory=str(Config.OUTPUTS_DIR)), name="outputs")
app.mount("/assets",  StaticFiles(directory=str(_FRONTEND)),          name="assets")


@app.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    return FileResponse(_FRONTEND / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "2.2.0"}
