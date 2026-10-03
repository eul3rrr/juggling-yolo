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

## 2026-08-26 09:00 — E7a/E7b: hand-event analysis

E7a: wrist-approach slopes on reviewed stitches (pose CSVs, conf>=0.5):
- WRONG pairs approach a hand much steeper at source end (median slope -4.9 px/f
  vs -0.2 for correct) -> wrong stitches concentrate at CATCH boundaries.
- Candidates mostly start receding (throw-like) in both classes.

E7b: naive catch+throw rescue of gate-rejected pairs HURTS: +3 correct but +5
wrong (precision 0.929 -> 0.806). Mechanism: one catch signature matches MULTIPLE
candidate throws (src 68 -> both correct 71 AND wrong 72 with identical source
signature). Hand events are necessary, not sufficient; need hand-inventory
mutual exclusion (one ball per hand) - future siteswap-style constraint layer.

Two-regime insight: synthetic-calibrated gates give 26/71 recall on labeled pairs
because contact occlusions produce large TRUE errors (e.g. 665px correct pair).
Mid-air occlusions (tight calibrated gates, 0 fp) vs contact occlusions (need
event logic, not error gates) are different regimes.

Artifacts: scripts/e7a_hand_events.py, scripts/e7b_hand_rescue.py,
data/e7a_hand_events.csv, data/e7b_hand_rescue.json, reports/e7a_report.md,
reports/e7b_report.md.

## 2026-08-26 09:15 — E9: physics/hand-aware tracklet filtering

E9a census: tracklet dynamics (speed, displacement, gravity-mode fraction).
Static background blobs cleanly identifiable (disp<15px, e.g. eggs tid48/41).

E9b naive filter (static + non-ballistic demotion): WRONG - kills held-ball
stubs (a held ball is static in image but is a real ball at a hand). Metrics
dropped (19 links/tp10). Lesson: cannot separate background from HELD balls
without hand context.

E9c hand-aware classification (AIRBORNE >=10% g-mode windows; HELD if near
wrist <110px; BACKGROUND static+far; SWEEP moving+far): identical-balls
states 45 AIRBORNE / 27 HELD / 2 SWEEP / 2 BACKGROUND; demote only [16,32,48,49];
global assignment UNCHANGED (31 links, tp20, fp0) - filter is free interpretability.
YouTube: no demotions needed, results unchanged (17/3/0).

Artifacts: scripts/e9a_tracklet_census.py, scripts/e9b_physics_filter.py,
scripts/e9c_hand_aware_filter.py, data/e9b_filter.json, data/e9c_hand_aware.json.

## 2026-08-26 09:30 — E10/E11: hand mutual exclusion + regime-split acceptance

E10: hand-inventory mutual exclusion on (source, hand) events, v2 keeps only
TIME-OVERLAPPING duplicates (sequential catch->carry->throw hops are legitimate):
ident-balls drops exactly 1 wrong, 0 correct. YouTube: nothing to drop.

E11 regime-split (air=calibrated gates, contact=hand-event arbitration):
- identical-balls: 38 accepts (21 air + 17 contact) -> 18 correct, 1 wrong.
- youtube: 15 accepts -> 3 correct, 0 wrong.
- Pooled: precision 0.955, recall 21/71.
vs E6c gate-only (44 accepts, 22 correct, 0 wrong): regime-split adds accepts
but LOSES one precision point and misses some correct gate-caught pairs; the
contact path's hand-start requirement (NEAR_HAND=110) is too strict and its
arbitration too permissive. MIXED result - keep gate-only as primary; contact
arbitration needs the full state machine (hand inventories + siteswap counts)
before it can beat error gates.

Artifacts: scripts/e10_mutual_exclusion.py, scripts/e11_regime_split.py,
data/e10_mutual_exclusion.json, data/e11_regime_split.json.

## 2026-08-26 08:05 — E8 family: Norfair motion-model comparison

E8 (association-level, dt50/hc5 fixed, existing YOLO detections):
- nofilter: 92 tracklets / med 23 pts (ident-balls)
- optvel (current default): 77 / 23
- optvel Q=1.0: 54 / 35.5
- constacc (custom CA Kalman, [pos,vel]-layout-compatible wrapper): 55 / 42
CA cuts fragmentation ~30% at the source. (Norfair 2.x API: string motion models
gone; must subclass FilterFactory; internals assume [pos,vel] x-layout.)

E8b synthetic recovery per variant: nofilter raw positions recover BEST
(0.987@20) -> suspicion: Kalman-smoothed stored points bias fits.

E8c raw-vs-estimate export: CONFIRMED - raw detection centers beat estimates
for observed rows everywhere (ident-balls ca: 0.905->0.964@20; vel: 0.949->0.987@20;
youtube vel: 0.821->0.895@20).

ADOPT: constant-acceleration association + export RAW centers for observed rows.
Best of both: 30% fewer fragments AND nofilter-level stitch recovery.

Artifacts: scripts/e8_norfair_models.py, scripts/e8b_model_recovery.py,
scripts/e8c_raw_vs_est.py, data/e8/*.csv+json.

## 2026-08-26 08:20 — E15: detector headroom probe

E15 grid (relaxed conf/imgsz on sampled frames): conf0.05/sz960 reaches 100%
recall vs Norfair-kept points but 4.86 dets/frame (FP flood); conf0.15/sz960
(= current settings) 0.988 recall, 2.57 dets/frame. GT is circular (Norfair's
own kept points), so treat as consistency check only.

E15b dropout forensics (651 frames with obs<3 in tracked run):
- Vision on dropout_f590: 3 balls clearly visible (1 air + 2 held); raw YOLO
  detection CSV at f590 contains 2 class-32 detections (conf 0.25/0.21) - the
  held balls WERE detected by the raw detector.
- Root cause of dropouts is NOT raw-detector blindness: it is the conf=0.15
  threshold + association losses. 771/2456 detections (31%) sit below conf 0.3;
  ByteTrack-style two-tier association could recover them.
- 486/1029 frames have <3 raw detections; 543 have >=3.
- FP sources for class 32: white eggs on the table (bottom-left) and lamp/
  bottle shapes - visible in dropout frames.

IMPLICATION: detector upgrade priority is (1) low-conf tier in association
(ByteTrack-style), (2) fine-tune/heatmap detector for held-ball states, not a
new backbone. Held balls near faces/hands are the systematic blind spot.

Artifacts: scripts/e15_detector_headroom.py, scripts/e15b_dropout_probe.py,
data/e15_detector_headroom.json, data/e15b_dropouts.json,
reports/frames/dropouts/*.png.
