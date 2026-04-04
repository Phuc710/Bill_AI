"""
Groq LLM Extractor — Dùng Llama 3.3-70B qua Groq API.

Ưu điểm:
  - Nhanh (Sử dụng Groq LPU inference chip)
  - Stable JSON mode: response_format={"type": "json_object"}
  - High Rate Limit: 6000 requests/ngày

Error types returned:
  [empty ocr]    — không có text đầu vào
  [no api key]   — GROQ_API_KEY chưa cấu hình
  [groq error]   — lỗi API
  [quota limit]  — rate limit hit
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from core.config import Config


_SYSTEM_PROMPT = """Bạn là chuyên gia kế toán Việt Nam.
Nhiệm vụ: Trích xuất thông tin từ văn bản OCR hóa đơn/biên lai và trả về STRICT JSON.

Schema BẮT BUỘC (không thêm key khác):
{
  "store_name": "Tên cửa hàng hoặc null",
  "address": "Địa chỉ hoặc null",
  "phone": "Số điện thoại hoặc null",
  "invoice_id": "Mã hóa đơn hoặc null",
  "datetime_in": "DD/MM/YYYY HH:MM hoặc DD/MM/YYYY hoặc null",
  "datetime_out": "DD/MM/YYYY HH:MM hoặc null",
  "cashier": "Tên thu ngân hoặc null",
  "table": "Số bàn hoặc null",
  "items": [
    {"name": "Tên món", "quantity": 1, "unit_price": 0, "total_price": 0}
  ],
  "subtotal": 0,
  "total": 0,
  "cash_given": 0,
  "cash_change": 0,
  "category": "Food & Beverage | Grocery | Transport | Entertainment | Healthcare | Shopping | Other"
}

Quy tắc:
- Tự sửa lỗi OCR (chính tả, dấu tiếng Việt sai)
- Số tiền luôn là Integer (VND, bỏ dấu phẩy/chấm)
- Nếu không tìm thấy giá trị → null (số nguyên → 0)
- CHỈ trả về JSON, KHÔNG có markdown, KHÔNG có giải thích"""


class GroqExtractor:
    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._client = None

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        raw_text = _prepare(ocr_text)
        if not raw_text:
            return self._empty("[empty ocr]", raw_text="")

        if not Config.GROQ_API_KEY:
            return self._empty("[no api key]", raw_text=raw_text)

        self._ensure_client()
        raw_response = self._call(raw_text)
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
        from groq import Groq
        self._client = Groq(api_key=Config.GROQ_API_KEY)

    def _call(self, ocr_text: str) -> str:
        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=Config.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"Văn bản OCR hóa đơn:\n{ocr_text}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content or ""
                if text.strip():
                    return text.strip()
                last_error = "[groq empty]"
            except Exception as exc:
                msg = str(exc).lower()
                if any(t in msg for t in ("quota", "429", "rate", "limit")):
                    return f"[quota limit] {exc}"
                last_error = f"[groq error] {exc}"
                if attempt < self.MAX_RETRIES:
                    time.sleep(1.0)
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
    if not raw or not raw.startswith("["):
        return None
    if "quota" in raw:
        return "quota_exceeded"
    if "empty ocr" in raw:
        return "empty_ocr"
    if "no api key" in raw:
        return "no_api_key"
    if "groq" in raw:
        return "groq_error"
    return "unknown"


def _prepare(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    lines = normalized.split("\n")
    if Config.GROQ_MAX_INPUT_LINES > 0:
        lines = lines[: Config.GROQ_MAX_INPUT_LINES]
    clipped = "\n".join(lines)
    if Config.GROQ_MAX_INPUT_CHARS > 0 and len(clipped) > Config.GROQ_MAX_INPUT_CHARS:
        return clipped[: Config.GROQ_MAX_INPUT_CHARS].rstrip()
    return clipped


def _parse_response(raw: str, raw_text: str) -> Dict[str, Any]:
    payload = _extract_json(raw)
    if payload is None:
        return _empty_structured(raw_text=raw_text)

    items = _parse_items(payload.get("items"))
    return {
        "store_name":   _str(payload.get("store_name")),
        "address":      _str(payload.get("address")),
        "phone":        _str(payload.get("phone")),
        "invoice_id":   _str(payload.get("invoice_id")),
        "datetime_in":  _str(payload.get("datetime_in")),
        "datetime_out": _str(payload.get("datetime_out")),
        "cashier":      _str(payload.get("cashier")),
        "table":        _str(payload.get("table")),
        "items":        items,
        "subtotal":     _opt_int(payload.get("subtotal")),
        "total":        _int(payload.get("total")),
        "cash_given":   _opt_int(payload.get("cash_given")),
        "cash_change":  _opt_int(payload.get("cash_change")),
        "payment_method": _str(payload.get("payment_method")),
        "category":     _str(payload.get("category")) or "Other",
        "raw_text":     raw_text,
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
        "cash_change": None, "payment_method": None,
        "category": "Other", "raw_text": raw_text,
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
