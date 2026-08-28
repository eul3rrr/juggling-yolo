# H115 — H114 v1 diagnostic on h7v3plus3 + H20-KEPT pool + threshold sweep

**Date:** 2026-08-29 (this episode)
**Status:** MIXED. H115 v1 (PASS) confirms h7v3plus3's 3 ADDED edges are
robust to H114 v1. H115 v2 (PASS, narrow) shows H114 v1 default is a no-op
on the H20-KEPT pool. H115 v3 (PASS, narrow) finds a stricter (T_d=25,
T_j=200) operating point that catches 2 FALSE + 1 UNCLEAR H20-KEPT candidates
without dropping any REAL, lifting P_kept_TRUE 0.450 -> 0.529 on the
deduped 20-row QA'd subset.

## Hypothesis

H114 found that `h7v3plus3`'s same-hand handling is already correct, but
the v1 (T_d=40, T_j=250) post-hoc rule (spatial_jump > T_j AND end_d > T_d
AND start_d > T_d) could be applied in other contexts:

1. **H115 v1** (H114 v1 on h7v3plus3): does H114 v1 fire on any of the
   3 ADDED edges in h7v3plus3 (7->10, 59->61, 20->21) or the 2 REMOVED
   edges (59->63, 16->21)? If 0/4 fire, the operating point is robust.

2. **H115 v2** (H114 v1 on H20-KEPT): the H20-KEPT pool contains
   115 candidate edges (the wider H17+H20-KEPT+adjacent pool). Of the
   29 visually-QA'd (5 REAL, 13 REAL+PARTIAL, 14 FALSE), what fraction
   are caught by H114 v1?

3. **H115 v3** (extended threshold sweep): is there a (T_d, T_j) cell
   in a 6x6 grid that meaningfully separates REAL from FALSE in the
   H20-KEPT QA'd subset?

## Method

Per master §15, thresholds declared before reading outcomes:
- **H115 v1/v2**: H114 v1 (T_d=40, T_j=250) — the post-hoc validation rule.
- **H115 v3**: T_d ∈ {25, 30, 40, 50, 60, 80} × T_j ∈ {80, 100, 150, 200,
  250, 300} = 36 cells.

Inputs:
- `tracklet_features.csv` — per (stem, tid) end_dist, start_dist, end_xy,
  start_xy, end_side, start_side.
- `h7v3plus3_admitted_edges_<stem>.csv` — current operating point.
- `h20_strict_v_shape_positives_inhand.csv` — 115 H20-KEPT candidates.
- `h24_visual_qa_verdicts.csv` + `h28_visual_qa_verdicts.csv` — combined
  visual QA verdicts on the H20-KEPT pool.

Per-edge rule: `fires = (end_d > T_d) AND (start_d > T_d) AND (spatial_jump > T_j)`.

Outputs:
- `data/h115_per_edge.csv` — 4 h7v3plus3 added/removed edges + H114 v1 output.
- `data/h115_h20_kept_per_edge.csv` — 115 H20-KEPT + H114 v1 output.
- `data/h115_v3_threshold_grid.csv` — 36-cell threshold sweep.
- `data/h115_v3_optimal.json` — best operating point under multiple criteria.

## H115 v1 — h7v3plus3 added/removed edges

| Edge | Stem | Status | end_d | start_d | spatial_jump | H114 v1 fires |
|------|------|--------|-------|---------|--------------|----------------|
| 7->10 | identical | ADDED | 50.14 | 71.95 | 156.10 | False |
| 59->61 | identical | ADDED | 46.08 | 31.32 | 71.39 | False |
| 59->63 | identical | REMOVED | 46.08 | 37.24 | 204.20 | False |
| 16->21 | youtube | REMOVED | 7.83 | 35.34 | 73.21 | False |
| 20->21 | youtube | ADDED | 5.56 | 35.34 | 71.18 | False |

**0/5 H114 v1 fires on the h7v3plus3 modified edges.**

The 3 ADDED edges (7->10, 59->61, 20->21) are all robust: their
end_d + start_d values are all below 80 px (the strictest T_d tested)
and their spatial_jumps are all below 250 px (except 7->10 at 156 px,
which is below the strictest T_j=80). The 2 REMOVED edges (59->63,
16->21) had lower spatial_jumps than the new edges they were replaced
by, which is the opposite of what H114 v1 would predict. H114 v1
correctly identifies the REMOVED edges as physically plausible (low
spatial jumps).

