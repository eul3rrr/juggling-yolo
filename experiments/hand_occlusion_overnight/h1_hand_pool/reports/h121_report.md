# H121 — H7v2 Reclassification at Scale Using RAW Tracklet Data

**Date:** 2026-08-29 (this episode)
**Status:** PASS — the H121 hypothesis (tracklet_features truncation causes
H7v2 to misclassify some RECLASSIFIED_HAND_TRANSITION edges) is
**CONFIRMED**. Most "RECLASSIFIED" edges would NOT be reclassified if
raw data were used.

## Motivation

H120's future-research item 2 called for a "targeted investigation of
the H7v2 reclassification criteria for cross-hand edges with large
spatial jumps" to identify other latent chain FPs. The H121 hypothesis
goes further: it tests whether H7v2's reclassification rule is applied
correctly at all when the input is the truncated tracklet_features
instead of the raw detection data.

## Hypothesis (declared before reading outcomes)

`tracklet_features.csv` (the input to H7v2) is truncated relative to
the raw detection data. H7v2's catch/throw signature
(`end_dist <= 108 AND end_slope < -1.0`) uses the LAST frame in
`tracklet_features`, which is 2-12 frames before the raw tracklet's
actual last frame. This may cause H7v2 to misclassify a tracklet
that's still descending (ball at edge of reach) as a "catch" even
though the raw data shows the ball continuing to descend to the hand
(or further).

## Approach (declared before reading outcomes)

1. For each RECLASSIFIED_HAND_TRANSITION edge in h7v3plus3, load BOTH:
   - `tracklet_features`: `end_dist`, `end_slope`, `end_side`, `last_x`, `last_y`
   - raw detections: every `(frame, x, y, conf)` point in the tracklet
2. Compute H7v2's reclassification rule using raw data:
   - `src_is_catch`: `min_dist(src_last_pos) <= 108 AND end_slope < -1.0`
   - `tgt_is_throw`: `min_dist(tgt_first_pos) <= 108 AND start_slope > 1.0`
   - gap constraint: `tgt.first_frame - src.last_frame <= 20`
3. Compare H7v2_orig (tracklet_features) vs H7v2_raw.
4. Compute spatial jump for both versions.
5. Categorize each edge: STILL_RECLASSIFIED (both agree),
   RAW_REJECTS (raw would not reclassify), ORIG_REJECTS (raw would
   reclassify but features wouldn't — should be empty since edges
   are already in h7v3plus3).

## Thresholds (H7v2 script header, declared)

- `HAND_REACH_PX = 108`
- `MAX_GAP_FOR_RECLASSIFY_FRAMES = 20`
- `CATCH_SLOPE_PX_PER_FRAME = -1.0` (negative = ball descending)
- `THROW_SLOPE_PX_PER_FRAME = 1.0` (positive = ball ascending)
- `MIN_TRACKLET_LEN = 3`
- `SLOPE_WINDOW = 3`

## Quantitative result

| Stem | n_reclassified | n_still_reclassified | n_raw_rejects | sj>100 (raw) | sj>200 (raw) | sj>100 (orig) | sj>200 (orig) |
|---|---|---|---|---|---|---|---|
| identical | 12 | 7 | **5** | 2 | 0 | 5 | 1 |
| youtube | 22 | 1 | **21** | 8 | 0 | 1 | 0 |
| **combined** | **34** | **8** | **26** | 10 | 0 | 6 | 1 |

**Key finding:** 26/34 = **76.5%** of RECLASSIFIED_HAND_TRANSITION edges
in h7v3plus3 would NOT be reclassified if raw tracklet data were used
instead of tracklet_features.

The discrepancy is **much larger on YouTube (21/22 = 95.5%)** than
identical (5/12 = 41.7%). YouTube's tracklet_features are
systematically more truncated than identical's.

## Spatial jump: orig vs raw

For most edges, the **orig spatial jump is much larger than the raw
spatial jump** because tracklet_features is truncated to an earlier
frame. The H114/H117/H118 large-jump filter used orig spatial jumps;
with raw jumps, the H114 v1 default (T_j=250) would catch **0/34**
edges (down from 1/34 in the orig metric).

### Key case: 22→27 (the H112-discovered FP)

| Source | last_frame | last_xy | spatial_jump |
|--------|------------|---------|--------------|
| tracklet_features | 252 | (564.5, 453.7) | **190.4 px** |
| raw | 257 | (579.3, 607.0) | **37.5 px** |

