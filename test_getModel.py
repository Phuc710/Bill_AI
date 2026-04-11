from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv() # Load from .env

# Lấy API Key từ biến môi trường
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("❌ Lỗi: Chưa cung cấp GROQ_API_KEY trong environment variables.")
    os._exit(1)

def get_all_groq_models():
    try:
        # Khởi tạo client
        client = Groq(api_key=api_key)
        
        # Lấy danh sách model
        models = client.models.list()
        
        print(f"{'STT':<5} | {'Model ID':<40} | {'Owned By':<15}")
        print("-" * 65)
        
        for i, model in enumerate(models.data, 1):
            print(f"{i:<5} | {model.id:<40} | {model.owned_by:<15}")
            
        print("-" * 65)
        print(f"Tổng cộng có {len(models.data)} models khả dụng.")

    except Exception as e:
        print(f"Có lỗi xảy ra: {e}")
        print("Hãy kiểm tra lại API Key của bạn.")

if __name__ == "__main__":
    get_all_groq_models()