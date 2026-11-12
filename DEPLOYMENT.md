# DEPLOYMENT.md — PACT-Compute

Status: plan + repo files written (`Dockerfile`, `deploy/entrypoint.sh`, `.dockerignore`). **Not yet built or deployed.** Docker is not installed on Sasha's machine, so the image build is untested; Render builds it remotely on first deploy. Values below are placeholders — enter real secrets only in the host dashboard, never in git or chat.

## Components and where they run
| Component | Where | Why | Cost |
| --- | --- | --- | --- |
| Frontend (built React) | Served by the API container (`frontend/dist`) | App already serves it; one origin means cookies/CSRF checks just work | free |
| API + research worker | One Docker container (Render free Web Service) | Entry script runs migrations, init, import, worker (background), then uvicorn | free tier (sleeps after ~15 min idle, cold start ~1 min; verify current limits on render.com/pricing) |
| Database | Neon PostgreSQL (already configured) | Already used | free tier |
| HTTPS | Provided by the host (`*.onrender.com`) | Needed for `PACT_SECURE_COOKIE=1` | free |
| Artifacts / experiment files | `PACT_STATE_DIR=/data` | **RISK:** free Render disk is ephemeral; artifacts, dataset snapshots and study outputs vanish on restart/redeploy. DB rows would then point at missing files. Persistent disks are paid. Acceptable for a demo; for real use move to object storage (backlog #6) or a paid disk | free (risky) |
| GPU runner | Your own NVIDIA machine (Windows) outside the container | Needs real GPU/driver; connects out to the deployed URL | free |
| Groq | Already configured | Optional assistance | free tier |

Alternative for a faculty demo that needs persistent files and the GPU on the same box: run locally (`scripts/start.ps1`) and expose with a Cloudflare quick tunnel (`cloudflared tunnel --url http://127.0.0.1:8765`, free, no account, URL changes each run, HTTPS). Set `PACT_URL` to the tunnel URL and `PACT_SECURE_COOKIE=1`.

## Environment variables for the host (names only)
| Name | Value / note |
| --- | --- |
| `PACT_DATABASE_URL` | Neon connection URL (secret) |
| `PACT_DB_TLS` | `1` |
| `PACT_URL` | Public https origin of the deployment (used by origin checks and runners) |
| `PACT_SECURE_COOKIE` | `1` |
| `PACT_SIGNING_SECRET` | **Required.** Random 64-hex string you generate once and keep. Without it a new secret is generated on each restart of an ephemeral disk, invalidating newly issued runner tokens and receipt/evidence signatures |
| `PACT_ADMIN_PASSWORD` | Only used if the `admin` user does not exist yet in the database; if it exists, the existing password still applies |
| `GROQ_API_KEY` | Secret, optional |
| `PACT_RUN_MIGRATIONS` / `PACT_RUN_IMPORT` / `PACT_RUN_WORKER` | Defaults `1`; set `PACT_RUN_MIGRATIONS=0` on any extra replica. Run a single replica: rate limits and Groq budget are process-local |
| `PORT` | Set by Render automatically |

## Decision needed before first deploy
The `.env` Neon database is a teammate's real database. A public deployment should use a **separate Neon project/branch** (free) so strangers who sign up do not write into it. The entrypoint runs `alembic upgrade head` automatically, which is a no-op on the already-migrated database but a full schema creation on an empty one.

## Steps
Repo-side (done in this branch): Dockerfile, entrypoint, dockerignore, health check at `/api/health`.

Manual steps (need Sasha's accounts — Claude will give click-by-click instructions at that point and wait for "done"):
1. Push this branch to GitHub (Step 3 wrap-up does this; Render deploys from a GitHub repo).
2. Create a Render account (sign in with GitHub). New + Web Service → connect the repo → branch `sasha-work` → Runtime: Docker, Dockerfile path `./Dockerfile`, context `.`, instance type Free.
3. In the Render service → Environment, add the variables above by hand (generate `PACT_SIGNING_SECRET` locally with `python -c "import secrets;print(secrets.token_hex(32))"` and paste it only into the dashboard).
4. Set the Health Check Path to `/api/health`. Deploy. Open the URL, create a producer account, enroll a runner under **Compute capacity**.
5. On the GPU machine: set `PACT_URL` to the Render URL, `PACT_RUNNER_ID` to the new runner id and `PACT_RUNNER_TOKEN` to the token shown once in the UI (put them in that machine's `.env`, not the repo), then run `python -m pact.runner` (see README for GPU prerequisites).
6. Smoke test: sign in, publish capacity, quote/confirm as a consumer with a reviewer-approved agreement (reviewer accounts still need `pact.cli member ... reviewer --org WORKSPACE_ID` run against that database).

## Known deployment gaps
- Ephemeral artifacts on free tier (above). Backups of the DB alone are incomplete.
- No monitoring/alerting, no restore drill, single replica only.
- `pact.cli member` for reviewers must be run with the deployment's `PACT_DATABASE_URL` (a local shell with that variable set, or Render Shell if available on the plan).
- Image build untested locally (no Docker). Python 3.12 in the image vs 3.11 tested locally; tests ran on 3.11.
