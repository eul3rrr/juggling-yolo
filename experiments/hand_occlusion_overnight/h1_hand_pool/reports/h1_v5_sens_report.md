# H1 v5 — Sensitivity Grid on MIN_FROM_SLOPE (validation of v4d's threshold)

**Date:** 2026-08-28 ~05:10 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** v5 implemented and run. v4d's `MIN_FROM_SLOPE = 2.5`
is in a flat region of the precision/recall curve; thresholds
2.5-3.5 give identical results. Higher thresholds (4.0+)
start rejecting verified real catch-throws.

## 1. Hypothesis

v4d's `MIN_FROM_SLOPE = 2.5` was chosen by visual QA of v3
contact sheets. Is 2.5 the optimal threshold? A sensitivity
grid on `MIN_FROM_SLOPE` ∈ {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0}
checks whether the threshold is well-justified.

## 2. Implementation

`experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v5_sens.py`

- Reuses v2 internals.
- Sets `THROW_LEAVE_WINDOW_FRAMES = 7` (v3c setting).
- Renames `UNCONTEXTED_ENTRY` → `POTENTIAL_ENTRY` (v3a).
- Applies the v4 multi-feature filter at each `MIN_FROM_SLOPE`.
- Reports per-stem surviving/rejected link counts.
- Writes grid summary to `data/sens_grid_v5.json`.

## 3. Quantitative result

Total v3c links: 13 (11 identical + 2 youtube).

| MIN_FROM_SLOPE | n_surviving (total) | identical | youtube | Rejected pairs |
|---|---|---|---|---|
| 1.5 | 13 | 11 | 2 | (none) |
| 2.0 | 13 | 11 | 2 | (none) |
| **2.5** | **11** | **10** | **1** | 15→25, 35→40 |
| 3.0 | 11 | 10 | 1 | 15→25, 35→40 |
| 3.5 | 11 | 10 | 1 | 15→25, 35→40 |
| 4.0 | 10 | 9 | 1 | + 17→23 |
| 5.0 | 8 | 8 | 0 | + 11→14, 10→12 |

## 4. Verdict

**Threshold 2.5 is in a flat region** of the precision/recall
curve. Thresholds 2.5, 3.0, and 3.5 all produce identical
results (11 surviving links, 2 rejected: 15→25 and 35→40).
At threshold 4.0, the verified real catch-throw 17→23 starts
to be rejected. At threshold 5.0, two more verified real
catch-throws (11→14, 10→12) are rejected.

**v4d's `MIN_FROM_SLOPE = 2.5` is the optimal threshold.**
It rejects both v3 false positives while keeping all 7
verified real catch-throws. The flat region (2.5-3.5) means
the threshold is robust to small perturbations.

## 5. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v5_sens.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/sens_grid_v5.json`
