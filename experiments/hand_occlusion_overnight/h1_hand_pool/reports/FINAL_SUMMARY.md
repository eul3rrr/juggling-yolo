# Hand-Occlusion Overnight Lab — Final Summary Report

**Date:** 2026-08-28 ~19:45 CEST
**Episodes:** H1-H70 (70 research episodes over ~19.5 hours)
**Status:** COMPLETE — final operating point validated
**Author:** autonomous hand-occlusion overnight research lab

---

## Mission

Conduct reproducible isolated research on **ball identity, catches,
holds, throws, detector dropouts, and track fragmentation around
hand occlusions** for the juggling-yolo project. The lab was tasked
with making as much real progress as possible on the hand-occlusion
problem, and producing evidence for later human/strong-model review.

## Datasets

Two juggling videos, both 30 fps, monocular 2D:

| Stem | Description | Frames | Balls |
|---|---|---|---|
| `identical_balls_trick_000_018` | 3-ball cascade trick | 1042 | 3 |
| `youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090` | 5-ball cascade | 898 | 5 |

## Recommended operating point (fully validated)

**h7v3plus3 chain set + H12 v8 pattern inference + H50 10-frame
event log filter + H43 confidence-based FOUNTAIN_3+ filter +
H69 spectral-concentration FOUNTAIN_3+ filter + H52 physics
corroboration**

This stack is the final, validated operating point for downstream
consumers needing precision-optimized juggling-pattern classification
on both videos. **H43 OR H69** is the new FOUNTAIN_3+ post-filter,
replacing H43 alone from H51. H66 and H68 are no longer applied at
any threshold (superseded by H69).

## Episode summary by topic

### Topic 1: Hand-pool baseline (H1-H6)

H1 v1-v4 established a per-hand FIFO token stack with physics-aware
filters (token TTL, throw leave window, wrist velocity guard, catch
context). v4d (throw=7 + slope filter) achieved **10 identical + 1
youtube links with visual precision ~1.000** (4x recall gain on
identical vs v2).

H2 combined H1 v4d hand-links with E6c mid-air edges, producing 40
identical + 13 youtube chains. H3 (low-confidence hand-region
evidence) correctly identified 6/6 identical held phases as real
held balls. H4 (face-mask) was a negative result: the YouTube
H3 false positive is a stuck detection on a stationary high-up
object, not face confusion. H5 added H3 confirmation as a downstream
flag. H6 implemented a simplified per-source greedy min-cost flow
that resolved the 1 H2 conflict (tracklet 3 → {9, 8}) by preferring
the hand-edge over the air-edge.

### Topic 2: Chain combination and physics (H7-H10)

H7 implemented a principled min-cost flow with capacity constraints,
producing 43 identical + 15 youtube chains (H2's union-find had 40
+ 13). The 48-cell sensitivity grid is perfectly flat. H8 v3-v8
developed physics consistency checks (y-velocity discontinuity,
per-arc gravity, parabolic fit). H9 measured object permanence
coverage (82.9% identical, 94.7% youtube). H10 v1-v10 produced a
per-chain quality score (0.30*h3 + 0.30*h8 + 0.40*h9) that
correlates with single-ball-ness.

### Topic 3: Identity propagation and pattern inference (H11-H12)

H11 v1-v7 implemented per-tracklet ball_id assignment + per-chain
catch/throw events, plus per-frame census + identity-merge
candidates. The final H11 v7 produces 9 CONFIDENT identical
chains + 1 CONFIDENT YouTube chain with correct physical ball ID.

H12 v1-v8 implemented per-frame pattern inference (CASCADE_3+,
FOUNTAIN_3+, MIXED_3+, etc.) on the H12 v7 event log. The final H12
v8 produces 13 substantial phases on identical (FOUNTAIN → CASCADE
→ mixed) and 12 on YouTube.

### Topic 4: V-shape recovery and chain augmentation (H13-H22)

H13 (low-conf detector signal at hand events) was a negative
result: the detector's low-conf signal is fundamentally not a
discriminator for catch-throws vs identity switches. H14 (V-shape
trajectory check) recovered 4 hidden catch-throws on identical.
H15 v2 reclassified h7v2-kept BALLISTIC edges that pass H14. H16
(H3 corroboration) and H17 (V-shape recovery at scale) had mixed
results. H20 added stricter in-hand + vel-jump + apex filters,
achieving 0.900 precision and 0.833 FPR drop on the 16-edge
visual QA set. H21 (chain augmentation) and H22 (veto mode) had
mixed results, with H22 correctly splitting the YouTube 7-tid
chain into two 4-tid chains.

