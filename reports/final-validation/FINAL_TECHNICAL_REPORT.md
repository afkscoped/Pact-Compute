# Authoritative technical inventory

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

The implemented application is a React/TypeScript console served by FastAPI. SQLAlchemy/Alembic stores organizations, members, memberships, sessions, policy versions, runners, jobs/attempts, offers/quotes/bookings, artifacts, events, reviews, rate hits and incidents. Current head is 0007. The research worker leases runs; the native runner authenticates, downloads hash-linked input, executes an approved template, reports telemetry/outcome and journals uncertain callbacks. Artifacts use local/S3 interfaces with content-addressed verification.

Policies are bounded typed constraints with source spans and privileged review. Admission and dispatch enforce current/pinned terms; independent monitoring reconstructs policy/protocol outcomes. Quotes expire without holding capacity; confirmation rechecks policy/offer versions under locks. One exclusive GPU and 1–16 image MobileNet embeddings are supported. Internal credits and adjustments are usage evidence, not a settlement ledger or payments.

Membership invitations and workspace switching, reviewer inbox, counterfactual preview, incident resolution, pagination and shared limits exist and have current local evidence. Counterfactuals create a new draft only on explicit acceptance; fixed suggested steps do not guarantee a feasible option, particularly from a zero budget. Live runtime remains 38 + 3 × images seconds. Research runtime models/CP-SAT are separate; no validated runtime model has been silently wired into live dispatch.

Formal synthesis, external FlexFringe, arbitrary workloads, distributed multi-GPU training, public billing, OIDC and independent commercial collusion determination remain future work. Deployment, research validation and pilot validation are distinct states. Historical reports/plans do not override the source manifest and current evidence.

Literature correction verified against primary sources: [Ji et al. SRAP-Agent](https://aclanthology.org/2024.findings-emnlp.15/) concerns resource-allocation policy simulation; [Wu and Tu, Layer-Condensed KV Cache](https://arxiv.org/abs/2405.10637) concerns inference memory, not allocation agents. The original slide/report files remain historical; use this correction before re-presenting the mismatched row. No exhaustive literature review or stronger novelty claim was added.

| ID | Fixed behavior | Regression evidence |
| --- | --- | --- |
| DATA-01 | Restored exact approved Git bytes; retained manifest identity and -text attributes | dataset-restored.json captures before/after hashes; current dataset-check.json and fresh imports |
| EVT-01 | Drains all reconnect/live SSE pages before advancing a cursor | event-regression-before.log (2 failures), event-regression-after.log; tests/test_event_delivery.py |
| EVT-02 | PostgreSQL writers acquire a transaction lock before application locks/sequence allocation | postgres-before.log fails slow writer; postgres-tests.log passes after fix |
| EVT-03 | Signed job exports and independent monitoring retain complete event history | evidence-before.log fails after 1,000 events; final regression passes |
| STORE-01 | Existing local/S3 bytes are reverified on idempotent writes | recovery-before.log fails corrupt retry; local and moto regressions pass |
| TEST-01 | Fresh database per validation invocation; skipped PostgreSQL collection no longer initializes app config | test-isolation-before.log; final and repeated final runs |
| ENV-01 | Local pip/GPU setuptools security updates and compatible pinned GPU pair | dependency audit JSON, pip check, repeated real GPU validation |
| E2E-01 | Correct consumer Home, accessible selectors, isolated state/port, feasible declared hardware policy | browser-initial.json.log versus final browser report |

Event ordering intentionally serializes PostgreSQL write transactions for this small private installation. Reads remain concurrent. Drain all older API/worker/runner writers before rollout; mixed-version writers do not share the guarantee. This is a throughput trade-off, not a scalable dispatcher implementation.
Backend: **260 passed, 0 failed, 0 errors, 6 skipped** ([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **5 passed** separately ([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed ([commands](final-summary.json)). Browser: **4 passed**, 0 failed ([report](browser-e2e.log)).

From `pact-compute`, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/validate.py datasets
.\.venv\Scripts\python.exe scripts/validate.py final
.\.venv\Scripts\python.exe scripts/postgres_validation.py
.\.venv\Scripts\python.exe scripts/validate.py contention
.\.venv\Scripts\python.exe scripts/gpu_validation.py
.\.venv\Scripts\python.exe scripts/browser_validation.py
.\.venv\Scripts\python.exe scripts/validate.py research
.\.venv\Scripts\python.exe scripts/validate.py research --label research-repeat
.\.venv\Scripts\python.exe scripts/export_research.py
```

PostgreSQL needs the official portable binaries under `.local/postgres-runtime/pgsql/bin`.
Browser validation needs Edge, the built console, prepared model weights under `.local/validation/browser`,
and a separate `.gpu-venv` with the recorded GPU lock. It refuses an occupied port 8766.
It starts/stops its own API, worker and runner. It never attaches to the pre-existing listener on 8765.
All databases/providers are explicitly isolated; preserve private .env files.
