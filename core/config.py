"""
Central configuration for Bill AI standard pipeline.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    BASE_DIR: Path = _BASE_DIR
    FAST_MODE: bool = _env_bool("FAST_MODE", True)  # Skip detection/standardize

    # Paths
    LOGS_DIR: Path = _BASE_DIR / "logs"
    OUTPUTS_DIR: Path = _BASE_DIR / "outputs"
    EXTRACTION_PROMPT: Path = _BASE_DIR / "extraction_vi.txt"

    # Detector (YOLOv8)
    DETECTOR_MODEL_PATH: Path = _BASE_DIR / "models" / "detec.pt"
    DETECTOR_CONF_THRESHOLD: float = _env_float("DETECTOR_CONF_THRESHOLD", 0.40)

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_MAX_INPUT_CHARS: int = _env_int("GEMINI_MAX_INPUT_CHARS", 2200)
    GEMINI_MAX_INPUT_LINES: int = _env_int("GEMINI_MAX_INPUT_LINES", 120)
    GEMINI_RETRY_DELAY: float = _env_float("GEMINI_RETRY_DELAY", 0.0)

    # Upload/input validation
    VALID_EXTENSIONS: set[str] = {
        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"
    }
    MAX_IMAGE_BYTES: int = _env_int("MAX_IMAGE_BYTES", 10 * 1024 * 1024)
    MIN_IMAGE_SIDE: int = _env_int("MIN_IMAGE_SIDE", 180)
    MAX_INPUT_SIDE: int = _env_int("MAX_INPUT_SIDE", 2600)

    # OCR quality threshold
    OCR_MIN_CONF: float = _env_float("OCR_MIN_CONF", 0.35)

    # API throughput controls
    BATCH_MAX_FILES: int = _env_int("BATCH_MAX_FILES", 10)
    BATCH_CONCURRENCY: int = _env_int("BATCH_CONCURRENCY", 3)

    # Debug output
    SAVE_DEBUG_IMAGES: bool = _env_bool("SAVE_DEBUG_IMAGES", True)
    PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "bill_ai_v4_detect_first")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
