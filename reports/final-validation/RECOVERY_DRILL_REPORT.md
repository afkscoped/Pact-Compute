# Recovery drill

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

PASS for an isolated PostgreSQL drill: upgrade a fresh old schema to head; write real artifact metadata/bytes and signed evidence; stop test writers; copy artifact/signing state; pg_dump; create a separate empty database; pg_restore; start cold verification subprocesses against the restored database and state. `artifacts-verify` and original evidence signature verification passed. [Results](postgres-summary.json), [verifier output](postgres-restore.log).

SQLite separately verifies retained old-schema data, latest migration rollback/forward, ORM drift and cold matched object restoration. Deliberate byte corruption is rejected. Production snapshots, RPO/RTO, cloud bucket versioning and disaster-region recovery remain unverified. Do not run restoration against an existing production database. For a partner drill, obtain a verified backup/approval, restore into a new staging database and private object prefix, verify all hashes/signatures, then inspect a real receipt/output before permitting dispatch.
