"""
gemini_extractor.py — Send raw OCR text to Gemini, parse new structured JSON output.

Flow:
  ocr_text (raw) → prompt + text → Gemini → JSON → structured output
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from core.config import Config

# ── Prompt loader ──────────────────────────────────────────────────────────────

def _load_prompt() -> str:
    p = Config.EXTRACTION_PROMPT
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return (
        "Extract Vietnamese bill fields. Return STRICT JSON only: "
        "{store_name, address, phone, invoice_id, datetime_in, datetime_out, "
        "cashier, table, items=[{name,quantity,unit_price,total_price}], "
        "subtotal, total, cash_given, cash_change, payment_method, raw_text}"
    )


# ── Regex helpers ──────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


# ── Main class ─────────────────────────────────────────────────────────────────

class GeminiExtractor:
    MAX_RETRIES = 2
    BASE_DELAY_S = 0.8

    def __init__(self) -> None:
        self._prompt: str = _load_prompt()
        self._client = None  # lazy init

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        """
        Send raw OCR text to Gemini.
        Returns: {legacy, structured, raw_response}
        """
        text = ocr_text.strip()
        if not text:
            return self._empty_result("[empty ocr]")

        if not Config.GEMINI_API_KEY:
            legacy = _regex_fallback(text)
            structured = _legacy_to_structured(legacy, text)
            return {"legacy": legacy, "structured": structured, "raw_response": "[no key]"}

        self._ensure_client()

        full_prompt = f"{self._prompt}\n\nTEXT:\n{text}\n\nJSON:"
        raw = self._call(full_prompt)
        structured = _parse_structured(raw, text)

        if _is_structured_empty(structured):
            legacy = _regex_fallback(text)
            structured = _legacy_to_structured(legacy, text)
        else:
            legacy = _structured_to_legacy(structured)

        return {"legacy": legacy, "structured": structured, "raw_response": raw}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self._client = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={
                "temperature": 0.0,
                "top_p": 0.8,
                "candidate_count": 1,
                "max_output_tokens": 1200,
            },
        )

    def _call(self, prompt: str) -> str:
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = self._client.generate_content(prompt)
                if not resp or not resp.candidates:
                    print(f"      [Gemini] No candidates returned (attempt {attempt+1})")
                    continue
                
                # Try to get text. If blocked, it may raise an exception on .text
                try:
                    text = resp.text
                    if text and text.strip():
                        return text
                except Exception as text_exc:
                    print(f"      [Gemini] Could not get text: {text_exc}")
                    if hasattr(resp, 'prompt_feedback'):
                        print(f"      [Gemini] Feedback: {resp.prompt_feedback}")
                
            except Exception as exc:
                msg = str(exc).lower()
                # Fail fast on quota/rate limits to save time in pipeline
                if any(k in msg for k in ("quota", "429", "503", "unavailable", "rate")):
                    print(f"      [Gemini] Lỗi: Hết giới hạn truy cập API (Quota/429). Thử lại sau.")
                    break
                print(f"      [Gemini] Lỗi: {exc}")
                # For other errors, we can retry once if attempt < MAX_RETRIES
                if attempt < self.MAX_RETRIES:
                    time.sleep(Config.GEMINI_RETRY_DELAY)
                    continue
                break
        return ""

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        structured = _empty_structured()
        legacy = _structured_to_legacy(structured)
        return {"legacy": legacy, "structured": structured, "raw_response": reason}


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _parse_structured(raw: str, ocr_text: str) -> Dict[str, Any]:
    """Strip markdown fences, parse JSON, enforce new schema."""
    text = _FENCE_RE.sub("", raw).strip()
    data: Dict[str, Any]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(text)
        if not m:
            return _empty_structured()
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            return _empty_structured()

    items: List[Dict[str, Any]] = []
    for item in (data.get("items") or []):
        name = str(item.get("name") or "").strip()
        qty = _intn(item.get("quantity", 1))
        unit = _intn(item.get("unit_price", 0))
        total = _intn(item.get("total_price", 0))
        # compute missing unit_price or total_price
        if unit == 0 and total > 0 and qty > 0:
            unit = round(total / qty)
        if total == 0 and unit > 0 and qty > 0:
            total = unit * qty
        if not name:
            continue
        items.append({"name": name, "quantity": qty, "unit_price": unit, "total_price": total})

    return {
        "store_name":     _str(data.get("store_name")),
        "address":        _str(data.get("address")),
        "phone":          _str(data.get("phone")),
        "invoice_id":     _str(data.get("invoice_id")),
        "datetime_in":    _str(data.get("datetime_in")),
        "datetime_out":   _str(data.get("datetime_out")),
        "cashier":        _str(data.get("cashier")),
        "table":          _str(data.get("table")),
        "items":          items,
        "subtotal":       _intn_or_none(data.get("subtotal")),
        "total":          _intn(data.get("total", 0)),
        "cash_given":     _intn_or_none(data.get("cash_given")),
        "cash_change":    _intn_or_none(data.get("cash_change")),
        "payment_method": _str(data.get("payment_method")),
        "raw_text":       ocr_text[:300],
    }


# ── Regex fallback (no Gemini) ─────────────────────────────────────────────────

def _regex_fallback(text: str) -> Dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    seller = lines[0] if lines else ""

    ts = re.search(
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APM]{2})?)?)",
        text, re.IGNORECASE,
    )
    timestamp = ts.group(1).strip() if ts else ""

    numbers = [_num(x) for x in re.findall(r"[\d.,]{4,}", text)]
    total = max(numbers, default=0.0)

    return {"SELLER": seller, "ADDRESS": "", "TIMESTAMP": timestamp, "PRODUCTS": [], "TOTAL_COST": total}


# ── Conversion helpers ─────────────────────────────────────────────────────────

def _empty_structured() -> Dict[str, Any]:
    return {
        "store_name": None, "address": None, "phone": None,
        "invoice_id": None, "datetime_in": None, "datetime_out": None,
        "cashier": None, "table": None, "items": [],
        "subtotal": None, "total": 0, "cash_given": None,
        "cash_change": None, "payment_method": None, "raw_text": "",
    }


def _structured_to_legacy(s: Dict[str, Any]) -> Dict[str, Any]:
    """Map new structured → legacy format (for backward compat)."""
    products = []
    for it in (s.get("items") or []):
        products.append({
            "PRODUCT": it.get("name", ""),
            "NUM": it.get("quantity", 0),
            "VALUE": it.get("total_price", 0),
        })
    return {
        "SELLER": s.get("store_name") or "",
        "ADDRESS": s.get("address") or "",
        "TIMESTAMP": s.get("datetime_in") or "",
        "PRODUCTS": products,
        "TOTAL_COST": float(s.get("total") or 0),
    }


def _legacy_to_structured(legacy: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """Map legacy format → new structured output."""
    items = []
    for p in (legacy.get("PRODUCTS") or []):
        qty = max(1, int(_num(p.get("NUM", 1))))
        total = int(_num(p.get("VALUE", 0)))
        unit = round(total / qty) if qty > 0 else 0
        items.append({
            "name": str(p.get("PRODUCT") or "").strip(),
            "quantity": qty,
            "unit_price": unit,
            "total_price": total,
        })
    total = int(_num(legacy.get("TOTAL_COST") or 0))
    return {
        "store_name":     legacy.get("SELLER") or None,
        "address":        legacy.get("ADDRESS") or None,
        "phone":          None,
        "invoice_id":     None,
        "datetime_in":    legacy.get("TIMESTAMP") or None,
        "datetime_out":   None,
        "cashier":        None,
        "table":          None,
        "items":          items,
        "subtotal":       total or None,
        "total":          total,
        "cash_given":     None,
        "cash_change":    None,
        "payment_method": None,
        "raw_text":       raw_text[:300],
    }


def _is_structured_empty(s: Dict[str, Any]) -> bool:
    return not (
        s.get("store_name")
        or s.get("items")
        or (s.get("total") or 0) > 0
    )


# ── Number parsers ─────────────────────────────────────────────────────────────

def _str(val: Any) -> Optional[str]:
    if val is None:
        return None
    v = str(val).strip()
    return v if v else None


def _num(val: Any) -> float:
    """Convert any money-like value to float."""
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return 0.0
    s = re.sub(r"[^\d,.]", "", val.strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if all(len(p) == 3 for p in parts[1:]):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _intn(val: Any) -> int:
    return int(_num(val))


def _intn_or_none(val: Any) -> Optional[int]:
    if val is None:
        return None
    n = _intn(val)
    return n if n > 0 else None
