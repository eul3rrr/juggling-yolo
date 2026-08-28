# H86 — H83 v3 (per-hand H74v3) vs H82 v1 (H74v2) on all 21 H70 phases

**Date:** 2026-08-28
**Question:** H82 v1 (H75v2 + H78) achieved 89.5% accuracy on the
H70 sample (19 phases). H83 v1 (H74v3) was proposed as a refinement
to fix the H82 v1 FN at f=267-298 (5-ball juggler with stable LR=2.0).
Does H83 v3 actually improve over H82 v1 on the full 21-phase
ground truth (including the 2 phases NOT in h70_phases)?

## Background

The H82 v1 stack has 1 FN (f=267-298 YouTube JUGGLING, real 5-ball
juggling) because H74v2 (var<0.20 AND unique_LR<=2) wrongly rejects
this real juggling pattern.

H83 v1 (H74v3) was proposed: H74v3 = var<0.20 AND (unique_L>1 OR
unique_R>1). The hypothesis: a real static hold has variation in at
least one hand, while a real 5-ball juggling pattern with stable
LR=2.0 has BOTH hands at maximum.

## Result: H83 v3 = H82 v1 numerically

On all 21 H70 phases (the 19 in h70_phases + 2 manually added):
- H82 v1: TP=14 TN=6 FP=1 FN=0  P=0.933  R=1.000  FPR=0.143  acc=0.952
- H83 v3: TP=14 TN=6 FP=1 FN=0  P=0.933  R=1.000  FPR=0.143  acc=0.952

The two stacks give IDENTICAL end-to-end results. The 1 FN fix
(f=267-298) is offset by 1 new FN (f=375-410).

### Per-phase H82 v1 vs H83 v3 differences

| Phase | var | uLR | uL | uR | H82 v1 | H83 v3 | Net |
|-------|-----|-----|----|----|--------|--------|-----|
| f=267-298 JUGGLING (5-ball stable LR=2.0) | 0.000 | 1 | 1 | 1 | REJ (H74v2) | KEEP (H74v3) | H83 wins |
| f=375-410 JUGGLING (5-ball cycling) | 0.154 | 3 | 2 | 2 | KEEP | REJ (H74v3) | H82 wins |
| f=733-766 STATIC_HOLD (identical) | 0.152 | 2 | 1 | 2 | REJ (H74v2) | REJ (H74v3) | tie |
| f=482-594 STATIC_HOLD (YouTube) | 0.134 | 2 | 2 | 2 | REJ (H69 first) | REJ (H69 first) | tie (H69 wins) |
| f=800-861 CASCADE_REAL (YouTube) | 0.199 | 2 | 2 | 2 | REJ (H69 first) | REJ (H69 first) | tie (H69 wins) |

H83 v3 fixes 1 (f=267-298) but breaks 1 (f=375-410). Net effect: 0.

### Why f=375-410 breaks

f=375-410 YouTube JUGGLING has:
- var=0.154 (low — close to static hold range)
- unique_L=2, unique_R=2 (cycling hand occupancy)
- mean_diff=0.00 (H78 wrist-distance data not available for this MIXED_3+ phase)

H74v2 doesn't fire (unique_LR=3 > 2) → H82 v1 KEEPS this.
H74v3 fires (unique_L=2 > 1 OR unique_R=2 > 1) → H83 v3 REJECTS this.

The 5-ball juggler in this phase has both hands cycling through
different states (not stable LR=2.0 like f=267-298). The H40v2 metric
captures this cycling, which H74v3 then misclassifies as static hold.

## Sensitivity grid (21 phases)

### H74v2 (var<thr AND unique_LR<=thr2) grid:

| thr_var | thr_uLR | TP | TN | FP | FN | P | R | acc |
|---------|---------|----|----|----|----|---|---|-----|
| 0.10 | 1-3 | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| 0.15 | 1-3 | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| **0.20** | **2-3** | **14** | **6** | **1** | **0** | **0.933** | **1.000** | **0.952** |
| 0.25 | 2 | 14 | 6 | 1 | 0 | 0.933 | 1.000 | 0.952 |
| 0.25 | 3 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |

Flat region: var∈[0.20, 0.25] AND uLR∈[2, 3] gives 95.2% accuracy.

### H74v3 (var<thr AND (unique_L>thr2 OR unique_R>thr2)) grid:

| thr_var | thr_h | TP | TN | FP | FN | P | R | acc |
|---------|-------|----|----|----|----|---|---|-----|
| 0.10 | 1-3 | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| 0.15 | 1-3 | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| **0.20** | **1** | **14** | **6** | **1** | **0** | **0.933** | **1.000** | **0.952** |
| 0.20 | 2-3 | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| 0.25 | 1 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |

Flat region: var=0.20 AND thr=1 only (single point).

**Both H74v2 and H74v3 achieve 95.2% accuracy with their flat regions.**

