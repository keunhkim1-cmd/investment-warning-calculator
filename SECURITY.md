# Security Operations

## Vercel Environment Variables

Production and Preview should use separate values for all secrets:

- `DART_API_KEY`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `FINANCIAL_MODEL_API_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Do not use the ambiguous legacy `SUPABASE_KEY` name in Vercel. The code only accepts it when
`SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY=true`, which should be limited to temporary local
migration work.

## Supabase Cache

The `financial_data` table is a server-side cache used by the authenticated
`/api/financial-model` endpoint. Keep the Supabase service-role key in serverless
environment variables only. Never expose it to browser JavaScript.

Recommended cache behavior:

- `SUPABASE_SERVICE_ROLE_KEY`: set only in server environments that need cache reads.
- `SUPABASE_CACHE_WRITES=false`: default. The API reads existing cache but does not write.
- `SUPABASE_CACHE_WRITES=true`: enable only after confirming the endpoint auth token,
  rate limit, and logging redaction are active in the same environment.

Recommended table hardening:

```sql
alter table public.financial_data enable row level security;

-- Do not create anon/authenticated policies for this cache table.
-- Serverless functions use SUPABASE_SERVICE_ROLE_KEY and endpoint-level auth.
revoke all on table public.financial_data from anon, authenticated;
```

## Dependency Audit

Dependencies are pinned in `requirements.txt`. Re-run an OSV or pip-audit scan before
updating pins, and update the whole Supabase dependency set together.
