# CLAUDE.md — PACT-Compute

Current review assignment (13 November 2026): remain on `sasha-work`, do not push/merge or change production. Current RC assessment, commands, commit plan and external blockers are in reports/release-candidate/RELEASE_ASSESSMENT.md and PROGRESS.md. The prior milestone is retained in reports/final-validation; older totals below are historical. No commit has been made. Use fresh isolated databases and preserve private env files. Do not regenerate old evidence against changed source.

Private GPU exchange: React+TS frontend, FastAPI backend, SQLAlchemy/Alembic (PostgreSQL or SQLite), research worker, native GPU runner, research experiments.

## Layout
- Project lives in `pact-compute/` (run ALL project commands from there). Plan/handoff copies `PACT-Compute_*.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `BACKUP_RESTORE.md`, `Dockerfile` and `deploy/entrypoint.sh` are at the repo root and committed. Sasha's machine also has a git-excluded `docs/` folder; a fresh clone does not.
- `pact-compute/backend/pact/` API (`api.py`, `market_api.py`), DB (`db.py`), live ops (`live.py`, `runner.py`), research (`research.py`, ...), `config.py`.
- `pact-compute/backend/migrations/` Alembic (0001-0007; `alembic upgrade head`). `pact-compute/frontend/` React console (esbuild). `pact-compute/tests/` pytest. `pact-compute/scripts/start.ps1|stop.ps1`.
- `PACT-Compute-data-preflight/` (repo root) = hashed source datasets; `.gitattributes` marks it `-text` (CRLF conversion breaks manifest SHA-256).
- Secrets: `pact-compute/.env` (gitignored; Neon PostgreSQL + Groq). `.local/` holds runtime state (ignored).

## Commands that worked (Windows PowerShell, Python 3.11.9, Node 25, from `pact-compute/`)
```powershell
python -m venv .venv; & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Tests (SQLite; always override DB url in the command, never in .env)
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:PACT_DATABASE_URL='sqlite:///C:/Users/<you>/pact_test.db'  # any writable path outside the repo; C:/Temp may not exist
& .\.venv\Scripts\python.exe -m pytest -q
# Frontend
cd frontend; npm.cmd ci; npm.cmd run build   # tsc --noEmit + esbuild -> frontend/dist
# Run API on loopback
$env:PYTHONPATH='backend'; & .\.venv\Scripts\python.exe -m uvicorn pact.api:app --host 127.0.0.1 --port 8765   # GET /api/health
```
Verified on a fresh clone with no `.env`: 235 backend tests pass, `npm.cmd ci`, `npm.cmd run build` and `npm.cmd test` (33 node tests) pass, and the API serves `/api/health` and the console on SQLite. Clone to a SHORT path (e.g. `C:/Users/<you>/pf`): under a very deep path pip silently drops files (`moto/utilities`), and `test_artifact_stores_local_s3_and_integrity` fails with `No module named 'moto.utilities'`.
Full launcher: `.\scripts\start.ps1 [-NoGpu] [-SkipImport]`, stop with `.\scripts\stop.ps1`.

## Conventions
- Smallest correct change following existing patterns; add/update tests; commit often; update HANDOFF.md.
- Work only on branch `sasha-work`. Never push to main/force-push/rewrite history.

## Safety rules
- Never print/log/commit `.env` values or dump env vars. Don't read `.local/`, `*.db`, `local-credentials.json`, `market-credentials.json` beyond need. Use placeholders in docs.
- The PostgreSQL in `.env` is a teammate's real DB: no drop/truncate/reset/downgrade/destructive tests. `alembic upgrade head` only if needed. Tell the user before any deliberate real-DB smoke check.
- No paid resources, no huge datasets (Alibaba v2026, Borg), no system-wide installs. No `rm -rf`, `git reset --hard`, `git clean`, or deleting outside task scope without asking.
- Research numbers must be reproduced before being quoted as verified.

## Ownership / instructions
- Sasha: no assigned module; does highest-value work from plan backlog + handoff "Work remaining", makes app run end-to-end on the configured PostgreSQL, then works out and does deployment. Hands over to Nithesh.
- Previous member: .env exists locally (not pushed) and must be shared privately; it was never tested by him; app may need extra services/apps to deploy.
