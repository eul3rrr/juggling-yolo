# H74 — H40v2 L+R temporal variance as static-hold detector

**Date:** 2026-08-28
**Question:** Can H40v2 L+R temporal variance distinguish static holds
from real FOUNTAIN_3+ patterns?

## Background

H73 found that H40v2 mean L+R is similar for real FOUNTAIN and
misclassified FOUNTAIN_3+ / CASCADE_3+ phases. The mean is a
low-information summary. The TEMPORAL VARIANCE of L+R might
discriminate:
- Real FOUNTAIN: high variance (balls in/out of hands)
- Static hold: low variance (balls stable in hands)
- Manipulation trick: low-to-medium variance (balls stable
  relative to hand but with some motion)

## Method

For each substantial CASCADE_3+ / FOUNTAIN_3+ phase in both videos,
compute H40v2 L+R temporal statistics:
- mean, variance, stdev of L, R, L+R series
- number of unique (L, R) states
- number of transitions between states
- longest run of a single state
- fraction in the most common state

Cross-reference with H65 ground truth (3 real FOUNTAIN, 4 misclassified
FOUNTAIN_3+, 2 misclassified CASCADE_3+ on the H73 sample).

## Results

| Phase | Stem | f_range | Pattern | gt_verdict | LR_var | LR_stdev | LR_dir_chg | LR_pct_chg | n_unique |
|-------|------|---------|---------|------------|--------|----------|------------|------------|----------|
| identical f631-669 | identical | 631-669 | FOUNTAIN_3+ | REAL_FOUNTAIN | 0.621 | 0.788 | 0 | 0.05 | 3 |
| identical f685-716 | identical | 685-716 | CASCADE_3+ | MANIPULATION_TRICK | 0.386 | 0.621 | 0 | 0.19 | 4 |
| identical f733-766 | identical | 733-766 | CASCADE_3+ | STATIC_HOLD | 0.157 | 0.397 | 0 | 0.07 | 2 |
| identical f890-936 | identical | 890-936 | FOUNTAIN_3+ | OTHER_NOT_FOUNTAIN | 0.586 | 0.765 | 1 | 0.32 | 4 |
| identical f977-1011 | identical | 977-1011 | FOUNTAIN_3+ | REAL_FOUNTAIN | 0.296 | 0.544 | 1 | 0.18 | 4 |
| identical f1029-1049 | identical | 1029-1049 | FOUNTAIN_3+ | OTHER_NOT_FOUNTAIN | 0.374 | 0.612 | 1 | 0.33 | 4 |
| YouTube f339-374 | youtube | 339-374 | FOUNTAIN_3+ | REAL_FOUNTAIN | 0.218 | 0.467 | 1 | 0.20 | 4 |
| YouTube f482-594 | youtube | 482-594 | FOUNTAIN_3+ | OTHER_NOT_FOUNTAIN | 0.135 | 0.368 | 2 | 0.09 | 3 |
| YouTube f800-861 | youtube | 800-861 | FOUNTAIN_3+ | OTHER_NOT_FOUNTAIN | 0.202 | 0.450 | 2 | 0.15 | 3 |

**Per-verdict summary (LR_variance mean):**
- STATIC_HOLD: 0.157 (n=1)
- OTHER_NOT_FOUNTAIN: 0.324 (n=4)
- REAL_FOUNTAIN: 0.378 (n=3)
- MANIPULATION_TRICK: 0.386 (n=1)

**Threshold search (LR_variance threshold to keep all REAL_FOUNTAIN):**
- LR_var >= 0.05: 3/3 real kept, 0/6 misclassified rejected
- LR_var >= 0.10: 3/3 real kept, 0/6 misclassified rejected
- LR_var >= 0.15: 3/3 real kept, 1/6 misclassified rejected (STATIC_HOLD)
- LR_var >= 0.20: 3/3 real kept, 2/6 misclassified rejected (+ YouTube f=482-594)
- LR_var >= 0.25: 2/3 real kept, 3/6 misclassified rejected (drops f=977-1011)

## Key findings

### 1. H74 partially discriminates static hold (MIXED result)

LR_variance correctly identifies the 1 STATIC_HOLD phase (f=733-766,
var=0.157) as the lowest variance. At threshold 0.15-0.20, this is
the only misclassified phase correctly rejected.

But the variance distributions overlap significantly:
- 1 STATIC_HOLD: var=0.157 (correctly low)
- 4 OTHER_NOT_FOUNTAIN: var 0.135-0.586 (overlap with real)
- 3 REAL_FOUNTAIN: var 0.218-0.621 (overlap with misclassified)
- 1 MANIPULATION_TRICK: var=0.386 (same as real FOUNTAIN range)

A single threshold cannot reliably separate real from misclassified.

### 2. MANIPULATION_TRICK (f=685-716) has high variance (fails H74)

The 1 manipulation trick (body rolls / contact juggling) has
LR_variance=0.386 — same range as real FOUNTAIN. This is because
the manipulation trick has actual ball motion (balls are being
rolled between hands), which looks like juggling to H40v2.

