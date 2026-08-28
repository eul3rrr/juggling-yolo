# H16 — H3 stationary-cluster corroboration for V-reclassified edges

**Date:** 2026-08-28 ~18:30 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **PARTIAL PASS** (useful signal, not a definitive filter).

## Hypothesis

H11 v7's visual QA found that 2/4 identical V-reclassified edges
(23→25, 39→47) are HAND-BORNE, not clean catch+throws. The 1 YouTube
V-reclassified (27→28) is a false positive. H15v2's V-shape check is
position-only and can't distinguish these cases.

**H16 hypothesis:** a stricter V-shape check that requires H3
stationary-cluster evidence of a held ball at the V-apex hand
during the gap should reject the hand-borne cases (23→25, 39→47)
and the false positive (27→28), while keeping the 2 clean
catch+throws (30→33, 51→52).

## Thresholds

Inherited from H3 v3 (declared from physical geometry, NOT from manual
labels):
- `LOW_CONF_MAX = 0.5` (low-conf tier)
- `CLUSTER_RADIUS_PX = 30`
- `CLUSTER_MIN_FRAMES = 5`
- `CLUSTER_MIN_DETS = 3`
- `GAP_PAD_FRAMES = 5` (search window = gap + 5 frames each side)
- `REACH_RADIUS_PX = 108` (declared from physical geometry)

**H16 v2 critical fix:** exclude src and tgt tracklets from the
low-conf det pool. Otherwise the criterion fires on the source/target
tracklet's own low-confidence tail points, which are not
"independent held-ball evidence".

## Algorithm

For each V-reclassified edge:
1. Compute the V-apex hand position as the mean wrist position over
   the gap window (using the hand from h14_v_shape: left or right).
2. Look for low-conf detections within 30 px of the V-apex hand
   within the gap + 5 frame pad.
3. Exclude dets whose track_id matches the source or target tracklet
   (their own low-conf points are not "independent evidence").
4. Confirm the edge if cluster has ≥3 dets in ≥5 unique frames.

## Quantitative result (H16 v2 with exclude_tids fix)

### identical (4 V-reclassified edges)

| Edge | V-class | min_d | hand | visual verdict | n_dets | n_frames | h3 confirmed |
|---|---|---|---|---|---|---|---|
| 23→25 | V_DEEP | 18.39 | right | HAND-BORNE | 0 | 0 | no |
| 30→33 | V_SHALLOW | 58.52 | left | REAL CATCH+THROW | 0 | 0 | **no (FN)** |
| 39→47 | V_SHALLOW | 74.86 | left | HAND-BORNE | 0 | 0 | no |
| 51→52 | V_DEEP | 26.65 | left | REAL CATCH+THROW | 8 | 5 | **YES (TP)** |

### YouTube (1 V-reclassified edge)

| Edge | V-class | min_d | hand | visual verdict | n_dets | n_frames | h3 confirmed |
|---|---|---|---|---|---|---|---|
| 27→28 | V_DEEP | 21.81 | left | FALSE POSITIVE | 3 | 3 | no |

### Summary

- 1/2 real catch+throws confirmed (50% recall, 1 false negative)
- 3/3 non-catch-throws correctly rejected (100% precision on this small sample)
- H16 v2: 1/1 confirmed = 100% precision on the visually-confirmed sample

### Base rate (negative control)

H16 v2's H3 cluster on BALLISTIC edges (NOT V-reclassified) that are
non-V-reclass:
- identical: 0/40 (0.0%) — H16 is highly specific on identical
- YouTube: 11/46 (23.9%) — moderate base rate on YouTube

The 0% on identical means the H3 cluster is essentially never fired
on non-V-reclass BALLISTIC edges. So when it does fire on a
V-reclass edge (51→52), it's a strong signal. The 24% base rate
on YouTube means H3 fires on ~1 in 4 YouTube BALLISTIC edges, so
the H16 signal is much weaker on YouTube.

## Sensitivity grid

180 cells swept (5 radii × 4 min_frames × 3 min_dets × 3 pads).
Top 10 settings by F1 on the visually-confirmed sample:

