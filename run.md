
# 1. Tạo environment ảo (khuyên dùng)
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Cài dependencies
python -m pip install -r requirements.txt

# 3. Chạy server
python -m uvicorn api.main:app --reload --port 8000

# 00000000-0000-0000-0000-000000000001, a3f8c2d9e1b4f7a0c5e2d8b3f1a6c9e4b7d2a5f8c3e0b6d9a2e5b8c1f4d7a0e3



Service type: Web Service
Build Command: pip install -r requirements.txt
Start Command: uvicorn api.main:app --host 0.0.0.0 --port $PORT
Env quan trọng: PYTHON_VERSION=3.12.10 (nên pin, vì Render default mới đã lên 3.14.x)