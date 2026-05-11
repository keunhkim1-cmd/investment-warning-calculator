# Operations Runbook

## External API Integration

### Environment Sync

Local development reads `.env` when running `python3 serve.py`, but deployed
functions only read Vercel environment variables.

Recommended flow:

1. Pull scoped Vercel values when you need an exact local mirror:
   `vercel env pull .env.local`
2. Run local smoke checks with Vercel-provided env:
   `vercel env run -- python3 serve.py`
3. Keep Production and Preview values separate for:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `CACHE_ADMIN_TOKEN`
   - `CRON_SECRET`

Required production checks:

- `/api/telegram` should report `configured`.
- `python3 scripts/set_telegram_webhook.py --info` should report the canonical
  Production URL, currently `https://kh-bot.vercel.app/api/telegram`. If it
  points at an old Vercel domain or reports `307 Temporary Redirect`, run
  `python3 scripts/set_telegram_webhook.py`.
- `/api/warm-cache` should return 401 without Vercel's cron bearer token, not 503.

### Required Checks After Deploy

1. Open `/api/debug` with `DEBUG_ENABLED=true` only in a protected environment.
   Confirm:
   - `durable_cache_enabled` is `true` when Upstash is configured.
   - `provider_rate_limits_per_minute` matches the intended production limits.
   - `environment.missing` is empty for enabled features.

2. Exercise one low-cost request per public endpoint:
   - `/api/stock-code?name=삼성전자`
   - `/api/stock-price?code=005930`
   - `/api/warn-search?name=삼성전자`
   - `/api/caution-search?name=삼성전자`

3. Check Vercel Logs for:
   - `external_api_call` with `result=success`
   - no burst of `external_api_retry`
   - no unexpected `provider_rate_limit_exceeded`

### Frontend Static Smoke

After frontend edits, run:

```bash
python3 scripts/check_frontend_smoke.py
```

See `FRONTEND_BUILD_ROI.md` for the current bundler decision record. The
per-asset size budget gate was retired on 2026-05-11 — re-introduce only when
an actual constraint (Vercel free-tier cost/bandwidth, Lighthouse regression,
user-reported latency) bites.

### Cache Hit/Miss Audit

Set `CACHE_ACCESS_LOGS_ENABLED=true` briefly, then repeat the same endpoint calls.
Turn it off after collecting enough logs.

Useful events:

- `cache_access`: cache name, key, state (`hit`, `miss`, `stale`, `durable_hit`)
- `cache_stale_returned`: stale fallback was used after an upstream failure
- `gemini_summary_stale_returned`: Gemini summary stale data was returned

### Rate Limit Audit

Useful events:

- `external_api_call`: provider, result, elapsed, attempts, rate wait
- `external_api_retry`: retry attempt and delay
- `provider_rate_limit_wait`: request waited locally before calling provider
- `provider_rate_limit_exceeded`: provider budget exhausted beyond max wait

Suggested first production limits:

- `EXTERNAL_RATE_DART_PER_MINUTE=900`
- `EXTERNAL_RATE_KRX_PER_MINUTE=120`
- `EXTERNAL_RATE_NAVER_PER_MINUTE=180`
- `EXTERNAL_RATE_GEMINI_PER_MINUTE=10`
- `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE=0`
- `EXTERNAL_RATE_TELEGRAM_PER_MINUTE=900`

Set `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE` only after you know your Gemini
project TPM limit. The value is measured in estimated 1K-token units per minute.

### Log Drain Monitoring

Use a Vercel Log Drain or the Logflare Vercel integration to retain runtime logs
outside Vercel's short live-log window. This project already emits structured
JSON-like events through `log_event`, so the first dashboard should stay narrow:

- Error stream: `level:error`, grouped by `event`, `provider`, and endpoint.
- External API health: `external_api_call`, `external_api_retry`,
  `provider_rate_limit_wait`, and `provider_rate_limit_exceeded`.
- Fallback quality: `cache_stale_returned` and `gemini_summary_stale_returned`.
- Telegram delivery: webhook 5xx logs, `telegram_duplicate_update`, and
  `telegram_info_unhandled`.

First alert rules:

- Any `level:error` spike above the normal baseline for 5 minutes.
- More than 3 `provider_rate_limit_exceeded` events in 10 minutes.
- Any `cache_stale_returned` event during market hours.
- Telegram webhook 5xx or timeout events.

Setup path:

1. Create one drain/source for this Vercel project rather than mixing all
   projects in one source.
2. Include runtime function logs for Production first; add Preview after noise is
   understood.
3. Trigger the Required Checks After Deploy requests and confirm logs are parsed
   by event fields.
4. Save the dashboard URL and alert recipients in the team's password manager or
   operations notes, not in the repository.

### Free-Plan Telegram Alerts

If Vercel Log Drains are unavailable on the current plan, enable compact
Telegram admin alerts instead. This does not replace retained logs or dashboards,
but it catches the first high-signal failure in each cooldown window.

Production environment variables:

- `ALERT_TELEGRAM_ENABLED=true`
- `TELEGRAM_BOT_TOKEN=...`
- `ALERT_TELEGRAM_CHAT_IDS=123456789` or reuse `TELEGRAM_ADMIN_CHAT_IDS`
- `ALERT_TELEGRAM_MIN_LEVEL=warning`
- `ALERT_TELEGRAM_COOLDOWN_SECONDS=900`
- `ALERT_TELEGRAM_EVENTS=` to use the default high-signal event set

Default alerted events:

- `external_api_call` only when `result=failure`
- `external_api_retry`
- `provider_rate_limit_exceeded`
- `cache_stale_returned`, `gemini_summary_stale_returned`
- `warm_cache_task_failed`, `warm_cache_lock_failed`
- `telegram_update_failed`, `telegram_info_summary_failed`

