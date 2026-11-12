# Reliability

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

| ID | Fixed behavior | Regression evidence |
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

The isolated SQLite gate ran 1000 independent two-buyer races, 2000 competing confirmations and 1000 duplicate retries with zero double bookings. PostgreSQL repeated 25 races/50 confirmations/25 retries. Fixture resets between rounds are not physical executions. [SQLite metrics](contention-1000.json); [PostgreSQL metrics](contention-postgres.json).

Existing tests cover quote expiry, key/body conflicts, stale fences, lease loss, uncertain holds/reconciliation, cancellation, producer pause, bad output, unknown carbon and Groq throttling/fallback. New tests cover large replay bursts, reconnect cursors, corrupt storage retries, failed research with safe errors, research lease reclaim rejecting an old worker, runner journal retry after a lost response, runner restart window protection and interrupted publication with metadata rollback. failure-injection.log records the five added deterministic checks. Real local runner cancellation/restart, API restart, persisted session and HTTP SSE reconnect are recorded in runtime-recovery.json. Database cold restore/reconnect is verified; an operating-system/database crash with simultaneous live GPU work is not a tested outage soak. No claim is made about every hardware/network combination.
Backend: **260 passed, 0 failed, 0 errors, 6 skipped** ([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **5 passed** separately ([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed ([commands](final-summary.json)). Browser: **4 passed**, 0 failed ([report](browser-e2e.log)).

