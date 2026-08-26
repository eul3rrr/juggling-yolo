# Overnight Results Log

Format: one entry per experiment/finding. Newest at BOTTOM. Keep entries factual:
what was run, on what, key numbers, verdict, artifact paths.

---

## 2026-08-26 07:05 — E1: motion-model rescoring of reviewed stitch candidates

Harness: reproduces all 113 shipped stitcher outputs EXACTLY (max err diff 0.000000)
from legacy pre-a77cc5d CSVs (git show 633d7d3). Discovered current detections/*.csv
were regenerated post-hoc with observed-only semantics -> shipped candidates came from
Norfair-estimate-inclusive points. Legacy snapshots stored in experiments/overnight/data/legacy_csv/.

Models scored per pair (same candidate universe), ranked within source, vs 113 labels:
- cv2 (shipped): AUC 0.871, correct-med 107px, top1 95.8%, MRR .979, H2H 22/24
- cvlsN (LS linear, N=3..12): ~= baseline (AUC 0.870-0.875)
- bal8 (x lin / y quad, last 8 pts): top1 97.2%, MRR .986, H2H 23/24, AUC .877
- bal12: best AUC 0.884, correct-med 96.3px
- kalman CA filter: AUC 0.860 (no better than LS)

Verdict: ballistic scoring yields a small real improvement (curved-flight cases where
CV underestimates curvature, e.g. src=50: 237->12 px). But gains are marginal overall:
scoring model is NOT the bottleneck; candidate ambiguity + candidate availability are.
Wrong-labeled rows have near-zero margins under ANY of these models (checked medians).

Artifacts: scripts/e1_ballistic_rescore.py, scripts/e1_repro_check.py,
data/e1_pair_scores.csv, data/e1_metrics.json, reports/e1_report.md.
Methodological bug found+fixed during E1: initial _fit_predict measured distance from
origin instead of query point; caught via hand-computed probe (src=43: expected ~6px,
got 699). All numbers above are post-fix, validated against shipped errors.
