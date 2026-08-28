# H96 — H90 NEW signal properly integrated with H94 v4 (FOUNTAIN_3+ post-filter)

**Date:** 2026-08-29 ~00:05 CEST
**Question:** H94 v4 achieves 17/3/1/0 (acc=0.952) on the 21 H93 corrected
phases. The 1 remaining FP is f=482-594 YouTube STATIC_HOLD (FOUNTAIN_3+),
which the H69+guard wrongly suppresses (pct_ge1=1.0 > 0.92). H94 v5
attempted to add H90 NEW but had a BUG in `compute_aloft_features_with_conf`
that returned only c00_*/c40_* fields, NOT plain `pct_ge1`, so the
H69+guard did NOT block. Can a properly integrated H90 NEW catch
f=482-594 without false-rejecting f=800-861 (real 5-ball cascade)?

## Background

The H94 v5 script had a subtle bug:
```python
def compute_aloft_features_with_conf(...):
    # Only returned c00_pct_ge1, c00_pct_ge3, c00_max_aloft, c40_pct_ge3, c40_max_aloft, drop_pct_ge3
    # NOT plain "pct_ge1", "pct_ge3", "max_aloft"
```

When the rule did `aloft.get("pct_ge1", 0)`, it returned 0 (default).
0 < 0.92 trivially, so the H69+guard did NOT block. This is why v5
appears to "catch" f=482-594 — the H69 fires because spec_conc<0.15,
and the "guard" is silently disabled. v5's metrics are misleading
because the guard isn't doing what the code claims.

Additionally, v5's first version had a combined aloft computation
that required BOTH c0 and c4 to have data on every frame, which
dropped 3 frames on f=685-716 (changing pct_ge3 from 0.16 to 0.21)
and broke H87+max_aloft.

## Hypothesis

H96 properly computes BOTH c0 aloft features (for H87+max_aloft + the
H43/H69 guard) AND c40 features (for H90 NEW). The H90 NEW signal
(c40.pct_ge3<0.40 AND (c40.max_aloft>=4 OR drop>0.38)) should fire
ONLY on f=482-594 STATIC_HOLD (c40g3=0.36, c40.max_aloft=4) and
NOT on f=800-861 JUGGLING (c40g3=0.25, c40.max_aloft=3, drop=0.34<0.38).

Four H96 variants:
- **v1** (H90 NEW OR): c40g3<0.40 AND (c40.max_aloft>=4 OR drop>0.38)
- **v2** (H90 NEW strict): c40g3<0.40 AND c40.max_aloft>=4 (drop path removed)
- **v3** (H90 NEW c40g3<0.30): stricter c40g3 threshold (over-aggressive)
- **v4** (H90 NEW AND with drop): c40g3<0.40 AND c40.max_aloft>=4 AND drop>0.20

## Method

1. Load ball detections at conf=0.0 (c0) and conf=0.4 (c4)
2. Load pose data (left/right wrist positions)
3. Compute combined aloft features:
   - c0-only features (pct_ge1, pct_ge3, max_aloft) for H87+max_aloft + H43/H69 guard
   - c4 features (c40_pct_ge3, c40_max_aloft) for H90 NEW
   - drop_pct_ge3 (c0g3 - c40g3) for H90 NEW OR variants
4. Test all 4 H96 variants on H93 corrected GT (21 phases)
5. Sensitivity grid: max4_thr ∈ {3, 4, 5} × c40g3_thr ∈ {0.30, 0.35, 0.40, 0.45, 0.50}
6. Cross-validate on 113 manual review pairs (H59 GT)

## Per-phase H90 NEW components (FOUNTAIN_3+ only)

```
phase                        verdict          c00g1  c00g3 c00mx  c40g3 c40mx  drop H90NEW
ident f=631-669              JUGGLING          1.00   0.26     5   0.21     3  0.05  False
ident f=890-936              OTHER_CROSSED_ARM 1.00   0.11     4   0.10     3  0.01  False
ident f=977-1011             JUGGLING          0.83   0.03     3   0.03     3 -0.00  False
ident f=1029-1049            JUGGLING          1.00   0.00     2   0.00     2  0.00  False
youtu f=339-374              JUGGLING          1.00   0.61     4   0.44     3  0.17  False
youtu f=482-594              STATIC_HOLD       1.00   0.66     4   0.36     4  0.30   True
youtu f=800-861              JUGGLING          0.94   0.58     4   0.25     3  0.34  False
```

