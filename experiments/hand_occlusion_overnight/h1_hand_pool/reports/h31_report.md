# H31 — Visual QA of H20+H30-AND intersection candidates at scale

**Date:** 2026-08-28 ~12:20 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE** (0/10 REAL, 2/10 PARTIAL, 8/10 FALSE)

## Hypothesis

H30 reported a precision-optimized filter (`src_above + src_desc`) with
0/14 FALSE on the deduplicated known-label set. H31 applies this filter
to the H17 strict pool and intersects with H20-KEPT to produce a
15-candidate high-precision pool. Of these 15, 5 are already in the
known-label set (4 REAL + 1 PARTIAL = 100% precision on QA'd set).
The remaining 10 are NEW candidates that need visual QA.

H31 hypothesis: the H20+H30-AND intersection is a precision-optimized
pool. The 10 NEW candidates should have similar or higher REAL precision
than the H20-KEPT-not-in-h7v2 pool (H24: 22% REAL on 9) and the
H20-KEPT adjacent pool (H28: 17% REAL on 12).

## Methodology

- Selected 10 NEW H20+H30-AND candidates (not in the known label set).
  Selection: sort by `gap` ascending, take all 10 (all are identical video,
  no YouTube candidates in the intersection).
- Rendered contact sheets via `h31_h20_h30_kept_qa.py` (2×3 grid:
  source-tail 3 frames + target-head 3 frames + V-apex annotation).
- Visually QA'd each via `vision_analyze` with structured verdict
  (REAL, PARTIAL, FALSE, UNCLEAR).

## Quantitative result

| Metric | Value |
|---|---|
| Total H20+H30-AND candidates | 15 |
| H31 sample (selected for QA) | 10 (NEW, not in known labels) |
| Verdicts: REAL | 0 |
| Verdicts: PARTIAL | 2 |
| Verdicts: FALSE | 8 |
| **Precision (REAL+PARTIAL=TP)** | **0.200** (2/10) |
| **Precision (REAL only)** | **0.000** (0/10) |

### Per-vshape

| V-shape | n | REAL | PARTIAL | FALSE | P (REAL) |
|---|---|---|---|---|---|
| V_DEEP | 8 | 0 | 2 | 6 | 0.000 |
| V_SHALLOW | 2 | 0 | 0 | 2 | 0.000 |

## Visual QA breakdown

| # | Edge | min_d | Verdict | Reason |
|---|------|-------|---------|--------|
| 1 | 17→21 identical (R) | 22.4 | **FALSE** | Source ascending (not descending to R hand); target ascending away from R hand. No V. |
| 2 | 17→22 identical (R) | 22.4 | **FALSE** | Source at R hand moving away; target 380 px above R hand. No connection. |
| 3 | 12→17 identical (L) | 38.2 | **FALSE** | Source stationary at L hand; target 175 px right of L hand, stationary. Cross-hand/cross-ball artifact. |
| 4 | 12→18 identical (L) | 38.2 | **FALSE** | Source ascending from L hand; target 400 px above L hand, stationary. No V. |
| 5 | 15→18 identical (R) | 50.9 | **FALSE** | Source at R hand stationary; target 300 px above R hand, stationary. No V. |
| 6 | 20→23 identical (R) | 65.6 | **PARTIAL** | Source descending but 165 px above R hand; target 90 px right of R hand. Weak V. |
| 7 | 54→58 identical (R) | 8.5 | **PARTIAL** | Source at R hand moving up; target approaching R hand from lower-left. min_d=8.5 but wrong geometry. |
| 8 | 17→24 identical (R) | 22.4 | **FALSE** | Source at R hand; target at L hand. Cross-hand artifact. |
| 9 | 56→59 identical (L) | 7.1 | **FALSE** | Source at L hand rising; target descending toward hands (not leaving L hand). V-apex at L hand but target descends, doesn't leave. |
| 10 | 54→60 identical (R) | 8.5 | **FALSE** | Source ascending from R hand; target 40 px left of R hand ascending. No V. |

## H31 vs H20 vs H24 vs H28 (visual QA comparison)

| Sample | n | REAL | PARTIAL | FALSE | P (REAL) | P (REAL+PARTIAL) |
|---|---|---|---|---|---|---|
| H20 `e6c_not_in_h7v2` (8-candidate sample) | 8 | 5 | 3 | 0 | **0.625** | 1.000 |
| H24 `e6c_not_in_h7v2` (9-candidate sample) | 9 | 2 | 2 | 5 | 0.222 | 0.444 |
| H20+H24 combined `e6c_not_in_h7v2` | 17 | 7 | 5 | 5 | 0.412 | 0.706 |
| H28 `adjacent` (12-candidate sample) | 12 | 2 | 4 | 4 | 0.167 | 0.500 |
| **H31 `H20+H30-AND` (10 NEW sample)** | **10** | **0** | **2** | **8** | **0.000** | **0.200** |

H31 has the LOWEST precision of any H20-KEPT subset QA'd so far.

## Negative findings

- **H31 fails the H30-derived hypothesis.** H30 reported
  `src_above + src_desc` as a precision-optimized filter with
  0/14 FALSE on the known-label set. H31 visual QA on 10 NEW
  H20+H30-AND candidates finds 0/10 REAL, 8/10 FALSE. The
  H30 claim was overfitted to a small biased known-label set.
- **The H30 claim of 0/14 FALSE on dedup'd known labels is
  misleading.** The known labels are themselves a biased sample
  (H17/H20/H24/H28 visual QA selected "interesting" candidates
  that may have shared geometric features). The H31 sample is
  a more representative sample of the H20+H30-AND pool, and on
  this sample H30 has 0% precision.
- **The 8 H31 FALSE positives** are dominated by:
  - "Continuous upward path through hand region" (3/8) — same
    failure mode as H28 #5, #6
  - "Cross-hand pairing" (1/8) — same as H28 #10 (24→26 L)
  - "V-apex at hand but ball is far away" (2/8) — e.g. 12→17,
    15→18 where target ball is 175-300 px from V-apex hand
  - "Source at hand moving up, target approaching from below"
    (2/8) — e.g. 54→58, 56→59 where the ball is descending
    toward the hand, not leaving it (reverse direction from
    a throw)
- **H30 does not address the cross-hand or cross-ball pairing
  failures.** The `src_above + src_desc` check only verifies
  that the source is descending. It does not verify that the
  source and target are the SAME physical ball.
- **The H30 check correctly identifies the throw-bias in H17
  (the original H30 hypothesis)**, but this is not enough to
  produce a precision-optimized pool. The H17 V-shape pool
  has multiple fundamental failure modes that no single
  geometric filter can fix.

## H31 as a chain-set augmentation tool

The 0/10 REAL precision of the H20+H30-AND pool means it is
NOT a reliable chain-set augmentation source. Combined with
H20/H24/H28 results, the overall conclusion is:

- **H20-KEPT `e6c_not_in_h7v2` (visually-confirmed REAL only)**
  is the ONLY reliable augmentation source. H21 (5 H20-KEPT
  REAL edges) and H26 (2 H24 NEW REAL edges) used this.
- **H20-KEPT `adjacent` (H28) and H20+H30-AND (H31) should NOT
  be used for augmentation.** Both have 0% or near-0% REAL
  precision on a larger sample.
- **The H17 V-shape strict pool has fundamental geometric
  limitations** that no amount of post-filtering (H20's
  in-hand + vel-jump + apex, H30's src_above + src_desc)
  can fix. The pool is useful for candidate MINING (finding
  candidates for human review) but not for automatic
  incorporation.

## Verdict

**NEGATIVE.** H31 visual QA confirms that the H20+H30-AND
intersection is NOT a precision-optimized pool, contradicting
H30's "0/14 FALSE on known labels" claim. The H17→H20→H30
pipeline produces 15 candidates with 0% REAL precision on a
10-candidate sample. The H17 V-shape strict pool should NOT
be used for automatic chain-set augmentation.

The recommended operating point remains h7v3plus2 (H26).

## Recommendation

- h7v3plus2 (H26) remains the recommended chain set.
- H30 src_above + src_desc is NOT a useful filter on the
  larger sample. The H30 report's "0/14 FALSE" claim was
  an overfit to a small biased known-label set.
- The H17→H20→H24→H28→H31 negative finding chain is now
  well-established. Every geometric post-filter on the H17
  V-shape pool fails to produce a reliable high-precision
  candidate set.
- Future work on chain-set augmentation should focus on
  using ONLY the H17+H20-KEPT visually-confirmed REAL
  subset (used by H21+H26), not on filtering the broader
  H17 pool.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h31_h20_h30_kept_qa.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h31/*.png` (10 sheets)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_h20_h30_kept.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_selected_candidates.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_visual_qa_verdicts.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h31_report.md` (this file)

## Cross-references

- H17 — V-shape strict pool (151 positives)
- H20 — in-hand + vel-jump + apex filter (115 H20-KEPT)
- H24 — visual QA of H20-KEPT-not-in-h7v2 (9 candidates, 22% REAL)
- H28 — visual QA of H20-KEPT adjacent (12 candidates, 17% REAL)
- H30 — direction-reversal check (claimed 0/14 FALSE on known labels)
- H31 — visual QA of H20+H30-AND intersection (10 candidates, 0% REAL)
- H26 — H24 NEW REAL H20-KEPT chain set augmentation v2
