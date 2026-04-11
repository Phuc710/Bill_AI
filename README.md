# 🧾 Kai Bill — Smart Personal Finance Assistant (Backend API)

> **Mục đích Backend**: Cung cấp AI Pipeline trích xuất tự động thông tin hóa đơn siêu tốc (Offline OCR & NLP), tự động tính toán đối chiếu tổng tiền, phân loại danh mục, và lưu trữ dữ liệu tập trung cho Mobile App.
> 
> **Mục đích Mobile App (Kai Bill)**: "Trợ lý Tài chính Cá nhân Thông minh" giúp người dùng quản lý chi tiêu mượt mà không cần nhập tay. Chụp bill là biết tiền đi đâu.
> 
> **Stack hiện tại**: FastAPI · VnCV (ONNX OCR Offline) · Groq Llama 3.3-70B · Supabase (Postgres + Storage + Auth)

---

## ⚡ Pipeline Flow (Kiến trúc chuẩn Production)

```
[Android App (Kai Bill)] ── POST /bills/extract ──> [FastAPI Backend]
                                                            │
                                         ┌──────────────────┼─────────────────────────┐
                                         ▼                  ▼                         ▼
                                   [Supabase DB]      [Storage Upload]            [VnCV OCR]
                                 status=detecting    url=Original/...    ─text─> (Warmup Cached)
                                         │                                            │
                                         │                                    [Groq Llama 3.3]
                                         │                                      (JSON & Math check)
                                         └────────── save_result ─────────────────────┘
                                                   status=completed
                                                            │
                                         <────── API JSON Response ───────────────────
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
Mỗi request được monitor và trả về header ID để trace log dưới nền Terminal/Server:
```
X-Request-Id: 3a9f12bc0e41
```

---

### `GET /health`
**Server health check** — Không cần auth.
Đảm bảo hệ thống Llama và Backend đang Ready.

```bash
curl http://localhost:8000/health
```

---

### `POST /bills/extract`
**Upload hóa đơn mới & Xử lý Trí tuệ nhân tạo (OCR+AI)**

```bash
curl -X POST http://localhost:8000/bills/extract \
  -H "X-API-Key: <secret>" \
  -F "file=@bill.jpg;type=image/png" \
  -F "user_id=<supabase-user-uuid>"
