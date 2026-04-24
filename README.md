# Shamanism Research

Korean market-data utility for investment-warning lookup, price thresholds,
DART disclosure search, financial-model JSON, and a Telegram bot webhook.

## Local Development

```bash
python3 serve.py
```

The local server reads `.env.local` first and then `.env`. Vercel functions read
only Vercel environment variables.

## Verification

Run these before deploy or broad refactors:

```bash
python3 -m py_compile api/*.py lib/*.py serve.py tests/*.py
python3 -m unittest discover -s tests
python3 -m json.tool vercel.json
python3 scripts/check_frontend_smoke.py
python3 scripts/check_frontend_budget.py
```

## Main Runtime Paths

- Static app: `index.html`, `assets/`
- Serverless handlers: `api/`
- Shared use cases and adapters: `lib/`
- Static server-side data: `data/`
- Maintenance scripts: `scripts/`

See `ARCHITECTURE.md`, `OPERATIONS.md`, and `SECURITY.md` for structure,
operations, and secret-handling rules.
