# PACT-Compute production and research plan

Prepared 12 November 2026 for teammate handoff. Read the companion current implementation inventory first. Everything described as a target, proposal or gate below is future work. Research sources were checked against primary paper pages, author releases and official documentation available on this date. This is a focused technical review, with reproducibility checks still required for each external implementation.

Companion document — [Current implementation handoff](<C:/Users/raddo/Documents/main el 5th sem/PACT-Compute_Current_Implementation_Handoff.md>).

## 1. Product outcome and first market

Build a private GPU exchange for a university consortium, research park or small enterprise with idle capacity distributed across teams. Start with two independently operated physical GPU hosts and several consumer teams running approved batch inference or embedding workloads. This is a proposed first customer segment, to validate through interviews and a pilot.

The complete customer outcome is a successful workload with an understood price, declared service constraints, accessible output, and an explainable usage record. Producers need trustworthy reservations, visibility into occupied capacity and controlled maintenance. Operators need tools to recover failures. Researchers need reproducible experiments whose assumptions are visible.

Keep a single backend application with well-defined modules through the pilot. Extend PostgreSQL, add durable object storage, and deploy supervised API, worker and runner processes. Introduce additional services when a measured operational requirement justifies them.

### Pilot charter

| Decision | Initial proposal | Evidence needed to revise it |
| --- | --- | --- |
| Customer | Private research and computer-vision teams | Interviews with at least two pool owners and five users |
| Workload | Approved batch inference and embeddings | Repeated jobs from consenting teams |
| Capacity | Two or more physical hosts, at least two hardware profiles | Measured compatibility and runtime differences |
| Money | Internal credit accounting during pilot | Reconciled usage and willingness to pay |
| Supply | Producer-posted rates and availability | Actual utilization and accepted quotes |
| Geographic scope | Verified physical regions | Appropriate grid signals for each location |
| Expansion | A second workload template, then managed external capacity | Stable operation and demand beyond initial template |

The research contribution should be tested as a connected system. A promising hypothesis is that source-grounded policies, uncertainty-aware scheduling and replayable evidence improve service reliability while exposing cost and carbon trade-offs. Novelty requires a separate comparison with prior systems and measured results.

## 2. Target user journeys

### Consumer

1. Create an account or accept an organization invitation. Verify identity through the configured identity service.
2. Enter a workspace showing jobs, usable credits, current restrictions and one clear next action.
3. Choose an approved workload template and supply a small test dataset or an authorized object-storage reference.
4. Set deadline, maximum spend, data-region restrictions and flexibility through a guided form. Show the corresponding agreement clauses alongside these controls.
5. Reuse a reviewed organization policy or submit changes to the review inbox. Ordinary jobs within an approved template proceed without repeating the same review.
6. Compare eligible offers with GPU compatibility, earliest start, predicted completion range, total estimate, charge cap, cancellation terms and data-transfer scope.
7. Confirm once. Show the accepted booking immediately, with a stable ID and an explicit response if capacity changed.
8. Follow staging, execution, validation and delivery. Show failure reasons and recovery choices when needed.
9. Retrieve outputs, inspect the usage receipt, and request an adjustment through a scoped incident workflow.

### Producer

Create a producer workspace, enroll an owned host using a short-lived installation token, run an automatic hardware verification job, and publish capacity after readiness checks pass. Inventory shows device identity, memory, supported workload templates, last verification, availability, reservations and maintenance windows.

Separate operational availability from advertised availability. A missing heartbeat makes new capacity temporarily unavailable. Existing commitments enter recovery handling. Producers can pause new bookings and schedule maintenance with a preview of affected reservations.

The first production runner installer should validate driver compatibility, disk, network, artifact access, model digest and a known-output workload. Ownership verification is a platform check with recorded evidence. It should not be represented as a hardware attestation guarantee without the appropriate mechanism.

### Organization administrator and reviewer

Introduce invitations, memberships, scoped roles and organization switching. A person can own a personal workspace and belong to a shared lab. The administrator sets budgets, workload templates and review rules. Reviewers see clauses, parsed values, unresolved questions, proposed changes and affected future jobs in one screen.

Create approval policies for routine versus exceptional workloads. A reviewed standard template can cover repeated jobs. Changes to maximum spend, jurisdiction, workload type or material service terms can trigger review. Store the policy version used by every accepted job.

### Operator

Provide an incident queue for stale runners, incomplete uploads, lease loss, budget conflicts, failed outputs and adjustment requests. Each incident has an owner, relevant evidence, permissible actions and recorded resolution. Operators should be able to replay the incident without manually reading unrelated logs.

