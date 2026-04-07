"""
Groq LLM Extractor — Dùng Llama 3.3-70b-versatile qua Groq API.

Prompt chỉ extract những gì app thực sự cần (phase 1):
  merchant_name, address, phone, invoice_id, datetime,
  bill_type, category, total_final, items[], summary

Không để LLM gánh các field ít tin cậy: payment_method,
subtotal, cash_given, cash_change.

Output nội bộ:
  extract() → {"internal": {...}, "raw_response": "...", "error_type": "..."}
  Không còn "legacy" key.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from core.config import Config

log = logging.getLogger("billai.groq_extractor")


# ── System prompt (gọn, ổn định) ─────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Bạn là chuyên gia kế toán Việt Nam.
Phân tích văn bản OCR hóa đơn và xuất JSON THEO ĐÚNG schema sau.
Tự sửa lỗi chính tả OCR. Gộp các món trùng lặp (Coca xuất hiện 2 lần → cộng qty).

Schema BẮT BUỘC:
{
    "merchant_name": "Tên quán/cửa hàng hoặc null",
    "address": "Địa chỉ hoặc null",
    "phone": "Số điện thoại hoặc null",
    "invoice_id": "Mã hóa đơn (string) hoặc null",
    "datetime": "YYYY-MM-DD HH:MM:SS hoặc null",
    "bill_type": "Dining / Shopping / Travel / Healthcare / Other",
    "category": "Ăn uống | Mua sắm | Di chuyển | Giải trí | Sức khỏe | Khác",
    "total_final": 0,
    "items": [
        {"name": "Tên món", "qty": 1, "unit_price": 25000, "amount": 25000}
    ],
    "summary": "Tóm tắt ngắn bằng tiếng Việt"
}

Quy tắc SỐ LIỆU (nghiêm ngặt):
1. total_final là số tiền thực khách trả — luôn là Int (VD: 225000), không có dấu chấm/phẩy.
2. qty là Int >= 1. unit_price và amount là Int (VND), không âm.
3. amount = qty × unit_price (bắt buộc nhất quán).
4. Nếu trùng món → CỘNG DỒN qty. Không tạo 2 dòng cho cùng 1 món.
5. KHÔNG output Markdown, KHÔNG dùng ```json. Chỉ JSON thuần.

Category (chọn 1 trong 6):
  Ăn uống   → nhà hàng, café, quán ăn, trà sữa
  Mua sắm   → siêu thị, quần áo, điện tử
  Di chuyển → taxi, grab, xăng, vé xe/máy bay
  Giải trí  → rạp phim, karaoke, tham quan
  Sức khỏe  → nhà thuốc, bệnh viện, phòng khám
  Khác      → không thuộc nhóm nào trên
"""


# ── Main extractor ─────────────────────────────────────────────────────────────

class GroqExtractor:
    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._client = None

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        """
        Nhận OCR text → gọi Groq LLM → trả về:
          {
            "internal": { store_name, address, phone, ... },   # nội bộ pipeline dùng
            "raw_response": "...",                              # raw JSON string từ LLM
            "error_type": None | "empty_ocr" | "no_api_key" | "groq_error" | ...
          }
        """
        raw_text = _prepare(ocr_text)
        if not raw_text:
            return self._empty("[empty ocr]", raw_text="")

        if not Config.GROQ_API_KEY:
            return self._empty("[no api key]", raw_text=raw_text)

        self._ensure_client()
        raw_response = self._call(raw_text)
        internal = _parse_response(raw_response, raw_text=raw_text)

        # Arithmetic validation
        warnings = _validate_math(internal)
        if warnings:
            internal["_math_warnings"] = warnings
            log.warning(f"Math warnings: {warnings}")

        return {
            "internal":     internal,
            "raw_response": raw_response,
            "error_type":   _classify_error(raw_response),
        }

    # ── internals ──────────────────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        if self._client is None:
            from groq import Groq  # lazy import
            self._client = Groq(api_key=Config.GROQ_API_KEY)

    def _call(self, ocr_text: str) -> str:
        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=Config.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": f"Văn bản OCR hóa đơn:\n{ocr_text}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=1024,
                )
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text
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
        return {
            "internal":     _empty_internal(raw_text=raw_text),
            "raw_response": reason,
            "error_type":   reason,
        }


# ── Domain parsers ────────────────────────────────────────────────────────────

