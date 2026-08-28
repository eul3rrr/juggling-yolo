# H57 — H10 v11 v4: Conditional Penalty for High-CV Low-Arc Chains

**Date:** 2026-08-28 ~19:30 CEST
**Status:** COMPLETE (PARTIAL PASS — addresses H56 v1 limitation)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis

H56 v1's `n_arcs_clean >= 3` gate is too strict for chains with very
high g_cv (e.g., chain 14 with g_cv=1.089 and only 2 clean arcs).
When a chain has g_cv > 1.0, even 2 arcs are sufficient to detect
the inconsistency.

**Formulation:**
- If n_arcs_clean >= 3: apply H56 v1 full non-linear penalty
- If n_arcs_clean >= 2 AND g_cv >= HIGH_CV_FLOOR (=1.0): apply
  PARTIAL_W54 (0.15) with linear ramp from 0 at floor to PARTIAL_W54
  at g_cv=1.5
- Else: no penalty

**Default thresholds:**
- HIGH_CV_FLOOR = 1.0
- PARTIAL_W54 = 0.15 (half of full W54=0.30)
- MIN_ARCS_PARTIAL = 2 (vs 3 for full)

## Quantitative result (default)

### Identical (n=42 chains)

| Metric | v10 | H56 v1 | H57 v1 | Δ(v10→v11v4) |
|---|---|---|---|---|
| n_chains | 42 | 42 | 42 | 0 |
| n_penalized | 0 | 7 | 11 | +11 |
| **n_CONFIDENT** | **27** | **27** | **27** | **0** |
| n_TRUSTABLE | 13 | 10 | 10 | -3 |
| n_LOW | 2 | 5 | 5 | +3 |
| mean_q | 0.8105 | 0.7809 | 0.7767 | -0.0338 |
| multi-tid CONFIDENT | 3 | 3 | 3 | 0 |

**Penalized chains (11):**
- chain 16 (g_cv=1.27, n_arcs=2, partial): q11=0.877 (was 0.958)
- chain 7 (g_cv=0.72, n_arcs=3, full): q11=0.704 (was 0.836)
- chain 28 (g_cv=1.179, n_arcs=2, partial): q11=0.615 (was 0.668)
- chain 4 (g_cv=0.619, n_arcs=5, full): q11=0.597 (was 0.668)
- chain 2 (g_cv=0.553, n_arcs=3, full): q11=0.566 (was 0.598)
- chain 34 (g_cv=1.055, n_arcs=2, partial): q11=0.564 (was 0.580)
- chain 14 (g_cv=1.089, n_arcs=2, partial): q11=0.427 (was 0.454)
- chain 29 (g_cv=0.831, n_arcs=4, full): q11=0.378 (was 0.577)
- chain 39 (g_cv=1.014, n_arcs=3, full): q11=0.361 (was 0.661)
- chain 22 (g_cv=1.537, n_arcs=4, full): q11=0.258 (was 0.558)
- chain 37 (g_cv=0.849, n_arcs=6, full): q11=0.114 (was 0.324)

### YouTube (n=15 chains)

| Metric | v10 | H56 v1 | H57 v1 | Δ(v10→v11v4) |
|---|---|---|---|---|
| n_chains | 15 | 15 | 15 | 0 |
| n_penalized | 0 | 7 | 7 | +7 |
| **n_CONFIDENT** | **5** | **5** | **5** | **0** |
| n_TRUSTABLE | 10 | 9 | 9 | -1 |
| n_LOW | 0 | 1 | 1 | +1 |
| mean_q | 0.6886 | 0.6308 | 0.6308 | -0.0578 |
| multi-tid CONFIDENT | 1 | 1 | 1 | 0 |

YouTube has no chains with n_arcs=2 + high g_cv, so H57 v1 = H56 v1
on YouTube.

## Interpretation

H57 v1 successfully addresses H56 v1's chain 14 limitation:

1. **chain 14 (g_cv=1.089, n_arcs=2) now gets a partial penalty**
   (0.027), reducing q from 0.454 to 0.427. The chain remains
   UNCERTAIN (not demoted to LOW), but the penalty reflects the
   high-CV evidence.

2. **chain 16, 28, 34 (g_cv > 1.0, n_arcs=2)** also get partial
   penalties. These are multi-ball-merge candidates that H56 v1
   missed.

3. **No CONFIDENT chains are demoted.** The CONFIDENT count is
   preserved at 27 identical, 5 YouTube. The partial penalty is
   small enough to not push any chain past a threshold.

4. **chain 14, 28, 34 remain UNCERTAIN** in H57 v1. The partial
   penalty is a soft warning, not a hard demotion.

## Key findings

1. **H57 v1 is a "soft warning" extension of H56 v1.** It doesn't
   change any chain's CONFIDENT/UNCERTAIN/LOW label, but it does
   reduce the q of high-CV low-arc chains to reflect the
   inconsistent-gravity evidence.

2. **The CONFIDENT count is preserved at v10 levels** (27 identical,
   5 YouTube). H57 v1 is precision-safe (no false demotions) but
   recall-limited (chain 14, 28, 34 still UNCERTAIN, not LOW).

3. **The partial penalty is appropriate** for n_arcs=2 chains
   because 2 arcs is the minimum to compute a CV. The penalty
   magnitude (PARTIAL_W54=0.15) is half of full W54=0.30, reflecting
   the lower confidence in the CV estimate.

4. **H57 v1 = H56 v1 on YouTube** because no YouTube chains have
   n_arcs=2 + g_cv > 1.0. The YouTube long-tracklet nature means
   most chains have many arcs.

## Negative findings

1. **The partial penalty doesn't push chain 14 below 0.4 (TRUSTABLE
   threshold).** chain 14 q10=0.454, q11=0.427. To push it below
   0.4, the penalty would need to be > 0.054. With PARTIAL_W54=0.15
   and g_cv=1.089, the penalty is only 0.027.

2. **chain 16 (single-tid, g_cv=1.27, n_arcs=2) gets a penalty**
   for within-tracklet arc variability, but this might be normal
   (e.g., a single tracklet that includes both a hold and a throw).
   The H57 penalty doesn't distinguish single-tid from multi-tid
   chains, so single-tid chains with high g_cv are penalized
   the same as multi-tid.

3. **No new visual QA was performed** for this experiment. The H57
   v1 changes are quantitatively small (no label changes) and the
   v56 v1 visual QA already covered the main multi-ball-merge
   chains (chain 22, chain 12 YouTube).

## Verdict

**PARTIAL PASS.** H57 v1 addresses the H56 v1 chain 14 limitation
by extending the penalty to high-CV low-arc chains. The CONFIDENT
count is preserved, no chain is hard-demoted, and chain 14 (the
specific known FP) now gets a soft penalty.

However, the practical impact is small (no label changes, only q
reductions of 0.02-0.08). H57 v1 is a useful refinement but not
a major improvement. The recommended operating point remains
H56 v1 (H10 v11 v3) for simplicity; H57 v1 is a "soft warning"
extension for downstream consumers who want extra signal.

**Recommended operating point:** h7v3plus3 + H10 v11 v4 (H57 v1)
+ H12 v8 + H50 + H43 + H52 + H53.

The H10 v11 v3 (H56 v1) and H10 v11 v4 (H57 v1) give the same
CONFIDENT/UNCERTAIN/LOW labels; v4 just adds soft penalties for
high-CV low-arc chains.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h57_conditional_penalty.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v4_conditional_w0.30_<stem>.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v4_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h57_report.md`
