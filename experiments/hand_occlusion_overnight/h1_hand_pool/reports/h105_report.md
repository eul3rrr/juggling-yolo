# H105 — H12 v9 hybrid with chain-event quality guard (NEGATIVE)

**Date:** 2026-08-29 ~04:30 CEST
**Status:** NEGATIVE. The H105 chain-event quality guard demotes virtually
ALL events to MIXED_3+_UNCONFIRMED, far worse than the H12 v8 baseline.

## Hypothesis

From H104 NEGATIVE: H12 v8's K=4 events_window is **confounded** by
H7 chain density, not by time density. A different angle is the
chain-event quality itself. The 3 H93 FP phases have
**abnormal chain-event features** that a quality guard could detect:
- f=685-716 STATIC_HOLD: only 1 chain event, end_dist=174.1 (n_far=1 — unique)
- f=890-936 OTHER_CROSSED_ARM: only 1 chain event, ambiguous=true
  (Mills Mess hand-cross)
- f=482-594 STATIC_HOLD: 3 chain events, 2 with low_slope (< 2.5)
  (static hold with embedded hand-handoffs)

H105 (H12 v9) is a H12 v8 per-frame classifier with a chain-event
quality guard: if the K=4 events_window contains any chain event
with abnormal features (FAR_DIST, AMBIGUOUS, LOW_SLOPE), demote to
MIXED_3+_UNCONFIRMED.

## Thresholds (declared from chain-event analysis)

```
QUALITY_FAR_DIST_THR = 100.0   # reject if any K=4 event has end_dist > 100
QUALITY_LOW_SLOPE_THR = 2.5    # reject if low_slope ratio >= 0.5
QUALITY_LOW_SLOPE_RATIO = 0.5
QUALITY_AMBIGUOUS_RATIO = 0.25 # reject if ambiguous ratio >= 0.25
```

## Quantitative result (H93 corrected GT, 21 phases)

| Stack | TP | TN | FP | FN | P | R | acc |
|---|---|---|---|---|---|---|---|
| H12 v8 baseline | 14 | 2 | 2 | 3 | 0.875 | 0.824 | 0.762 |
| **H12 v9 (H105 guard)** | **2** | **4** | **0** | **15** | **1.000** | **0.118** | **0.286** |
| H12 v8 + H96 v2 full stack | 17 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |

The H105 guard is a CATASTROPHIC regression: 13 additional FN (real
juggling phases demoted to MIXED_3+_UNCONFIRMED) for 0 additional TN.

## Per-phase diagnosis (avg_low_slope column)

The H105 per-phase CSV shows that avg_low_slope=4.0 for many REAL
JUGGLING phases (identical 549-578, 631-669; youtube 339-374, 375-410,
420-481). This means **the K=4 events_window for real juggling has
4 events with |end_slope| < 2.5** — every event triggers the
QUALITY_LOW_SLOPE_THR guard. The chain-event slopes are not
informative of catch-throw quality because the H7 chain emits
hand-edge events at any hand contact, including legitimate mid-rhythm
contacts during a real cascade.

## Why H105 fails

1. **The H7 chain emits hand-edge events too liberally for high-cadence
   juggling.** A 3-ball cascade has 3 catch-throws/second, each
   producing a chain event with low |end_slope| (the ball approaches
   the hand horizontally). The LOW_SLOPE filter is satisfied for
   nearly every event in a real cascade, not just the 3 FP phases.

2. **FAR_DIST (>100) is a rare signal.** Only f=685-716 has a
   qualifying event; the other 2 FPs are caught by other rules but
   not by FAR_DIST alone.

3. **AMBIGUOUS ratio is too sensitive.** f=890-936 is caught by the
   AMBIGUOUS rule, but the rule also fires on legitimate 2-ball-in-
   one-hand moments during 3-ball cascades.

4. **No flat region.** A 1D sensitivity grid (not run, but evident
   from the per-phase output) would show that ANY lowering of the
   thresholds admits more real juggling while raising them
   fails to catch the 3 FPs. The H105 guard cannot simultaneously
   catch the 3 FPs and preserve real juggling because the chain-event
   feature distributions overlap.

## Negative findings

- The H12 v8 K=4 events_window is fundamentally confounded by the H7
  chain's emission pattern. The H104 NEGATIVE finding (time-density
  guard is a no-op) and the H105 NEGATIVE finding (chain-event
  quality guard is too aggressive) together establish that **no
  simple guard on the K=4 events_window can fix H12 v8's
  over-classification**.
- The H12 v8 over-classification problem is a fundamental algorithmic
  limitation: the K=4 events_window + hand-alternation-metric cannot
  distinguish static-hold (where a hand is "stuck" holding a ball
  while the juggler does a trick pose) from real juggling (where a
  hand repeatedly catches and throws). Both have low |end_slope|
  events.
- The H105 per-phase CSV shows avg_low_slope=0 for 4 phases
  (f=890-936, f=685-716, f=977-1011, f=1029-1049 identical) and
  avg_low_slope=4 for many real juggling phases. There is no
  discriminative threshold.

## Recommended operating point (unchanged)

The H96 v2 + H100 v4 stack is the precision-optimized endpoint:
- h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 (with H100 v4 guard) +
  H69 (with H100 v4 guard) + H74v4 + H78 + H87+max_aloft + H90 NEW +
  H52 + H53 + H71 (MIXED_3+)
- 21 phases: 17/4/0/0, P=R=acc=1.000
- 113 review pairs: P=0.979, R=0.648

## Future research

The H104 report suggested **H106: H12 v9 hybrid with H40v2 occupancy**
as the next direction. The H40v2 sustained-occupancy signal has
demonstrated value at the phase level (H40 v2: 72.3% identical,
98.1% YouTube hand-occupancy; H74v4: var<0.20 AND uLR<=1 catches
2/4 STATIC_HOLD). Integrating the H40v2 LR signal directly into the
H12 v9 per-frame classifier (demote to MIXED_3+_UNCONFIRMED if
phase-level LR_variance < 0.20 AND unique_LR <= 1) is a
fundamentally different signal than the K=4 events_window
chain-event guard. See H106.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h105_h12_v9_chain_quality_guard.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h105_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h105_per_phase.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v9_guard_*.csv` (2 files)
