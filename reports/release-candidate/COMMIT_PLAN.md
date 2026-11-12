# Local commit plan — review before execution

Prepared on `sasha-work`, base `4bbc1d7077f3d3084df9eb1337b734880ee79181`. **No staging, commit, push, merge or branch change was performed.** The user requested a plan. Preserve the working tree and private state while reviewing.

## Proposed cohesive sequence

1. **`fix: preserve complete event and artifact evidence`**
   - Backend: `api.py`, `db.py`, `demo.py`, `outbox.py`, `storage.py` under `pact-compute/backend/pact`.
   - Tests: `test_control_plane.py`, `test_capacity_contention.py`, `test_event_delivery.py`, `test_failure_recovery.py`, `test_release_recovery.py`, `tests/postgres/test_postgres_integration.py`.
   - Review transaction serialization/rollout requirement explicitly. Evidence: current backend suite plus inherited five PostgreSQL cases and capacity/recovery results.
2. **`fix: make mobile navigation keyboard accessible`**
   - `frontend/src/main.tsx`, `package.json`, `package-lock.json`; changed existing E2E files plus `e2e/roles.spec.ts`; `playwright.rc.config.ts`, `rc-e2e/accessibility.spec.ts`.
   - Evidence: 33 frontend tests, TypeScript/build, two expanded RC browser cases. Four physical milestone workflows are historical evidence, not newly rerun tests.
3. **`build: isolate release inputs and supervise service processes`**
   - `.gitignore`, `.dockerignore`, Dockerfile, `deploy/entrypoint.sh`; `backend/pact/service.py`, `tests/test_service.py`, `tests/test_rc_packaging.py`.
   - Four Python lock files; `.github/workflows/validation.yml`.
   - Validation scripts: `browser_validation.py`, `export_research.py`, `export_runtime_lock.py`, `finalize_validation.py`, `gpu_validation.py`, `http_performance.py`, `postgres_validation.py`, `runtime_recovery.py`, `security_scan.py`, `validate.py`, `validation_manifest.py`, `rc_browser.py`, `rc_linux_smoke.py`, `rc_package.py`, `rc_packaging_smoke.py`.
   - Evidence: packaging canaries/determinism, clean packaged frontend, Linux smoke and process tests. Docker engine/image and hosted CI gates remain unexecuted.
4. **`docs: record validation evidence and staging release gates`**
   - Root `BACKUP_RESTORE.md`, `CLAUDE.md`, `DEPLOYMENT.md`, `HANDOFF.md`; project README and research-results pointer.
   - Review the complete intentional public evidence package: the 27 milestone Markdown reports, their linked non-secret JSON/XML/log/CSV/PNG/SVG inputs, and current RC reports/evidence. Preserve original/adverse results so links remain useful.
   - Evidence is about 2.5 MiB in the milestone directory, including a relatively large earlier isolation-failure log. It can be a separate evidence commit if reviewers prefer; do not silently omit linked adverse evidence. Never regenerate historical passes to match the new commit SHA.

Commit 3 intentionally follows the UI/test dependency change. For each proposed commit, stage **explicit named files** or reviewed hunks; inspect `git diff --cached --stat`, `git diff --cached --check`, the actual staged diff and the scanner output before committing. Do not use `git add .`, `git add -A` or blanket stage the workspace. The full current regression result applies to the aggregate patch; if intermediate commits need to be independently releaseable, validate each resulting staged snapshot separately before claiming that property.

## Exclusions and safeguards

- Exclude the preserved user-owned `PROJECT_STATUS_REPORT_2026-11-12.md` unless the user explicitly asks to include it.
- Do not stage the six dataset paths with status-only line-ending/index changes; their content diff is empty and manifest bytes are approved. Do not reset/discard them. Existing `.gitattributes` is already tracked and unchanged.
- Exclude root `env`, all dotenv/deploy credentials, `.local`, DB/WAL/SHM, model weights, runner journals, tokens/signing material, venvs, npm/Python caches, Playwright output, compiled `dist` and tar archives.
- Include dependency **lock definitions** and reviewed public package manifests, not installed distributions. Include intentional research figures/tables only as evidence, not runtime build inputs.
- Keep both report generations labeled with their original content identities. Final assessment/source manifest should record eventual local commit IDs as a new note without rewriting original test evidence.

## Final local review commands

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
git diff --numstat -- PACT-Compute-data-preflight
pact-compute/.venv/Scripts/python.exe pact-compute/scripts/security_scan.py --output-dir reports/release-candidate
```

Expect branch `sasha-work`, the recorded base SHA until commits are explicitly made, no whitespace errors and no content diff for the dataset paths. Verify `reports/release-candidate/source-manifest.json` against the executable tree. A later commit does **not** authorize a push; the historical Render service may auto-deploy on push, so obtain separate source/deployment authorization first.
