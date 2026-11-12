# Hosted staging verification — owner execution procedure

**Prepared, not executed.** This procedure uses the existing Render/Neon/storage arrangement as its reference. It does not authorize a push or a production change. Do not paste secrets, private dumps, cookies or invitation/runner tokens into reports or chats.

## 1. Identify and authorize the target

The historical handoff identifies Render service `pact-compute-sasha`, origin `https://pact-compute-sasha.onrender.com`, fork `sashank-talapaneni/Pact-Compute`, branch `sasha-work`, and Neon project `pact-deploy` in aws-us-east-2. These names are repository history, **not current dashboard verification**. The earlier public probe was unconfirmed; it did not establish an outage or a current deployed SHA.

The owner first records: Render workspace/service ID, current live deploy ID/full Git SHA, linked repository/branch, auto-deploy setting, Dockerfile/context/command overrides, instance plan/replica count, health path, Neon project/branch/database ID and server major version, storage backend/bucket-prefix identifiers, and secret-variable **presence only**. Keep sensitive identifiers in a private operator record when appropriate.

The owner must explicitly designate a non-production staging target and approve its fixtures, restart/drain window, migration, storage writes and one GPU demonstration. If the existing service/database serves production or shared teammate data, stop before mutation: use an already approved isolated staging service/Neon branch/storage prefix or obtain approval for the missing resources. Do not create duplicate infrastructure or touch the teammate's database.

The uncommitted patch cannot be selected in Render. First review the local commit plan. A future **separate explicit authorization** is needed to push the reviewed SHA to the linked fork, or to publish an approved immutable image to an existing registry. Current instructions prohibit both. Record the source fingerprint and exact eventual full commit SHA; do not substitute `latest`.

## 2. Close the image gate and freeze release inputs

Execute the actual container gate in [VALIDATION.md](VALIDATION.md), retaining the build, image/base digests, image audit, startup, PostgreSQL and shutdown results. Reconcile image contents with `package-manifest.json`. Git-based Render builds use the repository context and `.dockerignore`; independently inspect that context and ensure private/generated files are absent. An allowlisted local tar does not prove a remote Git build received the same inputs.

