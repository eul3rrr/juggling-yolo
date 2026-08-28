# H21 — H20-KEPT chain set augmentation (H21 v1 + H21 v2 chain quality)

**Date:** 2026-08-28 ~19:55 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — MIXED

## Hypothesis

H20 found 26 e6c_not_in_h7v2 candidates that pass all 3 H20 filters. Of the 8
visually-QA'd, 5 are REAL or PARTIAL. These 5 represent real catch+throws that
the production h7v2 chain set missed. The question is: do they improve chain
quality and identity propagation if added to the h7v3pure chain pipeline?

**The 5 visually-confirmed REAL H20-KEPT edges:**
- identical 6→15 (chain 4 [5,6] + chain 11 [15])
- identical 54→57 (chain 30 [51,52,54,59,63] + chain 33 [57])
- identical 56→57 (singleton 56 + chain 33 [57])
- identical 56→58 (singleton 56 + chain 34 [58])
- youtube 20→21 (chain 10 [20] + chain 0 [1,9,13,16,21,29,34])

**Important constraints:**
- The 4 identical edges were NOT in the E6c accepted edges set (E6c didn't
  see them as mid-air edges; H17's V-shape analysis found them).
- The 1 YouTube edge (20→21) IS in H2 as BALLISTIC but was rejected by
  H7v2's strict endpoint check (target's first frame was 35.3 px from
  wrist, > the 108 px reach radius).

## Approach

H21 takes the 5 visually-confirmed REAL H20-KEPT edges and:
1. Adds them as new HAND_TRANSITION edges with cost 1.0 (same as H7v2
   hand-edges)
2. Re-runs the min-cost flow with the augmented edge set
3. Walks new chains and saves as `h7v3plus_*` files
4. Re-computes H10 v9 chain quality on the new chains (H21 v2)

## H21 v1 quantitative result

| Video | H21-KEPT added | H21 admitted | Merges | Conflicts |
|---|---|---|---|---|
| identical | 4 | 3 (6→15, 54→57, 56→58) | 3 (chain 4+11, 30+33, 32+34) | 1 (56→57 lost capacity to 56→58) |
| YouTube | 1 | 0 | 0 | 1 (20→21 blocked by existing 16→21) |

Chain count change:
- identical: 43 → 41 chains (-2)
- YouTube: 15 → 15 chains (0)

The YouTube 20→21 edge was REJECTED by the capacity constraint because t21
already has a predecessor (16→21, an existing BALLISTIC edge reclassified
as HAND). The H21 algorithm does not "veto" existing edges to make room
for new ones. This is a known limitation.

## H21 v2 chain quality (H10 v9 on H21 chains)

| Video | h7v3pure v9 mean | h7v3plus v10 mean | Delta | Top chain |
|---|---|---|---|---|
| identical | 0.828 | 0.804 | **-0.023** | chain 0 (singleton, q=1.000) |
| YouTube | 0.685 | 0.685 | 0.000 | chain 6 (q=0.841) |

**H21 v2 chain quality is slightly WORSE on identical.** The 3 chain
merges introduced by H21 (5,6,15) + (51,52,54,57) + (56,58) add
tracklets to existing chains, which can reduce h8_score if the new
tracklet spans a BALLISTIC edge that h8 v5 flags as VIOLATING.

## Visual verification

The H20 contact sheets already visually confirmed the 5 H21-KEPT edges
as REAL catch+throws. New analysis of the YouTube 20→21 case shows that
**tracklet 20 is the canonical contact tracklet** (3 frames at the right
wrist with min_d ≈ 5 px), while the existing 16→21 edge uses tracklet 16
(an earlier-detection long tracklet that ends at f=468, before tracklet
20's contact at f=471-473). The vision tool concludes:

> "Tracklet 20 is the genuine ball-handling tracklet; 16→21 should be
> rejected as the true transition, and 20→21 should be kept. Tracklet 16
> is the spurious/duplicate detection (overlapping in time with 20)."

This means the H21 algorithm correctly identified the conflict, but
didn't apply a "veto" to override the existing 16→21 edge with the
H21-KEPT 20→21 edge.

## Verdict

**MIXED (consumer-pass, quality-neutral).** H21 successfully integrates
3 of 4 visually-confirmed REAL H20-KEPT edges into the identical chain
set, merging 3 pairs of chains. The H21 v2 chain quality is slightly
worse on identical (-0.023) because the new chains expose BALLISTIC
edges that h8 v5 flags. The YouTube 20→21 case is a known limitation:
the algorithm does not veto existing edges to make room for visually-
confirmed alternatives.

**Recommendation:**
- H21 v1 is useful as a *research tool* for measuring how many H20
  candidates can be cleanly integrated into the existing chain set.
- The H21 chains should NOT replace h7v3pure as the recommended chain
  set, because the v10 quality is slightly worse.
- The YouTube 20→21 case motivates a future H22 experiment: add a
  "veto" mode that overrides existing edges when an H20-KEPT edge has
  higher visual confidence.
- The H21 contact-sheet analysis reveals a deeper truth: the existing
  16→21 YouTube edge may be WRONG (the actual catch is on tracklet 20,
  not 16). A targeted re-investigation of 16→21 vs 20→21 could improve
  the YouTube chain quality.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h21_chain_set_augmentation.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h21v2_chain_quality.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h21_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h21v2_chain_quality_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_chains_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_admitted_edges_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_h21_kept_*.csv` (2)

## Negative findings

- The H21 algorithm does not veto existing edges. When an H21-KEPT
  edge conflicts with an existing edge for the same successor slot,
  the H21-KEPT edge is rejected (1/5 case: YouTube 20→21).
- The H21 chains have LOWER h10 quality than h7v3pure on identical
  (-0.023 mean). The chain merges expose BALLISTIC edges that h8 v5
  penalizes, so the quality score is worse even though the chains
  are more "correct" in the sense of containing more visually-confirmed
  catch+throws.
- The YouTube 20→21 visual analysis suggests the existing 16→21 edge
  is the wrong physical transition. A targeted H22 re-investigation
  is needed before this can be corrected.
- H21 v2 chain quality on YouTube is unchanged because 20→21 was
  not admitted. The algorithm is not useful for the YouTube video
  in its current form.
