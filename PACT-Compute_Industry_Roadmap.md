# PACT-Compute industry roadmap

**Recommendation.** Turn PACT-Compute into an invitation-only GPU capacity exchange. Start with two independently managed GPU pools and a small group of labs or teams running approved batch workloads. A producer publishes capacity it controls. A consumer requests a workload with a budget, deadline and policy. The platform verifies the match, holds the capacity, follows the job through execution and reconciles usage. Operators can explain every material decision from the same record. This model can begin with internal credits or partner chargeback and expand to paid exchanges after the parties have verified reliability and usage.

## 1. What the current system proves

The local application already demonstrates a source-linked SLA, human approval, policy-aware admission, an enrolled physical GPU, real MobileNetV3 execution, verified output artifacts, shadow recommendations and an independent policy audit. Its Research Lab imports a public Alibaba trace and NESO carbon history, compares five scheduling conditions and inspects provider pricing patterns. Its API has job and experiment event streams. The browser currently polls lists about every 4.2 seconds and job and run detail about every 2.2 seconds. A real exchange needs shared inventory, quotes and bookings visible to separate organizations, with each organization receiving its authorized view.

The 30-seed scarcity replay used 120 jobs per seed. Its carbon-aware arm averaged about 3.27 kg of modeled CO₂ per run, compared with about 3.89 kg for the policy-only arm. It increased p95 wait by 51 minutes and reduced on-time completion by about 0.47 percentage points. All 208 deadline flags in the carbon-aware arm and all 209 in the policy-only arm were attached to modeled runtime overruns. That evidence sets two priorities for the next version. First, predict runtimes from completed real jobs and distinguish a bad admission decision from a failure after dispatch. Second, give buyers explicit flexibility limits and compare policies at a comparable level of service. Preserve these replay results as a benchmark and measure the pilot separately.

## 2. Four product directions

| Direction | Customer and problem | Business model to test | What would justify pursuing it |
| --- | --- | --- | --- |
| Private GPU exchange | A university consortium, enterprise or research park has multiple GPU pools and teams that struggle to find usable capacity | Subscription per organization or managed pool, with internal chargeback | At least two pool owners agree to expose usable capacity, and multiple buyer teams repeatedly book it |
| Managed overflow broker | A computer-vision or AI team needs backup capacity when its own cluster is full or offline | Subscription for governance and orchestration, with transparent routing fees where permitted | A partner provides a supported booking interface, a real invoice and a failure or cancellation policy |
| GPU operations and assurance | A team already buys compute and needs evidence for SLA reviews, charge disputes or capacity planning | Subscription per managed pool or organization | A team can supply scheduler and invoice data even when there is only one provider, and the evidence saves review time |
| Flexible batch exchange | Producers have unused windows and buyers have deferrable workloads with measurable service bounds | A disclosed service fee per matched job or capacity window | The pilot shows recurring flexible demand, reliable forecasts and a material number of usable off-peak slots |

The private exchange is the strongest first build because it exercises genuine multi-party interactions while the team controls who can run work. If only one infrastructure partner is available, start with operations and assurance and use the data to recruit a second pool. If local providers are hard to onboard and a buyer already has an authorized cloud account, trial overflow routing in that buyer's account. Kueue already provides a multi-cluster dispatch mechanism, and commercial GPU providers expose their own catalogs. The product opportunity is the cross-party workflow that links a service promise to a booking, an execution record and a reconciled usage receipt. [Kueue MultiKueue](https://kueue.sigs.k8s.io/docs/concepts/multikueue/) · [Runpod GPU catalog API](https://docs.runpod.io/api-reference-v2/catalog/list-gpu-types)

## 3. The platform people would use

