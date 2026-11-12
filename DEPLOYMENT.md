# PACT-Compute deployment

Current RC status, 13 November 2026: local regression, clean source packaging and Linux startup checks passed. **The actual Docker image and current hosted deployment remain unverified.** No push, production migration, cloud-resource creation or deployment change was performed.

Read the [RC assessment](reports/release-candidate/RELEASE_ASSESSMENT.md), [exact hosted staging procedure](reports/release-candidate/HOSTED_STAGING_VERIFICATION.md) and [external requirements](reports/release-candidate/EXTERNAL_REQUIREMENTS.md) before any release action. The completed local milestone is retained in [reports/final-validation](reports/final-validation/FINAL_RELEASE_ASSESSMENT.md).

## Existing deployment reference

Historical HANDOFF records Render Docker service `pact-compute-sasha` at `https://pact-compute-sasha.onrender.com`, linked to the fork's `sasha-work` branch, and Neon project `pact-deploy` in aws-us-east-2. Current deploy SHA, dashboard settings, schema and actual storage backend require owner verification. Do not create replacement infrastructure or touch the teammate's database. The checked-out RC is uncommitted and cannot already be the hosted source.

## Runtime layout

| Component | Current source behavior |
| --- | --- |
| Frontend | Node 24 build stage; API serves bundled React/TypeScript files |
| API + research worker | Python 3.12 image with pinned runtime/S3 dependencies. Entrypoint optionally migrates/imports, then `pact.service` supervises worker and uvicorn; unexpected child exit stops the service |
| Database | PostgreSQL for hosting; SQLite for isolated local checks. Current schema head `0007` |
| GPU runner | Separate owner-controlled NVIDIA host with its own pinned GPU environment, scoped enrollment token and model digest; not part of the API image |
| Artifacts | Local `$PACT_STATE_DIR/artifacts` or implemented S3-compatible backend. Hosting requires verified durable storage and matching backups |
| Research/data state | Dataset snapshots and evaluation files under state directory; regenerable/importable separately from content-addressed artifacts |

Render free-service files are ephemeral and shell/one-off-job access is unavailable; local `/data` is not durable merely because the Dockerfile declares a volume. Use existing approved private object storage or a verified persistent disk on a supporting plan. No storage plan or free-tier entitlement is assumed. [Render limitations](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).

## Configuration - names only

| Variables | Purpose |
| --- | --- |
| `PACT_DATABASE_URL`, `PACT_DB_TLS=1` | Approved hosted PostgreSQL target and TLS |
| `PACT_URL`, `PACT_SECURE_COOKIE=1` | Exact HTTPS origin and secure browser session cookie |
| `PACT_SIGNING_SECRET` | Stable secret-store value retained across restarts and backed up for evidence verification |
| `PACT_ADMIN_PASSWORD` | Initial bootstrap only; not an existing-user password reset |
| `PACT_ARTIFACT_BACKEND`, `PACT_S3_BUCKET`, `PACT_S3_PREFIX`, optional endpoint/region, `AWS_*` | Private durable artifact backend and scoped credentials |
| `PACT_RUN_MIGRATIONS` | Set `0` after a dedicated approved migration step; avoid concurrent rollout migrations |
| `PACT_RUN_IMPORT`, `PACT_RUN_WORKER` | Normally `1` for the demonstration; verify import and worker process outcomes |
| `PACT_MODEL_WEIGHTS_SHA256` | Full approved model digest, shared with the staging runner |
| `PORT` | Host-provided port honored by the service supervisor |
| `GROQ_API_KEY` / configured provider variables | Optional authorized assistance; fallback works without live provider credentials |

Health at `/api/health` checks database access only. Verify worker activity, import/data availability, private storage, browser sessions and physical runner separately. PostgreSQL event ordering now serializes application writes: **drain every older writer before authorized rollout**, rather than mixing revisions in a normal rolling deploy.

## Release and recovery

Build from the allowlisted context and execute the [container gate](reports/release-candidate/VALIDATION.md) when an engine is available. Freeze source/image identities. Owner-approved staging must pass matched backup/restore, dedicated migration/drift check, exact-SHA deployment, storage across restart, role isolation and a physical hosted GPU transaction. Use [BACKUP_RESTORE.md](BACKUP_RESTORE.md) and the staged stop gates. A successful local simulation or public health response cannot replace those checks.

A future source push may trigger the historical service's auto-deploy. It requires separate explicit authorization. Production changes additionally require the verified matched backup and owner approval. No action in this document authorizes either.
