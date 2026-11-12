# PACT-Compute

Current RC preparation (13 November 2026): [release assessment](../reports/release-candidate/RELEASE_ASSESSMENT.md), [validation commands](../reports/release-candidate/VALIDATION.md), [hosted staging procedure](../reports/release-candidate/HOSTED_STAGING_VERIFICATION.md) and [local commit plan](../reports/release-candidate/COMMIT_PLAN.md) are the current release index. The completed milestone and [technical inventory](../reports/final-validation/FINAL_TECHNICAL_REPORT.md) remain in reports/final-validation. No commit, push, merge or production change was performed.

PACT-Compute is a GPU job control plane with a React console, FastAPI API, independent worker, and native GPU runner. A reviewer turns an agreement into an approved policy. The control plane checks it at admission and dispatch. The runner executes a pretrained image embedding model and returns a checksummed artifact. An independent monitor reconstructs policy outcomes from execution events.

Research Lab replays Alibaba GPU workload demand against NESO Great Britain carbon history. It compares posted-offer agents, rolling OR-Tools CP-SAT allocation, and a finite-state pricing-pattern audit. Live jobs and research runs each have downloadable evidence.

The GPU Exchange lets a producer publish a runner and availability window. A consumer requests an expiring quote against an approved SLA and confirms it to reserve the runner. Both organizations receive live booking updates and a shared signed receipt. The consumer's private job and input artifacts remain in its own workspace. The Explainable AI console contains role-specific guides, clickable execution traces, trained Q-tables, pricing interventions, runtime comparisons and paper-ready exports.

## Create a participant account

On the sign-in screen, choose **Create account**. Select **Producer** or **Consumer**, then enter an organization name, username, and password. Signup creates a separate workspace and opens its guide in **Explainable AI**. The first step shows the workspace ID to share with an operator.

Producers can enroll a runner in **Compute capacity** and receive its token once. Consumers can use **Team** to invite a reviewer, who redeems the invitation in a separate session. Approval remains a separate role. Operator CLI provisioning is also available; run the relevant command from the project folder and replace the example IDs.

~~~powershell
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m pact.cli enroll-runner runner-01 "Producer GPU" --org WORKSPACE_ID
& .\.venv\Scripts\python.exe -m pact.cli member reviewer-name reviewer --org WORKSPACE_ID
~~~

## Producer and consumer demonstration

Use separate browser profiles or private windows so each account has its own session. Create local-only demo roles after database initialization. This also provisions reviewed example agreements for both consumers.

~~~powershell
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m pact.cli init
& .\.venv\Scripts\python.exe -m pact.cli market-demo
~~~

1. Open the console as `demo-producer` using the Producer workspace. Use the password in `.local/market-credentials.json`. Open GPU Exchange, choose the enrolled runner and publish capacity.
2. In another browser profile, sign in as `demo-consumer` using the Consumer workspace. Request a quote against the approved image batch agreement, review the maximum charge and confirm.
3. Open Bookings on both sides. Inspect the accepted quote, lease, execution and capacity release step by step. Download the shared receipt. From the consumer's job screen, download the private embedding artifact.
4. In a third profile, use `demo-consumer-2` to demonstrate a concurrent quote. Confirm both quotes against the same slot before it is booked. One request receives the reservation. The other receives the changed-slot response.

For named accounts use `python -m pact.cli member NAME ROLE --org ORGANIZATION` with `PYTHONPATH=backend`. Supply `--org-name` when creating an organization. Supported roles include producer, consumer, reviewer, researcher and operator. A producer's runners belong to its organization. A buyer organization's reviewer approves its agreements. The launch script does not create local demo accounts automatically.

## Open the local console

On the configured Windows machine, run the following from this directory if the services have stopped.

~~~powershell
.\scripts\start.ps1
~~~

