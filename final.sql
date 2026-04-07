-- ============================================================
-- Bill AI — Supabase Database Schema (Production)
-- Dự án: Trích Xuất Hóa Đơn Thông Minh (Invoice Extraction)
-- Database: PostgreSQL (Supabase)
-- ============================================================
-- HƯỚNG DẪN: Chạy toàn bộ file này trên Supabase SQL Editor.
-- File này bao gồm: RESET → CREATE → INDEX → RLS → VIEW
-- ============================================================

-- ============================================================
-- RESET — Dọn dẹp toàn bộ trước khi tạo mới
-- ============================================================
DROP VIEW     IF EXISTS v_invoice_summary   CASCADE;
DROP TABLE    IF EXISTS invoice_items       CASCADE;
DROP TABLE    IF EXISTS invoices            CASCADE;
DROP FUNCTION IF EXISTS fn_set_updated_at  CASCADE;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
-- TABLE: invoices
-- Lưu toàn bộ thông tin của 1 hóa đơn đã được xử lý.
--
-- Pipeline Status:
--   uploaded → detecting → cropping → ocr_done → normalizing → completed
--                                                             → failed
-- ============================================================
CREATE TABLE invoices (

    -- ── Định danh ─────────────────────────────────────────────
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL,  -- Khớp với auth.users(id)

    -- ── Trạng thái pipeline ───────────────────────────────────
    status      TEXT        NOT NULL DEFAULT 'uploaded'
                CHECK (status IN (
                    'uploaded', 'detecting', 'cropping',
                    'ocr_done', 'normalizing', 'completed', 'failed'
                )),
    failed_step TEXT        DEFAULT NULL
                CHECK (failed_step IN ('detect', 'ocr', 'llm', 'db_init', 'unknown', NULL)),
    error_message TEXT      DEFAULT NULL,

    -- ── Ảnh lưu trên Supabase Storage ────────────────────────
    original_image_url  TEXT DEFAULT NULL,  -- Bills/Original/YYYY/MM/DD/{id}.jpg
    cropped_image_url   TEXT DEFAULT NULL,  -- Bills/Cropped/YYYY/MM/DD/{id}_crop.jpg

    -- ── Dữ liệu thô từ pipeline ──────────────────────────────
    ocr_raw_text        TEXT DEFAULT '',
    summary             TEXT DEFAULT NULL,
    llm_raw_response    TEXT DEFAULT NULL,

    -- ── Thông tin cửa hàng ────────────────────────────────────
    store_name    TEXT DEFAULT NULL,
    store_address TEXT DEFAULT NULL,
    store_phone   TEXT DEFAULT NULL,

    -- ── Thông tin hóa đơn ─────────────────────────────────────
    invoice_number TEXT        DEFAULT NULL,
    issued_at      TIMESTAMPTZ DEFAULT NULL,  -- Ngày/giờ xuất hóa đơn
    closed_at      TIMESTAMPTZ DEFAULT NULL,  -- Giờ ra (nếu là nhà hàng)
    cashier_name   TEXT        DEFAULT NULL,
    table_number   TEXT        DEFAULT NULL,
    payment_method TEXT        DEFAULT NULL,
    currency       TEXT        NOT NULL DEFAULT 'VND',

    -- ── Tiền (BIGINT tránh lỗi float với VND) ────────────────
    subtotal        BIGINT DEFAULT NULL,
    discount_amount BIGINT DEFAULT NULL,
    total_amount    BIGINT NOT NULL DEFAULT 0,
    cash_tendered   BIGINT DEFAULT NULL,
    cash_change     BIGINT DEFAULT NULL,

    -- ── Phân loại chi tiêu (AI tự đoán từ Groq Llama) ────────────
    category        TEXT NOT NULL DEFAULT 'Khác'
                    CHECK (category IN (
                        'Ăn uống',    -- Nhà hàng, café, trà sữa, quán ăn
                        'Di chuyển',  -- Grab, Be, xăng, vé xe
                        'Mua sắm',    -- Siêu thị, quần áo, điện thoại
                        'Dịch vụ',    -- Điện, nước, internet, y tế
                        'Khác'
                    )),

    -- ── Chỉ số chất lượng pipeline ────────────────────────────
    detect_confidence  FLOAT   NOT NULL DEFAULT 0,
    ocr_confidence     FLOAT   NOT NULL DEFAULT 0,
    processing_time_ms FLOAT   NOT NULL DEFAULT 0,
    needs_review       BOOLEAN NOT NULL DEFAULT FALSE,

    -- ── Timestamps ────────────────────────────────────────────
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  invoices IS 'Bảng chính lưu toàn bộ hóa đơn đã được xử lý qua AI pipeline.';
COMMENT ON COLUMN invoices.category   IS 'Danh mục chi tiêu do Groq AI tự phân loại.';
COMMENT ON COLUMN invoices.user_id    IS 'UUID của người dùng từ Supabase Auth.';
COMMENT ON COLUMN invoices.needs_review IS 'TRUE khi AI không tự tin về kết quả, cần người dùng kiểm tra.';


-- ============================================================
-- TABLE: invoice_items
-- Danh sách từng mặt hàng / món ăn trong hóa đơn.
-- ============================================================
CREATE TABLE invoice_items (

    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id  UUID    NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,

    item_name   TEXT    NOT NULL,
    quantity    INT     NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price  BIGINT  NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    total_price BIGINT  NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    sort_order  SMALLINT NOT NULL DEFAULT 0,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  invoice_items IS 'Danh sách mặt hàng được trích xuất từ hóa đơn.';
COMMENT ON COLUMN invoice_items.sort_order  IS 'Giữ đúng thứ tự các mặt hàng như trên hóa đơn gốc.';


-- ============================================================
-- INDEXES
-- ============================================================

-- Lấy danh sách hóa đơn của 1 user (History screen)
CREATE INDEX idx_invoices_user_created
    ON invoices (user_id, created_at DESC);

-- Lọc theo trạng thái
CREATE INDEX idx_invoices_status
    ON invoices (status) WHERE status != 'completed';

-- Thống kê theo ngày phát hành (Export CSV)
CREATE INDEX idx_invoices_issued_at
    ON invoices (user_id, issued_at DESC) WHERE issued_at IS NOT NULL;

-- Thống kê chi tiêu theo danh mục
CREATE INDEX idx_invoices_user_category
    ON invoices (user_id, category);

-- JOIN invoice_items
CREATE INDEX idx_invoice_items_invoice_id
    ON invoice_items (invoice_id, sort_order ASC);


-- ============================================================
-- TRIGGER: Tự động cập nhật updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoices_set_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- - User (anon key) : chỉ đọc/xóa dữ liệu của chính mình.
-- - Backend (service_role key) : bypass RLS hoàn toàn.
-- ============================================================
ALTER TABLE invoices      ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "policy_user_select_own_invoices"
    ON invoices FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "policy_user_delete_own_invoices"
    ON invoices FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "policy_user_select_own_invoice_items"
    ON invoice_items FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM   invoices
            WHERE  invoices.id      = invoice_items.invoice_id
              AND  invoices.user_id = auth.uid()
        )
    );


-- ============================================================
-- VIEW: v_invoice_summary
-- Dùng cho màn Lịch Sử (History Screen) trên App Android.
-- Bao gồm: thông tin cơ bản + category + số lượng món.
-- ============================================================
CREATE OR REPLACE VIEW v_invoice_summary
WITH (security_invoker = true) AS
SELECT
    inv.id,
    inv.user_id,
    inv.status,
    inv.failed_step,
    inv.store_name,
    inv.invoice_number,
    inv.issued_at,
    inv.total_amount,
    inv.currency,
    inv.category,
    inv.cropped_image_url,
    inv.needs_review,
    inv.processing_time_ms,
    inv.created_at,
    COUNT(itm.id)::INT AS item_count
FROM      invoices     inv
LEFT JOIN invoice_items itm ON itm.invoice_id = inv.id
GROUP BY  inv.id;

COMMENT ON VIEW v_invoice_summary IS 'View tóm tắt hóa đơn dùng cho History Screen trên App Android.';
