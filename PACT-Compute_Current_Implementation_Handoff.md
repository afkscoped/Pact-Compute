# PACT-Compute current implementation handoff

Prepared 12 November 2026. This is a new implementation inventory for the next teammate. Read it alongside the companion production plan. Statements about implemented behavior come from the source tree, existing generated artifacts, and the verification completed in this chat. Future work is explicitly identified.

Companion document — [Production and research plan](<C:/Users/raddo/Documents/main el 5th sem/PACT-Compute_Production_and_Research_Plan.md>).

## 1. What the teammate is inheriting

PACT-Compute is a working private GPU exchange with a React frontend, FastAPI backend, PostgreSQL persistence, a research worker, and a native GPU runner. Producers publish capacity. Consumers reserve it under reviewed service agreements. The runner executes an image embedding workload on physical NVIDIA hardware. Both parties can inspect a shared usage receipt, while consumers retain scoped access to their job inputs and outputs.

The same installation contains research experiments for contract monitoring, pricing behavior, finite-state modeling, runtime prediction, and carbon-aware scheduling. The research experiments use controlled market scenarios and public trace-derived demand. The live runner currently executes one approved image workload.

The latest setup connected the configured PostgreSQL service, applied migrations through revision 0002, and verified Groq assistance. Credentials were moved into the local ignored .env and the example file was restored to placeholders. Existing local SQLite data is a separate historical store.

### Recommended reading order

1. This handoff for the implemented system and operating procedures.
2. The companion production plan for proposed work and acceptance criteria.
3. README.md for the existing local workflows.
4. RESEARCH_RESULTS.md and the underlying study artifacts for experimental findings.
5. RESEARCH_REVIEW.md for earlier literature mappings.
6. The original report, slide deck, and earlier roadmaps for project history.

### Documentation reconciliation

| Existing document | How to use it |
| --- | --- |
| PACT_Compute_Project_Report.docx | Original research framing, questions, and methodology. Its simulation-only boundary predates the live runner and exchange. |
| Experiential Learning Phase -1 presentation | Academic presentation material. Update scope and literature before reuse. The literature row for Layer-Condensed KV Cache describes allocation agents, which requires bibliographic correction. |
| PACT-Compute_Implementation_Plan.md | Earlier build plan. Several listed deliverables are implemented. |
| PACT-Compute_Industry_Roadmap.md | Product direction and pilot hypotheses. Its description of the exchange as future work is superseded by current booking functionality. |
| pact-compute/README.md | Operational entry point and current commands. |
| pact-compute/RESEARCH_REVIEW.md | Method adaptations and limitations. Paper versions should be checked against the new plan. |
| pact-compute/RESEARCH_RESULTS.md | Recorded pact-study-2 results with caveats. |
| Dataset download guides | Acquisition instructions. Presence of a guide does not establish that its dataset has been downloaded. |

## 2. Architecture and ownership boundaries

The browser calls /api/v1 endpoints and receives a session cookie. FastAPI checks the authenticated member and scopes private records by organization. SQLAlchemy stores transactional state. Alembic provides database migrations. PostgreSQL is configured for this installation, with SQLite still available as the local default.

The worker leases research runs and performs maintenance. The GPU runner authenticates with an enrolled runner token, reports inventory and heartbeats, claims work, downloads its input, executes the approved template, and reports an outcome. Artifact bytes and experiment files are stored under .local on disk. Database backups alone therefore cannot restore the complete installation.

Groq is an optional suggestion provider. Admission, booking, dispatch, monitoring, and normal instructions have deterministic paths. It is invoked on explicit assistance actions and through optional agreement extraction.

