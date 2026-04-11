"""
Test Script: VNCV OCR + Groq Llama 3.3 70B
Optimized version: singleton client, model warm-up, text dedup, rác filter.
"""
import os, sys, time, json, re, logging
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from dotenv import load_dotenv

load_dotenv()

# ── Silence noisy libs ────────────────────────────────────────────────────────
os.environ["ORT_LOGGING_LEVEL"] = "3"
logging.disable(logging.CRITICAL)

@contextmanager
def _silence():
    with open(os.devnull, "w") as null:
        with redirect_stdout(null), redirect_stderr(null):
            yield

# ── Lazy-load VNCV once ───────────────────────────────────────────────────────
from vncv import extract_text as _vncv_extract

# Warm-up model (tránh delay 2-3s ở request đầu)
import tempfile
from PIL import Image
_dummy = Image.new("RGB", (64, 64), color=255)
with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
    _dummy.save(f); _warmup_path = f.name
with _silence():
    _vncv_extract(_warmup_path, lang="vi", return_dict=True)
os.remove(_warmup_path)

# ── Groq singleton ────────────────────────────────────────────────────────────
from groq import Groq
_api_key = os.getenv("GROQ_API_KEY") or sys.exit("❌ GROQ_API_KEY chưa set!")
_groq = Groq(api_key=_api_key)

# ── Prompt ────────────────────────────────────────────────────────────────────
_SYSTEM = """\
Bạn là chuyên gia kế toán Việt Nam. Phân tích OCR hóa đơn, xuất JSON thuần theo schema sau.
Tự sửa lỗi chính tả OCR. Gộp các món trùng lặp (cộng qty).

Schema BẮT BUỘC (chỉ JSON, không markdown):
{
    "metadata": {"bill_type": "Dining/Shopping/Travel/Healthcare/Other", "currency": "VND"},
    "shop": {"name": null, "address": null, "phone": null, "invoice_id": null},
    "transaction": {
        "datetime": "YYYY-MM-DD HH:MM:SS hoặc null",
        "payment_method": "Cash/Card/Transfer hoặc null",
        "subtotal": 0, "cash_given": 0, "cash_change": 0, "total_final": 0
    },
    "items": [{"name": "Tên món", "qty": 1, "unit_price": 0, "amount": 0}],
    "ai_assessment": {"category": "Ăn uống|Mua sắm|Di chuyển|Giải trí|Sức khỏe|Khác", "summary": "Ghi chú chi tiêu"}
}

Quy tắc nghiêm ngặt:
1. total_final = số tiền thực khách trả (Int, bỏ dấu chấm/phẩy).
2. amount = qty × unit_price (bắt buộc nhất quán).
3. Gộp món trùng, không tạo 2 dòng cùng tên.
4. Chỉ JSON thuần — KHÔNG có ```json hay markdown.

Quy tắc viết "summary" — ĐÂY LÀ GHI CHÚ TỰ ĐỘNG cho app tài chính cá nhân:
Viết như người dùng TỰ TAY ghi nhật ký chi tiêu — ngắn gọn, tự nhiên, đủ thông tin.
Cấu trúc chuẩn: [Hoạt động] tại [Tên quán/cửa hàng] · [Điểm nổi bật 2-3 món/mặt hàng] · Tổng: [số tiền]đ
Ví dụ theo category:
  Ăn uống  → "Ăn BBQ tại Quá Đã BBQ, Q.10 · Sườn nướng, trà đào, cà phê · Tổng: 636.000đ"
  Mua sắm  → "Mua sắm tại VinMart, Tân Phú · Thực phẩm, gia dụng · Tổng: 285.000đ"
  Di chuyển→ "Đi Grab từ Q.1 về Q.Bình Thạnh · Tổng: 45.000đ"
  Giải trí → "Xem phim tại CGV Vincom · 2 vé Avengers · Tổng: 220.000đ"
  Sức khỏe → "Mua thuốc tại Pharmacity, Q.3 · Panadol, vitamin C · Tổng: 95.000đ"
Quy tắc: Không dùng câu "Khách hàng đã thanh toán...". Luôn dùng giọng cá nhân, chủ động.\
"""

# ── OCR text cleanup ──────────────────────────────────────────────────────────
_JUNK_LINE = re.compile(r"^[^\w\d]{0,3}$", re.UNICODE)
_SHORT_LOGO = re.compile(r"^\S{2,8}$")   # Từ ngắn 2-8 ký tự không dấu cách → nghi logo

def _clean_ocr(items: list) -> str:
    """Lọc rác, dedup dòng liên tiếp, trả text sạch."""
    lines, seen_tail = [], set()
    for i in items:
        ln = str(i.get("text", "") if isinstance(i, dict) else i).strip()
        if not ln:
            continue
        if _JUNK_LINE.match(ln):
            continue
        if not re.search(r"[\w\d]", ln, re.UNICODE):
            continue
        # Bỏ dòng logo ngắn nằm ngay sau tên cửa hàng (không có số hay dấu cách)
        if _SHORT_LOGO.match(ln) and not re.search(r"\d", ln):
            continue
        # Dedup: bỏ nếu dòng này đã xuất hiện ở 20 dòng cuối (xử lý lặp cuối bill)
        key = re.sub(r"\s+", "", ln.lower())
        if key in seen_tail:
            continue
        seen_tail.add(key)
        if len(seen_tail) > 20:
            seen_tail.pop()
        lines.append(re.sub(r" {2,}", " ", ln))
    return "\n".join(lines)


# ── Main pipeline ─────────────────────────────────────────────────────────────
def process_bill(image_path: str):
    t0 = time.perf_counter()
    print(f"\n⏳ PHASE 1 — VNCV OCR Offline [{image_path}]...")

    # OCR
    t_ocr = time.perf_counter()
    try:
        with _silence():
            raw = _vncv_extract(image_path, lang="vi", return_dict=True) or []
        text = _clean_ocr(raw)
        if not text:
            print("❌ OCR không nhận diện được chữ nào.")
            return
    except Exception as e:
        print(f"❌ OCR lỗi: {e}")
        return
    ocr_ms = (time.perf_counter() - t_ocr) * 1000

    print("\n💬 TEXT OCR SAU KHI LỌC RÁC:")
    print("-" * 40)
    print(text)
    print("-" * 40)

    # Groq LLM
    print("\n⏳ PHASE 2 — Groq Llama 3.3-70B chuẩn hóa JSON...")
    t_llm = time.perf_counter()
    try:
        resp = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": f"Văn bản OCR:\n{text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1024,
        )
        llm_ms = (time.perf_counter() - t_llm) * 1000
        data = json.loads(resp.choices[0].message.content)
        print("✅ OUTPUT:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Groq lỗi: {e}")
        return

    total_ms = (time.perf_counter() - t0) * 1000
    print(f"\n{'='*50}")
    print(f"  OCR  : {ocr_ms/1000:.2f}s")
    print(f"  LLM  : {llm_ms/1000:.2f}s")
    print(f"  TOTAL: {total_ms/1000:.2f}s")
    print(f"{'='*50}")


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "222.jpg"
    process_bill(img)
