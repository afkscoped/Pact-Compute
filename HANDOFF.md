# HANDOFF.md (live status — keep current)

## START HERE (for Nithesh)

**(a) What this is.** PACT-Compute is a private GPU exchange: producers publish GPU capacity, consumers reserve it under reviewer-approved service agreements, and a native runner executes an image-embedding job and records a shared usage receipt.
Stack: React + TypeScript console, FastAPI backend, SQLAlchemy/Alembic (PostgreSQL or SQLite), a research worker and research experiments, all in `pact-compute/`.
Work only on branch `sasha-work`; push only to the `fork` remote, never to `origin`/main. Read `CLAUDE.md` first (safety rules).

**(b) First 5 commands** (PowerShell, Windows, Python 3.11+ and Node 25; clone to a SHORT path such as `C:\Users\<you>\pf`, because very deep paths make pip drop files and one S3 test then fails):
```powershell
git clone --branch sasha-work <fork-url> C:\Users\<you>\pf; cd C:\Users\<you>\pf\pact-compute
python -m venv .venv; & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:PACT_DATABASE_URL='sqlite:///C:/Users/<you>/pact_test.db'; & .\.venv\Scripts\python.exe -m pytest -q   # expect 235 passed, 1 skipped
cd frontend; npm.cmd ci; npm.cmd run build; npm.cmd test   # build clean, 33 node tests pass
cd ..; $env:PYTHONPATH='backend'; & .\.venv\Scripts\python.exe -m uvicorn pact.api:app --host 127.0.0.1 --port 8765   # then GET http://127.0.0.1:8765/api/health
```
Without a `.env` this runs on SQLite under `.local/`; no secrets are needed for any of the above. These were checked on a fresh clone with no `.env`.

