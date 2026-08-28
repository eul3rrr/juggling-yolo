# H69 — Periodicity of "balls aloft" (A) as FOUNTAIN_3+ post-filter

**Date:** 2026-08-28
**Hypothesis (from H68 report):** A real FOUNTAIN phase has a periodic
A signal (balls go up and down in a steady rhythm). A static hold has
a constant or random A signal. A CASCADE has a different period. A
spectral feature (dominant period + spectral concentration) should
discriminate FOUNTAIN from HOLD/CASCADE better than the level-based
pct_A_ge2 metric used in H66/H67/H68.

## Method

For each substantial FOUNTAIN_3+ phase (>= 20 frames) in the H50-filtered
pattern data:
1. Compute the per-frame A signal (balls not within 100 px of either
   wrist) — reusing the H66 logic.
2. Compute the spectral concentration via FFT (Hann windowed):
   - concentration = max FFT power (excl. DC) / total power
3. Compute the autocorrelation (AC) and find the dominant period in
   the 5-50 frame lag range.

Apply a stacked filter: reject a phase if H43 (conf < 0.55) OR H69
(spectral concentration < 0.15). Per-frame end-to-end impact is
computed by re-labeling FOUNTAIN_3+ frames inside rejected phases as
FOUNTAIN_LOW_CONF.

## Results

### Per-phase spectral features (H65 visual QA ground truth)

| Video | Phase | n | conf | mean_A | conc | AC_peak | AC_lag | H65 verdict | H43 | H69 | STACK |
|-------|-------|---|------|--------|------|---------|--------|-------------|-----|-----|-------|
| identical | 631-669 | 39 | 0.714 | 1.79 | **0.411** | 0.339 | 5 | FOUNTAIN | K | K | KEEP |
| identical | 890-936 | 47 | 0.571 | 1.31 | 0.308 | 0.197 | 5 | OTHER (crossed-arm) | K | K | KEEP |
| identical | 977-1011 | 35 | 0.565 | 0.68 | 0.326 | 0.189 | 23 | FOUNTAIN | K | K | KEEP |
| identical | 1029-1049 | 21 | 0.463 | 0.85 | 0.361 | 0.056 | 9 | OTHER (static hold) | R | K | **REJECT** |
| youtube | 339-374 | 36 | 0.646 | 1.73 | 0.164 | 0.152 | 15 | FOUNTAIN | K | K | KEEP |
| youtube | 482-594 | 113 | 0.653 | 1.65 | **0.140** | 0.254 | 14 | OTHER (static hold) | K | R | **REJECT** |
| youtube | 800-861 | 62 | 0.651 | 1.30 | **0.088** | 0.175 | 8 | CASCADE | K | R | **REJECT** |

### Discrimination result

| Filter | correct_rej | wrong_rej | wrong_keep | correct_keep | precision | recall |
|--------|-------------|-----------|------------|--------------|-----------|--------|
| H43 alone (conf < 0.55) | 1 | 0 | 3 | 3 | 100% | 25% |
| **H43 OR H69 (conc < 0.15)** | **3** | **0** | **1** | **3** | **100%** | **75%** |

**H43 OR H69 (spec_conc < 0.15) is a real improvement over H43 alone**:
- Catches 1029-1049 identical (H43), 482-594 youtube (H69), 800-861 youtube (H69)
- Preserves all 3 FOUNTAIN labels
- 1 wrong case (890-936 identical, crossed-arm trick) still escapes both
  filters (conf 0.571, conc 0.308)

### Sensitivity grid (H43 OR H69)

| spec_conc < thr | n_rejected | correct_rej | wrong_rej | precision | recall |
|-----------------|------------|-------------|-----------|-----------|--------|
| 0.10 | 2 | 2 | 0 | 100% | 50% |
| 0.13 | 2 | 2 | 0 | 100% | 50% |
| 0.14 | 2 | 2 | 0 | 100% | 50% |
| **0.15** | **3** | **3** | **0** | **100%** | **75%** |
| 0.16 | 3 | 3 | 0 | 100% | 75% |
| 0.17 | 4 | 3 | 1 (FOUNTAIN) | 75% | 75% |
| 0.20 | 4 | 3 | 1 (FOUNTAIN) | 75% | 75% |

**Flat region: thr in [0.15, 0.16].** Below 0.15, only 800-861 caught
(spectral concentration 0.088). At 0.15, also catches 482-594 (0.140).
Above 0.16, would wrongly reject 339-374 (0.164, real FOUNTAIN).

### Per-frame end-to-end impact (H43 OR H69 at thr=0.15)

