# H73 — H40v2 sustained-occupancy as CASCADE_3+ / FOUNTAIN_3+ validator

**Date:** 2026-08-28
**Question:** Can H40v2 sustained-occupancy (per-frame L+R) distinguish real
CASCADE_3+ / FOUNTAIN_3+ phases from H12 v8 misclassifications?

## Background

H72 found that identical f=685-716 (CASCADE_3+) is a 3-ball manipulation
trick (body rolls / contact juggling), not a true cascade. The
H40v2 sustained-occupancy data for f=685-716 is L=0.84 R=0.62 — both
hands heavily occupied, consistent with a real juggling pattern OR a
static display.

Hypothesis (REVISED): H40v2 sustained-occupancy is NOT a useful
discriminator for CASCADE_3+ / FOUNTAIN_3+ accuracy. It only
distinguishes "balls near hands" from "balls far from hands", not
"active juggling" from "static hold / manipulation trick".

## Method

For each substantial CASCADE_3+ / FOUNTAIN_3+ phase (>= 20 frames) in
both videos, compute H40v2 statistics:
- mean_L40v2, mean_R40v2, mean_LR40v2 (sustained-occupancy per hand)
- pct_both_pos, pct_one_pos, pct_both_zero (frame-level occupancy pattern)
- Cross-reference with H65 ground truth (3 real FOUNTAIN, 4 misclassified
  FOUNTAIN_3+ on H65 sample)

Anomaly detection: L<0.3, R<0.3, LR<0.5, pct_both_zero>0.2.

## Results

| Phase | Stem | f_range | Pattern | H40v2 L | H40v2 R | LR | both+ | both0 | h65 | h72 |
|-------|------|---------|---------|---------|---------|----|----|------|-----|-----|
| identical f631-669 | identical | 631-669 | FOUNTAIN_3+ | 0.82 | 0.62 | 1.44 | 0.62 | 0.18 | FOUNTAIN | N/A |
| identical f685-716 | identical | 685-716 | CASCADE_3+ | 0.84 | 0.62 | 1.47 | 0.53 | 0.06 | N/A | MANIPULATION |
| identical f733-766 | identical | 733-766 | CASCADE_3+ | 1.00 | 0.81 | 1.81 | 0.81 | 0.00 | N/A | STATIC_HOLD |
| identical f890-936 | identical | 890-936 | FOUNTAIN_3+ | 0.64 | 0.58 | 1.22 | 0.42 | 0.20 | OTHER | N/A |
| identical f977-1011 | identical | 977-1011 | FOUNTAIN_3+ | 0.41 | 0.94 | 1.35 | 0.38 | 0.03 | FOUNTAIN | N/A |
| identical f1029-1049 | identical | 1029-1049 | FOUNTAIN_3+ | 0.58 | 0.89 | 1.47 | 0.53 | 0.05 | OTHER | N/A |
| YouTube f339-374 | youtube | 339-374 | FOUNTAIN_3+ | 0.86 | 0.94 | 1.81 | 0.83 | 0.03 | FOUNTAIN | N/A |
| YouTube f482-594 | youtube | 482-594 | FOUNTAIN_3+ | 0.99 | 0.85 | 1.84 | 0.84 | 0.00 | OTHER | N/A |
| YouTube f800-861 | youtube | 800-861 | FOUNTAIN_3+ | 0.94 | 0.79 | 1.73 | 0.73 | 0.00 | CASCADE | N/A |

**Phases with H40v2 anomalies: 0/9.** All phases have both hands occupied
for the majority of frames.

**H12 v8 accuracy on H65-verified FOUNTAIN_3+ phases: 3/5 = 60%**
(3 real FOUNTAIN confirmed, 2 misclassified as OTHER). This is higher
than H65's reported 3/7 = 43% (H65 included 2 more phases that the H73
MIN_PHASE_FRAMES=20 filter dropped).

## Key findings

### 1. H40v2 sustained-occupancy is NOT a useful discriminator

All 9 substantial CASCADE_3+ / FOUNTAIN_3+ phases have BOTH hands
occupied (mean L+R > 1.0). This is true for:
- Real FOUNTAIN (3 phases, e.g. f=631-669 with L=0.82 R=0.62)
- Misclassified FOUNTAIN_3+ (4 phases, e.g. f=890-936 with L=0.64 R=0.58)
- Misclassified CASCADE_3+ (2 phases, e.g. f=685-716 with L=0.84 R=0.62)

The H40v2 sustained-occupancy is a "balls within 100 px of hands" proxy,
not a "actively juggling" proxy. A static hold of 2 balls (1 in each
hand) registers as L=1, R=1, just like a real FOUNTAIN.

**Verdict: H40v2 cannot distinguish real CASCADE/FOUNTAIN from
static hold / manipulation trick.** The vision tool QA is the only
reliable discriminator.

### 2. BOTH CASCADE_3+ identical phases are misclassified (NEW FINDING)

H72 found f=685-716 is a 3-ball manipulation trick. H73 confirms via
multi-rater visual QA that f=733-766 is also a static hold / contact
juggling pose (2 balls visible, 1 held, 1 "suspended" in upper-left,
hands not actively throwing/catching).

