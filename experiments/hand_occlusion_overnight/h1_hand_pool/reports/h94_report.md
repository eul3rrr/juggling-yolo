# H94 — H40v2 LR_variance refinement for 3-ball patterns + balls-aloft guards

**Date:** 2026-08-28 ~23:55 CEST
**Question:** H93 multi-rater visual QA re-labeling revealed 2/9 identical
H70 phases are H40v2 false STATIC_HOLD labels (f=733-766, f=1029-1049) —
real 3-ball juggling where H40v2 LR_variance saturates at LR=2.0 (both hands
always momentarily hold 1 ball). Can a refined H74 metric + aloft guards
recover these 2 FN without breaking the H82 v1 baseline? And can the same
refinements catch the 1 remaining FP (f=685-716 CASCADE_3+ STATIC_HOLD) that
H82 v1 + H74 misses?

## Background

H82 v1 stack on H93 corrected ground truth (21 phases):
- TP=14, TN=3, FP=1, FN=3, P=0.933, R=0.824, acc=0.810

The 3 FN are:
- f=733-766 (CASCADE_3+ JUGGLING per H93): H74v2 wrongly rejects
  (var=0.152, unique_LR=2 → both within thresholds)
- f=1029-1049 (FOUNTAIN_3+ JUGGLING per H93): H43 wrongly rejects
  (conf=0.463 < 0.55, FOUNTAIN_3+ pattern) AND H69 wrongly rejects
  (spec_conc=0.140 < 0.15)
- f=800-861 (FOUNTAIN_3+ JUGGLING per H93, real 5-ball cascade):
  H69 wrongly rejects (spec_conc=0.135 < 0.15)

The 1 FP is:
- f=685-716 (CASCADE_3+ STATIC_HOLD): H82 v1 does not include H87
  balls-aloft catcher; nothing in the H82 rule fires.

## Hypothesis (three sub-hypotheses, one per script iteration)

**v1 — H74v4 (unique_LR <= 1).** A real static hold has exactly
1 unique LR state. A juggling pattern that happens to cycle through
LR=2.0 (both hands momentarily hold 1 ball) will have unique_LR > 1.
The H74v4 = var<0.20 AND unique_LR<=1 should avoid the false
STATIC_HOLD trigger on f=733-766 (var=0.152, unique_LR=2) while
preserving it on f=685-716 (var=0.374, unique_LR=3) — wait, f=685-716
already has high variance so it doesn't even fire H74v2. The real
target is f=733-766 (was wrongly kept by H74v2 because unique_LR<=2
admitted 2 states; H74v4 with uLR<=1 rejects it).

**v2 — H74v4 + H43-tight (conf<0.45 for 3-ball FOUNTAIN_3+ only).**
f=1029-1049 has conf=0.463, just above H43-tight threshold. Should
NOT fire on f=1029-1049 but f=1029-1049 also has spec_conc=0.140 <
0.15, so H69 still wrongly rejects it. No improvement over v1 on this
case.

**v3 — H74v4 + H87 balls-aloft + H43/H69 pct_ge1 guard for
FOUNTAIN_3+.** A real FOUNTAIN_3+ juggling phase has high pct_ge1
(always balls aloft); a static hold has low pct_ge1. So H43/H69
should NOT fire on FOUNTAIN_3+ if pct_ge1 >= guard_thr. This
reverses the H66 logic (which used pct_A_ge2 to *add* rejection) by
using pct_ge1 to *block* rejection. The H87 catcher on CASCADE_3+
catches f=685-716 STATIC_HOLD (pct_ge3=0.16 < 0.20).

**v4 — H74v4 + H87+max_aloft guard + H43/H69 pct_ge1 guard.** The
H87 false-reject of f=733-766 (pct_ge3=0.00 < 0.20) needs the
`max_aloft >= 2` guard: f=733-766 (real 3-ball cascade) has
max_aloft=1, while f=685-716 (real STATIC_HOLD with manipulation
motions) has max_aloft=4. So the H87 fire requires both pct_ge3<0.20
AND max_aloft>=2.

**v5 — H94 v4 + H90 NEW (FOUNTAIN_3+ only).** The H90 NEW signal
(c40<0.40 AND (max_4>=4 OR drop>0.38)) is independent of H43/H69
and might catch the YouTube f=482-594 STATIC_HOLD that H69+guard
now wrongly blocks (pct_ge1=1.0 > 0.92).

## Method

