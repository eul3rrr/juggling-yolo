# H70 — H69 spec_conc characterization across pattern types

**Date:** 2026-08-28
**Question:** Is H69 spec_conc a FOUNTAIN-specific signal, or a more
general "pattern coherence" signal that applies to MIXED_3+, CASCADE_3+,
and other patterns?

## Method

For each substantial pattern phase (>= 20 frames of A data) in the
H50-filtered per-frame pattern data, compute the H69 spec_conc metric
(FFT spectral concentration of the per-frame A signal). Aggregate
spec_conc statistics per pattern type.

## Results

### Per-pattern H69 spec_conc statistics (n=19 substantial phases)

| Pattern | n | spec_conc mean | median | range | n<0.15 | ac_peak_mean |
|---------|---|----------------|--------|-------|--------|--------------|
| CASCADE_3+ | 1 | 0.498 | 0.498 | [0.498, 0.498] | 0 | 0.320 |
| FOUNTAIN_3+ | 6 | 0.240 | 0.308 | [0.088, 0.411] | 2 | 0.200 |
| MIXED_3+ | 11 | 0.205 | 0.196 | [0.124, 0.332] | 1 | 0.205 |
| MIXED_3+_UNCONFIRMED | 1 | 0.075 | 0.075 | [0.075, 0.075] | 1 | 0.163 |

**Key finding:** H69 spec_conc is **NOT FOUNTAIN-specific**. It is a
GENERAL "is this a real pattern?" signal that applies across all
pattern types:
- LOW spec_conc (< 0.15) catches: 2 FOUNTAIN_3+ (correct, both wrong),
  1 MIXED_3+ (transition), 1 MIXED_3+_UNCONFIRMED (video start setup)
- HIGH spec_conc (>= 0.20) is the dominant case for CASCADE_3+,
  real FOUNTAIN_3+, and most MIXED_3+

### H43 OR H69(spec_conc < 0.15) on ALL substantial phases

| Pattern | n_keep | n_reject | rejected phases (spec_conc) |
|---------|--------|----------|------------------------------|
| CASCADE_3+ | 1 | 0 | (none) |
| FOUNTAIN_3+ | 3 | 3 | 800-861 (0.088), 482-594 (0.140), 1029-1049 (H43 conf) |
| MIXED_3+ | 10 | 1 | 114-255 (0.124) |
| MIXED_3+_UNCONFIRMED | 0 | 1 | 2-71 (0.075) |

The 2 additional catches beyond FOUNTAIN_3+ are:
- 114-255 YouTube MIXED_3+ (conf 0.705, spec_conc 0.124)
- 2-71 YouTube MIXED_3+_UNCONFIRMED (conf 0.333, spec_conc 0.075)

### Visual QA of the 2 H70-rejected MIXED phases

Rendered contact sheets at `contact_sheets_h70/`. H70 vision tool calls
on these contact sheets (single vision pass, not multi-rater):

- **f=114-255 YouTube MIXED_3+** (H70 spec_conc 0.124): "NOT real
  5-ball juggling. Transition/pause sequence." H70 vision tool
  independently confirms the H69 spec_conc rejection.
- **f=2-71 YouTube MIXED_3+_UNCONFIRMED** (H70 spec_conc 0.075): "NOT
  real juggling. Static demonstration, pose, or freeze-frame." H70
  vision tool confirms the H69 rejection.

**Caveat:** the H70 vision tool is unreliable (consistent with the
H53 finding). The H65 multi-rater consensus verdicts on the FOUNTAIN_3+
phases are more trustworthy. For MIXED_3+ phases, we don't have
multi-rater consensus verdicts; the single-pass H70 vision call is the
best available signal. The H70 contact sheets are saved for future
multi-rater re-analysis.

### Per-frame end-to-end impact (extended to all pattern types)

If H43 OR H69(spec_conc < 0.15) were applied to ALL FOUNTAIN_3+ AND
MIXED_3+ phases (not just FOUNTAIN_3+):
- identical: 21 FOUNTAIN_3+ frames + 0 MIXED_3+ frames = 21 frames (2.0%)
- YouTube: 175 FOUNTAIN_3+ frames + ~100 MIXED_3+ frames (114-255) = ~275
  frames (~30% of substantial phases)

The YouTube 114-255 phase (142 frames) would be re-labeled as
MIXED_3+_LOW_CONF (analogous to FOUNTAIN_LOW_CONF for FOUNTAIN_3+).

## Why H69 spec_conc is general

A real juggling pattern has balls going up and down in a coherent
rhythm. This produces a strong spectral peak in the A signal at the
pattern's natural frequency. The H69 spec_conc metric measures the
*strength* of this peak relative to the total spectrum.

- A FOUNTAIN with synchronized parallel throws has high spec_conc
  because all balls rise and fall together.
- A CASCADE with alternating hand throws has the highest spec_conc
  (0.498) because of the clear 2-handed alternation pattern.
- A MIXED_3+ has medium spec_conc because it's a mix of patterns
  (less coherent than a single pattern type).
- A static hold or transition has low spec_conc because the A
  signal is dominated by YOLO false positives / detection noise,
  not a coherent pattern.

## Recommendation

The H69 spec_conc metric is a useful GENERAL "pattern coherence"
filter, not just a FOUNTAIN_3+ post-filter. It can be applied to
MIXED_3+ phases too, where it catches the same kind of "static hold
mislabeled as real juggling" problem that H43/H69 solved for
FOUNTAIN_3+.

**H70 operating point** (extends H69): h7v3plus3 + H10 v11 v3 + H12 v8
+ H50 + H43 + H69(spec_conc < 0.15) (for FOUNTAIN_3+) +
H70(spec_conc < 0.15) (for MIXED_3+) + H52 + H53

The H70 application to MIXED_3+ is a research-grade filter (not
production-validated) because we don't have H65-style multi-rater
verdicts for MIXED_3+ phases. The H70 contact sheets are saved for
future multi-rater verification.

## Negative findings

1. **Single-pass vision tool is unreliable on contact sheets.** The
   H70 vision tool calls on KEEP MIXED_3+ phases (conc 0.182, 0.235)
   said "not juggling" — opposite of what H12 v8 + H69 say. The H70
   vision tool also said 631-669 (H65-verified FOUNTAIN, conc 0.411)
   was "static pose, not juggling". This is the well-known
   vision_analyze unreliability (consistent with H53 finding).
   Multi-rater consensus is required for definitive verdicts.

2. **H69 spec_conc is overlapping across pattern types.** CASCADE_3+
   (0.498) and real FOUNTAIN_3+ (0.411) have similar high spec_conc.
   MIXED_3+ ranges 0.124-0.332. A single threshold (0.15) catches
   misclassifications across all pattern types but may over-reject
   real MIXED_3+ at the low end (e.g., 0.124 might be a real MIXED
   with low coherence due to the long 142-frame window).

3. **CASCADE_3+ has only 1 substantial phase in the dataset** (n=1).
   The 0.498 spec_conc for CASCADE_3+ is not generalizable.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h70_pattern_characterization.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h70_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h70v2_keep_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h70_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h70_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h70/*.png` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h70v2/*.png` (5 files)