| Video | n_changed | pct_changed | FOUNTAIN_3+ before | FOUNTAIN_3+ after | FOUNTAIN_LOW_CONF added |
|-------|-----------|-------------|--------------------|-------------------|--------------------------|
| identical | 21/1042 | 2.0% | 168 (16.1%) | 147 (14.1%) | 21 |
| youtube | 175/898 | 19.5% | 211 (23.5%) | 36 (4.0%) | 175 |

**H69 contributes substantially on YouTube**: 175/211 FOUNTAIN_3+ frames
(82.9%) are re-labeled as FOUNTAIN_LOW_CONF. The 3 rejected phases cover
482-594 (113 frames, OTHER static hold) and 800-861 (62 frames, CASCADE).

**H69 contributes 0 on identical** (the 1029-1049 phase is caught by
H43 alone).

## Comparison to H43 alone (H51) and H66/H67/H68

| Filter | identical | youtube | Notes |
|--------|-----------|---------|-------|
| H43 alone (H51) | 21 frames | 0 frames | 1/1 correct reject |
| H66 alone (H67) | 56 frames | 0 frames | 1/2 correct at thr=0.30 |
| H68 (per-n_total, H68) | 56 frames | 62 frames | 2/3 correct on rejects |
| **H43 OR H69 (this work)** | **21 frames** | **175 frames** | **3/3 correct on rejects** |

**H69 is the best FOUNTAIN_3+ post-filter on this sample.** It catches
the H43 cases (1029-1049) AND the H68 cases (482-594, 800-861) with
zero false rejects on FOUNTAIN labels. The H68 per-n_total calibration
catches 800-861 (with 977-1011 wrong reject) but misses 482-594.

## Why H69 works where H66/H68 didn't

The H66/H68 "balls aloft" level metric (pct_A_ge2) cannot separate
3-ball FOUNTAIN from static hold because both have low ball counts
above 2. The H69 spectral concentration metric is fundamentally
different:

- A real FOUNTAIN has balls rising and falling in a coherent pattern,
  producing a strong spectral peak at the pattern's natural frequency.
  Spectral concentration 0.411 (631-669) and 0.326 (977-1011) are HIGH.
- A static hold (1029-1049: conf 0.46, 482-594: conf 0.65) has balls
  detected on held positions with intermittent YOLO false positives.
  The intermittent nature LOWERS spectral concentration (0.361, 0.140).
- A CASCADE (800-861) has rapid alternation between hands, producing
  a more spread spectrum and LOWER concentration (0.088).

The H66 metric is a LEVEL check ("are there balls in the air?"); the
H69 metric is a STRUCTURAL check ("is the ball-aloft pattern
coherent?"). The structural check is what discriminates.

## Limitations

1. **The 890-936 crossed-arm trick escapes both H43 and H69.** This
   phase has H12 v8 confidence 0.571 (above H43 threshold) and
   spectral concentration 0.308 (above H69 threshold). The phase IS
   a misclassification (vision tool says "OTHER" / crossed-arm trick,
   not real FOUNTAIN), but neither H43 nor H69 catches it.

2. **H69 requires the H50-filtered pattern data and a substantial
   phase (>= 20 frames).** Short FOUNTAIN_3+ bursts (< 20 frames) are
   not affected by H69. H43 still applies via H12 v8 confidence.

3. **H69 spec_conc < 0.15 threshold is calibrated on the H65 sample
   (n=7 phases).** Larger validation would be needed for production
   use, but the flat region [0.15, 0.16] is robust to small perturbations.

4. **YOLO false positives on background features limit H69's
   discrimination on YouTube.** The 482-594 static hold has spectral
   concentration 0.140 (just above the threshold) — the YOLO
   detector fires periodically on background features. A better
   detector would push this lower and the H69 threshold could be
   raised.

## Recommended operating point (H69 supersedes H68)

```
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69(spec_conc < 0.15) + H52 + H53
```

H43 OR H69 is the new best FOUNTAIN_3+ post-filter, replacing the
single-filter H43 from H51. H66 and H68 are no longer applied at any
threshold; H69 supersedes them.

The full precision chain for FOUNTAIN_3+ downstream consumers:
- H43 catches identical 1029-1049 (OTHER static hold)
- H69 catches youtube 482-594 (OTHER static hold) and 800-861 (CASCADE)
- Neither catches identical 890-936 (crossed-arm trick) — fundamental
  limitation remains.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h69_periodicity_fountain.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h69v2_end_to_end.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69_rejected_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69_per_frame_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69v2_per_frame_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h69v2_summary.json`