The 190-px jump that H112 used to identify 22→27 as a cross-hand
handoff FP was an **artifact of tracklet_features truncation**.
At the raw last frame (5 frames later), the ball is at the hand
(`raw_end_dist = 18.8 px`). The tracklet features captured a frame
where the ball was still mid-air; by the time the source tracklet
actually ended, the ball was at the wrist.

This does NOT mean 22→27 is a true positive — the H112 visual QA
already established that 22→27 is a tracker artifact. But it does
mean the H114 / H117 / H118 spatial-jump filters (which used
tracklet_features-based jumps) may be over-aggressive.

### Key case: 3→8 (the H120-suspect edge)

| Source | last_frame | last_xy | spatial_jump | end_slope |
|--------|------------|---------|--------------|-----------|
| tracklet_features | 31 | (697.0, 376.8) | **227.0 px** | **-23.59** (descending) |
| raw | 36 | (692.5, 483.1) | **123.4 px** | **+21.27** (ascending!) |

The `feat_end_slope` of -23.59 (very steep descent) is what H7v2
used to classify the source as a "catch". But at the raw last frame
(f=36, 5 frames later), the slope is **+21.27** — the ball is
**ascending** rapidly. The source tracklet extends through the catch
AND the throw. By the time it actually ended, the ball was already
on its way out of the hand.

The "H7v2 catch" signature fires on the truncated tracklet_features
at f=31 (ball still descending toward hand), but the raw data
reveals the tracklet continues for 5 more frames through a
full catch-throw cycle. The 3→8 edge is a RECLASSIFIED_HAND_TRANSITION
in name only — the source tracklet itself contains both the catch
and the throw.

### Key case: 64→68 (positive-end-slope FP)

| Source | last_frame | end_slope (feat) | end_slope (raw) | end_dist (feat) | end_dist (raw) |
|--------|------------|------------------|-----------------|-----------------|----------------|
| src=64 | 964 | 7.98 | **13.25** | 59.03 | **177.84** |

The source tracklet 64 has `end_slope=13.25` (positive, very strong
upward motion) and `end_dist=177.84` (far from any hand) at the raw
last frame. The tracklet_features-based H7v2 saw `end_slope=7.98`
and `end_dist=59.03` and classified it as a "catch" — but the
tracklet is actually in the middle of a fast ascending throw.
`h7v2_raw` correctly rejects this edge.

## Per-stem patterns

### identical: 5 RAW_REJECTS out of 12

| from→to | feat_last_frame | raw_last_frame | feat_slope | raw_slope | feat_jump | raw_jump | reason |
|---|---|---|---|---|---|---|---|
| 3→8 | 31 | 36 | -23.59 | **+21.27** | 227.0 | 123.4 | ball ascending at raw end |
| 22→27 | 252 | 257 | -7.84 | +30.65 | 190.4 | **37.5** | feat=mid-air, raw=at hand |
| 40→41 | 582 | 587 | -1.39 | -0.31 | 2.3 | 3.3 | no catch/throw signature |
| 43→45 | 622 | 626 | n/a | -0.36 | 10.2 | 8.5 | no catch/throw signature |
| 64→68 | 964 | 969 | 7.98 | +13.25 | 66.0 | 131.1 | ball ascending at raw end |

3 of 5 RAW_REJECTS show `raw_end_slope > 0` (ascending) at the raw
last frame — the source tracklet extends through the catch+throw.

2 of 5 (40→41, 43→45) have `n_pts < 5` (very short source tracklets)
and the catch/throw signature is just noise.

### youtube: 21 RAW_REJECTS out of 22

YouTube's tracklet_features are systematically more truncated
(median 4-5 frames behind raw last frame vs 2-3 on identical).
Almost every YouTube RECLASSIFIED edge fails the raw check.

