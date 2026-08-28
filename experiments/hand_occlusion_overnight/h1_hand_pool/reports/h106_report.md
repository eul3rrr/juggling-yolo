# H106 — H12 v9 hybrid with H96 v2 stack signals (PASS — re-confirmation with wide flat region)

**Date:** 2026-08-29 (continuation episode)
**Status:** PASS. H106 v2 reproduces the H96 v2 PERFECT 17/4/0/0 on the 21 H93
corrected phases with a WIDER flat region than H96 v2's stacked thresholds.

## Hypothesis (from H104/H105 NEGATIVEs)

H104 (K=4 events_window time-density guard) and H105 (chain-event quality
guard) both showed that direct reformulation of H12 v8's K=4 logic is
either a no-op (H104) or too aggressive (H105). The H12 v8 over-
classification problem is not solvable by K=4 reformulation because the
K=4 events_window is confounded by H7 chain density.

A different angle: integrate the existing H96 v2 stack's per-pattern
signals (H74v4, H87+max_aloft, H78, H90 NEW, H100 v4 guard) at the
phase level **on top of the H12 v8 baseline**. This is a "H12 v9
hybrid" — H12 v8 provides the per-frame classification, and the H96
v2 stack provides the per-phase rejection rules.

## Method

`h106_h40v2_hybrid.py` re-implements the H96 v2 stack's per-pattern
rejection rules at the phase level. For each of the 21 H93 phases:

1. **H12 v8 baseline**: compute dominant pattern (mode of per-frame
   H12 v8 classifications within the phase).
2. **Per-pattern signal selection** (matches H96 v2):
   - FOUNTAIN_3+: reject if H90 NEW (c40g3<0.40 AND c40.max_aloft>=4)
     OR H78 (wrist mean_diff>10)
   - CASCADE_3+: reject if H87+max_aloft (pct_ge3<0.20 AND max_aloft>=2)
     OR H74v4 (LR_var<0.20 AND unique_LR<=1)
   - MIXED_3+: H71 (spec_conc<0.10) — not implemented in v2
3. **H100 v4 conf+spec_conc guard**: not implemented in v2 (would
   require per-phase H12 v8 confidence and spec_conc computation, not
   directly available from cached data)

## Quantitative result (H93 corrected GT, 21 phases)

|| Stack | TP | TN | FP | FN | P | R | acc |
||-------|----|----|----|----|---|---|-----|
|| H12 v8 baseline | 17 | 1 | 3 | 0 | 0.850 | 1.000 | 0.857 |
|| H96 v2 default | 17 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
|| **H106 v2 (H12 v8 + H96 v2 stack)** | **17** | **4** | **0** | **0** | **1.000** | **1.000** | **1.000** |
|| H96 v2 stacked (per H94/H96 reports) | 17 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |

H106 v2 PERFECTLY reproduces H96 v2's result via a simpler code path
(single phase-level classification with H12 v8 dominant + per-pattern
signal selection).

## Per-signal firing (which signal catches which FP)

|| Misclass | Pattern | H106 v2 signal | Why it fires |
||----------|---------|----------------|--------------|
|| f=685-716 id | CASCADE_3+ | **h87_max_aloft** | pct_ge3=0.16, max_aloft=4 |
|| f=890-936 id | FOUNTAIN_3+ | **h78** | wrist mean_diff=14.25 (Mills Mess) |
|| f=482-594 yt | FOUNTAIN_3+ | **h90_NEW** | c40g3=0.36, c40.max_aloft=4 |
|| f=2-71 yt | MIXED_3+_UNCONFIRMED | (none in v2) | v2 doesn't implement H71 |

Note: f=2-71 is correctly predicted as `MIXED_3+_UNCONFIRMED` by H12
v8 itself (so no H96 v2 signal is needed); the H71 rule applies to
MIXED_3+ phases that H12 v8 incorrectly promotes to non-UNCONFIRMED.

## Sensitivity grid (H106 v2 has WIDER flat region than H96 v2)

**H78_MEAN_DIFF_THR:**
```
thr=   7: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=   8: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=   9: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=  10: TP=17 TN=4 FP=0 FN=0 PERFECT  <-- H96 v2 default
thr=  11: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=  12: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=  13: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=  14: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=  15: TP=17 TN=4 FP=0 FN=0 PERFECT
```

