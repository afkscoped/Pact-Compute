"""Build evidence-linked release documents from completed local checks.

This does not run tests or upgrade any deployment. Run it only after validation.
"""
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from validation_manifest import capture

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = REPO / 'reports' / 'final-validation'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def pytest_counts(name):
    suites = ET.parse(OUT / name).getroot().iter('testsuite')
    totals = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    totals['passed'] = totals['tests'] - sum(totals[key] for key in ('failures', 'errors', 'skipped'))
    return totals


def main():
    current = capture()
    # Do not attach historical passes to different executable bytes. Reports
    # are generated only from successful, content-bound final suite runs.
    for name in ('final-summary.json', 'clean-install-summary.json', 'browser-summary.json', 'postgres-summary.json'):
        evidence = read(name)
        assert evidence.get('source_unchanged') and evidence.get('source') == current, f'Rerun {name}: executable source differs'
        assert not evidence.get('exit_code', 0), f'Failed suite: {name}'
        assert all(not row['exit_code'] for row in evidence.get('results', [])), f'Failed suite: {name}'
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    files = current['files']
    fingerprint = current['fingerprint']
    (OUT / 'source-manifest.json').write_text(json.dumps({'base_revision': revision, 'branch': 'sasha-work',
        'working_tree': 'uncommitted local review patch; no push or merge', 'source_fingerprint': fingerprint, 'files': files}, indent=2) + '\n', encoding='utf-8')
    baseline, final = pytest_counts('baseline-pytest.xml'), pytest_counts('final-pytest.xml')
    pg = pytest_counts('postgres-pytest.xml')
    browser = (OUT / 'browser-e2e.log').read_text(encoding='utf-8')
    browser = json.loads(browser[browser.index('{'):])
    gpu = read('gpu-independent-verification.json')
    race = read('contention-1000.json')
    pg_race = read('contention-postgres.json')
    perf = read('performance-http.json')
    source = ROOT / '.local' / 'validation' / 'research' / 'evaluations'
    study = json.loads((source / 'publication-study.json').read_bytes())
    carbon = study['paired_calibrated_minus_median']['carbon_g']
    prefix = (f'Verified 13 November 2026 (Asia/Calcutta). Base Git revision `{revision}` on `sasha-work`, with the local review patch. '
              f'Executable source fingerprint `{fingerprint}`; exact files in [source-manifest.json](source-manifest.json).\n\n')
    tests = (f'Backend: **{final["passed"]} passed, {final["failures"]} failed, {final["errors"]} errors, {final["skipped"]} skipped** '
             f'([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **{pg["passed"]} passed** separately '
             f'([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed '
             f'([commands](final-summary.json)). Browser: **{browser["stats"]["expected"]} passed**, '
             f'{browser["stats"]["unexpected"]} failed ([report](browser-e2e.log)).\n\n')
    blocked = ('Hosted revision/configuration and real bucket require owner account access. Production migrations require a verified backup and explicit approval. '
               'Independent agreement/support labels, screen-reader review, partner agreements, two-host pilot and a longer observation window require humans/resources. '
               'No hosted mutation, partner participation or production readiness is claimed.\n\n')
    commands = '''From `pact-compute`, using the project virtual environment:

```powershell
.\\.venv\\Scripts\\python.exe scripts/validate.py datasets
.\\.venv\\Scripts\\python.exe scripts/validate.py final
.\\.venv\\Scripts\\python.exe scripts/postgres_validation.py
.\\.venv\\Scripts\\python.exe scripts/validate.py contention
.\\.venv\\Scripts\\python.exe scripts/gpu_validation.py
.\\.venv\\Scripts\\python.exe scripts/browser_validation.py
.\\.venv\\Scripts\\python.exe scripts/validate.py research
.\\.venv\\Scripts\\python.exe scripts/validate.py research --label research-repeat
.\\.venv\\Scripts\\python.exe scripts/export_research.py
```

PostgreSQL needs the official portable binaries under `.local/postgres-runtime/pgsql/bin`.
Browser validation needs Edge, the built console, prepared model weights under `.local/validation/browser`,
and a separate `.gpu-venv` with the recorded GPU lock. It refuses an occupied port 8766.
It starts/stops its own API, worker and runner. It never attaches to the pre-existing listener on 8765.
All databases/providers are explicitly isolated; preserve private .env files.
'''
    fixes = '''| ID | Fixed behavior | Regression evidence |
| --- | --- | --- |
| DATA-01 | Restored exact approved Git bytes; retained manifest identity and -text attributes | dataset-restored.json captures before/after hashes; current dataset-check.json and fresh imports |
| EVT-01 | Drains all reconnect/live SSE pages before advancing a cursor | event-regression-before.log (2 failures), event-regression-after.log; tests/test_event_delivery.py |
| EVT-02 | PostgreSQL writers acquire a transaction lock before application locks/sequence allocation | postgres-before.log fails slow writer; postgres-tests.log passes after fix |
| EVT-03 | Signed job exports and independent monitoring retain complete event history | evidence-before.log fails after 1,000 events; final regression passes |
| STORE-01 | Existing local/S3 bytes are reverified on idempotent writes | recovery-before.log fails corrupt retry; local and moto regressions pass |
| TEST-01 | Fresh database per validation invocation; skipped PostgreSQL collection no longer initializes app config | test-isolation-before.log; final and repeated final runs |
| ENV-01 | Local pip/GPU setuptools security updates and compatible pinned GPU pair | dependency audit JSON, pip check, repeated real GPU validation |
| E2E-01 | Correct consumer Home, accessible selectors, isolated state/port, feasible declared hardware policy | browser-initial.json.log versus final browser report |

Event ordering intentionally serializes PostgreSQL write transactions for this small private installation. Reads remain concurrent. Drain all older API/worker/runner writers before rollout; mixed-version writers do not share the guarantee. This is a throughput trade-off, not a scalable dispatcher implementation.
'''
    gates = '''| Gate | Status | Evidence / scope |
| --- | --- | --- |
| A Backend | PASS | Final pytest, fixture-scoped functional coverage |
| B Frontend | PASS | Node, TypeScript/build and four browser workflows |
| C PostgreSQL | PASS | Disposable PostgreSQL 18.7, five integration cases |
| D Migrations | PASS | SQLite older-data upgrade, rollback/forward and drift check; PostgreSQL 0002→0007 |
| E Authentication/authorization | PASS | Existing route-derived matrix plus actual browser role separation |
| F Tenant isolation | PASS | Cross-tenant API and shared-receipt/private-artifact browser checks |
| G Marketplace integrity | PASS | 1,000 SQLite and 25 PostgreSQL races; duplicate confirmations |
| H Runner/workload | PASS | Physical CUDA jobs plus lease/fence/cancel contract regressions |
| I Artifact recovery | PASS | Integrity retries, local/moto, real PostgreSQL matched restore |
| J Failure injection | PASS | Covered bounded cases; not an outage soak certification |
| K API integration | PASS | TestClient matrix plus real loopback HTTP/browser requests |
| L Browser E2E | PASS | Producer/consumer race, reviewer invite/inbox, what-if/incident, GPU/research |
| M Accessibility | BLOCKED | Axe clean on two views and keyboard/mobile checks; full screen-reader/zoom/chart review pending |
| N Security regressions | PASS | Scoped auth/storage/fence tests and current dependency scans; no independent penetration test |
| O Performance | PASS | Declared small warm local workload; not WAN or production scale |
| P Research reproduction | PASS | 12 byte-identical artifacts over two frozen runs; human-label validity remains blocked |
| Q Live GPU | PASS | Physical GTX 1650, CPU reference, output hashes/vectors, measured board telemetry |
| R Hosted deployment | BLOCKED | Owner access, exact deployed SHA, storage and authorized rollout verification |
| S Backup/restore | PASS | Disposable pg_dump/pg_restore plus matching objects and original signature; production drill pending |

PASS applies only to the explicit evidence scope. Missing hardware-failure combinations, long outages and scale tests are not concealed by the aggregate counts.
'''
    docs = {}
    docs['BASELINE_TEST_REPORT.md'] = f'''# Baseline testing

At baseline, {baseline['passed']} backend cases passed, {baseline['failures']} failed and {baseline['skipped']} was skipped. All four failures were approved source checksum failures (environment/missing exact bytes), not fabricated replacement data. The 33 Node tests and production build passed. [Commands/timings](baseline-summary.json); [raw backend log](baseline-backend.log).

Two independent event-delivery tests then failed on the original code. A corrupt idempotent artifact retry, a real PostgreSQL slow writer and the long evidence export each had failing-before evidence. A later repeated full suite revealed configuration import/order and persistent fixture reuse; this test harness defect was corrected. Windows shared-temp permissions were avoided with workspace-local isolated temporary paths. These failures are retained rather than rewritten as successes.

'''+tests
    docs['ENVIRONMENT_MANIFEST.md'] = '# Environment manifest\n\n'+f'''Windows 11, CPython {platform.python_version()}, Node 24.11.1, npm 11.6.2. Python came from the Codex bundled runtime; no system Python installation was performed. Backend/application lock: `pact-compute/requirements-win-py312.lock.txt`. Audit/figure tool environment: [resolved packages](environment-final.resolved.txt). GPU environment: [resolved packages](gpu-environment.resolved.txt). GPU runtime: `{gpu['torch']}`, CUDA Driver API `{gpu['cuda']}`, GTX 1650. Portable PostgreSQL 18.7 ran only on loopback with disposable databases. No Docker engine was available.

The older Python 3.14 lock is historical; it does not describe this 3.12 validation. A fresh environment installed the exact new application lock and independently ran the final backend/Node/build suites: clean-install.log, clean-install-pytest.xml and clean-install-summary.json. The optional audit/plot tools have a separate requirements-validation-win-py312.lock.txt. The GPU uses CPU PyTorch for loading/preprocessing and actual NVIDIA Driver API kernels for inference. `torch.cuda.is_available()` is not the evidence for this path. A separate CUDA-enabled PyTorch engine was not validated.

'''+commands
    docs['DATASET_INTEGRITY_REPORT.md'] = '''# Dataset integrity

All **12/12** entries now match the approved SHA-256 manifest. Six initial mismatches were CRLF conversion only: the three active Alibaba CSVs and three acquisition guides. Restoration used exact Git blobs only after checking both the manifest hash and normalized equality to current bytes; substantive local edits would be refused. No manifest values were changed and no large dataset was redownloaded.

Fresh import verifies 7,064 GPU pods, 185 successful lifecycle proxies and 1,344 in-window carbon intervals. Schema `pact-dataset-1`; snapshot identity and complete source provenance are in [experiment-manifest.json](experiment-manifest.json). The raw carbon file has 1,345 entries; the endpoint interval is excluded by the declared window. Import checks duplicate/missing identities and contiguous intervals. CUAD/ContractNLI/LEDGAR remain auxiliary archives, not integrated benchmark labels. Guides are not downloads.

Evidence: [current check](dataset-check.json), [restoration with captured pre-write hashes](dataset-restored.json), research-import.log and final pytest. Repeat `python scripts/validate.py datasets`; only use `--restore-datasets` when exact approved Git blobs and line-ending-only differences are established.
'''
    docs['RELIABILITY_TEST_REPORT.md'] = '# Reliability\n\n'+fixes+f'''
The isolated SQLite gate ran {race['cases']} independent two-buyer races, {race['confirmations']} competing confirmations and {race['duplicate_retries']} duplicate retries with zero double bookings. PostgreSQL repeated 25 races/50 confirmations/25 retries. Fixture resets between rounds are not physical executions. [SQLite metrics](contention-1000.json); [PostgreSQL metrics](contention-postgres.json).

Existing tests cover quote expiry, key/body conflicts, stale fences, lease loss, uncertain holds/reconciliation, cancellation, producer pause, bad output, unknown carbon and Groq throttling/fallback. New tests cover large replay bursts, reconnect cursors, corrupt storage retries, failed research with safe errors, research lease reclaim rejecting an old worker, runner journal retry after a lost response, runner restart window protection and interrupted publication with metadata rollback. failure-injection.log records the five added deterministic checks. Real local runner cancellation/restart, API restart, persisted session and HTTP SSE reconnect are recorded in runtime-recovery.json. Database cold restore/reconnect is verified; an operating-system/database crash with simultaneous live GPU work is not a tested outage soak. No claim is made about every hardware/network combination.
'''+tests
    docs['RECOVERY_DRILL_REPORT.md'] = '''# Recovery drill

PASS for an isolated PostgreSQL drill: upgrade a fresh old schema to head; write real artifact metadata/bytes and signed evidence; stop test writers; copy artifact/signing state; pg_dump; create a separate empty database; pg_restore; start cold verification subprocesses against the restored database and state. `artifacts-verify` and original evidence signature verification passed. [Results](postgres-summary.json), [verifier output](postgres-restore.log).

SQLite separately verifies retained old-schema data, latest migration rollback/forward, ORM drift and cold matched object restoration. Deliberate byte corruption is rejected. Production snapshots, RPO/RTO, cloud bucket versioning and disaster-region recovery remain unverified. Do not run restoration against an existing production database. For a partner drill, obtain a verified backup/approval, restore into a new staging database and private object prefix, verify all hashes/signatures, then inspect a real receipt/output before permitting dispatch.
'''
    docs['GPU_EXECUTION_VALIDATION.md'] = '# Physical GPU execution\n\n'+f'''PASS on **{gpu['device']}**, CUDA Driver API {gpu['cuda']}, `{gpu['torch']}`. Preparation compared real kernel embeddings with a CPU model reference. [Prepare log](gpu-prepare.log). Independent execution returned two distinct, finite, unit-normalized 960-dimensional embeddings, corresponding input hashes and an output SHA-256. A real child-process timeout exited 124; altered input hash and separately copied corrupted weights were rejected. [Independent results](gpu-independent-verification.json).

Browser workflows separately executed four-image jobs and an exchange booking with measured board power coverage, receipt, policy findings and capacity release. Driver-visible VRAM is 4095 MiB, below a literal 4 GiB requirement; tests explicitly reviewed a 3 GiB policy. They did not inflate hardware inventory. Arbitrary containers, multiple physical GPUs and distributed jobs remain outside this validation. Runner restart while executing every failure combination still needs a longer hardware exercise.
'''
    docs['GPU_OUTPUT_VERIFICATION.md'] = '# Output verification\n\n'+f'''Independent output: `{gpu['artifact_sha256']}`. Approved weights: `{gpu['weights_sha256']}`. Kernel bytes: `{gpu['kernels_sha256']}`. Inference {gpu['inference_seconds']} seconds for two images in this recorded run. Every vector has 960 finite values; squared norm differs from one by less than 0.001; row identity and input hash match; distinct images yield distinct vectors. Browser tests rehash downloaded artifact bytes and compare the stored digest. Local browser validation pins the full weights hash.

Inference timing excludes loading, staging and orchestration. Board energy is not whole-machine or facility energy. Preserve raw output/evidence privately under `.local/validation/browser/verified`; generated summaries omit runner/session/signing credentials. Reproduce using `python scripts/gpu_validation.py` after preparing the approved weights. No GPU assertion is replaced with mocked inference.
'''
    docs['END_TO_END_WORKFLOW_REPORT.md'] = '''# Connected workflow

The actual browser exchange exercised producer login → publish real enrolled GPU capacity → two consumer quotes under reviewer-approved policies → competing confirmation → one reservation → native runner claim → physical CUDA execution → output validation/storage → matching producer/consumer receipt → private job access denied to producer/loser → protocol PASS and released capacity. The consumer downloaded/inspected its private evidence. The workspace browser scenario also approved a source-linked SLA, ran a real GPU job, rejected a 32 GiB requirement, executed a research replay and verified CSV/evidence exports.

New browser scenarios cover consumer signup, invitation redemption in another browser context, reviewer inbox approval, consumer self-approval denial, session persistence/sign-out, what-if proposal → explicit draft revision without mutating the original policy, and operator claim/resolution of a deliberate non-executing stale heartbeat fixture. Fixture incidents are not represented as physical GPU failures. The supervisor additionally verifies real runner cancellation/restart followed by physical execution, API restart, retained session and SSE catch-up (runtime-recovery.json). [Browser evidence](browser-e2e.log). Hosted endpoints and real third-party buyer data were not used.
'''+tests
    docs['FRONTEND_VALIDATION_REPORT.md'] = '# Frontend validation\n\n'+tests+'''Role flows use real HTTP APIs and independent browser contexts, not API mocks. Existing tests were repaired for changed Home navigation and accessible button/select names, and made to honor isolated state. The GPU policy is explicitly adapted to reported usable VRAM. Mobile 390px overflow, navigation open/close, skip focus and reduced-motion preference were checked; desktop physical-job, market and explanation screens were captured. Two representative screenshots were visually inspected.

Remaining review: complete screen-reader navigation, 200% zoom/reflow, every chart alternative, full offline/reconnect UI behavior, long-text edge cases and every role/error state. API event reconnect is covered by regression tests; that is distinct from a complete browser-network-disconnection study.
'''
    docs['ACCESSIBILITY_REPORT.md'] = '''# Accessibility

Automated axe checks with WCAG A/AA tags returned **zero violations** on sign-in and consumer Home at 390px. [Raw results](accessibility-axe.json). Actual browser checks cover keyboard skip-to-main focus, mobile navigation, 390px document width and reduced-motion emulation. Existing semantic labels and source-linked UI were preserved.

BLOCKED for a complete WCAG 2.2 AA conformance decision: a qualified manual review must cover screen readers, 200% zoom/reflow, focus order/return in every dialog, chart/table alternatives, all roles and dynamically changing errors. Automation on two views cannot certify the whole console. Use the [W3C criteria](https://www.w3.org/TR/WCAG22/) as the review checklist; record browser/assistive technology, view, steps and result for each criterion. [Frontend report](FRONTEND_VALIDATION_REPORT.md).
'''
    docs['RESEARCH_REPRODUCIBILITY_REPORT.md'] = '''# Research reproducibility

PASS: two independent frozen runs produced **12 byte-identical evaluation artifacts**. Each includes source card, configurations/splits/seeds or content manifests as appropriate. No research algorithm or threshold was changed before reproduction. [Hashes/configurations](experiment-manifest.json), research-summary.json and research-repeat-summary.json retain commands and durations. Figures are exported from the reproduced numbers, not hand-edited.

The connected system combines bounded source-grounded compilation, human approval, admission/market traces and independent monitoring; the held-out fixtures do not establish arbitrary legal interpretation. Planning uses the lagged historical signal; hindsight/oracle is separated. Runtime outcomes are successful lifecycle proxies with chronological availability cutoffs. Pricing labels are controlled configured strategies; no real collusion labels are inferred. Independent human agreement/support annotation remains pending; see ANNOTATION_PROTOCOL.md.
'''
    docs['RESEARCH_RESULTS_FINAL.md'] = '# Reproduced results\n\n'+f'''Study `{study['version']}`: 20 paired seeds × 90 jobs. Protocol monitor: 72/72 verdicts, zero unsafe accepts; event-presence baseline: 24/72 and 48 unsafe accepts. Pricing controlled detector F1 1.000; FSM accuracy {study['pricing']['fsm']['accuracy']:.4%}, log loss {study['pricing']['fsm']['log_loss']:.6f}. These remain controlled findings.

Runtime bound: 100% coverage on 46 held-out successful lifecycle proxies; p90 pinball loss 6,934 seconds versus 2,221 for the training-p90 baseline. The widened bound is not a useful production reservation estimate. Calibrated-minus-median modeled carbon delta: **{carbon['delta']:.6f} g/run**, paired 95% bootstrap interval **[{carbon['interval95'][0]:.6f}, {carbon['interval95'][1]:.6f}]**. There is no clear calibration benefit.

Within calibrated scheduling, carbon-aware averages 1845.709495 g modeled CO₂ and 48-minute p95 wait, versus policy-only 2014.563890 g and 21 minutes. Report completions (83.60 versus 83.65), energy and denominators together. New backfilling/aging baselines tie simpler arms at this light load; they do not establish a service advantage. The 50-case support benchmark passes developer-authored expectations; operator validation is pending.

Tables: publication-metrics.csv, publication-seeds.csv, scheduler-baselines.csv, runtime-baselines-slices.csv. Figures: scheduler-tradeoff.png/.svg and runtime-negative-result.png/.svg. Measured inputs, historical intensities, synthetic pricing controls, estimated power and counterfactual outcomes remain distinct. No real-world carbon saving or commercial collusion claim follows.
'''
    docs['EXPERIMENT_MANIFEST.md'] = '''# Experiment manifest

[Machine-readable manifest](experiment-manifest.json) records all 12 matching artifact hashes, source card, study version and scheduler configurations. Per-seed CSV and full private local study JSON include seeds, allocations, offers, audit traces and split boundaries. Source code is separately frozen by source-manifest.json; baseline application/environment lock and full local resolved environment are retained.

Commands: `python scripts/validate.py research`, then `python scripts/validate.py research --label research-repeat`, then `python scripts/export_research.py`. The second run uses a separate state directory. Reproduction is byte-identical in this documented environment; cross-platform OR-Tools/library determinism requires its own check. Original unsuccessful calibration findings are retained.
'''
    docs['ANNOTATION_PROTOCOL.md'] = '''# Independent annotation protocol — pending execution

Freeze the policy corpus and 50 support cases before annotation. Allocate two independent reviewers who did not author the expected answers. Remove system predictions while labeling. Group policy splits by template/paraphrase family; preserve source ID, exact source text, supported rule/value/unit, UTF-16/code-point span convention, ambiguity, unsupported semantics and executable expected outcomes. Record review time and confidence. For support cases, label diagnosis, cited evidence, permitted/forbidden actions, abstention and whether evidence is insufficient.

Have both reviewers label a stratified 30–40-case pilot including exceptions, negation, timezones, conflicting caps, missing evidence and embedded malicious instructions. Adjudicate disagreement with a third named reviewer, retaining both originals and reasons. Report rule agreement and categorical agreement, exact activation accuracy and unsupported-activation rate, then freeze the rubric before remaining cases. Keep related cases out of both training and holdout. Replace overlapping support-role fixtures with consenting partner incidents where possible.

No reviewer identities, agreement numbers or new human labels exist from this run. Access/consent and independent reviewer approval are the precise blockers. Publication must describe developer-authored labels until those steps actually occur.
'''
    docs['SECURITY_REVIEW.md'] = '# Security review\n\n'+fixes+'''Review scope: local source/tests and disposable services. Existing controls include salted PBKDF2, random session tokens stored as digests, HttpOnly/SameSite cookies, origin checks, scoped object reads, role revalidation, runner fences, hash-verified storage and bounded model suggestions. Route-derived authorization tests check anonymous/expired/wrong-role/wrong-tenant cases. Browser tests independently deny consumer approval and producer/loser access to private job data. S3 tests use moto, not cloud credentials.

References: [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS). This is a self-performed review, not an independent penetration test.

Residual risks: full-size evidence responses need operational size/retention controls; writes are globally serialized on PostgreSQL; trusted native templates do not isolate arbitrary untrusted code; password recovery/OIDC/token rotation and public onboarding need further design; shared HMAC secrets do not provide public-key third-party verification. Production cookies/TLS, actual bucket policy and private logs were not audited. Five recorded authorization product observations were left unchanged; no spending authority was expanded. Never expose private env/state files. [Dependency results](DEPENDENCY_AUDIT.md), [limited secret scan](secret-scan.json).
'''
    docs['PERFORMANCE_VALIDATION.md'] = '# Bounded performance\n\n'+''.join(f"- `{row['endpoint']}`: 100 samples, concurrency 4; p50 {row['p50_s']*1000:.2f} ms, p95 {row['p95_s']*1000:.2f} ms, target p95 <2 seconds: {row['gate']}.\n" for row in perf['measurements'])+f'''
SQLite confirmation contention p95 {race['confirmation_p95_s']*1000:.2f} ms over 2,000 competing calls; PostgreSQL p95 {pg_race['confirmation_p95_s']*1000:.2f} ms over 50 competing calls, both concurrency 2. Retries returned identical bookings. These are contract-level transactions with controlled inventory, not hardware throughput.

Artifact transfer: {perf['artifact_transfer']['bytes']} bytes in {perf['artifact_transfer']['seconds']:.6f} seconds with hash verification. Environment: Windows 11, SQLite WAL for HTTP, warm small loopback fixture, actual native runner. [HTTP measurements](performance-http.json), [SQLite race](contention-1000.json), [PG race](contention-postgres.json).

Do not extrapolate to WAN, large queues or production capacity. The quote endpoint is measured separately above. Sustained worker throughput and p95 event delivery under deployment load have not been established. Rollback sequence gaps retain a three-second grace, so a universal two-second notification target is not established. Long-duration load/SLO and storage performance need a separately declared staging workload.
'''
    docs['DEPENDENCY_AUDIT.md'] = '''# Dependency audit

Evidence: npm-audit.json for the locked frontend; pip-audit.json for the backend/tool environment; gpu-pip-audit.json for the separate GPU runtime. Frontend/backend scans report no known advisories. The GPU scan has no findings in audited packages but explicitly SKIPS torch 2.15.0+cpu and torchvision 0.29.2+cpu because those wheel versions are absent from its PyPI advisory lookup. GPU audit coverage is therefore PARTIAL, not a complete clean bill of health. Vendor/security review or advisory coverage for those exact wheels remains required before a production release.

Initial backend advisories concerned the local old pip tool, upgraded locally. The separate GPU scan found vulnerable setuptools, and a direct upgrade conflicted with the original torch constraint; the official CPU index resolver selected a compatible updated torch/torchvision pair. Its dependency check and physical GPU/browser checks were rerun. No system installation or paid service was used.

Before/after JSON is retained; advisory feeds may repeat identifiers. Refer to package/advisory lists rather than summing duplicate entries as distinct vulnerabilities. Locks describe installed versions; a zero-advisory scan is time-bounded and not proof of absence of vulnerabilities. GPU, application and audit/figure tool environments are separately recorded. CI was added locally and has not been pushed or run on GitHub.
'''
    docs['DEPLOYMENT_RUNBOOK_FINAL.md'] = '''# Deployment runbook

CURRENTLY DEPLOYED: older handoff records a Render Docker service and separate Neon pact-deploy database. VERIFIED HERE: local built frontend/API, worker, physical runner and disposable PostgreSQL startup/restore. NOT VERIFIED: exact hosted SHA, dashboard settings, actual bucket, TLS/cookie deployment behavior or cloud restore. BLOCKED: owner account access and explicit authorization for any production change. One public health probe timed out; hosted-health.json records UNCONFIRMED, not an outage conclusion.

1. Review the local source manifest/diff and pending draft PR; no push or merge was done.
2. Obtain owner access, identify the exact intended database/service and record current deployed SHA. Do not copy another teammate's private database settings.
3. Take and verify matching object/state and database backups; preserve signing keys in a secret store. Get explicit production migration/deployment approval.
4. Drain all old API/worker/runner writers before the event-order change. Run migrations through 0007 in a dedicated release step; the current entrypoint upgrades automatically unless PACT_RUN_MIGRATIONS=0.
5. Configure durable private object storage, explicit HTTPS origin, Secure cookies, stable signing secret, scoped runner credentials and the approved full model digest. Run one API+worker replica until supervision/load is measured.
6. Build Docker from repo root, validate staging startup/import/worker logs and artifact verification. No Docker engine was available for an actual local image build in this run.
7. Enroll an authorized runner with the verified region/power signal, perform the real producer/consumer workflow, check telemetry coverage, signed receipt and capacity release.
8. Rehearse forward recovery or restore into a separate environment. Database downgrades drop new data; do not use them as automatic production rollback.

Critical limitation: Docker entrypoint backgrounds the worker without a process supervisor. Health checks only database reachability, not worker/GPU/object readiness. Add service supervision/readiness/alerts before a pilot. Platform restart retention and RPO/RTO remain owner responsibilities.
'''
    docs['BACKUP_RESTORE_VALIDATION.md'] = '# Backup/restore validation\n\n'+docs['RECOVERY_DRILL_REPORT.md'].split('\n', 2)[2]+'''\nOperational correction: copying artifacts first while writers continue can leave later database references without copied objects. Quiesce writers for the whole backup pair, or establish a database snapshot and copy all objects reachable from that snapshot with suitable retention. The local drill quiesced writers. The production procedure must also preserve dataset/study outputs and signing material; artifacts-verify covers object references only.
'''
    docs['ENVIRONMENT_CONFIGURATION_CHECKLIST.md'] = '''# Configuration checklist

| Variable/group | Local validation | Before staging/production |
| --- | --- | --- |
| PACT_DATABASE_URL, PACT_DB_TLS | Explicit disposable SQLite/PostgreSQL, no private .env | Dedicated backed-up database; TLS where hosted |
| PACT_STATE_DIR, PACT_SOURCE_DIR | Ignored isolated state; approved manifest sources | Durable state/retention plus source snapshots |
| PACT_URL, PACT_SECURE_COOKIE | HTTP loopback 8766, Secure off | Explicit HTTPS origin and Secure on |
| PACT_SIGNING_SECRET, admin secret | Generated local fixture state, never printed | Stable secret store, rotation/backup policy |
| PACT_RUNNER_ID/TOKEN | Scoped enrolled runner, hidden | Host-owned secret storage and revocation procedure |
| PACT_GPU_PYTHON/ENGINE | Separate pinned CPU torch + driver kernels | Verified hardware/runtime combination |
| PACT_MODEL_WEIGHTS_SHA256 | Full local approved digest pinned | Same approved immutable model digest |
| PACT_ARTIFACT_BACKEND, S3/AWS variables | Local; S3 behavior mocked by moto | Real private durable bucket/policy/region, no public credentials |
| GROQ/provider variables | Explicitly disabled except controlled mocked tests | Owner authorization; fallback and shared budget retained |
| PACT_RUN_MIGRATIONS | Disposable runner only | Dedicated approved release procedure |

Do not place secrets in reports, git, screenshots or shell output. Root `env` is preserved and now ignored. Real bucket, hosted dashboard configuration and rotation are not verified.
'''
    docs['FINAL_TECHNICAL_REPORT.md'] = '# Authoritative technical inventory\n\n'+'''The implemented application is a React/TypeScript console served by FastAPI. SQLAlchemy/Alembic stores organizations, members, memberships, sessions, policy versions, runners, jobs/attempts, offers/quotes/bookings, artifacts, events, reviews, rate hits and incidents. Current head is 0007. The research worker leases runs; the native runner authenticates, downloads hash-linked input, executes an approved template, reports telemetry/outcome and journals uncertain callbacks. Artifacts use local/S3 interfaces with content-addressed verification.

Policies are bounded typed constraints with source spans and privileged review. Admission and dispatch enforce current/pinned terms; independent monitoring reconstructs policy/protocol outcomes. Quotes expire without holding capacity; confirmation rechecks policy/offer versions under locks. One exclusive GPU and 1–16 image MobileNet embeddings are supported. Internal credits and adjustments are usage evidence, not a settlement ledger or payments.

Membership invitations and workspace switching, reviewer inbox, counterfactual preview, incident resolution, pagination and shared limits exist and have current local evidence. Counterfactuals create a new draft only on explicit acceptance; fixed suggested steps do not guarantee a feasible option, particularly from a zero budget. Live runtime remains 38 + 3 × images seconds. Research runtime models/CP-SAT are separate; no validated runtime model has been silently wired into live dispatch.

Formal synthesis, external FlexFringe, arbitrary workloads, distributed multi-GPU training, public billing, OIDC and independent commercial collusion determination remain future work. Deployment, research validation and pilot validation are distinct states. Historical reports/plans do not override the source manifest and current evidence.

Literature correction verified against primary sources: [Ji et al. SRAP-Agent](https://aclanthology.org/2024.findings-emnlp.15/) concerns resource-allocation policy simulation; [Wu and Tu, Layer-Condensed KV Cache](https://arxiv.org/abs/2405.10637) concerns inference memory, not allocation agents. The original slide/report files remain historical; use this correction before re-presenting the mismatched row. No exhaustive literature review or stronger novelty claim was added.

'''+fixes+tests+commands
    docs['FINAL_TESTING_REPORT.md'] = '# Final testing\n\n'+tests+'''The final suite passed again in a fresh locked environment (clean-install-summary.json), and a separate repeat run is retained (final-repeat-summary.json). Five default-suite PostgreSQL skips ran and passed separately; the sixth skip explicitly duplicates another authorization test. One upstream Starlette/httpx TestClient deprecation warning remains; the actual HTTP/browser tests also passed. CI source is prepared locally but has not been remotely executed.\n\n'''+gates+commands
    docs['DEMONSTRATION_GUIDE.md'] = '''# Faculty demonstration

Use the isolated local environment and the recorded GPU lock; never use a private production database to seed demo fixtures. Run scripts/browser_validation.py for an automated rehearsal on port 8766. Local credentials stay in ignored validation state.

1. Draft “Jobs must finish by 17:00.” Show missing date/timezone and blocked approval. Create a corrected source-linked revision and have the reviewer approve it.
2. Producer publishes the verified GTX 1650 slot. Consumer selects the reviewed 3 GiB agreement (driver reports 4095 MiB). Two consumers quote; confirmation creates one accepted reservation.
3. Observe actual CUDA runner execution. Download the 4×960 embeddings and rehash bytes. Explain inference timing versus total service timing and board telemetry coverage.
4. Compare the identical shared receipt on both sides; demonstrate producer denial of the consumer's private job/output and loser denial of the booking.
5. Request 32 GiB and show admission rejection. Explain independent monitoring using a deliberately invalid controlled trace; do not call prevented admission an actual forbidden physical dispatch.
6. Run the five-arm replay and show source/model origin labels, scheduler trade-offs, per-seed CSV and the negative runtime-calibration result.
7. Show pricing FSM/intervention and legitimate scarcity control; a controlled pattern is not proof of real commercial collusion.
8. Explore a budget what-if, accept a draft revision and show the original is unchanged. Claim/resolve the deliberate stale-heartbeat fixture; explain why uncertain real execution requires proof of stop before capacity release.
9. Show the cold PostgreSQL matched restore evidence. State the blocked hosted/pilot/human-label and manual accessibility gates explicitly.

Fallback if hardware is unavailable: display the recorded verified output and hashes, label it a recorded run, and mark live execution blocked. Never present simulator callbacks as fresh GPU execution.
'''
    docs['FINAL_RELEASE_ASSESSMENT.md'] = '# Final release assessment\n\n'+tests+fixes+'\n'+gates+'''## Readiness decisions

| Intended release | Decision | Required next action |
| --- | --- | --- |
| Local academic demonstration | PASS within recorded single-host scope | Rehearse with the pinned GPU environment and exact dataset bytes |
| Reproducible research artifact | PASS | Preserve all manifests, environment locks and adverse results |
| Research submission with generalization claims | BLOCKED | Independent labels/review, claim scope and license/source checks |
| Hosted demonstration | BLOCKED | Owner access, exact deployed SHA, authorized rollout, durable storage and hosted GPU transaction |
| Restricted private GPU pilot | BLOCKED | Two authorized hosts/teams, workload agreement, monitoring, recovery targets and observation window |
| Public/commercial production | BLOCKED | Independent security/accessibility review, isolation, accounting/settlement, identity recovery, operational/SLO evidence |

'''+blocked+'''The working tree intentionally contains the reviewed implementation/test/documentation patch and the user's pre-existing report; no local commit, push or merge was performed. `source-manifest.json` identifies the exact tested executable content. `working-tree.txt` records filenames only. No production migration or deployment modification occurred. Recommended next action: review this patch and the blocked-gate procedures, then provide authorized staging/account access and independent reviewers for the remaining external gates. Do not equate this local demonstration with a public marketplace release.
'''
    docs['FINAL_PROJECT_STATUS.md'] = '# Final project status and report index\n\n'+tests+'''The safe local implementation and validation pass is complete within the documented scope. Three event/evidence defects and a corrupt-storage retry defect were fixed with failing-before regressions. Exact datasets, repeated research, physical GPU, browser roles, portable PostgreSQL, matched restore and bounded performance have real evidence. Full production/pilot, independent annotation and full accessibility decisions remain blocked or incomplete; see the release assessment.

'''+''.join(f'- [{name}]({name})\n' for name in sorted(docs) if name != 'FINAL_PROJECT_STATUS.md')
    docs['PROGRESS_TRACKER.md'] = '# Progress and resume tracker\n\n'+'''| ID | Priority/component | Initial state | Changes/files | Evidence | Final state/blocker |
| --- | --- | --- | --- | --- | --- |
| P0-00 | Repository/audit | main checked out | Requested sasha-work; preserved untracked files; audit | IMPLEMENTATION_AUDIT.md | PASS |
| P0-01 | Baseline/environment | No Python on PATH | Bundled 3.12, project/GPU venvs, pinned locks, repeat-safe driver | baseline/final summaries | PASS |
| P0-02 | Datasets | 6/12 exact | Guarded approved Git-byte restoration, retained -text | dataset-restored.json | PASS |
| P0-03 | Events/evidence | Truncated replay/export; unsound gap timer | db.py, outbox.py, api.py; independent regressions | before logs, final tests, PG slow writer | PASS |
| P0-04 | Storage | Corrupt duplicate silently accepted | storage.py, local/moto retry tests | recovery-before.log, final tests | PASS |
| P1-05 | Migrations/recovery | Historic claims | Older schema retention, drift check, portable PG, cold dump/restore/hash/signature | postgres summary/tests/restore | PASS local |
| P1-06 | UI/roles | New screens unverified | e2e roles/exchange/workspace, axe, isolated server supervisor | browser-e2e.log, accessibility-axe.json | PASS scoped; manual audit BLOCKED |
| P1-07 | Physical GPU | Inventory only | prepare, actual CUDA jobs, negative input/model/timeout, independent output verifier | gpu logs/JSON, browser receipt | PASS single host; more failure/host combinations pending |
| P1-08 | Research | Historic numbers only | Two independent frozen runs, 12 identical outputs, CSV/figures/manifests | experiment-manifest.json | PASS reproduction; independent labels BLOCKED |
| P1-09 | Security/performance | Existing matrix | Hash/tenant/fence regressions, audits, 1,000 SQLite/25 PG races, HTTP measurements | security/performance/dependency reports | PASS bounded scope; external review/soak pending |
| P1-10 | Deployment/docs | Stale instructions | Local runbooks, backup correction, CI source and authoritative report | documentation/index | PASS local preparation; hosted/Docker/account checks BLOCKED |
| P0-11 | Final regression | Earlier failures retained | Fresh database per invocation; rerun after last application fix | final and final-repeat summaries/source manifest | See final counts; no aggregate production claim |

Unfinished tasks, in order:
1. Owner: supply authorized Render/Neon/bucket access, confirm deployed SHA and backup; approve any production migration/deployment separately.
2. In staging: drain all old writers, verify 0007, durable private bucket, supervision/readiness and real hosted GPU transaction; test image build on a Docker host.
3. Independent reviewers: execute ANNOTATION_PROTOCOL.md and full screen-reader/zoom/chart accessibility checklist.
4. Operator: run long outage/reconnect, sustained write/event-latency, live cancellation/restart combinations and load tests at a declared service scale.
5. Partner: authorize a second physical host/team, retention and workload collection; measure a pilot rather than infer production value from synthetic races.

Resume by reading FINAL_RELEASE_ASSESSMENT.md, source-manifest.json and latest summaries. Preserve `env` and the pre-existing status report. Do not push, merge or change production without new authorization. Never copy ignored state/secrets into reports. CI is prepared locally, not remotely executed.
'''
    for name, content in docs.items():
        (OUT / name).write_text(content.split('\n', 1)[0] + '\n\n' + prefix + content.split('\n', 1)[1].lstrip(), encoding='utf-8')
    (OUT / 'working-tree.txt').write_text(subprocess.check_output(['git', 'status', '--short'], cwd=REPO, text=True), encoding='utf-8')
    print(f'Wrote {len(docs)} evidence-linked documents; source fingerprint {fingerprint}')


if __name__ == '__main__':
    main()