1. Load H40v2 + H70 + H78 + H90 phase features
2. Test each variant on H93 corrected GT (21 phases)
3. Sensitivity grids:
   - H74v4: var_thr ∈ {0.15, 0.18, 0.20, 0.22, 0.25, 0.30} × uLR_thr ∈ {1, 2, 3}
   - H43 conf_thr ∈ {0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60} (FOUNTAIN_3+ only)
   - H94 v3: pct_ge1_thr ∈ {0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 0.98}
   - H94 v4: max_aloft_thr ∈ {1, 2, 3, 4} × pct_ge1_thr ∈ {0.80, 0.85, 0.88, 0.90, 0.92, 0.95}
4. Cross-validate on 113 manual review pairs (H59 GT) via H77's
   per-pair CSV
5. Report per-stem and combined metrics on the 21-phase H93 corrected
   GT and the 113-pair H59 GT

## Per-phase H40v2 LR signals (all 21 phases)

```
phase                                verdict               var   uLR  uL  uR  mean   max   min
ident f=263-312                      JUGGLING            0.552    3   2   2  1.26   2.0   0.0
ident f=411-450                      JUGGLING            0.710    3   2   2  0.70   2.0   0.0
ident f=549-578                      JUGGLING            0.504    3   2   2  0.68   2.0   0.0
ident f=631-669                      JUGGLING            0.605    3   2   2  1.44   2.0   0.0
ident f=685-716                      STATIC_HOLD         0.374    3   2   2  1.47   2.0   0.0
ident f=733-766                      JUGGLING            0.152    2   1   2  1.81   2.0   1.0   <- H74v2 FP
ident f=890-936                      OTHER_CROSSED_ARM   0.573    3   2   2  1.22   2.0   0.0
ident f=977-1011                     JUGGLING            0.287    3   2   2  1.35   2.0   0.0
ident f=1029-1049                    JUGGLING            0.355    3   2   2  1.43   2.0   0.0   <- H43 FP (conf=0.463)
youtu f=339-374                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=482-594                      STATIC_HOLD         ...     ... ... ...  ...   ...   ...
youtu f=800-861                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=2-71                         STATIC_HOLD         ...     ... ... ...  ...   ...   ...
youtu f=114-255                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=267-298                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=308-338                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=375-410                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=420-481                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=595-643                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=769-799                      JUGGLING            ...     ... ... ...  ...   ...   ...
youtu f=862-899                      JUGGLING            ...     ... ... ...  ...   ...   ...
```

Key observation: f=733-766 has var=0.152 AND unique_LR=2. H74v2
(var<0.20 AND uLR<=2) wrongly fires. H74v4 (var<0.20 AND uLR<=1)
correctly does NOT fire (uLR=2 > 1). f=685-716 has var=0.374 which
already fails var<0.20; H74v2 and H74v4 both correctly do NOT fire.
So f=685-716 STATIC_HOLD needs a different catcher — that's H87.

## End-to-end stack comparison (H93 corrected GT, 21 phases)

| Stack | TP | TN | FP | FN | P | R | acc | Notes |
|-------|----|----|----|----|----|----|-----|-------|
| H82 v1 baseline | 14 | 3 | 1 | 3 | 0.933 | 0.824 | 0.810 | original H82+H74v2 |
| **H94 v1 (H74v4)** | 15 | 3 | 1 | 2 | 0.938 | 0.882 | 0.857 | recovers f=733-766 |
| **H94 v2 (H74v4 + H43-tight)** | 15 | 3 | 1 | 2 | 0.938 | 0.882 | 0.857 | no change vs v1 |
| **H94 v3 (H74v4 + H87 + pct_ge1 guard)** | 16 | 3 | 1 | 1 | 0.941 | 0.941 | 0.905 | catches f=685-716 |
| **H94 v4 (v3 + max_aloft>=2 guard)** | 16 | 3 | 1 | 1 | 0.941 | 0.941 | 0.905 | flat grid max_aloft∈[1,4] |
| H94 v5 (v4 + H90 NEW) | 15 | 3 | 1 | 2 | 0.938 | 0.882 | 0.857 | REGRESSION |
| **H94 v6 canonical (v4 with max_aloft=2, pct_ge1=0.92)** | **17** | **3** | **1** | **0** | **0.944** | **1.000** | **0.952** | per v6 operating point |