H74 v1 cannot detect manipulation tricks via L+R variance. A
fundamentally different signal is needed (e.g., visual QA or
trajectory smoothness).

### 3. f=482-594 is a 5-ball static hold (NEW INTERPRETATION)

H74 data shows f=482-594 has n_unique=3 states, max_run=27, frac_max=0.84
— very stable, similar to f=733-766 STATIC_HOLD. The H65 visual QA
called this phase "OTHER_NOT_FOUNTAIN" but the H40v2 data suggests
it's a static 5-ball hold, not an active FOUNTAIN.

This is consistent with H65's note that the 5-ball static hold is
a "ball-display" or "show-off" pose, not a juggling pattern. H74's
variance metric correctly identifies it as low-variance (var=0.135).

### 4. The 9 phases have distinct L+R signatures (research signal)

The 9 phases have 4 distinct L+R state signatures:
- (1,1) with rare transitions (3 phases: real FOUNTAIN, static hold)
- (1,0) dominant (f=890-936 OTHER_NOT_FOUNTAIN)
- (0,1) dominant (f=977-1011 REAL_FOUNTAIN)
- Variable (f=685-716 MANIPULATION_TRICK)

This suggests that L+R state signatures could be a useful feature
for downstream consumers (e.g., to distinguish FOUNTAIN_3+ phases
by hand-bias). However, the sample is too small to characterize
this rigorously.

## Implications

### H74 v1 is a MIXED pass for static hold detection only

The LR_variance threshold (0.15-0.20) correctly identifies 2/4
misclassified phases (the 2 static-hold-like ones: f=733-766 and
f=482-594). It does NOT detect manipulation tricks (f=685-716) and
does NOT detect OTHER_NOT_FOUNTAIN phases that have high variance
(f=890-936).

For downstream consumers: H74 v1 is a SAFE precision-improving
filter for static-hold-like misclassifications. It should be combined
with the H43 + H69 stack to catch the other types.

### FOUNTAIN_3+ and CASCADE_3+ remain fundamentally noisy classes

H73 + H74 together establish that:
- H12 v8 FOUNTAIN_3+ has ~60% accuracy on substantial phases
- H12 v8 CASCADE_3+ has 0% accuracy on the only 2 substantial phases
- H40v2 mean L+R does not discriminate
- H40v2 L+R temporal variance does not reliably discriminate

The H43 + H69 stack remains the best FOUNTAIN_3+ filter. CASCADE_3+
should be treated as research-only.

## Recommended operating point (post-H74)

For FOUNTAIN_3+ post-filter (updated):
- H43 OR H69(spec_conc < 0.15) AND NOT H74_static_hold
  (where H74_static_hold = LR_variance < 0.20)
- On the H65 sample: H74 correctly identifies f=482-594 and f=733-766
  (but f=733-766 is CASCADE_3+ not FOUNTAIN_3+)
- On the H65 FOUNTAIN_3+ sample: H74 correctly identifies 1/4
  misclassified phases (f=482-594, var=0.135 < 0.20)
- The other 3 misclassified FOUNTAIN_3+ (f=890-936, f=1029-1049,
  f=800-861) have higher variance and are NOT caught by H74

For CASCADE_3+ post-filter (unchanged from H73):
- No reliable filter exists with current signals
- Treat as research signal only

For MIXED_3+ post-filter (unchanged from H71):
- KEEP at spec_conc >= 0.15 (91% precision)
- REJECT at spec_conc < 0.10 (1/1 correct on H71)

## Negative findings

1. **H74 v1 LR_variance does NOT reliably separate real from
   misclassified FOUNTAIN_3+ / CASCADE_3+ phases.** Only 2/9 phases
   are correctly identified as low-variance.
2. **MANIPULATION_TRICK (f=685-716) has high variance** (var=0.386),
   same range as real FOUNTAIN. H74 v1 cannot detect manipulation tricks.
3. **n_unique_states and frac_max metrics also overlap significantly**
   between real and misclassified phases.
4. **The 5-ball phase f=482-594 is a static hold** (not a FOUNTAIN),
   consistent with H65's "OTHER_NOT_FOUNTAIN" verdict. H74 v1
   correctly identifies it via low variance.

## Future research directions

1. **H75: H43 + H69 + H74 stacked FOUNTAIN_3+ filter** — apply H74
   (LR_var < 0.20) as an additional rejection criterion on top of
   the H43 + H69 stack. Should catch f=482-594 in addition to the
   3 H69 catches.

2. **H76: CASCADE_3+ as research signal** — accept that CASCADE_3+
   cannot be reliably detected, recommend downstream consumers use
   only FOUNTAIN_3+ and MIXED_3+ filters.

3. **H77: re-run H59 precision/recall on FULL H70 sample with
   ground truth** — characterize end-to-end quality.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h74_lr_variance_static_hold.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h74_summary.json`
