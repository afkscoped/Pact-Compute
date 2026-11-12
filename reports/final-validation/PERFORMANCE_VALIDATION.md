# Bounded performance

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

- `/api/v1/jobs?limit=20`: 100 samples, concurrency 4; p50 27.59 ms, p95 44.94 ms, target p95 <2 seconds: PASS.
- `/api/v1/jobs/preview`: 100 samples, concurrency 4; p50 31.55 ms, p95 40.65 ms, target p95 <2 seconds: PASS.
- `/api/v1/market/quotes`: 100 samples, concurrency 4; p50 13.39 ms, p95 119.23 ms, target p95 <2 seconds: PASS.

SQLite confirmation contention p95 31.14 ms over 2,000 competing calls; PostgreSQL p95 51.35 ms over 50 competing calls, both concurrency 2. Retries returned identical bookings. These are contract-level transactions with controlled inventory, not hardware throughput.

Artifact transfer: 44252 bytes in 0.006329 seconds with hash verification. Environment: Windows 11, SQLite WAL for HTTP, warm small loopback fixture, actual native runner. [HTTP measurements](performance-http.json), [SQLite race](contention-1000.json), [PG race](contention-postgres.json).

Do not extrapolate to WAN, large queues or production capacity. The quote endpoint is measured separately above. Sustained worker throughput and p95 event delivery under deployment load have not been established. Rollback sequence gaps retain a three-second grace, so a universal two-second notification target is not established. Long-duration load/SLO and storage performance need a separately declared staging workload.