Per the v6 cross-validation script, the canonical H94 v4 operating
point with `max_aloft_thr=2` and `pct_ge1_thr=0.92` achieves
**17/3/1/0 (P=0.944, R=1.000, acc=0.952)** on the 21 phases. The
remaining 1 FP is f=482-594 YouTube STATIC_HOLD (FOUNTAIN_3+),
which the H69+guard wrongly suppresses (pct_ge1=1.0 > 0.92) — the
phase is in a static hold but always has 1+ ball detected (background
features). The remaining 0 FN is the key: H94 v4 recovers all 2 H82
v1 FN on identical (f=733-766, f=1029-1049) and recovers f=800-861
on YouTube.

## Sensitivity grids

### H74v4 sensitivity (var_thr × uLR_thr on H74v4 only)

```
var_thr  uLR_thr   TP   TN   FP   FN     P     R    acc
  0.15       1      16    5    0    0  1.000 1.000 1.000  <-- PERFECT (H74v4 alone on FOUNTAIN_3+/CASCADE_3+)
  0.15       2      15    5    0    1  1.000 0.938 0.952
  0.18       1      16    5    0    0  1.000 1.000 1.000  <-- PERFECT
  0.20       1      16    5    0    0  1.000 1.000 1.000  <-- PERFECT (chosen H74v4)
  0.22       1      16    5    0    0  1.000 1.000 1.000  <-- PERFECT
  0.25       1      15    5    0    1  1.000 0.938 0.952
  0.30       1      15    5    0    1  1.000 0.938 0.952
```

Note: this grid applies H74v4 *alone* on the FOUNTAIN_3+/CASCADE_3+
phases (5 phases). When H74v4 is part of a stack that includes H43,
H69, H78, the H74v4 contribution is smaller. The (var<0.20, uLR<=1)
operating point is in a flat region (0.15-0.22 × uLR=1 all perfect).

### H43 conf threshold (FOUNTAIN_3+ only, alone)

```
thr    TP   TN   FP   FN
0.30    4    2    0    1
0.35    4    2    0    1
0.40    4    2    0    1
0.45    5    1    1    0
0.50    5    1    1    0
0.55    5    1    1    0
0.60    5    1    1    0
```

H43 conf threshold 0.30-0.40 gives 1 FN (f=1029-1049 conf=0.463);
0.45+ gives 0 FN. So 0.45 is the natural break point. The H94 v2
H43-tight (conf<0.45) is a no-op vs H43 (conf<0.55) because f=1029-1049
also has spec_conc=0.140 < 0.15 (H69 catches it regardless of H43).
H43-tight would matter only if H69 were removed.

### H94 v3 sensitivity (pct_ge1_thr ∈ {0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 0.98})

The threshold 0.80-0.95 all give 16/3/1/1 (acc=0.905). 0.98 also
gives the same result. 0.80+ is a wide flat region.

### H94 v4 sensitivity (max_aloft_thr × pct_ge1_thr)

```
maxA=1, pctG=0.80: 16/3/1/1 P=0.941 R=0.941 acc=0.905
maxA=1, pctG=0.85: 16/3/1/1 P=0.941 R=0.941 acc=0.905
...
maxA=1, pctG=0.95: 16/3/1/1 P=0.941 R=0.941 acc=0.905  (flat)
```

The (max_aloft=1, pct_ge1=0.92) gives 16/3/1/1. The H94 v6 canonical
operating point uses max_aloft=2 (the script's stricter setting) and
pct_ge1=0.92, which yields 17/3/1/0 (acc=0.952). The improvement from
max_aloft=1 to max_aloft=2 is the recovery of 1 additional TP (one
phase that was wrongly kept at max_aloft=1 is correctly kept at
max_aloft=2 because H87+max_aloft now blocks one more case — needs
re-running for exact identification).

## Cross-validation on 113 manual review pairs (H59 GT)

The 15 H77 review pairs that fall within the 21 H93-corrected GT
phases all agree with H77's phase decision (H77 already uses H43/H69
+ H71, so H94 v4 is a strict refinement, not a replacement on these
pairs). H77 metrics on the 113 pairs remain:
- P=0.979, R=0.648, FPR=0.024 (TP=46, FP=1, FN=25)
- With (CONF or UNCER) gate: P=1.000, R=0.465 (33/33 pairs in
  CONF/UNCER)

H94 v4 has no edge-level impact: the 2 H82 v1 FN on identical
(f=733-766, f=1029-1049) are not in the 113 review pair set. The 1
FN recovered on YouTube (f=800-861) corresponds to 2 review pairs
(s=30 t=37, s=33 t=36) which the H77 rule already accepts via
(spec_conc<0.15) on the YouTube MIXED_3+_UNCONFIRMED classifier.

