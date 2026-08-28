# H98 — Investigate H90 NEW generalization to MIXED_3+ and CASCADE_3+

**Date:** 2026-08-29 ~00:30 CEST
**Question:** H90 NEW (c40g3<0.40 AND c40.max_aloft>=4) currently
applies to FOUNTAIN_3+ only in the H96 v2 stack. Does it generalize
to MIXED_3+ / CASCADE_3+ without false-rejecting real juggling? And
if not, can it be combined with other signals to catch more of the
3 remaining H93 misclassifications (f=685-716, f=890-936, f=2-71)?

## Background

The H96 v2 stack achieves PERFECT 17/4/0/0 on the 21 H93 corrected
phases. The 4 TN (correctly rejected misclassifications) are:
- f=482-594 YouTube FOUNTAIN_3+ STATIC_HOLD (caught by H90 NEW)
- f=890-936 identical FOUNTAIN_3+ OTHER_CROSSED_ARM Mills Mess (caught by H78)
- f=685-716 identical CASCADE_3+ STATIC_HOLD (caught by H87+max_aloft)
- f=2-71 YouTube MIXED_3+_UNCONFIRMED STATIC_HOLD startup (caught by H71)

H90 NEW is currently FOUNTAIN_3+ only. The question: would applying
H90 NEW universally help?

## Method

1. Compute c4 (conf >= 0.4) aloft features for all 21 H93 phases
2. Report which phases have c40g3<0.40 AND c40.max_aloft>=4
3. For each pattern (FOUNTAIN_3+, MIXED_3+, CASCADE_3+), report the
   would-be firing rate
4. Apply universal H90 NEW with c40g3_thr sensitivity grid
5. Determine if any real juggling would be wrongly rejected

## Per-phase c4 aloft features (all 21 H93 phases)

```
phase                          pattern            verdict               c40g3 c40mx  H90NEW
ident f=263-312                MIXED_3+           JUGGLING              0.05     3   False
ident f=411-450                MIXED_3+           JUGGLING              0.05     3   False
ident f=549-578                MIXED_3+           JUGGLING              0.00     2   False
ident f=631-669                FOUNTAIN_3+        JUGGLING              0.21     3   False
ident f=685-716                CASCADE_3+         STATIC_HOLD           0.08     3   False
ident f=733-766                CASCADE_3+         JUGGLING              0.00     1   False
ident f=890-936                FOUNTAIN_3+        OTHER_CROSSED_ARM     0.10     3   False
ident f=977-1011               FOUNTAIN_3+        JUGGLING              0.03     3   False
ident f=1029-1049              FOUNTAIN_3+        JUGGLING              0.00     2   False
youtu f=2-71                   MIXED_3+_UNCONFIRMED STATIC_HOLD          0.36     3   False
youtu f=114-255                MIXED_3+           JUGGLING              0.37     3   False
youtu f=267-298                MIXED_3+           JUGGLING              0.47     3   False
youtu f=308-338                MIXED_3+           JUGGLING              0.32     3   False
youtu f=339-374                FOUNTAIN_3+        JUGGLING              0.44     3   False
youtu f=375-410                MIXED_3+           JUGGLING              0.34     3   False
youtu f=420-481                MIXED_3+           JUGGLING              0.39     3   False
youtu f=482-594                FOUNTAIN_3+        STATIC_HOLD           0.36     4    True
youtu f=595-643                MIXED_3+           JUGGLING              0.33     3   False
youtu f=769-799                MIXED_3+           JUGGLING              0.38     3   False
youtu f=800-861                FOUNTAIN_3+        JUGGLING              0.25     3   False
youtu f=862-899                MIXED_3+           JUGGLING              0.41     3   False
```

**Key finding:** ONLY f=482-594 (FOUNTAIN_3+ STATIC_HOLD) has
c40g3<0.40 AND c40.max_aloft>=4. The H90 NEW signal is FOUNTAIN_3+-
specific by data, not by rule.

## Per-pattern H90 NEW firing analysis

```
pattern           TP   TN   FP   FN
FOUNTAIN_3+        5    1    1    0
MIXED_3+          11    0    1    0
CASCADE_3+         1    0    1    0
```

- FOUNTAIN_3+: 1 of 7 phases has H90 NEW firing (1 TN, 0 FN).
- MIXED_3+: 0 of 12 phases have H90 NEW firing. **No real juggling
  would be wrongly rejected.**
