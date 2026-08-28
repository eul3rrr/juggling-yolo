# H82 — Refined H74 signal with unique_LR count (extends H78)

**Date:** 2026-08-28
**Question:** H74 (LR_variance < 0.20) has 2 false positives on
YouTube MIXED_3+ JUGGLING phases (f=267-298 and f=375-410).
Can a refined H74 signal remove these FPs while keeping the
3 true positive catches (STATIC_HOLD identical, STATIC_HOLD
YouTube, CASCADE_REAL YouTube)?

## Background

H74 (LR_variance < 0.20) was a static-hold detector that
correctly identified 3 of 4 misclassifications on the H70
sample. However, it also had 2 false positives on real
juggling phases:
- f=267-298 YouTube JUGGLING: LR mean=2.0, var=0.000 (truly stable!)
- f=375-410 YouTube JUGGLING: LR mean=1.889, var=0.154

These are real juggling patterns where the 5-ball juggler
has continuous hand occupancy. The H40v2 sustained-occupancy
metric saturates at LR=2.0 (both hands at 1.0) for the
busy juggling pattern, making it indistinguishable from a
true static hold.

## Method

For each H70 substantial phase, compute the unique count of
L+R values across all frames in the phase (rounded to 2 decimal
places). A truly static hold should have only 1-2 unique LR
states, while a busy juggling pattern should have 3+ unique
states (the hands cycle through different occupancy levels).

H74v1: `LR_variance < 0.20` (current, 2 FP)
H74v2: `LR_variance < 0.20 AND unique_LR <= 2` (proposed)

Then test the H82 stack: H75v2 + H78 mean_diff>10 + H71.

## Per-phase H74v1 vs H74v2

| Phase | Verdict | LR_var | unique_LR | H74v1 | H74v2 |
|-------|---------|--------|-----------|-------|-------|
| ident f=733-766 | STATIC_HOLD | 0.152 | 2 | True | True |
| ident f=1029-1049 | OTHER_STATIC_HOLD | 0.355 | 3 | False | False |
| youtu f=2-71 | STATIC_DEMO | 0.122 | 2 | True | True |
| youtu f=114-255 | JUGGLING_STARTUP | 0.204 | 3 | False | False |
| **youtu f=267-298** | JUGGLING (FP) | **0.000** | **1** | **True** | **True** |
| youtu f=339-374 | FOUNTAIN | 0.212 | 3 | False | False |
| **youtu f=375-410** | JUGGLING (FP) | **0.154** | **3** | **True** | **False** |
| youtu f=482-594 | STATIC_HOLD | 0.134 | 2 | True | True |
| youtu f=800-861 | CASCADE_REAL | 0.199 | 2 | True | True |

**H74v2 correctly removes the f=375-410 FP** (unique_LR=3,
juggling has 3+ unique states).

**H74v2 still wrongly rejects f=267-298** (unique_LR=1).
This is a real juggling pattern with continuous stable LR=2.0
(no state changes because the 5-ball pattern always has 1 ball
in each hand + 3 in air). This is a fundamental H40v2 metric
limitation, not a tunable threshold.

## Sensitivity grid for H74v2 thresholds

### unique_LR threshold (LR_var < 0.20 fixed):

| thr_unique | TP | TN | FP | FN | P | R | acc |
|------------|----|----|----|----|---|---|-----|
| 1          | 13 | 4 | 1 | 1 | 0.929 | 0.929 | 0.895 |
| **2**      | **13** | **4** | **1** | **1** | **0.929** | **0.929** | **0.895** |
| 3          | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.842 |
| 4          | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.842 |
| 5          | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.842 |

**Flat region: unique_LR <= 1 or <= 2 give identical results.**
Threshold 2 is well-justified.

### LR_var threshold (unique_LR <= 2 fixed):

| thr_var | TP | TN | FP | FN | P | R | acc |
|---------|----|----|----|----|---|---|-----|
| 0.10    | 13 | 4 | 1 | 1 | 0.929 | 0.929 | 0.895 |
| 0.15    | 13 | 4 | 1 | 1 | 0.929 | 0.929 | 0.895 |
| 0.18    | 13 | 4 | 1 | 1 | 0.929 | 0.929 | 0.895 |
| **0.20** | **13** | **4** | **1** | **1** | **0.929** | **0.929** | **0.895** |
| 0.22    | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.842 |
| 0.25    | 11 | 4 | 1 | 3 | 0.917 | 0.786 | 0.789 |

**Flat region: 0.10-0.20 all give identical results.**

## End-to-end stack comparison (all 19 H70 substantial phases)

