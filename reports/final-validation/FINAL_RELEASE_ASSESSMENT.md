# Final release assessment

RC follow-up: the milestone below is retained at its original source identity. Read the newer [release candidate assessment](../release-candidate/RELEASE_ASSESSMENT.md) for current UI/startup/packaging fixes, verified RC evidence, adverse build-log correction, hosted procedure and commit plan. This note does not relabel the milestone results as new test runs.

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Backend: **260 passed, 0 failed, 0 errors, 6 skipped** ([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **5 passed** separately ([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed ([commands](final-summary.json)). Browser: **4 passed**, 0 failed ([report](browser-e2e.log)).

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
## Readiness decisions

Residual security/operational limits are detailed in [SECURITY_REVIEW.md](SECURITY_REVIEW.md) and [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md). In particular, the advisory tool skipped the two exact CPU PyTorch wheel versions; GPU dependency-audit coverage is partial. The PostgreSQL ordering guarantee requires all writers to use the new transaction lock, so drain older writers before any authorized rollout. A real cloud bucket, production restore and Docker image build remain unverified.

| Intended release | Decision | Required next action |
| --- | --- | --- |
| Local academic demonstration | PASS within recorded single-host scope | Rehearse with the pinned GPU environment and exact dataset bytes |
| Reproducible research artifact | PASS | Preserve all manifests, environment locks and adverse results |
| Research submission with generalization claims | BLOCKED | Independent labels/review, claim scope and license/source checks |
| Hosted demonstration | BLOCKED | Owner access, exact deployed SHA, authorized rollout, durable storage and hosted GPU transaction |
| Restricted private GPU pilot | BLOCKED | Two authorized hosts/teams, workload agreement, monitoring, recovery targets and observation window |
| Public/commercial production | BLOCKED | Independent security/accessibility review, isolation, accounting/settlement, identity recovery, operational/SLO evidence |

Hosted revision/configuration and real bucket require owner account access. Production migrations require a verified backup and explicit approval. Independent agreement/support labels, screen-reader review, partner agreements, two-host pilot and a longer observation window require humans/resources. No hosted mutation, partner participation or production readiness is claimed.

The working tree intentionally contains the reviewed implementation/test/documentation patch and the user's pre-existing report; no local commit, push or merge was performed. `source-manifest.json` identifies the exact tested executable content. `working-tree.txt` records filenames only. No production migration or deployment modification occurred. Recommended next action: review this patch and the blocked-gate procedures, then provide authorized staging/account access and independent reviewers for the remaining external gates. Do not equate this local demonstration with a public marketplace release.