Open [PACT-Compute on localhost](http://127.0.0.1:8765). Use username `admin` and the `admin_password` value in `.local/local-credentials.json`. This file also contains private runner and signing credentials. Keep it local.

Use `.\scripts\stop.ps1` to stop the launched processes. Logs are in `.local/logs/`. `-NoGpu` starts the app and worker without the hardware runner. `-SkipImport` starts without importing data. The restricted Codex shell on this Windows host blocks loopback. Run server and browser tests from a normal PowerShell terminal or an approved Codex execution.

### Fresh setup

The validated Windows environment uses Python 3.12.14, Node 24.11.1 and npm 11.6.2. Earlier Python 3.11/3.14 results are historical. Use a short checkout path and the Python 3.12 lock. Run `npm.cmd test` in `frontend` for Node tests. See the [environment manifest](../reports/final-validation/ENVIRONMENT_MANIFEST.md) if Python is not on PATH.

~~~powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade "pip==26.3"
& .\.venv\Scripts\python.exe -m pip install -r requirements-win-py312.lock.txt
Push-Location frontend
npm.cmd ci
npm.cmd run build
Pop-Location
~~~

The API and research worker can run without PyTorch. The default GPU runner uses PyTorch to load and preprocess the pretrained model and the installed NVIDIA driver to execute GPU kernels.

~~~powershell
python -m venv .gpu-venv
& .\.gpu-venv\Scripts\python.exe -m pip install --upgrade "pip==26.3"
& .\.gpu-venv\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-gpu-win-py312.lock.txt
$env:PACT_GPU_PYTHON = (Resolve-Path .\.gpu-venv\Scripts\python.exe).Path
& .\.gpu-venv\Scripts\python.exe backend/pact/gpu_task.py prepare --engine driver
.\scripts\start.ps1
~~~

The prepare command downloads MobileNetV3-Large IMAGENET1K_V2 weights into `.local/torch`, verifies their hash, and compares a GPU embedding against the CPU reference. A machine with an existing CUDA-enabled PyTorch runtime can set `PACT_GPU_PYTHON` and `PACT_GPU_ENGINE=torch` in `.env`. [PyTorch installation](https://pytorch.org/get-started/locally/) · [NVIDIA CUDA Driver API](https://docs.nvidia.com/cuda/cuda-driver-api/)

## Faculty demonstration

1. Open **Agreements**, choose **Load example**, and extract the six rules. Inspect the source spans and approve the revision. The separate example `Jobs must finish by 17:00.` blocks approval because it omits the date and timezone.
2. Open **Submit a job**. Use the four built-in images or upload up to 16 PNG, JPEG, or WebP files. Preview the placement, then submit. Download the 960-dimensional embeddings and signed audit evidence after completion. Each result row carries the corresponding input image hash.
3. Approve a separate agreement requiring 32 GiB VRAM. Preview a job to see the incompatible runner and the clause that prevented admission. Record the rejected request to save it in the audit history.
4. Run **Research Lab** with the imported snapshot and the default strategy mix. Inspect the five-arm comparison, move the market round slider, and open an automaton transition. Download the metrics CSV and evidence JSON. Change the supply pressure or controlled undercuts to test how the auditor responds.
5. Use **Shadow recommendation** on the job form to record a placement recommendation without dispatching or reserving GPU capacity.

## Data and evidence

The default source directory is the adjacent `PACT-Compute-data-preflight` folder. Set `PACT_SOURCE_DIR` if it moves. Import checks SHA-256 against the download manifest and writes canonical Parquet and a data card under `.local/datasets/`. The primary snapshot contains 7,064 GPU pods, 185 successful GPU lifecycle proxies, and 1,344 half-hour GB carbon intervals. The auxiliary legal corpora remain in the source folder for separate experiments. [Alibaba GPU trace](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2023) · [NESO carbon API](https://api.carbonintensity.org.uk/)

Research uses held-out arrivals, modeled runtimes calibrated on earlier successes, scaled arrival gaps, and a shared offer tape across scheduler arms. Rates, supply scenarios, and GPU energy are modeled. The lagged planning signal uses earlier observed intensity. The oracle deliberately uses hindsight. Live energy uses GPU board power samples and reports measurement coverage. Live carbon estimates require a verified grid zone, forecast, and documented power bound. The open live connector supports Great Britain.

Run exports include each seed, the source card, offers, allocations, and audit transitions. The live export includes the tenant's original agreement and execution events. Its HMAC can be verified with this installation's signing secret.

~~~powershell
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m pact.cli verify "C:\path\to\evidence.json"
& .\.venv\Scripts\python.exe -m pact.cli benchmark
~~~

The benchmark writes a 180-example template regression corpus and its report to `.local/evaluations/`. It exercises units, timezones, costs, ambiguity, and unsupported exceptions. Independent human annotation is still needed for a generalization study.

## Connect PostgreSQL

SQLite is the local default and requires no credentials. The app supports PostgreSQL through SQLAlchemy, pg8000, and Alembic. Create a dedicated application login and database. For a self-hosted server, open `psql` as a PostgreSQL administrator and run:

~~~sql
CREATE ROLE pact LOGIN;
\password pact
CREATE DATABASE pact OWNER pact;
~~~

For managed PostgreSQL, create a project and a dedicated database or role in the provider console. Get its direct connection address. Copy `.env.example` to `.env` and set:

~~~dotenv
PACT_DATABASE_URL=postgresql+pg8000://pact:URL_ENCODED_PASSWORD@HOST:5432/pact
PACT_DB_TLS=1
~~~

Use TLS for a hosted server with a trusted certificate. For a local development server without TLS, leave `PACT_DB_TLS` unset. Use this variable instead of a libpq-specific `sslmode` query parameter. Keep the URL in `.env` or a deployment secret store.

~~~powershell
.\scripts\stop.ps1
& .\.venv\Scripts\python.exe -m alembic upgrade head
.\scripts\start.ps1
~~~

The first launch bootstraps an operator account. Existing SQLite jobs and policies remain in SQLite until migrated. `/api/health` reports the active dialect. A live PostgreSQL server is needed to verify connectivity and concurrent locking. [PostgreSQL roles](https://www.postgresql.org/docs/current/sql-createrole.html) · [PostgreSQL databases](https://www.postgresql.org/docs/current/sql-createdatabase.html)

## Optional Groq assistance

Put `GROQ_API_KEY` in the project's `.env` and optionally set `GROQ_MODEL`. Restart the API. The default model is `openai/gpt-oss-20b`. Use **Ask Groq to rank guidance** in Explainable AI to send a question and public step titles. The console's booking and job evidence stays local. Choosing model extraction in Agreements sends the source agreement for that draft only. Every candidate still goes through source verification and review.

The gateway shares its database-backed request budget, single-flight and cooldown across API processes. It caps requests to four per minute and caches successful responses locally for 15 minutes. Invalid, throttled or unavailable responses fall back to local guidance and compilation. Multiple processes still need measured throughput and service supervision. [Groq API reference](https://console.groq.com/docs/api-reference) · [Groq rate limits](https://console.groq.com/docs/rate-limits)

## Reproduce the publication study

~~~powershell
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m pact.cli publication-study --seeds 20 --jobs 90
~~~

The command trains and freezes pricing agents, evaluates the probabilistic FSM on unseen episodes, checks held-out executable contract traces, calibrates a runtime predictor from earlier completed pod observations, and runs paired scheduler replays. Open **Explainable AI → Publication comparisons** for charts and step-by-step inspections. Download `publication-metrics.csv` for aggregate metrics, `publication-seeds.csv` for paired scheduler rows and `publication-study.json` for the full evidence and assumptions. Files are under `.local/evaluations`. See the [research review](RESEARCH_REVIEW.md) and [measured results](RESEARCH_RESULTS.md).

## Verification and deployment

To add a second authorized GPU, enroll it on the control plane with `python -m pact.cli enroll-runner lab-gpu-2 "Lab GPU 2" --rate-cents 250`, using `PYTHONPATH=backend`. The command writes a scoped token in the local state directory. On the GPU host, set `PACT_RUNNER_ID=lab-gpu-2`, `PACT_RUNNER_TOKEN` and `PACT_URL` to the control plane's HTTPS origin, then start `python -m pact.runner` after preparing the model. Assign the grid zone that describes the physical runner. Keep the token in the runner's secret store.

An expired execution lease keeps its capacity reserved until the runner reconciles or an operator confirms the original process stopped. The confirmation and its reason become audit events.

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& .\.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm.cmd run build
npm.cmd run test:e2e
Pop-Location
~~~

The browser tests expect the console and GPU runner on localhost, the local market accounts, and the generated publication study. They verify a live job and its output hash, a rejected placement, a five-arm replay, producer and consumer isolation, a real last-slot race, shared receipts and mobile layout. They save evidence to `.local/verified/`. The API schema is available at `/api/docs` only when `PACT_API_DOCS=1` is set (off by default because it lists every route).

This is a private installation with an enrolled runner. Hosted deployment is recorded in the historical handoff but remains unverified for this local patch. A customer pilot needs authorized capacity, a real queue, a verified grid zone, TLS, secret storage, recovery and retention. OIDC, Kubernetes, paid billing and marketplace settlement remain future integrations. The pricing auditor flags observed patterns for review; commercial outcomes need a customer pilot.
