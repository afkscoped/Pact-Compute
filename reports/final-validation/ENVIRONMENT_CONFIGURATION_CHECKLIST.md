# Configuration checklist

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

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
