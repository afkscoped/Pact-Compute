# Dataset integrity

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

All **12/12** entries now match the approved SHA-256 manifest. Six initial mismatches were CRLF conversion only: the three active Alibaba CSVs and three acquisition guides. Restoration used exact Git blobs only after checking both the manifest hash and normalized equality to current bytes; substantive local edits would be refused. No manifest values were changed and no large dataset was redownloaded.

Fresh import verifies 7,064 GPU pods, 185 successful lifecycle proxies and 1,344 in-window carbon intervals. Schema `pact-dataset-1`; snapshot identity and complete source provenance are in [experiment-manifest.json](experiment-manifest.json). The raw carbon file has 1,345 entries; the endpoint interval is excluded by the declared window. Import checks duplicate/missing identities and contiguous intervals. CUAD/ContractNLI/LEDGAR remain auxiliary archives, not integrated benchmark labels. Guides are not downloads.

Evidence: [current check](dataset-check.json), [restoration with captured pre-write hashes](dataset-restored.json), research-import.log and final pytest. Repeat `python scripts/validate.py datasets`; only use `--restore-datasets` when exact approved Git blobs and line-ending-only differences are established.
