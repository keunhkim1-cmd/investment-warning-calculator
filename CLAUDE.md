# 근형봇 — AI operator guide

Read this file first in every new session. It encodes the invariants that the
existing source already enforces, so future edits do not silently regress them.

> Status: stable. Last updated: 2026-05-07.

This project is a Korean market-data utility (investment-warning lookup, price
thresholds, DART disclosures, KRX/Naver providers) plus a Telegram bot webhook,
deployed as Vercel serverless handlers in region `icn1` with a weekday cache
warmer cron. Domain terminology stays in Korean (`투자주의`, `투자경고`,
`투자위험`, `단기과열`); code, comments, and docs default to English.

## 🛑 Never do

1. **Do not put business logic in `api/*.py`.** GET endpoints are 4-line shims
   over `lib.api_routes.ROUTES_BY_PATH[...]`; the route is defined once in
   `lib/api_routes.py` (`ROUTES` tuple) so `serve.py` and Vercel functions
   share the exact same payload, error shape, and CDN-cache header. POST,
   cron, and token-protected handlers (`api/telegram.py`, `api/warm-cache.py`,
   `api/cache-bust.py`, `api/debug.py`) keep their own handlers but still
   delegate logic to `lib/usecases.py` or feature modules.
2. **Do not open URLs directly inside provider adapters.** Always go through
   `lib/http_client.py` so retry, redaction, logging, and per-provider rate
   limiting apply uniformly.
3. **Do not duplicate `crtfc_key`, DART URL construction, or DART status
   handling outside `lib/dart_base.py`.** `lib/dart.py`, `lib/dart_registry.py`,
   and `lib/dart_report.py` keep domain-specific responsibilities only.
4. **Do not add new top-level legacy error fields.** JSON responses use
   `ok: true` on success; on failure use `ok: false` with `errorInfo.code` and
   `errorInfo.message`. The only intentional `errorMessage` compatibility
   surface is `/api/caution-search` (and the matching `serve.py` route) until
   older caution clients finish migrating.
5. **Do not share Production secrets with Preview** unless the Preview
   deployment is protected. Production-only values: `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `CACHE_ADMIN_TOKEN`,
   `CRON_SECRET`.
6. **Do not expose `SUPABASE_SERVICE_ROLE_KEY` to browser JavaScript** or use
   the ambiguous legacy `SUPABASE_KEY` name in Vercel. Legacy name is only
   honored when `SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY=true`, reserved for
   short-lived local migration work.
7. **Do not commit real API keys in VCR cassettes.** The recording fixture
   filters secret query params and headers; verify before committing a new
   cassette.
8. **Do not run `pytest --record-mode=once` in CI or hooks.** CI runs with
   recording disabled so new external calls fail loudly instead of silently
   hitting live providers. Record cassettes intentionally in a local session.
9. **Do not enable `ALERT_TELEGRAM_ENABLED=true` locally or in CI.** It is a
   Production-only fallback for free-plan log drains.
10. **Do not leave `DEBUG_ENABLED=true` outside a protected environment.**
    `/api/debug` exposes environment and cache health detail.
11. **Do not mix broad repo-wide ruff formatting with behavioral changes.**
    Format only changed Python files; the first lint gate is intentionally
    bug-focused (`select = ["E9", "F"]`) to avoid one-time formatting churn.
12. **Do not raise `tool.coverage.report.fail_under` (currently 34) for
    coverage's sake.** Raise it only after adding tests that protect real user
    or provider behavior.
13. **Do not expand `tool.mypy.files` ahead of cleanup.** Add one dependency
    boundary at a time, only after the current target passes without
    suppressing useful errors.
14. **Do not revert unrelated local changes** when editing. Check `git status`
    before staging.

## ✅ Always do

1. **Run the fast verification gate** before deploy or any non-trivial refactor.
   Verification:

   ```bash
   python -m ruff check .
   python -m mypy
   python -m compileall -q lib api scripts tests serve.py
   python -m pytest -m "not external" --disable-socket --allow-hosts=127.0.0.1,localhost --record-mode=none --cov --cov-report=term-missing
   python -m json.tool vercel.json
   python scripts/check_frontend_smoke.py
   python scripts/check_frontend_tokens.py
   ```

   These mirror `.github/workflows/qa.yml` and `.pre-commit-config.yaml`
   pre-push hooks; CI will fail on the same checks.
2. **Mock provider calls at the adapter boundary** in tests (`lib/<provider>.py`),
   not at `urllib`/`requests` level. Tests requiring live external APIs must
   carry the `external` marker (excluded from CI and pre-push).
3. **For new external providers, follow the adapter checklist** in
   `ARCHITECTURE.md` §Provider Adapter Checklist: adapter under `lib/`, route
   through `lib/http_client.py`, register timeout in `lib/timeouts.py`, register
   rate limit in `lib/provider_rate_limit.py`, typed error in `lib/errors.py`
   when callers need stable codes, orchestration in `lib/usecases.py`, env keys
   in `.env.example`, ops/security entries in `OPERATIONS.md` / `SECURITY.md`,
   tests with the adapter mocked.
4. **After production deploy, verify the Telegram webhook target.**
   Verification: `python3 scripts/set_telegram_webhook.py --info` should print
   the canonical Production URL (currently `https://kh-bot.vercel.app/api/telegram`).
   If it points at an old Vercel domain or returns `307 Temporary Redirect`,
   re-run `python3 scripts/set_telegram_webhook.py` (without `--info`) to reset.
