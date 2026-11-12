# Dependency audit

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Evidence: npm-audit.json for the locked frontend; pip-audit.json for the backend/tool environment; gpu-pip-audit.json for the separate GPU runtime. Frontend/backend scans report no known advisories. The GPU scan has no findings in audited packages but explicitly SKIPS torch 2.15.0+cpu and torchvision 0.29.2+cpu because those wheel versions are absent from its PyPI advisory lookup. GPU audit coverage is therefore PARTIAL, not a complete clean bill of health. Vendor/security review or advisory coverage for those exact wheels remains required before a production release.

Initial backend advisories concerned the local old pip tool, upgraded locally. The separate GPU scan found vulnerable setuptools, and a direct upgrade conflicted with the original torch constraint; the official CPU index resolver selected a compatible updated torch/torchvision pair. Its dependency check and physical GPU/browser checks were rerun. No system installation or paid service was used.

Before/after JSON is retained; advisory feeds may repeat identifiers. Refer to package/advisory lists rather than summing duplicate entries as distinct vulnerabilities. Locks describe installed versions; a zero-advisory scan is time-bounded and not proof of absence of vulnerabilities. GPU, application and audit/figure tool environments are separately recorded. CI was added locally and has not been pushed or run on GitHub.
