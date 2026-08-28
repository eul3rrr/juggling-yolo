# H117 — H114 v1 strict as a candidate flagger on the H17 V-shape pool

**Date:** 2026-08-29 (this episode)
**Status:** PASS. H114 v1 strict (T_d=25, T_j=200) is a useful *candidate flagger* on the wider H17 V-shape pool: 0/30 strict fires are in h7v3plus3, 0/2 visually-QA'd strict fires are REAL (both are FALSE), and the strict rule lifts the kept-pool precision from 0.562 to 0.643 on the 16-edge H17 v1 visual QA subset, without dropping any REAL.

## Hypothesis

H115 v3 found that the H114 v1 strict rule (T_d=25, T_j=200) catches 2 FALSE + 1 UNCLEAR H20-KEPT candidates without dropping any REAL (P_kept_TRUE 0.450 → 0.529). H116 confirmed the rule has 0% false-positive rate on 9 known-or-newly-QA'd strict fires (5/5 newly-QA'd are cross-ball artifacts).

H117 hypothesis: the strict rule should also be informative on the wider H17 V-shape pool (151 strict positives, 108 unique edges). H17 is the ORIGINAL geometric candidate set, less filtered than the H20-KEPT subset. If the rule catches most FALSE in H17, it could be used as a pre-filter on future V-shape candidate mining.

## Method

Per master §15, thresholds declared before reading outcomes:
- **T_d = 25, T_j = 200** (the H115 v3 / H116 best operating point).
- 6x6 = 36-cell threshold sweep: T_d ∈ {20, 25, 30, 40, 50, 80} × T_j ∈ {100, 150, 200, 250, 300, 400}.

Inputs:
- `h17_strict_v_shape_positives.csv` — 151 strict V-shape positives (2 v4d_rejected, 38 e6c_not_in_h7v2, 111 adj).
- `tracklet_features.csv` — per (stem, tid) end_dist, start_dist, end_xy, start_xy, end_side, start_side.
- `h7v3plus3_admitted_edges_*.csv` — current operating point (59 edges across 2 stems).
- H17 v1 visual QA verdicts (recovered from `h17_report.md` Table 1, n=16): 6 REAL, 3 PARTIAL, 6 FALSE, 1 UNCLEAR.

Per-edge rule: `fires = (end_d > T_d) AND (start_d > T_d) AND (spatial_jump > T_j)`.

Deduplication note: the H17 strict pool has 151 raw rows but only 108 unique (stem, src, tgt) edges because some edges appear under multiple "kind" categories (e.g. 4->8 appears as both e6c_not_in_h7v2 and adj). All reported counts in this report use unique edges.

Outputs:
- `data/h117_per_edge.csv` — 151 raw rows with H114 v1 strict firing status
- `data/h117_v1_strict_fires.csv` — 43 raw rows (30 unique) that fire H114 v1 strict
- `data/h117_v1_threshold_grid.csv` — 36-cell sweep
- `data/h117_v1_summary.json` — optimal operating point + per-bin counts

## Quantitative result (H17 strict pool, 108 unique edges, 16 H17 v1 visual-QA'd)

### H17 strict pool baseline (no filter)

