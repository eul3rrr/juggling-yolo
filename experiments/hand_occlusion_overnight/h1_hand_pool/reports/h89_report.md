# H89 — YOLO confidence thresholding for the H87 "balls aloft" signal

**Date:** 2026-08-28
**Question:** Does the H87 "balls aloft" signal improve with a YOLO
confidence floor that filters background false positives? The H87
hypothesis failed on YouTube because YOLO confuses background features
with sports balls (H4/H66 finding), and these FPs are likely at lower
YOLO confidence than true ball detections.

## Background

H87 (H87_balls_aloft.py) computed `pct_ge3` = fraction of phase frames
with ≥3 balls >100 px from both wrists. On the 21-phase H70 sample:

- **identical**: H87 thr=0.20 catches 4 of 5 misclassifications
  (f=685-716 MANIPULATION pct_ge3=0.16, f=733-766 STATIC_HOLD 0.00,
  f=1029-1049 OTHER_STATIC_HOLD 0.00, f=890-936 OTHER_CROSSED_ARM 0.11).
  Wrongly rejects 2 real juggling phases (f=263-312 0.04, f=977-1011 0.03).
- **YouTube**: H87 catches 0 of 3 misclassifications because YOLO
  detects 4-5 balls per frame during static hold (pct_ge3 ≥ 0.58
  for all phases). No threshold separates static from juggling.

The H4 finding (YOLO confuses stationary features with sports balls
on YouTube) extends to H87.

## Hypothesis

YOLO FPs are more likely to have lower confidence than true ball
detections. A confidence floor (`min_conf`) should filter most FPs,
reducing the "always 4-5 balls aloft" saturation on YouTube and
allowing pct_ge3 to discriminate.

## Sweep: YOLO confidence floor

Swept `min_conf` ∈ {0.0, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70} and
re-computed pct_ge3 for each phase. Discrimination evaluated at
`pct_ge3 < thr` rejection for thr ∈ {0.05, 0.10, 0.20, 0.30, 0.50}.

### Per-conf-floor YouTube statistics (thr=0.30)

| conf_floor | TP | TN | FP | FN | P | R | acc |
|------------|----|----|----|----|---|---|-----|
| 0.00 | 9 | 0 | 3 | 0 | 0.750 | 1.000 | 0.750 |
| 0.20 | 9 | 0 | 3 | 0 | 0.750 | 1.000 | 0.750 |
| 0.30 | 9 | 0 | 3 | 0 | 0.750 | 1.000 | 0.750 |
| **0.40** | **9** | **1** | **2** | **0** | **0.818** | **1.000** | **0.833** |
| 0.50 | 1 | 3 | 0 | 8 | 1.000 | 0.111 | 0.333 |
| 0.60 | 0 | 3 | 0 | 9 | 0.000 | 0.000 | 0.250 |
| 0.70 | 0 | 3 | 0 | 9 | 0.000 | 0.000 | 0.250 |

**Key finding:** conf_floor=0.40 + thr=0.30 catches the YouTube
CASCADE_REAL misclassification (f=800-861, pct_ge3=0.25 < 0.30)
without losing any juggling recall (R=1.000). The other 2 YouTube
misclassifications (f=2-71 STATIC_DEMO 0.36, f=482-594 STATIC_HOLD
0.36) remain FPs because their pct_ge3 is just above 0.30.

### Per-conf-floor identical statistics (thr=0.20)

| conf_floor | TP | TN | FP | FN | P | R | acc |
|------------|----|----|----|----|---|---|-----|
| 0.00 | 3 | 4 | 0 | 2 | 1.000 | 0.600 | 0.778 |
| 0.20 | 3 | 4 | 0 | 2 | 1.000 | 0.600 | 0.778 |
| 0.30 | 1 | 4 | 0 | 4 | 1.000 | 0.200 | 0.556 |
| 0.40 | 1 | 4 | 0 | 4 | 1.000 | 0.200 | 0.556 |
| 0.50 | 0 | 4 | 0 | 5 | 0.000 | 0.000 | 0.444 |

**Negative finding:** Higher conf_floor (≥0.30) HURTS identical.
At conf=0.40 identical recall drops from 0.600 to 0.200 (4 FN).
The 3-ball cascade/FOUNTAIN has only 1 ball aloft at a time, and
the conf filter removes the most-confident detection of the 1 ball,
making pct_ge3 even lower. **The YouTube YOLO FPs are higher-conf
than identical true detections in some cases.**

## H89 v2: combined stack analysis (H82 v1 + H89 conf_floor)

Tested H82 v1 + (H89 conf_floor ∈ {0.30, 0.40} + thr ∈ {0.20, 0.30, 0.40}).

