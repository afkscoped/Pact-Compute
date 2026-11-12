# Security review

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
Review scope: local source/tests and disposable services. Existing controls include salted PBKDF2, random session tokens stored as digests, HttpOnly/SameSite cookies, origin checks, scoped object reads, role revalidation, runner fences, hash-verified storage and bounded model suggestions. Route-derived authorization tests check anonymous/expired/wrong-role/wrong-tenant cases. Browser tests independently deny consumer approval and producer/loser access to private job data. S3 tests use moto, not cloud credentials.

References: [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS). This is a self-performed review, not an independent penetration test.

Residual risks: full-size evidence responses need operational size/retention controls; writes are globally serialized on PostgreSQL; trusted native templates do not isolate arbitrary untrusted code; password recovery/OIDC/token rotation and public onboarding need further design; shared HMAC secrets do not provide public-key third-party verification. Production cookies/TLS, actual bucket policy and private logs were not audited. Five recorded authorization product observations were left unchanged; no spending authority was expanded. Never expose private env/state files. [Dependency results](DEPENDENCY_AUDIT.md), [limited secret scan](secret-scan.json).
