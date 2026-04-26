-- The financial-model endpoint and its cache layer were removed; drop the
-- table and trigger function it relied on. telegram_updates remains.

drop table if exists public.financial_data cascade;
drop function if exists public.set_financial_data_updated_at();
