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

## 2026-08-26 08:10 — E4: synthetic occlusion benchmark (KEY RESULT)

4180 cuts (clean observed runs >=12f, all gap sizes tested per site, competitors =
all observed points at re-entry frame). Top1 rank of TRUE continuation:
- gap<=10: cv2 and bal8 both ~94-100% (confirms current regime is easy)
- gap 15: bal8 86.6% vs cv2 71.2%
- gap 20: bal8 85.4% vs cv2 52.8%
- gap 30: bal8 61.8% (top3 91.8%) vs cv2 23.5% (67.7%)
Kalman CA far worse than LS fits everywhere (err q90 up to 5945px @k=30) -
simple direct fitting beats the hand-tuned filter; consistent with E1.

Calibration for gap-dependent gates (bal8): median err 0.9/1.9/3.4/7.7/14.5/23.2/60.3 px
and q90 6.9/16.5/31.0/65.6/108.6/210.1/453.1 px at k=2/4/6/10/15/20/30.

ACTIONABLE: raise max_gap_frames 10->30 with bal8 scoring + k-dependent gate.
Caveat: synthetic cuts do not model contact-induced velocity breaks; expect worse
near hands/catches (which the 113 labels already flag as failure zone).

Artifacts: scripts/e4_synthetic_occlusion.py, data/e4_synthetic_occlusion.json,
reports/e4_report.md.

## 2026-08-26 08:30 — E6b/E6c: widened candidate universe (gap<=30)

E6b (raw widening): exposed PHANTOM TRACKLET problem - legacy CSVs contain Norfair
Kalman estimates during occlusions; long-gap 'thieves' with tiny errors were often
predictions, not observations. Also pooled E4 calibration misfit the youtube clip
(0 accepts at short gaps).

E6c v2 fixes: observed-only join (drop 596+547 phantom rows), per-video synthetic-
cut calibration (ident-balls q90@g10=147.7px vs youtube 47.4px - 3x difference!),
gap-normalized assignment costs err/q90(gap).

Results:
- ident-balls: rank1 accepts 29 (19 correct, 0 wrong); global 31 links,
  conflicts 0, labeled fp 0, 11 new links; chains 27->16, max len 6.
- youtube: rank1 accepts 14 (5 correct, 0 wrong); global 17 links, fp 0.
- Demotions when widening: 22 labeled pairs drop rank (17 of them human-labeled
  WRONG) -> widening actively dethrones greedy's mistakes.
- Per-video calibration matters enormously (motion scale differs 3x).

CONFIG TO ADOPT (experiment-land): observed-only points + bal8 scoring +
per-video q90(gap) gates + normalized-cost successor assignment.
Precision-first: zero wrong accepts on both labeled videos; recall limited by
tight gates on fast footage (future: per-regime calibration via E3c timeline).

Artifacts: scripts/e6b_wide_universe.py, scripts/e6c_wide_universe_v2.py,
data/e6c_wide_v2.json, reports/e6b_report.md, reports/e6c_report.md.

## 2026-08-26 08:45 — E6d/E6e: visual QA + physical consistency check

E6d rendered calibrated chains over the identical-balls video (reports/e6d_chains_*.mp4,
sample frames in reports/frames/). Vision inspection findings:
- Parabolic trails render correctly; long-gap bridges visible with labels.
- obs=1 frames confirm detector misses hand-held balls; obs=0 at f950 shows TOTAL
  detector dropout with 3 balls visible -> wide-gap bridges are essential.
- FALSE-POSITIVE tracklets exist: static blobs on background objects (white eggs,
  c49) and non-ballistic horizontal trails (shirt/arm). They pollute candidates.
  NEXT: physics-based tracklet filter (static/low-dynamics demotion).

E6e same-frame violation check: 0 violating chains at gate scales 0.8/1.0/1.3 on
both videos. Structurally guaranteed by successor formulation (candidate starts
strictly after source ends) - kept as regression test. Labels: tp 17/20/20 at
scales .8/1/1.3 with fp=0 everywhere (ident-balls); youtube stable at 2/3/3 fp=0.

Artifacts: scripts/e6d_render_chains.py, scripts/e6e_consistency.py,
reports/e6d_chains_identical_balls_trick_000_018.mp4, data/e6e_consistency.json.
