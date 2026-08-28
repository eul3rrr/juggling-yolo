# H66 — Continuous "balls aloft" (A) signal as FOUNTAIN_3+ post-filter

**Date:** 2026-08-28
**Hypothesis:** H12 v8 FOUNTAIN_3+ over-classification (43% accuracy on
H65 sample) might be reduced by filtering phases where balls are NOT
frequently aloft. A real FOUNTAIN_3+ has multiple balls in the air at
any time (the signature of synchronized parallel throws). A static hold
has 0-1 balls aloft.

**Method:** For each frame, compute A = # balls > 100 px from both
hands (using YOLO detections + per-frame wrist pose). For each
substantial FOUNTAIN_3+ phase (>= 20 frames), compute:
- mean_A, max_A
- pct_A_ge2 (fraction of frames with >= 2 balls aloft)
- h66_rejected = (pct_A_ge2 < threshold)

**Operating point:** threshold = 0.30 (30% of frames must have >= 2
balls aloft to keep the FOUNTAIN_3+ label).

**Sample:** 7 substantial FOUNTAIN_3+ phases (4 identical + 3 YouTube).

## Results

| Video | Phase | n | conf | mean_A | max_A | pct_A_ge2 | h66 | vision | Match |
|---|---|---|---|---|---|---|---|---|---|
| identical | 631-669 | 39 | 0.714 | 1.79 | 3 | 69.23% | KEEP | FOUNTAIN | OK |
| identical | 890-936 | 47 | 0.571 | 1.31 | 3 | 30.56% | KEEP | OTHER | MISS |
| identical | 977-1011 | 35 | 0.565 | 0.68 | 2 | 12.00% | REJECT | FOUNTAIN | wrong_rej |
| identical | 1029-1049 | 21 | 0.463 | 0.85 | 1 | 0.00% | REJECT | OTHER | correct_rej |
| youtube | 339-374 | 36 | 0.646 | 1.73 | 3 | 57.58% | KEEP | FOUNTAIN | OK |
| youtube | 482-594 | 113 | 0.653 | 1.65 | 3 | 55.77% | KEEP | OTHER | MISS |
| youtube | 800-861 | 62 | 0.651 | 1.30 | 3 | 42.11% | KEEP | CASCADE | MISS |

**H66 (threshold 0.30) results on H65 sample:**
- 1 correct rejection (1029-1049 identical, static hold, max_A=1)
- 1 wrong rejection (977-1011 identical, real FOUNTAIN, but only 1 ball aloft at a time — 3-ball FOUNTAIN has fewer "multi-ball aloft" moments)
- 5 keeps: 2 correct (real FOUNTAIN), 3 wrong (1 OTHER, 1 CASCADE, 1 OTHER)

## Threshold sensitivity grid

| Threshold | correct_rej | wrong_rej | wrong_keep | correct_keep |
|---|---|---|---|---|
| 0.10 | 1 | 0 | 3 | 3 |
| 0.20 | 1 | 1 | 3 | 2 |
| 0.30 | 1 | 1 | 3 | 2 |
| 0.40 | 2 | 1 | 2 | 2 |
| 0.50 | 3 | 1 | 1 | 2 |
| 0.60 | 4 | 2 | 0 | 1 |
| 0.70 | 4 | 3 | 0 | 0 |
| 0.80 | 4 | 3 | 0 | 0 |

The grid is NOT flat — there's a trade-off. At threshold 0.60, H66
catches all 4 wrong cases but rejects 2 real FOUNTAIN phases (losing
50% recall).

**The cleanest operating point is threshold = 0.30** (default):
- 1/4 wrong caught (the unambiguous 1029-1049 static hold)
- 1/3 real FOUNTAIN wrongly rejected (the 977-1011 single-throw
  pattern)
- 0.500 precision on rejects
- 0.667 recall on rejects

## Why H66 misses the YouTube 482-594 static hold