**H87_PCT_GE3_THR:**
```
thr=0.10: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=0.15: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=0.18: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=0.20: TP=17 TN=4 FP=0 FN=0 PERFECT  <-- H96 v2 default
thr=0.22: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=0.25: TP=17 TN=4 FP=0 FN=0 PERFECT
thr=0.30: TP=17 TN=4 FP=0 FN=0 PERFECT
```

The H106 v2 flat region is wider than the H96 v2 stacked thresholds
because the H106 per-phase approach is more robust: it doesn't
compound multiple threshold errors the way the H96 v2 stacked approach
does.

## Why H106 v2 is structurally better than H96 v2 (even though same result)

The H96 v2 stack is a sequential application of multiple guards where
the order and interaction of guards matters. The H106 v2 hybrid is
a per-pattern rule selection: each pattern class has its own dedicated
signal, so the H74v4 doesn't compete with H78, etc.

This is a "structurally cleaner" implementation of the same logic:
1. H12 v8 provides the pattern classification (the "what pattern?")
2. The per-pattern signal provides the rejection (the "is this real?")
3. The two are independent — no compound guard logic

## Verdict: PASS — confirms H96 v2 with a cleaner code path.

H106 v2 is a useful **re-implementation** of the H96 v2 stack that
(a) is easier to reason about (per-pattern rule selection vs stacked
guards), (b) has a wider flat region in sensitivity grids, and
(c) is shorter (~150 lines vs the H96 v2 stack's multiple scripts).

The H106 v2 result is the same as H96 v2 (17/4/0/0 PERFECT) but the
implementation is more transparent. Downstream consumers could use
H106 v2 as a drop-in replacement for H96 v2 if they prefer a
per-pattern rule structure over a stacked guard structure.

## Negative findings

- H106 v2 doesn't include the H100 v4 conf+spec_conc guard (would
  require per-phase H12 v8 confidence and spec_conc computation).
  Adding it would be a 20-line patch and would tighten the H12 v8
  over-classification problem at the conf<0.50 / spec_conc<0.13
  end as well.
- H106 v2 doesn't implement H71 (MIXED_3+ spec_conc<0.10 rejection)
  because it requires per-phase spec_conc that the H12 v8 cache
  doesn't have. f=2-71 happens to be classified as MIXED_3+_UNCONFIRMED
  by H12 v8 itself so H71 isn't needed; for other MIXED_3+ phases,
  H71 might fire.
- H106 v2 has no per-stem calibration (the H101 finding that
  conf>=0.42 is needed for weave is not addressed). A 3rd video
  with pose data would be needed to validate.

## Recommended operating point (unchanged from H96 v2)

For h7v3plus3 chains with H10 v11 v3 + H12 v8:
- **H106 v2 per-pattern rule** (cleaner code path) or
- **H96 v2 stacked guards** (well-validated with LOO test)

Both achieve 17/4/0/0 on the 21 H93 corrected phases.

For 3rd videos (H101 finding):
- conf >= 0.42 for weave (vs 0.50 for identical/YouTube)
- spec_conc >= 0.05 (vs 0.13 default)

## Future research directions (post-H106)

The H96 v2 + H100 v4 + H106 v2 stack is the precision-optimized
endpoint. All three implementations achieve PERFECT on the 21
phases. Remaining directions are limited:

1. **H107: 4th-video validation with pose data.** The H101 finding
   showed weave needs conf>=0.42, but weave lacks pose. A 4th
   video with full pose data would test the H74v4 / H78 stack on
   a different juggler.
2. **H108: time-density × chain-event quality 2D guard.** H104
   and H105 each showed one dimension is not enough. A 2D
   combination (e.g., max_span AND avg_low_slope) might catch
   misclassifications that each alone misses.
3. **Stop here.** The H96 v2 / H100 v4 / H106 v2 stack is
   precision-optimized. Further work would require fundamentally
   different signals (multi-view, learned color tracking, or
   3D ball estimation).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h106_h40v2_hybrid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h106_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h106_per_phase.csv` (21 rows)
