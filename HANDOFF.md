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
