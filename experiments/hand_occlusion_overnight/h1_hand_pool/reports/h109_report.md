# H109 — LOO structural analysis of R4b (NEGATIVE — honest finding)

**Date:** 2026-08-28 ~22:45 (continuation episode, post-H108)
**Status:** NEGATIVE (honest structural finding). R4b cannot be
re-derived from the other 3 TNs — it is uniquely tied to f=2-71's
specific signature. The H96 v2 / H108 v1 stack is an ENSEMBLE of 4
specific detectors, not a general STATIC_HOLD detector.

## Hypothesis (from H108 PASS)

R4b (unconf_frac >= 0.50) uniquely catches f=2-71 with 0 FPs. But is
this overfit to f=2-71? A truly general R4b would be re-derivable on
subsets of TNs and still catch the held-out TN.

## Method

`h109_loo_test.py` performs a structural LOO analysis:
1. For each of the 4 TNs, check if its signature is shared with any other
   phase (TN or TP) in the H93 sample.
2. Compute per-signal uniqueness: how many other phases share each TN's
   value of unconf_frac, mean_conf, max_A, max_events, min_A.
3. Conclude whether R4b is generalizable or overfit.

## Per-signal uniqueness analysis

| Signal | f=685-716 | f=890-936 | f=482-594 | f=2-71 |
|--------|-----------|-----------|-----------|--------|
| unconf_frac | 0.0 (shared w/ 19 others) | 0.0 (shared w/ 19) | 0.0 (shared w/ 19) | **1.0 (UNIQUE)** |
| mean_conf | 0.738 (UNIQUE) | 0.471 (UNIQUE) | 0.653 (UNIQUE) | **0.333 (UNIQUE)** |
| max_A | 5 (shared w/ 8 TPs) | 3 (shared w/ 5 TPs) | 6 (shared w/ 3 incl. f=2-71) | 6 (shared w/ 3 incl. f=482-594) |
| max_events | 4 (shared w/ 19) | 4 (shared w/ 19) | 4 (shared w/ 19) | **2 (UNIQUE)** |
| min_A | 3 (shared w/ 10) | 3 (shared w/ 10) | 4 (shared w/ 7) | 4 (shared w/ 7) |

Key observations:
- f=2-71 is the ONLY phase with `unconf_frac = 1.0` in the H93 sample.
- f=2-71 is the ONLY phase with `max_events = 2` (all others have 4).
- f=2-71 has the LOWEST `mean_conf` (0.333) of any phase.
- Each of the 4 TNs has a unique `mean_conf` value: 0.333, 0.471, 0.653, 0.738.

## LOO results (re-deriving R4 threshold on 3-of-4 TNs)

For each LOO split, we hold out 1 TN and re-derive the R4b threshold on
the remaining 3 TNs + 17 TPs:

| Held-out TN | sep_thr | status | held_out_caught | FP at new thr |
|-------------|---------|--------|-----------------|---------------|
| f=685-716 | ? | overlap | - | - |
| f=890-936 | ? | overlap | - | - |
| f=482-594 | ? | overlap | - | - |
| f=2-71 | ? | overlap | - | - |

All 4 LOO splits show "overlap" — this is because the 3 non-held-out TNs
have unconf_frac=0.0 (they are caught by H78, H87+max_aloft, H90 NEW
per-pattern signals, not by R4b). The R4b threshold derivation set
contains 0 TNs with high unconf_frac, so the rule cannot be re-derived
without seeing f=2-71.

## Conclusion

**The 4 TNs have ORTHOGONAL signatures, each caught by a specific detector:**

- f=685-716 STATIC_HOLD (CASCADE_3+): caught by H87+max_aloft
  (low pct_ge3=0.16, high max_aloft=4)
- f=890-936 OTHER_CROSSED_ARM (FOUNTAIN_3+): caught by H78
  (high wrist mean_diff=14.25, Mills Mess signature)
- f=482-594 STATIC_HOLD (FOUNTAIN_3+): caught by H90 NEW
  (low c40_pct_ge3=0.36, high c40_max_aloft=4)
- f=2-71 STATIC_HOLD (MIXED_3+_UNCONFIRMED): caught by R4b
  (unconf_frac=1.0 — UNIQUE in H93)

**The H96 v2 / H106 v2 / H108 v1 stack is an ENSEMBLE of 4 specific
detectors, not a general STATIC_HOLD detector.** Each TN has its own
dedicated signal that does not generalize across TNs.

**R4b is overfit to f=2-71's specific signature in the H93 sample.**
A different STATIC_HOLD phase in a 3rd video with unconf_frac < 0.50
would NOT be caught by R4b. The flat region (0.50-1.00) shows that R4b
is robust to threshold perturbations ON THE H93 SAMPLE, but does not
prove generalization to a new video.

## Implications

1. **The PERFECT 17/4/0/0 result is a consequence of 4 independent
   detectors catching 4 specific TN signatures.** This is a real
   structural finding, not a coincidence.

2. **Generalization to a 3rd video is not guaranteed.** A new STATIC_HOLD
   phase that doesn't match any of the 4 signatures would be a false
   positive. A 3rd video with H93-style GT is needed to test this.

3. **The H108 R4b rule provides a useful explicit signal for f=2-71
   but should not be relied upon as a general "UNCONFIRMED-heavy phase"
   detector.** The rule is tied to the specific f=2-71 signature.

4. **The H100 v4 conf+spec_conc guard has similar scope:** it catches
   f=2-71 (conf=0.333 < 0.50 AND spec=0.075 < 0.13) without false-
   rejecting any other H93 phase. This is the same TN being caught by
   a different explicit signal. The H108 R4b and H100 v4 guards are
   functionally equivalent for f=2-71.

## Verdict: NEGATIVE (honest structural finding).

R4b cannot be re-derived from the other 3 TNs. The H96 v2 / H108 v1
stack is an ensemble of 4 specific detectors, not a general
STATIC_HOLD detector. This is a real structural limitation that
requires a 3rd video with H93-style GT to address.

## Recommended operating point (post-H109, unchanged)

- H108 v1 (H106 v2 + R4b) is the recommended operating point
- R4b provides an explicit signal for f=2-71 (was implicit in H96 v2 via
  H12 v8's UNCONFIRMED label)
- H96 v2 / H106 v2 / H108 v1 all achieve 17/4/0/0 on the 21 H93 phases
- A 3rd video with H93-style GT is needed to test generalization
  to STATIC_HOLD phases with different signatures

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h109_loo_test.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h109_summary.json`