| Role | Main tasks | What their view exposes |
| --- | --- | --- |
| GPU producer | Enroll a pool, verify hardware and runner health, post availability, set rates and billing terms, schedule maintenance, and review completed bookings | Own inventory, reserved windows, payouts or chargeback, incident status and evidence for jobs assigned to that pool |
| GPU consumer | Submit a batch, choose service requirements, compare offers, reserve capacity, track progress and retrieve outputs | Offers eligible for their organization, their approved policies, current estimate, maximum authorized charge, attempts, receipts and alternatives |
| Organization administrator | Invite users, set quotas and procurement rules, approve datasets and locations, configure billing | Own teams, budgets, memberships, policy changes and usage. A participant can belong to multiple organizations with distinct roles |
| Operator or auditor | Handle outage exceptions, conflicting evidence, suspected meter errors and disputes | A scoped incident queue, replayable evidence and reasoned manual actions. Sensitive payloads require separate authorization |
| Billing reviewer | Reconcile reservations and metered usage, review adjustments and approve invoices | Usage and rate records necessary for reconciliation, including provenance and invoice line references |

### The first complete transaction

1. A producer links a real runner or cluster, publishes a 16:00–20:00 window and sets a fixed price, supported job templates, region and cancellation terms. The platform verifies GPU inventory, runner freshness and a short health workload. A listing that has lost heartbeat shows when it was last verified.
2. A consumer submits a versioned batch request. The request identifies an approved job template or image digest, data location, required GPU profile, estimated work size, start and finish targets, total spend cap, and permission to retry or move the job. Hard constraints come from the approved policy. The consumer chooses whether carbon and cost preferences may influence timing.
3. The comparison presents viable offers with a current capacity time, quote expiry, all-in estimate and maximum authorized charge. Show which figures include storage, startup or transfer. Separate a posted indicative rate from a reservable quote. The buyer can inspect rejected candidates through their own policy and the reported constraint.
4. A reservation transaction validates current capacity, quote version, budget and inventory ownership. It creates the capacity hold and pins the quote, policy, job template and offer revision together. Both parties receive the same booking reference. If someone else claimed the slot, the buyer gets an immediate explanation and refreshed options.
5. The runner receives an expiring lease, starts the approved job and reports heartbeats, resource usage, status and signed artifact references. The producer sees occupancy and the consumer sees the job timeline. A progress update never implies a guaranteed completion time. Show prediction confidence and refresh the estimate as evidence arrives.
6. The job finishes, fails or requires reconciliation. The platform records actual runtime, billable quantities, observed power coverage and any service shortfall. Both parties can inspect a usage receipt and its evidence. An adjustment or dispute creates a new ledger entry and an audit event.

### Situations the exchange should handle

| Situation | Interaction between parties | Required system behavior |
| --- | --- | --- |
| Two buyers claim the last GPU | Both see the slot. One wins the hold and the other sees the loss and alternatives. | Allocate capacity and reserve budget atomically. Verify one active hold, one charge envelope and a consistent status on both screens. |
| A price changes during checkout | The producer publishes a new rate. The buyer may still have a valid quote or must reconfirm the new price. | Honor locked terms within the committed quote window. Reject or reprice an expired quote explicitly. Keep rate revisions and timestamps. |
| Producer schedules maintenance | The producer marks a future pool drain. Affected consumers see a notice and eligible alternatives. | Prevent new overlaps. Preserve existing bookings until the applicable terms and operator decision resolve them. Record who accepted a move. |
| GPU becomes unreachable during a job | Both sides see the last heartbeat and the uncertain execution status. The operator or runner reconciles the original attempt. | Hold the capacity and avoid duplicate execution or billing. Retry within the remaining budget and deadline only when the original attempt is resolved. |
| Buyer asks for an urgent run | The buyer sees the earliest feasible start and expected completion, including provisioning time. | Apply hard deadline and budget checks. Avoid promising a slot whose completion estimate lacks support. Escalate an expiring critical job visibly. |
| Buyer permits carbon-based deferral | The buyer sets a latest start or allowable delay and compares the projected wait, price and carbon range. | Use the forecast issued before the decision, reassess as conditions change and stop deferring at the configured bound. Keep the forecast and realized estimate in the receipt. |
| Spot capacity or preemption | The producer offers a discounted interruption-prone pool. The buyer chooses a checkpointable workload. | Track lost work, checkpoint age, restart cost and actual service delivery. Require explicit consent for an interruption-prone service class. |
| Dataset can only run in one approved location | A cheaper or cleaner pool may be technically capable and excluded by the data policy. | Apply data location and access rules before ranking offers. Give the buyer a clear exclusion reason without exposing private producer information. |
| Final meter disagrees with the quote | Producer and buyer each see quote, usage, billing increments and evidence. A billing reviewer opens a case. | Reconcile in the ledger and issue a traceable adjustment. Avoid charging twice across retries, timeout recovery or duplicate payment events. |
| Prices rise during a real supply shortage | An auditor sees demand, inventory losses and affected offers alongside price changes. | Compare like-for-like conditions and abstain when evidence is thin. Escalate a documented behavior pattern for human review. |

