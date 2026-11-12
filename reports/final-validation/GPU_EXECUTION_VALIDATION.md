# Physical GPU execution

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

PASS on **NVIDIA GeForce GTX 1650**, CUDA Driver API 13.1, `2.15.0+cpu`. Preparation compared real kernel embeddings with a CPU model reference. [Prepare log](gpu-prepare.log). Independent execution returned two distinct, finite, unit-normalized 960-dimensional embeddings, corresponding input hashes and an output SHA-256. A real child-process timeout exited 124; altered input hash and separately copied corrupted weights were rejected. [Independent results](gpu-independent-verification.json).

Browser workflows separately executed four-image jobs and an exchange booking with measured board power coverage, receipt, policy findings and capacity release. Driver-visible VRAM is 4095 MiB, below a literal 4 GiB requirement; tests explicitly reviewed a 3 GiB policy. They did not inflate hardware inventory. Arbitrary containers, multiple physical GPUs and distributed jobs remain outside this validation. Runner restart while executing every failure combination still needs a longer hardware exercise.
