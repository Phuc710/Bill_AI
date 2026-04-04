import os
import time
import json
from groq import Groq

# Thư viện Viet Nam CV OCR hoạt động 100% Offline (Không lo sập web)
from vncv import extract_text

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("❌ Lỗi: Chưa cung cấp GROQ_API_KEY trong environment variables.")
    os._exit(1)

def process_bill_with_vncv(image_path):
    t_start = time.time()
    
    # --- PHASE 1: VNCV OCR (Offline) ---
    t_ocr_start = time.time()
    print(f"\n⏳ CÔNG ĐOẠN 1: Dùng VNCV OCR để quét ảnh Offline [{image_path}]...")
    try:
        # vncv.extract_text trả về một List các dòng text. Ta ghép lại bằng ký tự xuống dòng (\n)
        raw_text_list = extract_text(image_path)
        
        if not raw_text_list:
            print("❌ OCR thất bại, không nhìn ra chữ nào trên ảnh.")
            return
            
        raw_text = "\n".join(raw_text_list)
        
        print("\n💬 VĂN BẢN VNCV THU ĐƯỢC (ĐẦU VÀO CHO AI):")
        print("-" * 40)
        print(raw_text)
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Lỗi trong quá trình quét VNCV OCR: {e}")
        return
        
    t_ocr_end = time.time()

    # --- PHASE 2: GROQ NLP ---
    t_llm_start = time.time()
    print("\n⏳ CÔNG ĐOẠN 2: Dùng Groq Llama 3.3 70B chuẩn hóa thành JSON...")
    try:
        client = Groq(api_key=api_key)
        
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """Bạn là chuyên gia kế toán Việt Nam. Phân tích OCR hóa đơn và xuất JSON CHUYÊN NGHIỆP sau. Tự sửa lỗi chính tả và CỘNG DỒN các món trùng lặp (ví dụ: Coca 2 lần thì cộng qty lại).

Schema BẮT BUỘC:
{
    "metadata": {
        "bill_type": "Dining / Shopping / Travel / Healthcare / Other",
        "language": "Tiếng Việt",
        "currency": "VND"
    },
    "shop": {
        "name": "Tên quán hoặc null",
        "address": "Địa chỉ hoặc null",
        "phone": "SĐT hoặc null",
        "invoice_id": "Mã hóa đơn hoặc null"
    },
    "transaction": {
        "datetime": "YYYY-MM-DD HH:MM hoặc null",
        "payment_method": "Cash/Card/Transfer hoặc null",
        "subtotal": 0,
        "cash_given": 0,
        "cash_change": 0,
        "total_final": 0
    },
    "items": [
        {"name": "Món A", "qty": 1, "unit_price": 0, "amount": 0}
    ],
    "ai_assessment": {
        "category": "Ăn uống | Mua sắm | Di chuyển | Giải trí | Sức khỏe | Khác",
        "summary": "Tóm tắt ngắn gọn"
    }
}

Quy tắc:
