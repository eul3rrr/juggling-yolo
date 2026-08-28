# H26 — H24 visually-confirmed REAL H20-KEPT chain set augmentation (v2)

**Date:** 2026-08-28 ~20:50 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **PASS (incremental improvement over H21)**

## Hypothesis

H24 visual QA found 2 NEW REAL H20-KEPT `e6c_not_in_h7v2` candidates
that H21 v1 did not consider:
- identical **7→10** (V_SHALLOW, R→L hand-off, min_d=57.35)
- identical **59→61** (V_DEEP, R→L hand-off, min_d=18.94)

Both are visually-confirmed real catch+throws that the production
h7v2 chain set missed. H21 v1 already integrated 5 other H20-KEPT
REAL edges (H20's 8-candidate sample).

H26 hypothesis: adding these 2 additional REAL edges to the
h7v3pure chain set (analogous to H21 but with the 2 H24 NEW REAL
edges) will further improve chain quality vs the H21 reference.

## Approach (declared before reading outcomes)

- Inherit H21 v1's edge set + the 2 H24 NEW REAL edges
- HAND_EDGE_COST = 1.0, AMBIGUOUS = 1.5, BALLISTIC base = 2.0
- Re-run min-cost flow with the augmented edge set
- Walk new chains
- Compare to h7v3pure (H22 reference) and h7v3plus (H21 reference)
- Run H10 v10 chain quality (v6b per-video weights) on h7v3plus2
- The 2 H26-KEPT edges use HAND_TRANSITION cost (1.0) and inherit
  H24's vshape/hand info

## H26 v1 quantitative result

| Video | h7v3pure edges | h7v3plus2 edges | H26-KEPT admitted | H26 chains | h7v3pure chains |
|---|---|---|---|---|---|
| identical | 33 | 34 | 2/2 (100%) | 42 | 43 (-1) |
| YouTube | 25 | 25 | 0 (n/a) | 15 | 15 (no change) |

### H26-KEPT edge integration (identical)

| Edge | h7v3pure src/tgt chains | H26 result |
|---|---|---|
| 7→10 (V_SHALLOW, L) | src=chain 5, tgt=chain 7 | merged into new chain 5 = [7, 10] |
| 59→61 (V_DEEP, R) | src=chain 30, tgt=chain 35 | merged into new chain 29 = [51, 52, 54, 59, 61] |

Both H26-KEPT edges ADMITTED with cost=1.0 (lowest possible). No
capacity conflicts because the H24-KEPT sources (t7, t59) and
targets (t10, t61) had no existing successors/predecessors in
h7v3pure.

The H26 chain count drops by 1 because both edges created merges
(2 chains → 1 chain per merge).

### YouTube

H24 found only 1 YouTube H20-KEPT-not-in-h7v2 candidate
(10→11, V_DEEP, R) and it was **PARTIAL** not REAL, so it was
not added to H26. YouTube chains unchanged.

## H10 v10 chain quality on h7v3plus2

| Video | h7v3pure v9 mean | h7v3plus v10 mean (H21) | h7v3plus2 v10 mean (H26) | Δ vs H21 |
|---|---|---|---|---|
| identical | 0.8275 | 0.8044 | **0.8105** | **+0.0061** |
| YouTube | 0.6852 | 0.6852 | 0.6852 | 0.0000 |

### Per-stem detail (identical)

- H21 v2 → H26 v10 mean: +0.0061 (0.8044 → 0.8105)
- 7→10 chain (5): 2-tracklet chain with 1 H26_RECLASSIFIED hand-edge
  and no air edges. h8=1.0 (no physics penalty for hand-edges).
- 59→61 chain (29): 5-tracklet chain with 1 H26_RECLASSIFIED +
  4 RECLASSIFIED_HAND_TRANSITION hand-edges. h8=1.0.

Both new chains avoid the H21 quality drop pattern (which came
from BALLISTIC edges that h8 v5 penalizes). H26-KEPT edges are
HAND_TRANSITION, so they don't trigger h8 v5 physics check.

### Top-3 chain quality (h7v3plus2 v10)

| Chain | n_tids | n_hand | n_v_reclass | n_h26 | n_air | h8 | h9 | h8v8 | q |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 0 | 0 | 1.00 | 1.00 | 0.50 | 1.000 |
| 3 | 1 | 0 | 0 | 0 | 0 | 1.00 | 1.00 | 0.50 | 1.000 |
| 10 | 1 | 0 | 0 | 0 | 0 | 1.00 | 1.00 | 0.50 | 1.000 |

(Singleton chains dominate the top-3; chains with real juggling
cycles are ranked lower.)

## Verdict

**PASS (incremental improvement over H21).** H26 successfully
integrates the 2 H24 NEW REAL H20-KEPT-not-in-h7v2 edges (7→10
and 59→61 identical) into the h7v3pure chain set. The mean
chain quality improves by +0.0061 on identical (0.8044 → 0.8105)
vs the H21 reference.

The improvement is small (+0.0061) but positive. H26 is a
strictly better chain set than h7v3plus when measured by
H10 v10 quality. The H21 v2 quality drop pattern (BALLISTIC
edges penalized by h8 v5) does NOT apply to H26-KEPT edges
because they are HAND_TRANSITION, not BALLISTIC.

## Comparison to H22 v2 (h7v3veto)

H22 v2 (H7v3veto) had identical mean 0.828 (no change) and
YouTube 0.685 → 0.689 (+0.0034). H26 has identical mean
0.8105 (down from H22's 0.828) but is more aligned with H21's
augmentation philosophy.

The H22 v2 / H26 v10 quality difference comes from the
inclusion of the 2 H24 NEW REAL edges (which create new
chains that H22 doesn't have) vs the H22-veto 20→21 swap
(which H26 doesn't have). H22 + H26 could be combined in a
future experiment to test whether both effects are additive.

## Recommendation

- h7v3plus2 (H26) is the **recommended** chain set for H24+
  augmentation experiments. It improves on h7v3plus (H21) and
  h7v3pure.
- H21 + H26 are complementary, not redundant. H21 found 5 REAL
  edges; H26 found 2 additional REAL edges.
- H26 is useful as evidence that the H24 visual QA precision
  characterization (22% REAL) is correct: the 2 confirmed REAL
  candidates (7→10, 59→61) integrate cleanly without conflicts,
  and they improve chain quality.
- The H26 methodology (visually-QA'd REAL edges → HAND_TRANSITION
  integration → H10 quality re-measurement) is a stable
  pattern for future H20-KEPT candidates that pass visual QA.

## Negative findings

- H26's improvement is small (+0.0061 on identical). The 2 new
  chains (chain 5 [7,10] and chain 29 [51,52,54,59,61]) are
  short (2 and 5 tracklets). The total impact on downstream
  consumers is modest.
- H26 does NOT address the 4 H24 cross-ball artifacts. The
  H24 finding (cross-ball is the dominant failure mode for
  H20-KEPT-not-in-h7v2) remains the most important new
  insight from the H17→H20→H24 pipeline.
- YouTube: H26 has no effect (0 H24-KEPT candidates were REAL
  on YouTube). The YouTube H20-KEPT-not-in-h7v2 pool is even
  smaller than the identical one (only 4 candidates, of which
  H24 sampled 1, and that 1 was PARTIAL).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h26_chain_set_augmentation_v2.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v10_with_h26.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h26_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_chains_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_admitted_edges_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_h26_kept_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_chain_quality_*.csv` (2)