5. **Use `git status --short`** before any edit to confirm the worktree is the
   one you expect.

## 📋 Change type → files to touch

| What you want to change | Files (in order) | Verification |
|---|---|---|
| Add a new external provider | `lib/<provider>.py` (via `http_client`) → `lib/timeouts.py` → `lib/provider_rate_limit.py` → `lib/errors.py` (if typed) → `lib/usecases.py` → `api/<endpoint>.py` → `.env.example` → `OPERATIONS.md` + `SECURITY.md` → `tests/test_<provider>.py` | Fast gate above |
| Add a GET JSON endpoint | `lib/usecases.py` (`<name>_payload(...)`) → `lib/api_routes.py` (append `ApiRoute` to `ROUTES`) → `api/<kebab>.py` (4-line `RouteHandler` shim) → `vercel.json` (`maxDuration`, headers, CDN cache) → `tests/test_api_contract.py` | Fast gate; `curl` against `python3 serve.py` |
| Add a POST / cron / protected endpoint | `lib/usecases.py` (logic) → `api/<kebab>.py` (own handler with auth/idempotency/signature) → `vercel.json` (cron, `maxDuration`) → tests | Fast gate; trigger with required token after deploy |
| Add a Telegram command | `lib/telegram_commands.py` → `lib/telegram_messages.py` → `lib/telegram_transport.py` (transport only if new API surface) → `tests/test_telegram*.py` → optionally `scripts/set_telegram_commands.py` | Fast gate; admin chat smoke after deploy |
| Add a scheduled job | `api/<job>.py` (check `CRON_SECRET` bearer) → `vercel.json` `crons` entry → `lib/warm_cache.py` if it's a warm task → Upstash lock if overlap risk | `python -m json.tool vercel.json`; trigger manually with `CRON_SECRET` after deploy |
| Add an environment variable | `.env.example` → reader/parser in `lib/` → `SECURITY.md` (if a secret) and/or `OPERATIONS.md` (if operational) → `README.md` only when user-facing | Fast gate; `/api/debug` shows `environment.missing` empty |
| Record a new VCR cassette | Run `python -m pytest tests/test_external_cassettes.py --record-mode=once` locally with real keys → confirm secrets filtered → commit | Fast gate must pass with `--record-mode=none` afterward |
| Refresh DART corp registry snapshot | `DART_API_KEY=... python3 scripts/update_dart_corps.py` → re-run fast gate | Fast gate; `data/dart-corps.json` diff is a snapshot update |
| Frontend (HTML/JS/CSS) edit | `index.html` / `assets/*` → `python3 scripts/sync_frontend_metadata.py` → smoke + tokens | `python3 scripts/check_frontend_smoke.py` and `python3 scripts/check_frontend_tokens.py`; Playwright via `pytest tests/test_playwright_flows.py` |

## 🔒 Invariants