| Component | Main responsibility | Primary files under pact-compute |
| --- | --- | --- |
| Web application | Authentication, navigation, live operations | frontend/src/main.tsx, shared.tsx, operations.tsx |
| Exchange | Offers, quote review, booking details and receipts | frontend/src/exchange.tsx |
| Explanation and research UI | Guides, charts, FSM views, model comparisons | frontend/src/explain.tsx, research.tsx |
| API and access | HTTP routes, roles, session handling, tenant scoping | backend/pact/api.py, access.py, security.py |
| Storage | ORM entities, transactions, artifact metadata | backend/pact/db.py, backend/migrations |
| Contracts | Supported language parsing, validation and optional extraction | backend/pact/policy.py, llm.py |
| Live operations | Admission, capacity, leases, execution updates | backend/pact/live.py, runner.py |
| GPU computation | Image preprocessing, model preparation, kernels | backend/pact/gpu_task.py, cuda_driver.py, mobilenet.ptx |
| Marketplace | Quote and offer versions, booking transactions, shared views | backend/pact/market.py, market_api.py |
| Monitoring | Policy outcomes and event-order validation | backend/pact/audit.py, protocol.py |
| Research | Replay scheduling, pricing agents, runtime prediction | backend/pact/research.py, pricing_model.py, runtime_model.py |
| Study and explanation | Evaluation orchestration, fixtures and explanation API | backend/pact/publication.py, benchmark.py, explain.py |
| Data and grid signals | Hash checks, Parquet snapshots, GB forecasts | backend/pact/datasets.py, carbon.py |
| Model gateway | Request budget, caching, cooldown and fallback | backend/pact/model_gateway.py |
| Operations | Configuration, provisioning, process lifecycle | backend/pact/config.py, cli.py, demo.py, worker.py, scripts |

## 3. Accounts and role behavior

Create account is available on the sign-in screen. Public registration accepts a producer or consumer role, organization name, username, and password. Each registration creates an independent organization and authenticated session in a transaction. Duplicate usernames return a conflict. Usernames follow the same lowercase naming convention used by CLI provisioning. Registration passwords require 12–200 characters. Organization names are trimmed and bounded.

Passwords use salted PBKDF2-HMAC-SHA256 with 350,000 iterations. Session tokens are random, and their digests are stored in the sessions table. Sessions expire after eight hours. Cookies are HttpOnly and SameSite Strict, with Secure controlled by deployment configuration. Sign-out deletes the current session.

The process limits sign-in attempts to 12 per minute per client address and signup attempts to six. These limits are process-local. The browser middleware rejects cross-site writes and imposes a declared upload-size ceiling. Tenant checks and action-specific role checks remain the primary access boundaries.

| Role | Implemented workflow |
| --- | --- |
| Producer | Own runners, capacity publication and pausing, shared bookings and receipts |
| Consumer | Agreement drafting, quotes, bookings, own jobs, cancellation and artifacts |
| Reviewer | Review and approve policies in their organization |
| Researcher | Research and review functions permitted by backend role checks |
| Operator | Authorized operational actions, including reconciliation |
| Submitter | Legacy job submission role in an organization |
| Admin | Administrative actions within the implemented scoping model |

Each member currently has one role and one organization. A shared organization name does not join accounts together. Membership invitations, organization switching, organization-admin screens, password reset, email verification and OIDC are future work. Privileged users are provisioned through the CLI.

After signup, the user enters Explainable AI. Its first step gives the workspace ID and explains the next operational dependency. Producers ask an operator to enroll hardware. Consumers ask an operator to provision a reviewer. This is the largest remaining onboarding gap.

## 4. The complete current transaction

1. An operator enrolls a runner for a producer organization. The runner authenticates and reports hardware readiness.
2. The producer publishes a named availability window and a rate expressed in internal compute credits per GPU-hour.
3. A consumer drafts an agreement. The compiler extracts typed rules and source spans. A reviewer resolves issues and approves a version.
4. The consumer chooses an offer, approved policy, image count or uploaded images, and flexibility preference.
5. The backend creates a short-lived quote if a feasible reservation exists. Quotes normally expire after 90 seconds and do not reserve capacity.
6. Confirmation locks the relevant organizations, rechecks offer and policy terms, checks capacity, and records a booking. Confirmation retries refer to the same quote. Changed input conflicts with an existing booking.
7. The runner claims eligible work under an execution lease. Dispatch checks the current hardware and applicable constraints again.
8. Inputs are hashed, the model executes, output embeddings are validated, and an artifact is stored.
9. The runner reports a terminal result. Capacity is released through recorded events. If execution becomes uncertain, the reservation stays held pending evidence or operator reconciliation.
10. Both parties retrieve the shared receipt. The consumer can inspect private job details and output artifacts. A producer's booking view excludes the consumer's private job reference.

Offer changes have versions. Pausing a listing stops new availability without rewriting a previously accepted booking. The protocol checks accepted terms, attempt identity, state ordering, charge envelope, and evidence completeness.

### State interpretation

