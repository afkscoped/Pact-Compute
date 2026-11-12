# Output verification

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Independent output: `b9b60985c98da53d9c36603a43cbe8ce536494722ab68cd8b8ff4c279aa4a28f`. Approved weights: `5c1a416349c4cf298f2a6a5e2600ed0ee55e604713578f5e74e6bc8bcaef7997`. Kernel bytes: `411e482d8fb8c14a4ff0d26b7120d2d0bb168155dc314324bb97e0ff1f149f17`. Inference 0.026674 seconds for two images in this recorded run. Every vector has 960 finite values; squared norm differs from one by less than 0.001; row identity and input hash match; distinct images yield distinct vectors. Browser tests rehash downloaded artifact bytes and compare the stored digest. Local browser validation pins the full weights hash.

Inference timing excludes loading, staging and orchestration. Board energy is not whole-machine or facility energy. Preserve raw output/evidence privately under `.local/validation/browser/verified`; generated summaries omit runner/session/signing credentials. Reproduce using `python scripts/gpu_validation.py` after preparing the approved weights. No GPU assertion is replaced with mocked inference.
