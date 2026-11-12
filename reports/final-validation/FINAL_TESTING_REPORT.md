# Final testing

The content-bound `final-summary.json` and `clean-install-summary.json` are the authoritative final runs at 260 passes. The older `final-repeat-summary.json` is historical evidence from before the five additional failure-recovery cases; it is not used for the final source attestation.

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Backend: **260 passed, 0 failed, 0 errors, 6 skipped** ([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **5 passed** separately ([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed ([commands](final-summary.json)). Browser: **4 passed**, 0 failed ([report](browser-e2e.log)).

The final suite passed again in a fresh locked environment (clean-install-summary.json), and a separate repeat run is retained (final-repeat-summary.json). Five default-suite PostgreSQL skips ran and passed separately; the sixth skip explicitly duplicates another authorization test. One upstream Starlette/httpx TestClient deprecation warning remains; the actual HTTP/browser tests also passed. CI source is prepared locally but has not been remotely executed.

| Gate | Status | Evidence / scope |
| --- | --- | --- |
| A Backend | PASS | Final pytest, fixture-scoped functional coverage |
| B Frontend | PASS | Node, TypeScript/build and four browser workflows |
| C PostgreSQL | PASS | Disposable PostgreSQL 18.7, five integration cases |
| D Migrations | PASS | SQLite older-data upgrade, rollback/forward and drift check; PostgreSQL 0002→0007 |
| E Authentication/authorization | PASS | Existing route-derived matrix plus actual browser role separation |
| F Tenant isolation | PASS | Cross-tenant API and shared-receipt/private-artifact browser checks |
| G Marketplace integrity | PASS | 1,000 SQLite and 25 PostgreSQL races; duplicate confirmations |
| H Runner/workload | PASS | Physical CUDA jobs plus lease/fence/cancel contract regressions |
| I Artifact recovery | PASS | Integrity retries, local/moto, real PostgreSQL matched restore |
| J Failure injection | PASS | Covered bounded cases; not an outage soak certification |
| K API integration | PASS | TestClient matrix plus real loopback HTTP/browser requests |
| L Browser E2E | PASS | Producer/consumer race, reviewer invite/inbox, what-if/incident, GPU/research |
| M Accessibility | BLOCKED | Axe clean on two views and keyboard/mobile checks; full screen-reader/zoom/chart review pending |
| N Security regressions | PASS | Scoped auth/storage/fence tests and current dependency scans; no independent penetration test |
| O Performance | PASS | Declared small warm local workload; not WAN or production scale |
| P Research reproduction | PASS | 12 byte-identical artifacts over two frozen runs; human-label validity remains blocked |
| Q Live GPU | PASS | Physical GTX 1650, CPU reference, output hashes/vectors, measured board telemetry |
| R Hosted deployment | BLOCKED | Owner access, exact deployed SHA, storage and authorized rollout verification |
| S Backup/restore | PASS | Disposable pg_dump/pg_restore plus matching objects and original signature; production drill pending |

PASS applies only to the explicit evidence scope. Missing hardware-failure combinations, long outages and scale tests are not concealed by the aggregate counts.
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
