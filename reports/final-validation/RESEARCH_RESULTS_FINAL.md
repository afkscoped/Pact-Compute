# Reproduced results

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Study `pact-study-2`: 20 paired seeds × 90 jobs. Protocol monitor: 72/72 verdicts, zero unsafe accepts; event-presence baseline: 24/72 and 48 unsafe accepts. Pricing controlled detector F1 1.000; FSM accuracy 79.3143%, log loss 0.548334. These remain controlled findings.

Runtime bound: 100% coverage on 46 held-out successful lifecycle proxies; p90 pinball loss 6,934 seconds versus 2,221 for the training-p90 baseline. The widened bound is not a useful production reservation estimate. Calibrated-minus-median modeled carbon delta: **-9.395375 g/run**, paired 95% bootstrap interval **[-29.086525, 9.058000]**. There is no clear calibration benefit.

Within calibrated scheduling, carbon-aware averages 1845.709495 g modeled CO₂ and 48-minute p95 wait, versus policy-only 2014.563890 g and 21 minutes. Report completions (83.60 versus 83.65), energy and denominators together. New backfilling/aging baselines tie simpler arms at this light load; they do not establish a service advantage. The 50-case support benchmark passes developer-authored expectations; operator validation is pending.

Tables: publication-metrics.csv, publication-seeds.csv, scheduler-baselines.csv, runtime-baselines-slices.csv. Figures: scheduler-tradeoff.png/.svg and runtime-negative-result.png/.svg. Measured inputs, historical intensities, synthetic pricing controls, estimated power and counterfactual outcomes remain distinct. No real-world carbon saving or commercial collusion claim follows.