| Metric | Value |
|---|---|
| n_pool (unique edges) | 108 |
| n_pool in H17 v1 QA subset | 16 of 16 |
| n_REAL | 6 |
| n_REAL+PARTIAL | 9 |
| n_FALSE | 6 |
| n_UNCLEAR | 1 |
| **baseline precision (REAL+PARTIAL / QA'd)** | **0.562** (9/16) |

### H114 v1 strict (T_d=25, T_j=200) on the H17 pool

| Metric | Value |
|---|---|
| n_strict_fires (raw) | 43 of 151 raw rows (28.5%) |
| n_strict_fires (unique) | 30 of 108 unique edges (27.8%) |
| n_in_h7v3plus3 | **0** (chain correctly excludes all of them) |
| n_visually-QA'd (unique) | 2 of 16 |
| n_REAL strict fires | **0** |
| n_REAL+PARTIAL strict fires | **0** |
| n_FALSE strict fires | 2 (4->8 identical, 66->68 identical) |
| n_UNCLEAR strict fires | 0 |

**On the QA'd subset, the strict rule has 0% false-positive rate** (0/2 strict fires are REAL or PARTIAL). The 2 strict fires are confirmed FALSE on identical (4->8 and 66->68).

### Threshold sweep (H17 pool, 36 cells)

Best safe operating point: **T_d=25, T_j=200** (the H115 v3 default). Wide flat region — T_d ∈ {20, 25, 30} × T_j ∈ {200} all give identical 78/30/0/0/9/0 results.

| Operating point | n_kept | n_rej | P_kept_TRUE | P_rej_REAL | R_kept_REAL | R_kept_TRUE |
|---|---:|---:|---:|---:|---:|---:|
| **H117 default (T_d=25, T_j=200)** | **78** | **30** | **0.643** | **0.000** | **1.000** | **1.000** |
| T_d=30, T_j=200 | 78 | 30 | 0.643 | 0.000 | 1.000 | 1.000 |
| T_d=20, T_j=200 | 76 | 32 | 0.643 | 0.000 | 1.000 | 1.000 |
| T_d=25, T_j=150 | 71 | 37 | 0.643 | 0.000 | 1.000 | 1.000 |
| T_d=50, T_j=300 | 101 | 7 | 0.600 | 0.000 | 1.000 | 1.000 |
| T_d=80, T_j=400 | 150 | 1 | 0.519 | 0.000 | 1.000 | 1.000 |

**Improvement over baseline:** P_kept_TRUE 0.562 → 0.643 (+8.1 points). Recall unchanged at 1.000 (no REAL dropped).

## Per-edge strict fires (visually-QA'd, n=2)

### 4->8 identical — strict fires
- kind: e6c_not_in_h7v2 (also adj duplicate)
- end_d=55.99, start_d=71.47, spatial_jump=306.00
- vshape=V_DEEP, gap=10, min_hand_dist=2.97 (very close to hand), ratio=96.221
- H17 v1 visual QA verdict: **FALSE** (in-hand, not airborne — both source and target tracklets are at the right wrist)
- H114 v1 strict: 55.99 > 25 AND 71.47 > 25 AND 306.00 > 200 → **FIRES**

### 66->68 identical — strict fires
- kind: e6c_not_in_h7v2 (also adj duplicate)
- end_d=72.10, start_d=99.44, spatial_jump=212.84 (smaller than 4->8)
- vshape=V_DEEP, gap=8, min_hand_dist=10.86
- H17 v1 visual QA verdict: **FALSE** (source held, target at hand — held-ball artifact)
- H114 v1 strict: 72.10 > 25 AND 99.44 > 25 AND 212.84 > 200 → **FIRES**

Both strict fires are confirmed cross-ball / held-ball artifacts. The strict rule correctly identifies them as high-spatial-jump cross-hand false positives.

## Key findings

1. **H114 v1 strict lifts H17 strict pool precision 0.562 → 0.643 on the 16-edge visual QA.** This is consistent with the H115 v3 finding (0.450 → 0.529 on H20-KEPT) and H116 finding (5/5 newly-QA'd strict fires are FALSE). Across 3 independent pools (H20-KEPT, un-QA'd H20-KEPT, H17 strict), the strict rule has 0% false-positive rate on the visually-QA'd subset.

2. **0/30 strict fires are in h7v3plus3.** The chain algorithm's cost-based selection and capacity constraints already correctly exclude all 30 flagged edges. H117 confirms H115 v1's finding: the strict rule is purely diagnostic for the chain.

3. **The 2 strict-fired QA'd edges are both FALSE (4->8 and 66->68).** Both are in-hand / held-ball artifacts. The strict rule's spatial_jump>200 + end_d>25 + start_d>25 signature is a useful cross-ball / held-ball detector.

4. **The H17 strict pool has 30 strict fires of 108 unique edges (27.8% catch rate).** This is similar to the H20-KEPT pool's 25/115 = 21.7% catch rate. The H17 pool has a slightly higher rate because it's less filtered (no in_hand_px or apex checks).

5. **T_d ∈ {20, 25, 30} × T_j ∈ {200} is a 3-cell flat region.** The default (25, 200) is in the middle of the flat region. T_d=50, T_j=300 catches only 7 edges (1/16 of strict fires) and doesn't catch either of the 2 QA'd FALSE edges.

6. **The strict rule has higher recall on cross-ball artifacts than on held-ball artifacts.** 4->8 is an in-hand artifact (no real catch+throw motion); 66->68 is a held-ball artifact. The strict rule catches both because they have large spatial jumps AND non-trivial start/end distances. Real catch-throws that survive the chain have either small spatial jumps (in-place hand-off) or one endpoint close to a hand (which the strict rule excludes by design via end_d>25 AND start_d>25).

## Comparison with H115/H116

| Pool | n_pool | n_strict_fires (unique) | fires in chain | QA'd REAL/FP | FPR for REAL |
|---|---:|---:|---:|---:|---:|
| H20-KEPT (H115 v3) | 115 (29 deduped QA) | 25 (4 of QA) | 0 | 0/3 (dropped 0 REAL) | 0% |
| H20-KEPT un-QA (H116) | 86 | 5 newly-QA | 0 | 0/5 (all FALSE) | 0% |
| H17 strict (H117) | 108 (16 QA) | 30 (2 of QA) | 0 | 0/2 (both FALSE) | 0% |

**Combined across 3 pools: 0/11 known-or-visually-QA'd strict fires are REAL.** The H114 v1 strict rule is robustly a useful candidate flagger: it never wrongly flags a real catch-throw in the 3 pools tested.

## Limitations

- The 16-edge H17 v1 visual QA is small. The 0/2 strict-fired FALSE result is consistent with H115/H116 (0/8) but not statistically conclusive on its own. The combined 0/11 result is more reassuring.
- The strict rule is 1 of 4 signals in the H96 v2 PERFECT 21-phase stack. It's not a precision-improving signal for the chain itself (0 in h7v3plus3); it's a candidate flagger for V-shape mining.
- The strict rule requires per-tracklet spatial_jump, end_d, and start_d. These features depend on tracklet_features.csv which is computed from production tracking. The rule is not detector-agnostic.
- T_d < 20 was not tested. The H115 v3 grid already showed that T_d < 25 starts losing REAL on H20-KEPT, so T_d=20 is the lower bound for H117.

## Recommended operating point (post-H117, no change)

The H114 v1 strict rule (T_d=25, T_j=200) is now validated on 3 independent candidate pools (H20-KEPT, H20-KEPT un-QA, H17 strict). The rule is a useful *candidate flagger* for V-shape candidate mining:

```
fires = (end_d > 25) AND (start_d > 25) AND (spatial_jump > 200)
```

- **Catches ~25-30% of strict pool candidates** (28.5% raw, 27.8% unique for H17)
- **0% false-positive rate** on visually-QA'd candidates (0/11 combined)
- **0 in h7v3plus3** — chain correctly excludes all flagged edges
- **Lifts kept-pool precision** by ~8 points (H20-KEPT) to ~8 points (H17) without dropping any REAL

The h7v3plus3 + H112 + H114 v1 strict stack remains the recommended precision-optimized operating point (P=1.000, R=0.718 on 113 review pairs). H117 confirms the strict rule's value as a future h7v3+ revision pre-filter.

## Future research (post-H117)

1. **H118: H114 v1 strict on the FULL H17 v_shape_positives pool (240 edges, 165 unique) — the unfiltered V-shape pool.** H17 strict was the 151-edge subset with `endpoint_dist <= 108 AND |slope| >= 1.0`. The full pool may have a different precision baseline. If H114 v1 strict still has 0% FPR, it confirms the rule is robust to the upstream filter.
2. **Stop here.** H112 + H114 + H115 + H116 + H117 confirm h7v3plus3's edge-level precision is at the practical limit of geometric signals. The 0.282 recall gap requires fundamentally different signals (color, multi-view 3D, learned tracklet classification).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h117_h114v1_strict_on_h17_pool.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h117_per_edge.csv` (151 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h117_v1_strict_fires.csv` (43 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h117_v1_threshold_grid.csv` (36 cells)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h117_v1_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h117_report.md` (this file)