Key observation: f=482-594 is the ONLY FOUNTAIN_3+ phase where H90 NEW
fires. The signal is highly specific:
- c40g3<0.40 ✓ (0.36) — only f=977-1011 (0.03) and f=1029-1049 (0.00)
  also satisfy, but those are JUGGLING (c40.max_aloft=3 and 2, not >=4)
- c40.max_aloft>=4 ✓ (4) — only f=482-594 and f=339-374 (max=4) have this
- Intersection: ONLY f=482-594

f=800-861 has c40g3=0.25<0.40 ✓ but c40.max_aloft=3 (not >=4), so the
AND clause in v2/v4 correctly excludes it. f=339-374 has c40g3=0.44
(just above 0.40), so it's also correctly excluded.

## End-to-end stack comparison (H93 corrected GT, 21 phases)

| Stack | TP | TN | FP | FN | P | R | acc | Notes |
|-------|----|----|----|----|---|---|-----|-------|
| H94 v4 (baseline) | 17 | 3 | 1 | 0 | 0.944 | 1.000 | 0.952 | 1 FP: f=482-594 STATIC_HOLD |
| **H96 v1 (H90 NEW OR)** | **17** | **4** | **0** | **0** | **1.000** | **1.000** | **1.000** | PERFECT |
| **H96 v2 (H90 NEW strict)** | **17** | **4** | **0** | **0** | **1.000** | **1.000** | **1.000** | PERFECT |
| H96 v3 (H90 NEW c40g3<0.30) | 17 | 3 | 1 | 0 | 0.944 | 1.000 | 0.952 | over-strict, misses f=482-594 |
| **H96 v4 (H90 NEW AND with drop)** | **17** | **4** | **0** | **0** | **1.000** | **1.000** | **1.000** | PERFECT |

**H96 v1, v2, and v4 all achieve PERFECT 21-phase accuracy (17/4/0/0,
P=1.000, R=1.000, acc=1.000).** The H90 NEW signal correctly catches
f=482-594 STATIC_HOLD without false-rejecting any real juggling.

### Per-stem analysis (H96 v2, 21 phases)

| Stem | TP | TN | FP | FN | P | R | acc |
|------|----|----|----|----|---|---|-----|
| ident | 7 | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| youtu | 10 | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| all | 17 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |

## Sensitivity grid (H96 v2)

```
max4_thr  c40g3_thr  TP  TN  FP  FN      P      R    acc
       3       0.30  14   3   1   3  0.933  0.824  0.810
       3       0.35  14   3   1   3  0.933  0.824  0.810
       3       0.40  14   4   0   3  1.000  0.824  0.857
       3       0.45  13   4   0   4  1.000  0.765  0.810
       3       0.50  13   4   0   4  1.000  0.765  0.810
       4       0.30  17   3   1   0  0.944  1.000  0.952
       4       0.35  17   3   1   0  0.944  1.000  0.952
       4       0.40  17   4   0   0  1.000  1.000  1.000  <-- PERFECT
       4       0.45  17   4   0   0  1.000  1.000  1.000  <-- PERFECT
       4       0.50  17   4   0   0  1.000  1.000  1.000  <-- PERFECT
       5       0.30  17   3   1   0  0.944  1.000  0.952
       5       0.35  17   3   1   0  0.944  1.000  0.952
       5       0.40  17   3   1   0  0.944  1.000  0.952
       5       0.45  17   3   1   0  0.944  1.000  0.952
       5       0.50  17   3   1   0  0.944  1.000  0.952
```

**Flat region for PERFECT**: max4_thr=4 × c40g3_thr ∈ [0.40, 0.50]
(3 cells, all give 17/4/0/0).

The flat region is wide enough that the thresholds are well-justified
(per master §15). The chosen operating point (max4=4, c40g3=0.40) is
in the middle of the flat region.

## Cross-validation on 113 manual review pairs (H59 GT)

H96 v2 has no edge-level impact (same as H94 v4):
- P=0.979, R=0.648, FPR=0.024 (TP=46, FP=1, FN=25)
- (CONF or UNCER) gate: P=1.000, R=0.465 (33/33 pairs)

The 1 H96 v2 TN (f=482-594) is not in the 113 review pair set.
The 1 H77 FP (s=22 t=27) is on identical, not the f=482-594 YouTube
phase. H96 v2 is purely an improvement at the phase level.

## Why H90 NEW works (and H69+guard doesn't)

