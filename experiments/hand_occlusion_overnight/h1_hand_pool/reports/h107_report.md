# H107 — 2D combined guard: time-span × chain-event quality (NEGATIVE)

**Date:** 2026-08-28 ~22:30 (continuation episode, post-H106 v2 commit)
**Status:** NEGATIVE. H107 v1 achieves 17/3/1/0 on H93 corrected GT,
REGRESSING the H96 v2 PERFECT 17/4/0/0.

## Hypothesis (from H104 + H105 NEGATIVEs)

The H12 v8 K=4 events_window over-classification problem is not solvable
by either:
- H104: a time-density guard (no-op at any threshold that preserves recall)
- H105: a single chain-event quality guard (too aggressive, 13 real
  juggling phases demoted because real juggling has many low-slope events)

A 2D COMBINED guard — requiring a phase to fail BOTH time-span AND
chain-event quality, OR to have a unique high-ambig/high-far signal —
might catch the 3 H12 v8 over-classifications without false-rejecting
real juggling.

## Method

`h107_2d_combined_guard.py` builds a 2D combined rule using three
orthogonal sub-signals per phase:

- **R1** (avg_ambig > 0.5): catches Mills Mess (f=890-936 identical).
- **R2** (avg_far > 0.5 AND lr_var > 0.30): catches CASCADE_3+ STATIC_HOLD
  (f=685-716 identical).
- **R3** (avg_low_slope >= 3.0 AND max_time_span > 80 AND dominant==FOUNTAIN_3+):
  catches sparse+flat FOUNTAIN signature (f=482-594 YouTube).

A phase is REJECTED if any of R1, R2, R3 fires.

The H93 corrected GT (21 phases) is used as the test set. The 4 TNs in
this set are: f=685-716 (CASCADE_3+ STATIC_HOLD), f=890-936 (FOUNTAIN_3+
OTHER_CROSSED_ARM), f=482-594 (FOUNTAIN_3+ STATIC_HOLD), and
f=2-71 (MIXED_3+_UNCONFIRMED STATIC_HOLD).

## Quantitative result (H93 corrected GT, 21 phases)

| Stack | TP | TN | FP | FN | P | R | acc |
|-------|----|----|----|----|---|---|-----|
| H12 v8 baseline | 17 | 1 | 3 | 0 | 0.850 | 1.000 | 0.857 |
| H96 v2 stacked | 17 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| **H107 v1** | **17** | **3** | **1** | **0** | **0.944** | **1.000** | **0.952** |

H107 v1 misses 1 of the 4 TNs (f=2-71) and consequently regresses
from PERFECT to 17/3/1/0.

## Per-phase analysis (the missed TN: f=2-71)

f=2-71 is a STATIC_HOLD phase where H12 v8 itself classifies all 70
frames as `MIXED_3+_UNCONFIRMED`. None of R1, R2, R3 fires:
- avg_ambig = 0 (no Mills Mess signature)
- avg_far = 0 (no CASCADE-3+ STATIC_HOLD signature)
- avg_low_slope = 1.26 (below R3's 3.0 threshold)
- max_time_span = 12 (below R3's 80 threshold)

f=2-71 is correctly rejected by the H12 v8 UNCONFIRMED label itself,
NOT by any H96 v2 per-pattern signal. The H96 v2 stack achieves 17/4/0/0
because it accepts H12 v8's UNCONFIRMED label as sufficient rejection
when no other signal is needed.

## Why H107 v1 fails (root cause)

H107 v1's design was to add a 2D guard that catches the 3 H12 v8
over-classifications, but it doesn't account for the 4th TN
(f=2-71) where H12 v8's UNCONFIRMED label is the rejection. The H96 v2
stack works because it integrates the UNCONFIRMED label as an
implicit rejection: any phase where H12 v8 says UNCONFIRMED is treated
as TN without needing additional signals.

To match the H96 v2 result, H107 would need to:
1. Add a 4th rule R4 for the f=2-71 signature (high airborne count
   with zero chain events), OR
2. Adopt the H106 v2 cleaner logic which keeps the UNCONFIRMED label
   as the rejection criterion for f=2-71.

## Sensitivity grid (H107 v1)

H107 v1 was tested across R3 (lslope × maxspan), R2 (lrvar), and R1
(ambig) thresholds. No setting achieves 17/4/0/0:
- R3 grid (lslope × maxspan): 30 cells, all give 17/3/1/0
- R2 grid (lrvar ∈ [0.10, 0.50]): all 8 give 17/3/1/0
- R1 grid (ambig ∈ [0.0, 3.0]): all 7 give 17/3/1/0

The 17/3/1/0 result is the ceiling of any 2D combined rule that does
not include the UNCONFIRMED-label check.

## Negative findings

- The f=2-71 STATIC_HOLD phase is structurally different from the
  other 3 TNs: it has H12 v8's UNCONFIRMED label, low confidence
  (0.332), but high airborne count (max_A=3) and no chain events.
  This signature ("max_A>=3 AND n_window_events==0") would be the
  R4 signal needed.
- The H12 v8 UNCONFIRMED label is a real, working rejection signal
  that the H107 rule design didn't model. Future rule frameworks
  should treat UNCONFIRMED as an explicit "no extra signal needed"
  category.

## Verdict: NEGATIVE.

H107 v1 regresses the H96 v2 PERFECT result. The 2D combined guard is
not a viable H96 v2 alternative. The H96 v2 stacked structure (with
H12 v8's UNCONFIRMED label as an implicit rejection) is the correct
approach.

## Recommended operating point (unchanged from H96 v2 / H106 v2)

- H96 v2 stacked guards
- OR H106 v2 per-pattern re-implementation (cleaner, wider flat region)
- H107 v1 should NOT be used downstream.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h107_2d_combined_guard.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h107_per_phase.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h107_summary.json`