| Invariant | Violation symptom |
|---|---|
| GET endpoints are defined once in `lib/api_routes.py`; `api/*.py` is a 4-line `RouteHandler` shim | `serve.py` and Vercel diverge; payload, error shape, or CDN cache silently differs between local and prod |
| POST/cron/protected handlers (`telegram`, `warm-cache`, `cache-bust`, `debug`) keep their own `api/*.py` but delegate to `lib/usecases.py` | Auth/idempotency/signature logic leaks into shared modules, or business logic ends up in transport |
| Provider HTTP goes through `lib/http_client.py` | Lost retry/redaction/rate-limit; raw secrets in logs |
| DART operations route through `lib/dart_base.py` | Duplicated `crtfc_key` handling; inconsistent retryable status set |
| JSON error shape is `{ok: false, errorInfo: {code, message}}` (except legacy `/api/caution-search`) | Clients break when error fields drift |
| Vercel functions read only Vercel env vars; `serve.py` reads `.env.local` then `.env` | Env-only config silently differs between local and deploy |
| New external API calls require an adapter test, not a live integration test | CI breaks intermittently on provider downtime |
| `ALLOWED_ORIGINS=https://kh-bot.vercel.app` is the canonical Production origin | CORS preflights fail for the SPA |
| Region pin `icn1` and cron `10 7 * * 1-5` (16:10 KST, post-Korean cash close) | Warm cache misses the daily window |
| Coverage `fail_under = 34` is a regression floor, not a target | Vanity coverage masks untested behavior |
| Mypy file list expands one boundary at a time | Suppressed errors leak into shared modules |

## 🗺️ Repo map

```
api/                                  # HTTP transport — Vercel serverless handlers (kebab-case URLs)
  cache-bust.py                       # POST /api/cache-bust — delete one durable cache key (CACHE_ADMIN_TOKEN)
  caution-search.py                   # GET  /api/caution-search — investment caution lookup (legacy errorMessage)
  dart-search.py                      # GET  /api/dart-search — DART disclosure search
  debug.py                            # GET  /api/debug — env + cache health (DEBUG_ENABLED gate)
  market-alert-forecast.py            # GET  /api/market-alert-forecast — short-term forecast policy
  market-alerts/investment-warning.py # GET  /api/market-alerts/investment-warning
  stock-code.py                       # GET  /api/stock-code?name= — Naver code lookup
  stock-overview.py                   # GET  /api/stock-overview?code= — combined stock view
  stock-price.py                      # GET  /api/stock-price?code= — Naver price lookup
  telegram.py                         # POST /api/telegram — webhook (signature, idempotency, command routing)
  warm-cache.py                       # POST /api/warm-cache — cron warmer (CRON_SECRET, weekdays 07:10 UTC)
  warn-search.py                      # GET  /api/warn-search?name= — investment warning lookup

lib/                                  # Shared application + adapter layer
  usecases.py                         # Application layer used by api/ and serve.py
  api_routes.py                       # Single source for GET API routes (ROUTES tuple) — api/*.py shims and serve.py both use ROUTES_BY_PATH
  http_client.py                      # Retry, redaction, logging, rate limiting — provider adapters call this
  http_utils.py                       # Common HTTP helpers
  retry.py                            # Retry policy
  timeouts.py                         # Per-provider timeout constants
  provider_rate_limit.py              # Per-minute rate budgets (Upstash-backed when configured)
  errors.py                           # Typed provider errors
  validation.py                       # Input validation
  cache.py                            # In-memory TTL cache
  durable_cache.py                    # Upstash/KV-backed cross-instance cache
  warm_cache.py                       # Cache warmer task definitions
  alerting.py                         # Telegram admin alert fallback (free-plan log drain)
  forecast_policy.py                  # Short-term forecast rules
  warning_policy.py                   # Investment warning policy
  holidays.py                         # Korean market holidays
  supabase_client.py                  # Supabase client (used only by telegram_updates idempotency)

  # Provider adapters
  krx.py                              # KRX KIND lookups
  naver.py                            # Naver finance lookups
  gemini.py                           # Gemini summary
  dart_base.py                        # DART API key + URL + fetch — single source of truth
  dart.py                             # DART disclosure list search
  dart_registry.py                    # DART corp-code registry
  dart_report.py                      # DART business-report extraction
  dart_corp.py                        # DART corp lookup (data/dart-corps.json fallback)

  # Investment warning domain (split modules)
  investment_warning_status.py        # Status orchestration
  investment_warning_dates.py         # Date parsing
  investment_warning_release.py       # Release detection
  investment_warning_rows.py          # Row parsing
  investment_warning_errors.py        # Typed errors

  # Telegram (split layers)
  telegram_commands.py                # Command use cases
  telegram_messages.py                # Text builders
  telegram_transport.py               # Bot API requests
  telegram_idempotency.py             # Update dedup (Upstash + optional Supabase)

serve.py                              # Local dev server; reads .env.local then .env

scripts/                              # Operator-run maintenance utilities
  check_frontend_smoke.py             # Static SPA smoke
  sync_frontend_metadata.py           # Frontend metadata sync (--check)
  set_telegram_webhook.py             # Set/inspect Telegram webhook (--info)
  set_telegram_commands.py            # Set Telegram bot commands
  update_dart_corps.py                # Refresh data/dart-corps.json snapshot

data/                                 # Packaged server-side fallbacks (not browser payloads)
  dart-corps.json                     # DART corp-code fallback (refreshed via scripts/update_dart_corps.py)
  holidays.json                       # Korean market holidays (24h CDN cache)
  patchnotes.json                     # Patch notes (60s SWR)

assets/                               # Static frontend assets (long-cache, immutable)
index.html                            # Single-page app shell

tests/                                # pytest (kept compatible with unittest.TestCase discovery)
  conftest.py                         # Shared fixtures
  test_telegram*.py                   # Webhook + commands + messages
  test_investment_warning_status.py
  test_external_cassettes.py          # VCR.py replay (CI runs --record-mode=none)
  test_playwright_flows.py            # Browser-level (mocked APIs) — runs against serve.py
  test_local_api_smoke.py             # serve.py smoke
  test_api_contract.py                # JSON shape contract checks

supabase/migrations/                  # Telegram idempotency table only

.github/workflows/qa.yml              # CI: ruff → mypy → compile → pytest → vercel.json validate → frontend smoke/budget
.pre-commit-config.yaml               # ruff-check + ruff-format on commit; pytest/mypy/compile on push
vercel.json                           # Fluid; region icn1; cron weekdays 07:10 UTC; per-route headers
pyproject.toml                        # Python 3.14; ruff/mypy/pytest/coverage config
.env.example                          # Authoritative list of supported env vars
```