## 3. Situation-based acceptance scenarios

| Situation | Expected platform behavior | Evidence to retain |
| --- | --- | --- |
| Two buyers confirm the final slot | One atomic reservation, a clear capacity-changed response for the other | Transaction IDs, request keys and inventory version |
| Client retries after a timeout | The same accepted operation is returned | Idempotency key and request fingerprint |
| Runner disconnects during a job | Hold uncertain capacity and present recovery status | Lease, last heartbeat, process identity and fence |
| Old runner reconnects after recovery | Reject obsolete execution authority | Current fence and rejected event |
| Producer pauses a listing | Block new quotes and show existing commitments | Offer version and accepted quote |
| Job exceeds prediction | Enforce agreed timeout or authorized extension, preserve partial evidence | Prediction version, elapsed time and decision |
| Consumer cancels during upload | Stop staging and release applicable holds | Cancellation acknowledgement and storage cleanup |
| Consumer cancels during execution | Request stop, wait for evidence, account for executed usage | Runner acknowledgement and final meter record |
| Grid data becomes stale | Show freshness and apply the declared missing-signal policy | Retrieval time, forecast version and decision reason |
| Groq is throttled | Continue local guidance and show provider status | Provider outcome and local guide version |
| Output upload fails | Retry content-addressed transfer while retaining execution state | Manifest hash, transfer attempts and validation |
| Database restarts | Recover pending work and replay undelivered notifications | Durable job state and outbox entries |
| A disputed charge appears | Freeze disputed settlement and record an adjustment decision | Original receipt, meter scope and ledger entries |
| User switches organizations | Update all scoped views and caches | Membership context and authorization result |
| Workload or region is unsupported | Explain the failing requirement and feasible choices | Constraint IDs and rejected candidate facts |
| No current offers match | Offer bounded resubmission or queueing with user consent | Constraints and expiration of request |

Build deterministic fault-injection cases for these scenarios before widening public access. Retrying a database transaction requires an idempotent operation and a fresh transaction. A physical GPU execution needs fencing and reconciliation because a retried network request can outlive its original worker.

## 4. Production backend and deployment

### Identity and tenancy

Add organization memberships, invitations, account recovery, session revocation and a scoped service-account model. Use an established OIDC integration when the pilot organization has an identity provider. Keep self-registration configurable for the installation. Validate tenant boundaries at every endpoint and background task, including artifact downloads and event streams.

Add a tenant-aware authorization matrix to the test suite. Test direct API requests from the wrong tenant, stale memberships and users with multiple roles. Public signup grants participant permissions. Privileged role assignment belongs to the authorized organization or platform administrator.

### Transaction integrity and event delivery

Write business mutations and outbox events in one PostgreSQL transaction. A dispatcher publishes committed events with durable delivery progress. Consumers acknowledge or deduplicate by event ID and entity version. Reconnecting browsers receive a scoped snapshot plus subsequent events.

Global sequence numbers can be allocated before transactions commit. Design event cursors and reconciliation to handle visibility order and gaps. Verify that a late commit cannot permanently hide an offer update. Keep bounded periodic reconciliation even after event delivery improves.

Move admission toward explicit reservation records with resource identifiers, intervals, ownership and version checks. Benchmark lock contention before replacing organization-level locking. Add database constraints where expressible and property tests for aggregate capacity and budgets. Introduce bounded retries for retriable database errors, retaining the accepted-operation identity.

### Workload execution

Define a versioned workload specification with template ID, immutable image/model digest, input manifest, hardware requirements, region, timeout, output schema and retry permissions. Add a second real template only after its runtime and isolation behavior are measured.

Use supervised container execution on controlled Linux GPU hosts for the next pilot runner. Restrict privileges, mounts and network access according to the workload template. Record startup, data staging, compute, validation and upload durations separately. Preserve checkpoints only for workloads that support reliable restart semantics.

