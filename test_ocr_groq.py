import os
import re
import time
import base64
import requests
import json
from io import BytesIO
from typing import Union
from groq import Groq

# ---------------------------------------------
# 1. OCR Solver (Crawler tự động quét web imgtotext)
# ---------------------------------------------
class OCRSolverError(Exception):
    def __init__(self, err_message):
        super().__init__(f"{err_message}")

class OCRSolver:
    def __init__(self, *, image_path=None, image_base64=None):
        self.token = None
        self.img_b64 = image_base64
        self.img_path = image_path
        self.session = requests.Session()
        # Fake User-Agent để web tưởng đây là trình duyệt thật
        self.session.headers.update({
            "Accept": "*/*",
            "origin": "https://imgtotext.net",
            "referer": "https://imgtotext.net",
            "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": "eyJpdiI6Ik1sRXFXSmt6ckdmKzZYcVJxMUxjZEE9PSIsInZhbHVlIjoicU02N2FNZHFBNlIxS0RFdTBBdzRDME5oNTVHamtlUyt1WGhpaUtHWkpoTktNdFc4ZEtOYVdHOEhDa3NnWkVnME9CSXg2UzdoMTd0dHNsR2E5anRwOUxjaVFEbFgrbzV4TytHcmljbTdMNUlHL24rb0lSOElqc2ZBQVFjNWJZTHkiLCJtYWMiOiIxYWVlMmUxYWRjMGI1OWMwNzQ1YWU1Y2ZlNWU2NzViNWM4NjJkNTk0MzMwNTBhMzRhODMyMTgxMTM2ZmFiZjBhIiwidGFnIjoiIn0="
        })
        self.setup()
    
    def setup(self) -> None:
        try:
            # 1. Ép Hardcode Cookies xịn từ Browser của user để chống lỗi 500 do Session bị hủy
            self.session.cookies.set('laravel_session', 'eyJpdiI6Ino3SEUvU3g0bWpjbUVpMEljYXhQUnc9PSIsInZhbHVlIjoiYkVTTWpqakhoNDZKRGRGV0owU0hJYktVL01hMU12VThaS0ZqZUZaRmJTTG1yRzE4ekExSTliZUc2QitUTEJkWFhYVkRKNnFDNWF1MGlnME9Pd056MjMrdVdtMFNNd2RzKzRwWDNqOEVUUlVXYTB5WVRkZGNpK3E0OHYvcXVWNCsiLCJtYWMiOiJkMTZmODlhZTZiYjBlOGQzYzZlZjhlNDg2OGY3NzhkYjQ2NDEwY2Y2NzIzMTJmMmZmZDYyZTgxNmNhNjlkYzdiIiwidGFnIjoiIn0%3D', domain='imgtotext.net')
            self.session.cookies.set('XSRF-TOKEN', 'eyJpdiI6Ik1sRXFXSmt6ckdmKzZYcVJxMUxjZEE9PSIsInZhbHVlIjoicU02N2FNZHFBNlIxS0RFdTBBdzRDME5oNTVHamtlUyt1WGhpaUtHWkpoTktNdFc4ZEtOYVdHOEhDa3NnWkVnME9CSXg2UzdoMTd0dHNsR2E5anRwOUxjaVFEbFgrbzV4TytHcmljbTdMNUlHL24rb0lSOElqc2ZBQVFjNWJZTHkiLCJtYWMiOiIxYWVlMmUxYWRjMGI1OWMwNzQ1YWU1Y2ZlNWU2NzViNWM4NjJkNTk0MzMwNTBhMzRhODMyMTgxMTM2ZmFiZjBhIiwidGFnIjoiIn0%3D', domain='imgtotext.net')

            # 2. Bắt đầu Get token giả diện session thật
            site = self.session.get('https://imgtotext.net/')
            comp = re.compile(r'"_token" value=\s*"([^"]+)"')
            token_found = comp.findall(site.text)
            if not token_found:
                raise OCRSolverError("API token not found on web.")
            
            self.token = token_found[0]
            # Update thêm cookie mới chứ ko xóa mảng cookie cứng
            self.session.cookies.update(site.cookies)
        except Exception as e:
            raise OCRSolverError(f"Setup failed: {str(e)}")
    
    def upload_image(self) -> str:
        self.time_upload = f"{int(time.time() * 1000)}"
        payload = {
            "_token": self.token,
            "fiLes": "",
            "url_upload": "",
            "time": self.time_upload,
            "from": "png, jpg, jpeg, gif, jfif, pdf, webp, bmp, heif, heic, JPEG",
            "upload": "upload"
        }
        
        # Cập nhật fileName giống hệt trình duyệt
        fileName = f"itt_{self.time_upload}.png"
        files = [("file", (fileName, open(self.img_path, "rb"), "image/png"))]
        
        upload = self.session.post("https://imgtotext.net/upload", data=payload, files=files)
        print(f"[DEBUG] Upload Status: {upload.status_code}, Text: {upload.text}")
        if upload.status_code != 200:
            return "error"
        return "success"
    
    def convert_image(self) -> str:
        fileName = f"itt_{self.time_upload}.png"
        files = [("fiLes", (fileName, open(self.img_path, "rb"), "image/png"))]
        payload = {
            "_token": self.token,
            "url_upload": "",
            "fileNames[]": fileName,
            "convert": ""
        }
        convert = self.session.post("https://imgtotext.net/", data=payload, files=files)
        print(f"[DEBUG] Convert Status: {convert.status_code}")
        if convert.status_code != 200:
            return "error"
        return "success"
    
    def extract(self) -> str:
        try:
            self.time_upload = f"{int(time.time() * 1000)}"
            uploaded_status = self.upload_image()
            if uploaded_status == "error":
                raise OCRSolverError("Upload Error")
            
            converted_status = self.convert_image()
            if converted_status == "error":
                raise OCRSolverError("Convert Error")
            
            fileName = f"itt_{self.time_upload}.png"
            print(f"[DEBUG] fileName expected: {fileName}")
            
            # CẤU TRÚC PAYLOAD MỚI NHẤT DO TRÌNH DUYỆT GỬI LUÔN!!!
            payload = {
                "_token": self.token,
                "fileName": fileName,
                "zipFileName": fileName,
                "fromExt": ".png, .jpg, .jpeg, .gif, .jfif, .pdf, .webp, .bmp, .heif, .heic, .JPEG, .PNG, .JPG, .GIF, .JFIF, .PDF, .WEBP, .BMP, .HEIF, .HEIC",
                "toExt": ".txt",
                "tool": "IMG To Text",
                "locale": "en"
            }
            
            extract = self.session.post("https://imgtotext.net/image-to-text", data=payload)
            print(f"[DEBUG] Extract Status: {extract.status_code}")
            
            if extract.status_code != 200:
                print(f"[DEBUG] Extract Response Text: {extract.text}")
                raise OCRSolverError("Extract Error")
            
            # Trích xuất JSON từ chuỗi trả về
            data = json.loads(extract.text)
            return "".join(data["text"])
        except Exception as e:
            raise OCRSolverError(f"Extraction failed: {str(e)}")


