# 🧾 Kai Bill — Smart Personal Finance Assistant (Backend API)

> **Mục đích Backend**: Cung cấp AI Pipeline trích xuất tự động thông tin hóa đơn (OCR & NLP), phân loại danh mục chi tiêu thông minh, và lưu trữ dữ liệu tập trung cho Mobile App.
> 
> **Mục đích Mobile App (Kai Bill)**: "Trợ lý Tài chính Cá nhân Thông minh" giúp người dùng quản lý chi tiêu mượt mà không cần nhập tay. Chụp bill là biết tiền đi đâu.
> 
> **Stack**: FastAPI · YOLOv8 · VnCV OCR · Gemini AI · Supabase (Postgres + Storage + Auth)

---

## ⚡ Pipeline Flow

```
[Android App (Kai Bill)] ──POST /bills/extract──> [FastAPI Backend]
                                                         │
                                         ┌───────────────┼──────────────────────┐
                                         ▼               ▼                      ▼
                                   [Supabase DB]  [YOLO Detect]         [VnCV OCR]
                                   status=detecting  ─crop─>             ─text─>
                                         │         [Storage Upload]    [Gemini AI]
                                         │         Bills/Cropped/...      (Categorize)
                                         └───────── save_result ───────────┘
                                                   status=completed
                                                         │
                                         <──────JSON Response─────────────────────
```

---

## 🔌 API Reference

### Base URL
```
http://<your-server>:8000
```

### Authentication
> Mọi request (trừ `/health`) **bắt buộc** có header:
> ```
> X-API-Key: <64-char-secret>
> ```
> Sai key → `401 Unauthorized`

### Request Tracking
Mỗi response trả về header `X-Request-Id` để trace log:
```
X-Request-Id: 3a9f12bc0e41
```

---

### `GET /health`
**Server health check** — Không cần auth.

```bash
curl http://localhost:8000/health
```

**Response `200`:**
```json
{
  "status": "ok",
  "version": "3.0.0",
  "model": "gemini-2.0-flash-lite",
  "supabase_configured": true
}
```

---

### `POST /bills/extract`
**Xử lý hóa đơn mới & Tự động phân loại**

```bash
curl -X POST http://localhost:8000/bills/extract \
  -H "X-API-Key: <secret>" \
  -F "image=@bill.jpg" \
  -F "user_id=<supabase-user-uuid>"
```

**Request** (`multipart/form-data`):
| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `image` | File | ✅ | Ảnh hóa đơn (jpg/png/webp, ≤ 10MB) |
| `user_id` | string | ✅ | UUID từ Supabase Auth |

**Response `200` — Thành công:**
```json
{
  "bill_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "original_image_url": "https://.../Bills/Original/YYYY/MM/DD/{id}.jpg",
  "cropped_image_url":  "https://.../Bills/Cropped/YYYY/MM/DD/{id}_crop.jpg",
  "data": {
    "store_name":     "Highlands Coffee",
    "address":        "171 Cao Thắng, P.12, Q.10",
    "phone":          "01213171171",
    "invoice_id":     "2.1-191021-000002",
    "datetime":       "2019-10-21T10:43:00",
    "total":          55000,
    "subtotal":       null,
    "cash_given":     100000,
    "cash_change":    45000,
    "category":       "Ăn uống",
    "currency":       "VND"
  },
  "items": [
    { "name": "Trà Sen Vàng", "quantity": 1, "unit_price": 55000, "total_price": 55000 }
  ],
  "meta": {
    "needs_review":      false,
    "detect_confidence": 0.8540,
    "processing_ms":     4200.0,
    "gemini_error":      null
  }
}
```

**Response `200` — Lỗi pipeline** (bill vẫn được lưu DB với status `failed`):
```json
{
  "bill_id": "...",
  "status": "failed",
  "failed_step": "detect",
  "message": "Không phát hiện Bill trong ảnh",
  "original_image_url": "https://...",
  "cropped_image_url": null,
  "data": null,
  "items": [],
  "meta": { "processing_ms": 5200.0 }
}
```