The executable monitor moves through initial, quoted, submitted, committed, reserved, dispatched, running, uncertain, terminal, and closed states. Branches handle admission rejection, shadow recommendations, reservation cancellation, expiration, failed dispatch checks, and reconciliation. Its verdict is pass, fail, or incomplete. Missing terminal evidence leaves a trace incomplete.

An observed execution state and a monitor verdict serve different purposes. A successful job can still have a policy finding. The UI exposes both.

### PostgreSQL fixes already made

Organization serialization uses PostgreSQL FOR NO KEY UPDATE semantics through SQLAlchemy. This permits foreign-key references while coordinating scheduling writes. Expiration follows runner ownership, including jobs owned by consumers in other organizations. Maintenance takes a separate transaction per producer organization instead of accumulating locks across all organizations.

Marketplace event queries run in a worker thread so synchronous PostgreSQL I/O does not block the asynchronous stream loop. Clients still use periodic snapshots as a recovery path. Production-scale contention, commit-order event delivery, multi-replica limits and prolonged outages need further tests.

## 5. Agreements and execution constraints

Supported policy kinds include minimum VRAM, GPU count and model, grid zone, relative and absolute deadlines, maximum deferral, charge and hourly-rate limits, carbon limits, lower-carbon preference, and reporting requirements.

The local parser recognizes bounded language patterns, normalizes supported units, and attaches source offsets. Unsupported or ambiguous content becomes a review issue. The example “Jobs must finish by 17:00” requires clarification of date and timezone. Optional model extraction proposes structured rules that undergo source verification and review.

Policies have versions through parent links. Review records preserve decisions and reasons. Approval is a privileged action. The runtime checks the approved policy at admission and dispatch. The independent audit reconstructs outcomes from recorded evidence.

The implementation is a domain-specific policy compiler and event monitor. General contract interpretation, complete temporal-logic synthesis, a deployed TLA+ model checker, arbitrary exception semantics, and a full satisfiability solver remain proposed extensions.

## 6. GPU execution and measurement

The implemented template computes pretrained MobileNetV3-Large image embeddings. It accepts 1–16 images and supports PNG, JPEG and WebP through the existing preprocessing path. Built-in images provide a reproducible smoke workload. Output includes a 960-dimensional normalized vector per image and corresponding input hashes.

The runner supports the custom CUDA Driver API path and a configured PyTorch runtime. Model preparation downloads and checks weights, and the preparation workflow compares a GPU embedding with a CPU reference. Live output validation checks model and backend identity, row identities, vector length, finite values and normalization.

One exclusive GPU is supported per live job. Arbitrary customer containers, multi-GPU distributed training, fractional reservations, checkpoint migration and interactive notebooks are future capabilities.

Live placement currently estimates runtime as 38 + 3 × image count seconds and adds reservation allowances. It enumerates eligible runners and start windows, filters hard constraints, and orders feasible choices by available carbon estimates or start time and price. The research CP-SAT scheduler is a separate implementation. The trained research runtime estimator is also separate from the live fixed formula.

Live power measurement samples GPU board power and records coverage. One preserved verification artifact reports an RTX 4050, four rows, 960 dimensions, approximately 0.0504 seconds of GPU inference, 0.00001257 kWh, and 69% telemetry coverage. Those values describe that recorded run and measurement scope. End-to-end service duration includes preparation and orchestration.

Live carbon estimation requires the runner's actual grid zone, a current forecast and a documented power bound. The open connector supports Great Britain. A runner operating elsewhere needs its own appropriate signal. GPU board energy and whole-facility energy need distinct reporting boundaries.

## 7. Research implementation and observed results

### Data normalization

The importer verifies source hashes against download-manifest.json, checks pod identity across variants, validates time and resource fields, and writes versioned Parquet snapshots and data cards. The fingerprint incorporates schema and input hashes. Invalid source identities or carbon gaps fail validation.

| Local material | Current usage |
| --- | --- |
| Alibaba GPU v2023 pod variants and node CSV | Active normalized demand and inventory inputs |
| NESO October 2025 GB history | Active 1,344 half-hour intervals |
| Daily NESO and regional sample files | Auxiliary downloaded examples |
| CUAD archive | Downloaded, absent from active training and evaluation pipeline |
| ContractNLI archive | Downloaded, absent from active training and evaluation pipeline |
| LEDGAR archive | Downloaded, absent from active training and evaluation pipeline |
| Alibaba GPU v2026 guide | Acquisition instructions only |
| Google Borg 2019 and power guides | Acquisition instructions only |

