# H78 — Wrist-distance signal as FOUNTAIN_3+ / CASCADE_3+ discriminator

**Date:** 2026-08-28
**Question:** Can the per-frame Euclidean distance between the two
wrists (a direct signal for arm-crossing behavior) discriminate
real FOUNTAIN_3+ phases from H12 v8 misclassifications like
f=890-936 (crossed-arm / Mills Mess trick)?

## Background

H65 / H73 found that the H12 v8 FOUNTAIN_3+ classifier is only
~43% accurate on the H70 substantial phase sample. f=890-936
identical is consistently misclassified as FOUNTAIN_3+ but is
actually a **Mills Mess / crossed-arm juggling trick** where the
hands periodically cross the body midline.

The hypothesis: the wrist-distance time series should be able to
detect this kind of trick. A Mills Mess trick has very large
variations in wrist distance as the hands come together and
separate. A real FOUNTAIN has the hands held roughly parallel and
the wrist distance should be more stable.

## Method

For each of the 11 H70 substantial FOUNTAIN_3+ / CASCADE_3+ /
MIXED_3+ phases with sufficient pose data, compute the per-frame
wrist distance `|wrist_L - wrist_R|`. Aggregate to:

- mean, median, min, max, std, range
- mean_diff_per_frame: mean of |Δ wrist_dist| between consecutive frames
- ac_peak_value, ac_peak_lag: autocorrelation peak over lags 1..20
- pct_lt80, pct_lt100, pct_gt200, pct_gt250: fraction of frames at
  extreme wrist distances

Then test these as filters on the FOUNTAIN_3+ / CASCADE_3+ phases
against the H65 + H72 + H73 visual QA ground truth.

## Per-phase results (FOUNTAIN_3+ only)

| Phase | Verdict | mean | std | range | mean_diff | pct_gt200 | pct_lt80 |
|-------|---------|------|-----|-------|-----------|-----------|----------|
| ident f=631-669  | FOUNTAIN  |  86.46 | 49.94 | 150.88 | **7.76** |  0.000 | 0.462 |
| ident f=890-936  | OTHER_CROSSED_ARM | 163.23 | **65.72** | **236.15** | **14.25** | 0.362 | 0.085 |
| ident f=977-1011 | FOUNTAIN  | **215.73** | 17.19 |  61.83 |  **4.33** | **0.829** | 0.000 |
| youtu f=339-374  | FOUNTAIN  |  95.70 |  9.39 |  40.26 |  5.56 | 0.000 | 0.056 |
| youtu f=482-594  | STATIC_HOLD |  95.41 | 12.29 |  67.25 |  5.08 | 0.000 | 0.106 |
| youtu f=800-861  | CASCADE_REAL |  97.19 | 10.62 |  45.16 |  4.89 | 0.000 | 0.081 |

**Key finding:** `mean_diff_per_frame` discriminates the
Mills-Mess trick (f=890-936, mean_diff=14.25) from real FOUNTAIN
phases (mean_diff 4.33-7.76). The threshold **mean_diff > 10**
catches f=890-936 without losing any real FOUNTAIN.

## Sensitivity grid (H78 mean_diff threshold on FOUNTAIN_3+ only)

| thr | TP | TN | FP | FN | P | R |
|-----|----|----|----|----|---|---|
|  5.0 |  1 |  2 |  1 |  2 | 0.500 | 0.333 |
|  6.0 |  2 |  1 |  2 |  1 | 0.500 | 0.667 |
|  7.0 |  2 |  1 |  2 |  1 | 0.500 | 0.667 |
|  8.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
|  9.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 10.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 11.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 12.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 13.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 14.0 |  3 |  1 |  2 |  0 | 0.600 | 1.000 |
| 15.0 |  3 |  0 |  3 |  0 | 0.500 | 1.000 |
| 20.0 |  3 |  0 |  3 |  0 | 0.500 | 1.000 |

**Flat region: 8-14 all give identical results (TP=3, TN=1, FP=2, FN=0).**
Threshold 10 is well-justified (in the middle of the flat region).

## End-to-end stack comparison (all 19 H70 substantial phases)

| Stack | TP | TN | FP | FN | P | R | FPR | Accuracy |
|-------|----|----|----|----|---|---|-----|----------|
| H75 (H43 OR H69 OR H74)              | 12 | 3 | 2 | 2 | 0.857 | 0.857 | 0.400 | 0.789 |
| **H78v5 (H75 OR H78 mean_diff>10)**  | **12** | **4** | **1** | **2** | **0.923** | **0.857** | **0.200** | **0.842** |
| H78v5b (H75 OR (mean_diff>10 AND std>50)) | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.200 | 0.842 |
| Full (H75 OR H78v5 OR H71)           | 12 | 4 | 1 | 2 | 0.923 | 0.857 | 0.200 | 0.842 |

**H78v5 catches 1 additional misclassification** (f=890-936
Mills Mess) without losing any real juggling phases. End-to-end
accuracy improves from 78.9% (H75) to 84.2% (H78v5).

## Per-phase FOUNTAIN/CASCADE behavior under H78v5

| Phase | Verdict | H75_keep | H78v5_keep | H78 triggered? |
|-------|---------|----------|------------|----------------|
| ident f=631-669  | FOUNTAIN (H65), but vision now sees crossed-arm columns | True  | True  | False |
| ident f=685-716  | MANIPULATION | True  | True  | False |
| ident f=890-936  | OTHER (Mills Mess, vision confirmed) | True  | **False** | **True** |
| ident f=977-1011 | FOUNTAIN (H65), vision now sees wide cascade | True  | True  | False |
| youtu f=339-374  | FOUNTAIN (5-ball) | True  | True  | False |
| youtu f=482-594  | STATIC_HOLD | False | False | False |
| youtu f=800-861  | CASCADE (real CASCADE mislabeled) | False | False | False |

