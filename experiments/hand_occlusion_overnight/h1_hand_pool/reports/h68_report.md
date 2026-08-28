# H68 — per-n_total threshold calibration for H66 + H43 stacked

**Date:** 2026-08-28
**Hypothesis:** A per-n_total threshold (3-ball: 0.20, 5-ball: 0.45)
should catch 2/4 wrong FOUNTAIN_3+ phases while preserving real
FOUNTAIN. H67 recommended 0.20 for 3-ball; H68 tests per-n_total
calibration to also catch the 5-ball 800-861 CASCADE.

**Method:** Apply H43 (conf < 0.55) and H66 (per-n_total pct_A_ge2
< threshold) to the H50-filtered per-frame pattern data.

| n_total | threshold | rationale |
|---|---|---|
| 3 | 0.20 | H67 recommendation; preserves 3-ball FOUNTAIN with only 1 ball aloft |
| 5 | 0.45 | H68 hypothesis; catches 5-ball CASCADE (pct_A_ge2=0.42) |

**Result:**

| Video | n_total | phase | conf | pct_A_ge2 | thr | H43 | H66 | H68 | vision |
|---|---|---|---|---|---|---|---|---|---|
| identical | 3 | 631-669 | 0.714 | 0.69 | 0.20 | K | K | KEEP | FOUNTAIN |
| identical | 3 | 890-936 | 0.571 | 0.31 | 0.20 | K | K | KEEP | OTHER |
| identical | 3 | 977-1011 | 0.565 | 0.12 | 0.20 | K | R | REJECT | FOUNTAIN |
| identical | 3 | 1029-1049 | 0.463 | 0.00 | 0.20 | R | R | REJECT | OTHER |
| youtube | 5 | 339-374 | 0.646 | 0.58 | 0.45 | K | K | KEEP | FOUNTAIN |
| youtube | 5 | 482-594 | 0.653 | 0.56 | 0.45 | K | K | KEEP | OTHER |
| youtube | 5 | 800-861 | 0.651 | 0.42 | 0.45 | K | R | REJECT | CASCADE |

**H68 rejection precision: 2/3 = 67% (2 correct, 1 wrong)**.
**H68 recall on rejects: 2/4 = 50% (catches 1029-1049 OTHER and
800-861 CASCADE)**.

**Per-frame end-to-end impact:**
- identical: 56/1042 (5.4%) frames changed (same as H67)
- YouTube: 62/898 (6.9%) frames changed (H67 had 0; H68 adds the
  800-861 CASCADE frames)

## Comparison to H67 (single threshold 0.30)

| Filter | correct_rej | wrong_rej | wrong_keep | correct_keep | precision |
|---|---|---|---|---|---|
| H43 (conf < 0.55) | 1 | 0 | 3 | 3 | 100% |
| H66 thr=0.20 (3-ball) | 1 | 1 | 3 | 2 | 50% |
| H66 thr=0.30 (H67) | 1 | 1 | 3 | 2 | 50% |
| H66 thr=0.45 (5-ball) | 0 | 0 | 1 | 2 | n/a |
| H68 (per-n_total) | 2 | 1 | 2 | 2 | 67% |
| H43 + H68 stacked | 2 | 1 | 2 | 2 | 67% |

H68 catches 800-861 (5-ball CASCADE) at the cost of wrongly
rejecting 977-1011 (3-ball FOUNTAIN). Net useful: 1 additional
correct catch, 1 additional wrong reject.

## Per-n_total threshold sensitivity (3-ball only)

For 3-ball FOUNTAIN_3+ on identical:
- threshold 0.00: 0 rejects (no separation)
- threshold 0.10: 0 rejects (1029 below 0.10 false; wait, 1029=0.00, so 1029 IS rejected; but 977=0.12, just above 0.10)
  Actually: threshold 0.10 rejects 1029 (pct=0.00 < 0.10) only. 977 (0.12) > 0.10 so keep.
- threshold 0.20: 1 correct (1029), 1 wrong (977=0.12 < 0.20)
- threshold 0.30: 1 correct (1029), 1 wrong (977 + 890=0.31 < 0.30 false; actually 890=0.31 > 0.30)
  Wait, 890-936 has pct=0.31. threshold 0.30 keeps 890 (0.31 > 0.30). threshold 0.20 keeps 890.
- threshold 0.40: 1 correct (1029), 1 wrong (977 + 890=0.31 < 0.40)

For 3-ball: NO threshold preserves 977-1011 AND rejects 1029-1049
without threshold 0.10 (which would only reject 1029 — same as
H43 alone, 977 has pct_A_ge2=0.12 which is above 0.10).

**At threshold 0.10, H66 catches only 1029-1049** — same as H43
alone. Adding H66 doesn't help.

**At threshold 0.20, H66 catches 1029-1049 + wrongly 977-1011** —
worse than H43 alone.

**Conclusion: for 3-ball, H66 cannot improve over H43 on the H65
sample.** The 977-1011 phase is too close to 0.10 to be safely
separated from 1029-1049.

## Per-n_total threshold sensitivity (5-ball only)

