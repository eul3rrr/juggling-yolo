# H24 — Visual QA of H20-KEPT e6c_not_in_h7v2 candidate pool at scale

**Date:** 2026-08-28 ~20:30 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE** (precision 22-44%, lower than the
H17 strict baseline)

## Hypothesis

The 26 H20-KEPT `e6c_not_in_h7v2` candidates that survive H20's
in-hand + vel-jump + apex filters represent a pool of "missed
catch+throws" that the production h7v2 chain set failed to
capture. H20 visually QA'd 8 of the 26 (8 candidates had
`e6c_not_in_h7v2` kind in the H20 visual QA set; 5 were REAL,
3 PARTIAL). The other 18 candidates were NOT visually QA'd.

H24 hypothesis: a larger visual QA sample of the 26 H20-KEPT-not-
in-h7v2 pool will confirm the 5/8 = 62.5% REAL precision observed
in the H20 sample, and characterize the pool as a high-precision
candidate list for chain set augmentation.

## Methodology

- Selected 12 H20-KEPT `e6c_not_in_h7v2` candidates (8 identical +
  4 YouTube) from the 18 not yet QA'd. Selection criteria (declared
  in `h24_candidate_qa_at_scale.py`):
  1. Sort by gap ascending (prefer short gaps typical of catch-throws)
  2. Take first 8 identical + first 4 YouTube.
- Found only 1 YouTube candidate (the 18-candidate pool had only
  4 YouTube H20-KEPT-not-in-h7v2 positives; selection recovered
  1). Final sample: 8 identical + 1 YouTube = 9 candidates.
- Rendered contact sheets via `h24_contact_sheets.py` (2×3 grid:
  source-tail + target-head + V-apex annotation).
- Visually QA'd each via `vision_analyze` with structured verdict
  (REAL, PARTIAL, FALSE, UNCLEAR).

## Thresholds (declared from physical geometry, not tuned to labels)

- Inherited from H20 default: `IN_HAND_PX=30, MIN_IN_HAND_FRAMES=3,
  MAX_GAP_VEL=70, APEX_SRC_DIST_REJECT=20`.
- The H24 selection filter: `kind=e6c_not_in_h7v2 AND h20_keep=True`
  AND `NOT in H20 visual QA set`.

## Quantitative result

| Metric | Value |
|---|---|
| Total H17 strict positives | 151 |
| H20-KEPT (e6c_not_in_h7v2) | 26 |
| H24 sample (selected for QA) | 9 (8 identical + 1 YouTube) |
| Verdicts: REAL | 2 |
| Verdicts: PARTIAL | 2 |
| Verdicts: FALSE | 5 |
| Verdicts: UNCLEAR | 0 |
| **Precision (PARTIAL=TP)** | **0.444** (4/9) |
| **Precision (REAL only)** | **0.222** (2/9) |

### Per-stem

| Stem | n | REAL | PARTIAL | FALSE |
|---|---|---|---|---|
| identical | 8 | 2 | 1 | 5 |
| YouTube | 1 | 0 | 1 | 0 |

### Per-hand

| Hand | n | REAL | PARTIAL | FALSE |
|---|---|---|---|---|
| left | 5 | 1 | 1 | 3 |
| right | 4 | 1 | 1 | 2 |

### Per-vshape

| V-shape | n | REAL | PARTIAL | FALSE |
|---|---|---|---|---|
| V_DEEP | 8 | 1 | 2 | 5 |
| V_SHALLOW | 1 | 1 | 0 | 0 |

The single V_SHALLOW candidate (7→10 identical) is REAL; V_DEEP
candidates are predominantly FALSE (5/8 = 62.5%).

## Visual QA breakdown

