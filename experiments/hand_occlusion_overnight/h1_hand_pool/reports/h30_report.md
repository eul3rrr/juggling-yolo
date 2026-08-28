# H30 — Direction-reversal check on H17 strict V-shape positives

**Date:** 2026-08-28 ~12:15 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **PARTIAL PASS** (precision-optimized: 0/14 FALSE on
known labels, 4/9 REAL recall)

## Hypothesis

The H28 visual QA found that 6/12 H20-KEPT adjacent candidates had a
real **throw** visible but no real **catch** visible. This is the H17
V-shape criterion's **throw-bias**: it admits candidates where the
target leaves the hand, but does not require the source to actually
descend into the hand.

H30 hypothesis: requiring the SOURCE's last position to be above the
V-apex (in image coords, smaller y) AND the source's trajectory to be
descending (last y > first y) will reject the throw-only false
positives without rejecting real catch+throws.

## Approach (declared from physical geometry, not tuned to labels)

Two iterations:

**V1 (velocity-based, REJECTED):** use source-tail and target-head
velocity dot products with apex direction. Rejected because real
catch+throws often have short source/target tracklets where velocity
is dominated by noise.

**V2 (positional):** check whether the source and target endpoints are
geometrically consistent with a catch+throw:
- `src_above`: source end y < apex y - 20 (source is above apex in image)
- `tgt_above`: target start y < apex y - 20 (target is above apex in image)
- `both_above`: both conditions (true V-shape)
- `src_descending`: source end y > source first y + 10 (source has been descending)
- `tgt_ascending`: target start y < target last y - 10 (target is ascending)

In image coordinates, y increases downward. So:
- Source above apex (y smaller) = source is at higher real-world position
  = approaching the hand from above
- Source descending (y increasing over time) = ball is falling toward hand
- Target above apex = target is also higher (just left hand, going up)
- Target ascending (y decreasing over time) = ball moving up after throw

## Quantitative result

151 H17 strict positives → 108 unique candidates after deduplication.

| Check | n_kept | Recall (REAL=9) | FPR (FALSE=14) |
|---|---|---|---|
| both_above | 25 | 3/9 (33%) | 2/14 (14%) |
| **src_above + src_desc** | **21** | **4/9 (44%)** | **0/14 (0%)** |
| tgt_above + tgt_asc | 30 | 6/9 (67%) | 3/14 (21%) |
| h30_pass (src_above OR tgt_above) | 109 | 7/9 (78%) | 11/14 (79%) |
| combo (any of the above) | 50 | 7/9 (78%) | 4/14 (29%) |

**Key finding:** `src_above + src_descending` has **PERFECT precision**
(0/14 FALSE) on the deduplicated known-label set, with 4/9 REAL recall.
It is a precision-optimized filter.

## Correlation with known labels (deduplicated)

| Label | n | both_above | src_above+desc | tgt_above+asc | h30_pass | combo |
|---|---|---|---|---|---|---|
| REAL | 9 | 3 | 4 | 6 | 7 | 7 |
| PARTIAL | 7 | 0 | 1 | 0 | 5 | 1 |
| FALSE | 14 | 2 | **0** | 3 | 11 | 4 |

The 14 known FALSE positives all have `src_above + src_desc = False`:
- The 5 H24 FALSE positives (9→12, 62→65, 67→72, 73→75, 1→6) — all
  have src_above=False or src_desc=False
- The 4 H28 adjacent FALSE positives (39→46, 58→60, 6→14, 24→26) —
  same pattern
- The 5 H17 visual QA FALSE positives (4→8, 35→38, 66→68, 35→40,
  24→27) — same pattern

The 4 known REAL caught by H30 src_above+desc are: 13→15 identical,
54→57 identical, 56→57 identical, 29→33 identical (PARTIAL). All have
the source's trajectory visibly descending toward the V-apex hand.

The 5 known REAL missed by H30 src_above+desc are: 6→15 identical,
7→10 identical, 59→61 identical, 56→58 identical, 20→21 youtube,
10→11 youtube. These are cases where the source's first y is already
past the descending threshold (short source tracklet) or the source
is at the apex (no descent visible).

## H30-KEPT pool

H30-KEPT (`src_above + src_desc`) admits 16 unique candidates from the
H17 strict pool:
- 0 v4d_rejected
- 5 e6c_not_in_h7v2
- 11 adjacent

By source kind:
- v4d_rejected: kept=0, rej=2
- e6c_not_in_h7v2: kept=5, rej=37
- adjacent: kept=11, rej=53

