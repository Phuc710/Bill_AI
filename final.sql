-- ============================================================
-- Bill AI — Supabase Database Schema (Final)
-- Project: BILLAI | wnzwympdwnnvdzhsxcin.supabase.co
-- ============================================================

-- DỌN DẸP / CHẠY LẠI MỚI TOÀN BỘ (RESET ALL)
DROP VIEW IF EXISTS v_bills_summary CASCADE;
DROP TABLE IF EXISTS bill_items CASCADE;
DROP TABLE IF EXISTS bills CASCADE;
DROP FUNCTION IF EXISTS update_updated_at CASCADE;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE: bills
-- Lưu metadata + kết quả xử lý cho từng hóa đơn
-- ============================================================
CREATE TABLE IF NOT EXISTS bills (
    -- Identity
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT        NOT NULL DEFAULT '',

    -- Pipeline status
    status              TEXT        NOT NULL DEFAULT 'uploaded'
                        CHECK (status IN (
                            'uploaded',     -- Đã nhận ảnh, chưa xử lý
                            'detecting',    -- Đang detect vùng bill (YOLO)
                            'cropping',     -- Đang crop & lưu Storage
                            'ocr_done',     -- OCR hoàn tất
                            'normalizing',  -- Gemini đang chuẩn hóa
                            'completed',    -- Thành công toàn bộ
                            'failed'        -- Lỗi ở bước nào đó
                        )),
    failed_step         TEXT        DEFAULT NULL,   -- detect | ocr | gemini | null
    error_message       TEXT        DEFAULT NULL,

    -- Supabase Storage URLs
    original_image_url  TEXT        DEFAULT NULL,   -- Bills/Original/YYYY/MM/DD/{id}.jpg
    cropped_image_url   TEXT        DEFAULT NULL,   -- Bills/Cropped/YYYY/MM/DD/{id}_crop.jpg

    -- Raw data
    ocr_raw_text        TEXT        DEFAULT '',     -- Text thô từ VnCV OCR
    gemini_raw_response TEXT        DEFAULT NULL,   -- Response JSON gốc từ Gemini

    -- Extracted invoice fields
    store_name          TEXT        DEFAULT NULL,
    address             TEXT        DEFAULT NULL,
    phone               TEXT        DEFAULT NULL,
    invoice_code        TEXT        DEFAULT NULL,   -- Số HĐ
    datetime_in         TIMESTAMPTZ DEFAULT NULL,   -- Giờ vào / ngày in
    datetime_out        TIMESTAMPTZ DEFAULT NULL,   -- Giờ ra (nếu có)
    cashier             TEXT        DEFAULT NULL,   -- Thu ngân
    table_num           TEXT        DEFAULT NULL,   -- Số bàn
    payment_method      TEXT        DEFAULT NULL,   -- CASH | CARD | ...
    currency            TEXT        NOT NULL DEFAULT 'VND',

    -- Money fields (VND, lưu integer để tránh float error)
    subtotal            BIGINT      DEFAULT NULL,
    total               BIGINT      NOT NULL DEFAULT 0,
    cash_given          BIGINT      DEFAULT NULL,
    cash_change         BIGINT      DEFAULT NULL,

    -- Quality metrics
    detect_confidence   FLOAT       DEFAULT 0,
    ocr_confidence      FLOAT       DEFAULT 0,
    processing_ms       FLOAT       DEFAULT 0,
    needs_review        BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TABLE: bill_items
-- Danh sách món ăn / sản phẩm trong từng hóa đơn
-- ============================================================
CREATE TABLE IF NOT EXISTS bill_items (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id     UUID    NOT NULL REFERENCES bills(id) ON DELETE CASCADE,

    name        TEXT    NOT NULL,
    quantity    INT     NOT NULL DEFAULT 1,
    unit_price  BIGINT  NOT NULL DEFAULT 0,
    total_price BIGINT  NOT NULL DEFAULT 0,

    sort_order  INT     DEFAULT 0,  -- Giữ đúng thứ tự xuất hiện trên hóa đơn
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEXES — Tối ưu các query phổ biến
-- ============================================================

-- Lấy danh sách bill của 1 user, sort by mới nhất
CREATE INDEX IF NOT EXISTS idx_bills_user_created
    ON bills (user_id, created_at DESC);

-- Filter theo status (e.g. completed only)
CREATE INDEX IF NOT EXISTS idx_bills_status
    ON bills (status);

-- Filter theo khoảng thời gian (export CSV)
CREATE INDEX IF NOT EXISTS idx_bills_created_at
    ON bills (created_at DESC);

-- JOIN bill_items theo bill_id
CREATE INDEX IF NOT EXISTS idx_bill_items_bill_id
    ON bill_items (bill_id, sort_order ASC);

-- ============================================================
-- FUNCTION: auto-update updated_at on bills
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bills_updated_at
    BEFORE UPDATE ON bills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Mỗi user chỉ đọc/xóa được bill của mình
-- Backend dùng service_role key => bypass RLS hoàn toàn
-- ============================================================
ALTER TABLE bills      ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_items ENABLE ROW LEVEL SECURITY;

-- Chỉ đọc được bill của chính mình (dùng anon/user key)
CREATE POLICY "users_read_own_bills"
    ON bills FOR SELECT
    USING (user_id = auth.uid()::text);

-- Chỉ xóa được bill của chính mình
CREATE POLICY "users_delete_own_bills"
    ON bills FOR DELETE
    USING (user_id = auth.uid()::text);

-- bill_items: đọc theo bill_id thuộc về mình
CREATE POLICY "users_read_own_bill_items"
    ON bill_items FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM bills
            WHERE bills.id = bill_items.bill_id
              AND bills.user_id = auth.uid()::text
        )
    );

-- ============================================================
-- VIEW: v_bills_summary
-- Dùng cho màn lịch sử bill (GET /bills)
-- ============================================================
CREATE OR REPLACE VIEW v_bills_summary WITH (security_invoker = true) AS
SELECT
    b.id,
    b.user_id,
    b.status,
    b.failed_step,
    b.store_name,
    b.datetime_in,
    b.total,
    b.currency,
    b.payment_method,
    b.cropped_image_url,
    b.needs_review,
    b.created_at,
    COUNT(i.id) AS item_count
FROM bills b
LEFT JOIN bill_items i ON i.bill_id = b.id
GROUP BY b.id;
