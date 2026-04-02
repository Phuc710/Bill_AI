"""
Central configuration for Bill AI backend.
All values are loaded from environment variables (.env).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, ""))
    except (ValueError, TypeError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    BASE_DIR: Path = _BASE_DIR
    LOGS_DIR: Path = _BASE_DIR / "logs"
    OUTPUTS_DIR: Path = _BASE_DIR / "outputs"
    EXTRACTION_PROMPT: Path = _BASE_DIR / "extraction_vi.txt"

    # ── Model ──────────────────────────────────────────────────────────────
    DETECTOR_MODEL_PATH: Path = _BASE_DIR / "models" / "detec.pt"
    DETECTOR_CONF_THRESHOLD: float = _env_float("DETECTOR_CONF_THRESHOLD", 0.10)

    # ── Gemini ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    GEMINI_MAX_INPUT_CHARS: int = _env_int("GEMINI_MAX_INPUT_CHARS", 2200)
    GEMINI_MAX_INPUT_LINES: int = _env_int("GEMINI_MAX_INPUT_LINES", 120)
    GEMINI_RETRY_DELAY: float = _env_float("GEMINI_RETRY_DELAY", 0.0)

    # ── Security ───────────────────────────────────────────────────────────
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "")

    # ── Supabase ───────────────────────────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "Bills")

    # ── Input validation ───────────────────────────────────────────────────
    VALID_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    MAX_IMAGE_BYTES: int = _env_int("MAX_IMAGE_BYTES", 10 * 1024 * 1024)
    MIN_IMAGE_SIDE: int = _env_int("MIN_IMAGE_SIDE", 180)
    MAX_INPUT_SIDE: int = _env_int("MAX_INPUT_SIDE", 2600)
    OCR_MIN_CONF: float = _env_float("OCR_MIN_CONF", 0.35)

    # ── Batch ──────────────────────────────────────────────────────────────
    BATCH_MAX_FILES: int = _env_int("BATCH_MAX_FILES", 10)
    BATCH_CONCURRENCY: int = _env_int("BATCH_CONCURRENCY", 3)

    # ── Pipeline ───────────────────────────────────────────────────────────
    PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "bill_ai_v7_supabase")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