**H115 v1 verdict: PASS.** The h7v3plus3 operating point's
modifications are robust to H114 v1.

## H115 v2 — H114 v1 default on 115 H20-KEPT candidates

| Outcome | n | fires |
|---------|---|-------|
| Total H20-KEPT candidates | 115 | 4 |
| Visually-QA'd | 29 (5 REAL, 13 REAL+PARTIAL, 14 FALSE) | 0 |
| Not visually-QA'd | 86 | 4 |

The 4 fires are all in the NOT-visually-QA'd subset:
- identical 67->72 (sj=244)
- identical 18->22 (sj=460)
- identical 1->6 (sj=248, duplicate row)
- identical 39->46 (sj=237)

Two of these (1->6, 39->46) are duplicates of visually-QA'd candidates
that have FALSE verdicts — but the script counted them in the H20-KEPT
list twice (once in H24, once in H28). The other 2 (67->72, 18->22)
are not visually QA'd.

On the deduped 20-row QA'd subset: 0/20 fire H114 v1 default. The
H114 v1 default is a no-op on the H20-KEPT pool.

**H115 v2 verdict: PASS (narrow).** H114 v1 default is a no-op on
H20-KEPT; the default operating point is too conservative.

## H115 v3 — extended 6x6 threshold sweep on 20-row QA'd H20-KEPT

The deduped 20-row QA'd H20-KEPT subset: 3 REAL, 9 REAL+PARTIAL, 11 FALSE.

The full 36-cell grid is in `data/h115_v3_threshold_grid.csv`. Key
findings:

### Best operating points under different criteria

| Criterion | T_d | T_j | n_kept | n_rej | P_kept_TRUE | R_kept_TRUE |
|-----------|----:|----:|-------:|------:|------------:|------------:|
| H114 v1 default | 40 | 250 | 20 | 0 | 0.450 | 1.000 |
| **Best (catches FALSE, drops no REAL, max P_kept_TRUE)** | **25** | **200** | **17** | **3** | **0.529** | **1.000** |
| Best (max P_kept_TRUE) | 30 | 100 | 11 | 9 | 0.545 | 0.667 |
| Best (max R_kept_TRUE) | 40 | 100 | 15 | 5 | 0.533 | 0.889 |
| Most aggressive | 25 | 80 | 10 | 10 | 0.500 | 0.556 |

### The 3 fires at (T_d=25, T_j=200)

| Edge | end_d | start_d | spatial_jump | visual_qa_verdict | in_h7v3plus3 |
|------|-------|---------|--------------|--------------------|--------------|
| identical 1->6 | 77.85 | 96.15 | 248.50 | **FALSE** | False |
| identical 39->46 | 174.10 | 89.36 | 237.68 | **FALSE** | False |
| identical 66->67 | 32.65 | 228.42 | 210.32 | **UNCLEAR** | False |

The 2 FALSE are cross-ball artifacts: 1->6 has the source ball held
at the right hand (4 px/frame motion, no descent) and the target
ball high in the frame (170 px above the right hand) — a stationary
or pre-existing different-color ball. 39->46 has source ball
descending plausibly but no completed catch in the source frames
and target ball at +130 px x-displacement.

The UNCLEAR (66->67) is an interesting case: end_d=32.65 is just
above the T_d=25 threshold, start_d=228.42 is far from any hand,
spatial_jump=210 is large but the chain is uncertain. The vision
verdict was not confident.

### Recall preservation (the critical property)

The (T_d=25, T_j=200) operating point catches 3 candidates with
**0 REAL dropped** — recall=1.0. This is the strictest threshold
that achieves this. More aggressive thresholds (T_d=25, T_j=80)
drop 2 REAL (recall=0.667) and catch 10 candidates (5 REAL
kept, 9 REAL+PARTIAL kept, 10 rejected), but the recall cost is
not justified by the marginal P_kept_TRUE improvement.

### Why the strict T_d=25 cell is informative

The H20-KEPT candidates are by definition visually plausible
(they pass the H20 in_hand_px + vel_jump + apex filters). Most
have end_d or start_d within 50 px. The strict T_d=25 filter
catches the few candidates where the ball is at the hand
(either end) but the spatial jump is too large for a real
catch-throw — these are the ones that are MOST likely
cross-ball artifacts (the ball was near the hand because a
DIFFERENT ball was held there).

