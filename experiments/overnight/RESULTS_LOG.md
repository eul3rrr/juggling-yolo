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

## 2026-08-26 07:25 — E3: shared-gravity constrained stitching + regime discovery

E3 (shared-g scoring): estimating one image-space gravity per video and fixing it
inside candidate y-fits changed NOTHING vs free ballistic fits (<1px inside short
windows/horizons; metrics identical). Negative result: constraint has no leverage
at gap<=10 frames with 6-12 point windows.

E3b (gravity distribution): per-window y-accelerations (dt==1 8-pt windows,
observed-only join between legacy+regenerated CSVs: kept=2178/2774) are sharply
BIMODAL in clip 1: mode A ~ +0.12..0.25 px/f^2 (n~550) and mode B ~ +1.8..2.0
px/f^2 (n~390), plus negative tail (hand-propelled/held segments).

E3c (regime timeline): classifying windows by accel mode + rolling vote recovers
the clip edit structure EXACTLY, unsupervised, physics-only:
  [0-263 normal][263-764 SLOW][764-1079 normal], playback factor sqrt(gN/gS)=4.13x.
Matches the documented normal/slow/normal edit. Cross-referencing reviewed pairs:
only 2 pairs cross regime boundaries (1 correct/1 wrong) -> no label conclusion,
but the timeline enables per-regime time-base normalization for future gating/
prediction (a slow-mo segment inflates pixel velocities 4x otherwise).

Artifacts: scripts/e3_shared_gravity.py, scripts/e3b_gravity_hist.py,
scripts/e3c_regime_timeline.py, data/e3_pair_scores.csv, data/e3_gravity.json,
data/e3c_regime_timeline.json/.csv, reports/e3_report.md.

## 2026-08-26 07:35 — E2: global one-to-one assignment vs greedy rank-1

Hungarian (scipy linear_sum_assignment) over source x candidate cost matrices
(bal8/bal12/cv2 costs from E1), no-match dummy columns priced at gate; compared
against shipped-style greedy accept-rank-1-under-gate across 6 percentile gates,
per video, scored against 113 labels as an acceptance classifier.

Findings:
- Greedy conflicts are REAL and frequent: 1-11 candidate tracklets claimed by
  2+ sources per setting. Shipped reconstruction pipeline silently resolves
  these by union-find chain merging.
- Global assignment: conflicts=0 always; at matched gates it trades ~2-5 TP
  for ~5-7 fewer FP. Best pooled F1 points move from .84-.86 (greedy) to
  .85-.89 (global), consistently higher precision at similar recall.
- All remaining FP at loose gates concentrate in the identical-balls clip;
  the YouTube clip's wrong candidates are already excluded by error gates.

Verdict: adopt global assignment over greedy when this leaves experiment-land;
combined with bal8/bal12 costs it is the best known automatic acceptance rule.
Still ceiling-limited: even perfect assignment of THIS candidate universe caps
at ~71 correct of 113 (candidates missing where fragmentation exceeded gap<=10).

Artifacts: scripts/e2_global_assignment.py, data/e2_sweep.json, reports/e2_report.md.

## 2026-08-26 07:55 — E6: chain-level global stitching (successor assignment)

Formulation: each tracklet gets <=1 successor via Hungarian on N x (N+N) matrix;
eligibility edges strictly increase time so result is cycle-free disjoint paths.
Dummy no-successor columns priced AT THE GATE (first attempt priced them at 0 ->
solver correctly refused all real edges; formulation bug caught immediately).

Results (bal8 costs, gates = error percentiles):
- identical-balls clip: global cuts FP hard at matched gates (g4: TP39/FP4 vs
  greedy TP42/FP11; conflicts 12 -> 0) while keeping corrConn 39/45 vs 43/45.
- youtube clip: global dominates outright (g5: TP23/FP0/conflicts0 vs greedy
  TP25/FP2/conflicts2).
- Chain stats: fewer, longer chains under global (ident-balls g5: 21 chains,
  mean len 3.14 vs greedy 27 @ 2.56).
- CEILING CONFIRMED: even optimal chaining leaves ~20 chains for 3 balls in
  clip 1. The gap<=10 candidate universe misses most true re-links. Next gains
  must come from WIDER candidate generation (longer gaps w/ ballistic prediction
  uncertainty growth), not better scoring of existing candidates.

Artifacts: scripts/e6_chain_flow.py, data/e6_chains.json, reports/e6_report.md.