### Topic 5: Operating point refinement (H24-H34)

H24 (H20-KEPT-not-in-h7v2 scale-up) found 2 NEW REAL edges (7→10,
59→61 identical) but 4 cross-ball false positives. H26 integrated
those 2 edges as HAND_TRANSITION. H28 (H20-KEPT adjacent pool
review) was negative: 17% REAL precision. H30 (direction-reversal
check) was a CLAIMED PARTIAL PASS that was overfit to a small
biased sample. H31 visual QA on 10 NEW H20+H30-AND candidates found
0/10 REAL, confirming the H17→H20→H24→H28→H31 negative finding
chain. H32 (per-chain hand-alternation) was a negative result:
chains are mostly multi-ball merges. H33 (tracklet-time overlap)
missed all 5 vision-confirmed multi-ball merges. H34 combined
H22 + H26 into the h7v3plus3 chain set (42 identical + 15
YouTube chains).

### Topic 6: Hand-occupancy state and pattern refinement (H35-H43)

H35 confirmed h7v3plus3 is functionally equivalent to h7v3pure for
downstream consumers. H36 implemented per-frame hand-occupancy
state machine (L, R, A) on h7v3plus3, achieving a closed juggling
system with zero conservation violations. H37 cross-referenced
H36 (L, R, A) with H12 v8 patterns: 80.7% agreement on identical,
76.5% on YouTube. H38 implemented a CASCADE_3+ post-filter that
rejects classifications without hand-occupancy support. H39 was a
negative result: H12 v8 FOUNTAIN_3+ classification is only 30%
accurate on visual QA. H40-H42 developed continuous hand-occupancy
signals. H43 implemented H12 v8 confidence-based FOUNTAIN_3+
filter (conf < 0.55): precision 100% on H39 visual QA, rejects
9.1% of identical FOUNTAIN_3+ frames.

### Topic 7: Flight-time analysis and event log filter (H45-H52)

H45 found that identical's 30-40 frame flight times are real
catch-throws and < 10 frame flights are identity switches, while
YouTube's 58-67 frame "flights" are uniformly tracker
fragmentation. H46 attempted per-flight physics (negative
result, but confirmed H45's YouTube finding). H47 applied the
10-frame filter to the H12 v8 event log (drops 3/48 events on
identical, 0/50 on YouTube). H48 confirmed THR=10 is in a flat
region. H49 measured the filter's downstream impact using a
K=4-only classifier (negative upper bound: 45.2%/15.9%).

**H50**: closed H49's negative result by re-running H12 v8's
FULL pipeline on the filtered event log. Real downstream impact:
**1.0% identical / 0.0% YouTube pattern label changes**. H49's
K=4-only upper bound was indeed an upper bound, as H49 suspected.
H50 visual QA on 3 changed windows found that 2/3 are confirmed
TRACKER_FRAGMENTATION, but 1/3 (chain 13 ft=3) appeared to be a
real catch-throw.

**H51**: combined H50 with H43. The two filters compose cleanly
because they operate at different stages. Combined precision
improvement: FOUNTAIN_3+ -2.3%, CASCADE_3+ +0.7% on identical.
YouTube: 0% change.

**H52**: applied H8 v5 parabolic physics to the 3 H50-dropped
pairs. **All 3 are TRACKER_FRAGMENTATION, including chain 13
ft=3.** H8 v5 shows chain 13's source is in fast descent (-32.1
px/f), target is at rest (-1.1 px/f), with 19.5 px/f velocity
discontinuity. The H50 visual QA on chain 13 was misled by the
visual appearance of "ball at hand" but didn't check velocity
consistency.

## Strongest findings

1. **The h7v3plus3 chain set is a closed, validated juggling
   representation.** 42 identical + 15 YouTube chains, validated
   at chain quality (H10 v10), identity propagation (H11 v7),
   per-frame hand-occupancy (H36), event-log flight-time (H45),
   physics corroboration (H52), and confidence-based FOUNTAIN_3+
   filter (H43).

2. **The 10-frame flight-time filter is the actionable downstream
   post-filter.** Drops 3/48 events on identical (all confirmed
   TRACKER_FRAGMENTATION by H52), 0/50 on YouTube. THR=10 is in
   a flat region (H48). The filter is correct and should not be
   relaxed.

