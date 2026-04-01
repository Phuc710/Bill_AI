
# 1. Tạo environment ảo (khuyên dùng)
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Cài dependencies
python -m pip install -r requirements.txt

# 3. Chạy server
python -m uvicorn api.main:app --reload --port 8000