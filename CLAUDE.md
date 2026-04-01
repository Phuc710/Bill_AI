# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

### Environment setup (Windows)
```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Run the app
```bash
python -m uvicorn api.main:app --reload --port 8000
```

### Manual verification flow
1. Start server with uvicorn.
2. Open `http://localhost:8000`.
3. Upload invoice image — extraction runs in a single call.
4. Verify `logs/` JSON output and CSV export.

### Test scripts
```bash
python test/pure_model_test.py
python test/drop_bill_test.py
```

## High-level architecture

### System shape
Single-service FastAPI application:
- API endpoints under `/api/*`
- Browser UI from `frontend/index.html` (served at `/`)
- Static frontend assets under `/assets`
- Generated pipeline artifacts under `/outputs`

Entry point: `api/main.py`.

### Core request flow (v2.1 — single call)
1. Frontend uploads image to `POST /api/process`.
2. API reads the file bytes and calls `InvoicePipeline.run()` via `run_in_threadpool`.
3. Pipeline: Load → Detect → Standardize → OCR → Gemini → Log → Return.
4. API returns structured JSON with extraction results + image URLs.
5. Frontend renders fields and allows CSV export via `POST /api/export-csv`.

Legacy 2-step flow (`/api/upload-invoice` → `/api/extract-invoice`) is still supported for backward compatibility.

### Pipeline stages (`core/pipeline.py`)
1. Load image bytes → PIL Image
2. Detect receipt region (`core/detector.py`) — lazy-loaded YOLOv8
3. Standardize image (`core/standardizer.py`) — crop, resize, deskew, enhance
4. OCR (`core/ocr.py`) — EasyOCR primary, YOLO fallback (lazy-loaded)
5. Build plain text from OCR lines
6. Gemini Flash structuring (`core/gemini_extractor.py`) — lazy-loaded client
7. Log + return (`core/logger.py`)

### Key design decisions
- **Lazy model loading**: All ML models (YOLO, EasyOCR, Gemini) load on first use, not at import/startup.
- **Single endpoint**: `/api/process` replaces the 2-step upload → extract flow.
- **No PaddleOCR**: Removed — was never installable from requirements.txt.
- **Overlay images**: Detection overlay is conditional via `Config.SAVE_DEBUG_IMAGES`.
- **Stateless helpers**: Scoring, parsing, overlay functions are module-level and stateless.

### Data contracts
- API schemas: `api/schemas.py` (Gemini-aligned: `SELLER`, `PRODUCTS`, `TOTAL_COST`).
- Per-request logs: `logs/<request_id>.json`.
- Output images: `outputs/` (`_orig.jpg`, `_detect.jpg`, `_proc.jpg`, `_ocr.jpg`).

### Config
Central config: `core/config.py`.
- Model files: `models/detec.pt`, `models/ocr.pt`.
- Gemini keys from `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`).
- `Config.ensure_dirs()` is called **once** at app startup via lifespan handler.