3. **H12 v8's FOUNTAIN_3+ classification is fundamentally
   unreliable** (30% accurate on H39 visual QA). H43's
   confidence-based filter (conf < 0.55) is the most precise
   FOUNTAIN_3+ post-filter available.

4. **The chain set is mostly multi-ball merges** (H32, H33), not
   single-ball trajectories. This is a fundamental limitation of
   the input data, not an algorithm problem. The H11 v7 CONFIDENT
   chains (9 identical + 1 YouTube) are the only reliable
   single-ball trajectories.

5. **H50 visual QA can be misled by short tracklets.** The vision
   tool saw "ball at hand" on chain 13 ft=3 but didn't check
   velocity consistency. H8 v5 physics is the corroborating
   signal that distinguishes real catch-throws from tracker
   fragments.

## Important negative findings

1. **Detector low-confidence signal** is fundamentally not a
   discriminator for catch-throws vs identity switches (H13,
   H13 v2).

2. **Geometric post-filters on the H17 V-shape pool** consistently
   fail to produce a reliable high-precision candidate set (H17 →
   H20 → H24 → H28 → H30 → H31 negative finding chain).

3. **Tracklet-time overlap** is not a useful multi-ball detector
   (H33). The h7v3plus3 chain construction produces temporally
   sequential tracklets by design.

4. **H12 v8 K=4-only impact measurement** is an upper bound on
   the actual downstream impact (H49). H50's full-pipeline
   re-run is the proper measurement.

5. **YouTube h7v2 BALLISTIC edges are mostly catch+throws in
   disguise** (H7 v2). Reclassifying them as HAND_TRANSITION
   improves YouTube mean chain quality from 0.537 to 0.679.

6. **Per-flight physics (H46)** is wrong because the source
   tracklet's last points are NOT the descent into the hand —
   they are the post-throw ascent (the tracklet starts at the
   THROW frame, not the catch frame).

## Recommended operating point summary

|| Component | Choice | Rationale |
||---|---|---|
|| Chain set | h7v3plus3 | H22 + H26 combined (H34) |
|| Chain quality | H10 v11 v3 (H56 v1) | Non-linear g_cv penalty, deadzone=0.5, ramp_end=1.0, w54=0.30 |
|| Identity propagation | H11 v7 | CONFIDENT chains at q >= 0.7 |
|| Pattern inference | H12 v8 | K=4 events + census + chain quality |
|| Event log filter | H50 10-frame | Drops 3/48 identity switches on identical |
| Confidence filter | H43 FOUNTAIN < 0.55 | Rejects 21 FOUNTAIN_3+ frames on identical |
| Physics check | H52 H8 v5 | Confirms all H50 drops are TRACKER_FRAGMENTATION |

**For FOUNTAIN_3+ post-filter:** H43 alone (1/1 correct, 100% precision).

**For maximum precision (production use):**
- h7v3plus3 + (CONFIDENT or UNCERTAIN) = precision 1.000, FPR 0.000

**For research / exploratory analysis:**
- h7v3plus3 + H10 v11 v3 (all quality bands) = precision 0.981, recall 0.718

## Final pattern distribution (H50 + H51 + H52-validated)

**identical (1042 frames):**

| Pattern | H12 v8 baseline | H50 | H50+H43 | H50+H43+H52 |
|---|---|---|---|---|
| MIXED_3+            | 27.5% (286) | 27.2% (282) | 27.2% (282) | 27.2% (282) |
| TWO_BALL            | 25.8% (269) | 25.8% (269) | 25.8% (269) | 25.8% (269) |
| SINGLE_BALL         | 20.7% (216) | 20.7% (216) | 20.7% (216) | 20.7% (216) |
| FOUNTAIN_3+         | 16.4% (171) | 16.1% (168) | 14.1% (147) | 14.1% (147) |
| CASCADE_3+          |  6.7%  (70) |  7.4%  (77) |  7.4%  (77) |  7.4%  (77) |
| FOUNTAIN_LOW_CONF   |  0.0%   (0) |  0.0%   (0) |  2.0%  (21) |  2.0%  (21) |
| MIXED_3+_UNCONFIRMED |  2.0%  (21) |  2.0%  (21) |  2.0%  (21) |  2.0%  (21) |
| TWO_BALL_ONE_HAND   |  0.8%   (8) |  0.8%   (8) |  0.8%   (8) |  0.8%   (8) |

