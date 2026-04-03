-- ============================================================
-- Bill AI — Supabase Database Schema (Production v2)
-- Dự án: Trích Xuất Hóa Đơn Thông Minh (Invoice Extraction)
-- Database: PostgreSQL (Supabase)
-- Project: wnzwympdwnnvdzhsxcin.supabase.co
-- ============================================================

-- ============================================================
-- RESET: Dọn dẹp toàn bộ trước khi tạo mới
-- Chạy section này nếu bạn muốn reset sạch CSDL
-- ============================================================
DROP VIEW  IF EXISTS v_invoice_summary   CASCADE;
DROP TABLE IF EXISTS invoice_items       CASCADE;
DROP TABLE IF EXISTS invoices            CASCADE;
DROP FUNCTION IF EXISTS fn_set_updated_at CASCADE;

-- Kích hoạt extension tạo UUID
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
-- TABLE: invoices
-- Mục đích: Lưu toàn bộ thông tin của 1 hóa đơn đã được xử lý.
--
-- Luồng xử lý (Pipeline Status):
--   uploaded → detecting → cropping → ocr_done → normalizing → completed
--                                                             → failed
-- ============================================================
CREATE TABLE IF NOT EXISTS invoices (

    -- ── Định danh ─────────────────────────────────────────────
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL,   -- Khóa ngoại khớp với auth.users(id)

    -- ── Trạng thái pipeline ───────────────────────────────────
    -- Theo dõi hóa đơn đang ở bước nào trong quy trình xử lý AI
    status          TEXT        NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN (
                        'uploaded',     -- Đã nhận ảnh, chưa xử lý
                        'detecting',    -- YOLO đang phát hiện vùng hóa đơn
                        'cropping',     -- Đang cắt & lưu ảnh lên Storage
                        'ocr_done',     -- VnCV OCR đã đọc xong văn bản
                        'normalizing',  -- Gemini AI đang phân tích và chuẩn hóa
                        'completed',    -- Hoàn tất toàn bộ pipeline
                        'failed'        -- Thất bại tại một bước nào đó
                    )),
    failed_step     TEXT        DEFAULT NULL
                    CHECK (failed_step IN ('detect', 'ocr', 'gemini', 'db_init', 'unknown', NULL)),
    error_message   TEXT        DEFAULT NULL,   -- Mô tả lỗi chi tiết (nếu failed)

    -- ── Ảnh lưu trên Supabase Storage ────────────────────────
    -- URL công khai (public URL) của ảnh trong bucket "Bills"
    original_image_url  TEXT    DEFAULT NULL,   -- Bills/Original/YYYY/MM/DD/{id}.jpg
    cropped_image_url   TEXT    DEFAULT NULL,   -- Bills/Cropped/YYYY/MM/DD/{id}_crop.jpg

    -- ── Dữ liệu thô từ pipeline ──────────────────────────────
    ocr_raw_text        TEXT    DEFAULT '',     -- Văn bản thô đọc từ VnCV OCR
    gemini_raw_response TEXT    DEFAULT NULL,   -- Response JSON gốc từ Gemini AI

    -- ── Thông tin cửa hàng / nhà cung cấp ────────────────────
    store_name      TEXT        DEFAULT NULL,   -- Tên cửa hàng / nhà hàng
    store_address   TEXT        DEFAULT NULL,   -- Địa chỉ cửa hàng
    store_phone     TEXT        DEFAULT NULL,   -- Số điện thoại cửa hàng

    -- ── Thông tin hóa đơn ─────────────────────────────────────
    invoice_number  TEXT        DEFAULT NULL,   -- Số hóa đơn (invoice code)
    issued_at       TIMESTAMPTZ DEFAULT NULL,   -- Ngày/giờ xuất hóa đơn (giờ vào)
    closed_at       TIMESTAMPTZ DEFAULT NULL,   -- Giờ ra (nếu là nhà hàng)
    cashier_name    TEXT        DEFAULT NULL,   -- Tên thu ngân
    table_number    TEXT        DEFAULT NULL,   -- Số bàn (áp dụng cho nhà hàng)
    currency        TEXT        NOT NULL DEFAULT 'VND',

    -- ── Các khoản tiền (lưu BIGINT tránh lỗi float với VND) ──
    subtotal        BIGINT      DEFAULT NULL,   -- Tạm tính (trước giảm giá/thuế)
    discount_amount BIGINT      DEFAULT NULL,   -- Số tiền giảm giá (nếu có)
    total_amount    BIGINT      NOT NULL DEFAULT 0, -- TỔNG CỘNG phải trả
    cash_tendered   BIGINT      DEFAULT NULL,   -- Tiền khách đưa
    cash_change     BIGINT      DEFAULT NULL,   -- Tiền thối lại
    payment_method  TEXT        DEFAULT NULL,   -- CASH | CARD | TRANSFER

    -- ── Chỉ số chất lượng pipeline ────────────────────────────
    -- Dùng để đánh giá độ tin cậy của kết quả trích xuất
    detect_confidence   FLOAT   NOT NULL DEFAULT 0, -- Độ tin cậy phát hiện hóa đơn (0.0–1.0)
    ocr_confidence      FLOAT   NOT NULL DEFAULT 0, -- Độ tin cậy nhận dạng văn bản (0.0–1.0)
    processing_time_ms  FLOAT   NOT NULL DEFAULT 0, -- Tổng thời gian xử lý (milliseconds)
    needs_review        BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE nếu kết quả cần kiểm tra lại bởi người dùng

    -- ── Timestamps ────────────────────────────────────────────
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  invoices IS 'Bảng chính lưu toàn bộ hóa đơn đã được xử lý qua AI pipeline.';
COMMENT ON COLUMN invoices.user_id          IS 'UUID của người dùng từ Supabase Auth.';
COMMENT ON COLUMN invoices.status           IS 'Trạng thái hiện tại trong pipeline xử lý.';
COMMENT ON COLUMN invoices.needs_review     IS 'TRUE khi AI không tự tin về kết quả, cần người dùng kiểm tra.';
COMMENT ON COLUMN invoices.total_amount     IS 'Tổng số tiền phải trả, lưu dạng số nguyên (VND).';
COMMENT ON COLUMN invoices.detect_confidence IS 'Điểm tin cậy từ model YOLO (0.0 = không chắc, 1.0 = chắc chắn).';