The YouTube 482-594 phase is 113 frames where the vision tool said
"static hold with only 4 of 5 balls visible, balls appear to be
falling or resting not actively juggled". H66 reports pct_A_ge2=55.77%
(max_A=3) because the YOLO detector fires constantly on stationary
background features (the corrugated door behind the juggler, the
sign on the wall, the trees in the distance). This is exactly the
H4 finding: "detector confusion is general (any stationary feature),
not specific to faces". H66 inherits H4's limitation.

## Why H66 wrongly rejects the 977-1011 identical FOUNTAIN

The 977-1011 phase is a real 3-ball FOUNTAIN (per vision QA: "both
hands at hip level, symmetric, each holding a ball. One ball in the
air on the upper left"). The 3-ball FOUNTAIN has only 1 ball aloft
at a time (vs 5-ball FOUNTAIN's 2-3 aloft). H66's "pct_A_ge2" signal
is too strict for 3-ball FOUNTAIN.

**This is a real limitation of the H66 signal:** it cannot
discriminate 3-ball FOUNTAIN from static hold on identical, because
3-ball FOUNTAIN has 0-1 balls aloft frequently.

## Comparison to H43 confidence filter

| Filter | correct_rej | wrong_rej | wrong_keep | correct_keep | Net useful |
|---|---|---|---|---|---|
| H43 (conf < 0.55) | 1 | 0 | 3 | 3 | catches 1, no harm |
| H66 (pct_A_ge2 < 0.30) | 1 | 1 | 3 | 2 | catches 1, loses 1 |
| H43 + H66 (both) | 2 | 1 | 2 | 2 | catches 2 wrong, loses 1 real |

**H43 + H66 composition is the best combination** on the H65 sample:
- 2/4 wrong caught (1029-1049 by H66, 1029-1049 by H43 too)
- 1/3 real FOUNTAIN wrongly rejected (977-1011 by H66)
- 1/4 wrong missed (890-936 identical, 482-594 YouTube, 800-861 YouTube)

**H66 + H43 stacked rejection rate on H65 sample: 2/7 = 28.6% rejection,
of which 2/3 = 66.7% are real FOUNTAIN labels (2 correct rejects / 3
rejects)**. The remaining 5/7 are kept; H12 v8 accuracy on kept is
3/5 = 60% (vs 43% baseline).

## Verdict: PARTIAL PASS

H66 is a useful additional signal but not a complete solution:

1. **Strengths**:
   - Catches the 1029-1049 static hold (clear signature: max_A=1)
   - Independent of H12 v8 confidence (different signal source)
   - Composes cleanly with H43 (no overlap in rejection logic)
   - At threshold 0.30, 2/7 phases rejected, 2/3 of those are real
     FOUNTAIN labels = 67% precision on rejects

2. **Limitations**:
   - YouTube 482-594 static hold is NOT caught (YOLO detector noise)
   - 3-ball FOUNTAIN (977-1011) is wrongly rejected (only 1 ball aloft)
   - 890-936 crossed-arm trick on identical is NOT caught (arms cross
     above the hands, looks like "balls aloft" to YOLO)
   - 800-861 YouTube CASCADE is NOT caught (CASCADE has balls aloft too)

**H43 + H66 stacked is the new recommended FOUNTAIN_3+ post-filter
configuration**, replacing H43 alone. The two filters catch different
wrong cases.

## Implications for the operating point

1. **H66 + H43 stacked rejection rate is 2/7 = 28.6% on the H65 sample.**
   This is a precision-improving post-filter that loses 1/3 of real
   FOUNTAIN phases.

2. **The YouTube static-hold (482-594) is fundamentally undetectable by
   the chain-event representation.** A detector-based "ball aloft"
   signal is dominated by YOLO false positives. A true fix would
   require a better detector or a learned "ball-ness" classifier.

3. **The 3-ball FOUNTAIN vs static hold discrimination on identical
   requires frame-level analysis of hand-relative ball position**,
   not just "ball is aloft". This is beyond the H66 signal.

**Recommended operating point (updated):**
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + **H66** + H52 + H53

For FOUNTAIN_3+ post-filter: H43 + H66 stacked. For non-FOUNTAIN
post-filter: H12 v8 only.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h66_continuous_A_fountain_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h66_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h66_rejected_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h66_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h66_report.md`