# ---------------------------------------------
# 2. Xử lý logic chuẩn hóa qua Groq 
# ---------------------------------------------
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    # Fallback if already set in environment
    api_key = os.environ.get("GROQ_API_KEY")

def process_bill_pipeline(image_path):
    t_start = time.time()
    
    # --- PHASE 1: OCR ---
    t_ocr_start = time.time()
    print(f"⏳ CÔNG ĐOẠN 1: Tiến hành bắn ảnh [{image_path}] lên imgtotext.net lấy text...")
    try:
        solver = OCRSolver(image_path=image_path)
        raw_text = solver.extract()
        
        if not raw_text:
            print("❌ OCR thất bại, không nhìn ra chữ nào trên ảnh.")
            return
            
        print("\n💬 VĂN BẢN OCR THU ĐƯỢC (ĐẦU VÀO CHO AI):")
        print("-" * 40)
        print(raw_text)
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Lỗi trong quá trình quét OCR: {e}")
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
                    "content": """Bạn là chuyên gia kế toán. 
                    - Đọc nội dung văn bản OCR hóa đơn và trích xuất thành object JSON. 
                    - Xóa đi các chữ thừa (logo, lời chào, mã vạch). 
                    - Tự động sửa lỗi chính tả máy quét.
                    - Schema DUY NHẤT trả về: {"shop_name": "", "date": "DD/MM/YYYY", "total_amount": 0, "items": [{"name": "", "quantity": 1, "price": 0}], "category": "Tiếng anh"}
                    - CHỈ output chuỗi JSON."""
                },
                {
                    "role": "user",
                    "content": f"Chuyển cái này qua JSON:\n{raw_text}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.0 
        )

        final_data = json.loads(chat.choices[0].message.content)
        t_llm_end = time.time()
        
        print("\n" + "🔥 "*20)
        print("✅ OUTPUT CUỐI CÙNG CHO HỆ THỐNG CỦA BẠN:")
        print("🔥 "*20)
        print(json.dumps(final_data, indent=4, ensure_ascii=False))
        
        t_total_end = time.time()
        
        print("\n" + "=" * 50)
        print("⏱️ THỐNG KÊ THỜI GIAN THỰC THI (TRACKING TIME):")
        print("-" * 50)
        print(f"👉 1. Thời gian cào OCR (imgtotext.net):  {t_ocr_end - t_ocr_start:.2f} giây")
        print(f"👉 2. Thời gian AI xử lý JSON (Groq):     {t_llm_end - t_llm_start:.2f} giây")
        print(f"🚀 TÔNG THỜI GIAN TOÀN BỘ QUY TRÌNH:      {t_total_end - t_start:.2f} giây")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Có lỗi ở khâu Groq AI: {e}")

if __name__ == "__main__":
    process_bill_pipeline("bill1.png")
