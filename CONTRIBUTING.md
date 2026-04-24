# Contributing

## Before Editing

Check the current worktree:

```bash
git status --short
```

Do not revert unrelated local changes.

## Code Conventions

- Python files use `snake_case`; public Vercel endpoint files keep URL-matching
  kebab names under `api/`.
- Keep `api/*.py` thin. Move shared endpoint behavior into `lib/usecases.py`.
- Keep provider calls behind `lib/http_client.py`.
- Prefer typed provider errors from `lib/errors.py` over broad `RuntimeError`
  when callers need a stable response code or message.
- Add type hints to new `lib/` and `scripts/` functions.

## Tests

Use `unittest` and mock network calls at the provider adapter boundary.

Minimum check:

```bash
python3 -m py_compile api/*.py lib/*.py serve.py tests/*.py
python3 -m unittest discover -s tests
```

For frontend changes, also run:

```bash
python3 scripts/check_frontend_smoke.py
python3 scripts/check_frontend_budget.py
```

## Deploy Notes

Use `OPERATIONS.md` for deployment checks and `SECURITY.md` for env/secret
rules. Production and Preview should not share webhook, cache admin, Supabase
service-role, or financial-model tokens unless the Preview is protected.