```

**Request** (`multipart/form-data`):
| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `file` | File | ✅ | Ảnh hóa đơn (jpg/png/webp, tối đa 10MB) |
| `user_id` | string | ✅ | UUID từ Supabase Auth theo chuẩn CSDL (Bắt buộc) |

**Response `200` — Thành công:**
```json
{
  "bill_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "failed_step": null,
  "message": "Khách hàng uống 2 cà phê và 1 trà đào...", // Summary AI tự tóm tắt
  "original_image_url": "https://.../Bills/Original/YYYY/MM/DD/{id}.jpg",
  "cropped_image_url": "https://.../Bills/Original/YYYY/MM/DD/{id}.jpg", 
  "data": {
    "store_name": "Highlands Coffee",
    "store_address": "171 Cao Thắng, P.12, Q.10",
    "store_phone": "01213171171",
    "invoice_number": "20191021-02",
    "issued_at": "2019-10-21 10:43:00",
    "total_amount": 55000,
    "subtotal": null,
    "cash_tendered": null,
    "cash_change": null,
    "payment_method": null,
    "category": "Ăn uống",
    "currency": "VND"
  },
  "items": [
    { "item_name": "Trà Sen Vàng", "quantity": 1, "unit_price": 55000, "total_price": 55000 }
  ],
  "meta": {
    "detect_confidence": 1.0, 
    "processing_ms": 10500.0, // Thời gian xử lý hệ thống ~10s
    "llm_error": null
  }
}
```

**Response `200` — Pipeline thất bại giữa chừng** (Bill vẫn được lưu DB ở dạng nháp với `status: failed`):
Lỗi được trả về `message` kèm thông tin lỗi thô để hiển thị trên UI.
```json
{
  "bill_id": "...",
  "status": "failed",
  "failed_step": "ocr",
  "message": "Không tìm thấy văn bản trên ảnh",
  ...
}
```

---

### `PUT /bills/{bill_id}`
*(Tham khảo mã hệ thống cho endpoint Update / Patch hóa đơn)*
Người dùng edit hóa đơn, field `message` trên API sẽ được patch qua cột `summary` nhằm lưu bản ghi chú chỉnh sửa vào CSDL.

---

### `GET /bills` & `GET /bills/{bill_id}`
API truy vấn thông tin hóa đơn và lịch sử trả về nguyên vẹn kiến trúc tương đồng `BillResponse` của extraction.

---

## 🗄️ Database Schema (`final.sql`)

Cơ sở dữ liệu hoàn thiện Production:

### Bảng `invoices`
```sql
id, user_id, status, failed_step, error_message
original_image_url, cropped_image_url
ocr_raw_text, summary, llm_raw_response -- (Dữ liệu Thô OCR & Llama)
store_name, store_address, store_phone, invoice_number -- (Store info)
issued_at, closed_at, cashier_name, table_number, payment_method, currency  -- (Invoice Metadata)
subtotal, discount_amount, total_amount, cash_tendered, cash_change -- (Giá tiền)
category -- (Phân loại AI)
detect_confidence, ocr_confidence, processing_time_ms
created_at, updated_at
```

### Bảng `invoice_items`
```sql
id, invoice_id (FK → invoices.id), item_name, quantity, unit_price, total_price, sort_order
```

### View `v_invoice_summary`
Query rút gọn trích xuất riêng `store_name`, `total_amount`, ID kèm `item_count` siêu tốc (Chuyên phục vụ màn Lịch sử Mobile App).

---

## 📦 Supabase Storage

**Bucket:** `Bills` (Public)

```
Bills/
└── Original/YYYY/MM/DD/{bill_id}.jpg
```

---

## ⚙️ Setup & Run (Dev/Prod Mode)

### 1. Cài dependencies
Hệ thống sử dụng Python 3.x với requirements chuẩn:
```bash
pip install -r requirements.txt
```

### 2. Update Database & Supabase
Vào [Supabase SQL Editor](https://supabase.com/dashboard/project/wnzwympdwnnvdzhsxcin/sql), copy toàn bộ nội dung file `final.sql` và RUN để thiết lập bảng.

### 3. Cấu hình Runtime
Copy file `.env.example` thành `.env`, điền đầy đủ `GROQ_API_KEY` và `SUPABASE_KEY`.

### 4. Chạy Server Start Uvicorn
Uvicorn sẽ load trước ONNX Weights của hệ thống Offline OCR ngay khi khởi động (`warmup`) giúp request về sau mượt và chuẩn dưới 10s.
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📋 Production Logging & Tracker
Log ghi chuẩn xác luồng thông tin vào console Terminal/server:
```
2026-04-04 15:40:27 | INFO | billai.routes  | [2fbc3] extract_bill START | bill=b4dffd2c-.. file=bill.jpg user=uuid
2026-04-04 15:40:36 | INFO | billai.pipeline| [b4dffd2c-..] OCR done | chars=367 | conf=0.890 | time=5707ms
2026-04-04 15:40:38 | INFO | billai.pipeline| [b4dffd2c-..] LLM done | error=None | total=537000 | time=1546ms
2026-04-04 15:40:39 | INFO | billai.pipeline| [b4dffd2c-..] COMPLETED | store=Nhà Hàng | total=537000 | ocr=5707ms | llm=1546ms | total=10910ms
```
Hệ thống tự động phát hiện `Math warnings` để backend log và theo dõi chất lượng trích xuất.

---

## 📱 Yêu cầu Tối ưu Mobile Client (Client-Side Optimization)

Để đạt tốc độ xử lý **< 15s** và tiết kiệm băng thông, Mobile App (Android/iOS) nên thực hiện các bước tiền xử lý sau trước khi gọi API:

### 1. Sử dụng Google ML Kit Document Scanner
* **Mô tả**: Thay vì chụp ảnh thô, hãy tích hợp [ML Kit Document Scanner API](https://developers.google.com/ml-kit/vision/doc-scanner).
* **Lợi ích**: Tự động nhận diện 4 góc, bẻ phẳng (Perspective Correction), khử bóng và làm nét chữ. Giúp OCR Backend đạt độ chính xác gần như 100%.

### 2. Định dạng & Kích thước ảnh
* **Định dạng**: Chuyển đổi sang **WebP** (Quality 80-85). Kích thước file sẽ giảm ~70% so với JPEG mà không mất chi tiết viền chữ.
* **Resize**: Giới hạn cạnh dài nhất (**Max Side**) ở mức **1280px**. To hơn mức này không giúp tăng độ chính xác nhưng làm chậm OCR đáng kể.
* **Màu sắc**: Nếu được, hãy chuyển ảnh sang **Grayscale** (Trắng đen) để giảm dung lượng file xuống mức tối thiểu (300KB - 500KB).

### 3. Quy trình gửi Ideal
`Chụp (ML Kit) -> Crop & Deskew -> Resize (1280px) -> Convert WebP -> POST /extract`

---
*Cập nhật và hoàn thiện cho dự án Kai Bill Backend v3.0 / Production Ready 🚀*