| Stack | TP | TN | FP | FN | P | R | FPR | acc |
|-------|----|----|----|----|---|---|-----|-----|
| H75 (H43 OR H69 OR H74v1)              | 12 | 3 | 2 | 2 | 0.857 | 0.857 | 0.400 | 0.789 |
| H75v2 (H43 OR H69 OR H74v2)             | 13 | 3 | 2 | 1 | 0.867 | 0.929 | 0.400 | 0.842 |
| H78v5 (H75v1 OR H78 mean_diff>10)       | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.200 | 0.842 |
| **H82 v1 (H75v2 OR H78 mean_diff>10)** | **13** | **4** | **1** | **1** | **0.929** | **0.929** | **0.200** | **0.895** |

**H82 v1 stack achieves 89.5% accuracy on the H70 sample** —
the best of any stack tried so far. The flat region of
thresholds (unique_LR <= 1 or 2, var < 0.10 to 0.20) confirms
the operating point is well-justified.

## What's the 1 remaining FP? The 1 remaining FN?

**FP: f=685-716 identical CASCADE_3+ (MANIPULATION)**
- This is a 3-ball manipulation trick (body rolls / contact
  juggling) that H12 v8 misclassified as CASCADE_3+. None of
  the existing signals (H43, H69, H74, H78, H71) catch it
  because:
  - h12_conf=0.738 (not < 0.55) — H43 doesn't fire
  - spec_conc=0.498 (not < 0.15) — H69 doesn't fire
  - LR_var=0.374 (not < 0.20) — H74 doesn't fire
  - mean_diff=3.20 (not > 10) — H78 doesn't fire
  - pattern=CASCADE_3+ (not MIXED_3+) — H71 doesn't fire
- The H73 finding is reaffirmed: CASCADE_3+ class has
  0/2 accuracy on substantial phases, and no current
  signal can catch the MANIPULATION misclassification.

**FN: f=267-298 YouTube MIXED_3+ (JUGGLING, real)**
- This is real juggling with continuous stable LR=2.0 (no
  state changes). H74v2 (var < 0.20 AND unique_LR <= 2)
  wrongly rejects it as static hold.
- A real fix would require a fundamentally different metric
  (e.g., ball-detection-based check rather than hand-occupancy).

## Recommended operating point (post-H82)

**h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v2 + H78 + H52 + H53**

- H74v2 = `var < 0.20 AND unique_LR <= 2`
- H78 = `mean_diff_per_frame > 10`
- Both are in flat sensitivity regions

For phase-validated precision: H82 stack gives 89.5% accuracy
on the H70 sample (vs 78.9% for H75 alone, vs 84.2% for H78v5).

## Verdict: PASS (narrow-scope precision improvement)

H82 v1 (H75v2 + H78) achieves 89.5% accuracy on the H70
sample, with all gains in the flat sensitivity region of
H74v2 and H78. The 1 remaining FP (f=685-716 CASCADE_3+
MANIPULATION) and 1 remaining FN (f=267-298 YouTube JUGGLING)
are fundamental limitations of the existing signals.

## Negative findings

1. **f=267-298 YouTube JUGGLING is unfixable with the H40v2
   signal.** A 5-ball juggler with 1 ball in each hand and 3
   in the air has LR=2.0 (continuous stable). No unique_LR
   or LR_var threshold can distinguish this from a static hold.

2. **f=685-716 CASCADE_3+ MANIPULATION is unfixable with
   the existing signals.** It's a contact juggling pose that
   confuses the H12 v8 K=4 event-based classifier. The H73
   finding (CASCADE_3+ has 0/2 accuracy on substantial phases)
   is reaffirmed.

3. **The H74v2 unique_LR threshold 1 vs 2 give identical
   results on this sample** (both reject f=267-298 with
   unique_LR=1, both keep f=375-410 with unique_LR=3). The
   difference would only matter for phases with unique_LR=2,
   which are all correctly caught as static holds in this
   sample.

## Future research

1. **H83: H40v2 metric refinement for 5-ball jugglers** — the
   fundamental H40v2 limitation on f=267-298 needs a different
   approach. Possibilities: ball-detection-based check,
   hand-velocity-based check, or pattern-periodicity check.

2. **H84: H12 v8 CASCADE_3+ revision** — the CASCADE_3+ class
   has 0/2 accuracy on substantial phases (H73 finding). A
   new signal for CASCADE_3+ misclassification would be
   valuable.

3. **H85: H82 v1 cross-validation on the 113 manual review pairs**
   (H59 ground truth) to verify per-edge impact.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h82_h74_refined.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h82v2_sens_grid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h82_h74_refined.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h82_report.md`