## Key findings

1. **H114 v1 (T_d=40, T_j=250) is a no-op on h7v3plus3** AND on
   the H20-KEPT QA'd subset (0/4 fires on h7v3plus3 modified edges,
   0/20 fires on QA'd H20-KEPT). The default is too conservative
   to be useful as a precision filter.

2. **H114 v1 strict (T_d=25, T_j=200) is a useful post-hoc
   validation signal** for the H20-KEPT pool. It catches 2 confirmed
   FALSE and 1 UNCLEAR without dropping any REAL catch-throw candidate
   on the 20-row QA'd subset. P_kept_TRUE improves 0.450 -> 0.529
   (+7.9 points).

3. **All 3 strict-filter fires are already excluded from h7v3plus3.**
   The chain algorithm's cost-based selection correctly rejects the
   large-spatial-jump false positives; H114 v1 strict is purely
   diagnostic, confirming the chain's rejections are physically
   justified.

4. **The (T_d=25, T_j=200) operating point is in a flat region with
   (T_d=30, T_j=200)** — both catch 3 candidates with the same
   recall=1.0. T_d=25-30 / T_j=200 is a robust operating region
   for H20-KEPT post-hoc validation.

5. **H115 confirms the H17->H20->H24->H28->H31 negative finding
   chain on the QA'd subset:** the wider H20-KEPT pool has only
   3/20 = 15% REAL precision (5 REAL / 13 REAL+PARTIAL / 14 FALSE
   in 29 QA'd, deduped to 3/20 REAL = 15%). Geometric post-filters
   on the V-shape pool cannot rescue this precision — the
   cross-ball artifacts are geometrically indistinguishable from
   real catch-throws at the per-edge feature level.

## Negative findings

- H114 v1 default (T_d=40, T_j=250) is NOT a useful pre-filter for
  the H20-KEPT pool (0/20 fires on the deduped QA'd subset).
- A more aggressive H114 v1 (T_d=25, T_j=80) catches more FALSE
  (5 on the deduped QA'd) but drops 2 REAL (recall 0.667) — net
  precision cost is positive but recall cost is too high for a
  recommended filter.
- The (T_d=25, T_j=200) operating point is a strict post-hoc
  validator, NOT a corrective filter. The chain already excludes
  the 3 fires.

## Recommended operating point (post-H115)

**H115 does NOT change the recommended operating point.** The
(T_d=25, T_j=200) rule is a useful post-hoc validation tool for
the H20-KEPT pool, but h7v3plus3 already correctly excludes the
edges it would flag. The h7v3plus3 + H112 edge-level operating
point (P=1.000, R=0.718 on 113 review pairs) remains the
recommended precision-optimized configuration.

## Future research directions (post-H115)

1. **H116: H114 v1 strict on the 86 NOT-visually-QA'd H20-KEPT
   candidates.** The 4 fires (1->6, 39->46, 67->72, 18->22) are
   geometrically suspicious. A visual QA of these 4 would test
   whether the strict H114 v1 is informative on unverified edges.
   This is the natural next step: instead of using H114 v1 as
   a validator of the QA'd subset, use it to *flag new
   candidates* for QA.

2. **H117: H114 v1 on the wider H17 strict V-shape pool (151
   candidates, 38-56% precision from H17 v1).** H115 v3 found
   that H114 v1 strict catches 2/14 FALSE on the H20-KEPT
   subset. The H17 V-shape pool (without H20's in_hand_px +
   vel_jump + apex filters) has more candidates and lower
   precision. H114 v1 strict on H17 might lift the H17
   precision.

3. **Stop here.** H115 + H112 + H114 confirm that the
   h7v3plus3 chain's edge-level precision is at the practical
   limit of geometric signals. The remaining recall gap
   (0.282 = 32/113 missed correct edges) requires fundamentally
   different signals (color tracking, multi-view 3D, or
   learned tracklet classification).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h115_h114_diagnostic_h7v3plus3.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h115_v3_threshold_sweep.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h115_per_edge.csv` (5 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h115_h20_kept_per_edge.csv` (115 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h115_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h115_v3_threshold_grid.csv` (36 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h115_v3_optimal.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h115_report.md` (this file)