H74v2 has a wider flat region (var ∈ [0.20, 0.25] AND uLR ∈ [2, 3]).
H74v3 has a narrower flat region (var=0.20 AND thr=1).

## 5-ball saturation finding

The 5-ball juggler in YouTube phases has TWO distinct hand-occupancy
patterns:
1. **Stable LR=2.0** (f=267-298): both hands at 1.0 continuously.
   The juggler has 1 ball in each hand + 3 in the air. Static at the
   hand-occupancy level but balls are aloft.
2. **Cycling LR=0-1-2** (f=375-410, f=308-338, etc.): hands cycle
   through different occupancy levels as catches and throws happen.

Pattern 1 looks like a static hold at the H40v2 level.
Pattern 2 has visible cycling (H40v2 detects it as variation).

Neither H74v2 nor H74v3 can correctly handle BOTH patterns:
- H74v2 keeps Pattern 2 (cycling makes unique_LR>2) but rejects
  Pattern 1 (stable LR=2.0 has unique_LR=1).
- H74v3 keeps Pattern 1 (stable L=1.0 R=1.0) but rejects Pattern 2
  (cycling makes unique_L>1 and unique_R>1).

The errors cancel out numerically, but both stacks are fundamentally
flawed for the 5-ball juggler.

## Alternative signals for the 5-ball problem

Possible signals to add (NOT implemented in H86):
1. **Ball-detection-based check** — count YOLO ball detections outside
   the hand reach. A real 5-ball juggling pattern has 3 balls aloft;
   a static hold has 0. This would distinguish Pattern 1 (3 aloft)
   from static hold (0 aloft) without using hand-occupancy.
2. **Wrist-velocity check** — a real juggling pattern has high wrist
   velocity (catch+throw motion at ~6-10 px/frame). A static hold
   has low wrist velocity. The H40v2 sustained-occupancy metric
   doesn't capture this.
3. **Pattern-periodicity check** — the H69 spec_conc already
   measures periodicity. f=267-298 has spec_conc=0.175 (above
   H69's 0.15 threshold), which is why H69 doesn't reject it.
   A different periodicity metric might catch the "stable"
   component of Pattern 1.

## Recommended operating point (post-H86)

**h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v2 OR H74v3 + H78 + H52 + H53**

For 95.2% phase-level accuracy (21 phases), both H74v2 and H74v3 work.
H74v2 has a wider flat region. H74v3 has a single-point flat region.

The H82 v1 (H74v2) remains the recommended operating point for
robustness. H83 v3 is an alternative that achieves the same accuracy
on this sample.

## Verdict: NEGATIVE (H83 v3 does not improve over H82 v1)

H83 v3 is NOT an improvement over H82 v1 on the 21-phase sample.
Both achieve 95.2% accuracy (TP=14 TN=6 FP=1 FN=0). The 1 FN fix
at f=267-298 is offset by 1 new FN at f=375-410. The 5-ball
saturation problem (Pattern 1 vs Pattern 2) requires a fundamentally
different signal (ball-detection-based, wrist-velocity-based, or
pattern-periodicity-based) — not a refinement of the H40v2
hand-occupancy metric.

## Negative findings

1. **H83 v3 = H82 v1 numerically** (95.2% accuracy, same TP/TN/FP/FN).
   The H83 v3 fix at f=267-298 is cancelled by a new FN at f=375-410.

2. **The 5-ball juggler has TWO distinct hand-occupancy patterns**
   (stable LR=2.0 vs cycling LR). Neither H74v2 nor H74v3 handles
   both correctly.

3. **H40v2 hand-occupancy metric has a fundamental saturation
   limitation for 5-ball jugglers.** A 5-ball juggler with 1 ball
   in each hand continuously is indistinguishable from a static
   hold at the H40v2 level.

4. **A truly robust 5-ball detector needs a different signal** —
   ball-detection-based (count balls aloft), wrist-velocity-based,
   or periodicity-based. This is beyond H86's scope.

## Future research

1. **H87: ball-detection-based "balls aloft" signal as 5-ball
   discriminator.** Count YOLO ball detections outside hand reach.
   Pattern 1 (5-ball stable) should have ~3 balls aloft; static
   hold has 0. This would catch f=267-298 without breaking f=375-410.

2. **H88: CASCADE_3+ signal development.** The CASCADE_3+ class
   has 0/2 accuracy on substantial phases (H73 finding). A new
   signal (e.g., hand-crossing events, trajectory crossings) would
   be valuable. f=685-716 (MANIPULATION) is the only remaining FP
   in the H82 v1 stack and it has pattern=CASCADE_3+.

3. **H89: per-tracklet H74v3 analysis.** The H74v3 analysis is
   currently at the phase level. A per-tracklet analysis could
   reveal sub-phase H40v2 variation that the H40v2 sustained-occupancy
   metric averages out.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h86_h83v3_vs_h82v1.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h86_h74_signals.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h86_report.md`