def parse_money(v: Any) -> int:
    """Parse tiền VND: '25.000' | '25,000' | 25000 → 25000 (int)."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return max(0, int(v))
    s = str(v).strip()
    # Bỏ dấu phân cách nghìn (dấu chấm hoặc phẩy trước 3 chữ số)
    s = re.sub(r"[.,](?=\d{3}(?:[,.\s]|$))", "", s)
    digits = re.sub(r"[^\d]", "", s)
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0


def parse_qty(v: Any, default: int = 1) -> int:
    """Parse số lượng — luôn là int >= 1."""
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return max(1, int(v))
    digits = re.sub(r"[^\d]", "", str(v))
    try:
        return max(1, int(digits)) if digits else default
    except ValueError:
        return default


def parse_invoice_id(v: Any) -> Optional[str]:
    """Invoice ID giữ nguyên string, không ép số."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("null", "none", "") else None


def parse_datetime(v: Any) -> Optional[str]:
    """Datetime string YYYY-MM-DD HH:MM(:SS)."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("null", "none", "") else None


# ── Math validation ────────────────────────────────────────────────────────────

_TOLERANCE = 0.05  # 5% chênh lệch cho phép


def _validate_math(internal: Dict[str, Any]) -> List[str]:
    """
    Validate tính nhất quán số học:
      1. qty × unit_price ≈ total_price (với tolerance 5%)
      2. sum(items.total_price) ≈ total (với tolerance 5%)
    """
    warnings: List[str] = []
    items: List[Dict[str, Any]] = internal.get("items") or []

    item_sum = 0
    for i, item in enumerate(items):
        qty        = item.get("quantity", 1)
        unit_price = item.get("unit_price", 0)
        total_price = item.get("total_price", 0)
        item_sum  += total_price

        if qty > 0 and unit_price > 0 and total_price > 0:
            expected = qty * unit_price
            if expected > 0 and abs(total_price - expected) / expected > _TOLERANCE:
                warnings.append(
                    f"item[{i}] '{item.get('name','?')}': "
                    f"qty({qty})×unit({unit_price})={expected} ≠ amount({total_price})"
                )

    total = int(internal.get("total") or 0)
    if item_sum > 0 and total > 0:
        diff = abs(item_sum - total) / total
        if diff > _TOLERANCE:
            warnings.append(
                f"sum(items)={item_sum} ≠ total={total} (diff {diff*100:.1f}%)"
            )

    return warnings


# ── Helpers ────────────────────────────────────────────────────────────────────

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
        return _empty_internal(raw_text=raw_text)

    items = _parse_items(payload.get("items"))

    return {
        "store_name":   _str(payload.get("merchant_name")),
        "address":      _str(payload.get("address")),
        "phone":        _str(payload.get("phone")),
        "invoice_id":   parse_invoice_id(payload.get("invoice_id")),
        "datetime_in":  parse_datetime(payload.get("datetime")),
        "bill_type":    _str(payload.get("bill_type")),
        "items":        items,
        "total":        parse_money(payload.get("total_final")),
        # payment fields — null (not extracted in phase 1, app reads from DB)
        "subtotal":       None,
        "cash_given":     None,
        "cash_change":    None,
        "payment_method": None,
        "category":     _str(payload.get("category")) or "Khác",
        "summary":      _str(payload.get("summary")),
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
        qty        = parse_qty(item.get("qty", item.get("quantity")))
        unit_price = parse_money(item.get("unit_price"))
        raw_amount = item.get("amount", item.get("total_price"))
        amount     = parse_money(raw_amount)
        # Fallback: tính lại nếu amount == 0 nhưng có qty + unit_price
        if amount == 0 and unit_price > 0:
            amount = qty * unit_price

        items.append({
            "name":        name,
            "quantity":    qty,
            "unit_price":  unit_price,
            "total_price": amount,
        })
    return items


def _empty_internal(raw_text: str = "") -> Dict[str, Any]:
    return {
        "store_name": None, "address": None, "phone": None,
        "invoice_id": None, "datetime_in": None, "bill_type": None,
        "items": [], "total": 0,
        "subtotal": None, "cash_given": None, "cash_change": None,
        "payment_method": None, "category": "Khác",
        "summary": None, "raw_text": raw_text,
    }


def _str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return None if s.lower() in ("null", "none", "") else s