The active snapshot contains 7,064 GPU pods and 185 successful GPU lifecycle proxies. A proxy is scheduled-to-deleted elapsed time for an eligible successful record. This target can include time beyond GPU computation. Successful-only filtering also limits representativeness.

### Scheduler replay

Research Lab compares FCFS, EDF, a policy ablation, policy-aware scheduling and carbon-aware scheduling. CP-SAT first prioritizes service and then reduces a weighted cost, wait and carbon objective. A bounded candidate batch and rolling horizon control search. Only present-slot decisions are dispatched in the replay. Time-limited solves have fallback behavior.

The current study uses trace-derived arrivals, modeled providers and offers, modeled energy, runtime assumptions and historical GB grid data. Historical values score outcomes after decisions. The deployable planning comparison uses a lagged historical proxy. An oracle condition uses hindsight. Research scarcity and time compression are explicit experimental settings.

### Pricing and finite-state models

The publication study trains two tabular Q-learning sellers over 160 inventory-constrained episodes, then freezes their policies. It evaluates controlled strategy families and held-out trajectories. Interventions compare price cuts and raises with matched sham runs.

The current FSM aggregates bounded contexts based on market pressure and preceding own and rival actions. It merges compatible contexts using next-action frequency distributions, with a minimum support and distance threshold. This is an in-project simplified state-merging method. The external FlexFringe implementation has not been integrated.

Research labels describe configured strategies and controls. The product's observed marketplace does not yet supply independently adjudicated commercial collusion labels.

### Runtime model

The model groups successful lifecycle observations by QoS, GPU-count band and fractional request, estimates empirical upper quantiles, and applies a one-sided calibration residual. Chronological cutoffs restrict available outcomes. Baselines include the training median and training p90.

### Recorded pact-study-2 results

| Measurement | Existing result | Interpretation |
| --- | --- | --- |
| Protocol monitor | 72/72 fixture verdicts, zero unsafe accepts | Controlled fixture coverage |
| Event-presence baseline | 24/72 correct, 48 unsafe accepts | Ordering and identity checks matter on these fixtures |
| Matched pricing detector | F1 1.000 on 120 labelled held-out controlled episodes | Generalization to observed markets remains unmeasured |
| FSM prediction | 79.31% accuracy, 0.548 log loss, 13 states | Majority baseline has 74.94% accuracy and 0.737 log loss |
| Runtime bound | 100% coverage on 46 test proxies | Overly wide bounds and worse pinball loss |
| Calibrated versus median carbon-aware scheduling | Roughly −9 g modeled CO₂ per run, 95% interval −29 to +9 g | Clear improvement is unestablished |
| Carbon-aware versus policy-only within calibrated replay | About 169 g less modeled CO₂ and 27 minutes more p95 wait | Service and emissions trade-off |

The study uses 20 paired scheduling seeds and 90 jobs per seed. Its runtime split has 102 training, 37 calibration and 46 test observations. Reproduce the artifacts before using these numbers in a paper. Preserve unsuccessful experiments and report the scope of each claim.

## 8. Frontend and explainable assistance

The current interface uses React, TypeScript, Lucide icons, Recharts and React Flow, with a dark green theme. It has responsive navigation, hover and focus states, mobile navigation, form feedback and role-filtered navigation.

| Screen | Implemented behavior |
| --- | --- |
| Sign in / Create account | Workspace selection, producer/consumer signup, errors and loading state |
| Overview | Operations summary and links to active work |
| GPU exchange | Capacity filters, availability, publication, quotes and confirmation |
| Bookings | Shared booking projections and detail |
| Job queue / job detail | Submission, placement preview, live/shadow operation, findings, attempts and output |
| Agreements | Example loading, extraction, revisions, source-linked review and approval |
| Compute capacity | Runner inventory and dispatch control |
| Research Lab | Configured replay, progress, comparisons, timeline and exports |
| Data sources | Snapshot cards and import |
| Explainable AI | Role guides, decision traces, Q-tables, interventions, FSM graph, runtime views and publication comparisons |