H78 only triggers on f=890-936 (Mills Mess trick). It does NOT
incorrectly trigger on f=631-669 (which has lower-amplitude
crossings, mean_diff 7.76 < 10) or on f=977-1011 (which has
steady wide stance, mean_diff 4.33 < 10).

## Visual QA via vision_analyze

Three contact sheets were rendered at `contact_sheets_h78/`:

1. **phase_identical_balls_trick_000_018_f890-936_OTHER_CROSSED_ARM.png**:
   Vision tool confirms Mills Mess pattern. Wrist distance
   oscillates 22.3 → 244.0 → 115.4 in 27 frames. Hands physically
   cross the body midline at f=917. The dramatic V-shape is
   diagnostic of crossed-arm juggling.

2. **phase_identical_balls_trick_000_018_f631-669_FOUNTAIN_REAL.png**:
   Vision tool labels this as a "crossed-arm columns variation"
   (not a true FOUNTAIN per the strict juggling definition). Wrist
   distance oscillates 8.3 → 158.9 in 38 frames. The crossings
   are present but lower-amplitude than f=890-936.

3. **phase_identical_balls_trick_000_018_f977-1011_FOUNTAIN_REAL_WIDE.png**:
   Vision tool labels this as "3-ball cascade" (also not a true
   FOUNTAIN per the strict definition). Wrist distance is STABLE
   in 180-243 range — the wide-stance signature. This is the
   "uncrossed but wide" pattern.

**Key visual finding:** H12 v8's FOUNTAIN_3+ class actually
captures **3 different kinds of 3-ball patterns**:
- True FOUNTAIN (parallel-hand columns, no crossings)
- Crossed-arm columns (lower-amplitude hand crossings)
- Wide cascade (uncrossed but wide)
- Mills Mess (full hand-body crossings)

The H65 ground truth labeled all 3 identical FOUNTAIN_3+ phases
as either "FOUNTAIN" or "OTHER" inconsistently. The H78
mean_diff signal can distinguish Mills Mess (mean_diff > 10) from
the other two (mean_diff < 8).

## Recommended operating point (post-H78)

**h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74 + H78v5 + H52 + H53**

- H78v5 = `mean_diff_per_frame > 10` rejects Mills Mess
  (f=890-936) and similar extreme-crossing patterns
- H78v5 is in a flat sensitivity region (thresholds 8-14 all give
  identical results)
- H78v5 adds 1 correct rejection (f=890-936) with 0 false rejections
- End-to-end accuracy: 78.9% (H75) → 84.2% (H78v5) on the H70 sample

## Verdict: PASS (narrow-scope precision improvement)

H78 wrist-distance signal is a useful, flat-region post-filter
that adds 1 new correct rejection (f=890-936 Mills Mess) to the
H75 stack. The filter is well-justified by physical geometry
(crossed-arm patterns have inherently more rapid wrist-distance
changes than parallel-hand patterns).

## Negative findings

1. **H78 does NOT catch the YouTube FOUNTAIN_3+ misclassifications**
   (f=482-594 static hold, f=800-861 real CASCADE). These have
   mean_diff 5.08 and 4.89, well below the 10 threshold. The
   YouTube juggler has a stable hand stance across all phases.

2. **H78's mean_diff signal depends on the juggler's individual
   style.** A juggler who does more dramatic Mills Mess vs a
   juggler who does gentler crossings will have different
   mean_diff values. The threshold of 10 is calibrated for the
   2 identical videos but may need re-calibration for other
   jugglers.

3. **The "real FOUNTAIN" ground truth may itself be unreliable.**
   H65's verdicts on f=631-669 and f=977-1011 are both labeled
   "FOUNTAIN" but vision tool now describes them as "crossed-arm
   columns" and "wide cascade" respectively. The strict
   juggling-technique definition of "fountain" is "two parallel
   columns of balls thrown by the same hand" — neither phase
   meets this strict criterion. The H12 v8 classifier's
   FOUNTAIN_3+ label may be capturing all non-cascade patterns
   (which includes Mills Mess, crossed-arm columns, and wide
   cascade).

4. **H78's std_wrist_dist signal (threshold > 50) is also
   useful** but redundant with mean_diff > 10 on this sample
   (f=890-936 has both high std and high mean_diff). The flat
   region of the std threshold is narrower (only std > 50 gives
   the same result).

## Future research

1. **H79: per-ball-count calibration of H78** — the YouTube
   5-ball phases have lower mean_diff than the identical 3-ball
   phases. A per-ball-count threshold (e.g., 8 for 5-ball, 10 for
   3-ball) might preserve more real juggling on YouTube.

2. **H80: stricter "true FOUNTAIN" detection** — if downstream
   consumers want only true parallel-column patterns, the H12 v8
   FOUNTAIN_3+ class can be partitioned into "true FOUNTAIN"
   (low std AND low mean_diff) vs "other non-cascade patterns"
   (high std OR high mean_diff). This would be a much narrower
   filter that the H12 v8 class doesn't natively support.

3. **H81: cross-validate H78v5 on the 113 manual review pairs**
   (the H59 ground truth) to verify the per-edge impact. The
   H78 signal is at the phase level; the per-edge impact would
   need a separate evaluation.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78_wrist_distance.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78v2_wrist_distance.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78v3_sens_grid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78v4_end_to_end.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78v5_refined.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h78_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h78_wrist_distance_per_phase.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h78v2_wrist_distance_per_phase.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h78v3_sensitivity_grid.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h78v4_stack_per_phase.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h78v4_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h78/*.png` (3 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h78_report.md` (this file)
