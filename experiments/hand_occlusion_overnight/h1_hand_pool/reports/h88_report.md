# H88 — H87 cross-validation on 113 manual review pairs

**Date:** 2026-08-28
**Question:** Does the H87 ball-detection-based pct_ge3 < 0.20
filter (which catches the H82 v1 FP at f=685-716 MANIPULATION)
add any new false positives or false negatives at the 113-pair
level?

## Background

H82 v1 (H75v2 + H78 mean_diff>10) achieves 95.2% accuracy on 21 H70
phases (TP=14 TN=6 FP=1 FN=0). The 1 FP is f=685-716 identical
MANIPULATION (CASCADE_3+), caught by H87's pct_ge3 < 0.20 rule.

H85 already cross-validated H82 v1 on the 113 manual review pairs:
H85 full P=0.979 R=0.648 (TP=46 FP=1 FN=25 TN=41), and H85 + (CONF or
UNCER) gate P=1.000 R=1.000 (33/33 pairs).

H88 re-runs the same 113-pair evaluation with the H87 filter added
on top of H82 v1.

## Result: H88 = H85 numerically

| Metric | H85 (H82 v1) | H88 (H82 v1 + H87) |
|--------|--------------|-------------------|
| H88 full P | 0.979 | 0.979 |
| H88 full R | 0.648 | 0.648 |
| H88 full FPR | 0.024 | 0.024 |
| TP | 46 | 46 |
| FP | 1 | 1 |
| FN | 25 | 25 |
| TN | 41 | 41 |
| + (CONF or UNCER) gate P | 1.000 | 1.000 |
| + (CONF or UNCER) gate R | 1.000 | 1.000 |

**H88 produces IDENTICAL results to H85 on the 113 review pairs.**

### Why identical?

Of the 113 review pairs, 15 have H70 phase mappings. H88's H87 filter
fires only on phases with pct_ge3 < 0.20. Of the 15 phase-mapped
pairs:
- 1 pair (ident s=39 t=48) is in f=685-716 (pct_ge3=0.15625 < 0.20).
  H87 REJECTS this pair. But the pair is already not in_h7v3plus3
  (label=wrong, NOT_IN_CHAIN), so the H87 rejection is a no-op.
- 14 other pairs are in YouTube phases with pct_ge3 ≥ 0.58. H87
  doesn't fire on any of them.

The H87 false FN cases (f=263-312 JUGGLING pct_ge3=0.04 and f=977-1011
FOUNTAIN pct_ge3=0.03) are NOT in the 113 review pairs. The 113 pairs
are mostly mid-air or hand-transition edges that fall outside H70
substantial phases.

## Per-phase mapping (113 review pairs)

| Phase | n_pairs | pct_ge3 | H87 fires? |
|-------|---------|---------|------------|
| ident f=685-716 (CASCADE_3+) | 1 | 0.16 | YES (but pair is wrong + NOT_IN_CHAIN) |
| youtu f=2-71 (MIXED_3+_UNCONFIRMED) | 1 | 0.74 | NO |
| youtu f=114-255 (MIXED_3+) | 1 | 0.71 | NO |
| youtu f=308-338 (MIXED_3+) | 1 | 0.65 | NO |
| youtu f=375-410 (MIXED_3+) | 1 | 0.69 | NO |
| youtu f=420-481 (MIXED_3+) | 2 | 0.69 | NO |
| youtu f=482-594 (FOUNTAIN_3+) | 3 | 0.66 | NO |
| youtu f=595-643 (MIXED_3+) | 1 | 0.67 | NO |
| youtu f=769-799 (MIXED_3+) | 1 | 0.65 | NO |
| youtu f=800-861 (FOUNTAIN_3+) | 2 | 0.58 | NO |
| youtu f=862-899 (MIXED_3+) | 1 | 0.71 | NO |

H87 fires only on f=685-716 (1 pair). The pair is already excluded by
in_h7v3plus3, so H88 == H85.

## Key findings

1. **H88 = H85 numerically.** The H87 filter has no effect on the
   113 review pairs because:
   - The 1 pair H87 would reject (s=39 t=48 wrong, NOT_IN_CHAIN)
     is already excluded.
   - The 14 YouTube phase-mapped pairs have pct_ge3 ≥ 0.58, well
     above the H87 threshold of 0.20.
   - The H87 false FN cases (f=263-312, f=977-1011) are not in the
     113 review pairs.

2. **The 113 review pairs and the H70 phase sample measure
   different things.** The 113 pairs are mostly mid-air edges
   (gap=0-3) outside H70 substantial phases. The H70 sample
   measures phase-level pattern classification. H87's value is at
   the phase level (catching the 1 FP), not at the edge level.

3. **H87 is a phase-level precision improvement, not an edge-level
   improvement.** The H82 v1 stack already achieves P=1.000 on
   the (CONF or UNCER) gate subset. H87 adds no new edge-level
   precision gain.

## Verdict: PASS (validation)

H88 confirms that the H82 v1 + H87 stack's phase-level improvement
(precision 1.000 on the 21-phase sample) does NOT introduce any new
edge-level issues. The (CONF or UNCER) gate remains P=1.000 R=1.000
on 33/33 review pairs.

## Negative findings

1. **H87 has no effect at the 113-pair level.** The H87 false FN
   cases (f=263-312, f=977-1011) are not in the 113 review pairs,
   and the 1 case H87 would reject (f=685-716) is already
   excluded by the chain filter.

2. **H82 v1 + (CONF or UNCER) gate is sufficient for chain-edge
   precision.** H87 doesn't add anything at this level. The
   H82 v1 + H87 stack's precision improvement is real at the
   phase level (90.5% acc, P=1.000) but invisible at the edge
   level.

3. **The 113 review pairs are a saturated evaluation set.** Most
   pairs are mid-air edges (gap=0-3) outside H70 substantial
   phases. New signals that fire only on substantial phases
   cannot be cross-validated on this set.

## Recommended operating point (post-H88)

**For chain-edge precision: h7v3plus3 + H10 v11 v3 + (CONF or UNCER) gate → P=1.000 R=1.000 on 33/33 review pairs**

**For phase-level pattern precision: h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v2 + H78 + H87 (pct_ge3 < 0.20) + H52 + H53 (90.5% acc, P=1.000 on 21 phases)**

For most downstream consumers, the H82 v1 + (CONF or UNCER) gate
remains the right choice. H87 + H82 v1 is useful only for downstream
consumers who consume the H70 phase sample directly (not the
chain edges).

## Future research

1. **H89: H87 cross-validation on a different edge-level ground
   truth.** The 113 review pairs are mostly mid-air edges that
   don't overlap with H70 phases. A different edge-level ground
   truth (e.g., phase-anchored pairs) would be needed to
   validate H87 at the edge level.

2. **H90: per-ball-count H87 threshold calibration.** The
   3-ball threshold (0.20) wrongly rejects f=263-312 and
   f=977-1011. A 5-ball threshold (0.50) catches f=482-594 but
   also catches f=800-861 (CASCADE_REAL) and f=339-374
   (FOUNTAIN). Per-ball-count calibration is unlikely to help
   because the YOLO false positive problem on YouTube is
   fundamental.

3. **H91: H87 with better YOLO confidence filtering.** If we only
   count YOLO detections with confidence > 0.7, the YouTube
   false positives might be filtered out. This requires
   post-filtering the existing detections.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h88_h87_per_pair.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h88_per_pair_eval.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h88_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h88_report.md`