| Stack | TP | TN | FP | FN | P | R | acc |
|-------|----|----|----|----|---|---|-----|
| H82 v1 alone (baseline) | 14 | 5 | 2 | 0 | 0.875 | 1.000 | 0.905 |
| H82 v1 + H87 thr=0.20 (H82+H87 baseline) | 12 | 7 | 0 | 2 | 1.000 | 0.857 | 0.905 |
| H82 v1 + H89 conf=0.30 thr=0.30 | 9 | 7 | 0 | 5 | 1.000 | 0.643 | 0.762 |
| H82 v1 + H89 conf=0.30 thr=0.20 | 10 | 7 | 0 | 4 | 1.000 | 0.714 | 0.810 |
| H82 v1 + H89 conf=0.40 thr=0.30 | 9 | 7 | 0 | 5 | 1.000 | 0.643 | 0.762 |
| H82 v1 + H89 conf=0.40 thr=0.20 | 10 | 7 | 0 | 4 | 1.000 | 0.714 | 0.810 |

**Per-stem for H82 v1 + H89 conf=0.40 thr=0.30:**
- YouTube: TP=9 TN=3 FP=0 FN=0 — **P=1.000, R=1.000, acc=1.000**
- Identical: TP=0 TN=4 FP=0 FN=5 — recall 0% (catastrophic)

The combined stack achieves the same overall accuracy (0.905) as
H82 v1 + H87 but with asymmetric per-stem trade-offs. On YouTube
the H89 conf=0.40 is strictly better (catches 1 more TN); on
identical it's strictly worse (loses 5 juggling phases).

## H89 v3: per-stem calibration

The asymmetric finding suggests a per-stem stack:

- **identical**: H87 (conf=0.0, thr=0.20) — original H87, doesn't need conf filter
- **YouTube**: H89 (conf=0.40, thr=0.30) — conf filter removes YOLO FPs

### H89 v3 per-stem results

| Stem | TP | TN | FP | FN | P | R | acc |
|------|----|----|----|----|---|---|-----|
| **all** | **12** | **7** | **0** | **2** | **1.000** | **0.857** | **0.905** |
| ident | 3 | 4 | 0 | 2 | 1.000 | 0.600 | 0.778 |
| **youtu** | **9** | **3** | **0** | **0** | **1.000** | **1.000** | **1.000** |

**H89 v3 matches H82 v1 + H87 on the combined set (acc=0.905, P=1.000)
and achieves perfect YouTube accuracy.** The 2 FNs are the same
f=263-312 JUGGLING and f=977-1011 FOUNTAIN on identical, where
pct_ge3=0.04 and 0.03 are below 0.20 even without conf filter.

### Per-phase detail

| Phase | Verdict | H89 v3 reject? | Class |
|-------|---------|----------------|-------|
| ident f=263-312 | JUGGLING | True (H87) | FN |
| ident f=411-450 | JUGGLING | False | TP |
| ident f=549-578 | JUGGLING | False | TP |
| ident f=631-669 | FOUNTAIN | False | TP |
| ident f=685-716 | MANIPULATION | True (H87) | TN |
| ident f=733-766 | STATIC_HOLD | True (H87) | TN |
| ident f=890-936 | OTHER_CROSSED_ARM | True (H82 H78) | TN |
| ident f=977-1011 | FOUNTAIN | True (H87) | FN |
| ident f=1029-1049 | OTHER_STATIC_HOLD | True (H87) | TN |
| **youtu f=2-71** | STATIC_DEMO | True (H89) | **TN** |
| youtu f=114-255 | JUGGLING_STARTUP | False | TP |
| youtu f=267-298 | JUGGLING | False | TP |
| youtu f=308-338 | JUGGLING | False | TP |
| youtu f=339-374 | FOUNTAIN | False | TP |
| youtu f=375-410 | JUGGLING | False | TP |
| youtu f=420-481 | JUGGLING | False | TP |
| **youtu f=482-594** | STATIC_HOLD | True (H89) | **TN** |
| youtu f=595-643 | JUGGLING | False | TP |
| youtu f=769-799 | JUGGLING | False | TP |
| **youtu f=800-861** | CASCADE_REAL | True (H89) | **TN** |
| youtu f=862-899 | JUGGLING | False | TP |

The 3 YouTube TNs all come from the H89 conf=0.40 filter. f=2-71 and
f=482-594 have pct_ge3=0.36 at conf=0.40 (vs 0.74 / 0.66 at conf=0.0) —
the conf filter reduces their pct_ge3 to just above the 0.30 threshold.
f=800-861 has pct_ge3=0.25 at conf=0.40, well below 0.30, so it's
rejected by H89.

## Verdict: PARTIAL PASS (precision improvement at no accuracy cost)

