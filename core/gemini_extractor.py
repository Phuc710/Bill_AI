"""
GeminiExtractor — sends OCR text to Gemini Flash, returns structured JSON.

Output schema:
  {
    "SELLER":     str,
    "ADDRESS":    str,
    "TIMESTAMP":  str,
    "PRODUCTS":   [{"PRODUCT": str, "NUM": number, "VALUE": number}],
    "TOTAL_COST": number
  }
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

from core.config import Config


# ── Prompt ────────────────────────────────────────────────────────────────

def _load_prompt() -> str:
    p = Config.EXTRACTION_PROMPT
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    # Inline fallback — kept short for speed (fewer input tokens → faster)
    return (
        "Extract invoice data as JSON:\n"
        '{"SELLER":"","ADDRESS":"","TIMESTAMP":"","PRODUCTS":[{"PRODUCT":"","NUM":0,"VALUE":0}],"TOTAL_COST":0}\n'
        "Rules: Vietnamese text, NUM/VALUE/TOTAL_COST numeric, output JSON only."
    )


_EMPTY: Dict[str, Any] = {
    "SELLER": "", "ADDRESS": "", "TIMESTAMP": "",
    "PRODUCTS": [], "TOTAL_COST": 0,
}

# Regex: strip markdown code fences in one pass
_FENCE_RE = re.compile(r"^```(?:json)?\s*|```\s*$", re.MULTILINE)
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class GeminiExtractor:
    """Thin Gemini Flash wrapper — sync for simplicity, run via threadpool."""

    MAX_RETRIES = 3
    BASE_DELAY  = 1.0

    def __init__(self) -> None:
        self._prompt_template = _load_prompt()
        self._client = None      # lazy

    # ── Lazy client ───────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is not None:
            return
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self._client = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={"temperature": 0.1, "top_p": 0.8, "candidate_count": 1},
        )
        print(f"[Gemini] Model ready: {Config.GEMINI_MODEL}")

    # ── Public API ────────────────────────────────────────────────────────

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        """OCR plain text → structured dict."""
        if not ocr_text.strip():
            return dict(_EMPTY)

        self._ensure_client()
        prompt = (
            f"{self._prompt_template}\n\n"
            f"--- OCR TEXT ---\n{ocr_text}\n--- END ---\n\n"
            f"Return JSON only."
        )
        raw = self._call(prompt)
        return _parse_response(raw)

    # ── Retry logic ───────────────────────────────────────────────────────

    def _call(self, prompt: str) -> str:
        last_err: Exception = RuntimeError("no attempt")
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = self._client.generate_content(prompt)
                return resp.text
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                retryable = any(k in msg for k in ("quota", "429", "503", "unavailable"))
                if retryable and attempt < self.MAX_RETRIES:
                    delay = min(self.BASE_DELAY * (2 ** attempt), 30.0)
                    print(f"⏳ [Gemini] Retry {attempt+1}/{self.MAX_RETRIES} in {delay:.0f}s …")
                    time.sleep(delay)
                    continue
                raise
        raise last_err


# ── Response parsing (module-level, stateless) ────────────────────────────

def _parse_response(text: str) -> Dict[str, Any]:
    """Strip code fences, parse JSON, normalise numeric fields."""
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(cleaned)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                print(f"⚠️ [Gemini] Bad JSON: {text[:300]}")
                return dict(_EMPTY)
        else:
            print(f"⚠️ [Gemini] No JSON found: {text[:300]}")
            return dict(_EMPTY)

    # Normalise numbers
    data["TOTAL_COST"] = _num(data.get("TOTAL_COST", 0))
    for p in data.get("PRODUCTS", []):
        p["NUM"]   = _num(p.get("NUM", 0))
        p["VALUE"] = _num(p.get("VALUE", 0))
    return data


def _num(val: Any) -> float:
    """Coerce various formats to float."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = re.sub(r"[^\d,.]", "", val)
        # Vietnamese: 225.000 (dot = thousands), 225,000 (comma = thousands)
        if "." in s and "," not in s:
            s = s.replace(".", "")
        elif "," in s and "." not in s:
            s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            pass
    return 0.0