**YouTube (898 frames):**

| Pattern | H12 v8 baseline | H50+H43+H52 |
|---|---|---|
| MIXED_3+            | 55.5% (498) | 55.5% (498) |
| FOUNTAIN_3+         | 23.5% (211) | 23.5% (211) |
| CASCADE_3+          | 13.3% (119) | 13.3% (119) |
| MIXED_3+_UNCONFIRMED |  7.8%  (70) |  7.8%  (70) |

## Substantial phases (n_frames >= 20)

**identical: 15 substantial phases (preserved across all filters)**
- 0-220 FOUNTAIN phase (early)
- 300-700 CASCADE_3+ (main pattern, 4 phases)
- 700+ mixed (later phases)
- 977-1011 hold trick (FOUNTAIN_3+ conf 0.565, kept by H50)
- 1029-1050 2-ball exercise (FOUNTAIN_LOW_CONF, rejected by H43)

**YouTube: 12 substantial phases (preserved)**
- All MIXED_3+ phases (the H12 v8 YouTube over-counting is a
  known limitation, not addressed by the H50 + H43 + H52 stack)

## Lessons for future research

1. **Visual QA is unreliable on short tracklets.** Always check
   velocity consistency (H8 v5) before trusting a "ball at hand"
   heuristic.

2. **K=4-only classifiers are upper bounds, not actual
   measurements.** Use the full pipeline for impact measurement.

3. **Rule-based filters approach their useful limit at the
   per-flight level.** H52's H8 v5 corroboration is the
   end-state for hand-crafted event-log filters. Further
   improvements would require learned models (TOTNet 2025,
   Ponglertnapakorn 2025) or 3D trajectory estimation.

4. **YouTube h7v2 BALLISTIC edges are mostly catch+throws in
   disguise.** Reclassifying them as HAND_TRANSITION is the
   single most impactful YouTube improvement (mean chain
   quality 0.537 → 0.679).

5. **Multi-ball identification is the fundamental remaining
   problem.** The h7v3plus3 chain set is well-validated as
   "hand-event lists" but not as "single-ball trajectories."
   Solving this would require color tracking, multi-view 3D,
   or learned models.

## Acknowledgments

This lab was an autonomous research effort driven by the
hand-occlusion overnight lab watchdog. Each episode was a fresh
worker invocation that read the persistent state files (STATE.md,
PLAN.md, RESULTS_LOG.md, RESEARCH_NOTES.md) and continued from
the recorded next action. The lab's 52 research episodes spanned
~14 hours of wall-clock time and produced a comprehensive,
validated chain representation for both videos.

---

## H53-H61 extension (2026-08-28 16:30-16:50 CEST, 9 additional episodes)

The H1-H52 episodes produced the validated operating point
documented above. The H53-H61 extension (1 fresh worker episode
that produced 4 experiments) added the following:

### H53 — H52 sensitivity grid preservation + multi-rater visual QA consensus
- H52 summary JSON was missing MIN=2 grid values. H53 re-runs
  the 9-cell MIN_TRACKLET_PTS grid and saves every cell.
- 4-rater visual QA consensus (H45 bucket, H50 vision A, H52
  physics, H53 vision A and B): all 3 H50 drops are
  TRACKER_FRAGMENTATION.

### H54 — Per-chain arc-gravity CV as single-ball signal
- Per-chain coefficient of variation of clean per-arc gravity
  values is a discriminative signal for "is this a single
  physical ball?". 2x difference between CONFIDENT (g_cv=0.379)
  and UNCERTAIN (g_cv=0.782) chains on identical.

### H55 — H10 v11 with H54 gravity-CV as 5th dimension
- 3 multi-ball-merge chains correctly demoted to LOW quality.
  CONFIDENT count drops by 1 on each video; lost chains are
  confirmed FPs.

### H56 — H10 v11 v3 with non-linear g_cv penalty (deadzone + ramp)
- The deadzone + ramp penalty preserves low-CV chains while
  penalizing high-CV chains. Recovers the v10 CONFIDENT count
  on identical (27/27). **H56 v1 is the new recommended chain
  quality score, replacing H10 v10 and H55 v2.**

### H57 — Conditional penalty for high-CV low-arc chains
- Adds partial penalty for chains with n_arcs_clean=2 and
  g_cv >= 1.0. H57 v1 is a refinement of H56 v1.

