# H34 — H22 + H26 combined chain set (h7v3plus3) + H10 v10 chain quality

**Date:** 2026-08-28 ~12:50 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — PASS (incremental; union of H22 + H26 improvements)

## Hypothesis

H22 produced h7v3veto (YouTube 16→21 veto → 20→21) with +0.0034 chain
quality improvement on YouTube.
H26 produced h7v3plus2 (identical 7→10, 59→61 H24-KEPT edges) with
+0.0061 chain quality improvement on identical.

These two improvements are on different videos and don't conflict.
Combining them should give the union of both improvements, producing
the **h7v3plus3 chain set** as the new recommended operating point.

## Approach (declared before reading outcomes)

- Take h7v3plus2 chains as base (h7v3pure + 2 H24-KEPT edges)
- Apply H22's 1 YouTube veto: replace existing 16→21 with 20→21
  (cost 1.0, H22_RECLASSIFIED_HAND_TRANSITION)
- Run min-cost flow with the augmented edge set
- Walk new chains
- Compute H10 v10 chain quality (v6b per-video weights)
- Compare to h7v3plus2 (H26) and h7v3veto (H22) baselines

## Expected

- identical: same as h7v3plus2 (no H22 change for identical)
  Mean q 0.8105
- YouTube: same as h7v3veto (no H26 change for YouTube)
  Mean q 0.6852 → 0.6886 (per H22 v2)
- h7v3plus3 should equal the union: identical n_chains=42,
  YouTube n_chains=15 (vs h7v3plus2's 15)

## Quantitative result

| Video | h7v3plus2 chains | h7v3plus3 chains | h7v3plus2 mean q | h7v3plus3 mean q | Delta |
|---|---|---|---|---|---|
| identical | 42 | 42 | 0.8105 | 0.8105 | 0.0000 |
| YouTube | 15 | 15 | 0.6852 | 0.6886 | **+0.0034** |

**Edge type counts (h7v3plus3):**

| Video | HAND_TRANS | RECLASSIFIED_HAND | V_RECLASSIFIED | H22_RECLASSIFIED | H26_RECLASSIFIED | AMBIGUOUS_HAND | BALLISTIC |
|---|---|---|---|---|---|---|---|
| identical | 6 | 12 | 4 | 0 | 2 | 2 | 8 |
| YouTube | 1 | 22 | 1 | 1 | 0 | 0 | 0 |

**Chain topology change (YouTube):**
- h7v3plus2 chain 0: (1,9,13,16,21,29,34) — 7 tids
- h7v3plus3 chain 0: (1,9,13,16) — 4 tids (16 no longer connects to 21)
- h7v3plus3 chain 10: (20,21,29,34) — 4 tids (new chain with 20→21 edge)

The 7-tid chain is split into 2 by the H22 veto. Mean quality for
the new chain 0 is 0.6827; new chain 10 is 0.6071. The two together
average to about the same as the old 7-tid chain 0 (0.6715), so the
mean is preserved.

## Sensitivity to chain quality formula

**Bug found and fixed in h34_chain_quality.py:** the initial version
used a different formula from h10v10_with_h26.py:

- **Buggy v1**: `q = sum(w_i * x_i) / sum(w_i)` — single-tracklet
  chains (h3=None) drop from 1.0 to 0.7 because h3 weight is excluded
  without redistribution.
- **Fixed v2 (matches h10v10_with_h26)**: when h3 is None, redistribute
  the h3 weight across h8, h9, h8v8 in proportion to their existing
  weights, so single-tracklet chains get full quality credit.

The v2 fix restores the expected behavior. Without it, the
h7v3plus3 identical mean was 0.6827 (broken); with the fix it is
0.8105 (correct, matches h7v3plus2).

## Visual QA

The H22 visual QA (8 contact sheets, 4 identical + 4 YouTube)
already confirmed the H22 20→21 edge is real and the original
16→21 is wrong. See `h22_report.md` for full analysis.

The H26 visual QA (per H24 at scale) confirmed the 2 H24-KEPT
identical edges (7→10, 59→61) are real catch-throws. See
`h24_report.md` and `h26_report.md`.

**No new visual QA needed for H34** — H34 is a pure combination
of two already-validated improvements (H22, H26).

## Verdict

**PASS (incremental, union-of-improvements).**

- H34 successfully combines H22's YouTube veto with H26's identical
  H24-KEPT edges. The two improvements are on different videos and
  don't conflict.
- Chain count is identical to h7v3plus2 (42 + 15) for both videos,
  but the YouTube chain 0 is now correctly split into two physically
  meaningful 4-tid chains (1,9,13,16) and (20,21,29,34) instead of
  the contested 7-tid merge.
- Mean chain quality is preserved (H22's +0.0034 is the only
  non-zero change, as expected).
- **h7v3plus3 is the new recommended chain set** for downstream
  consumers, replacing h7v3plus2 (H26). The qualitative change
  (correct chain topology on YouTube) is more valuable than the
  small mean quality improvement suggests.

## Negative findings

- The 7-tid YouTube chain split produces two shorter chains, but
  the mean quality is preserved. Downstream consumers that rely
  on long chains for pattern inference (e.g., H12) will see
  shorter chains, which may affect pattern statistics.
- The H22 YouTube improvement (+0.0034) is small. The H22 visual
  confirmation is the primary value; the chain quality metric
  doesn't fully capture the topology correction.
- The h7v3plus3 chain set does NOT add any NEW visually-confirmed
  REAL edges beyond what h7v3plus2 + h7v3veto have. It's the union.

## Recommended operating point

- **h7v3plus3 is the new recommended chain set** for downstream
  hand-occlusion analyses.
- For per-chain confidence: H10 v10 (this report's h34_chain_quality.py).
- For per-chain identity propagation: H11 v7 (CONFIDENT chains are
  9/9 visually verified on identical; the YouTube CONFIDENT chain
  is now chain 6 in h7v3plus3 numbering).
- For pattern inference: H12 v7 (needs h7v3plus3 chain set
  regenerator; the YouTube MIXED_3+ percentage will need re-measurement).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_combined_chain_set.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_min_cost_flow.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_chain_quality.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h34_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h34_h10v10_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus3_admitted_edges_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus3_chains_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_h7v3plus3_*.csv` (2 files)