For the authorized staging service, keep auto-deploy disabled during this controlled verification. Select **Manual Deploy → Deploy a specific commit** only after backup, drain and migration below. Record the full SHA and deploy ID. The dashboard supports this selection; CLI/API behavior around auto-deploy differs, so use the documented dashboard flow. [Render deployment documentation](https://render.com/docs/deploys).

## 3. Prepare matched recovery material before migration

1. Stop new submissions and all existing API/worker/runner writers for the approved target. Finish or safely reconcile in-flight attempts first. Record the last event sequence and affected attempt states. A normal zero-downtime rolling swap is insufficient for this patch: older writers lack the PostgreSQL transaction advisory lock.
2. Back up the target database, all reachable artifact bytes, applicable state snapshots/evaluations and the original signing secret in the owner secret store. Record hashes and the quiescent interval privately. A DB-only snapshot cannot restore outputs/signatures.
3. Use a PostgreSQL client compatible with the actual server. The owner configures private libpq service/password files or equivalent secret injection; keep password-bearing URLs out of arguments, logs and history. Example PowerShell, with aliases already configured privately:

```powershell
$env:PGSERVICE = 'pact-staging-source'
pg_dump --format=custom --file .local/staging-backup/database.dump
if ($LASTEXITCODE -ne 0) { throw 'Backup failed' }
pg_restore --list .local/staging-backup/database.dump > .local/staging-backup/contents.txt
```

Create the ignored backup directory first. Inspect dump warnings and record its hash. `pg_dump` supports custom archives consumed by `pg_restore`; the database export alone does not coordinate object storage. [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).

4. Restore into a separately approved **empty disposable** staging database, never over the live database. Change `PGSERVICE` to its explicit restore alias, then run `pg_restore --no-owner --exit-on-error .local/staging-backup/database.dump`. Avoid `--clean` against populated databases. Copy the matching artifacts into an isolated restore prefix/directory; use the same signing material privately for signature verification.
5. With that restore target's application environment loaded privately, run `python -m pact.cli artifacts-verify` and `python -m pact.cli verify PATH_TO_EXISTING_EVIDENCE_JSON`. Expect missing=0, corrupt=0 and `Evidence signature verified.` for a known original envelope. Confirm a known receipt/output is downloadable and hash-identical from the isolated restore app. Record actual counts/hash and restore duration.

Neon child branches isolate subsequent data changes from their parents, but branch creation and resource use require owner approval and do not back up the external artifact store. [Neon branch documentation](https://neon.com/docs/manage/branches).

**Stop gate:** no successful matched restore, no migration or rollout. If the current ephemeral service has already lost referenced bytes, record the missing artifacts and resolve that data gap; a redeploy cannot recreate them.

## 4. Validate staging configuration without printing values

| Setting | Required staging state |
| --- | --- |
| `PACT_DATABASE_URL`, `PACT_DB_TLS` | Approved staging DB only; TLS enabled (`1`); verify target identity privately before CLI commands |
| `PACT_URL`, `PACT_SECURE_COOKIE` | Exact HTTPS staging origin, no path; cookie setting `1` |
| `PACT_SIGNING_SECRET` | Stable owner-managed secret, backed up; do not rotate during this verification |
| `PACT_ADMIN_PASSWORD` | Owner secret for first bootstrap only; does not reset an existing admin |
| `PACT_STATE_DIR`, `PACT_SOURCE_DIR` | `/data`, `/app/PACT-Compute-data-preflight` in image; dataset import success required |
| `PACT_ARTIFACT_BACKEND` | `s3` with verified private store, or `local` on a verified persistent mount |
| S3 configuration | Existing approved `PACT_S3_BUCKET`, `PACT_S3_PREFIX`, optional endpoint/region; scoped object read/write and required missing-key lookup permissions; standard `AWS_*` credentials/session token if applicable, in the secret store |
| `PACT_MODEL_WEIGHTS_SHA256` | Approved full digest from the validated model evidence; same digest on the authorized runner |
| `PACT_RUN_MIGRATIONS` | `0` after the dedicated successful migration step |
| `PACT_RUN_IMPORT`, `PACT_RUN_WORKER` | `1` for the demonstration; supervisor command enabled, not bypassed by a dashboard command override |
| `GROQ_API_KEY`, `PACT_LLM_API_KEY` | Leave unset/disabled for deterministic demo unless provider use/budget is separately approved |
| `PORT`, health path | Render-provided port honored by supervisor; `/api/health` |

Free Render services cannot attach persistent disks or use dashboard/SSH shell or one-off jobs. Their filesystem is ephemeral; a restart can remove local artifacts. Therefore the existing free service needs verified external artifact storage, and administrative commands must run from an authorized operator environment against the staging database. Do not prescribe an unavailable Render shell. [Render free-service limitations](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).

Do not change bucket policy or enable billing without approval. On S3, verify private access and scoped permissions; corresponding non-AWS provider behavior must be checked with that provider. [AWS S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).

The current store checks `HEAD` before a new object upload and treats 403 as a real permission error. AWS uses `s3:GetObject` for HEAD and returns 404 for a missing key only when the caller also has `s3:ListBucket`; otherwise it returns 403. The owner must approve the necessary bucket permission or compatible provider policy and verify a previously absent key can be uploaded. Do not treat every 403 as an absent object. KMS-encrypted storage may need additional key permissions. [AWS HeadObject permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html).

## 5. Apply the approved migration and deploy exact source

In the approved operator environment, with the reviewed runtime and target settings injected privately:

```powershell
$env:PYTHONPATH = 'backend'
python -m alembic current
python -m alembic heads
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; keep target drained' }
python -m alembic current
python -m alembic check
```

Expected head is `0007`. Retain before/after schema revision and drift-check result. There is no new RC migration; an already-current DB should remain at 0007. Do not run downgrade as a rollout shortcut. Run `python -m pact.cli init`/`import` only for the approved target if needed. Import success should report 7,064 GPU pods and 1,344 carbon intervals with the approved dataset identity.

Ensure every old application writer remains stopped. Deploy the exact authorized SHA, using the image CMD (`/entrypoint.sh` → `python -m pact.service`). Inspect restricted startup logs for migration/import outcomes, worker/API process start and errors; do not export secret-bearing logs. Start the new authorized runner only after the new API is healthy. Retain one API/worker installation for this small-scope demonstration.

Dataset import restores source snapshots, not frozen publication-study files. If those publication panels are part of the hosted demonstration, provide an approved deployment/state-restoration path for the hash-verified frozen outputs or an authorized regeneration step. Free Render has no shell to copy them after deployment, and S3 artifact storage does not automatically persist the entire state directory. Otherwise record those hosted publication panels as unavailable; retain their verified local evidence.

## 6. Verify hosted behavior and durable storage

Use the owner-confirmed HTTPS origin in place of `STAGING_ORIGIN`:

```sh
curl --fail --silent --show-error --max-time 120 STAGING_ORIGIN/api/health
curl --silent --show-error --max-time 30 -o /dev/null -w '%{http_code}\n' STAGING_ORIGIN/api/v1/jobs
curl --silent --show-error --max-time 30 -o /dev/null -w '%{http_code}\n' \
  -H 'Content-Type: application/json' -H 'Origin: https://example.invalid' \
  --data '{}' STAGING_ORIGIN/api/v1/session
```

Expect health JSON `status=ok`, `database=postgresql`; unauthenticated jobs **401**; cross-origin write **403**. Record TLS/browser certificate status and health timing, allowing a bounded cold start. Health success alone does not establish runner, storage, dataset or worker readiness.

In separate browser profiles create approved test producer and consumer organizations, plus reviewer through Team invitation. Prove consumer self-approval is forbidden and reviewer approval works. Inspect cookie **attributes only** (Secure, HttpOnly, SameSite) and same-origin session behavior. Do not copy cookie values or invitation codes into reports. Check desktop/mobile navigation, error recovery, reviewer inbox, what-if revisions and incident queue.

Publish one known test artifact through the application, download it as its permitted member, record SHA-256 and verify denied access from an unrelated organization. Run `artifacts-verify` using the exact approved backend/prefix. Restart the staging service with owner approval; verify the same artifact and earlier evidence signatures still work. If switching from local to S3, copy existing bytes first and verify every metadata reference before changing backend; configuration alone does not migrate bytes.

## 7. Perform the physical hosted GPU demonstration

1. On the already validated NVIDIA host, use the pinned GPU environment, approved model digest and CUDA Driver engine. Enroll a **new scoped staging runner** in the producer UI. Store its ID/token privately on that host. Do not reuse production tokens or report the one-time token screen.
2. Point only that runner at the confirmed staging HTTPS origin. Verify real heartbeat/device/VRAM/ready status from actual hardware. The local GTX 1650 exposed 4,095 MiB, so the example 4 GiB threshold is infeasible. Use a reviewer-approved 3 GiB policy (or appropriate actual hardware); never edit inventory to make admission pass.
3. Publish a bounded offer, request a quote as consumer, confirm once and retry confirmation. Require one booking/job and no duplicate reservation. Record non-secret entity IDs and event sequence.
4. Execute the approved image-embedding workload on physical CUDA. Verify backend/engine, input/model/output hashes, 960 finite normalized dimensions, attempt count, timing/telemetry, usage receipt, capacity release and independent evidence/audit result. Clearly label modeled energy/carbon estimates separately from measured telemetry.
5. Download output and evidence through the permitted consumer session; verify hash and original HMAC with owner-controlled signing material. Prove unrelated-tenant denial and producer receipt scope. Do not export token/session/signing material.
6. Reconnect a browser using its retained event cursor, then perform one approved runner/API restart and confirm no duplicate execution or missing terminal events. A cancellation test may use a separate bounded approved job; record actual acknowledgement/release, never assume a requested cancel succeeded.

## 8. Acceptance and recovery decision

Hosted demonstration is ready only when the owner records: exact source/image/deploy identity; approved target and restore evidence; schema 0007/drift check; PostgreSQL health/TLS/cookie/CSRF results; private durable storage round trip across restart; producer/consumer/reviewer isolation; one genuine hosted GPU job with verified output/receipt/audit; reconnect/recovery result; manual accessibility walkthrough and any explicitly accepted scoped limitations.

If verification fails, keep new submissions paused, stop the staging runner and retain evidence. Choose a tested forward fix or restore the matched backup into an isolated target. Any change back to production or database replacement needs its own approval. An older app rollback can remove the event-order guarantee and cannot be mixed with new writers. Record the operator's final decision and unresolved defects; do not mark the hosted gate passed from this prepared procedure alone.
