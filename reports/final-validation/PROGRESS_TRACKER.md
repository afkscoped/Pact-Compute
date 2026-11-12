# Progress and resume tracker

The next objective, release candidate preparation, is tracked in [RC PROGRESS.md](../release-candidate/PROGRESS.md). This completed milestone tracker and its original source identity remain below for provenance.

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

| ID | Priority/component | Initial state | Changes/files | Evidence | Final state/blocker |
| --- | --- | --- | --- | --- | --- |
| P0-00 | Repository/audit | main checked out | Requested sasha-work; preserved untracked files; audit | IMPLEMENTATION_AUDIT.md | PASS |
| P0-01 | Baseline/environment | No Python on PATH | Bundled 3.12, project/GPU venvs, pinned locks, repeat-safe driver | baseline/final summaries | PASS |
| P0-02 | Datasets | 6/12 exact | Guarded approved Git-byte restoration, retained -text | dataset-restored.json | PASS |
| P0-03 | Events/evidence | Truncated replay/export; unsound gap timer | db.py, outbox.py, api.py; independent regressions | before logs, final tests, PG slow writer | PASS |
| P0-04 | Storage | Corrupt duplicate silently accepted | storage.py, local/moto retry tests | recovery-before.log, final tests | PASS |
| P1-05 | Migrations/recovery | Historic claims | Older schema retention, drift check, portable PG, cold dump/restore/hash/signature | postgres summary/tests/restore | PASS local |
| P1-06 | UI/roles | New screens unverified | e2e roles/exchange/workspace, axe, isolated server supervisor | browser-e2e.log, accessibility-axe.json | PASS scoped; manual audit BLOCKED |
| P1-07 | Physical GPU | Inventory only | prepare, CUDA jobs, negative input/model/timeout, actual cancellation and runner restart, independent output verifier | gpu logs/JSON, browser receipt, runtime-recovery.json | PASS single host; multi-host/soak combinations pending |
| P1-08 | Research | Historic numbers only | Two independent frozen runs, 12 identical outputs, CSV/figures/manifests | experiment-manifest.json | PASS reproduction; independent labels BLOCKED |
| P1-09 | Security/performance | Existing matrix | Hash/tenant/fence regressions, audits, 1,000 SQLite/25 PG races, HTTP measurements | security/performance/dependency reports | PASS bounded tests; GPU wheel audit PARTIAL; external review/soak pending |
| P1-10 | Deployment/docs | Stale instructions | Local runbooks, backup correction, CI source and authoritative report | documentation/index | PASS local preparation; hosted/Docker/account checks BLOCKED |
| P0-11 | Final regression | Earlier failures retained | Fresh database per invocation; content-bound full and clean-install runs | final/clean-install/browser/PostgreSQL summaries and source manifest | PASS: 260 backend, 5 separate PostgreSQL, 33 Node, 4 browser; 6 explained default-suite skips |

Unfinished tasks, in order:
1. Owner: supply authorized Render/Neon/bucket access, confirm deployed SHA and backup; approve any production migration/deployment separately.
2. In staging: drain all old writers, verify 0007, durable private bucket, supervision/readiness and real hosted GPU transaction; test image build on a Docker host.
3. Independent reviewers: execute ANNOTATION_PROTOCOL.md and full screen-reader/zoom/chart accessibility checklist.
4. Operator: run long outage/reconnect, sustained write/event-latency, live cancellation/restart combinations and load tests at a declared service scale.
5. Partner: authorize a second physical host/team, retention and workload collection; measure a pilot rather than infer production value from synthetic races.

Resume by reading FINAL_RELEASE_ASSESSMENT.md, source-manifest.json and latest summaries. Preserve `env` and the pre-existing status report. Do not push, merge or change production without new authorization. Never copy ignored state/secrets into reports. CI is prepared locally, not remotely executed.
