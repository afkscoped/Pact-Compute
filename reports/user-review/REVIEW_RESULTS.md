# Project review on 13 November 2026

The local faculty demonstration is working on this laptop. Start from the repository root with `run-demo.cmd`; stop with `run-demo.cmd -Stop`. The isolated demo is at http://127.0.0.1:8767 and retains state under `pact-compute/.local/faculty-demo`. Its administrator password and role passwords are in that directory's local credential files. Keep those files private.

## Fresh verification

- Backend: 265 passed, 6 skipped. Five PostgreSQL integration cases require their separate disposable server; one authorization scenario is covered elsewhere. See `final-review-backend.log` and `final-review-pytest.xml`.
- Frontend: 33 passed; TypeScript and production bundle passed. See `final-review-summary.json`, which records unchanged captured source.
- Browser: 4 passed, no failures, skips or flaky cases. See `faculty-browser.json`. Includes actual GPU output and hash verification, rejection, replay, exchange contention and tenant privacy, invitation/reviewer workflow, accessibility and mobile checks.
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU, driver engine, 4 rows of 960 values; inference 0.06491 seconds, GPU board energy 0.00001878 kWh, telemetry coverage 91.2%. Evidence is in the demo state's `verified/verification.json`. Model preparation CPU-reference cosine was 1.0; maximum numerical error was 5.21540641784668e-07.
- Startup: `run-demo.cmd -NoBrowser`, `run-demo.cmd -Stop`, and restart all succeeded; existing state retained.
- Dependencies: both used Python environments pass `pip check`. `npm ci` installed 66 packages and reported zero known audit findings at install time.
- Research: all six commands passed in the final unchanged-source run recorded in `final-research-summary.json`. All 12 evaluation artifacts match the earlier complete run byte for byte, as recorded in `research-reproduction.json`. Final files are under `.local/validation/final-research/evaluations`. The earlier complete `existing-research` numerical outputs match the report, but its driver returned nonzero because source files changed during that run; use final-research for the accepted provenance gate.
- Hosted health: https://pact-compute-sasha.onrender.com/api/health returned HTTP 200 with `status=ok` and `database=postgresql` after an initial timeout and retry. A later final check timed out after 20 seconds on both health and homepage; see `server-health.json`. Availability was intermittent from this client and is not confirmed reliable. Existing local port 8765 also returned PostgreSQL health. These checks do not establish hosted runner availability, deployed SHA, storage durability or all-user-workflow success. The final faculty-demo health check returned HTTP 200 on port 8767.

## Repairs and additions

Installed missing Moto S3 test dependencies into the project environment. Added a local compatible `prometheus-fastapi-instrumentator==8.1.0` to resolve the inherited 7.1.0 versus Starlette 1.10 conflict without altering the global installation. Synchronized frontend packages with the existing lockfile, including the missing axe Playwright dependency.

Added `run-demo.cmd`, `scripts/demo.ps1` and `scripts/demo.py`; ignored `.venv-demo`; allowed the browser role test report location to be overridden with `PACT_TEST_REPORT_DIR` so historical evidence is preserved. Existing application logic and the team's private `.env` were not edited. No commit, push or deployment was performed.

The working application interpreter is the existing Python 3.14.4 `.venv`, which inherits system packages. The GPU interpreter is a separate Python 3.12.14 `.venv-demo` with the GPU lock. The launcher prefers the existing application environment and passes the separate GPU interpreter explicitly. This is a tested laptop setup, not a claim that a clean machine bootstrap passed.

The newly installed Python 3.12 application libraries encountered Windows Application Control blocks in OR-Tools and PyArrow Parquet. Those blocks were not disabled. The existing application's native libraries load and pass the functional tests. The initial clean-review logs preserve this failure. The GPU runtime in the new environment loads and executes successfully.

## Remaining deployment limits

No Docker engine is installed, so an actual image build was not run. Current hosted commit, durable artifact storage, matched backup restoration, remote GPU execution, and hosted acceptance remain unverified. No writes or migrations were performed against the teammate's PostgreSQL database. The new demo uses its own SQLite database and local artifacts. Optional live Groq calls were not tested.

## Documents

`PACT_Compute_Implementation_Report.docx` contains approximately 4,985 words covering architecture, theory, implementation, metrics, limitations and future improvements. `PACT_Compute_Teacher_Demonstration_Guide.docx` contains approximately 3,496 words covering startup, exact website walkthroughs, expected results, roles, viva preparation, deployment and troubleshooting.

The packaged DOCX renderer could not locate LibreOffice on this Windows host. Microsoft Word's installed export engine was used instead, followed by bundled Poppler PNG rendering. All 10 report pages and 8 guide pages were visually inspected after the final edit. QA PDFs and PNGs are internal review intermediates rather than additional deliverables.