## 4. Real data acquisition and validation

The first dataset to pursue is an authorized, linked pilot trace from both sides of the exchange. Public GPU traces remain useful for performance testing and reproducible research. The pilot creates the job, price, execution and billing evidence that those datasets lack.

| Data stream | First practical source | What to collect and how to verify it |
| --- | --- | --- |
| Real workload demand | One university lab, AI startup or enterprise team. Start with a sanitized job export and read-only observation | Submission, queue wait, GPU request, hardware class, job size proxy, retry count, outcome and deadline. Map source job IDs and strip payloads, prompts and user identifiers from analytics. |
| Hardware supply and reservation history | Existing local runner plus a second lab or partner pool. Choose Slurm or Kubernetes based on the partner | GPU model, memory, topology if needed, allocatable count, uptime, planned downtime and reservation windows. Compare registry state to scheduler inventory and a probe run. [Slurm accounting](https://slurm.schedmd.com/sacct.html) · [Kueue MultiKueue](https://kueue.sigs.k8s.io/docs/concepts/multikueue/) |
| Execution and resource telemetry | A controlled NVIDIA host with DCGM Exporter or a partner's permitted equivalent | Start and end, resource assignment, sampled power, memory and utilization, missing samples and interruption reason. Attribute samples only at supported granularity. Mark shared-device estimates and compare exclusive-job totals to a meter where available. [NVIDIA DCGM Exporter](https://docs.nvidia.com/datacenter/dcgm/latest/installation/install-dcgm-exporter.html) |
| Real offers and prices | Direct partner rate cards and signed quotes. An authorized commercial catalog is useful for a comparison feed | Availability timestamp, GPU and region, term, rate, currency, minimum billable duration, cancellation terms, storage and transfer. Record quote acceptance separately. A catalog observation carries no capacity commitment. Verify booking and reuse permissions with the provider. [Runpod GPU catalog API](https://docs.runpod.io/api-reference-v2/catalog/list-gpu-types) |
| Actual cost and usage | Internal chargeback export, partner invoice, or the customer's cloud billing export | Link metered usage to reservation, attempt and invoice line. Capture rounding rules, fees and any adjustment. Reconcile provider charges before evaluating margins. Use FOCUS terminology where supported by the provider. [FinOps FOCUS specification](https://focus.finops.org/focus-specification/) |
| Grid carbon and facility power | NESO for GB. For an Indian pilot, first verify the physical region and temporal coverage of an authorized feed | Store forecast vintage, event and retrieval time, source methodology, grid zone and measurement boundary. Indian public generation data can support historical context. A dispatch feature needs an appropriately licensed, region-matched and time-aligned signal. Electricity Maps academic access has noncommercial limits. [NESO API](https://api.carbonintensity.org.uk/) · [NITI Aayog generation dashboard](https://iced.niti.gov.in/energy/electricity/generation) · [Electricity Maps academic terms](https://help.electricitymaps.com/en/articles/13168512-academic-data-access-and-availability) |
| Policies and human review | Partner-approved service templates, approved examples, and reviewed outcomes | Capture clause spans, exceptions, versions, reviewer decisions and whether an outcome was prevented, violated or lacked evidence. Obtain permission for contract text before using an external extractor. |

### Pilot collection protocol

1. **Obtain a data agreement.** Define fields, permitted use, retention, access, exports and deletion with each partner. Request aggregate history first and a read-only connection once the partner approves it. Collect workload data at the minimum granularity needed. Keep each partner's raw data within its authorized boundary.
2. **Observe a real baseline.** Aim for four weeks of queue and inventory history, at least two distinct pools and three buyer teams. Start with one reproducible workload family such as image embeddings or offline batch inference. Collect enough completed jobs to estimate a runtime distribution for common hardware and job sizes. Treat a few hundred job records as a planning target. Extend observation if the sample is thin or biased.
3. **Link and grade the evidence.** Use immutable IDs for source job, quote, booking, allocation and attempt. Check clocks, duplicate records, feed gaps and inconsistent resources. Label inputs as measured, provider-reported, forecast, derived or modeled. Record every derived field and its confidence. Keep billing, energy and model metrics traceable to their source.
4. **Improve runtime prediction.** Use input size, workload template, GPU class, observed throughput, provisioning time and recent failures. Report p50 and a conservative interval or p90 for admission. Validate on held-out time windows and hardware pools. Compare interval coverage and error to the current baseline. Tag unsupported combinations and fall back to bounded pilot templates.
5. **Run a shadow trial.** Generate recommendations for the existing queue and compare feasibility, costs and expected service against actual outcomes. Ask operators to label recommendations they could have used. Trial bounded dispatch with opt-in workloads after shadow recommendations and inventory reconciliation are credible.
6. **Evaluate live performance.** Use matched workload sizes, comparable service classes and clearly documented dispatch rules. Compare job success, on-time completion, GPU-hours delivered, cost, operator time, dispute rate and energy. Report energy and emissions with coverage and uncertainty. For sustainability comparisons, show both total and per-successful-job values and service impact.

## 5. Market rules and dynamic updates

**First pricing mechanism.** Use posted prices and time-limited fixed quotes. Offer on-demand, scheduled and interruptible capacity only where partners can honor those terms. A quote includes a UTC validity window, capacity version, currency, minimum billing increment and maximum authorized spend. Buyers can rank eligible offers by earliest completion, lowest total estimate or lowest estimated emissions. Providers set their own offers and see their own performance. New market mechanisms, such as sealed requests for quotes, should follow evidence that multiple providers routinely respond to the same demand.

**Inventory and events.** Keep booking, quote and ledger decisions authoritative in PostgreSQL with transactional capacity and budget checks. Write the business change and event record in the same transaction. Deliver updates at least once and deduplicate by event ID. Keep public listing projections separate from private bookings and billing data. Server-sent events can reuse the existing application direction, with cursor replay and a fresh snapshot on reconnect. Clients retain their filters, scroll and selection as rows update. Indicate delayed feeds and the time of last confirmed data. The server rechecks all state-changing requests. [HTML standard for server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)

**Booking, execution and billing are distinct.** Track a reservation as held, confirmed, released or expired. Track a job as queued, running, uncertain, succeeded, failed or cancelled. Track usage as pending, metered, reconciled, disputed or adjusted. A disconnect from the browser does not cancel a confirmed reservation. A runner disconnect leaves its attempt uncertain until reconciled. A successful job may still have pending billing. A quote can expire while the page stays open and its reservation action must reflect that.

**Money.** Begin with internal chargeback and verify quotes, caps, units, idempotent event handling and invoice reconciliation. Move to a limited paid pilot after partner agreements, payment provider eligibility for the chosen countries and a worked test of cancellations, reversals, disputes and payouts. Use a marketplace payments provider where appropriate. Keep the authorization, metering, invoice and adjustment records separate and auditable. Decide the billing entity, applicable terms and operational responsibilities with qualified local support before the paid launch. [Stripe Connect documentation](https://docs.stripe.com/connect)

**Business case.** Track delivered GPU-hours and repeat bookings per active organization, share of searches with eligible offers, quote-to-reservation conversion, gross booking value, direct GPU and transfer costs, support effort and reconciliation time. Validate the producer's net benefit after power, operations and maintenance. Validate the consumer's actual outcome relative to their current procurement workflow. Start with subscription or managed-pool pricing as a hypothesis and use interviews and pilots to test willingness to pay.

## 6. Frontend specification

Keep the current application recognizable and improve it into a professional operations console. The landing screen should reflect the user's role and next decision. Use a restrained palette, consistent type and spacing, readable tables, and line icons only where they clarify a control or status. Remove emoji from product copy, labels, empty states, alerts and exported interface text. Use Inter for interface text and IBM Plex Mono for identifiers, log entries and hashes. Keep technical details available in an evidence drawer and default primary screens to the information users need to take action.

| Area | Primary interaction | Information that must stay visible |
| --- | --- | --- |
| Consumer workspace | Find GPU capacity, compare, hold and confirm a slot | GPU profile, location, earliest start, estimated finish, rate and all-in estimate, quote expiry, maximum charge, source of the carbon estimate |
| Producer workspace | Publish or pause an offer, drain a pool, review bookings and usage | Verified inventory, capacity calendar, current reservations, rate version, heartbeat freshness, outstanding usage discrepancies |
| Booking and job detail | Track work, act on failure, download evidence | Pinned terms, reservation and execution state, authorized spend, estimated finish or its uncertainty, next action, output artifact, and receipt |
| Operator workspace | Triage incidents and billing disputes | Impacted bookings, evidence age, ownership, timeline, available actions, and documented reasons for overrides |
| Research Lab | Compare replay and pilot experiments, inspect an event sequence | Scenario assumptions, data origin, controlled inputs, measured versus modeled metrics, uncertainty and comparable cohort |

### Button and form behavior

- **A clear action on each screen.** Use one primary action where it drives the workflow. Use verbs that identify the consequence, such as **Hold capacity**, **Confirm reservation**, **Publish offer**, **Pause new bookings** and **Cancel job**. Place price, expiry and consequences beside the relevant button. Keep destructive or costly actions visually distinct.
- **Responsive interaction.** Specify default, hover, pressed, keyboard focus, pending, confirmed, unavailable and retryable states for shared controls. Use subtle color and border transitions of roughly 120–180 ms where appropriate. Keep button dimensions stable while text changes. Respect reduced-motion settings. Use motion to communicate a state change.
- **Honest progress.** A click gives immediate local feedback. The server confirms a capacity hold, charge authorization, cancellation or publication before the interface declares success. Keep a duplicate click from creating a second request. If a response is lost, look up the prior request by its ID and restore the correct state. The user can retry safe actions without re-entering the form.
- **Useful failure states.** For an expired quote, retain inputs and show a refreshed price and availability. For a capacity conflict, show eligible alternatives. For a blocked approval, show the missing clause or field beside the action. For stale data, show when the last verified snapshot was received and let the user refresh.
- **Stable live views.** Use a shared event connection for authorized updates. Change individual cells, statuses and counters in place. Preserve selected offers, filters, scroll, focus and form drafts. For rapidly changing prices, indicate changes and require explicit confirmation on material differences.
- **Accessible interaction.** Use semantic buttons and form fields, text alongside color cues, clear focus rings and consistent focus return after dialogs. Provide keyboard access to charts through tables or a usable equivalent, readable touch targets and useful live announcements for material updates. Test both desktop and mobile. Use WCAG 2.2 AA as the target and record manual and automated accessibility results. [WCAG 2.2](https://www.w3.org/TR/WCAG22/)

### UI acceptance walkthrough

Open producer and consumer sessions on separate devices or browser profiles. Publish a slot as the producer. Verify it appears in the consumer list without a full page reload. Hold it from one consumer and attempt the same booking from another. Verify both see the right result, including a refreshed alternative for the losing consumer. Let a quote expire, reconnect after a network interruption, and close a confirmation dialog with the keyboard. Finish the booking, confirm the receipt becomes available to both parties, and check that each organization sees only its authorized data. Test narrow screens, slow connections and long offer names. Capture the completed flows as the visual baseline for future changes.

## 7. Operational readiness

| Capability | Minimum before partner dispatch | Additional gate before open access or larger spend |
| --- | --- | --- |
| Identity and tenant boundaries | Organization roles, scoped runner credentials, HTTPS, authorized event subscriptions and verified cross-tenant denial | SSO where needed, credential rotation, access review, and independent testing of boundaries |
| Workload execution | Allowlisted images or templates pinned by digest, resource and time limits, scoped artifact links, restricted network access | Threat model, stronger isolation appropriate to untrusted tenants, independent security testing and a policy for acceptable workloads |
| Reliability | Lease reconciliation, duplicate prevention, recovery runbooks, queue and heartbeat alerts, and a tested backup restore | Defined availability and recovery targets, staged releases, load testing and incident coverage |
| Ledger and usage | One committed reservation and usage record per transaction, clear rounding, matched source IDs, exportable evidence | Reconciliation against invoices and payment events, operator-approved adjustments and external settlement monitoring |
| Privacy and data rights | Partner permission, data minimization, retention and deletion processes, scoped data access | Reassess each new region, third-party data feed, workload type and account integration |
| Model and audit quality | Runtime confidence ranges, source-backed facts, measurement coverage, and a human review path | Drift monitoring, appeal and correction processes, independently reviewed benchmarks and periodic assessment |

Use one hosted control plane, a transactional database and private artifact storage for the pilot. Keep execution in the producer's or consumer's approved environment. Choose the cluster integration based on the first partner's infrastructure. Treat arbitrary third-party containers as a separate security milestone with dedicated isolation requirements. Keep signed receipts for disputes and collect service telemetry for support. Kubernetes provides controls for multi-tenancy, with isolation decisions depending on the tenant trust model. [Kubernetes multi-tenancy guidance](https://kubernetes.io/docs/concepts/security/multi-tenancy/)

### Proposed pilot success criteria

These are starting targets to agree with a pilot partner and refine after measuring the baseline.

- Run with at least two independently managed pools and three buyer teams. Record repeat bookings from more than one buyer and bookings delivered by both producers.
- Capture linked quote, booking, runtime outcome and usage evidence for at least 95% of completed pilot bookings. Resolve unexplained billing differences before charging.
- Pass concurrent booking, duplicate callback, lost heartbeat, quote expiry, cross-tenant access, backup restore and data-location tests. Reconcile every uncertain attempt before reusing its capacity.
- Demonstrate p95 quote preview within two seconds and p95 confirmed event delivery within two seconds in the declared pilot load test. Measure separately on slow mobile and after reconnect.
- Report p95 wait, on-time completion and cost with the denominators stated. Compare carbon-aware policies against an agreed service floor and include uncertainty and coverage. Stop offering a service class where prediction calibration or capacity reliability falls outside the agreed range.
- Complete the producer-to-consumer walkthrough with representative users. Measure whether they can complete and understand the task without help. Fix any blocker in booking, approval, cancellation or dispute review.

## 8. Product ideas worth testing

1. **Verified capacity listings.** Show when GPU type, memory, driver compatibility and a standardized probe were last verified. Combine health checks and measured service history with partner-defined maintenance windows. This helps buyers distinguish capacity they can book from a catalog listing. Test whether it lowers failed starts.
2. **Offers with a flexibility range.** Let a buyer declare a latest start, maximum delay and willingness to trade time for lower cost or emissions. Show urgent, scheduled and flexible offers together with the conditions they satisfy. Test whether flexibility fills unused hours at an acceptable completion rate. This is the best candidate for a research contribution once real workloads are available.
3. **Receipts that explain charges.** Give each party a shareable, access-controlled receipt linking the approved terms, quoted amount, metered runtime, billing increments, failure events and adjustments. Design a reviewer workflow that can decide a dispute using the record. Track review time and correction rate.
4. **Policy-aware backup capacity.** Let a buyer name acceptable alternate pools and authorize a maximum recovery spend. A confirmed outage can prompt a new booking with the relevant contract and data rules rechecked. Test with checkpointable workloads and show when switching would worsen the deadline or exceed budget.
5. **Schedule jobs near approved data.** Let organizations register dataset location, transfer size and eligible compute environments while keeping the underlying data in its existing store. Rank placements with transfer time and charges included. Use this for image-heavy batches where data movement can erase the benefit of a lower GPU rate.
6. **Replay real incidents.** Export a de-identified timeline of an outage, billing dispute or scarcity event into Research Lab. Let operators compare alternate decisions under the same input timeline. Keep replay status visible and include the limits of the available evidence. Use replay outcomes to improve operations and train reviewers.
7. **Service reliability by workload class.** Show historical start delay, success, interruption and telemetry coverage for comparable jobs, with sample size and time window. Distinguish hardware capability from observed service. Give providers a way to correct bad records. Avoid a single score that hides differences in workload complexity.

Build verified listings and usage receipts first because they also improve the private-exchange pilot. Add flexibility offers once there are usable runtime estimates and a reliable feed. Select backup capacity or data-local routing based on the first partner's most frequent failures and costs.

## 9. Implementation sequence

This is an illustrative five-to-six-month roadmap for a small team. The milestones depend on partner access, hardware, and decisions on who runs and supports the service.

| Stage | Estimated window | Product deliverable | Exit evidence |
| --- | --- | --- | --- |
| 0. Recruit and observe | Weeks 1–3 | Pilot brief, pool and workload selection, participant roles, data agreements, UI flows for producer and consumer | A named pool owner and workload owner, sample records, baseline definitions and a plan for the second pool |
| 1. Instrument real workloads | Weeks 4–7 | Authorized read-only connectors, normalized real records, runtime calibration, evidence quality checks, refined existing console | A real workload can be followed from queue entry through artifact and usage. Baseline statistics and coverage are documented. |
| 2. Build the private exchange | Weeks 8–12 | Producer listings, consumer comparison and booking, organization roles, live inventory and booking updates, shared receipts | Two pools and multiple buyers can use separate sessions to publish, book, run and verify work. The concurrent last-slot test passes. |
| 3. Run a limited live pilot | Weeks 13–17 | Bounded production workloads, operator support, chargeback reconciliation, failure and restore drills, user testing | Repeat bookings and reconciled usage from both pools, documented recovery behavior, reviewed accessibility and workflow feedback |
| 4. Differentiate and prepare paid rollout | Weeks 18–24 | One validated differentiator, partner or payment integration where justified, staged security and reliability review | Evidence supports the chosen differentiator. Paid rollout follows only after provider agreements, supported payment operations and support ownership are in place. |

### First milestone to choose

The next deliverable should be a **two-pool private exchange demonstration with real jobs and shared booking state**. Choose the first workload family and a producer partner, agree on a minimal data export, and prototype three connected screens for publishing an offer, reserving it and inspecting the resulting receipt. Run two browsers against the same event stream and deliberately introduce a capacity conflict and a runner disconnect. That demonstration tests the commercial interaction, the scheduler's guardrails, the audit evidence and the frontend behavior in one workflow.

If access to the second pool is delayed, keep the same transaction model and run a single-provider assurance pilot. Add the second producer once access is available. Use a cloud connector when a buyer already has a permitted account and the arrangement can provide real booking and usage evidence.

### Existing evidence

- [Current application and setup guide](<C:/Users/raddo/Documents/main el 5th sem/pact-compute/README.md>)
- [Verified live job evidence](<C:/Users/raddo/Documents/main el 5th sem/pact-compute/.local/verified/gpu-job-evidence.json>)
- [Thirty-seed benchmark summary](<C:/Users/raddo/Documents/main el 5th sem/pact-compute/.local/verified/benchmark-30-seeds.json>)