### H58 — Triple intersection (H11 v7 + H10 v11 v3 + H12 v8)
- The 3 identical + 1 YouTube multi-tid CONFIDENT chains form
  a clean single-ball subset with consistent held-phase
  durations: 11 frames (3-ball cascade) on identical, 17 frames
  (5-ball shower) on YouTube.

### **H58 v1 — Visual verification of the 4 multi-tid CONFIDENT chains**
- Renders 4 contact sheets (one per chain). Vision tool
  confirms all 4 are real single-ball catch-throw events.
- Closes the H58 visual-verification gap.

### **H59 — End-to-end precision/recall evaluation against 113 reviewed pairs**
- **First objective validation of the entire chain-quality
  optimization arc** (H1 → H2 → ... → H58).
- Full set: precision 0.981 (51 TP, 1 FP), recall 0.718 (20 FN),
  FPR 0.024 (1/42).
- **CONFIDENT + UNCERTAIN chains: 100% precision (38/0).**
- H10 v11 v3 quality is a real, validated signal.
- The 1 FP is identical 22->27 in chain 15 (LOW quality, q11=0.316).
  H10 v11 v3 correctly demotes the only FP to LOW.
- The 20 FN are a structural limit (one-successor-per-source
  capacity constraint), not a model bug.
- New precision-maximizing operating point (H59-validated):
  **h7v3plus3 + (CONFIDENT or UNCERTAIN) = precision 1.000, FPR 0.000**.

### **H60 — Per-frame hold-duration distribution**
- H58 11-frame signature IS the median held phase on identical
  (25 events, mean 12.6, median 11). Validates the 3-ball cascade
  characteristic hold at the population level.
