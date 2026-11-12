# Backup and restore

Local validation on 13 November 2026 passed a disposable PostgreSQL dump/restore with matching artifacts and original evidence signatures. See [the drill report](reports/final-validation/BACKUP_RESTORE_VALIDATION.md). This does not certify production backups. Never restore over populated production data without a verified backup and explicit approval.

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
1. **Database.** With owner authorization, use an approved Neon branch/snapshot or a PostgreSQL custom dump. Configure private libpq service/password files (or equivalent secret injection), select the intended `PGSERVICE`, then run `pg_dump --format=custom --file=pact-YYYYMMDD.dump`. Do not pass the application's password-bearing URL on the command line; a SQLAlchemy `+pg8000` URL is also not a libpq URL. Verify plan history/branch limits before creating resources. SQLite: stop the app, copy the `.db` file.
2. **Artifacts.** Local: archive `$PACT_STATE_DIR/artifacts` (e.g. `tar czf artifacts-YYYYMMDD.tgz artifacts`). S3: enable bucket versioning and/or `aws s3 sync s3://BUCKET/artifacts ./artifacts-copy --endpoint-url URL`.
3. **Secrets.** Store `PACT_SIGNING_SECRET` outside the repo (password manager). Without it, receipts and evidence signed earlier can no longer be verified.
4. **Consistency.** Quiesce all writers for the matched backup interval, copy artifact/state bytes, then snapshot the database. Copying artifacts first while writers continue is insufficient: later database rows may reference uncopied bytes. An alternative is to pin a database snapshot and copy every object reachable from it under a suitable retention guarantee. Preserve signing material and regenerable study/dataset state separately.

## Restore
1. Create an empty database (or restore the snapshot/branch) and set `PACT_DATABASE_URL`, `PACT_DB_TLS`.
2. For a dump, select a private `PGSERVICE` pointing to an explicitly approved **empty** restore target, then run `pg_restore --no-owner --exit-on-error pact-YYYYMMDD.dump`. Never restore over the populated production database as a routine drill. Replacing existing data requires a separate verified backup and explicit approval.
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
