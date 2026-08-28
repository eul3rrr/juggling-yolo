# H85 — H82 v1 (H75v2 + H78 mean_diff>10) cross-validation on 113 manual review pairs

**Date:** 2026-08-28
**Question:** Does H82 v1 (which achieved 89.5% on the H70 phase sample)
improve over H77 (which achieved 84.2% on H70 / P=0.979 R=0.648 on 113 review pairs)
on the 113 manual review pairs? Or does the H82 v1 phase-level improvement
come at a cost on the chain-edge level?

## Background

H77 evaluated H75v1 + H78 mean_diff>10 on the 113 manual review pairs
and achieved:
- H77 full (113 pairs): P=0.979 R=0.648 FPR=0.024 (TP=46 FP=1 FN=25 TN=41)
- H77 + (CONF or UNCER) gate: P=1.000 R=1.000 (33/33 pairs)

H82 v1 added H74v2 (var<0.20 AND unique_LR<=2) on top of H75v1+H78 and
achieved 89.5% on the H70 phase sample (vs H77's 84.2%).

The H85 question: does H82 v1 also improve over H77 on the 113 review
pairs? Specifically, does H74v2 catch any new false positives on the
chain-edge level? And does H78 mean_diff>10 add any new rejects?

## Method

For each of the 113 manual review pairs:
1. Find the H70 phase containing the (source_end + target_start) / 2 midpoint frame.
2. Apply the H82 v1 stack:
   - FOUNTAIN_3+: H43 (conf<0.55) OR H69 (spec_conc<0.15) OR H74v2 (var<0.20 AND unique_LR<=2) OR H78 (mean_diff>10)
   - CASCADE_3+: H74v2
   - MIXED_3+: H71 (spec_conc<0.10)
3. Pair is KEPT iff in_h7v3plus3 AND H82 v1 does not reject.
4. Compute per-pair confusion matrix.

## Result (H85 full vs H77 full)

H77 full: P=0.979 R=0.648 FPR=0.024 (TP=46 FP=1 FN=25 TN=41)
**H85 full: P=0.979 R=0.648 FPR=0.024 (TP=46 FP=1 FN=25 TN=41)**

H85 and H77 give IDENTICAL results on the 113 review pairs. The 47
"kept" pairs are exactly the same 47 in both evaluations.

### Why identical?

Of the 113 review pairs:
- 98 have no H70 phase (their midpoint frame is outside any H70 substantial phase)
- 15 have an H70 phase (and are evaluated by the phase filter)

For the 98 no-phase pairs, both H77 and H85 use only the in_h7v3plus3
filter (the phase filter is a no-op because there's no phase to evaluate).

For the 15 phase-mapped pairs, H85's H82 v1 stack and H77's H75v1+H78
stack give the same result on every pair. Specifically:
- 5 FOUNTAIN_3+ pairs (s=17 t=24, s=19 t=22, s=30 t=37, s=33 t=36, s=23 t=24)
  on YouTube f=482-594 and f=800-861 are rejected by H69 (spec_conc<0.15).
  Both stacks reject these.
- 1 MIXED_3+_UNCONFIRMED pair (s=3 t=6) on YouTube f=2-71 is rejected
  by H71 (spec_conc<0.10). Both stacks reject.
- 6 MIXED_3+ pairs on YouTube f=114-255, f=267-298, f=308-338, f=375-410
  are KEPT. Both stacks keep.
- 1 CASCADE_3+ pair (s=39 t=48 identical) is NOT_IN_CHAIN. No filter applies.

H74v2 doesn't fire on any of the 15 phase-mapped pairs because:
- H74v2 = var<0.20 AND unique_LR<=2
- The 3 FOUNTAIN_3+ pairs that H74v1 would have rejected (f=482-594
  var=0.134 unique_LR=2, f=800-861 var=0.199 unique_LR=2, f=482-594 again)
  already fail H69 (spec_conc<0.15=0.140) so the H74v2 distinction
  is moot.

H78 mean_diff>10 doesn't fire on any of the 15 phase-mapped pairs because:
- f=482-594 mean_diff=5.08 (below 10)
- f=800-861 mean_diff=4.89 (below 10)
- All YouTube f=114-255 phases have mean_diff ~0-5 (the wrist-distance
  data has n_unique issues for these phases)

### Per-gap subsets (H85)

| gap | TP | FP | FN | TN | P | R | FPR |
|-----|----|----|----|----|----|----|----|
| 0   | 6  | 0  | 2  | 6  | 1.000 | 0.750 | 0.000 |
| <=1 | 9  | 0  | 3  | 8  | 1.000 | 0.750 | 0.000 |
| <=3 | 24 | 0  | 9  | 14 | 1.000 | 0.727 | 0.000 |
| all | 46 | 1  | 25 | 41 | 0.979 | 0.648 | 0.024 |

### Per-stem (H85)

| stem | TP | FP | FN | TN | P | R | FPR |
|------|----|----|----|----|----|----|----|
| ident | 27 | 1  | 18 | 39 | 0.964 | 0.600 | 0.025 |
| youtu | 19 | 0  | 7  | 2  | 1.000 | 0.731 | 0.000 |

YouTube is perfect precision (1.000). Identical has 1 FP (s=22 t=27)
which is also the H59 FP (q11=0.316 LOW, EXCLUDED by the (CONF or UNCER)
gate).

### H85 + (CONF or UNCER) gate

**H85 + (CONF or UNCER) gate: P=1.000 R=1.000 FPR=0.000 (33/33 pairs).**

The 33 pairs are 16 identical + 17 YouTube, all in the (CONF or UNCER)
quality band. This matches H77's 33/33 = 100% finding.

The 14 H85-KEPT-but-LOW pairs are all in the q11<0.4 LOW quality band
(13 correct + 1 wrong, the 1 wrong being s=22 t=27 identical).

## Key findings

1. **H82 v1's phase-level improvement (89.5% vs 84.2%) does NOT come
   at any cost on the chain-edge level.** H85 and H77 produce
   identical 113-pair metrics (P=0.979, R=0.648, FPR=0.024).

2. **The (CONF or UNCER) gate achieves perfect precision AND recall
   on 33/33 review pairs.** This is a strong, validated operating
   point for downstream consumers who need the highest-precision
   chain-edge set.

3. **The 14 LOW-quality pairs (H85 KEPT but EXCLUDED by gate) include
   13 correct + 1 wrong.** The wrong pair (s=22 t=27 identical) is
   the H59 FP, which the (CONF or UNCER) gate correctly excludes.
   The 13 correct LOW pairs are recoverable by the gate if the user
   wants the highest precision.

4. **H82 v1 is a strict improvement over H77 at the phase level with
   no edge-level regressions.** This is an important validation:
   the H74v2 refinement (unique_LR<=2) and the H78 mean_diff>10
   addition did not cause any new false positives in the chain-edge
   evaluation.

## Recommended operating point (post-H85)

**h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v2 + H78 + H52 + H53 + (CONF or UNCER) gate**

For precision-maximizing downstream consumers:
- H85 + (CONF or UNCER) gate: P=1.000 R=1.000 on 33/33 review pairs

For exhaustive coverage:
- H85 (or H77, equivalent) on full 113 pairs: P=0.979 R=0.648

## Verdict: PASS (validation)

H85 validates that the H82 v1 stack achieves 89.5% phase-level accuracy
WITHOUT any chain-edge precision regression. The two evaluations
(phase level at 89.5% / edge level at P=1.000 on gated subset)
are consistent.

## Negative findings

1. **H85 == H77 numerically.** The H82 v1 stack's phase-level
   improvement (89.5% vs 84.2%) does not translate to chain-edge
   improvement because most review pairs (98/113) are outside any
   H70 substantial phase. The 15 phase-mapped pairs are
   rejected/kept identically by both stacks.

2. **The 1 remaining FP (s=22 t=27 identical) is fundamental.**
   It's a chain-edge-level low-quality edge that the
   (CONF or UNCER) gate correctly excludes. No phase-level signal
   would change this.

3. **The 5 H69-rejected correct pairs (YouTube FOUNTAIN_3+ in
   f=482-594 and f=800-861) are recoverable only by relaxing
   H69 or by changing the H12 v8 FOUNTAIN_3+ classification.**
   Neither is in scope for H85.

## Future research

1. **H86: H40v2 metric refinement for 5-ball jugglers** — the
   fundamental H40v2 limitation on f=267-298 (unique_LR=1, real
   5-ball juggling) needs a different approach. Possibilities:
   ball-detection-based check, hand-velocity-based check, or
   pattern-periodicity check.

2. **H87: CASCADE_3+ classification reliability** — the
   CASCADE_3+ class has 0/2 accuracy on substantial phases
   (H73 finding). A new signal for CASCADE_3+ misclassification
   (e.g., ball trajectory crossings, hand-crossing events)
   would be valuable.

3. **H88: extend H82 v1 to 113 review pairs at a deeper level.**
   The H85 finding suggests that the H70 phase sample is too
   small to characterize the full edge-level impact. A
   per-tracklet-level H82 v1 analysis (not just per-phase)
   could reveal new signals.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h85_h82v1_per_pair.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h85_per_pair_eval.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h85_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h85_report.md`