For 5-ball FOUNTAIN_3+ on YouTube:
- threshold 0.50: 0 rejects (no separation; 339=0.58, 482=0.56, 800=0.42)
- threshold 0.45: 1 correct (800-861=0.42 < 0.45)
- threshold 0.40: 1 correct (800-861=0.42 > 0.40 — keep!)

Wait: 0.42 > 0.40 means KEEP. So threshold 0.40 keeps 800-861.
- threshold 0.42: 1 correct (800-861=0.42 < 0.42? No, equal means KEEP)

Let me recompute. For YouTube:
- 339-374 (FOUNTAIN): pct=0.576
- 482-594 (OTHER): pct=0.558
- 800-861 (CASCADE): pct=0.421

threshold 0.50: 0 rejects (all keep)
threshold 0.45: 1 reject (800, correct catch)
threshold 0.40: 0 rejects (800=0.42 > 0.40)
threshold 0.30: 0 rejects (800=0.42 > 0.30)

**For 5-ball, threshold 0.45 catches 800-861 only.** This is
correct (CASCADE), no harm.

## Combined H68 analysis

H43 + H68 stacked (per-n_total thresholds):
- 3-ball: H43 + H66(thr=0.20) catches 1029 + wrongly 977. Same as H43 + H66(thr=0.30).
- 5-ball: H43 + H66(thr=0.45) catches 800-861 (NEW, not caught by H43 alone).

**Net improvement over H43 + H66 (single 0.30 threshold):**
- 1 additional correct catch (800-861 YouTube CASCADE)
- 0 additional wrong rejects

**H43 + H68 (per-n_total) rejection precision: 2/2 = 100% on the
H65 sample.** (Both 1029-1049 and 800-861 are correctly caught; no
real FOUNTAIN wrongly rejected.)

Wait, let me recheck. 977-1011 (FOUNTAIN) is wrongly rejected at
threshold 0.20. So precision is 1/2 (only 1029-1049 correct, 977-1011
wrong). Let me re-do:

H43 + H68 stacked at 3-ball threshold 0.20:
- 1029-1049 OTHER: H43 rejects (conf 0.46) AND H66 rejects (pct 0.00). REJECT.
- 977-1011 FOUNTAIN: H43 keeps (conf 0.57) BUT H66 rejects (pct 0.12 < 0.20). REJECT.
- 890-936 OTHER: H43 keeps (conf 0.57), H66 keeps (pct 0.31 > 0.20). KEEP.
- 631-669 FOUNTAIN: H43 keeps (conf 0.71), H66 keeps (pct 0.69 > 0.20). KEEP.

H43 + H68 stacked at 5-ball threshold 0.45:
- 339-374 FOUNTAIN: H43 keeps, H66 keeps (pct 0.58 > 0.45). KEEP.
- 482-594 OTHER: H43 keeps, H66 keeps (pct 0.56 > 0.45). KEEP.
- 800-861 CASCADE: H43 keeps, H66 rejects (pct 0.42 < 0.45). REJECT.

Combined:
- 3 rejected: 1029-1049 (correct), 977-1011 (wrong), 800-861 (correct)
- 4 kept: 631-669 (correct), 890-936 (wrong), 339-374 (correct), 482-594 (wrong)

Rejection precision: 2/3 = 67%. **Worse than H43 alone (100%)**.

**H43 alone is still the best FOUNTAIN_3+ post-filter on the H65
sample.** The H68 per-n_total calibration doesn't help because the
3-ball 977-1011 wrongly reject is the dominant cost.

## Final verdict: NEGATIVE result for H68

H68 attempted to improve on H67 by using per-n_total thresholds
(3-ball: 0.20, 5-ball: 0.45). The 5-ball threshold correctly
catches 800-861 YouTube CASCADE. But the 3-ball threshold
incorrectly rejects 977-1011 (real FOUNTAIN with only 1 ball
aloft at a time).

**Net: 1 additional correct catch, 1 additional wrong reject.**
H68 ends up with 67% precision on rejects, the same as H67.

**H43 alone remains the best FOUNTAIN_3+ post-filter.** The H66
signal is real but its operating point cannot safely separate
"3-ball FOUNTAIN" from "static hold" — the gap is too narrow
(0.12 vs 0.00).

## The fundamental limit

The H66 signal (balls aloft) cannot discriminate 3-ball FOUNTAIN
from static hold. The reason: a 3-ball FOUNTAIN has only 1 ball
aloft at most times. The pct_A_ge2 metric is therefore inherently
low for 3-ball FOUNTAIN. A static hold also has low pct_A_ge2.
The two cases overlap.

**A truly reliable FOUNTAIN_3+ classifier would need a different
signal** — perhaps the periodicity of ball aloft (FOUNTAIN has
cyclic pattern, hold is constant) or the ball HAND-OFF pattern
(FOUNTAIN has periodic catch-throw pairs, hold has none).

## Operating point: UNCHANGED

The recommended operating point remains:
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H52 + H53

H66 + H68 do not improve over H43 alone on the H65 sample. They
remain useful as diagnostic signals but should NOT be applied as
post-filters at the current thresholds.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h68_per_n_total_calibration.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h68_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h68_rejected_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h68_per_frame_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h68_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h68_report.md`
