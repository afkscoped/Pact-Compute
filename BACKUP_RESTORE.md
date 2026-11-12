# Backup and restore

PACT-Compute state lives in **three places**. A restore is only complete when all three match.

| State | Where | Backed up by |
| --- | --- | --- |
| Transactional data (accounts, policies, jobs, bookings, events, artifact *metadata*) | PostgreSQL (Neon) or SQLite | Database snapshot / dump |
| Artifact bytes (job inputs, embeddings, research evidence) | `PACT_ARTIFACT_BACKEND`: local disk `$PACT_STATE_DIR/artifacts` (default) or an S3-compatible bucket | Copy the directory / bucket |
| Secrets and other files | `PACT_SIGNING_SECRET`, `PACT_ADMIN_PASSWORD`, runner tokens (environment); `$PACT_STATE_DIR` (`local-credentials.json`, dataset snapshots, study outputs, runner journals) | Your secret store; copy the state directory |

Artifacts are **content-addressed** (file name = SHA-256 of its bytes) and never modified, so:
- An artifact copy that is *newer* than the database is harmless (extra objects).
- An artifact copy that is *older* than the database leaves gaps. `artifacts-verify` finds them.

## Choose the artifact backend (no paid service required)
Default is local disk. On hosts with an ephemeral disk (Render free tier) use an S3-compatible bucket instead, set in the host's environment (never in git):

| Variable | Meaning |
| --- | --- |
| `PACT_ARTIFACT_BACKEND` | `local` (default) or `s3` |
| `PACT_S3_BUCKET` | Bucket name (required for `s3`) |
| `PACT_S3_PREFIX` | Key prefix, default `artifacts/` |
| `PACT_S3_ENDPOINT_URL` | Optional, for non-AWS providers (Cloudflare R2, Backblaze B2, MinIO, ...) |
| `PACT_S3_REGION` | Optional region |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credentials (standard boto3 variables) |

Install the client with `pip install -r requirements-s3.txt` (the Docker image already includes it). Several providers offer a free storage tier; check each provider's current terms, some ask for a payment method at signup. Local MinIO is a fully free option for testing. Existing local artifacts are **not** migrated automatically: copy them with a tool such as `aws s3 sync artifacts/ s3://BUCKET/artifacts/ --endpoint-url URL` before switching, then run `artifacts-verify`.

## Back up
1. **Database.** Neon: create a branch of the project (Console → Branches → Create branch) or use point-in-time restore within the plan's history window. Any PostgreSQL: `pg_dump --format=custom --file=pact-YYYYMMDD.dump "$PACT_DATABASE_URL"`. SQLite: stop the app, copy the `.db` file.
2. **Artifacts.** Local: archive `$PACT_STATE_DIR/artifacts` (e.g. `tar czf artifacts-YYYYMMDD.tgz artifacts`). S3: enable bucket versioning and/or `aws s3 sync s3://BUCKET/artifacts ./artifacts-copy --endpoint-url URL`.
3. **Secrets.** Store `PACT_SIGNING_SECRET` outside the repo (password manager). Without it, receipts and evidence signed earlier can no longer be verified.
4. **Cadence.** Take the database and artifact backups together (artifact copy first, then database), so the database never references bytes the copy lacks.

## Restore
1. Create an empty database (or restore the snapshot/branch) and set `PACT_DATABASE_URL`, `PACT_DB_TLS`.
2. For a dump: `pg_restore --clean --if-exists --no-owner --dbname "$PACT_DATABASE_URL" pact-YYYYMMDD.dump`. **Never run this against a database you are not sure you want to overwrite.**
3. Restore artifacts to the same backend location (extract the archive into `$PACT_STATE_DIR`, or sync the bucket back).
4. Set the same `PACT_SIGNING_SECRET` as before.
5. Apply any newer migrations: `python -m alembic upgrade head` (the Docker entrypoint does this on start).
6. **Verify**: `PYTHONPATH=backend python -m pact.cli artifacts-verify` prints `Artifacts checked: N, missing: M, corrupt: C` and exits non-zero if anything is missing or fails its hash check.
7. Start the app, then reconcile in-flight work: open any booking in `execution_unknown` and follow the Explainable AI reconcile guide. Runners reconnect with their existing tokens.

## Restore drill (do this before relying on backups)
Use a scratch database, never production: restore the latest backup into it, point a local instance at it with a separate `PACT_STATE_DIR` holding the restored artifacts, run `artifacts-verify`, sign in, open a recent booking and download its receipt and output. Record the date and result in HANDOFF.md.

## Known gaps
- Dataset snapshots and study outputs under `$PACT_STATE_DIR` (not artifacts) are regenerable (`pact.cli import`, `publication-study`) and are not covered by `artifacts-verify`.
- No automated scheduled backups yet; no retention or deletion policy for artifacts.
