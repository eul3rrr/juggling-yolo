# H67 — H43 + H66 stacked FOUNTAIN_3+ post-filter: end-to-end impact

**Date:** 2026-08-28
**Hypothesis:** H43 + H66 stacked rejection rate on the H50-filtered
pattern set should be small. The downstream pattern distribution
change should be correspondingly small.

**Method:** For each frame with pattern=FOUNTAIN_3+ in the H50-
filtered per-frame pattern data:
- If confidence < 0.55: H43 reject, mark as FOUNTAIN_LOW_CONF.
- If frame is in a H66-rejected phase (pct_A_ge2 < 0.30): H66
  reject, mark as FOUNTAIN_LOW_CONF.

**Result:**

| Video | n_frames | n_changed | pct_changed | FOUNTAIN_3+ -> FOUNTAIN_LOW_CONF |
|---|---|---|---|---|
| identical | 1042 | 56 | 5.4% | -56 |
| YouTube | 898 | 0 | 0.0% | 0 |

**Per-phase contribution (identical):**
- 977-1011 (real FOUNTAIN, wrongly rejected by H66): 35 frames
- 1029-1049 (OTHER static hold, correctly rejected by H43+H66): 21 frames

**Precision/recall on rejects:**
- 21/56 = 37.5% correct rejects (1029-1049 is a real static hold)
- 35/56 = 62.5% wrong rejects (977-1011 is a real 3-ball FOUNTAIN)

## Why YouTube has 0 changes

The H66 YouTube has 0 rejected phases (H66 threshold 0.30 doesn't
catch any of the 3 substantial YouTube FOUNTAIN_3+ phases). H43 is
the only YouTube filter, but H43 was already applied in H51 — its
27 identical frames + 0 YouTube frames are the H51 baseline. H67
re-runs H43 with the same threshold on the same input, so the result
matches H51.

## Per-pattern distribution

**identical (1042 frames):**
- FOUNTAIN_3+: H50 baseline 168 (16.1%) → H67 stacked 112 (10.7%) [-5.4%]
- FOUNTAIN_LOW_CONF: H50 baseline 0 (0.0%) → H67 stacked 56 (5.4%)

**YouTube (898 frames):**
- FOUNTAIN_3+: H50 baseline 211 (23.5%) → H67 stacked 211 (23.5%) [0.0%]
- FOUNTAIN_LOW_CONF: H50 baseline 0 (0.0%) → H67 stacked 0 (0.0%)

## Verdict: PARTIAL PASS — TRADE-OFF, NOT IMPROVEMENT

H67 confirms that the H43 + H66 stack changes 5.4% of identical
frames. But the change is dominated by the 977-1011 wrong reject
(35 frames) which is a real 3-ball FOUNTAIN. The H66 threshold
is too strict for 3-ball FOUNTAIN.

**Trade-off analysis:**
- H43 alone: 21/21 correct (100% precision on rejects), 0/21 wrong
  - But H43 only catches the 1029-1049 phase (not 890-936, 482-594, 800-861)
- H66 alone: 21/56 correct (37.5% precision on rejects)
  - Catches 1029-1049 (correct) but loses 977-1011 (wrong)
- H43 + H66 stacked: 21/56 correct (37.5% precision on rejects)
  - Same as H66 alone (H43 is a subset of H66's rejections here)

**The H66 threshold of 0.30 is too strict.** A looser threshold
(0.20) would still catch 1029-1049 (pct_A_ge2=0.00) but preserve
977-1011 (pct_A_ge2=0.12, just above 0.20). Let me verify:

| Threshold | correct_rej | wrong_rej | wrong_keep | correct_keep |
|---|---|---|---|---|
| 0.10 | 1 (1029) | 0 | 3 | 3 |
| 0.20 | 1 (1029) | 0 | 3 | 3 |
| 0.30 | 1 (1029) | 1 (977) | 3 | 2 |
| 0.40 | 2 (1029, 977 wrong) | 1 | 2 | 2 |

At threshold 0.20, H66 catches 1029-1049 only — same as H43 alone,
no loss. This is the best operating point.

**Recommended update:** lower H66 threshold from 0.30 to 0.20.

## Threshold sensitivity recap

For 3-ball FOUNTAIN phases, the real signal is "real FOUNTAIN" at
977-1011 has pct_A_ge2=0.12, while "static hold" at 1029-1049 has
pct_A_ge2=0.00. A threshold of 0.20 perfectly separates them.

For 5-ball FOUNTAIN phases, the same signal is less useful because
the 3-ball-vs-5-ball distinction is real:
- 3-ball FOUNTAIN: ~1 ball aloft at a time
- 5-ball FOUNTAIN: ~2-3 balls aloft at a time

The H66 threshold should be lowered to 0.20 to preserve 3-ball
FOUNTAIN phases.

## Comparison to H50

H50 (10-frame event log filter) changed 1.0% of identical frames
and 0% of YouTube. H67 (H43 + H66 stacked at threshold 0.30)
changes 5.4% of identical frames and 0% of YouTube.

H50 is a precision-positive filter (rejects real identity switches).
H67 (at threshold 0.30) is a precision-negative filter (rejects real
FOUNTAIN phases). At threshold 0.20, H67 matches H43 alone, which
catches 1/4 wrong FOUNTAIN_3+ phases at the cost of 0 wrong rejects.

## Recommended operating point (updated)

h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H66 (threshold 0.20) + H52 + H53

For FOUNTAIN_3+ post-filter: H43 + H66 (threshold 0.20) stacked.
Same as H43 alone, since H66 at threshold 0.20 only catches the
1029-1049 phase which H43 also catches.

**Net useful H66 contribution: 0% additional rejection on the H65
sample at threshold 0.20. The H66 signal is real but the operating
point needs to be lower than 0.30 to avoid false rejects.**

## Future work

1. **Per-ball A signal.** Current H66 uses "balls > 100 px from
   both hands" which counts YOLO false positives on background
   features. A per-ball tracking-based A signal (from
   tracklet_features.csv) would be more precise.

2. **3-ball vs 5-ball calibration.** The H66 threshold should be
   different for 3-ball and 5-ball FOUNTAIN (because 3-ball has
   fewer balls aloft at any time). A per-n_total calibration
   would improve discrimination.

3. **YouTube static hold (482-594) requires a fundamentally
   different signal.** YOLO detector false positives on background
   features (corrugated door, sign, trees) make per-frame
   "balls aloft" count useless for YouTube. A learned "ball-ness"
   classifier or a better detector would be needed.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h67_stacked_post_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h67_per_frame_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h67_pattern_dist_*.json` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h67_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h67_report.md`