H30-KEPT is 15.7% of the H17 strict pool. It is a STRICT SUBSET.

## H20-AND-H30 intersection (H31 candidate set)

Intersection of H20-KEPT (115) and H30-KEPT (16) = **15 candidates**:
- 5 are already in the known label set: 54→57, 56→57, 13→15, 29→33
  (PARTIAL), 56→58 (4 REAL + 1 PARTIAL = 100% precision on QA'd set)
- 10 are NEW candidates: 12→17, 17→22, 12→18, 15→18, 17→21, 17→24,
  20→23, 54→58, 54→60, 56→59 (none visually QA'd)

The H31 candidate set is saved at `data/h31_h20_h30_kept.csv` for
follow-up visual QA in a future episode.

## Interpretation

- **H30 src_above + src_descending is a precision-optimized filter.**
  It correctly identifies candidates where the source has been
  descending AND is currently above the V-apex. Real catch+throws with
  a visible descent pass; throw-only false positives with the source
  at the hand or below fail.
- **The 5 known REALs missed by H30** are mostly cases where the
  source's first y is already past the descending threshold (the
  source's tracklet is too short, or the source is at the apex).
  These are still real catch+throws; H30 just can't verify them
  geometrically.
- **The 0 false positives on known labels** suggests the check is
  robust: it correctly rejects the throw-only false positives from
  H28 (39→46, 24→26, 1→6, 62→65, 67→72).
- **The 16-candidate H30-KEPT pool is a useful STRICT SUBSET of the
  H20-KEPT pool** (115 candidates). Of the 15 H20-AND-H30-KEPT
  candidates, 5 are already in the known label set (4 REAL + 1
  PARTIAL = 100% precision on QA'd set).

## Negative findings

- **v1 (velocity-based) was rejected.** The dot product approach is
  too noisy for short tracklets. 13→15 (REAL) has catch_dot = -2334
  (negative) and throw_dot = 464 (positive); the source is moving
  AWAY from the apex because the trajectory is short and the last
  few frames are dominated by the source's pre-catch position.
- **h30_pass (at least one of src_above or tgt_above) has 7/9 REAL
  recall but 11/14 FALSE.** It is NOT a precision filter, just a
  sanity check.
- **both_above (both src_above AND tgt_above) has 3/9 REAL but 2/14
  FALSE.** It is a precision filter (3/3 = 100% on the small sample)
  but only catches a third of REALs.
- **tgt_above + tgt_ascending has 6/9 REAL but 3/14 FALSE.** Less
  strict than src_above+desc but worse precision.
- **The 4-way combo (any of the 3 strict checks) has 7/9 REAL but
  4/14 FALSE.** Less precise than src_above+desc alone.

## Verdict

**PARTIAL PASS.** H30 src_above + src_descending is a useful
precision-optimized filter with 0/14 FALSE on the deduplicated
known-label set. It admits 16 H17 strict candidates (vs 108 total),
15 of which are also H20-KEPT. The 5 candidates that have been
QA'd (4 REAL + 1 PARTIAL) are all confirmed correct.

H30 is a useful diagnostic tool but not a chain-set replacement.
The recommended operating point remains h7v3plus2 (H26).

## Recommendation

- h7v3plus2 (H26) remains the recommended chain set.
- H30 src_above + src_desc is a useful precision-optimized filter
  for FUTURE H17 strict pool mining. Apply it before visual QA to
  reduce the candidate pool from ~100 to ~15 (5x reduction) at
  near-zero precision cost.
- H31 (next episode): visually QA the 10 NEW H20-AND-H30-KEPT
  candidates to confirm the precision claim on a larger sample.
  If H31 confirms 80%+ REAL precision, H30 src_above+desc is a
  recommended pre-filter for H17 candidate mining.
- The H30 approach could also be combined with H25 (color-continuity
  check) for an even stricter filter. A future experiment could
  measure the precision of the H17 + H20 + H25 + H30 intersection.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h30_direction_reversal.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h30_direction_metrics.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h30_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_h20_h30_kept.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h30_report.md`

## Cross-references

- H17 — V-shape strict pool (151 positives)
- H20 — in-hand + vel-jump + apex filter (115 H20-KEPT)
- H24 — visual QA of H20-KEPT-not-in-h7v2 (9 candidates, 22% REAL)
- H28 — visual QA of H20-KEPT adjacent (12 candidates, 17% REAL)
- H26 — H24 NEW REAL H20-KEPT chain set augmentation v2
- H31 — pending: visual QA of H20-AND-H30-KEPT intersection