## 🚀 Deployment

Vercel project deploys to `icn1` with Fluid Compute. `python3 serve.py` mirrors
the handler routing locally; Vercel functions only read Vercel-set env vars,
not `.env*` files. The cache warmer runs at `10 7 * * 1-5` (16:10 KST,
post-Korean cash-market close) and uses `CRON_SECRET` plus an Upstash lock when
configured. `OPERATIONS.md` is the runbook for required post-deploy checks,
log drain setup, rate-limit tuning, and rollback (`vercel rollback`).

## 🎭 Recently decided (don't re-argue)

- **No new top-level `errorMessage`.** Only `/api/caution-search` keeps it
  during the legacy client migration; new endpoints use `errorInfo.code` /
  `errorInfo.message` only.
- **Frontend stays as a static SPA, no bundler.** See `FRONTEND_BUILD_ROI.md`.
  The per-asset size budget gate was retired on 2026-05-11 — re-introduce only
  when an actual constraint (Vercel free-tier cost/bandwidth, Lighthouse
  regression, user-reported latency) bites.
- **DART access consolidated in `lib/dart_base.py`.** Do not propose a per-
  module DART client.
- **Telegram split is intentional**: `api/telegram.py` (transport + dedup +
  routing), `lib/telegram_commands.py` (use cases), `lib/telegram_messages.py`
  (text), `lib/telegram_transport.py` (Bot API). Do not collapse.
- **Investment-warning domain is split into per-concern modules** under
  `lib/investment_warning_*.py`. Do not re-merge into a single file.
- **Mypy expansion is incremental.** `tool.mypy.files` grows one dependency
  boundary at a time after the current set is clean.
- **Coverage `fail_under` is a regression floor**, not a vanity goal. Raise it
  with new behavior tests, not with assertions on existing code.
- **Region pin `icn1`** is intentional for Korean-market data latency.
- **Python 3.14** per `.python-version` and `pyproject.toml`.

## More

- [`README.md`](./README.md) — overview and full local verification commands
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — layer rules, Telegram split,
  provider checklist, JSON response contract
- [`OPERATIONS.md`](./OPERATIONS.md) — deploy checks, rate-limit tuning, log
  drain, free-plan Telegram alerts, cache bust, rollback
- [`SECURITY.md`](./SECURITY.md) — env vars, Supabase, durable cache,
  external rate limits
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — code conventions, test minimums,
  deploy notes
- [`DESIGN.md`](./DESIGN.md) — frontend typography rules
- [`FRONTEND_BUILD_ROI.md`](./FRONTEND_BUILD_ROI.md) — bundler decision record
- [`.env.example`](./.env.example) — authoritative env var list
