# Release candidate assessment — 13 November 2026

**Local RC preparation is complete within the executable scope below. Hosted demonstration readiness remains blocked.** Work is on `sasha-work`, base `4bbc1d7077f3d3084df9eb1337b734880ee79181`, with an uncommitted review patch. No commit, push, merge, cloud deployment or production migration was performed.

All 27 milestone reports in `reports/final-validation` were read. Their original source fingerprint and results remain historical evidence. The current executable fingerprint is `772472e23d5ac3fc885b525083abcdc65b72c31fab2291618ac43e517617502c`; [source-manifest.json](source-manifest.json) records the files. Capture scope now also includes Docker ignore rules, frontend build/test configuration and RC tools; additions to that capture are not necessarily new Git files.

## Changes completed during RC preparation

| Finding | Resolution | Verification |
| --- | --- | --- |
| Docker context could include ignored root `env`, dotenv variants and the GPU environment | Hardened `.dockerignore`; added an explicit allowlisted, deterministic context builder | Two packaging regressions; real repeated archives identical; clean frontend built from archive |
| Mobile drawer did not move/trap keyboard focus or close on Escape | Focus entry, Tab containment, Escape, focus return, inert background and modal semantics | Browser regression and expanded axe/reflow/chart checks |
| Entrypoint background worker could die while API health stayed green | Added API/worker process supervisor; unexpected child exit fails the service and stops its sibling | Three backend subprocess cases; equivalent Linux smoke checks |
| Windows esbuild child error was hidden by a zero npm exit code with file-backed stderr | Validation now captures pipes, persists bytes and rejects known fatal output even with exit zero | Clean corrected build and fresh packaged build; adverse log retained |
| New fixtures could fall through to dotenv bootstrap secrets | Explicit random, isolated RC bootstrap credentials | Fresh fixture runs; no secret values in public reports |
| Evidence collector and report generator could disagree on captured inputs | One capture implementation; expanded build/configuration coverage; separate RC output destination | Content manifests and before/after source checks |

See [PATCH_REVIEW.md](PATCH_REVIEW.md) for the complete change classification and [VALIDATION.md](VALIDATION.md) for commands and evidence limits.

## Verified evidence and its scope

| Gate | Result | Scope |
| --- | --- | --- |
| Current backend regression | **265 passed, 6 skipped** | Fresh isolated SQLite run; five skipped PostgreSQL cases retain their separate completed milestone evidence, one authorization case is covered by another test |
| Current frontend unit/build | **33 passed; TypeScript and fresh production build passed** | Corrected subprocess capture; fatal child output absent |
| Accessibility automation | **2 browser tests passed** | 13 role/view combinations plus pricing/FSM and runtime chart alternatives; zero tagged axe violations; mobile focus/Escape; 320px reflow; reduced-motion preference; CSS 200% zoom proxy |
| Release context | **PASS** | 82 allowlisted inputs, 2,037,760 bytes; deterministic archive SHA-256 `69b516ed31b5c7cf6115cd245e131c1664a75d4ce3b15e3f0c0154c2d5e05dc8` |
| Clean packaged frontend | **PASS** | Fresh `npm ci --ignore-scripts` and build using only archived inputs; new HTML/JS/CSS produced |
| Linux runtime packaging | **PASS** | Existing Ubuntu, Python 3.12.3; all 42 runtime lock versions installed, pip 26.3; dependency check, shell syntax, migrations to 0007, init/import, API/auth/storage and supervisor smoke |
| Secret/file hygiene | **PASS within scan scope** | Reviewable text/common secret formats; no forbidden credential/state files; private root `env` preserved and ignored |
| Actual Docker image | **BLOCKED** | No local Docker/Podman engine. No OCI build, image scan, image signal lifecycle or container PostgreSQL/S3 run is claimed |
| Full accessibility conformance | **PENDING human review** | Native browser zoom, screen readers, content-rich forms/errors, visual chart comprehension and target-size/contrast review remain |

The accepted final local regression is [rc-final-summary.json](rc-final-summary.json), with [backend XML](rc-final-pytest.xml). The initial `rc-summary.json` frontend-build result is **invalidated**: its zero exit code hid an esbuild error. The corrected final result supersedes it. Preserve `rc-frontend-build-before.log` as adverse evidence.

The completed milestone remains: **5 PostgreSQL tests**, **4 browser workflows**, physical GTX 1650 CUDA execution and CPU-reference/output checks, 1,000 SQLite/25 PostgreSQL capacity races, 12 artifacts reproduced twice, and matched recovery/restore checks. These were not unnecessarily repeated. Database, scheduling, GPU, model and research implementation bytes remain unchanged from that milestone; RC changes affect UI focus, startup supervision, packaging and validation tools. The exact historical scope and source identity remain in [the milestone assessment](../final-validation/FINAL_RELEASE_ASSESSMENT.md).

All six dependency manifests/locks match that milestone ([comparison](dependency-provenance.json)). Earlier frontend/backend scans had no known findings at their recorded time. **GPU advisory coverage remains partial:** exact torch/torchvision CPU wheel versions were skipped by the tool. Linux installation compatibility does not close that advisory gap. CI source is present but has not run on GitHub. Existing base image tags are mutable; record their resolved digests and audit the completed image at the image gate.

## Readiness decisions

| Intended use | Decision | Remaining gate |
| --- | --- | --- |
| Local academic demonstration | Ready within recorded single-host scope | Use the pinned environments and genuine feasible GPU policy |
| Locally reproducible research artifact | Ready within frozen-study scope | Retain adverse results, manifests and limits on modeled/generalization claims |
| Hosted demonstration | **Not ready** | Image build, owner-approved staging target/source transfer, exact hosted SHA/config, matched backup/restore, durable storage, hosted GPU transaction and manual acceptance |
| Restricted pilot | **Not ready** | Hosted gates plus two authorized hosts/teams, workload agreement, monitoring, recovery targets and observation period |
| Public/commercial production | **Not ready** | Independent security/accessibility review, GPU advisory closure, operational/SLO evidence and product/accounting/identity decisions |

The PostgreSQL event-order fix serializes application writers and requires **all older writers to be drained before rollout**. It is a correctness trade-off for a small installation; there is no new production throughput claim. API health checks test the database, not storage, research imports or runner readiness. The supervisor detects process death, not a hung-but-alive worker.

To reach hosted demonstration readiness, follow [HOSTED_STAGING_VERIFICATION.md](HOSTED_STAGING_VERIFICATION.md) in order. The exact access, approval, hardware and human requirements are in [EXTERNAL_REQUIREMENTS.md](EXTERNAL_REQUIREMENTS.md). A reviewable local commit sequence, with exclusions, is in [COMMIT_PLAN.md](COMMIT_PLAN.md). No external action is implied by these procedures.