Notes:

- Telegram provider events are skipped to avoid alert loops.
- Alerts are best-effort and per function instance; cooldown state is in memory.
- Keep `ALERT_TELEGRAM_ENABLED=false` locally and in CI unless testing alerting.
- If alerts get noisy, set `ALERT_TELEGRAM_EVENTS` to a comma-separated subset,
  for example `provider_rate_limit_exceeded,cache_stale_returned,telegram_update_failed`.

### Monthly QA Maintenance

Dependabot checks Python tooling and GitHub Actions monthly. For each PR:

1. Confirm CI passes with network disabled tests and coverage.
2. Re-record VCR cassettes only when provider response contracts intentionally
   changed.
3. Raise coverage only when added tests protect real endpoint, provider, or
   frontend behavior.
4. Expand `tool.mypy.files` by one dependency boundary after the current list is
   clean.

### Manual Cache Bust

Use `/api/cache-bust` only with `CACHE_ADMIN_TOKEN`. It deletes one durable
cache key from Upstash. Warm in-memory entries inside already-running function
instances may remain until their local TTL expires.

Example durable keys:

- `krx-kind:kind:1:1:21:1000:YYYY-MM-DD`
- `market-alert-forecast:latest:v1`
- `naver-code:code:삼성전자`
- `dart-report-summary:summary:005930:RCEPT_NO:v1`

### Scheduled Cache Warm

`vercel.json` runs `/api/warm-cache` at 07:10 UTC, Monday-Friday. That is
16:10 KST, shortly after the Korean cash-market close.

The job warms:

- KRX warning/risky pages
- KRX caution page
- investment-warning forecast snapshot (`market-alert-forecast:latest:v1`)
- DART corp registry in Upstash (`dart:corp-registry:v1`)
- Samsung Electronics Naver price lookup
- KOSPI/KOSDAQ index price lookups
- DART corp-code map

Set `CRON_SECRET` in Production before deployment. With Upstash configured, the
job uses a Redis lock to avoid overlapping runs.

`/api/market-alert-forecast` is read-only against this durable snapshot. The
snapshot TTL is 7 days so weekend/holiday gaps and a few failed cron runs keep
serving the last successful result. Public user requests do not call KRX or
Naver directly; if the snapshot is missing, the endpoint returns an empty
"preparing" forecast with a `forecast-cache` source error until the next
successful weekday 16:10 KST warm-cache run.

### KIND IP Block (KRX 403) — Follow-ups

KRX KIND (`kind.krx.co.kr`) periodically WAF-blocks Vercel egress IPs and
returns 403 even when the same URL/headers succeed from a non-Vercel IP.
This is not solvable in code. What is already in place:

- 403 is treated as non-retryable for the `krx` provider
  (`lib/http_client.py`); retries within seconds never recover and only
  double `external_api_retry` alert traffic.
- `_krx_cache` (warning/caution GETs) and `_status_cache`
  (investment-warning status orchestrator) both fall back to stale entries
  for up to 6 hours on error.
- `_invwarn_rows_cache` does the same per-stockCode for the
  `fetch_investment_warning_rows` POST.
- `/api/warn-search` and `/api/market-alerts/investment-warning` translate
  KRX 403 into a `temporary_limit` status payload (HTTP 200) so the SPA and
  Telegram bot do not surface 500.

Operational follow-ups when blocks persist beyond the 6-hour stale window:

1. Request a Vercel egress IP whitelist from KRX KIND support. Vercel's
   outbound IPs are documented per region; `icn1` is the relevant one. This
   is the cheapest long-term fix.
2. If a whitelist is not feasible, route KIND-only traffic through a
   forward proxy on a non-Vercel IP (e.g., a tiny fly.io/render service or
   a Cloudflare Worker on a non-blocked IP). Keep the proxy scoped to
   `kind.krx.co.kr` only, with the same `BROWSER_HEADERS` and rate budget
   as `lib/http_client.py`.

Monitoring:

- `external_api_call` with `provider=krx` and `status=403` indicates the
  block is active. Cross-reference with `cache_stale_returned` (cache=
  `krx-kind`, `investment-warning-status`, or `kind-invwarn-rows`) to
  confirm the stale fallback is absorbing the outage.
- If `temporary_limit` status appears in `/api/market-alerts/investment-warning`
  responses, the per-stockCode cache had no entry to fall back to. That is
  the user-visible signal that an operational fix is overdue.

### DART Corp Registry Refresh

`/api/warm-cache` refreshes the DART registry from `corpCode.xml` into Upstash
on weekdays. `data/dart-corps.json` is the bundled fallback for exact company
lookup when Upstash is unavailable or cold. Refresh the snapshot after
meaningful listing changes, or schedule it in a trusted maintenance environment:

```bash
DART_API_KEY=... python3 scripts/update_dart_corps.py
python -m pytest -m "not external" --disable-socket --allow-hosts=127.0.0.1,localhost --record-mode=none
```

### Telegram Webhook

Telegram retries webhooks when the function times out or fails before returning
200. With Upstash configured, update processing claims expire after
`TELEGRAM_IDEMPOTENCY_PROCESSING_TTL`, while completed updates remain deduped for
`TELEGRAM_IDEMPOTENCY_DONE_TTL`.

Long term, `/info` should move to an acknowledge-first flow if real p95 exceeds
Telegram webhook tolerance.

### Rollback

If a Production deployment is bad but a previous deployment is healthy:

1. List recent Production deployments with `vercel list`.
2. Inspect the known-good deployment with `vercel inspect <deployment-url>`.
3. Promote or roll back from the Vercel dashboard, or use
   `vercel rollback <deployment-url>` when the CLI is available.
4. Re-run the Required Checks After Deploy section.