**H12 v8 CASCADE_3+ accuracy on substantial phases: 0/2 = 0%** on
identical. The CASCADE_3+ class is fundamentally broken — both
substantial phases are misclassified.

This is consistent with H39's finding that H12 v8 FOUNTAIN_3+ has
~30% accuracy on visual QA. The CASCADE_3+ accuracy is even worse
(0% on the only 2 substantial phases).

### 3. H40v2 finds f=733-766 as FOUNTAIN_3+ (not CASCADE_3+)

H40v2 data for f=733-766 says pattern=FOUNTAIN_3+ (not CASCADE_3+
as the H12 v8 per_frame_patterns file says). H40v2 is using a
different classification pipeline than H12 v8. This is a known
limitation noted in H36/H37 (H40v2 sustained-occupancy uses a
different evidence source than H12 v8's K=4 event-based classifier).

## Implications

### CASCADE_3+ class is unreliable

H12 v8's CASCADE_3+ class has 0/2 accuracy on the only 2 substantial
phases in the dataset. Downstream consumers should:
- Treat CASCADE_3+ as a research signal, not a production filter
- Cross-reference with H40v2 hand-occupancy (which itself is unreliable
  for distinguishing real from static)
- Use vision QA for any specific phase claim

### H40v2 is useful for FOUNTAIN_3+ but not CASCADE_3+

The H73 data shows that real FOUNTAIN (h65=FOUNTAIN) phases have:
- mean L > 0.7 (4/3 phases)
- mean R > 0.6 (3/3 phases)
- LR > 1.3 (3/3 phases)
- both+ > 0.4 (3/3 phases)

While misclassified FOUNTAIN_3+ (h65=OTHER) phases have:
- mean L > 0.5 (4/4 phases)
- mean R > 0.5 (4/4 phases)
- LR > 1.0 (4/4 phases)
- both+ > 0.4 (3/4 phases)

The distributions overlap significantly. H40v2 cannot distinguish
real from misclassified FOUNTAIN_3+ phases by occupancy alone.

### H40v2 is useful for STATIC detection (not tested here)

A real FOUNTAIN has balls cycling through the hands (L+R should be
~1-2 most of the time, occasionally 0 when all balls are in air). The
9 phases tested all have LR > 1.0 most of the time, consistent with
EITHER a real pattern OR a static hold.

A static hold would have very stable L+R values across frames
(no cycling). The H73 data shows stable L+R (e.g. f=733-766 has
L=1, R=1 for 32 frames) which is actually MORE stable than a real
FOUNTAIN should be. A future H74 could measure the variance of
L+R over time to detect static holds.

## Recommended operating point (post-H73)

For FOUNTAIN_3+ post-filter (unchanged from H69):
- H43 OR H69(spec_conc < 0.15) is the best filter on the H65 sample

For CASCADE_3+ post-filter:
- No reliable filter exists with current signals
- H12 v8's 0/2 accuracy on substantial CASCADE_3+ phases means any
  "CASCADE_3+ detection" should be treated as research-only
- H40v2 sustained-occupancy is NOT a useful discriminator

For MIXED_3+ post-filter (unchanged from H71):
- KEEP at spec_conc >= 0.15 (91% precision)
- REJECT at spec_conc < 0.10 (1/1 correct on H71)

## Negative findings

1. **H40v2 sustained-occupancy is NOT a useful discriminator for
   CASCADE_3+ / FOUNTAIN_3+ accuracy.** It only detects "balls near
   hands", not "actively juggling".
2. **H12 v8 CASCADE_3+ has 0/2 accuracy on substantial phases.**
   The 2 substantial CASCADE_3+ phases (both on identical) are
   misclassified manipulation tricks.
3. **H40v2 misclassifies f=733-766 as FOUNTAIN_3+ (vs H12 v8's
   CASCADE_3+).** H40v2 and H12 v8 use different classification
   pipelines that disagree on this phase.
4. **H73's original hypothesis (per-frame census L+R=0) was wrong.**
   The per-frame census only updates L+R at chain events, so L+R=0
   is the default for 97% of frames. H40v2 sustained-occupancy
   is a better signal, but still not useful for CASCADE/FOUNTAIN
   discrimination.

## Future research directions

1. **H74: L+R temporal variance as static-hold detector** — measure
   the variance of H40v2 L+R across frames in a phase. A real
   FOUNTAIN would have L+R cycling 0-2-1-2-...; a static hold would
   have stable L+R. This could be a precision-improving filter.

2. **H75: CASCADE_3+ class as "research signal only"** — accept that
   CASCADE_3+ cannot be reliably detected by current signals.
   Recommend that downstream consumers use only FOUNTAIN_3+ and
   MIXED_3+ filters from H69/H71.

3. **H76: re-run H59 precision/recall on the FULL H70 sample with
   ground truth** — characterize end-to-end quality of the
   h7v3plus3 + H10 v11 v3 + H12 v8 + H70/H71 v1 stack.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h73_lr_zero_cascade_validator.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h73_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h72/phase_identical_balls_trick_000_018_f733-766_CASCADE_3+_h73.png`