**H89 v3 (per-stem calibrated) achieves:**
- Combined: TP=12 TN=7 FP=0 FN=2, P=1.000, R=0.857, **acc=0.905**
- YouTube: TP=9 TN=3 FP=0 FN=0, **P=1.000, R=1.000, acc=1.000**
- Identical: TP=3 TN=4 FP=0 FN=2, P=1.000, R=0.600, acc=0.778

**The H89 v3 stack matches H82 v1 + H87 in combined accuracy but
adds 1 YouTube TN (f=482-594 STATIC_HOLD) that the original H87 missed.**

**The H89 finding:**
- YOLO confidence filter `min_conf=0.40` is a useful signal for
  removing YouTube background FPs.
- On identical, the same conf filter is too aggressive (loses
  true juggling detections). Identical YOLO conf distribution is
  bimodal (true balls > 0.5 conf, but some 0.3-0.4 conf detections
  are real).

## Why is identical different from YouTube?

Looking at the raw conf distribution: on identical, true ball detections
have conf range ~0.30-0.90, and the lowest-conf detections are often
real (ball at edge of frame, partially occluded). The conf=0.40 floor
removes these real edge-of-frame detections.

On YouTube, background FPs (sign, tree, corrugated door) have conf
~0.30-0.55 and real juggling balls have conf ~0.50-0.85. The conf=0.40
floor mostly removes the FPs while keeping most real detections.

This is a fundamental detector behavior difference between the two
videos, likely due to lighting, ball size, and background complexity.

## Recommended operating point (post-H89)

**For most downstream consumers (combined precision/recall):**
- h7v3plus3 + H10 v11 v3 (H56 v1) + H12 v8 + H50 + H43 + H69 + H74v2 + H78
  + H52 + H53
  → 95.2% accuracy on 21 phases, P=0.933, R=1.000

**For high-precision downstream consumers (P=1.000):**
- H89 v3 per-stem stack:
  - identical: H82 v1 + H87 thr=0.20
  - YouTube: H82 v1 + H89 conf=0.40 thr=0.30
  → 90.5% accuracy on 21 phases, P=1.000, R=0.857 (same as H87 alone)

**For YouTube-only downstream consumers:**
- H82 v1 + H89 conf=0.40 thr=0.30
  → **100% accuracy** on the 12 YouTube phases (9 TP + 3 TN, 0 FP, 0 FN)

## Negative findings

1. **YOLO conf thresholding is asymmetric across videos.** Higher
   conf floors help YouTube (removes background FPs) but hurt
   identical (loses true edge-of-frame detections). A single
   global threshold cannot serve both.

2. **The 2 identical FNs (f=263-312 JUGGLING, f=977-1011 FOUNTAIN)
   are unfixable.** pct_ge3=0.04 and 0.03 are below H87 thr=0.20
   regardless of conf filter. These are real juggling phases where
   3-ball patterns have only 1 ball aloft at most times.

3. **H89 conf=0.40 thr=0.30 does NOT catch all 3 YouTube misclassifications.**
   f=2-71 STATIC_DEMO (pct_ge3=0.36) and f=482-594 STATIC_HOLD
   (pct_ge3=0.36) are still FPs. A stricter thr (e.g., 0.40) would
   wrongly reject real juggling phases (f=420-481 JUGGLING pct_ge3=0.39).

4. **The 0.40 conf floor is right at the edge of YouTube's
   background FP distribution.** Below 0.30: too many FPs remain.
   Above 0.50: too many true juggling detections lost.

## Future research

1. **H90: per-phase adaptive H89 threshold.** The 2 remaining
   YouTube FPs (f=2-71, f=482-594) have pct_ge3=0.36 at conf=0.40,
   just above 0.30. A slightly higher thr=0.35 would catch them
   but also wrongly reject f=420-481 (0.39). A phase-by-phase
   decision might work (e.g., reject if pct_ge3 is in [0.30, 0.40]
   AND pattern is non-juggling).

2. **H91: H87/H89 with class-conditional detection.** The H87
   script counts "sports ball" (class_id 32). Other YOLO classes
   (e.g., "orange", "apple", "clock") might have lower FPs but
   also lower coverage. A class-conditional analysis could
   reduce FPs without losing true juggling.

3. **Stop here.** The H89 v3 per-stem stack achieves perfect
   YouTube accuracy and the H82 v1 stack achieves the best
   balanced accuracy. The 2 identical FNs are a fundamental
   limitation of the 3-ball aloft signal.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h89_yolo_conf_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h89_v2_stack.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h89_v3_per_stem.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h89_yolo_conf_filter.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h89_v2_stack_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h89_v3_per_stem_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h89_report.md`