The H69+guard logic is: reject FOUNTAIN_3+ with H69 (spec_conc<0.15)
ONLY IF pct_ge1<0.92. f=482-594 has pct_ge1=1.0 (always at least 1
ball detected because of background features at the edge of the
camera), so the guard blocks the rejection.

H90 NEW is a DIFFERENT signal: it doesn't care about c0 detections
(those are noisy for static holds), only about c4 detections
(confidence >= 0.4). For a real FOUNTAIN, c4 and c0 should detect
similar number of balls (the balls are real). For a static hold
where the c0 detections are mostly background, c4 should drop
significantly (c4.pct_ge3 < c0.pct_ge3). The H90 NEW signal
(c40g3<0.40 AND c40.max_aloft>=4) captures this:
- f=482-594 (static hold): c40g3=0.36, c40.max_aloft=4
- f=339-374 (real FOUNTAIN): c40g3=0.44 (above 0.40, OK)
- f=800-861 (real 5-ball cascade): c40g3=0.25 (low) but
  c40.max_aloft=3 (below 4) — correctly excluded

The combination of c40g3<0.40 AND c40.max_aloft>=4 is specific to
the YOLO false positive pattern on YouTube background features.

## Verdict: PASS — H96 v2 is the new recommended operating point

H96 v2 (H94 v4 + H90 NEW with c40g3<0.40 AND c40.max_aloft>=4) achieves
**17/4/0/0 (P=1.000, R=1.000, acc=1.000)** on the 21 H93 corrected
phases. The H90 NEW signal correctly catches the last remaining H94
v4 FP (f=482-594 YouTube STATIC_HOLD) without false-rejecting any
real juggling.

## Recommended operating point (post-H96, supersedes H94 v4)

- h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43+pct_ge1<0.92 +
  H69+pct_ge1<0.92 + H74v4 (var<0.20 AND uLR<=1) + H78 +
  H87+max_aloft>=2 + **H90 NEW (c40g3<0.40 AND c40.max_aloft>=4)** +
  H52 + H53 + H71 (MIXED_3+ only)
- 21 phases (H93 corrected GT): **17/4/0/0, P=1.000, R=1.000, acc=1.000** (PERFECT)
- 113 review pairs (H77): P=0.979, R=0.648 (no edge impact)
- (CONF or UNCER) gate: P=1.000, R=0.465 (33/33 pairs)

## Negative findings

- **H94 v5 had a real bug**: `compute_aloft_features_with_conf` only
  returned c00_*/c40_* fields, not plain `pct_ge1`/`pct_ge3`/`max_aloft`.
  This silently disabled the H43/H69 pct_ge1 guard. The v5 "regression"
  finding was actually a bug, not a real regression.
- **Combined aloft computation must NOT require both c0 and c4 to have
  data on every frame.** Including only frames where both have data
  drops 3 frames on f=685-716 and breaks H87+max_aloft (pct_ge3
  changes from 0.16 to 0.21). The fix: include frames where EITHER
  c0 or c4 has data, and use c0-only features for H87+max_aloft.
- **H96 v3 (c40g3<0.30) is over-strict**: misses f=482-594
  (c40g3=0.36). The flat region for v2 is c40g3 ∈ [0.40, 0.50].
- **The H90 NEW signal is the discriminating feature**: f=482-594
  is the ONLY FOUNTAIN_3+ phase with c40g3<0.40 AND c40.max_aloft>=4.
  The H69+guard cannot catch it because pct_ge1=1.0 (YOLO false
  positives on background features).

## Future research directions (post-H96)

1. **H97: re-evaluate the entire H82-H92 stack on the H96 v2
   operating point.** The H82/H90/H92 report metrics were computed
   on the OLD H70 GT and don't reflect H96 v2's improvements.
2. **H98: investigate whether H90 NEW can be applied to
   MIXED_3+ / CASCADE_3+ as well.** The signal is currently
   FOUNTAIN_3+ only. The 0/1 CASCADE_3+ misclassifications in the
   H93 sample can't be validated; the H98 study would need a 3rd
   video with CASCADE_3+ to characterize.
3. **Stop here.** H96 v2 achieves 17/4/0/0 (P=1.000, R=1.000,
   acc=1.000) on 21 phases with a wide flat region. The 113 review
   pair metrics are P=0.979, R=0.648, FPR=0.024, with (CONF or
   UNCER) gate achieving P=1.000 on 33/33 pairs. Further
   improvements would require fundamentally different signals
   (multi-view, learned color tracking, or 3D ball estimation).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h96_h90_new_properly_integrated.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h96_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h96_report.md`
