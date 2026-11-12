# Deployment runbook

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

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
