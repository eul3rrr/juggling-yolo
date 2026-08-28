# H103 — H12 v8 vs H93 phase verdict cross-tabulation

**Date:** 2026-08-29 (continuation episode)
**Status:** Consumer-pass (quantitative measurement, no new operating point)

## Hypothesis

H12 v8's per-frame pattern classifier over-classifies H93 STATIC_HOLD /
OTHER_CROSSED_ARM phases as active patterns (FOUNTAIN_3+ / CASCADE_3+ /
MIXED_3+). The H102 finding (3 of 5 phase-vs-review disagreements are in
H93 STATIC_HOLD phases that H12 v8 calls FOUNTAIN_3+) suggests this is
systematic, not coincidental.

## Method

For each of the 21 H93 corrected phases, load H67 per-frame data
(H12 v8 baseline + H43/H66/H67 reject flags) and compute the
within-phase H12 v8 pattern distribution. Identify the 3 STATIC_HOLD
phases (or similar) that H12 v8 over-classifies.

This is a small, isolated consumer-pass experiment that uses existing
per-frame data (no new runs).

## Quantitative result

Cross-tabulation of H93 phase verdict × H12 v8 dominant pattern
(21 phases):

| H93 verdict | MIXED_3+ | FOUNTAIN_3+ | CASCADE_3+ | FOUNTAIN_LOW_CONF | MIXED_3+_UNCONFIRMED | total |
|-------------|---------:|------------:|-----------:|------------------:|---------------------:|------:|
| JUGGLING         | 11 | 3 | 1 | 2 | 0 | 17 |
| STATIC_HOLD      |  0 | 1 | 1 | 0 | 1 |  3 |
| OTHER_CROSSED_ARM|  0 | 1 | 0 | 0 | 0 |  1 |

**3/3 STATIC_HOLD phases and 1/1 OTHER_CROSSED_ARM phase are
over-classified by H12 v8 as active patterns.** The over-classification
rate is essentially 100% — every H93 STATIC/OTHER phase has H12 v8
calling it an active juggling pattern.

## Per-phase H12 v8 over-classification

| Phase | H93 verdict | H12 v8 dominant | H12 v8 confidence | Notes |
|-------|-------------|-----------------|-------------------|-------|
| identical 685-716 | STATIC_HOLD    | CASCADE_3+  | 0.569 | manipulation trick (body rolls / contact juggling) |
| identical 890-936 | OTHER_CROSSED_ARM | FOUNTAIN_3+ | 0.571 | Mills Mess / crossed-arm trick |
| youtube 2-71     | STATIC_HOLD    | MIXED_3+_UNCONFIRMED | 0.333 | static demo / setup |
| youtube 482-594  | STATIC_HOLD    | FOUNTAIN_3+ | 0.653 | static hold with embedded hand-handoffs (H102) |

The H102 finding extends: ALL 4 H93 non-juggling phases are
over-classified by H12 v8. The 2 f=977-1011 and f=1029-1049 identical
"FOUNTAIN_LOW_CONF" labels are H12 v8 + H43 reject (H93 re-classified
both as JUGGLING), so they're real juggling, not over-classification.

## Interpretation

H12 v8's K=4 sliding window classifier interprets:
- 1+ recent chain event (catch or throw) as evidence of active juggling
- A high conf FOUNTAIN_3+ label fires even when the underlying pattern
  is a static hold with embedded hand-handoffs (f=482-594)
- A high conf CASCADE_3+ label fires when the pattern is a
  contact-juggling pose with body rolls (f=685-716)
- A high conf FOUNTAIN_3+ label fires when the pattern is a Mills
  Mess / crossed-arm trick (f=890-936)

The K=4 sliding window does NOT distinguish "many events in a short
window" (active juggling) from "few events in a long window" (hand-handoff
during static hold or trick). H12 v8's pattern labels therefore cannot
be used directly to discriminate juggling from non-juggling at the
phase level — this is exactly why the H43+H69+H74+H78+H87+H90 stack
exists.

## Negative finding

H12 v8's per-frame pattern distribution alone is NOT a sufficient
discriminator for "is this phase juggling?". The H93 multi-rater QA
required substantial contextual reasoning (L+R sustained occupancy,
wrist-distance signal, aloft ball distribution) to make the
distinction. H12 v8's conf and pattern labels are necessary but not
sufficient.

## Recommended follow-up

A continuous-density H12 v9 hybrid classifier (H104) that requires
N events in M frames (not just 1+ event in K=4 context) could
distinguish "many events in a short window" from "few events in a
long window". This is the most direct fix for the H12 v8
over-classification problem.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h103_h12v8_vs_h93_crosstab.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h103_per_phase.csv` (21 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h103_summary.json`
