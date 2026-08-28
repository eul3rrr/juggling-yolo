# H22 — H20-KEPT edge veto mode (H22 v1 + H22 v2 chain quality)

**Date:** 2026-08-28 ~20:15 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — MIXED (consumer-pass, narrow-scope)

## Hypothesis

H21 v1 integrated 3/4 visually-confirmed REAL H20-KEPT edges on identical,
but the YouTube 20→21 edge was REJECTED by capacity conflict with the
existing 16→21 edge. Visual analysis of the H20 contact sheet for 20→21
strongly suggests the existing 16→21 edge is WRONG:

- Tracklet 20 is the canonical contact tracklet (3 detections at the
  right wrist with min_d ≈ 5 px, f=471-473)
- Tracklet 16 is a spurious earlier-detection (n=126 frames, ending at
  f=468, 2 frames BEFORE t20's contact)
- The catch physically happens on t20, not t16

H22 implements a VETO mode: when an H20-KEPT edge is rejected by capacity
because of an existing edge, check if the H20-KEPT edge has STRONGER
hand-proximity evidence (lower min_d from V-shape) than the existing
edge. If so, VETO the existing edge and admit the H20-KEPT edge.

## Veto criteria (declared from physical geometry, not tuned to labels)

- `MIN_D_VETO = 30.0` px — the H20-KEPT edge's V-shape min_hand_dist must
  be below this (a real catch+throw has min_d < 30)
- `VETO_DIST_THRESHOLD = 30.0` px — the existing edge's target
  start_dist must be above this (a real catch has the ball at the hand,
  start_dist < 30)
- The H20-KEPT edge's source must NOT already have a successor in the
  chain set (otherwise vetoing would break a chain topology)

## H22 v1 quantitative result

| Video | Veto decisions | H22-KEPT admitted | Chains |
|---|---|---|---|
| identical | 0 (2 H20-KEPT blocked by source successor) | 0 | 43 (no change) |
| YouTube | 1 (20→21 vetoes 16→21) | 1 | 15 (chain 0 split) |

**Identical side:** 2 H20-KEPT edges (17→22, 68→70) had strong V-shape
(min_d=22.4 and 12.9) AND the existing target had high start_dist
(297.2 and 197.1) — both criteria met. But the H20-KEPT sources
(t17 and t68) already have successors in the chain set (t17→t23 in
chain 13, t68→t71 in chain 31). The H22 veto would need to break
the existing chain topology, so they were excluded.

**YouTube side:** 1 H20-KEPT edge (20→21) has strong V-shape (min_d=5.3)
AND the existing target (t21) has start_dist=35.3 > 30. The H20-KEPT
source (t20) is a singleton (no existing successor), so vetoing
16→21 is safe. The H22 veto successfully removed 16→21 and admitted
20→21.

**Chain topology change (YouTube):**
- h7v3pure chain 0: (1,9,13,16,21,29,34) — 7 tids
- h7v3veto chain 0: (1,9,13,16) — 4 tids (16 no longer connects to 21)
- h7v3veto chain 10: (20,21,29,34) — 4 tids (new chain with 20→21 edge)

The original 7-tid chain was split into TWO chains by the veto. The
H22 chain 0 has the first 4 tids, and a NEW chain 10 contains the
last 4 tids (20,21,29,34) connected by the H22-KEPT 20→21 edge.

## H22 v2 chain quality (H10 v9 on H7v3veto chains)

| Video | h7v3pure v9 mean | h7v3veto v11 mean | Delta |
|---|---|---|---|
| identical | 0.828 | 0.828 | 0.000 |
| YouTube | 0.685 | 0.689 | **+0.0034** |

The YouTube mean quality improved by 0.0034. This is a small but
real signal that the H22 veto mode produces better-calibrated chains
(20→21 is the right edge, 16→21 is wrong).

## Verdict

**MIXED (narrow-scope PASS).** H22 successfully vetoes the existing
16→21 YouTube edge in favor of the H20-KEPT 20→21 edge, producing a
slight chain quality improvement (+0.0034 on YouTube). The chain
topology change is consistent with the visual analysis: t16 is a
spurious earlier-detection, t20 is the canonical contact.

H22 has a narrow scope:
- The veto only applies when the H20-KEPT source has no existing
  successor (the "source successor" check). This excludes the
  identical-side cases (17→22, 68→70) where t17 and t68 already
  have successors in the chain set.
- A more aggressive H22 v2 could break the existing chain topology
  to admit these edges, but this would be a much more complex
  change with chain-quality tradeoffs.

**Recommendation:**
- H22 is a useful narrow-scope experiment. The YouTube case shows
  the veto mode can correct existing chain errors when the H20-KEPT
  has stronger evidence.
- The h7v3veto YouTube chain set has the correct physics (20→21 is
  the real catch, 16→21 is spurious) and a slight quality improvement.
- H22 is NOT recommended as the default chain set because the
  chain topology change is significant (long chain split into 2
  shorter chains) and the quality improvement is small.
- h7v3pure (H7v2 + H15v2) remains the recommended chain set.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h22_veto_mode.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h22v2_chain_quality.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h22_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h22v2_chain_quality_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_chains_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_admitted_edges_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_veto_decisions_*.csv` (2)

## Negative findings

- The H22 veto is narrow-scope: 0 identical veto decisions, 1 YouTube
  veto decision. The 2 H20-KEPT edges on identical (17→22, 68→70) had
  strong V-shape AND weak existing target, but the H20-KEPT sources
  already had successors in the chain set. A more aggressive H22 could
  break the existing chain topology to admit these edges, but this
  would be a much more complex change.
- The YouTube chain topology change is significant: the original 7-tid
  chain (1,9,13,16,21,29,34) is split into 2 chains (1,9,13,16) and
  (20,21,29,34) by the veto. The chain count is unchanged (15→15),
  but the chain lengths are shorter on average. The mean quality
  improvement is small (+0.0034).
- The "source successor" check is a conservative choice. It prevents
  the veto from breaking existing chains, but it also limits the
  veto's applicability. A more aggressive H22 v2 could allow source
  successor conflicts if the H20-KEPT edge is much stronger.
- H22 demonstrates that the existing 16→21 YouTube edge is wrong,
  but the cost of correcting it (chain split + small quality change)
  may not be worth the benefit. The visual confirmation is the
  primary value of H22.
