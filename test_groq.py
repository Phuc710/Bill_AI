import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Lấy API Key từ biến môi trường
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("❌ Lỗi: Chưa cung cấp GROQ_API_KEY trong environment variables.")
    os._exit(1)

def test_json_extraction_with_groq():
    try:
        # Khởi tạo client
        client = Groq(api_key=api_key)
        
        # 2. Giả lập một đoạn text OCR thô, xước, có nhiều lỗi chính tả do scan hóa đơn
        raw_text_from_ocr = """
        CUA HANG TIEN LOI CIIRKLE K
        Ngai: 24/10/2023
        Hoa don: S00345
        
        Snacck Khoai tay Layys    : 20,000 VND
        Nuoc suoi AIquafinna 500m : 5.000 d
        Banh cuon chao thit bam   :  25.000
        
        Thue VAT 8%: 4.000
        Tỏng conng : 54.000 vnđ
        Cam om quy khak!
        """

        print(f"Đang gửi yêu cầu trích xuất OCR tới model llama-3.3-70b-versatile...\nVui lòng đợi vài giây...")
        
        # 3. Thực hiện gọi API
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {
                    "role": "system",
                    "content": """Bạn là một chuyên gia AI về trích xuất dữ liệu hóa đơn. 
                    Nhiệm vụ: Chuyển đoạn văn bản OCR thô từ hóa đơn thành định dạng JSON chuẩn.
                    Yêu cầu:
                    1. Tự động sửa các lỗi chính tả phổ biến do máy quét OCR gây ra (VD: Ngai -> Ngày, Snacck -> Snack, Tỏng conng -> Tổng cộng).
                    2. Chuyển đổi tất cả giá tiền thành số nguyên integer hợp lệ (VD: 20,000 VND -> 20000). Số lượng mặc định là 1 nếu không ghi.
                    3. Trả về ĐÚNG MỘT OBJECT JSON theo mẫu sau (không thêm bớt key):
                    {
                        "shop_name": "Tên cửa hàng chuẩn hóa (hoặc null)",
                        "date": "Ngày mua định dạng DD/MM/YYYY (hoặc null)",
                        "items": [
                            {
                                "name": "Tên món hàng chuẩn hóa",
                                "quantity": 1,
                                "price": 0
                            }
                        ],
                        "total_amount": 0,
                        "category": "Phân loại chung (chọn 1 mục bằng Tiếng Anh: Food, Transport, Utilities, Shopping, Entertainment, Others)"
                    }
                    4. CHỈ TRẢ VỀ CHUỖI JSON. Nghiêm cấm giải thích hay output thêm bất kỳ từ ngữ nào ở đầu và cuối đoạn JSON."""
                },
                {
                    "role": "user",
                    "content": f"Văn bản OCR:\n{raw_text_from_ocr}"
                }
            ],
            response_format={"type": "json_object"}, # (BẮT BUỘC) Ép model chỉ trả về JSON
            temperature=0.0 # (QUAN TRỌNG) Đặt bằng 0.0 để model đưa ra kết quả trích xuất luôn ổn định (không chế cháo linh tinh)
        )

        # 4. Lấy kết quả chuỗi Text (bản chất định dạng của nó hiện tại đang là JSON String do bị ép kiểu)
        result_json_string = chat_completion.choices[0].message.content
        
        # 5. Parse JSON String sang Python Dictionary để chắc chắn 100% dữ liệu không bị lỗi cú pháp ngoặc {}, [], v.v.
        final_data = json.loads(result_json_string) 
        
        # 6. In kết quả cuối cùng siêu đẹp
        print("\n" + "="*50)
        print("✅ TRÍCH XUẤT THÀNH CÔNG! JSON ĐÃ CHUẨN HÓA:")
        print("="*50)
        print(json.dumps(final_data, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Có lỗi xảy ra: {e}")

if __name__ == "__main__":
    test_json_extraction_with_groq()