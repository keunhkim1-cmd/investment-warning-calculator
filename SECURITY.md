# Security Operations

## Vercel Environment Variables

Production and Preview should use separate values for all secrets:

- `DART_API_KEY`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `CACHE_ADMIN_TOKEN`
- `CRON_SECRET`

Do not use the ambiguous legacy `SUPABASE_KEY` name in Vercel. The code only accepts it when
`SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY=true`, which should be limited to temporary local
migration work.

Preview deployments should not share production bot, Supabase service-role, or
cache admin tokens unless the preview deployment is protected. Use separate
Preview values where practical, and keep Production-only values for anything
that can mutate data or receive external webhooks.

## Supabase

Supabase is optional and currently used only by the Telegram webhook idempotency
store (`telegram_updates`). Keep the service-role key in serverless environment
variables only — never expose it to browser JavaScript. The original runtime
cache migration also created the removed `financial_data` table; apply
`supabase/migrations/20260426000000_drop_financial_data_cache.sql` after
`supabase/migrations/20260424000000_create_runtime_cache_tables.sql` so only the
Telegram idempotency store remains.

## Dependency Audit

Dependencies are pinned in `requirements.txt`. Re-run an OSV or pip-audit scan before
updating pins, and update the whole Supabase dependency set together.

## Durable Runtime Cache

When `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN` or Vercel Marketplace's
`KV_REST_API_URL`/`KV_REST_API_TOKEN` are set, selected server-side caches use
Upstash Redis as a cross-instance TTL cache. Keep those variables server-only.

The `/api/cache-bust` endpoint deletes a single durable cache key. Protect it
with `CACHE_ADMIN_TOKEN`. It does not purge already-warm in-memory entries
inside other Vercel function instances, so short local TTLs still apply.

The `/api/warm-cache` cron endpoint is protected with `CRON_SECRET`. Vercel
automatically sends this value as a bearer token for configured cron jobs. Keep
`CRON_SECRET` different from user-facing API tokens and set it in Production
before enabling the cron.

## External Rate Limits

Provider-wide rate limiting is enabled by default through
`EXTERNAL_RATE_LIMITS_ENABLED=true`. With Upstash configured, limits are shared
across Vercel function instances; without Upstash they are per warm instance.

Tune these values after looking at `external_api_call`,
`provider_rate_limit_wait`, and `provider_rate_limit_exceeded` logs:

- `EXTERNAL_RATE_DART_PER_MINUTE`
- `EXTERNAL_RATE_KRX_PER_MINUTE`
- `EXTERNAL_RATE_NAVER_PER_MINUTE`
- `EXTERNAL_RATE_GEMINI_PER_MINUTE`
- `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE`
- `EXTERNAL_RATE_TELEGRAM_PER_MINUTE`
- `EXTERNAL_RATE_LIMIT_MAX_WAIT`

Set `CACHE_ACCESS_LOGS_ENABLED=true` temporarily when you need hit/miss/stale
ratios from Vercel Logs. Leave it off during normal operation if log volume
matters.
