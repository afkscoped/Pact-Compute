# Release candidate preparation — 13 November 2026

Baseline: `sasha-work` at `4bbc1d7` with the previous uncommitted validation patch. All 27 prior reports were read; milestone evidence is retained in reports/final-validation and will not be overwritten as a new result.

| Task | State | Evidence / next step |
| --- | --- | --- |
| RC-01 Diff and generated-file review | COMPLETE within stated scope | PATCH_REVIEW.md; no dataset content diff; private state/user report preserved; secret scan and final hygiene record |
| RC-02 Packaging isolation | COMPLETE locally | Hardened .dockerignore; deterministic 82-member archive; canary tests; clean packaged npm install/build; package-manifest.json and packaging-summary.json |
| RC-03 Accessibility | AUTOMATION COMPLETE / HUMAN GATE PENDING | Mobile focus defect fixed; 2 browser cases across 13 role/views and chart tables pass; native zoom/screen-reader review pending |
| RC-04 Linux/Docker compatibility | LINUX PASS / IMAGE BLOCKED | Existing Ubuntu 3.12.3, 42 pinned runtime packages, migrations/API/storage/supervision pass; no Docker/Podman engine, no OCI build |
| RC-05 Dependencies and evidence provenance | COMPLETE within stated scope | Six locks/manifests match completed milestone; dated scans retained; GPU advisory coverage still partial; false-green Windows build capture corrected |
| RC-06 Hosted staging procedure | PREPARED / EXECUTION BLOCKED | HOSTED_STAGING_VERIFICATION.md; existing Render/Neon/storage target verification, backup/restore, writer drain, exact SHA, GPU transaction; owner access/approval required |
| RC-07 Commit plan and assessment | COMPLETE | RELEASE_ASSESSMENT.md, COMMIT_PLAN.md and EXTERNAL_REQUIREMENTS.md; explicit file groups/exclusions, no commits made |

No push, merge or production action is authorized. Preserve the private ignored root env and pre-existing project report. Use reports/release-candidate for new evidence.

Accepted final RC regression: **265 backend passes, 6 skips; 33 frontend tests; TypeScript/production build pass**, bound to source fingerprint `772472e23d5ac3fc885b525083abcdc65b72c31fab2291618ac43e517617502c`. Use rc-final-summary.json, not the earlier rc-summary.json build result, which was invalidated by fatal esbuild output hidden by a zero exit code. Before logs are preserved. Clean packaged frontend and Linux smoke both refer to archive `69b516ed31b5c7cf6115cd245e131c1664a75d4ce3b15e3f0c0154c2d5e05dc8`.

Resume with the first unmet external gate: obtain an authorized container engine/build host and owner-confirmed isolated staging access/source-transfer approval. Follow the staged procedure; do not rerun the completed GPU/research/contention milestone merely to increase totals. Complete native zoom/screen-reader acceptance with a human. Any new executable change requires affected checks and an updated RC manifest; never regenerate historical passes against changed bytes.
