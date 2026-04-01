# Bill AI

## Models Confirmed
| Model | Path | Role |
|---|---|---|
| [detec.pt](file:///c:/Users/Phucc/Downloads/billAI/detec.pt) | [models/detec.pt](file:///c:/Users/Phucc/Downloads/billAI/models/detec.pt) | YOLOv8 — detect bill bounding box |
| [ocr.pt](file:///c:/Users/Phucc/Downloads/billAI/ocr.pt) | [models/ocr.pt](file:///c:/Users/Phucc/Downloads/billAI/models/ocr.pt) | YOLO-based OCR — read text + bbox |

## Core Logic: Key → Value Extraction
OCR lines are sorted top-to-bottom. Each line is scanned for a **key** keyword (e.g., `"Tổng tiền:"`). The value associated with that key is extracted from the **same line** (after the `:` or `—`) or the **next adjacent cell** on the same row. Only keys that match the target schema are kept; all others are ignored.

```
Input ảnh
→ Validate (format + size)
→ YOLOv8 detect bill  ──── no bill? → EXIT (status: no_bill_detected)
→ Chuẩn hóa ảnh (crop + deskew + denoise + CLAHE)
→ OCR (ocr.pt) → text + bbox + confidence
→ Clean text (ký tự rác, chuẩn hóa số/ngày/MST)
→ Key-Value Extract → fill target schema
→ Validate output (format + confidence flag)
→ Log (request_id, ảnh, OCR raw, output, thời gian, status)
→ Structured Output JSON
```

---

## New Project Structure

```
billAI/
├── models/
│   ├── detec.pt          ← YOLOv8 bill detector (đã move vào đây)
│   └── ocr.pt            ← YOLO OCR model (đã move vào đây)
├── core/
│   ├── config.py         ← Config tập trung (paths, thresholds)
│   ├── logger.py         ← PipelineTracker (request_id, step logging)
│   ├── detector.py       ← BillDetector — detect + bbox + conf
│   ├── standardizer.py   ← ImageStandardizer — crop/deskew/denoise
│   ├── ocr.py            ← OCREngine — text + bbox + conf từ ocr.pt
│   ├── text_cleaner.py   ← TextCleaner — normalize text
│   ├── extractor.py      ← FieldExtractor — KV map → schema
│   └── validator.py      ← OutputValidator — format + flag review
├── api/
│   ├── main.py           ← FastAPI app
│   ├── schemas.py        ← Pydantic models
│   └── routes/
│       └── invoice.py    ← API routes
├── frontend/
│   └── index.html        ← Single-page UI
├── logs/                 ← Per-request JSON logs (auto-created)
├── outputs/              ← Saved images (auto-created)
├── target_schema.json    ← Schema định nghĩa output bắt buộc
└── requirements.txt      ← Updated
```

---

## Proposed Changes

### [NEW] target_schema.json
```json
{
  "tax_code":        { "value": null, "confidence": 0, "needs_review": false },
  "transaction_date":{ "value": null, "confidence": 0, "needs_review": false },
  "total_amount":    { "value": null, "confidence": 0, "needs_review": false },
  "items": []
}
```

---

### Core Modules

#### [NEW] core/config.py
```python
class Config:
    DETEC_MODEL = "models/detec.pt"
    OCR_MODEL   = "models/ocr.pt"
    DETEC_CONF  = 0.4   # Ngưỡng confidence detect bill
    OCR_CONF    = 0.3   # Ngưỡng confidence OCR
    MAX_IMG_PX  = 1600
    LOW_CONF_THRESHOLD = 0.6  # Dưới mức này gắn needs_review=True
```

#### [NEW] core/detector.py — `BillDetector`
- [detect(image) → BillRegion(bbox, confidence)](file:///c:/Users/Phucc/Downloads/billAI/app.py#200-216)
- Nếu `confidence < DETEC_CONF` hoặc không có box → raise `NoBillError`
- Vẽ bbox màu đỏ vào ảnh debug
- Chỉ trả về **bbox + conf**, không làm gì thêm

#### [NEW] core/standardizer.py — `ImageStandardizer`
- `standardize(image, bbox) → PIL.Image`
- Bước 1: Crop theo bbox
- Bước 2: Deskew (sửa nghiêng)
- Bước 3: Resize về max 1600px
- Bước 4: Grayscale → denoise → CLAHE

#### [NEW] core/ocr.py — `OCREngine`
- Load [ocr.pt](file:///c:/Users/Phucc/Downloads/billAI/ocr.pt) một lần khi khởi tạo
- [extract(image) → list[OCRLine]](file:///c:/Users/Phucc/Downloads/billAI/pipeline.py#94-139)
- `OCRLine = { text: str, bbox: [x1,y1,x2,y2], confidence: float }`
- Sort lines top→bottom, left→right

#### [NEW] core/text_cleaner.py — `TextCleaner`
- `clean(lines) → list[OCRLine]`
- Xóa ký tự rác (`|`, `_`, `—`)
- Chuẩn hóa số tiền: `636.000` `636,000` → `636000`
- Chuẩn hóa ngày: nhiều format → `DD/MM/YYYY`
- Chuẩn hóa MST: giữ chỉ `[0-9-]`

#### [NEW] core/extractor.py — `FieldExtractor`
**Key mapping (tiếng Việt + many aliases):**
| Keywords | Field |
|---|---|
| `mst`, `mã số thuế`, `tax` | `tax_code` |
| `ngày`, [date](file:///c:/Users/Phucc/Downloads/billAI/config.py#30-32), `thời gian`, `hóa đơn ngày` | `transaction_date` |
| `tổng cộng`, `tổng tiền`, [total](file:///c:/Users/Phucc/Downloads/billAI/validator.py#110-121), `khách trả` | `total_amount` |
| `tên hàng`, `mô tả`, `diễn giải`, `sản phẩm` | `items[].name` |
| `sl`, `số lượng`, `qty`, `đvt` | `items[].qty` |
| `đ.giá`, `đơn giá`, `unit price`, `giá` | `items[].unit_price` |
| `t.tiền`, `thành tiền`, [amount](file:///c:/Users/Phucc/Downloads/billAI/app.py#142-160) | `items[].total` |

Logic:
1. Sort lines top→bottom
2. With each line: normalize text → check keyword map
3. If key matches → extract value from same line (after `:` or [tab](file:///c:/Users/Phucc/Downloads/billAI/formatter.py#7-50)) or adjacent line
4. If no match → skip

#### [NEW] core/validator.py — `OutputValidator`
- MST: `^\d{10}(-\d{3})?$`
- Date: parseable string
- Total: numeric > 0
- Fields with `confidence < 0.6` → `needs_review = True`

#### [NEW] core/logger.py — `PipelineTracker`
Logs the entire pipeline per request:
```json
{
  "request_id": "uuid",
  "timestamp": "ISO8601",
  "status": "success | no_bill_detected | fail | need_review",
  "timing_ms": { "detect": 0, "standardize": 0, "ocr": 0, "extract": 0 },
  "original_image": "outputs/xxx_orig.jpg",
  "processed_image": "outputs/xxx_proc.jpg",
  "detector_confidence": 0.92,
  "ocr_raw": [...],
  "result": { ...target_schema... }
}
```

---

### API Layer (FastAPI)

#### [NEW] api/schemas.py
```python
class InvoiceItem(BaseModel): name, qty, unit_price, total
class InvoiceResult(BaseModel): request_id, status, result, log_path
```

#### [NEW] api/routes/invoice.py
| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload-invoice` | Upload image → validate → save → return `request_id` |
| POST | `/extract-invoice` | Run pipeline from `request_id` → return result |
| GET | `/result/{id}` | Fetch results by `request_id` |
| POST | `/export-csv` | Export results to CSV |

#### [NEW] api/main.py
- FastAPI app, CORS, mount frontend
- `GET /` returns `frontend/index.html`

---

### Frontend

#### [NEW] frontend/index.html
- Upload (drag-and-drop)
- Image preview + red bbox after detection
- Result table (editable cells, yellow = `needs_review`)
- Confidence badge per field
- Export CSV/Excel button

---

## Verification Plan

1. `pip install fastapi uvicorn ultralytics pillow opencv-python-headless python-multipart`
2. `uvicorn api.main:app --reload`
3. Open `http://localhost:8000`
4. Test with local images.
5. Check logs in `logs/`
6. Export CSV
