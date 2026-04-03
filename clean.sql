DROP VIEW IF EXISTS public.v_bills_summary CASCADE;
DROP VIEW IF EXISTS public.v_invoice_summary CASCADE;

DROP TABLE IF EXISTS public.bill_items CASCADE;
DROP TABLE IF EXISTS public.bills CASCADE;
DROP TABLE IF EXISTS public.invoice_items CASCADE;
DROP TABLE IF EXISTS public.invoices CASCADE;

DROP FUNCTION IF EXISTS public.fn_set_updated_at() CASCADE;
