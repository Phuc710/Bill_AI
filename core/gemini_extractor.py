"""
Gemini extractor — structured invoice output from raw OCR text.

Error types returned in raw_response:
  [empty ocr]       — no text was given, skipped
  [no api key]      — GEMINI_API_KEY not configured
  [quota exceeded]  — 429, free-tier rate limit hit
  [gemini error]    — any other API error
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from core.config import Config


def _load_prompt() -> str:
    p = Config.EXTRACTION_PROMPT
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return (
        "Extract invoice fields from OCR text and return STRICT JSON only with keys: "
        "store_name,address,phone,invoice_id,datetime_in,datetime_out,cashier,table,"
        "items,subtotal,total,cash_given,cash_change,payment_method,raw_text"
    )


class GeminiExtractor:
    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._prompt = _load_prompt()
        self._client = None

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        raw_text = _prepare(ocr_text)
        if not raw_text:
            return self._empty("[empty ocr]", raw_text="")

        if not Config.GEMINI_API_KEY:
            return self._empty("[no api key]", raw_text=raw_text)

        self._ensure_client()
        prompt = f"OCR_TEXT:\n{raw_text}"
        raw_response = self._call(prompt)
        structured = _parse_response(raw_response, raw_text=raw_text)
        return {
            "legacy": _to_legacy(structured),
            "structured": structured,
            "raw_response": raw_response,
            "error_type": _classify_error(raw_response),
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self._client = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            system_instruction=self._prompt,
            generation_config={
                "temperature": 0.0,
                "top_p": 0.8,
                "candidate_count": 1,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json",
            },
        )

    def _call(self, prompt: str) -> str:
        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self._client.generate_content(prompt)
                text = _read_text(response)
                if text:
                    return text
                last_error = "[gemini empty]"
            except Exception as exc:
                msg = str(exc).lower()
                if any(t in msg for t in ("quota", "429", "rate")):
                    # Quota hit — no point retrying immediately
                    return f"[quota exceeded] {exc}"
                last_error = f"[gemini error] {exc}"
                if attempt < self.MAX_RETRIES:
                    time.sleep(Config.GEMINI_RETRY_DELAY)
                    continue
                break
        return last_error

    def _empty(self, reason: str, raw_text: str) -> Dict[str, Any]:
        structured = _empty_structured(raw_text=raw_text)
        return {
            "legacy": _to_legacy(structured),
            "structured": structured,
            "raw_response": reason,
            "error_type": reason,
        }


# ── helpers ───────────────────────────────────────────────────────────────────

def _classify_error(raw: str) -> Optional[str]:
    """Return an error type string if gemini returned an error, else None."""
    if not raw or not raw.startswith("["):
        return None
    if "quota" in raw:
        return "quota_exceeded"
    if "empty ocr" in raw:
        return "empty_ocr"
    if "no api key" in raw:
        return "no_api_key"
    if "gemini" in raw:
        return "gemini_error"
    return "unknown"


def _prepare(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    lines = normalized.split("\n")
    if Config.GEMINI_MAX_INPUT_LINES > 0:
        lines = lines[: Config.GEMINI_MAX_INPUT_LINES]
    clipped = "\n".join(lines)
    if Config.GEMINI_MAX_INPUT_CHARS > 0 and len(clipped) > Config.GEMINI_MAX_INPUT_CHARS:
        return clipped[: Config.GEMINI_MAX_INPUT_CHARS].rstrip()
    return clipped


def _read_text(response: Any) -> str:
    if response is None:
        return ""
    try:
        text = response.text
    except Exception:
        text = ""
    if text and text.strip():
        return text.strip()
    parts: List[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            v = getattr(part, "text", None)
            if v:
                parts.append(v)
    return "\n".join(parts).strip()


def _parse_response(raw: str, raw_text: str) -> Dict[str, Any]:
    payload = _extract_json(raw)
    if payload is None:
        return _empty_structured(raw_text=raw_text)

    items = _parse_items(payload.get("items"))
    return {
        "store_name":     _str(payload.get("store_name")),
        "address":        _str(payload.get("address")),
        "phone":          _str(payload.get("phone")),
        "invoice_id":     _str(payload.get("invoice_id")),
        "datetime_in":    _str(payload.get("datetime_in")),
        "datetime_out":   _str(payload.get("datetime_out")),
        "cashier":        _str(payload.get("cashier")),
        "table":          _str(payload.get("table")),
        "items":          items,
        "subtotal":       _opt_int(payload.get("subtotal")),
        "total":          _int(payload.get("total")),
        "cash_given":     _opt_int(payload.get("cash_given")),
        "cash_change":    _opt_int(payload.get("cash_change")),
        "payment_method": _str(payload.get("payment_method")),
        "raw_text":       raw_text,
    }


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    candidates = [text]
    if start != -1 and end >= start:
        candidates.append(text[start: end + 1])
    for c in candidates:
        try:
            p = json.loads(c)
            if isinstance(p, dict):
                return p
        except json.JSONDecodeError:
            continue
    return None


def _parse_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"))
        if not name:
            continue
        items.append({
            "name":        name,
            "quantity":    max(1, _int(item.get("quantity"), default=1)),
            "unit_price":  max(0, _int(item.get("unit_price"))),
            "total_price": max(0, _int(item.get("total_price"))),
        })
    return items


def _empty_structured(raw_text: str = "") -> Dict[str, Any]:
    return {
        "store_name": None, "address": None, "phone": None,
        "invoice_id": None, "datetime_in": None, "datetime_out": None,
        "cashier": None, "table": None, "items": [],
        "subtotal": None, "total": 0, "cash_given": None,
        "cash_change": None, "payment_method": None, "raw_text": raw_text,
    }


def _to_legacy(s: Dict[str, Any]) -> Dict[str, Any]:
    products = [
        {"PRODUCT": i.get("name", ""), "NUM": i.get("quantity", 0), "VALUE": i.get("total_price", 0)}
        for i in (s.get("items") or [])
    ]
    return {
        "SELLER":     s.get("store_name") or "",
        "ADDRESS":    s.get("address") or "",
        "TIMESTAMP":  s.get("datetime_in") or "",
        "PRODUCTS":   products,
        "TOTAL_COST": float(s.get("total") or 0),
    }


def _str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _opt_int(v: Any) -> Optional[int]:
    n = _int(v)
    return n if n > 0 else None


def _int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    try:
        return int(digits) if digits else default
    except ValueError:
        return default