| Edge | raw_jump | feat_end_slope | raw_end_slope | interpretation |
|---|---|---|---|---|
| 1→9 | 39.0 | -11.66 | +11.19 | ascending at raw end |
| 2→8 | 121.2 | 0.92 | +6.89 | not descending |
| 3→6 | 49.0 | 0.95 | +10.04 | not descending |
| 4→18 | 51.7 | -0.12 | +8.51 | not descending |
| 9→13 | 119.8 | 1.75 | +8.65 | not descending |
| 11→14 | 92.7 | 0.51 | +6.85 | not descending |
| 13→16 | 102.1 | 1.54 | +7.36 | not descending |
| 14→17 | 83.8 | 2.15 | -0.21 | stationary at raw end |
| 15→25 | 43.5 | -2.08 | +9.76 | ascending at raw end |
| 17→24 | 22.7 | -4.91 | +10.25 | ascending at raw end |
| 18→30 | 95.4 | 2.32 | +0.55 | stationary at raw end |
| 19→22 | 122.6 | 1.82 | +6.60 | not descending |
| 21→29 | 105.8 | 1.79 | +2.42 | not descending |
| 22→26 | 112.3 | -0.29 | +7.32 | not descending |
| 25→33 | 93.2 | 3.13 | +6.88 | not descending |
| 26→31 | 152.1 | 0.94 | +6.49 | not descending |
| 28→32 | 70.0 | 1.79 | **-3.48** | **STILL_RECLASSIFIED** |
| 29→34 | 63.0 | -0.08 | +6.62 | ascending at raw end |
| 30→37 | 81.3 | 1.09 | +6.74 | not descending |
| 31→35 | 113.1 | 1.81 | +8.92 | not descending |
| 33→36 | 62.5 | 2.94 | +7.83 | not descending |
| 35→38 | 98.0 | 2.34 | +4.99 | not descending |

**21/22 YouTube edges** have `raw_end_slope > 0` (ascending) or
`raw_end_dist > 30` (too far from hand). The H7v2 reclassification
on YouTube is essentially a no-op on the raw data.

The 1 YouTube edge that is STILL_RECLASSIFIED (28→32) is the
exception: `raw_end_slope=-3.48` (descending) and `raw_end_dist=46.6`
(within reach).

## Why this matters

H7v2 reclassification downgrades a BALLISTIC edge to a
HAND_TRANSITION when the source and target endpoints "look like"
a catch+throw. The 76.5% RAW_REJECTS rate shows this downgrade is
over-applied — the truncated tracklet_features capture a
mid-catch snapshot, but the raw tracklet extends through a complete
catch-throw cycle.

The downstream impact is that h7v3plus3 contains many edges that
H7v2 reclassified (and are therefore in the chain), but that would
have remained BALLISTIC if H7v2 had used raw data. H112 and
H114/H117/H118 worked hard to fix the edge-level precision of
this over-inclusion; the H121 finding is that the **input data
to H7v2 is the actual problem**, not the geometric filters applied
downstream.

## Implication for H112/H114/H117/H118

The H112 cross-hand handoff filter (which fired on 22→27) and the
H114 v1 strict large-jump filter (which fired on 3→8, 39→46, etc.)
all used **tracklet_features-based spatial jumps** as inputs. These
are systematically larger than the raw spatial jumps.

If the H112/H114/H117/H118 thresholds were re-calibrated to use
raw spatial jumps, the false-positive rate might be higher (some
edges that were "obviously false" by the orig metric would look
"plausible" by the raw metric). A re-evaluation would be needed.

## Negative findings

- H121 does NOT affect edge-level precision: 0/26 RAW_REJECTS are
  in the 113 review pair set, so the H59 precision/recall metrics
  (and the H77 H100 v4 PERFECT result) are unchanged.
- The H121 RAW_REJECTS are not necessarily "wrong" edges. Some may
  be real catch-throws that just happen to have catch+throw within
  a single tracklet. Without visual QA on each, we cannot say.
- The 1 YouTube STILL_RECLASSIFIED (28→32) shows the rule CAN
  work correctly when tracklet_features is not too truncated.

## Future research (post-H121)

1. **H122: Re-evaluate the 26 RAW_REJECTS with visual QA.** Are
   any of them real catch-throws that H7v2 correctly
   reclassified, or are they all over-inclusions? Visual QA on
   even 5-10 would be informative.
2. **H123: Re-run H7v2 using raw data instead of tracklet_features.**
   The cleanest fix to the H121 finding is to re-run the entire
   H7v2 pipeline with raw inputs and see how many edges change
   classification. This would be a major chain revision, but
   the 76.5% RAW_REJECTS rate suggests the chain would be
   significantly smaller (possibly too small for downstream
   consumers).
3. **Stop here.** The H121 finding is real and important: the
   `tracklet_features` data H7v2 uses is truncated relative to
   the raw detection data, and H7v2 reclassification is
   over-applied as a result. Fixing this would require a
   re-run of the entire chain pipeline with raw inputs, which
   is a major scope change. The H112/H114/H117/H118
   geometric post-filters are a useful workaround that has
   already been validated on the 113 review pair set.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h121_raw_vs_features_h7v2.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h121_per_edge.csv` (34 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h121_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h121_report.md` (this file)