| # | Edge | min_d | Verdict | Reason |
|---|------|-------|---------|--------|
| 1 | 9→12 identical (L) | 15.43 | **FALSE** | Source 'ball' held at L hand (4 px/frame motion, no descent); target 'ball' high in frame (170 px above L hand) is a stationary or pre-existing different-color ball. Cross-ball artifact. |
| 2 | 62→65 identical (R) | 32.58 | **FALSE** | Source ball descending to R hand plausibly but catch not completed in source frames. Target ball at +130 px x-displacement, R hand moving down-left (opposite of post-catch rebound). Cross-ball artifact. |
| 3 | 10→11 identical (R) | 34.72 | **PARTIAL** | Source ball near apex drifting horizontally (not descending). Target ball at R wrist. Both events within the 8-frame gap, not visible. min_d=34.7 is plausible but V-shape artifact not confirmed. |
| 4 | 7→10 identical (L) | 57.35 | **REAL** | R hand has thrown (blue ball in air), L hand has caught (orange ball adjacent to L wrist in target frames). Hand ownership inverts from R to L. Shallow V-throw consistent with V_SHALLOW. |
| 5 | 67→72 identical (L) | 26.14 | **FALSE** | Source ball at high apex y=200 (blue, large). Target ball at y=475 (orange, small). Different colors, 270 px y-jump across 9 frames. The V-apex (705,474) does not match the airborne ball position. Cross-ball artifact. |
| 6 | 73→75 identical (L) | 35.20 | **FALSE** | Ball held at L wrist in BOTH source and target frames. No throw event between R and L hand visible. Held-ball artifact. |
| 7 | 1→6 identical (R) | 41.88 | **FALSE** | Source ball far below R hand (y=680, wrist at y=540). Target ball well above L hand (y=400, wrist at y=490). Hands empty in all frames. No catch+throw event. Cross-ball artifact. |
| 8 | 59→61 identical (R) | 18.94 | **REAL** | Source R hand holds ball, L hand held high (wind-up pose). Target L hand now holds ball, R hand moved away (post-catch pose). Wrist-relative-to-ball configurations invert across the gap. min_d=18.9 is tight. Clear R→L transfer. |
| 9 | 10→11 YouTube (R) | 4.69 | **PARTIAL** | Catch visible in source (ball descending to R hand, co-located at f=241). Ball-in-flight-after-throw visible in target (ball high above hands, rising). Throw moment hidden in the 9-frame gap. |

## H24 vs H20 visual QA precision

| Sample | n | REAL | PARTIAL | FALSE | UNCLEAR | P (PARTIAL=TP) | P (REAL only) |
|---|---|---|---|---|---|---|---|
| H20 `e6c_not_in_h7v2` (subset) | 8 | 5 | 3 | 0 | 0 | **1.000** | 0.625 |
| H24 `e6c_not_in_h7v2` (new) | 9 | 2 | 2 | 5 | 0 | 0.444 | 0.222 |
| **Combined H20+H24** | **17** | **7** | **5** | **5** | **0** | **0.706** | **0.412** |

H24 finds 5/9 = 55.6% FALSE positives, where H20 found 0/8 = 0%.
This is a 56% drop in precision when extending the QA sample.

The H20 8-candidate sample was selected with the same sort strategy
(gap ascending, then min_d ascending) but produced a much more
favorable sample. The H24 sample reaches further into the pool,
where the precision drops substantially.

## Negative findings

- **H24 fails the hypothesis.** The 26-candidate H20-KEPT-not-in-
  h7v2 pool is NOT a high-precision pool for chain set augmentation.
  Combined H20+H24 precision (PARTIAL=TP) is 70.6% (12/17) but
  REAL-only precision is 41.2% (7/17). Half of the "candidate
  catch+throws" produced by H20+H17 are false positives that the
  V-shape + strict + in-hand + vel-jump + apex filters cannot
  reject.
- **The dominant failure mode is "cross-ball artifact"** (4/5
  FALSE positives in H24): the V-shape + min_d criterion finds
  V-shaped trajectories but the source and target tracklets are
  DIFFERENT physical balls at different positions in the juggling
  pattern. The trajectory-fit error (E6c) is not informative
  here because the E6c predecessor is on the source's own tracklet
  history, not on the candidate target.
- **The 2 REAL candidates (7→10, 59→61 identical) ARE real
  hand-off events** that the production h7v2 chain set missed.
  H21 v1 already integrates 7→10 via a different candidate (6→15).
  59→61 is a NEW candidate that H21 did not have.
- **The 2 PARTIAL candidates (10→11 identical, 10→11 YouTube) are
  consistent with real catch+throws** but the catch/throw moments
  are within the gap, so they are not visually confirmed. These
  are downstream-consumable as low-confidence positives.
- **V_SHALLOW candidates (n=1) are more reliable than V_DEEP (5/8
  = 62.5% FALSE).** This makes physical sense: a shallow V-throw
  between adjacent hands has fewer opportunities for cross-ball
  contamination than a deep V-throw spanning a long airborne arc.

## H24 as a chain-set augmentation tool