For Kubernetes partners, implement an adapter mapping PACT admission to Kueue Workloads and quotas. Define which component owns the reservation and which owns cluster placement to avoid two schedulers making conflicting decisions. NVIDIA GPU Operator provides a supported path for GPU-related cluster components, with hardware-specific feature validation. [Kueue overview](https://kueue.sigs.k8s.io/docs/overview/) · [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html)

### Persistence, secrets and recoverability

Store artifacts and checkpoints in object storage with per-tenant access, content hashes, retention and deletion policies. Upload to temporary keys, validate the manifest, then publish availability. Test recovery from a database snapshot together with matching artifact versions.

Move signing and runner credentials into a deployment secret store. Implement runner-token rotation and revocation. Use TLS for public ingress, secure cookies and explicitly configured origins. Add public-key signatures if receipts must be verified independently by both parties without sharing the signing secret.

Add shared rate limits and model-request budgets before running multiple API replicas. Give migrations a dedicated release step and validate rollback or forward recovery. Test upgrades against a copy of representative prior data.

### Accounting and commercial readiness

Create an append-only usage ledger with reservation holds, metered usage, release, adjustment and refund entries. Define rounding, time boundaries, startup charges, transfer charges and failed-job treatment. Reconcile ledger entries to signed meter records and external invoices where applicable.

Start with internal chargeback. Add payment collection and producer payouts after billing semantics and customer requirements are agreed. Provider API access, commercial contracts and spending authority are explicit prerequisites for paid external-capacity experiments.

### Performance and observability

Instrument request, database, booking and runner spans with shared correlation IDs. Track quote latency, lock waits, worker lag, heartbeat freshness, failed dispatches, event delivery age, artifact failures and meter coverage. Build an operator dashboard and actionable alerts. OpenTelemetry supplies the standard signal and context model. [OpenTelemetry observability guide](https://opentelemetry.io/docs/concepts/observability-primer/)

Profile and eliminate repeated database round trips in offer lists and booking detail. Add pagination and scoped incremental refresh. Validate indexes against representative query plans. Co-locate the API and database where feasible, and report network latency as part of performance measurements.

## 5. Real-data program

### Priority and acquisition plan

| Priority | Source | Purpose and acquisition work | Important limitation |
| --- | --- | --- | --- |
| P0 | Existing Alibaba GPU v2023 snapshot | Preserve as a fixed regression baseline and rerun current results | Only 185 usable successful lifecycle proxies |
| P0 | Consenting pilot runners | Collect actual stage timing, queueing, failures, GPU metrics and outputs | Requires partner workloads and collection agreement |
| P1 | Alibaba GPU v2026 | Acquire source manifest, schema and selected tables, then validate representative windows before expanding | Large archives and uneven joins need explicit profiling |
| P1 | Helios | Add a second organization and cluster family for held-out evaluation | Align job and resource semantics before comparison |
| P1 | Philly | Add multi-attempt and failure-aware workload analysis | Older hardware and workload mix |
| P1 | Region-correct grid series and forecast vintages | Record issued-at and valid-at times, units and coverage | Historical actual values cannot substitute for information available at scheduling time |
| P1 | Reviewed pilot SLAs | Independently label clauses and executable outcomes | Consent, confidentiality and annotation cost |
| P2 | CUAD, ContractNLI and LEDGAR already downloaded | Build adapters for clause extraction, evidence and entailment experiments | Their labels require a documented mapping to GPU SLA tasks |
| P2 | Google Borg and power traces | Test general queueing and aggregate power hypotheses through bounded queries | Aggregate measurements have a different scope from per-GPU energy |

Alibaba's 2026 release describes about six months of heterogeneous production behavior. The repository provides schemas and download instructions. First reproduce basic counts and join coverage on the chosen window, then expand. A public issue reports uneven job-summary coverage across days, so independent coverage checks are an ingestion gate. The issue is a lead to investigate. [Official trace](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2026) · [OSDI 2026 paper](https://www.usenix.org/conference/osdi26/presentation/li-suyi) · [Reported coverage issue](https://github.com/alibaba/clusterdata/issues/259)

Helios provides traces from four GPU clusters and offers useful cross-cluster evaluation. Philly includes job attempts and a published parsing example. Acquire the documented releases with a pinned revision and content hashes. Inspect licenses and redistribution terms for the intended artifact release. [Helios release](https://github.com/S-Lab-System-Group/HeliosData) · [Philly release](https://github.com/msr-fiddle/philly-traces)

Google's 2019 cluster trace is available through BigQuery and is large enough to require bounded queries. The local download guides describe the access workflow. Export a reproducible query and its result manifest, with a byte-scan cap. Use its power-domain data only at the measurement granularity documented by the release. [Google trace repository](https://github.com/google/cluster-data)

### Ingestion procedure

1. Register source URL, version, retrieval time, owner, access terms, schema and expected archive size.
2. Check storage and memory requirements. Use resumable downloads into staging and validate checksums before extraction.
3. Inspect archive paths and extract within a dedicated dataset root. Record decompressed size.
4. Normalize source identifiers, clock basis, time units, GPU requests, placements and outcomes without fabricating missing observations.
5. Produce counts, duplicate rates, missingness, join coverage and time coverage by day and cluster.
6. Keep failed and right-censored jobs with explicit labels. Distinguish queue wait, startup, active compute and lifecycle time where observed.
7. Write partitioned Parquet and a data card containing transformations and exclusions.
8. Publish frozen train, calibration and test manifests. Keep related jobs and repeated attempts together where needed to avoid leakage.
9. Run adapter regression checks and reproduce selected source-paper summaries before training.

The new large archives are proposed acquisitions. This documentation task did not download them. The existing preflight folder holds three legal archives, the v2023 trace files, NESO files and acquisition guides.

### Canonical observation contract

Every record should carry source ID, dataset version, tenant pseudonym where applicable, job and attempt IDs, workload class, hardware profile, requested resources, observed allocation, region, submitted/start/finish times, terminal state, censoring status and timestamp semantics.

Store prediction-time features separately from outcomes. Record price and offer history only where observed or explicitly generated by an experiment. Public cluster workload logs generally do not identify buyer valuations, negotiated rates or collusive intent.

Telemetry records need sample timestamp, unit, device identity, sample quality, collection interval and scope. Grid records need region, signal type, publication time, validity interval and revision. Keep observed, inferred and synthetic fields distinguishable in both schema and UI.

### Proposed pilot collection

Collect four weeks of observations across at least two physical hosts. Target at least 1,000 task executions covering image count, resolution, model variant, hardware and repeated time periods. The sample target is a planning assumption and should be revised after a power and variance analysis. Include unsuccessful runs and warm/cold starts.

Retain consented operational metadata and checksums with a configurable retention policy. Keep private payloads in the tenant's storage. Train runtime models on completed earlier observations and evaluate on later weeks and held-out hardware where feasible.

## 6. Contract-to-protocol research

### Research basis

nl2spec links formal subexpressions back to source fragments and supports iterative correction. Adopt that interaction pattern in the reviewer screen. TLA+-Bench, released in July 2026, emphasizes execution-grounded specification evaluation and how grading choices affect measured correctness. Adopt explicit properties, bounded model-checker configurations and published scoring rules. [nl2spec](https://arxiv.org/abs/2303.04864) · [TLA+-Bench v1](https://arxiv.org/html/2607.23425v1)

### Proposed method

Build a typed intermediate representation containing actor, action, condition, quantity, unit, temporal scope, exception, evidence span and confidence or abstention reason. Keep deterministic parsing for supported common clauses. Use optional constrained model extraction for proposals and run every proposal through type, unit, source and contradiction checks.

Add explicit temporal semantics for deadlines, cancellation acknowledgement, lease expiry, reservations, retry authorization and capacity release. Define which clauses are enforceable before execution, during execution, or only auditable afterward.

For the booking protocol, build a bounded TLA+ model covering two consumers, one capacity resource, quote expiry, lease loss and retry. Specify invariants such as exclusive reservation, authorized spend and obsolete-fence rejection. State fairness assumptions for liveness and publish explored bounds. Turn counterexamples into application-level regression cases.

Run the source-linked reviewer before activating an ambiguous policy. Show a minimal contradictory set when constraints conflict. A natural-language explanation should point to the exact clause and failing property.

### Evaluation

Propose an initial independently labelled corpus of 300–500 short service agreements, including paraphrases, units, exceptions, ambiguity and contradictory obligations. Have two annotators label a subset and adjudicate disagreement. Split by document family or source organization.

Compare deterministic extraction, direct structured extraction, source-grounded extraction with validation, and human-reviewed output. Hold model and request budget fixed within comparisons. Measure field F1, source-span accuracy, unsupported-rule rate, abstention, review time and executable verdict correctness.

For temporal monitoring, compare the current presence baseline, current monitor and model-derived checks on held-out valid, invalid and incomplete traces. Include duplicate, delayed and reordered events. Report false acceptance and incomplete-evidence rates with denominators. A perfect fixture score needs independent tests before supporting generalization.

Deliver a clause handbook, labelled corpus, annotation protocol, versioned policy schema, executable model, counterexample viewer and reproducible evaluation report.

## 7. Runtime prediction and sustainable scheduling

### Research basis and adaptation

Flex was revised in October 2026 and describes coordinated provisioning and scheduling guided by recent workload history and grid conditions. Its learned provisioning approach is an additional baseline to reproduce after workload elasticity exists. The current rolling solver is an independent in-project implementation. [Flex v2](https://arxiv.org/html/2505.18357v2)

CarbonScaler motivates measuring how workload progress changes with resource allocation. Introduce elasticity only after obtaining workload-specific scaling curves and checkpoint costs. [CarbonScaler](https://arxiv.org/abs/2302.08681)

Conformalized quantile regression combines conditional quantile prediction with residual calibration. It motivates replacing the current coarse grouped upper bound with a richer predictor and evaluating interval efficiency. Chronological drift and heterogeneous hardware require empirical coverage checks alongside the method's exchangeability assumptions. [Conformalized Quantile Regression](https://proceedings.neurips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html)

### Runtime program

1. Change the live measurement target to separately measured staging, startup, compute and upload durations.
2. Fit hardware/workload medians and simple linear models as inexpensive baselines.
3. Compare quantile gradient-boosted models using input size, template, model version, hardware and available pre-dispatch features.
4. Add calibration on a distinct later window and test coverage and width on a subsequent window.
5. Evaluate survival methods when cancelled or timed-out jobs materially censor the target.
6. Store model version, feature snapshot, quantiles and fallback reason with every scheduling decision.
7. Trigger conservative fallback on insufficient support, stale calibration or unseen hardware.

The current bound achieved high coverage with poor efficiency on a small sample. Promotion should require improved pinball loss and useful interval width at comparable empirical coverage, plus no unacceptable increase in missed deadlines. Report per-hardware and per-workload slices.

### Scheduler design

Create one reusable feasibility representation for live decisions and replay. It should express policy constraints, device capacity, time intervals, budgets and workload compatibility. Keep algorithm choice behind this representation so experiments compare decision policies under the same constraints.

Use a rolling horizon. First maximize feasible admitted service subject to policy and capacity. Then optimize normalized cost, estimated carbon and waiting, with aging or fairness constraints. Report solver status, bounds where available, solve time and fallback rate. Weighted preferences must be visible and normalized so units do not determine outcomes accidentally.

Estimate emissions by integrating power over time and applying the region-appropriate intensity for each interval. Account separately for board, host and facility scope. When intensity is measured in grams per kWh, compute energy in kWh before multiplication. Model transfer and startup overhead when comparing providers.

Use upper runtime quantiles for reservations, and evaluate risk tolerances through scenario-based uncertainty experiments. A statistical coverage target is an empirical scheduling input whose reliability must be measured under drift. Keep hard policy and physical capacity checks deterministic.

Add EASY-style conservative backfilling and EDF with aging as strong practical baselines. Evaluate fragmentation-aware placement on compatible multi-GPU traces, then gang scheduling only after real multi-GPU execution exists.

### Comparison design

Use the same arrivals, resource inventory, forecast vintages, job requirements and random seeds for each arm. Include FCFS, EDF, backfilling, cost-aware scheduling, policy-only CP-SAT, carbon-aware CP-SAT, uncertainty-aware scheduling and an explicitly labelled hindsight reference.

Factor the experiment into runtime model, admission policy and scheduling objective. Compare median versus calibrated duration with and without backfilling to identify where gains originate. Evaluate native trace scale and separately disclosed contention scenarios.

Report admitted fraction, completed fraction, on-time completion, p50/p95 queue wait, bounded slowdown, throughput, utilization, fragmentation, fairness, cost, energy and emissions. Include total emissions and emissions per successfully completed job. Capture jobs rejected or unfinished at the evaluation boundary.

Promote from replay to shadow recommendation, then a limited live canary, then broader traffic after service gates pass. A carbon improvement accompanied by unacceptable service degradation fails the pilot gate.

## 8. Pricing behavior and automata research

### Research basis

FlexFringe provides probabilistic automata learning through state merging, with a 2025 revision. Reproduce an external state-merging baseline alongside the current bounded-context merger. [FlexFringe](https://arxiv.org/abs/2203.16331)

Deng, Schiffer and Bichler's 2025 study broadens the analysis beyond tabular Q-learning and examines how learning algorithms affect pricing outcomes. Use heterogeneous agent families and sensitivity tests rather than assuming one learner represents all providers. [Pricing study](https://arxiv.org/abs/2503.11270)

The October 2026 revision of Algorithmic Collusion Without Deterrence examines frozen policies, directional interventions, re-matched agents and profitable deviations. Extend PACT's existing cut/raise/sham experiment with re-pairing and best-response evaluation in the bounded research environment. These tests examine mechanisms that a price-response motif alone leaves unresolved. [Mechanism audit](https://arxiv.org/html/2610.21867v2)

### Proposed method

Record demand, supply, workload mix, hardware quality, availability, costs where actually known, posted offers and realized allocations. Define price actions relative to an explicit time interval and comparable hardware class.

Build three separate outputs for evaluation. Predict the provider's next observed action. Summarize recurrent behavior with a compact state machine. Flag trajectories that warrant human review using declared criteria and uncertainty. Each output needs its own metrics and ground truth.

Train and freeze tabular agents, simple competitive heuristics, fixed premiums and scarcity-sensitive controls. Add one deep-RL family only after the baseline training and evaluation pipeline is repeatable. Split training seeds, FSM fitting, threshold calibration and final testing.

Compare majority action, first-order Markov prediction, the existing merger and an external probabilistic automata learner. Select complexity by held-out log loss and coverage. Show support on every state and edge, with an explicit unknown state for unsupported contexts.

For controlled mechanism tests, compare cuts, raises and sham shocks under identical demand and capacity. Re-match frozen agents from independent training runs. Compute a bounded best response against a frozen opponent when the model permits it. Record profit consequences, recurrence, recovery time and sensitivity to demand shocks.

In the live exchange, produce review leads from observations. Label uncertainty and alternative explanations such as scarcity, cost changes and hardware mix. Price interventions belong to controlled research or a separately consented experiment.

### Evaluation and deliverables

Report held-out log loss, action accuracy, state coverage, calibration, state count and transition support. For labelled controlled detection, report precision, recall, PR-AUC, false positives under scarcity, abstention and per-family confusion matrices.

Deliver an experiment specification, versioned agent configurations, external-baseline adapter, trajectory dataset, trained automata and an interactive explanation linking each finding to observed events. Have a reviewer record whether the evidence is actionable.

## 9. Frontend redesign specification

### Information architecture

Consumer navigation should expose Workspace, New workload, Jobs, Bookings, Agreements, Usage and Help. Producer navigation should expose Overview, Hardware, Availability, Bookings, Usage and Incidents. Organization settings contain People, Budgets and Policies. Research Lab becomes a dedicated workspace mode so experiment controls do not crowd routine job execution.

Login should discover authorized workspaces after authentication. The current requirement to guess the right workspace before login can be replaced by a visible workspace switcher.

### Visual system

The preserved overview screenshot shows a coherent dark theme, but the operations view mixes job execution, research and policy administration in one dense navigation structure. Its capacity panel also shows an unconfigured grid zone. The next design should make the user's current task and incomplete setup immediately visible, while presenting research tools through a deliberate workspace choice.

Keep recognizable PACT branding and use a restrained graphite and green palette with semantic warning and error colors. Specify typography using the existing Inter or Geist stack, with readable numeric columns. Define spacing, surface, border, focus, typography and chart tokens before individual page redesigns.

Use consistent 8-point spacing, a readable minimum body size, clear heading hierarchy and aligned form labels. Show one primary action for each stage. Use Lucide icons for navigation and status with text labels where meaning is ambiguous. Keep emojis out of the interface.

Use short opacity and color transitions around 120–180 ms, respect reduced-motion preferences, and retain visible keyboard focus. Loading controls preserve their width and explain the action underway. Disable duplicate submission while showing the accepted operation when a request succeeds.

### Screens to prototype first

| Screen | Required contents | Acceptance walkthrough |
| --- | --- | --- |
| Consumer home | Active jobs, available balance, pending approvals and next action | A new user can identify how to submit their first job |
| Workload wizard | Template, input, requirements, review and confirmation | A user can explain deadline, maximum charge and retry policy before confirming |
| Offer comparison | Comparable GPU profile, estimate range, start, cap and freshness | A user can explain why two offers differ |
| Producer onboarding | Connection status, diagnostic checks and test workload result | A producer can connect a host without editing the database |
| Booking workspace | Timeline, parties, pinned terms, outputs and incident status | Both parties see consistent shared facts |
| Agreement reviewer | Source clause, typed rule, unresolved issue and version diff | Reviewer can correct one clause without redoing the whole agreement |
| Explanation drawer | What happened, supporting evidence, next action and alternatives | A user reaches the relevant event or policy with one action |
| Research workspace | Dataset card, split, model version, comparisons and export | A teammate can reproduce the displayed experiment |

### Model and FSM visualization

Use a step-by-step graph linked to the selected booking timeline. Selecting a transition highlights its event, source policy clause, actor, guard and outcome. Offer play, pause, next step and a keyboard-accessible table.

For pricing FSMs, display edge probability, support, held-out coverage and unknown contexts. For scheduler decisions, show a candidate table with each failed hard constraint and the objective contribution of feasible choices. For runtime prediction, show the interval, observed duration and calibration slice.

Add a counterfactual preview answering what becomes feasible if the user changes their deadline, budget or region. Generate alternatives by rerunning the feasibility engine on explicit candidate edits, and require user acceptance before changing the job.

### Interaction and accessibility gates

Test keyboard-only registration, submission, review, booking and output download. Check focus movement, screen-reader names, chart alternatives, contrast, 200% zoom and a 390-pixel viewport. Error messages identify the field and corrective action. Reconnecting live views show freshness and preserve selected items.

Set proposed targets of p95 under one second for common reads and under three seconds for quote responses in the chosen deployment region. Measure these under a documented pilot load before promising them. Define API acknowledgement separately from GPU completion.

## 10. Explainable AI and guide design

Create a versioned guide corpus from approved platform procedures, supported workload templates and verified troubleshooting steps. Each answer should expose the observed status, evidence references, applicable rule, uncertainty, permissible next actions and guide version.

Deterministic explanations should cover normal operations and all known failure codes. Groq can rank or summarize bounded retrieved material on explicit request. Keep tenant payloads out of generic guide requests and make any intentional external submission clear in the product.

Implement a shared request budget, deduplicated cache, timeout, circuit breaker and a queue for optional assistance. Record provider/model/prompt versions and fallback outcomes. Evaluate groundedness, actionable-step correctness, cross-tenant disclosure, stale guidance and prompt injection.

Propose a 50-case initial support benchmark from the scenario table, with expected evidence and next steps reviewed by an operator. Increase cases from real pilot incidents. A fluent answer that cites the wrong event fails evaluation.

## 11. Reproducible evaluation and publication

Freeze a protocol before final comparisons. Record research questions, primary metrics, minimum useful effects, splits, seeds, baselines, tuning budget, failure handling and exclusion criteria.

Use separate training, calibration and evaluation windows. Split related jobs and document families together where independence requires it. Evaluate on another dataset or organization after model selection. Fit thresholds only on training or calibration data.

Report paired effect estimates and confidence intervals. Resample at the unit that reflects dependence, such as days, workload families or episodes. Report sample counts and variation across seeds. Distinguish tuning runs from final held-out tests.

| Research question | Primary comparison | Primary endpoint | Additional checks |
| --- | --- | --- | --- |
| Do grounded clauses improve correctness? | Direct extraction versus validated source-grounded extraction | Unsupported-rule rate and executable false acceptance | Review time and abstention |
| Do better duration estimates improve service? | Median, quantile model and calibrated quantile | Deadline misses at comparable admission | Interval width, pinball loss and subgroup coverage |
| Does carbon-aware planning help? | Matched scheduler arms with equal constraints | Emissions at an agreed service level | Wait, throughput, cost and forecast error |
| Do automata explain behavior? | Markov, current merger and external learner | Held-out log loss with coverage | Complexity and reviewer comprehension |
| Does the whole platform improve operations? | Prior manual workflow versus pilot workflow | Time to successful workload and incident resolution | User errors, reliability and evidence completeness |

Package data manifests, source hashes, release versions, environment lockfiles, experiment configurations, model artifacts, per-run metrics, counterexamples and scripts for every figure. Keep measured live energy, modeled replay energy and customer-reported outcomes explicitly labelled in the paper.

The primary-source review identified an ATLAS-related repository link through search, but that link returned 404 during verification. Treat it as an acquisition lead until the authors' release can be confirmed. Avoid making unavailable artifacts a dependency of the next phase.

## 12. Proposed delivery sequence

The schedule below assumes roughly two contributors, access to two GPU hosts and a cooperative pilot partner. It is a planning estimate. Advance based on acceptance evidence.

| Phase | Approximate window | Deliverables | Exit evidence |
| --- | --- | --- | --- |
| A. Baseline and product decisions | Week 1 | Source-controlled baseline, verified document inventory, pilot charter and journey prototypes | Teammate reproduces one live job and one study |
| B. Membership and onboarding | Weeks 2–3 | Invitations, workspace switcher, reviewer inbox and producer enrollment wizard | Fresh producer and consumer complete onboarding through UI |
| C. Reliability and persistence | Weeks 3–5 | Object storage, outbox, shared limits, idempotency, supervised runner and restore procedure | Fault scenarios preserve reservations, outputs and accounting |
| D. Data and measurement | Weeks 4–7 | Pilot telemetry, v2026 and secondary trace adapters, quality cards and splits | Dataset counts, joins and provenance pass review |
| E. Runtime and scheduling | Weeks 6–9 | Prediction baselines, calibration, fair scheduling and shadow rollout | Improved held-out metrics and acceptable service trade-off |
| F. Contracts and automata | Weeks 6–10 | Independent labels, bounded formal model and external FSM baseline | Reproducible holdout reports and interpretable counterexamples |
| G. Product and research validation | Weeks 10–12 | Polished journeys, accessibility review, pilot report and paper artifacts | Pilot gates met and teammate can reproduce figures |

### Work ownership

The platform contributor owns membership, booking integrity, execution, persistence, instrumentation and deployment. The research contributor owns adapters, annotation protocol, baselines, splits, metrics and experimental artifacts. Both review the workload schema, event vocabulary and explanation evidence because these connect the system.

The frontend can be split by complete journeys after the shared design tokens and API contracts are agreed. Every ticket should identify its user outcome, dependencies, acceptance scenario and evidence artifact.

### First ten concrete backlog items

1. Capture a clean versioned baseline and reproduce the latest live and research evidence.
2. Define membership and workspace switching semantics, including the existing single-role accounts.
3. Prototype consumer submission and producer onboarding with five representative users.
4. Add the reviewer inbox and approved reusable workload policies.
5. Introduce versioned workload specifications and stage timing telemetry.
6. Move artifact publication and recovery to durable object storage.
7. Implement transaction outbox delivery and reconnection tests.
8. Register and profile a bounded Alibaba v2026 sample and one secondary trace.
9. Train and evaluate runtime baselines on a frozen chronological split.
10. Run the full failure-scenario matrix on two real hosts before inviting wider users.

## 13. Proposed release gates and resources

| Area | Initial gate |
| --- | --- |
| Correctness | Zero duplicate accepted capacity allocations in 1,000 repeated contention cases |
| Isolation | Every tenant-boundary case passes for API, events and artifacts |
| Recoverability | Restore a matched database/artifact snapshot and reconcile in-flight work |
| Accounting | Every completed pilot booking has balanced ledger entries and traceable usage |
| Availability | Observe at least 14 days against a declared pilot service objective |
| Latency | Meet the declared read/quote target at a documented concurrency level |
| Usability | At least 8 of 10 representative users complete the main journey without developer intervention |
| Research | Independent test split, credible baselines, uncertainty intervals and reproducible exports |
| Explanation | All critical support scenarios cite correct evidence and permissible actions |
| Rollback | Demonstrated application rollback or forward recovery with prior data |

These are proposed gates, not measured achievements. Zero observed failures across finite tests is evidence within the tested conditions.

Budget for hosted API and database resources, object storage and egress, monitoring, backup retention, two GPU hosts, annotation time and pilot support. Measure storage and bandwidth on sample runs before sizing. Obtain current supplier quotes once the deployment region and capacity are chosen.

Required external inputs are access to actual hosts, workload-owner consent, a deployment domain, organization identity settings if used, and a correct grid-data source. Existing PostgreSQL and Groq credentials cover the current local installation. Additional services should receive separate scoped deployment credentials.

## 14. Distinctive product experiments

| Idea | Practical experiment | Success measure |
| --- | --- | --- |
| Deadline flexibility offers | Let a buyer compare several finish-by options using the same workload | Acceptance and measured service/carbon trade-off |
| Evidence-backed provider reliability | Show observed completion rates by workload and hardware with uncertainty | Better buyer decisions and fewer avoidable incidents |
| Agreement impact preview | Replay a proposed policy edit against the organization's recent jobs | Reviewer comprehension and prevented infeasible submissions |
| Portable execution receipt | Verify artifact, workload version and usage with a public key | Independent verification by both parties |
| Capacity rescue workflow | Offer an authorized alternative after a producer outage | Successful recovery time and preserved budget limits |
| Measurement confidence view | Show which runtime, energy and carbon values are directly measured | Fewer interpretation errors in user testing |
| Operations replay | Reconstruct a failed booking and inspect alternative permitted actions | Faster incident resolution |

Run these experiments after core reliability and onboarding gates. Select the next feature from demonstrated user value, operational evidence and research results.
