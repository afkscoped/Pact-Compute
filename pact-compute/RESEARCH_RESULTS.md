# PACT-Compute research results

Reproduced locally on 13 November 2026: two independent frozen runs produced 12 byte-identical evaluation artifacts. See [current results](../reports/final-validation/RESEARCH_RESULTS_FINAL.md), [experiment hashes/configurations](../reports/final-validation/experiment-manifest.json) and [reproducibility report](../reports/final-validation/RESEARCH_REPRODUCIBILITY_REPORT.md). The numerical findings and limitations below remain unchanged; no independent human labels or real-world carbon reductions were added.

Study version pact-study-2, generated 12 November 2026. The results below come from the runnable publication study. The research review documents the source methods and where the implementation adapts them.

| Experiment | Test data | Baseline | PACT comparison |
| --- | --- | --- | --- |
| Contract protocol verification | 72 held-out trace cases across six independently specified families | Event presence baseline matched 24 of 72 verdicts and accepted 48 unsafe traces | Temporal monitor matched 72 of 72 verdicts and accepted zero unsafe traces |
| Pricing response detection | 120 labelled held-out episodes, including 30 configured response positives and 90 competitive, fixed-premium and scarcity controls | High markup produced F1 0.667 and 30 false positives | Matched cut versus sham detection produced F1 1.000 and zero false positives in these controlled scenarios |
| Pricing state prediction | 15,750 held-out action observations across 450 trajectories, including unlabeled frozen-agent trajectories | Majority action accuracy 74.94%, log loss 0.737 | A 13-state merged FSM reached 79.31% accuracy and log loss 0.548, with 100% state coverage |
| Runtime estimation | 46 chronologically held-out successful Alibaba GPU lifecycle proxies | Training median covered 52.17%. Training p90 covered 86.96% with 2,221 s p90 pinball loss. | One-sided calibrated bound covered 100% with 6,934 s p90 pinball loss and an average bound of 74,668 s |
| Scheduling | 20 paired seeds, 90 trace-derived jobs per seed, with common arrivals, provider offers and GB grid histories | Carbon-aware scheduling with median duration averaged 83.85 completions, 5.75 overruns and 1,855 g modeled CO₂ | With the calibrated duration, it averaged 83.60 completions, 5.60 overruns and 1,846 g modeled CO₂ |

The runtime result shows overconservatism. The calibrated bound was wider than a useful production estimate on this dataset, and its higher coverage came with substantially worse pinball loss. The replay limits the supported job horizon. The paired difference in estimated emissions between calibrated and median carbon-aware scheduling was about −9 g per run, with a 95% bootstrap interval from −29 to +9 g. The comparison provides no clear gain from this calibration on this workload.

Within the calibrated replay, the carbon-aware solver compared with the policy-only solver averaged about 169 g less modeled CO₂ and 27 minutes more p95 wait. Report both measures and the completion outcomes. These results depend on the scarcity scenario, forecast proxy, timing allowances and modeled power, so they should be repeated with partner workload measurements before making a production claim.

## Evidence interpretation

- The protocol test uses controlled fixtures with known expected verdicts. Independent partner contracts and annotators are needed for a general contract extraction claim. The existing 180-case extraction regression corpus is a separate check of supported text patterns.
- The pricing study trains two independent tabular agents for 160 repeated inventory-market episodes. It freezes the policies for evaluation, then uses distinct episode sets for fitting the FSM, calibrating thresholds and testing. Labelled positives contain a configured price response. Frozen learned policies are excluded from those labels. The detector results establish performance against these synthetic controls.
- The runtime split uses 102 training, 37 calibration and 46 test lifecycle proxies, ordered by arrival. The lifecycle includes scheduler-to-deletion time and may differ from pure GPU compute time. The filtered sample excludes unsuccessful and censored observations.
- The allocation study reports paired comparisons on public trace-derived demand. The market, power, and most job durations are modeled. The historical intensity series scores outcomes. The planning condition uses only earlier observations as a forecast proxy.

## Artifacts for the paper

- [Aggregate results CSV](.local/evaluations/publication-metrics.csv)
- [Per-seed scheduler CSV](.local/evaluations/publication-seeds.csv)
- [Full study evidence, dataset manifest, traces and trained parameters](.local/evaluations/publication-study.json)
- [Primary-source literature review](RESEARCH_REVIEW.md)

The Explainable AI console provides the same comparisons, with an interactive Q-table, intervention chart, FSM transition graph and runtime view. Regenerate the study from the README command before changing any threshold or dataset, and retain earlier results if a new condition performs differently.