H21 v1 integrated the 5 H20-KEPT REAL `e6c_not_in_h7v2` edges
into the chain set. H24 finds 2 additional REAL edges
(7→10 identical, 59→61 identical) and 2 PARTIAL edges that
H21 did not consider.

Of these:
- **7→10 identical (REAL, V_SHALLOW)**: connects chain 4 (5,6)
  with chain 13 (15) via a NEW path. The h7v3plus chain
  augmentation (H21) already added 6→15 as a HAND_TRANSITION,
  but 7→10 is a different, distinct transition. Adding 7→10
  would create a 3-tracklet chain (5,6,7,10,15) — but t7 is
  the source of 7→10 and is the SOURCE of the (existing) 7→10
  V_DEEP edge. The h7v2 chain set already accepts 7→10 via
  the V_DEEP reclassification (it's in the H17 positives).
  Wait — let me check: 7→10 is `kind=e6c_not_in_h7v2` so it
  was rejected by h7v2. H17 strict V-shape finds it; H20 keeps
  it; H24 confirms REAL. So 7→10 is a genuine missed catch+throw.

- **59→61 identical (REAL, V_DEEP)**: connects chain 30
  (51,52,54,59,63) with chain 33 (57) and possibly a singleton
  61. Looking at the chain 30 membership: t59 is in chain 30.
  t61 would be a new successor to t59 in the same chain
  (currently t59's successor in chain 30 is t63, via the
  59→63 HAND_TRANSITION). 59→61 would be a competing successor
  for t59, requiring the H21 chain augmentation logic.

These are real, useful candidates for a future H25 chain-set
augmentation that goes beyond the H20 5-candidate set.

## Verdict

**NEGATIVE.** H24 fails the H20-derived hypothesis that the
H20-KEPT `e6c_not_in_h7v2` pool is a high-precision candidate
list for chain set augmentation. The pool's REAL-only precision
on the 9-candidate H24 sample is 22.2% (2/9) vs H20's 62.5%
(5/8) on its 8-candidate sample. The combined 17-candidate
H20+H24 REAL precision is 41.2%.

The dominant failure mode is cross-ball artifacts where the
V-shape trajectory looks plausible but the source and target
tracklets are different physical balls. H20's in-hand + vel-
jump + apex filters do not reject these because:
1. Neither source nor target is "held" in a hand (the false
   positives are airborne balls, not held balls).
2. The vel-jump criterion is permissive enough (70 px/frame)
   that some V-shaped cross-ball trajectories pass.
3. The apex-criterion is permissive (20 px) that some V-apex
   positions that happen to be near a hand pass.

A fundamentally different filter is needed to reject cross-
ball artifacts. Possible ideas:
- **Color-histogram continuity check** across the gap: a real
  ball is a single color. Cross-ball artifacts have different
  ball colors (e.g. blue ball at source, orange ball at target).
  The H17/H20 contact sheets already show this color mismatch
  in many FALSE positives.
- **Trajectory overlap check**: the source's tracklet history
  and the target's tracklet history should intersect spatially
  within the gap (a real ball passes through the hand region
  during the gap; a cross-ball does not).
- **Source-end velocity × gap-time vs target-start velocity**:
  for a real catch+throw, the source's exit velocity (after
  the hand interacts) should approximately equal the gap
  time × gravity correction of the target's entry velocity.
  Cross-ball artifacts do not satisfy this.

These are not in scope for the current H24 episode but are
useful follow-up directions.

## Recommendation

- H20-KEPT `e6c_not_in_h7v2` is NOT a reliable chain-set
  augmentation source. The 5 H20-KEPT REAL `e6c_not_in_h7v2`
  edges integrated by H21 (6→15, 54→57, 56→57, 56→58, 20→21)
  remain the only safe additions to the chain set.
- The 2 H24 REAL candidates (7→10, 59→61) are genuine missed
  catch+throws. A future H25 could integrate them, but the
  trade-off (chain quality drop) should be re-measured.
- The 4 cross-ball FALSE positives (9→12, 62→65, 67→72, 1→6)
  are the dominant failure pattern. A color-continuity check
  is the most promising future improvement.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h24_candidate_qa_at_scale.py` (selection + contact sheets)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h24_visual_qa.py` (verdict recording + summary)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h24/*.png` (9 contact sheets)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_selected_candidates.csv` (9-candidate pool)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_visual_qa_verdicts.csv` (verdicts)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_summary.json` (tally + per-stem/hand/vshape)