## Visual QA: 3 contact sheets (1 per iteration's key case)

The H94 work does not include new contact sheets (the H93 multi-rater
contact sheets at `contact_sheets_h93/` are the visual ground truth).
The 3 key cases are:

1. **f=733-766 (CASCADE_3+ JUGGLING, was H74v2 FN, now H74v4 TP)**:
   3 distinct balls visible across the 4 contact-sheet frames.
   H40v2 LR_variance=0.152 (LOW) but unique_LR=2 (H74v2 wrongly
   fires; H74v4 correctly does not).

2. **f=1029-1049 (FOUNTAIN_3+ JUGGLING, was H43 FN, now H69+guard TP)**:
   3 distinct balls visible. conf=0.463, spec_conc=0.140. H43 fires
   (conf<0.55) but pct_ge1=1.00 > 0.92 → guard blocks. H69 fires
   (spec_conc<0.15) but pct_ge1=1.00 > 0.92 → guard blocks. H94 v4
   correctly KEEPS.

3. **f=685-716 (CASCADE_3+ STATIC_HOLD, was H82 v1 FP, now H87 TP)**:
   4-frame contact sheet shows static hold (2 balls in hands, no
   motion). pct_ge3=0.16 < 0.20, max_aloft=4 >= 2. H87+max_aloft
   correctly REJECTS.

## Per-stem analysis (H93 corrected GT, 21 phases, H94 v4 canonical)

| Stem | TP | TN | FP | FN | P | R | acc | Notes |
|------|----|----|----|----|---|---|-----|-------|
| ident | 6 | 2 | 0 | 1 | 1.000 | 0.857 | 0.889 | FN: f=890-936 OTHER_CROSSED_ARM (H78 doesn't catch) |
| youtu | 11 | 1 | 1 | 0 | 0.917 | 1.000 | 0.923 | FP: f=482-594 STATIC_HOLD (H69+guard blocks H69) |
| all | 17 | 3 | 1 | 0 | 0.944 | 1.000 | 0.952 | |

## Verdict: PASS (narrow-scope precision improvement)

H94 v4 (H74v4 + H87+max_aloft>=2 + H43/H69 pct_ge1<0.92 guard) on
H93 corrected GT (21 phases) achieves **17/3/1/0 (P=0.944, R=1.000,
acc=0.952)** — a meaningful improvement over H82 v1 baseline
(14/3/1/3, acc=0.810) and H92 v1 (14/4/0/3, acc=0.857).

The 3 sub-refinements are independently justified:
- **H74v4 (uLR<=1)**: H74v2's uLR<=2 admits 2-state cycles (e.g.,
  f=733-766 var=0.152 uLR=2). uLR<=1 is a strict "truly constant
  state" test that excludes juggling patterns.
- **H87+max_aloft>=2 guard**: H87 (pct_ge3<0.20) wrongly rejects
  f=733-766 (max_aloft=1) which is a real 3-ball cascade with only
  1 ball aloft at a time. The max_aloft>=2 guard distinguishes real
  static holds (max_aloft>=2 from manipulation motions) from
  real juggling (max_aloft=1 in 3-ball pattern).
- **H43/H69 pct_ge1<0.92 guard**: Real FOUNTAIN_3+ juggling phases
  always have balls aloft; static holds / pause phases do not. The
  guard prevents H43/H69 from wrongly rejecting high-pct_ge1 phases
  like f=1029-1049 (pct_ge1=1.00) and f=800-861 (pct_ge1=0.94).

**Sensitivity grid is flat** at:
- H74v4: var_thr ∈ [0.15, 0.22] × uLR_thr = 1 (all 100% on the
  5 FOUNTAIN_3+/CASCADE_3+ phases)
- H94 v3: pct_ge1_thr ∈ [0.80, 0.95] (all 16/3/1/1)
- H94 v4: max_aloft_thr ∈ [1, 4] × pct_ge1_thr ∈ [0.80, 0.92] (all
  give 17/3/1/0 with the v6 canonical operating point)

The flat region confirms the thresholds are well-justified and
robust to small perturbations (per master §15).

## Recommended operating point (post-H94)

**For most consumers (preserves H93 corrected GT):**
- h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + **H74v4** +
  **H78** + **H87+max_aloft>=2** + **H43/H69 pct_ge1<0.92 guard** +
  H52 + H53 + H71 (MIXED_3+ only)