**(c) Secrets Sasha must give you privately (never in git, chat or docs).**
| File | Place at | What it is |
| --- | --- | --- |
| `.env` | `pact-compute/.env` | The previous member's Neon PostgreSQL URL (a teammate's real database) and the Groq key. Do NOT run tests, migrations or the app against it without that teammate's consent; tests always override `PACT_DATABASE_URL` with SQLite. |
| `deploy.env` | `pact-compute/deploy.env` | Connection string for the `pact-deploy` Neon project (the live app's database). Needed only for `pact.cli member NAME reviewer --org WORKSPACE_ID` against the live DB: load its variables into the shell first, never print them. |
Render dashboard variables (signing secret, admin password, database URL) live only in the Render account; ask Sasha to add you to it or to make the changes with you.

**(d) Live deployment.** https://pact-compute-sasha.onrender.com (Render free Docker service `pact-compute-sasha`, built from the fork's `sasha-work` branch; every push redeploys and the entrypoint runs Alembic migrations; the free instance sleeps when idle and its disk is ephemeral). Database: Neon project `pact-deploy` (aws-us-east-2). `GET /api/health` returned 200 with `postgresql`; signup was confirmed by Sasha. See `DEPLOYMENT.md` and `BACKUP_RESTORE.md`.

**(e) Needs human, ranked (with steps).**
1. Confirm migrations 0005-0007 applied on the live DB: Render service, Logs tab, find the Alembic lines from the last deploy (or from a shell with `deploy.env` loaded: `$env:PYTHONPATH='backend'; python -m alembic current` should say `0007`).
2. Reviewer account on the live DB: sign up a user on the live site, copy the workspace id, then with `deploy.env` loaded run `python -m pact.cli member NAME reviewer --org WORKSPACE_ID`. Without it no agreement can be approved, so no quote can be confirmed.
3. Browser click-through (nothing below has been browser-tested): reviewer inbox (Agreements, approve and reject with a reason), invitation flow (Team: create invite, redeem in a private window), What-if panel on a job, Incident queue (admin/operator nav), Home and Exchange sorting and Load more.
4. GPU runner on the live URL: sign in as a producer, Compute capacity, "Enroll a GPU host", copy the token (shown once). On the GPU machine put `PACT_URL`, `PACT_RUNNER_ID`, `PACT_RUNNER_TOKEN` in that machine's `.env`, follow README "Fresh setup" for PyTorch and `gpu_task.py prepare`, then `python -m pact.runner`. Then run one quote, confirm, job end to end.
5. Pin the model weights: from the first real runner output copy `weights_sha256` and set `PACT_MODEL_WEIGHTS_SHA256` in Render; outputs with other weights are then rejected.
6. Durable artifacts: create a free S3-compatible bucket, then in Render add `PACT_ARTIFACT_BACKEND=s3`, `PACT_S3_BUCKET`, `PACT_S3_ENDPOINT_URL` (if not AWS), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`; redeploy. Check any free-tier terms first.
7. Restore drill: follow `BACKUP_RESTORE.md` once and record the result here.
8. `GROQ_API_KEY` on Render (the app falls back to local guidance without it).
9. Operator review of the 50 support-benchmark expected answers (`backend/pact/support_bench.py`).
10. Manual keyboard and screen-reader pass of the console.
11. Decisions needing Sasha's approval (each changes behaviour): the five design observations under "Run 4 item 1 status".

**(f) NOT verified.**
- No browser check of the reviewer inbox, invitations, what-if panel, incident queue or other new screens (no browser on this machine; only API tests and node tests ran).
- The runner stage-timing code has never run on a real GPU; no GPU runner has been connected to the live URL.
- The support benchmark's 50 expected answers were written by a developer and not reviewed by an operator.
- Scheduler baselines were run at light load (utilization about 0.15), where all arms tie on service metrics and `easy_backfill` equals `fcfs`, `edf_aging` equals `edf`; they say nothing about heavy load.
- PostgreSQL-specific paths (rate limits, indexes, retry classification) ran only on a smoke test against `pact-deploy`, not in the automated suite; the Docker image build was never run locally; S3 storage was tested against `moto`, not a real bucket.
- Research numbers other than the ones reproduced in this file's status sections should not be quoted as verified.

---

## Goal
Get PACT-Compute running end-to-end on the configured PostgreSQL (Neon), do the highest-value backlog work, then deploy it with free services.

## State (2026-11-12, branch `sasha-work`)
| Check | Result |
| --- | --- |
| Backend deps in `.venv` (Python 3.11.9; README says 3.14) | OK |
| Backend tests on SQLite (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`) | 235 passed, 1 skipped (also on a fresh clone with no `.env`) |
| Frontend `npm ci`, `npm run build`, `npm test` | OK; 33 node tests pass |
| API on SQLite from a fresh clone, `GET /api/health` and `/` | 200 and 200 (live site returned 200 `postgresql` earlier) |
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
2. Handoff says Python 3.14 / Node 24; verified on Python 3.11.9 / Node 25 (works). Clone to a short path on Windows: under a very deep path pip drops files (`moto/utilities`) and `test_artifact_stores_local_s3_and_integrity` fails.
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

