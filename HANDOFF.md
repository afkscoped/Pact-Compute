# HANDOFF.md (live status — keep current)

## Goal
Get PACT-Compute running end-to-end on the configured PostgreSQL (Neon), do the highest-value backlog work, then deploy it with free services.

## State (2026-11-12, branch `sasha-work`)
| Check | Result |
| --- | --- |
| Backend deps in `.venv` (Python 3.11.9; README says 3.14) | OK |
| Backend tests on SQLite (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`) | 8/8 pass (after restoring the data files; Known issues #1) |
| Frontend `npm ci` + `npm run build` (tsc + esbuild) | OK (bundle ~900 kB) |
| App started with real `.env`, `GET /api/health` | 200, `database: postgresql` (startup `bootstrap()` ran idempotently) |
| Playwright e2e, GPU runner, live job | NOT run (need demo accounts, GPU; this machine has no verified GPU runner) |

## Done
- Orientation, env setup, `.gitattributes` (`PACT-Compute-data-preflight/** -text`), CLAUDE.md, this file.

- Task 3a: `POST /api/v1/runners` (producer/operator/admin) enrolls a runner in the caller's org and returns its token once; "Enroll a GPU host" form on Compute capacity page; test added (9/9 pass, build OK). Consumer self-approval NOT added (reviewer separation kept on purpose); reviewer provisioning still needs `pact.cli member`.

## Prioritized tasks (cost: S/M/L)
1. [DONE] Fix data checksum failure: data files restored to committed bytes, 8/8 tests pass.
2. [DONE] API smoke test on PostgreSQL, run against the NEW `pact-deploy` Neon project only (9/9). User instructed: never touch the teammate's DB again.
3. [PARTLY DONE] Close the onboarding gap: after signup a producer/consumer needs an operator CLI to enroll runner / provision reviewer (plan backlog #2/#4). Candidate: self-service runner enrollment for producers + consumer self-review option (config-gated).
4. [DONE] Deployed on Render free (Docker, branch sasha-work of the fork) at https://pact-compute-sasha.onrender.com; /api/health 200 postgresql; signup works (user confirmed). See DEPLOYMENT.md. Deployment artifacts: Dockerfile (API+worker, serves built frontend), health checks, start scripts, env var docs (Step 2).
5. [M] Shared/persistent rate limits & artifact storage risk (artifacts live in `.local`; needs persistent disk or object storage).
6. [L] Outbox events, object storage, pagination (plan backlog #6/#7).

## Decisions
- Tests never touch the real DB: the test file sets its own SQLite; we also override `PACT_DATABASE_URL` in the command.
- Pristine data for tests: `git -c core.autocrlf=false archive HEAD PACT-Compute-data-preflight` into a scratch dir, then `PACT_SOURCE_DIR=<that dir>`.

## Known issues
1. `core.autocrlf=true` rewrote the dataset CSVs to CRLF on checkout, so SHA-256 manifest checks fail (`Source checksum changed for openb_pod_list_gpuspec33.csv`; sizes 595620 vs 587467). Git blobs are correct. `.gitattributes` prevents recurrence; files were restored by copying the committed bytes over them (`git checkout` alone skipped them as unchanged). `git status` may still list them as M with an empty diff; harmless. On a fresh clone elsewhere, `.gitattributes` keeps them byte-exact.
2. Handoff says Python 3.14 / Node 24; verified on Python 3.11.9 / Node 25 (works).
3. Artifacts/experiments under `.local` are not in the database: backups of DB alone are incomplete.
4. Rate limits and Groq budget are process-local (single replica only).

## Next steps
Continue the task list above; Step 2 deployment plan goes to DEPLOYMENT.md.

## Secrets
`pact-compute/.env` is not in the repo. Share it with Nithesh privately. Never paste values into docs/chat.

## Accounts/tools set up (2026-11-12)
- gh CLI installed (user scope, winget) and logged in as the user; neonctl via `npx neonctl` (logged in). Fork + `fork` remote created. Secrets only in gitignored `pact-compute/deploy.env`.

## Live deployment status
- Render service `pact-compute-sasha` (free, ephemeral disk, sleeps when idle) + Neon `pact-deploy`. Env vars were entered by the user in the Render dashboard.
- Not yet done: GPU runner connected to the live URL (needs GPU machine), reviewer account on the deployed DB (`pact.cli member NAME reviewer --org WORKSPACE_ID` with deploy.env vars loaded), GROQ_API_KEY on Render, full quote->confirm->job flow live.
- `/api/v1/config` returned non-200 unauthenticated (likely needs session; unchecked).