-- ============================================================
-- TABLE: invoice_items
-- Mục đích: Lưu danh sách từng mặt hàng / món ăn trong hóa đơn.
-- Quan hệ: Nhiều items thuộc về 1 invoice (Many-to-One).
-- ============================================================
CREATE TABLE IF NOT EXISTS invoice_items (

    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID    NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,

    item_name       TEXT    NOT NULL,               -- Tên mặt hàng / món ăn
    quantity        INT     NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price      BIGINT  NOT NULL DEFAULT 0 CHECK (unit_price >= 0),  -- Đơn giá
    total_price     BIGINT  NOT NULL DEFAULT 0 CHECK (total_price >= 0), -- Thành tiền

    sort_order      SMALLINT NOT NULL DEFAULT 0,    -- Thứ tự xuất hiện trên hóa đơn gốc

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  invoice_items IS 'Danh sách mặt hàng / sản phẩm được trích xuất từ hóa đơn.';
COMMENT ON COLUMN invoice_items.invoice_id   IS 'Khóa ngoại tới bảng invoices. Xóa invoice sẽ xóa luôn items.';
COMMENT ON COLUMN invoice_items.sort_order   IS 'Giữ đúng thứ tự các mặt hàng như trên hóa đơn gốc.';
COMMENT ON COLUMN invoice_items.unit_price   IS 'Đơn giá của 1 đơn vị sản phẩm (VND, số nguyên).';
COMMENT ON COLUMN invoice_items.total_price  IS 'Thành tiền = quantity × unit_price (VND, số nguyên).';


-- ============================================================
-- INDEXES — Tối ưu hiệu năng cho các truy vấn phổ biến
-- ============================================================

-- [Query] Lấy danh sách hóa đơn của 1 user, sort theo mới nhất → App Android History screen
CREATE INDEX IF NOT EXISTS idx_invoices_user_created
    ON invoices (user_id, created_at DESC);

-- [Query] Lọc hóa đơn theo trạng thái (ví dụ: chỉ lấy 'completed')
CREATE INDEX IF NOT EXISTS idx_invoices_status
    ON invoices (status) WHERE status != 'completed';

-- [Query] Thống kê chi tiêu theo khoảng thời gian (Export CSV)
CREATE INDEX IF NOT EXISTS idx_invoices_issued_at
    ON invoices (user_id, issued_at DESC) WHERE issued_at IS NOT NULL;

-- [Query] JOIN invoice_items theo invoice + giữ đúng thứ tự
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id
    ON invoice_items (invoice_id, sort_order ASC);


-- ============================================================
-- FUNCTION + TRIGGER: Tự động cập nhật cột updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
SET search_path = ''   -- Bảo mật: tránh tấn công qua search_path injection
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
-- Nguyên tắc:
--   - User thường (anon key): Chỉ đọc và xóa dữ liệu của CHÍNH MÌNH.
--   - Backend (service_role key): Bypass RLS hoàn toàn → Ghi/cập nhật thoải mái.
-- ============================================================
ALTER TABLE invoices        ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items   ENABLE ROW LEVEL SECURITY;

-- [Policy] User chỉ đọc được hóa đơn của chính mình (App Android dùng anon key)
CREATE POLICY "policy_user_select_own_invoices"
    ON invoices FOR SELECT
    USING (user_id = auth.uid());

-- [Policy] User chỉ xóa được hóa đơn của chính mình
CREATE POLICY "policy_user_delete_own_invoices"
    ON invoices FOR DELETE
    USING (user_id = auth.uid());

-- [Policy] User chỉ đọc được items của hóa đơn thuộc về mình
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
-- Mục đích: Cung cấp dữ liệu tóm tắt cho màn Lịch Sử (History Screen)
--           trên App Android. Bao gồm số lượng món trong mỗi hóa đơn.
-- Bảo mật: security_invoker = true → View tuân thủ đúng RLS của bảng gốc.
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
    inv.payment_method,
    inv.cropped_image_url,
    inv.needs_review,
    inv.processing_time_ms,
    inv.created_at,
    COUNT(itm.id)::INT AS item_count   -- Số lượng mặt hàng trong hóa đơn
FROM       invoices     inv
LEFT JOIN  invoice_items itm ON itm.invoice_id = inv.id
GROUP BY   inv.id;

COMMENT ON VIEW v_invoice_summary IS 'View tóm tắt hóa đơn dùng cho màn Lịch Sử trên App Android. Trả về thông tin cơ bản + số lượng món.';