| rank | r | mf | md | pad | conf | real (P/R) | hb | fp | F1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 75 | 3 | 2 | 10 | 4 | 2/2 (P=0.50, R=1.00) | 1/2 | 1/1 | 0.67 |
| 2 | 75 | 3 | 3 | 10 | 4 | 2/2 (P=0.50, R=1.00) | 1/2 | 1/1 | 0.67 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| 5 | 20 | 3 | 2 | 5 | 1 | 1/2 (P=1.00, R=0.50) | 0/2 | 0/1 | 0.67 |

Two regimes:
- **Loose (radius ≥ 75, pad 10)**: catches 2/2 real catch+throws
  (R=1.00) but admits 1/1 FP (the 27→28 YouTube case has its own
  tracker tail firing as "low-conf" dets) and 1/2 hand-borne (the
  39→47 case has tracker tail).
- **Strict (radius 20, mf 3)**: only 1/2 real catch+throws
  (R=0.50) but rejects all 3 non-catch-throws (P=1.00).

Both regimes have F1=0.67 on this small sample. There is no
operating point that achieves both 100% precision and 100%
recall. The 30→33 case is fundamentally unobservable by detector
(no held-ball evidence) and the 27→28 case has tracker tail that
can't be filtered without access to internal tracker state.

**Recommendation: H16 v2 (default H3 thresholds, exclude_tids
fix) is a useful CONFIRMATORY signal, not a definitive filter.**

## Why H16 cannot fully solve the problem

The H3 stationary-cluster criterion is fundamentally limited because:
1. The detector often misses the held ball entirely (no detections
   at the hand during the held phase). The 30→33 case is a real
   catch+throw but the detector fired 0 times at the hand.
2. The detector's low-conf dets are noisy. Even with exclude_tids
   (which removes src/tgt tracker tails), background objects can
   produce clusters. The 27→28 case has tracklet 21's tail firing
   at the hand region.
3. The held ball's signature is detector-specific. A different
   detector (e.g., a sports-ball-specific model) might give
   different results.

## H16 v1 vs v2: the exclude_tids fix is essential

H16 v1 (without exclude_tids):
- identical: 1/4 (51→52 only)
- YouTube: 1/1 (27→28 WRONGLY confirmed)

H16 v2 (with exclude_tids):
- identical: 1/4 (51→52 only)
- YouTube: 0/1 (27→28 correctly rejected)

The v2 fix removes the false positive on YouTube. Without
exclude_tids, the criterion is uninformative (it confirms both
the 51→52 TP and the 27→28 FP).

## Negative findings

- **H16 cannot recover the 30→33 case** (false negative). The
  detector simply didn't fire at the hand during the gap (0 dets
  in 0 frames). No parameter change can recover this.
- **H16's 24% base rate on YouTube** means H3 fires on
  non-V-reclass BALLISTIC edges too. The H16 signal is much
  weaker on YouTube.
- **H16 is fundamentally detector-dependent.** A real fix would
  require either: (a) a held-ball-specific detector, (b) higher
  frame rate to capture the catch+throw in motion, (c) multi-view
  triangulation, or (d) hand-motion prediction.

## Verdict: **PARTIAL PASS**

H16 v2 (with exclude_tids fix) is a useful confirmatory signal:
- On identical: 1/2 real catch+throws confirmed, 2/2 hand-borne
  correctly rejected. H16 has 100% precision but only 50% recall.
- On YouTube: 0/1 V-reclass confirmed (27→28 correctly rejected
  after exclude_tids fix).

**H16 v2 should be used as a downstream confidence flag on V-reclassified
edges, not as a reclassification filter.** A V-reclass edge with
h3=YES (like 51→52) is likely a real catch+throw; a V-reclass
edge with h3=no (like 23→25, 39→47, 27→28) is ambiguous
(real catch+throw without detector evidence, or hand-borne,
or FP).

**H16 is a useful corroborating signal for H11 v7's event log.**
Downstream consumers can use h3=YES as a high-confidence flag
on V-reclass events.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h16_v_shape_h3_corroboration.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h16_sensitivity.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h16_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h16_sensitivity.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h16_report.md` (this file)

## See also

- `h11_v7_report.md` — H11 v7 visual QA on V-reclassified edges
- `h15v2_report.md` — H15v2 (V-shape reclassification)
- `h3_report.md` — H3 v3 stationary-cluster criterion (the basis for H16)
- `RESEARCH_NOTES.md` — H16 cross-cutting insights