**Các `failed_step` có thể xảy ra:**
| Step | Nguyên nhân |
|------|-------------|
| `detect` | YOLO không tìm thấy bill trong ảnh |
| `ocr` | OCR không đọc được văn bản sau khi crop |
| `gemini` | Gemini lỗi (quota, timeout...) |
| `db_init` | Không kết nối được Supabase |
| `unknown` | Lỗi không xác định |

---

### `GET /bills`
**Danh sách hóa đơn của user**

```bash
curl "http://localhost:8000/bills?user_id=<uuid>&page=1&limit=20" \
  -H "X-API-Key: <secret>"
```

**Query params:**
| Param | Type | Default | Mô tả |
|-------|------|---------|-------|
| `user_id` | string | required | UUID từ Supabase Auth |
| `page` | int | `1` | Trang hiện tại |
| `limit` | int | `20` | Số bill mỗi trang (max 100) |
| `status` | string | all | Filter: `completed`, `failed`, etc. |

**Response `200`:**
```json
{
  "data": [
    {
      "id": "550e...",
      "user_id": "user-uuid",
      "status": "completed",
      "store_name": "Highlands Coffee",
      "total_amount": 55000,
      "currency": "VND",
      "payment_method": "CASH",
      "category": "Ăn uống",
      "cropped_image_url": "https://...",
      "needs_review": false,
      "created_at": "2026-04-02T14:00:00Z",
      "failed_step": null
    }
  ],
  "page": 1,
  "limit": 20
}
```

---

### `GET /bills/{bill_id}`
**Chi tiết 1 hóa đơn**

```bash
curl http://localhost:8000/bills/550e8400-... \
  -H "X-API-Key: <secret>"
```

**Response `200`:** Cấu trúc đầy đủ như `POST /bills/extract`.
**Response `404`:** Bill không tồn tại.

---

### `DELETE /bills/{bill_id}`
**Xóa hóa đơn** (DB + Storage)

```bash
curl -X DELETE http://localhost:8000/bills/550e8400-... \
  -H "X-API-Key: <secret>"
```

**Response `200`:**
```json
{ "success": true, "bill_id": "550e8400-..." }
```

---

## 🗄️ Database Schema (`final.sql`)

### Bảng `invoices` (Có lưu Category)
```sql
id, user_id, status, failed_step, error_message
original_image_url, cropped_image_url
ocr_raw_text, gemini_raw_response
store_name, address, phone, invoice_number
issued_at, closed_at, cashier_name, table_number
currency
subtotal, discount_amount, total_amount, cash_tendered, cash_change
category -- (Ăn uống, Di chuyển, Mua sắm, Dịch vụ, Khác)
detect_confidence, ocr_confidence, processing_time_ms, needs_review
created_at, updated_at
```

### Bảng `invoice_items`
```sql
id, invoice_id (FK → invoices.id), item_name, quantity, unit_price, total_price, sort_order
```

### View `v_invoice_summary`
Dùng cho màn Lịch Sử trên **Kai Bill App**, trả về thông tin tóm tắt và `item_count` (số lượng món) + `category`.

---

## 📦 Supabase Storage

**Bucket:** `Bills` (Public)

```
Bills/
├── Original/YYYY/MM/DD/{bill_id}.jpg
└── Cropped/YYYY/MM/DD/{bill_id}_crop.jpg
```

---

## ⚙️ Setup & Run

### 1. Cài dependencies
```bash
pip install -r requirements.txt
```

### 2. Tạo database
Chạy `final.sql` trên [Supabase SQL Editor](https://supabase.com/dashboard/project/wnzwympdwnnvdzhsxcin/sql).

### 3. Cấu hình
`cp .env.example .env` → điền các key.

### 4. Chạy server
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📋 Production Logging

Log ghi vào `logs/api.log` + console với format:
```
2026-04-02 14:00:00 | INFO | billai.access  | [abc123] POST /bills/extract | status=200 | 4200ms | ip=... | user=...
2026-04-02 14:00:00 | INFO | billai.pipeline| [bill-uuid] Detected conf=0.854 bbox=[192,157,1338,828]
2026-04-02 14:00:00 | INFO | billai.pipeline| [bill-uuid] COMPLETED | store=Highlands Coffee total=55000 ms=4200
```

---

*Kai Bill Backend v3.0*
