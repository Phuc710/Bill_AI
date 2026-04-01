"""
Central configuration — single source of truth for paths, thresholds, and keys.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from project root ───────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


class Config:
    """All tunables live here.  Import once, use everywhere."""

    # ── Paths ─────────────────────────────────────────────────────────────
    BASE_DIR:    Path = _BASE_DIR
    DETEC_MODEL: Path = _BASE_DIR / "models" / "detec.pt"
    OCR_MODEL:   Path = _BASE_DIR / "models" / "ocr.pt"
    LOGS_DIR:    Path = _BASE_DIR / "logs"
    OUTPUTS_DIR: Path = _BASE_DIR / "outputs"
    EXTRACTION_PROMPT: Path = _BASE_DIR / "extraction_vi.txt"

    # ── Gemini ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL:   str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ── Detection thresholds ──────────────────────────────────────────────
    DETEC_CONF:      float = 0.10   # YOLO raw confidence floor
    DETEC_MIN_SCORE: float = 0.60   # Composite receipt-likeness score

    # ── OCR thresholds ────────────────────────────────────────────────────
    OCR_CONF: float = 0.30          # Minimum line confidence

    # ── Image constraints ─────────────────────────────────────────────────
    MAX_IMAGE_BYTES: int = 15 * 1024 * 1024      # 15 MB upload limit
    MAX_IMG_SIDE:    int = 1600                   # Longest side after resize
    VALID_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"})

    # ── Runtime flags ─────────────────────────────────────────────────────
    SAVE_DEBUG_IMAGES: bool = True   # Set False in prod to skip detect overlay

    # ── One-time directory creation (called at app startup only) ──────────
    @classmethod
    def ensure_dirs(cls) -> None:
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
