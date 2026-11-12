# Baseline testing

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

At baseline, 235 backend cases passed, 4 failed and 1 was skipped. All four failures were approved source checksum failures (environment/missing exact bytes), not fabricated replacement data. The 33 Node tests and production build passed. [Commands/timings](baseline-summary.json); [raw backend log](baseline-backend.log).

Two independent event-delivery tests then failed on the original code. A corrupt idempotent artifact retry, a real PostgreSQL slow writer and the long evidence export each had failing-before evidence. A later repeated full suite revealed configuration import/order and persistent fixture reuse; this test harness defect was corrected. Windows shared-temp permissions were avoided with workspace-local isolated temporary paths. These failures are retained rather than rewritten as successes.

Backend: **260 passed, 0 failed, 0 errors, 6 skipped** ([XML](final-pytest.xml), [log](final-backend.log)). PostgreSQL: **5 passed** separately ([XML](postgres-pytest.xml)). Frontend: **33 Node tests passed**, TypeScript/production build passed ([commands](final-summary.json)). Browser: **4 passed**, 0 failed ([report](browser-e2e.log)).