Shell lists refresh about every 4.2 seconds. Job and run details have faster polling. Exchange uses event-driven invalidation with a periodic fallback. Some data views have bounded record limits rather than full pagination.

Groq currently ranks relevant guide steps and can propose agreement extraction. The default configured model name is openai/gpt-oss-20b. The gateway allows one request in flight, four per minute, caches successful responses for 15 minutes and applies a bounded retry cooldown. Guides use local evidence, and provider failure has a local fallback. These request budgets and caches are local to a process.

The explanation console has detailed deterministic instructions and evidence views. Free-form conversational troubleshooting, a vetted retrieval corpus, support escalation and an evaluation suite for explanation factuality remain future work.

## 9. Storage and operational state

| Entity | Purpose |
| --- | --- |
| Organization / Member | Tenant identity, role and password digest |
| Login | Hashed session token and expiration |
| Policy | Source text, hash, rules, issues, approval and revision lineage |
| Runner | Ownership, identity, token digest, hardware, rate and heartbeat |
| Job | Approved policy, request identity, reservation decision and status |
| Attempt | Execution lease, fence, status, times and reported result |
| CapacityOffer | Producer window, rate, status and version |
| MarketQuote | Consumer request, selected capacity, pinned terms and expiry |
| MarketBooking | Accepted quote and both organizations |
| Artifact | Content hash and ownership metadata for disk-stored bytes |
| ResearchRun | Configuration, progress, lease and result |
| Event | Ordered evidence records for entities |
| FindingReview | Human review disposition and explanation |

Content hashes support integrity checks. Receipts and evidence use an installation HMAC secret. HMAC verification depends on access to that shared secret. Public-key verification, independently retained evidence and tamper-evident external storage are proposed production additions.

### Configuration and private state

Use .env for PACT_DATABASE_URL, PACT_DB_TLS, GROQ_API_KEY and optional provider settings. PACT_URL declares the public origin. PACT_SECURE_COOKIE controls secure cookies. PACT_STATE_DIR and PACT_SOURCE_DIR control local storage. Runner options include its identity, token, grid zone, runtime engine and power bound.

The .local directory includes database history, credentials, artifacts, dataset snapshots, trained-study outputs, runner state, model cache and logs. Share credentials through a private handoff channel. Documentation and screenshots should contain configuration names and placeholders.

## 10. Teammate operating guide

Run commands from the pact-compute project directory. The existing environment is Windows with Python 3.14 and Node.js 24. Dependency portability should be checked on a clean machine before packaging deployment.

~~~powershell
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m pact.cli init
& .\.venv\Scripts\python.exe -m pact.cli import
Push-Location frontend
npm.cmd run build
Pop-Location
.\scripts\start.ps1 -SkipImport
~~~

When services already run, use scripts/stop.ps1 before restarting. The scripts track owned processes and logs. The usual local URL is http://127.0.0.1:8765 and the health endpoint is /api/health. Interactive API documentation is /api/docs.

Use pact.cli market-demo for local producer, consumer and reviewer accounts. Credentials are stored in .local/market-credentials.json. The bootstrap admin password is in .local/local-credentials.json. Demo provisioning is intended for the localhost installation.

For named memberships use pact.cli member NAME ROLE --org ORGANIZATION. Supply --org-name for a new organization. For hardware use pact.cli enroll-runner RUNNER_ID NAME --org ORGANIZATION. Configure the resulting token privately on its GPU host and run pact.runner. Independently enrolled processes require distinct physical capacity assignments.

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& .\.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm.cmd run test:e2e
Pop-Location
& .\.venv\Scripts\python.exe -m pact.cli benchmark
& .\.venv\Scripts\python.exe -m pact.cli publication-study --seeds 20 --jobs 90
~~~

The browser suite expects local demo accounts, a prepared GPU runner and generated publication artifacts. This workstation required normal Windows permissions for loopback and remote database verification. In the last implementation pass all eight backend tests passed. Both browser scenarios passed after fixes, with final reruns performed separately. Browser signup checks additionally exercised both roles, duplicate usernames, session persistence, mobile layout, sign-out and sign-in. A live Groq guide-ranking request succeeded.

Those checks validate specific workflows on this installation. Load, long-duration reliability, backup recovery, regional failover and public deployment have not been demonstrated.

### Troubleshooting map