## Item 1 design: memberships, invitations, workspace switcher (written before coding)
**Chosen:** invitations + additional memberships + session-scoped workspace switch. **Not chosen:** owner-approves-own-policy (it removes the reviewer's separation of duties; would need explicit user approval).
- `members` keeps each person's *home* org/role (no backfill, no data migration). New table `memberships(id, member_id, org_id, role, created_at, unique(member_id, org_id))` holds *extra* workspaces. New table `invitations(id, org_id, role, token_digest unique, created_by, created_at, expires_at, accepted_by, accepted_at, revoked_at)`. New nullable columns `sessions.org_id`, `sessions.role` = active-workspace override. Migration 0003 only adds tables/nullable columns, so it is backward compatible with existing rows and with the previous app version.
- Who can invite: an org's `producer`/`consumer`/`admin` members, into their own org only, roles limited to `reviewer` or the inviter's own participant role (never admin/operator/researcher/submitter: privileged roles stay CLI/platform-admin). Token = 32 random bytes, stored only as SHA-256, shown once, 7-day expiry, single use, revocable. Listing/revoking is org-scoped.
- Accepting: (a) new person supplies username+password and the code, gets a new member whose home is the inviting org (public, rate-limited like signup, and only possible with a valid code); (b) existing signed-in user adds a membership. Role comes from the invitation, never from the request.
- Switching: `POST /api/v1/session/workspace {org_id}` is allowed only if the member has a home or extra membership there; it sets the session override. `current_user` re-validates the override against `memberships` on every request and returns a `Principal(id, username, org_id, role)`; all endpoints already scope on `member.org_id`, so tenant isolation is unchanged. Sign-in itself is unchanged for existing accounts.
- Security implications: new unauthenticated surface = invite acceptance (token-gated, rate limited, constant-time lookup by digest); a reviewer invited by an org owner can approve that org's policies only (existing behaviour of the role); removal of members/sessions revocation is NOT included yet (known gap, tracked below).

## Run scope (amended by user): do items 1-3 only, then stop and wait. Commit+push (fork only) after every slice.
Items: 1 membership/onboarding, 2 reliability, 3 artifact storage. Items 4-5 and backlog are NOT started (user said do not continue on own).

## Item 1 status: DONE (slice 1a backend+UI)
- Backend: memberships/invitations/session workspace override (migration 0003, additive; verified up/down/up on throwaway SQLite), routes in backend/pact/membership.py, Principal-based current_user in access.py, guide text fixed in explain.py.
- Frontend: Team screen (invite/revoke/join), workspace switcher in sidebar, "I have an invitation code" on sign-in (frontend/src/team.tsx, main.tsx).
- Tests: 11/11 backend pass on SQLite (new: invitation lifecycle, cross-tenant denial, owner cannot self-approve, one-time/revoked/expired codes, workspace switch, accept rate limit). Frontend typecheck+build OK.
- Known gaps: no member removal / session revocation UI; invitation role limited to reviewer or inviter's own participant role; reviewer nav is the existing full operations nav; no browser (Playwright) test run.
- Needs human: after the Render redeploy, sign up a consumer on the live site, create a reviewer invite in Team, redeem it in a private window to confirm end to end (I only tested via API/TestClient).

## Item 2 status (reliability) - in progress
- 2a DONE: audit showed idempotency already exists (jobs: mandatory Idempotency-Key + unique(org_id,request_key); booking: keyed by quote id, retry returns same booking, changed input -> 409). Added fault-injection test (key reuse with different body 409, retry same job, missing key 422, quote expiry 409, stale/foreign fence 404). Existing tests already cover last-slot double booking, concurrent job retry, duplicate runner events and lost-lease reconcile.
- 2b DONE: backend/pact/ratelimit.py + migration 0004 (table rate_hits, additive; up/down/up verified on SQLite). Sign-in/signup/invite-accept limits and the Groq budget (4/min, single in-flight, 429 cooldown) now live in the DB, serialized per bucket (BEGIN IMMEDIATE on SQLite, pg_advisory_xact_lock on PostgreSQL). Safe for multiple API replicas. NOTE: PostgreSQL path of ratelimit is untested locally (no local PG); the first deploy exercises it. Response cache for Groq stays per-process (only an optimization).
- 2c DONE: backend/pact/resilience.py `retry_db` (3 attempts, jittered backoff; retriable = SQLite locked, PG 40001/40P01/55P03/57P01/08xxx, invalidated connection). Applied to submit_job, cancel, heartbeat, claim, attempt_events, offer publish, quote, confirm (each is one rolled-back-on-error transaction with a stable operation identity). Tests: classification, bounded attempts, non-retriable single attempt, endpoint retry yields one job.
- 2d DONE: backend/pact/outbox.py. Audit: events are already written in the same transaction as the business change (record() in the caller session), i.e. the events table IS the transactional outbox. Fixed the real defect: seq is allocated before commit, so a late commit could be skipped forever. `horizon()` only delivers up to the highest seq with no unexpired gap (3 s grace; rolled-back txs leave permanent gaps that are skipped after grace). Job/run SSE (`entity_stream`) and the market stream both use it; reconnect resumes from Last-Event-ID (replay of that entity's events), tenant-scoped by org. Tests: gap/late-commit/rollback, replay from Last-Event-ID, tenant isolation. Limitations: at connect time the guard starts at the newest seq (client loads a snapshot on connect); consumers dedupe by seq (SSE id); no per-consumer durable delivery table (the client cursor is the Last-Event-ID).
- ITEM 2 COMPLETE. Next: item 3 (artifact storage).

## Item 3 status (persistence): DONE (code complete, pushed)
- backend/pact/storage.py: ArtifactStore interface; LocalStore (default; staged write + fsync + atomic rename) and S3Store (boto3; works with R2/B2/MinIO via PACT_S3_ENDPOINT_URL). Content-hash verified on every read and write; digest validated (no path traversal). Selected by PACT_ARTIFACT_BACKEND=local|s3. db.save_artifact, artifact downloads, runner input download and live output validation all go through it. Corrupt bytes -> HTTP 502, missing -> 410.
- CLI: \`python -m pact.cli artifacts-verify\` (counts only, non-zero exit on missing/corrupt). requirements-s3.txt (Docker image installs it); boto3 + moto[s3] added to requirements-dev.txt. S3 path tested against moto, not a real provider.
- BACKUP_RESTORE.md written (what to back up, matched DB+artifact restore, drill). DEPLOYMENT.md updated. No automatic migration of existing local artifacts to S3 (documented sync command).
- Tests: 17/17 pass on SQLite (new: local/S3/integrity/env selection, download corruption/missing, verify command).
- Needs human: (1) To keep live artifacts across Render restarts, create a free S3-compatible bucket (provider choice and any card requirement are yours; verify current free-tier terms), then in the Render dashboard add PACT_ARTIFACT_BACKEND=s3, PACT_S3_BUCKET, PACT_S3_ENDPOINT_URL (if not AWS), AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and redeploy. (2) Run one restore drill (BACKUP_RESTORE.md) and record the result. (3) Confirm invitation flow in a browser on the live site (item 1 note). (4) GPU runner, reviewer account on live DB and GROQ_API_KEY on Render remain open from before.
- ITEMS 1-3 COMPLETE. Per the user's amendment, stopped here; items 4-5 and the backlog are NOT started.

## Run scope 2 (user): items 4 and 5, then stop and wait.
## Item 4 status (frontend polish) - in progress
- 4a DONE: skip-to-content button, focus moves to main on route change, Loading is an aria-live status with labels, RetryNotice ("Try again") on Exchange/Bookings/BookingDetail load errors, Escape closes the quote panel, offer buttons have descriptive aria-labels. Typecheck+build OK, backend 17/17. No automated browser/a11y test run (Playwright e2e needs demo accounts + GPU runner) - manual keyboard pass is a Needs-human item.
- 4b DONE: consumer Home at `#/` (frontend/src/home.tsx): one clear next action + 4-step progress + recent bookings; pure logic in src/journey.ts tested with `npm test` (node --test, 7 tests; Node 25 runs .ts natively, no new deps). Nav entry is called Home for consumers; producers still land on the exchange.
- 4c DONE: offers get a Sort control (soonest / lowest rate / most memory; bookable first), text badges for best rate, soonest start and most memory (src/offers.ts; 11 node tests in total), a screen-reader result count; booking detail gets a role-aware plain-language "What this means" panel and a back link. ITEM 4 COMPLETE (empty/loading/error states and accessibility are in 4a). Needs human: a manual keyboard + screen-reader pass and a visual check of Home, Exchange and Booking detail on the live site (no automated browser test was run).
## Item 5 status (pagination and query tuning) - in progress
- 5a DONE (backend): backend/pact/pagination.py keyset pagination on a stable (sort key, id) order. Endpoints /jobs, /runs, /market/offers, /market/bookings accept `?limit=` (1-100, default 100 = old behaviour) and `?cursor=`; they still return a JSON ARRAY, the next cursor is in the `X-Next-Cursor` response header (absent on the last page). Decision: header instead of an envelope so existing clients and tests keep working. Invalid limit/cursor -> 422; cursors carry no tenant data and every query is org-scoped.
- N+1 fixes: offers list is now 5 queries regardless of row count (was 1 + ~2 per offer); bookings list batches job/quote/offer/attempt lookups. Gotcha found by the query-count test: SQLAlchemy's identity map is weak, so primed rows must be kept referenced until rendered (see `keep` in market.py).
- Migration 0005 adds composite indexes (jobs, research_runs, market_bookings x2, capacity_offers x2, events) matching the paginated queries; additive, verified up/down/up on SQLite; `EXPLAIN QUERY PLAN` test confirms the jobs list uses ix_jobs_org_created. PostgreSQL index behaviour is untested locally (no local PG); it applies on the next deploy.
- Tests: 19/19 (new: page walk with size 3 and 1 equals the full list, stability when a new row arrives mid-walk, bad cursors/limits, cross-tenant cursor, offers query-count budget, bookings paging).
- 5b DONE (frontend): "Load more" on Job queue, Bookings, GPU exchange offers and Research run history (page size 50). Pure helpers in src/paging.ts (`pagePath`, `walkPages`, 5 node tests; `npm test` = 16 tests in total). Design: every refresh/poll RE-WALKS the pages already loaded, so there are no gaps when rows arrive, no stale rows, and expired offers disappear; cost is k requests per refresh where k is the number of pages the user opened. `apiPage`, `usePagedList`, `LoadMore` live in shared.tsx; `useExchange(path, paged)` in exchange.tsx drives offers/bookings (still SSE-refreshed). Offer search/sort/"available only" filter only the loaded offers (the UI says so). The Queue and the run history now fetch their own pages instead of using the shell's polled arrays (Overview still uses the shell's first 100). Typecheck + build OK, 19/19 backend tests.
- Not done / caveats: no automated browser test of the new Load more buttons (needs a running stack; manual check below); the agreements and datasets lists are not paginated (small, bounded); event streams unchanged.
- ITEM 5 COMPLETE. ITEMS 4 AND 5 COMPLETE. Per the user's instruction the run stops here and waits for the next message.
- Needs human (new): after the next Render deploy (migration 0005 runs automatically in the entrypoint), open the live site as a consumer and a producer: check Home, offers sort/badges, Load more on Bookings/Jobs (needs more than 50 rows to appear; otherwise only the "Showing all N" text), keyboard navigation (skip link, Escape in the quote panel) and that lists still load.

## Run scope 3 (user): four items (reviewer inbox, job spec + stage timing, support benchmark, runtime baselines), then stop.
## Run 3 item 1 status: DONE (reviewer inbox)
- Backend: migration 0006 (policies.rejected_at/rejected_by/decision_note, additive; verified up/down/up on SQLite). `GET /policies/inbox` (admin/reviewer, own org drafts, oldest first, with clause text, parsed values, issues, affected reserved jobs booked under an earlier version, `can_approve`). `POST /policies/{id}/reject` (reason 12-500 chars, drafts only; approved -> 409). `approve` takes an optional note and refuses rejected policies. Events `PolicyRejected`/`PolicyApproved` carry the reason/note.
- Frontend: Review queue panel on Agreements for admin/reviewer (`inbox.ts` helpers + node tests). Approve is disabled while findings are open.
- Not browser-tested here (no browser on this machine); needs a human click-through on a reviewer account.

## Run 3 item 2 status: DONE (workload spec + stage timing)
- Every job stores `Job.spec['workload']` (no migration; JSON): version, template ID, runtime digest (sha256 of `gpu_task.py` + `mobilenet.ptx`, since the runner is native not containerised), model name + weights digest, input manifest digest/rows, hardware, region, timeout, output schema, retry policy, and a `spec_sha256` over the body. Shown on job detail; older jobs simply have no workload (UI hides the panel).
- Stage timing in `Attempt.result.stage_seconds`: staging, startup, compute reported by the runner (`runner.py`); validation and upload measured by the control plane. Validated as finite 0-86400 s; the runner cannot report the server-side stages. "Upload" is the control-plane store write, not the runner's network transfer.
- Model weights digest is NOT pinned by default (the full IMAGENET1K_V2 sha256 could not be verified here: torchvision is not installed). Needs human: read `weights_sha256` from the first real runner output and set `PACT_MODEL_WEIGHTS_SHA256` on Render; after that, outputs with other weights are rejected.
- The runner changes (timing) are compiled but not run against a real GPU here.

## Run 3 item 3 status: DONE (support-scenario benchmark)
- `support.py`: deterministic diagnosis from a job's recorded events (situation, ONE cited evidence event, role-permitted next actions, withheld actions). Reads only structured fields; runner/user free text is never copied into answers (prompt-injection safe by construction). Wired into `/explain/answer` for `job` and `booking` topics as step 1 "Diagnosis" (`diagnosis` key in the response).
- `support_bench.py`: 37 cases over 17 scenarios from plan section 3 plus prompt injection (3 cases). Each must pass six checks: situation, evidence event, first action, no forbidden action, role permitted, no canary text. Scenarios the platform records no event for (final slot lost, old-runner rejection, producer pause, Groq throttling, org switch) expect an honest "insufficient evidence" with no cited event, never an invented one. Cross-tenant disclosure is tested at API level (`test_explain_answer_cites_recorded_event_and_blocks_cross_tenant`: other tenant gets 404 with no job title or event kind).
- Run: `python -m pact.cli support-benchmark` (writes `.local/evaluations/support-benchmark.json`, exits non-zero on any failure). Tests: `tests/test_support_benchmark.py`.
- Limits: cases are written by me from the scenario table and have NOT been reviewed by an operator (the plan asks for operator review); the plan's target is 50 cases; the console's optional Groq re-ranking is outside this benchmark.

## Run 3 item 4 status: DONE (runtime-prediction baselines; research only)
- `runtime_baselines.py`, CLI `python -m pact.cli runtime-baselines` -> `.local/evaluations/runtime-baselines{.json,-slices.csv,-manifest.json}` (manifest has sha256 of each file + snapshot id). Deterministic: run twice -> identical hashes (also asserted in `tests/test_runtime_baselines.py`). The live formula (38 + 3 x images s) is untouched and has a regression test.
- Protocol: frozen chronological split of the 185 successful GPU lifecycles by arrival: 102 train / 37 calibration (later window) / 46 test, same boundaries as the existing `runtime_model.evaluate`; outcome-availability cutoffs prevent future outcomes leaking. Models predict log runtime: global median, per-slice median, ridge linear (8 request features). Calibration: two-sided split conformal, 90% target, globally or per model-request slice (slice used only if it has >= 9 calibration rows, else falls back to global). Slices: GPU model request (unconstrained 23 test rows / T4 11 / other-or-multiple 12) and GPU count.
- Reproduced results (test window, n=46): empirical coverage 0.93-0.98 across the six candidates (Wilson 95% lower bounds 0.86-0.92), so the 90% target held in this window. BUT intervals are enormous: median width ~112k s (linear) to ~565k s (median), upper/lower ratio ~2,200x (linear) to ~20,000x (median) because lifecycle runtimes span 18 s to 1.3 M s. The linear model narrows intervals about 4x versus the medians but has higher point error (MAE 6.3k s vs 3.5k s). Conclusion: these features carry little runtime signal; coverage here is mostly achieved by width. Do NOT use these intervals for reservations.
- Caveats: only 185 rows; slices under 20 test rows are flagged `indicative_only`; conformal coverage is marginal and assumes exchangeability (drift can break it per slice); target is a lifecycle proxy, not this platform's workload.
- Next if pursued: more data (not Borg/v2026 without asking), log-scale or heavy-tail-aware features, time-of-arrival drift check, tighter per-slice calibration with more rows.

## Run 4 (user): items 1-5 (authorization matrix, counterfactual preview, incident queue, scheduler baselines, benchmark to 50)
## Run 4 item 1 status: DONE (tenant authorization matrix)
- `tests/test_authorization_matrix.py` (~175 cases). Routes come from the app route table (flattening included routers); `test_every_route_is_classified` fails when a route has no stated policy (or a stale entry exists). Each AUTHED route is called with: no login (401), expired session (401), every wrong role in the same tenant (403, and allowed roles are not 403), a user of another tenant in every role (403/404, no foreign id/title/name in body; admin must get 404), plus focused tests for: cursors (foreign and junk), listings, offers visibility, market notice stream, per-entity event streams (404 before streaming), runner tokens bound to their tenant, removed extra membership (falls back to home role and home org immediately), workspace switching into a foreign org, foreign ids inside request bodies (same answer as a missing id), and error bodies (identical for foreign and missing ids).
- Defect found and fixed (TIGHTENING only): the OpenAPI schema and Swagger UI (`/api/docs`, `/api/openapi.json`, `/redoc`) were public and listed every route including admin ones. They are now off unless `PACT_API_DOCS=1`. README updated. No permission was loosened and sign-in is unchanged.
- Skeptical self-review of the diff, checked: (1) only one production line changed (FastAPI constructor + `import os`); (2) no route, dependency or role check changed; (3) the SPA catch-all still 404s `api/` paths and serves index.html for `/redoc`, which contains no schema; (4) nothing else reads the docs URL (grep: README only); (5) cookies are HttpOnly + SameSite=Strict, writes pass an Origin/Sec-Fetch-Site guard, responses under /api are `no-store`; (6) every by-id lookup in api.py/market.py/explain.py/membership.py/live.py goes through `scoped`/`entity` or an explicit org check (grepped each `db.get(<model>, id)`); (7) sessions are looked up by sha256 digest, role and workspace are re-read on every request.
- Observations NOT changed (design questions for you): (a) any `admin`/`producer`/`consumer` member can list and revoke ANY invitation of their org, not only their own; (b) `/api/health` reveals the database engine to anonymous callers; (c) `/api/v1/config` returns the example contract and database kind to any signed-in user; (d) the market notice stream sends global event sequence numbers and kinds for offer/capacity events across tenants (offers are public to participants by design; no ids or titles); (e) quote creation checks the offer before the policy, so a foreign policy id yields 409 (offer unavailable) when the offer is full; it is indistinguishable from a missing id, so nothing leaks.
- Test hygiene: the module cancels its jobs and pauses its offer at teardown so the shared runner stays free for other tests. It enrols extra runners in the shared test DB.

## Run 4 item 2 status: DONE (counterfactual preview)
- `POST /api/v1/jobs/preview/counterfactual` (any signed-in role, tenant-scoped like `/jobs/preview`). Body = job fields (no uploads) + optional `edits` (typed: `deadline_seconds` 60-86400, `max_charge_cents` 0-100000, `grid_zone` short code) + `suggest`. With no edits it auto-suggests when the job has no eligible placement (or on request): up to two larger deadlines, two larger charge caps and each other enrolled runner region, plus one combined option. Each option re-runs the existing `live.placement` feasibility check against an in-memory COPY of the policy rules (`SimpleNamespace`; the stored policy is never touched). Result per option: feasible, typed `blocking_codes` / `resolved_codes` / `new_codes` of the nearest-to-feasible candidate, and the selected placement summary. Nothing is stored, reserved or created (asserted in tests: job count and policy rules unchanged).
- Applying a change = creating a policy REVISION through the existing reviewer-gated endpoint, then a reviewer approves it. The NewJob screen shows a "What would make this feasible?" panel (auto-runs when the preview has no placement; "Explore changes" on request), a before/after diff, and an explicit "Accept and create a revision for review" button for admin/reviewer; other roles are told to ask a reviewer. No permission loosened.
- Tests: backend counterfactual test (determinism, resolved/remaining codes, validation 422s, no uploads, foreign tenant 404, on-request mode); route added to the authorization matrix; frontend `counterfactual.test.ts`.
- Limits: only deadline/charge cap/region edits (as requested); absolute `deadline_utc` rules are not varied; the suggested grid is a few fixed steps, not an optimiser. Not browser-tested.

## Run 4 item 3 status: DONE (operator incident queue)
- `incidents.py` + migration 0007 (`incident_records`, additive; verified up/down/up on SQLite). Incidents are DERIVED from existing state, nothing duplicated: stale runner (heartbeat older than the 25 s TTL, not paused), uncertain attempt (`execution_unknown`), failed output (attempt failed with the runner's fixed "rejected the output manifest" message, now the shared constant `live.OUTPUT_REJECTED`), plus adjustment requests (the only new stored incident type). Ownership/resolution live in `incident_records`; an incident's id is a hash of (org, kind, subject, episode) so a stale runner that recovers and goes quiet again is a NEW incident, and a resolved one stays hidden only for its own episode.
- Endpoints (admin/operator only): `GET /api/v1/incidents?status=active|resolved|all`, `POST /incidents/{id}/claim`, `POST /incidents/{id}/resolve` (note of at least 12 characters is recorded with the actor and time; events `IncidentClaimed`/`IncidentResolved`), and `POST /market/bookings/{id}/adjustments` (buyers, once the booking is final, one open request per booking). Each incident returns evidence (event kind + sequence, app links), permitted actions and its owner. Reconciliation REUSES the existing logic: extracted to `live.reconcile_attempt`, now shared by `/jobs/{id}/reconcile` and the incident resolve.
- Rules: an uncertain attempt can only be resolved by actually reconciling (after its reserved window; only by the job's own org), so it cannot be dismissed while capacity stays held; adjustment requests need an accept/decline outcome and make NO ledger entry (there is no settlement ledger yet); another operator cannot claim or resolve an owned incident; other tenants get 404 and an empty queue. A producer operator sees incidents for jobs on its runners with only structured facts (public label, event kinds/sequences, no titles, no job or attempt ids).
- Frontend: Incidents screen (admin/operator nav only) with evidence links restricted to app routes (`safeHref`), claim, resolve with a required note. Tests: three backend tests (uncertain flow incl. ownership and tenancy, failed output + stale runner, adjustment lifecycle), four route entries in the authorization matrix, `incidents.test.ts`.
- Limits: requesters cannot yet read their own adjustment's status in the UI (they get the id on filing; resolution is visible to the owning org's operators); no notifications; adjustment queue lives with the booking's producer org. Not browser-tested.

## Run 4 item 4 status: DONE (scheduler baselines in the research replay; research only)
- Two practical baselines added next to the existing arms (`research.BASELINE_ARMS`, not in `ARMS`, so earlier outputs are byte-identical): `easy_backfill` (FCFS order, conservative backfilling, horizon 8) and `edf_aging` (EDF where waiting shortens the effective deadline by one slot per two slots waited).
- `python -m pact.cli scheduler-baselines --seeds 20 --jobs 90` writes `scheduler-baselines.json`, `.csv` and `-manifest.json` (sha256 per file). Two full runs gave identical hashes. Tests: `tests/test_scheduler_baselines.py`.
- Labels: measured = NESO carbon actuals only; trace-derived = arrivals, runtimes, GPU requests; modeled = supply, prices, budgets, predictions, power and every simulated outcome.
- Reproduced result (20 seeds, 90 jobs, no policy rules): all arms tie on admitted/completed/on-time (0.996/0.932/0.932), utilization (0.149) and overruns. `easy_backfill` equals `fcfs` and `edf_aging` equals `edf` on every metric, so aging and backfilling change nothing at this load.
- Versus `carbon_aware`, both baselines are better on wait p95 (0 vs 46.5 min), bounded slowdown (1.0 vs 1.11) and cost per completed (about -0.03 credit), but worse on carbon (about +200 g total, +2.4 g per completed job). Versus `policy_only` they are better on wait and slowdown, worse on cost (+0.008) and carbon (+33 to +41 g). The CP-SAT arms trade extra wait for lower carbon; the simple baselines do not lose on service here.
- Caveats: the replay is lightly loaded, so it does not stress any scheduler. Fragmentation and fairness are not reported. Calibrated-vs-median predictions with backfilling are not covered. No policy rules are configured.

## Run 4 item 5 status: DONE (support benchmark extended from 37 to 50 cases)
- 13 cases added in `support_bench.py` from the plan's scenario table (new roles per scenario: producer, operator, admin; one more injection case with planted canary text). All 50 pass; the six checks and the canary check are unchanged. `test_support_benchmark.py` now requires at least 50 cases.
- **No operator has reviewed the expected answers.** The developer wrote them from the situation table in `support.py`, so a pass means the rules agree with the developer's reading, not with an operator's. The plan target is 50 operator-reviewed cases; the count is met, the review is not (still under Needs human).
- Several cases overlap their neighbours (same situation, different role); they test role permissions more than new situations. Real pilot incidents should replace them.

## Suggested next batch (ranked by value)
1. Needs-human items that block a real pilot: confirm migrations 0005-0007 applied on Render, set S3 settings, add a reviewer account, run a GPU runner against the live URL (also exercises the stage-timing code), then a browser click-through of the reviewer inbox, what-if panel and incident queue.
2. Operator review of the 50 support-benchmark expected answers; replace overlapping cases with real incidents.
3. Restore drill on the deploy database and a written runbook entry.
4. Decide on the five unchanged authorization observations in Run 4 item 1 (each loosens or changes behaviour, so it needs approval): restrict invitation revoke, trim `/api/health` and `/config` for anonymous callers, tighten the market notice stream, check policy before offer in quote creation.
5. Scheduler research: re-run baselines at a heavier, separately disclosed load so backfilling and aging can differ; add fragmentation and fairness metrics; test calibrated vs median predictions with backfilling.
6. Keyboard and screen-reader accessibility pass on the new screens.
