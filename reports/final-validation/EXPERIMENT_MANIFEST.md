# Experiment manifest

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

[Machine-readable manifest](experiment-manifest.json) records all 12 matching artifact hashes, source card, study version and scheduler configurations. Per-seed CSV and full private local study JSON include seeds, allocations, offers, audit traces and split boundaries. Source code is separately frozen by source-manifest.json; baseline application/environment lock and full local resolved environment are retained.

Commands: `python scripts/validate.py research`, then `python scripts/validate.py research --label research-repeat`, then `python scripts/export_research.py`. The second run uses a separate state directory. Reproduction is byte-identical in this documented environment; cross-platform OR-Tools/library determinism requires its own check. Original unsuccessful calibration findings are retained.