| Symptom | First checks and response |
| --- | --- |
| Database unavailable | Read health and API error logs, confirm environment variable names, TLS and network access |
| Empty producer inventory | Confirm organization ownership, enrollment, token and runner heartbeat |
| Consumer cannot quote | Confirm approved policy in that consumer organization, eligible offer and fresh inventory |
| Booking remains uncertain | Inspect lease and runner process evidence before releasing capacity |
| Groq unavailable | Check configuration and request cooldown, use local guide while provider recovers |
| Missing outputs after database restore | Restore matching artifact storage and verify hashes |
| Study panel unavailable | Generate publication study and check .local/evaluations |
| API view loads slowly | Inspect PostgreSQL round trips, repeated polling, query count and event-stream behavior |

## 11. Work remaining

The next production phase needs self-service organization membership and onboarding, workload packaging and isolation, multiple real hosts, reliable live event delivery, measured runtime prediction, pagination and query tuning, shared request limits, recoverable artifact storage, service supervision, monitoring and restore drills.

Commercial billing requires a ledger, agreed pricing units, reconciliation and adjustments. Current credits and receipts provide usage evidence. Provider payouts and payment processing are future work.

Research needs broader traces, independent agreement labels, explicit censored-runtime treatment, external FSM baselines, stronger uncertainty evaluation and actual partner workloads. The companion plan defines the implementation sequence and measurable release gates.

## Appendix A. Current API inventory

Generated from the route decorators in the reviewed source. Private routes apply session authentication and their relevant tenant and role checks. Runner routes use runner authentication.

| Method | Path | Handler |
| --- | --- | --- |
| GET | /api/health | api.py / health |
| POST | /api/v1/accounts | api.py / register |
| POST | /api/v1/session | api.py / login |
| GET | /api/v1/session | api.py / whoami |
| DELETE | /api/v1/session | api.py / logout |
| GET | /api/v1/config | api.py / capabilities |
| GET | /api/v1/policies | api.py / policies |
| POST | /api/v1/policies | api.py / create_policy |
| GET | /api/v1/policies/{policy_id} | api.py / policy_detail |
| POST | /api/v1/policies/{policy_id}/revisions | api.py / revision |
| POST | /api/v1/policies/{policy_id}/approve | api.py / approve |
| GET | /api/v1/runners | api.py / runners |
| PATCH | /api/v1/runners/{runner_id}/dispatch | api.py / pause |
| GET | /api/v1/jobs | api.py / jobs |
| POST | /api/v1/jobs/preview | api.py / preview_job |
| POST | /api/v1/jobs | api.py / submit_job |
| GET | /api/v1/jobs/{job_id} | api.py / job_detail |
| POST | /api/v1/jobs/{job_id}/cancel | api.py / cancel |
| POST | /api/v1/jobs/{job_id}/reconcile | api.py / reconcile |
| POST | /api/v1/runners/{runner_id}/heartbeat | api.py / heartbeat |
| POST | /api/v1/runners/{runner_id}/claim | api.py / claim |
| GET | /api/v1/runners/{runner_id}/attempts/{attempt_id}/input | api.py / input_manifest |
| POST | /api/v1/runners/{runner_id}/attempts/{attempt_id}/events | api.py / attempt_events |
| GET | /api/v1/artifacts/{artifact_id} | api.py / artifact |
| GET | /api/v1/datasets | api.py / dataset_list |
| POST | /api/v1/datasets/import | api.py / dataset_import |
| GET | /api/v1/runs | api.py / runs |
| POST | /api/v1/runs | api.py / start_run |
| GET | /api/v1/runs/{run_id} | api.py / run_detail |
| GET | /api/v1/runs/{run_id}/metrics.csv | api.py / metrics_csv |
| POST | /api/v1/{kind}/{object_id}/reviews | api.py / review |
| GET | /api/v1/jobs/{job_id}/evidence.json | api.py / job_export |
| GET | /api/v1/{kind}/{object_id}/events | api.py / event_stream |
| GET | /{path:path} | api.py / frontend |
| GET | /api/v1/market/offers | market_api.py / offer_list |
| POST | /api/v1/market/offers | market_api.py / publish |
| PATCH | /api/v1/market/offers/{offer_id} | market_api.py / offer_status |
| POST | /api/v1/market/quotes | market_api.py / quote |
| POST | /api/v1/market/quotes/{quote_id}/confirm | market_api.py / confirm |
| GET | /api/v1/market/bookings | market_api.py / booking_list |
| GET | /api/v1/market/bookings/{booking_id} | market_api.py / booking_details |
| GET | /api/v1/market/bookings/{booking_id}/receipt | market_api.py / receipt |
| GET | /api/v1/market/events | market_api.py / events |
| POST | /api/v1/explain/answer | explain.py / answer |
| GET | /api/v1/explain/options | explain.py / options |
| GET | /api/v1/explain/study | explain.py / study |
| GET | /api/v1/explain/study/download/{name} | explain.py / download |