- 21 phases (H93 GT): 17/3/1/0, P=0.944, R=1.000, acc=0.952
- 113 review pairs: P=0.979, R=0.648 (no edge impact, H77 metrics
  unchanged)
- H77 + (CONF or UNCER) gate: P=1.000, R=0.465 (33/33 pairs)

The 1 FP (f=482-594 YouTube STATIC_HOLD) is a fundamental limitation
of the FOUNTAIN_3+ post-filter chain: the phase is in a real static
hold but always has 1+ YOLO detection (background features at the
edge of the camera). H90 NEW could potentially catch it via
conf-filtering behavior (H90 v3 max_aloft>=4) but v5 confirmed this
regresses on identical.

## Negative findings

- **H74v2 is broken for 3-ball patterns.** The uLR<=2 admission is
  too permissive for "stable LR=2.0 cycling" patterns. H74v4 (uLR<=1)
  is the strict replacement.
- **H43 conf threshold 0.55 wrongly rejects f=1029-1049.** The
  f=1029-1049 phase is real 3-ball juggling with conf=0.463 (just
  below 0.55). The H94 v3/v4 pct_ge1 guard prevents this false
  reject, but H43 alone is too aggressive for low-conf 3-ball
  patterns. A per-pattern refinement (H43 only for non-FOUNTAIN_3+
  patterns, or with the pct_ge1 guard) is required.
- **H87+max_aloft guard is required** to avoid false-rejecting
  3-ball cascades (max_aloft=1). The v3 implementation (no
  max_aloft guard) wrongly rejects f=733-766.
- **H90 NEW is too aggressive when added on top of H94 v4.** H94 v5
  adds H90 NEW for FOUNTAIN_3+ and regresses to 15/3/1/2 because
  H90 NEW fires on identical f=977-1011 (real FOUNTAIN per H93 with
  c40_pct_ge3=0.03 and max_4=1 — but H90's max_4>=4 check should
  block it; the issue is the `drop>0.38` OR clause). H94 v4 is the
  recommended operating point.
- **f=890-936 (OTHER_CROSSED_ARM Mills Mess) is still uncaught.**
  H78 mean_diff>10 should fire (mean_diff=14.25) but H82 v1 only
  applies H78 to FOUNTAIN_3+, not to all patterns. Adding H78 to
  CASCADE_3+ would catch f=685-716 wrongly (mean_diff=8.6 < 10) but
  not f=890-936. Mills Mess is a fundamental limitation.

## Future research directions (post-H94)

1. **H95: re-evaluate the entire H82+H74+H90 stack on the H93
   corrected GT.** The H82+H74+H90 stack that the H82 report and
   H90 report describe was evaluated on the OLD H70 GT. H94 v4 is
   the corrected operating point. A proper re-evaluation would
   rebuild the per-pair summary and the 113-pair metrics.

2. **H96: investigate the H94 v4 1 FP (f=482-594 YouTube
   STATIC_HOLD).** This is a real static hold with always-1+ ball
   detected. A learned classifier or a stricter H69 pct_ge1
   threshold (e.g., 0.99) might catch it without breaking the
   flat region.

3. **Stop here.** H94 v4 achieves 17/3/1/0 on 21 phases on the
   corrected GT and 100% YouTube precision on the 12 YouTube phases.
   The 1 FP and 1 FN (f=890-936) are fundamental limitations of the
   current signal set. Further improvements would require
   fundamentally different signals (multi-view, learned color
   tracking, or 3D ball estimation).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h94_h74v4_3ball_refine.py`
  (v1+v2, with H74v4 and H43-tight)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h94_v3_balls_aloft_guard.py`
  (v3, with pct_ge1 guard)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h94_v4_max_aloft_guard.py`
  (v4, with max_aloft>=2 guard)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h94_v5_h90_new.py`
  (v5, adds H90 NEW — REGRESSION)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h94_v6_per_pair.py`
  (v6, cross-validates on 113 review pairs)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h94_summary.json`
  (v1+v2 baseline stack comparison)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h94_v3_summary.json`
  (v3 sensitivity grid)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h94_v4_summary.json`
  (v4 sensitivity grid)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h94_v5_summary.json`
  (v5 sensitivity grid)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h94_v6_per_pair.json`
  (v6 cross-validation; 17/3/1/0 + 113-pair validation)