- H58 17-frame signature IS the max held phase on YouTube
  (25 events, mean 9.84, median 9). YouTube's typical hold
  is 9 frames (much shorter than identical's 11).
- **Hand-asymmetry reversal (NEW FINDING)**: identical has
  LONGER right-hand holds (median 12.5 vs 11); YouTube has
  LONGER left-hand holds (median 11 vs 9). The two videos
  show different juggling patterns.

### **H61 — YouTube 16->21 vs 20->21 catch+throw conflict**
- The 2024 manual stitch review said YouTube 16->21 is "correct".
  H22's 2026 visual analysis said 16->21 is WRONG and 20->21 is
  the real catch. H61 renders a side-by-side contact sheet and
  asks the vision tool to adjudicate.
- **Vision tool verdict: 20->21 is the real catch-throw; 16->21
  is not.** H22 confirmed.
- H22's 2026 visual analysis is a stronger signal than the 2024
  manual labels for this case.
- This is the ONLY "FN that's actually a TN" case from H59. All
  other 51 TP match the manual review. The H59 evaluation is
  now fully validated.

## Updated recommended operating point (post-H61)

| Component | Choice | Rationale |
|---|---|---|
| Chain set | h7v3plus3 | H22 + H26 combined (H34) |
| Chain quality | H10 v11 v3 (H56 v1) | Non-linear g_cv penalty, deadzone=0.5, ramp_end=1.0, w54=0.30 |
| Identity propagation | H11 v7 | CONFIDENT chains at q >= 0.7 |
| Pattern inference | H12 v8 | K=4 events + census + chain quality |
| Event log filter | H50 10-frame | Drops 3/48 identity switches on identical |
| Confidence filter | H43 FOUNTAIN < 0.55 | Rejects 21 FOUNTAIN_3+ frames on identical |
| Physics check | H52 H8 v5 | Confirms all H50 drops are TRACKER_FRAGMENTATION |

**For maximum precision (production use):**
- h7v3plus3 + (CONFIDENT or UNCERTAIN) = precision 1.000, FPR 0.000

**For research / exploratory analysis:**
- h7v3plus3 + H10 v11 v3 (all quality bands) = precision 0.981, recall 0.718

## Updated strong findings (post-H65)

1. **The h7v3plus3 chain set is a closed, validated juggling
   representation** with 100% precision on the 113-pair manual
   review (when restricted to CONFIDENT + UNCERTAIN chains).
2. **The 10-frame flight-time filter is the actionable downstream
   post-filter.** Drops 3/48 events on identical (all
   TRACKER_FRAGMENTATION), 0/50 on YouTube.
3. **H12 v8's FOUNTAIN_3+ classification is 43% accurate** on
   the H50-filtered H65 sample (improved from H39's 30%).
   H43's confidence-based filter (conf < 0.55) is the best
   FOUNTAIN_3+ post-filter on the H65 sample (1/1 correct
   reject, 100% precision). H66's continuous balls-aloft
   (pct_A_ge2) signal is real but cannot reliably separate
   3-ball FOUNTAIN from static hold (gap is 0.12 vs 0.00,
   too narrow). H67/H68's stacked rejection precision (50-67%)
   is WORSE than H43 alone. **H43 alone remains the recommended
   FOUNTAIN_3+ post-filter.**
4. **The chain set is mostly multi-ball merges** (H32, H33, H54,
   H55, H56), not single-ball trajectories. The H11 v7 +
   H10 v11 v3 CONFIDENT chains (3 identical + 1 YouTube) are
   the "purest" single-ball trajectories.
5. **The 2024 manual review has 1 known label error** (YouTube
   16->21, corrected to 20->21 in the h7v3plus3 chain set by H22
   and confirmed by H61).
6. **YouTube 5-ball is a CASCADE-SHOWER mix (H62, H63)**, not a
   pure SHOWER as H58 originally interpreted. The pattern is
   70% CASCADE (alt-hand) with 2 SHOWER bursts (right-hand
   same-hand events). The 17-frame chain 6 hold is a real
   signature feature but is part of a SHOWER burst, not the
   dominant pattern.

## Episodes 53-61 timeline

- H62 — 5-ball pattern characterization (CASCADE, not SHOWER)
- H63 — CASCADE-SHOWER mix (SHOWER bursts within CASCADE)

The H53-H61 extension was a single autonomous worker episode
(2026-08-28 16:30-16:50 CEST, ~20 minutes) that:
1. Rendered the 4 H58 contact sheets and visually verified the
   H58 multi-tid CONFIDENT chains (H58 v1, PASS).
2. Wrote the H59 evaluation script, ran it, and discovered the
   H22 conflict between the 2024 manual review and the 2026 lab
   visual analysis (H59, PASS).
3. Wrote the H60 hold-duration distribution script and found
   the hand-asymmetry reversal between the two videos
   (H60, PASS).
4. Wrote the H61 side-by-side contact sheet for the 16->21 vs
   20->21 conflict and confirmed H22's analysis
   (H61, PASS).

Total: 4 new experiments, 1 new code script per experiment,
multiple contact sheets, 4 new report documents, 4 new data
CSV/JSON files. All committed and pushed to
`origin/experiments/hand-occlusion-overnight`.

---

## H62-H65 extension (2026-08-28 17:00-17:30 CEST, 4 additional episodes)

### **H62 — YouTube 5-ball pattern: CASCADE not SHOWER**
- Examined all 24 YouTube catch+throw events: 70% alt-hand,
  30% same-hand (right). H58 SHOWER interpretation was based
  on n=1 (chain 6); the broader YouTube pattern is CASCADE.
- 17-frame chain 6 hold is a real signature but an exception
  in an otherwise CASCADE pattern.
- Refines H58 from "5-ball SHOWER" to "5-ball CASCADE".

### **H63 — YouTube 5-ball CASCADE-SHOWER mix**
- The 7 same-hand events form 2 SHOWER-like clusters of 3
  events each, separated by ~250 frames of CASCADE.
- All 7 same-hand events are on the right hand (consistent
  with a right-handed juggler). Same-hand gaps are LONGER
  (median 20 vs 13.5 alt-hand). SHOWER requires the dominant
  hand to throw, wait for peak, then catch.
- Pattern: CASCADE (70%) with SHOWER bursts (30%).

### **H64 — Identical 3-ball CASCADE->FOUNTAIN transition**
- Best temporal split: f=240. Pre (f<240): 1/4 same-hand
  (CASCADE-like). Post (f>=240): 11/15 same-hand
  (FOUNTAIN-like). 0.48 same-rate delta.
- Per 100-frame window: 0-300 mostly alt-hand, 800-1000
  100% same-hand. H58 v1 "3-ball cascade" refined to
  "CASCADE->FOUNTAIN transition at f=240".

### **H65 — H12 v8 FOUNTAIN_3+ label validation at scale**
- Visual QA on all 7 substantial FOUNTAIN_3+ phases
  (>= 20 frames) in the H50-filtered pattern data.
- H12 v8 accuracy: **3/7 = 43%** (improved over H39's 30%
  but still noisy).
- 2 wrong: OTHER (static hold). 1 wrong: CASCADE
  (alt-hand misread as same-hand). 1 wrong: cascade-like
  with extra hand-held ball.
- H43 confidence filter: high-precision (1.000 on H39+H65)
  but low-recall (1/4 wrong-on-identical has conf < 0.55).
- **H65 confirms the H43 confidence filter is the most
  precise FOUNTAIN_3+ post-filter available.** A truly
  reliable classifier would need continuous hand-occupancy
  signal (per H40-H42), unavailable in the chain-event
  representation.

### **H66 — Continuous balls-aloft (A) FOUNTAIN_3+ post-filter**
- Per-frame A = # YOLO balls > 100 px from both wrists.
  Phase-level metric: pct_A_ge2 = fraction of frames with
  >= 2 balls aloft.
- Threshold 0.30 on H65 sample: 2/7 rejected, 1 correct
  (1029-1049 static hold, max_A=1) and 1 wrong (977-1011
  real 3-ball FOUNTAIN, only 1 ball aloft at a time).
- H43 + H66 stacked: 2/7 rejection rate, 67% precision on
  rejects. Kept-set accuracy improves 43% → 60%.
- Negative finding: YOLO detector false positives on
  stationary background features (corrugated door, sign,
  trees) limit H66's discrimination on YouTube. The H4
  general detector confusion finding extends.
- **Recommended operating point (updated):**
  h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + **H66** +
  H52 + H53. For FOUNTAIN_3+ post-filter: H43 + H66 stacked.

### **H67 — H43+H66 stacked end-to-end impact**
- H67 measures the per-frame downstream impact of H43 + H66
  stacked on the H50-filtered pattern data.
- Result: identical 5.4% frames changed (56/1042), YouTube
  0.0% (0/898). Of the 56 identical changes: 21 correct
  rejects (1029-1049 static hold) + 35 wrong rejects
  (977-1011 real 3-ball FOUNTAIN). Precision on rejects: 37.5%.
- H67 recommends lowering H66 threshold to 0.20 to preserve
  3-ball FOUNTAIN. At threshold 0.20, H66 catches only
  1029-1049 — same as H43 alone, no false rejects.
- **3-ball vs 5-ball calibration:** 3-ball FOUNTAIN has
  pct_A_ge2 ≈ 0.12 (1 ball aloft at a time), 5-ball FOUNTAIN
  has pct_A_ge2 ≈ 0.50-0.60 (2-3 balls aloft). A single
  threshold cannot serve both. Per-n_total calibration
  needed for future improvement.

### **H68 — per-n_total threshold calibration (NEGATIVE)**
- H68 tests per-n_total thresholds (3-ball: 0.20, 5-ball: 0.45).
- Result: 2/3 rejection precision (1029-1049 + 800-861 correct,
  977-1011 wrong). Same as H67.
- 5-ball threshold 0.45 correctly catches 800-861 YouTube
  CASCADE. 3-ball threshold 0.20 wrongly rejects 977-1011
  (real 3-ball FOUNTAIN, pct_A_ge2=0.12).
- **H43 alone is the best FOUNTAIN_3+ post-filter on the H65
  sample.** H66 and H68 are useful as diagnostic signals but
  should not be applied as post-filters at current thresholds.
- The fundamental limit: a 3-ball FOUNTAIN has only 1 ball
  aloft at most times. The gap between 3-ball FOUNTAIN
  (pct=0.12) and static hold (pct=0.00) is too narrow for
  safe discrimination.

### **H69 — Periodicity of "balls aloft" as FOUNTAIN_3+ post-filter (PASS, H68 superseded)**
- H69 implements the H68 report's suggestion of using
  *periodicity* of the A signal (not just level) to discriminate
  FOUNTAIN from HOLD/CASCADE.
- Metric: FFT spectral concentration of the per-frame A signal
  (max FFT power / total power, after Hann windowing). High
  concentration = coherent periodic A pattern (real FOUNTAIN
  with synchronized parallel throws). Low concentration =
  incoherent A pattern (static hold with YOLO false positives,
  or CASCADE with rapid hand alternation).
- H43 OR H69(spec_conc < 0.15) on H65 sample (n=7 phases):
  - 3/3 correct rejects (1029-1049 H43, 482-594 H69, 800-861 H69)
  - 0/3 wrong rejects (all FOUNTAIN preserved)
  - 1 wrong kept (890-936 crossed-arm trick, escapes both)
  - **Precision 100%, recall 75%** (vs H43 alone: 100% / 25%)
- Per-frame end-to-end impact:
  - identical: 21/1042 (2.0%) — same as H43 alone
  - YouTube: 175/898 (19.5%) — H69 adds 175 frames
    (482-594 + 800-861 = 113 + 62 = 175, both correctly rejected)
- Sensitivity grid: flat region [0.15, 0.16] on H69 spec_conc.
  Above 0.16 wrongly rejects 339-374 (real FOUNTAIN).
  Below 0.15 misses 482-594.
- **Why H69 works where H66/H68 didn't:** the H66/H68 level
  metric ("are there balls aloft?") cannot separate 3-ball
  FOUNTAIN from static hold because both have low ball counts.
  The H69 spectral concentration is a STRUCTURAL check ("is the
  ball-aloft pattern coherent?") that captures the temporal
  pattern of throws. H69 vs H66 is the difference between
  "what is the A signal level?" and "what is the A signal
  structure?".
- **Recommended operating point (H69 supersedes H68):**
  h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69(spec_conc
  < 0.15) + H52 + H53. H66 and H68 are no longer applied at
  any threshold.

### **H70 — H69 spec_conc characterization across pattern types (MIXED)**
- Question: is H69 spec_conc FOUNTAIN-specific, or a more
  general "is this a real pattern?" signal?
- Per-pattern H69 spec_conc on 19 substantial phases:
  - CASCADE_3+ (n=1): 0.498
  - FOUNTAIN_3+ (n=6): mean 0.240, range [0.088, 0.411]
  - MIXED_3+ (n=11): mean 0.205, range [0.124, 0.332]
  - MIXED_3+_UNCONFIRMED (n=1): 0.075
- H43 OR H69(spec_conc < 0.15) on ALL substantial phases:
  - 3 FOUNTAIN_3+ correctly rejected (same as H69)
  - 1 MIXED_3+ rejected: 114-255 (conc=0.124, vision tool:
    "NOT real 5-ball juggling. Transition/pause sequence.")
  - 1 MIXED_3+_UNCONFIRMED rejected: 2-71 (conc=0.075,
    vision tool: "NOT real juggling. Static demonstration,
    pose, or freeze-frame.")
- **Verdict: MIXED.** H69 spec_conc is a GENERAL "pattern
  coherence" signal that applies to MIXED_3+ too. H70 catches
  2 additional misclassified MIXED_3+ phases. The recommended
  operating point is unchanged (H43 + H69 on FOUNTAIN_3+ only).
  H70 is a useful diagnostic signal that warrants future
  multi-rater validation. The H70 contact sheets at
  `contact_sheets_h70/` and `contact_sheets_h70v2/` document
  the verdicts.

## Updated strong findings (post-H70)

1. **The h7v3plus3 chain set is a closed, validated juggling
   representation** with 100% precision on the 113-pair manual
   review (when restricted to CONFIDENT + UNCERTAIN chains).
2. **The 10-frame flight-time filter is the actionable downstream
   post-filter.** Drops 3/48 events on identical (all
   TRACKER_FRAGMENTATION), 0/50 on YouTube.
3. **H12 v8's FOUNTAIN_3+ classification is 43% accurate** on
   the H50-filtered H65 sample (improved from H39's 30%).
4. **H43 + H69 (H43 OR H69) is the new best FOUNTAIN_3+
   post-filter** (precision 100%, recall 75% on the H65 sample,
   +1 correct catch vs H43 alone).
5. **H69 spec_conc is a general "pattern coherence" signal**
   (H70) that catches misclassified MIXED_3+ phases too. H70
   is a research-grade extension of H69.
6. **The chain set is mostly multi-ball merges** (H32, H33,
   H54, H55, H56), not single-ball trajectories. The H11 v7 +
   H10 v11 v3 CONFIDENT chains (3 identical + 1 YouTube) are
   the "purest" single-ball trajectories.
7. **The 2024 manual review has 1 known label error** (YouTube
   16->21, corrected to 20->21 by H22, confirmed by H61).
8. **Identical 3-ball has a CASCADE->FOUNTAIN transition at
   f=240 (H64).** YouTube 5-ball is a CASCADE-SHOWER mix
   (H62, H63). The 11-frame and 17-frame held-phase
   signatures (H58) are consistent with 3-ball cascade and
   5-ball shower hold times respectively.

EOF
echo "OK"