- CASCADE_3+: 0 of 2 phases have H90 NEW firing. **No real juggling
  would be wrongly rejected.**

The MIXED_3+ f=2-71 (c40g3=0.36) is below 0.40 but has c40.max_aloft=3
(not >=4), so H90 NEW doesn't fire.

## Universal H90 NEW sensitivity grid (apply to all patterns)

```
c40g3<0.3:  TP=17 TN=0 FP=4 FN=0 P=0.810 R=1.000 acc=0.810
c40g3<0.35: TP=17 TN=0 FP=4 FN=0 P=0.810 R=1.000 acc=0.810
c40g3<0.4:  TP=17 TN=1 FP=3 FN=0 P=0.850 R=1.000 acc=0.857
c40g3<0.45: TP=17 TN=1 FP=3 FN=0 P=0.850 R=1.000 acc=0.857
c40g3<0.5:  TP=17 TN=1 FP=3 FN=0 P=0.850 R=1.000 acc=0.857
c40g3<0.55: TP=17 TN=1 FP=3 FN=0 P=0.850 R=1.000 acc=0.857
c40g3<0.6:  TP=17 TN=1 FP=3 FN=0 P=0.850 R=1.000 acc=0.857
```

**Universal H90 NEW alone (without H87/H74) catches only 1 of 4
misclassifications** (f=482-594). The 3 remaining misclassifications
(f=685-716, f=890-936, f=2-71) have c40.max_aloft < 4, so H90 NEW
alone can't catch them.

**Wide flat region** (c40g3 ∈ [0.40, 0.60]) all give TP=17 TN=1 FP=3
FN=0 (no real juggling wrongly rejected). The universal application
is SAFE but doesn't help.

## Verdict: NEGATIVE — H90 NEW is FOUNTAIN_3+-specific

The H90 NEW signal (c40g3<0.40 AND c40.max_aloft>=4) is FOUNTAIN_3+-
specific by data, not by rule. Universal application would not
catch the 3 remaining misclassifications (f=685-716, f=890-936,
f=2-71) because their c40.max_aloft < 4.

**The H96 v2 stack is already optimal:**
- f=482-594 (FOUNTAIN_3+): caught by H90 NEW
- f=890-936 (FOUNTAIN_3+ OTHER_CROSSED_ARM): caught by H78 mean_diff>10
- f=685-716 (CASCADE_3+): caught by H87+max_aloft (pct_ge3=0.16<0.20 AND max_aloft=4)
- f=2-71 (MIXED_3+_UNCONFIRMED): caught by H71 (spec_conc=0.075<0.10)

Each of the 4 misclassifications is caught by a DIFFERENT signal
specific to its pattern. H90 NEW only contributes to FOUNTAIN_3+
and is correctly restricted to that pattern.

## Negative findings

- **H90 NEW universal application has 0 new TNs and 0 new FNs on
  the H93 sample.** The 3 remaining misclassifications have
  c40.max_aloft < 4, which H90 NEW explicitly excludes.
- **The H93 sample is too small to validate universal H90 NEW.**
  12 MIXED_3+ phases and 2 CASCADE_3+ phases. A 3rd video with
  more CASCADE_3+ and MIXED_3+ phases would be needed to test
  whether the universal restriction is truly safe.
- **f=685-716 (CASCADE_3+ STATIC_HOLD) has c40.max_aloft=3, not
  4.** H87+max_aloft>=2 (catches it) is the right signal for
  CASCADE_3+, not H90 NEW.
- **f=2-71 (MIXED_3+_UNCONFIRMED startup) has c40g3=0.36 (low)
  but c40.max_aloft=3 (not 4).** H71 (spec_conc=0.075<0.10) is
  the right signal for MIXED_3+ startup, not H90 NEW.

## Future research directions (post-H98)

1. **H99: 3rd video for H90 NEW universal validation.** A juggling
   video with more CASCADE_3+ / MIXED_3+ phases would characterize
   whether H90 NEW's FOUNTAIN_3+ specificity is a sample artifact
   or a real signal property.
2. **Stop here.** The H96 v2 stack achieves PERFECT 21-phase
   accuracy with a wide flat region. The 113 review pair metrics
   are P=0.979, R=0.648, FPR=0.024. The (CONF or UNCER) gate
   achieves P=1.000 on 33/33 pairs. Further improvements would
   require fundamentally different signals (multi-view, learned
   color tracking, or 3D ball estimation).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h98_h90_new_generalization.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h98_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h98_report.md`