## Appendix B. Persisted fields

Generated from ORM declarations. Relationships use stored IDs. Nullability, constraints and defaults are defined in db.py and migrations.

| Entity | Fields |
| --- | --- |
| Organization | id, name |
| Member | id, org_id, username, password, role |
| Login | digest, member_id, expires |
| Policy | id, org_id, parent_id, title, source, source_hash, rules, issues, method, status, created_at, approved_at, approved_by |
| Runner | id, org_id, name, token_digest, device, vram_mib, ready, zone, rate_cents, last_seen, dispatch_paused |
| Job | id, org_id, policy_id, submitted_by, runner_id, request_key, title, mode, status, spec, decision, created_at, start_after, deadline_at, cancel_requested |
| Attempt | id, job_id, runner_id, ordinal, fence, status, lease_until, started_at, finished_at, result |
| CapacityOffer | id, org_id, runner_id, title, starts_at, ends_at, rate_cents, status, version, created_at |
| MarketQuote | id, org_id, offer_id, consumer_id, offer_version, policy_id, spec, selection, issued_at, expires_at |
| MarketBooking | id, quote_id, offer_id, consumer_org_id, producer_org_id, job_id, accepted_at |
| Artifact | id, org_id, job_id, filename, kind, digest, size, created_at |
| ResearchRun | id, org_id, created_by, config, result, status, progress, created_at, finished_at, lease_until, worker, error, artifact_id |
| Event | seq, org_id, entity_type, entity_id, kind, details, at |
| FindingReview | id, org_id, member_id, entity_type, entity_id, finding_id, disposition, note, at |

## Appendix C. Dataset files and integrity

Hashes below were recomputed during this documentation pass and compared with the existing download manifest. Active import status is described in section 7.

| File | Bytes | SHA-256 | Manifest match |
| --- | --- | --- | --- |
| openb_pod_list_default.csv | 575468 | 1ee7ed79c27a3b0861cda8ddba86a004c6aba904caafa329a76ae93ca63834a8 | True |
| openb_pod_list_gpuspec33.csv | 587467 | eca4f746db1e5b25864ad021b55ece3943e101a3ebd4574d09dcb95c46117652 | True |
| openb_node_list_gpu_node.csv | 42353 | 2beca64b4d3dfa342036a34b56a495c6cef9225db836c81f541282cb1df320b5 | True |
| neso_gb_2025-10-01_to_2025-10-29.json | 149523 | 3a87023bfc80685a03018a17c10c3abf85eaf774f09097c8b624e606fe771ef1 | True |
| neso_gb_2025-10-01_daily.json | 8502 | 1781b4c7bb3d345cf6f689adec2993c27f324b07896ed51d6c2af540a2344f81 | True |
| neso_regional_forecast_sample.json | 7407 | 5a998f8c190cedf9999e9a23d34f16655076d3d9342bd63c9c1aa53dddc77181 | True |
| cuad_data.zip | 18309308 | f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a | True |
| lexglue-ledgar.tar.gz | 16255623 | f7507bcce46ce03e3e91b8aaa1b84ddf6e8f1d628c0d7fa351f97ce45366d5d8 | True |
| alibaba-gpu-v2026-download-guide.md | 1939 | 69e3db5f6219eb9c457d4f3718d203f974027a2ad96d68f6ef4d446ece960704 | True |
| google-power-data-2019-guide.md | 1843 | a00c9d4cd97171b3bbee8641028a3b719a1ff4daad95d69b2a659df54fd2cd49 | True |
| google-borg-cluster-data-2019-guide.md | 2323 | 6209413ba5dc94e45b9dda811871b7eab406980aab5279466fa9eb48578ff6e3 | True |
| contract-nli.zip | 65362913 | e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b | True |
