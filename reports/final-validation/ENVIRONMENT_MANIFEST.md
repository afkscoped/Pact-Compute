# Environment manifest

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Windows 11, CPython 3.12.14, Node 24.11.1, npm 11.6.2. Python came from the Codex bundled runtime; no system Python installation was performed. Backend/application lock: `pact-compute/requirements-win-py312.lock.txt`. Audit/figure tool environment: [resolved packages](environment-final.resolved.txt). GPU environment: [resolved packages](gpu-environment.resolved.txt). GPU runtime: `2.15.0+cpu`, CUDA Driver API `13.1`, GTX 1650. Portable PostgreSQL 18.7 ran only on loopback with disposable databases. No Docker engine was available.

The older Python 3.14 lock is historical; it does not describe this 3.12 validation. A fresh environment installed the exact new application lock and independently ran the final backend/Node/build suites: clean-install.log, clean-install-pytest.xml and clean-install-summary.json. The optional audit/plot tools have a separate requirements-validation-win-py312.lock.txt. The GPU uses CPU PyTorch for loading/preprocessing and actual NVIDIA Driver API kernels for inference. `torch.cuda.is_available()` is not the evidence for this path. A separate CUDA-enabled PyTorch engine was not validated.

From `pact-compute`, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/validate.py datasets
.\.venv\Scripts\python.exe scripts/validate.py final
.\.venv\Scripts\python.exe scripts/postgres_validation.py
.\.venv\Scripts\python.exe scripts/validate.py contention
.\.venv\Scripts\python.exe scripts/gpu_validation.py
.\.venv\Scripts\python.exe scripts/browser_validation.py
.\.venv\Scripts\python.exe scripts/validate.py research
.\.venv\Scripts\python.exe scripts/validate.py research --label research-repeat
.\.venv\Scripts\python.exe scripts/export_research.py
```

PostgreSQL needs the official portable binaries under `.local/postgres-runtime/pgsql/bin`.
Browser validation needs Edge, the built console, prepared model weights under `.local/validation/browser`,
and a separate `.gpu-venv` with the recorded GPU lock. It refuses an occupied port 8766.
It starts/stops its own API, worker and runner. It never attaches to the pre-existing listener on 8765.
All databases/providers are explicitly isolated; preserve private .env files.
