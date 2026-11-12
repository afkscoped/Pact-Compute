# Uncommitted patch review

Reviewed against `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`. This review includes tracked diffs and reviewable untracked source/test/configuration files. The user's pre-existing root project report is preserved as user-owned content.

## Classification and correctness

| Change group | Files / behavior | Review conclusion |
| --- | --- | --- |
| Transaction and event correctness | `backend/pact/db.py`, `outbox.py`, `api.py`; event/history/capacity tests | Retains scoped ordered events across pages and complete signed traces. PostgreSQL advisory lock is taken before other application locks. Intentional write-throughput trade-off; drain mixed-version writers |
| Artifact integrity | `backend/pact/storage.py`; local/moto/recovery tests | Existing object bytes are verified on duplicate writes. No storage migration or existing-object deletion added |
| Local fixture origin | `backend/pact/demo.py`, backend regression | Explicit loopback HTTP ports permitted; remote/lookalike origins rejected |
| Mobile navigation | `frontend/src/main.tsx`, RC browser test | Focus managed inside drawer; background inert; Escape/focus return; established visual layout retained |
| Browser regressions | Existing E2E files plus `roles.spec.ts`, RC config/test, axe package and lock | Changes address accessible selectors, isolated state, real feasible 3 GiB policy and role/session workflows. Inventory/VRAM is not falsified |
| Process lifecycle | `backend/pact/service.py`, entrypoint, subprocess tests | Both API and enabled worker required to remain alive; unexpected exit fails service, siblings terminated and reaped; bounded kill fallback |
| Packaging | Dockerfile, ignore files, runtime lock, `rc_package.py`, packaging tests/smoke | Runtime/test dependencies separated. Explicit archive excludes env, credentials, caches, reports, databases and virtual environments. Required inputs/data hashes checked; symlink inputs refused by code |
| Validation and CI | Scripts, four locks, `.github/workflows/validation.yml`, new regression fixtures | Local databases/ports and hardware evidence are distinguished. Optional PostgreSQL tests reject non-local/non-disposable databases. CI workflow is unexecuted source, not hosted evidence |
| Documentation/evidence | Root handoff/deployment/backup docs, project README/research pointer, both report directories | Historical milestone preserved; RC results and blocked gates separately dated; exact commit plan provided |

The six dataset paths shown as modified by Git contain **no content diff** (`git diff --numstat -- PACT-Compute-data-preflight` is empty). Approved manifest bytes remain intact. This is cached line-ending/index metadata from the earlier restoration; do not stage, reset or discard these paths merely to make status look clean. `.gitattributes` retains `-text` for approved assets.

No unrelated feature redesign, authorization expansion, pricing-rule change, new schema migration or production configuration mutation was introduced. Correctness review does not certify scalability or independent security approval.

## Secrets and generated files

- Private root `env` was not read and is ignored; dotenv/deploy files and runtime credentials must remain private. The Docker exclusion omission was a possible exposure path, not evidence that a secret was previously uploaded.
- Format scanning includes reviewable source, documentation, JSON, logs and XML. Results contain locations/kinds only, never matched values. See [secret-scan.json](secret-scan.json). Common-pattern scanning is not an arbitrary-secret or Git-history audit.
- `.local`, virtual environments, databases, weights, runner journals, npm/Python caches, frontend `dist`, Playwright results and release tar archives stay ignored. Their presence is expected during validation.
- Research CSV/PNG/SVG outputs and report JSON/XML/logs are intentional generated evidence. Preserve adverse logs. Review and commit these only as the separate evidence group in the commit plan; do not blanket-stage `reports`.
- The existing `PROJECT_STATUS_REPORT_2026-11-12.md` is user-owned and excluded from this plan. No user work was discarded.

## Confirmed RC defects and adverse outcomes

1. Mobile drawer focus/Escape failure was independently reproduced before its fix; the final regression is green. No pre-fix raw browser log is represented as retained evidence.
2. Docker ignore rules omitted secret/environment variants. The allowlist and canary regressions address this locally; actual Docker ignore matching/image contents still need an engine.
3. The old entrypoint left a background worker unsupervised. Windows subprocess regressions and Linux smoke now verify child exit propagation and shutdown.
4. A build subprocess produced an unhandled esbuild error with npm exit zero when stderr was a Windows file. `rc-frontend-build-before.log` retains the failure. Pipe capture and fatal-output rejection now prevent that false green. The clean-package first attempt also failed writing npm's default cache; the project-local cache run passed.

## Review limits to carry forward

Global PostgreSQL writer serialization must be measured under hosted load; unbounded complete evidence exports can use more memory for very long histories. Process supervision does not establish application-level worker liveness. The real object store, container build/base layers, deployed revision, hosted TLS/cookies and independent manual accessibility/security reviews remain separate gates. Exact GPU wheel advisory coverage remains incomplete. None is silently converted into a pass by aggregate test counts.
