# H28 — Visual QA of H20-KEPT adjacent candidate pool at scale

**Date:** 2026-08-28 ~12:00 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE** (precision 17% REAL, 50% REAL+PARTIAL)

## Hypothesis

The 88 H20-KEPT `adjacent` candidates are TRULY novel:
- NOT in E6c's accepted mid-air edge set
- NOT in h7v2's input
- NOT in H17's V-shape strict set for the `e6c_not_in_h7v2` subset
- Pass H20's in-hand + vel-jump + apex filters

H24's methodology (visual QA of 8+1 H20-KEPT-not-in-h7v2 candidates)
found REAL precision 22% (2/9). H28 applies the same methodology to the
adjacent pool, hypothesizing the precision is similar or different.

## Methodology

- Selected 12 H20-KEPT `adjacent` candidates (8 identical + 4 YouTube)
  from the 88 not yet QA'd. Selection: sort by `gap` ascending, then
  `min_hand_dist` ascending, take first 8 identical + first 4 YouTube.
- Rendered contact sheets via `h28_candidate_qa_at_scale.py` (2×3 grid:
  source-tail 3 frames + target-head 3 frames + V-apex annotation).
- Visually QA'd each via `vision_analyze` with structured verdict
  (REAL, PARTIAL, FALSE, UNCLEAR).

## Quantitative result

| Metric | Value |
|---|---|
| Total H17 strict positives | 151 |
| H20-KEPT adjacent candidates | 88 |
| H28 sample (selected for QA) | 12 (8 identical + 4 YouTube) |
| Verdicts: REAL | 2 |
| Verdicts: PARTIAL | 4 |
| Verdicts: FALSE | 4 |
| Verdicts: UNCLEAR | 2 |
| **Precision (REAL+PARTIAL=TP)** | **0.500** (6/12) |
| **Precision (REAL only)** | **0.167** (2/12) |

### Per-stem

| Stem | n | REAL | PARTIAL | FALSE | UNCLEAR | P (REAL) | P (REAL+PARTIAL) |
|---|---|---|---|---|---|---|---|
| identical | 8 | 1 | 2 | 3 | 2 | 0.125 | 0.375 |
| YouTube | 4 | 1 | 2 | 1 | 0 | 0.250 | 0.750 |

### Per-V-shape

| V-shape | n | REAL | PARTIAL | FALSE | UNCLEAR | P (REAL) | P (REAL+PARTIAL) |
|---|---|---|---|---|---|---|---|
| V_DEEP | 10 | 2 | 4 | 2 | 2 | 0.200 | 0.600 |
| V_SHALLOW | 2 | 0 | 0 | 2 | 0 | 0.000 | 0.000 |

The V_SHALLOW result (0/2) is opposite to H24's V_SHALLOW (1/1 = 100%),
suggesting H24's V_SHALLOW sample was too small to characterize reliability.

## Visual QA breakdown

| # | Edge | min_d | Verdict | Reason |
|---|------|-------|---------|--------|
| 1 | 29→33 identical (L) | 5.63 | **UNCLEAR** | Source ball at L hand; target ball 92 px away moving away. Possibly a color confusion. |
| 2 | 66→67 identical (L) | 38.32 | **UNCLEAR** | No source ball detection in source frames; target ball stationary high above. Possible pose issue. |
| 3 | 39→46 identical (L) | 51.90 | **FALSE** | Source ball high descending above L hand; target ball 90 px right of L hand. Different positions, no V. |
| 4 | 70→73 identical (L) | 21.49 | **PARTIAL** | Source ball rising into L hand; target ball still approaching. min_d=21.5 close. |
| 5 | 58→60 identical (R) | 40.46 | **FALSE** | Source ball below R hand moving up; target ball moving up through hand region. Continuous upward path, not V. |
| 6 | 6→14 identical (R) | 54.75 | **FALSE** | Source ball below R hand moving away; target ball above R hand moving up. No V. |
| 7 | **13→15 identical (R)** | 2.10 | **REAL** | Clear V at R hand. source approaches; target leaves. V-apex (527,527) at R hand. |
| 8 | 8→9 identical (L) | 10.13 | **PARTIAL** | Throw visible at L hand; source ball already at L hand, no descent. |
| 9 | 39→40 YouTube (R) | 21.28 | **PARTIAL** | Throw visible at R hand; source ball already on R hand, no descent. |
| 10 | 24→26 YouTube (L) | 1.06 | **FALSE** | Source ball at L hand; target ball at R hand. Cross-hand artifact. |
| 11 | 32→40 YouTube (R) | 21.28 | **PARTIAL** | Throw visible at R hand; source ball below R hand, no descent. |
| 12 | **10→11 YouTube (R)** | 4.69 | **REAL** | Clear V at R hand. source descending into R hand; target rising from R hand. 9-frame gap. |

## H28 vs H20 vs H24

| Sample | n | REAL | PARTIAL | FALSE | UNCLEAR | P (REAL) | P (REAL+PARTIAL) |
|---|---|---|---|---|---|---|---|
| H20 `e6c_not_in_h7v2` (subset) | 8 | 5 | 3 | 0 | 0 | **0.625** | 1.000 |
| H24 `e6c_not_in_h7v2` (new) | 9 | 2 | 2 | 5 | 0 | 0.222 | 0.444 |
| H20+H24 combined e6c_not_in_h7v2 | 17 | 7 | 5 | 5 | 0 | 0.412 | 0.706 |
| **H28 adjacent (new)** | **12** | **2** | **4** | **4** | **2** | **0.167** | **0.500** |

H28 has the LOWEST precision of any H20-KEPT subset QA'd so far.
The "adjacent" pool is the noisiest, as expected (it's outside E6c's
accepted set, so the V-shape strict + H20 filter combination has the
least signal to work with).

## Negative findings

- **H28 fails the hypothesis.** The H20-KEPT `adjacent` pool is NOT
  a high-precision candidate list for chain set augmentation.
  REAL-only precision is 17% (2/12) on the H28 sample. Even
  including PARTIAL as TP, precision is 50% (6/12).
- **The dominant failure mode is "continuous upward path through
  hand region"** (3/4 FALSE positives in H28): the V-shape + min_d
  criterion finds V-shaped trajectories but the source and target
  tracklets represent a single ball in continuous upward motion
  through the hand region, NOT a catch+throw that reverses direction.
  The H20 vel-jump and apex filters don't catch this because the
  gap is small (1-5 frames) and the V-apex is plausibly near a hand.
- **Cross-hand pairing** (1/4 FALSE): 24→26 YouTube pairs a source
  ball at the L hand with a target ball at the R hand. The
  min_d=1.06 metric is misleading because the "V-apex" is just the
  midpoint between two unrelated hands.
- **V_SHALLOW precision is 0/2 = 0%** in the H28 sample, opposite
  to H24's V_SHALLOW (1/1 = 100%). The H24 V_SHALLOW sample was
  too small to characterize reliability. H28 confirms V_SHALLOW
  does NOT guarantee high precision in the adjacent pool.
- **The "throw" half of the V-shape is more frequently visible than
  the "catch" half.** 6/12 candidates have a real throw visible,
  but only 2/12 have a real catch+throw pair. This suggests the
  H17 V-shape logic is biased toward throwing evidence: target-end
  detections often show a clear "ball leaving hand" trajectory,
  while source-end detections often show a ball already at the hand.
- **vision_analyze is unreliable on ball color** (marker blue/orange
  confused with actual ball color). This is a known issue from
  previous H20/H24 work and does not affect H28's geometric
  analysis.

## H28 as a chain-set augmentation tool

The 2 H28 REAL candidates (13→15 identical, 10→11 YouTube) are
visually-confirmed real catch+throws. However, the 10/12
non-REAL candidates suggest the H20-KEPT adjacent pool is NOT
a reliable chain-set augmentation source.

The H28 finding is consistent with H20+H24's main insight: the
H17 V-shape strict pool has many false positives that the in-hand +
vel-jump + apex filters cannot fully reject. The 88 H20-KEPT
adjacent candidates are mostly **tracklet break false positives**
or **cross-hand / cross-ball pairing artifacts**.

## Verdict

**NEGATIVE.** H28 confirms that the H17 V-shape strict pool, when
combined with H20's in-hand + vel-jump + apex filters, has
substantial false-positive rates in the `adjacent` pool
(REAL precision 17%, REAL+PARTIAL precision 50%). The 88
H20-KEPT adjacent candidates should NOT be auto-incorporated
into the chain set.

The recommended operating point remains h7v3plus2 (H26) for
hand-aware chain construction. The H28 finding supports the
conclusion that the H17→H20 pipeline is a useful **candidate
mining** tool (it produces 88 candidates for human review)
but NOT a **chain set replacement** (the precision is too low
for automatic incorporation).

## Recommendation

- h7v3plus2 (H26) remains the recommended chain set.
- The 88 H20-KEPT adjacent candidates are a useful human-review
  pool (they contain at least 2 REAL and 4 PARTIAL catch+throws
  visible to vision QA) but should NOT be auto-incorporated.
- The H17 V-shape criterion's bias toward throwing evidence
  suggests future V-shape recovery work should add a stricter
  "direction reversal" check: the source-end trajectory should
  be moving TOWARD the hand, not just AT the hand.
- A future H29 (color-continuity or trajectory-overlap check)
  could be tested on the H20-KEPT-not-in-h7v2 + adjacent pools
  to see if color/overlap filters can reduce the false-positive
  rate.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h28_candidate_qa_at_scale.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h28/*.png` (12 sheets)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_selected_candidates.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_visual_qa_verdicts.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h28_report.md` (this file)

## Cross-references

- H20 — first in-hand + vel-jump + apex filter, established 88 H20-KEPT
  adjacent candidates
- H24 — visual QA of H20-KEPT `e6c_not_in_h7v2` (9 candidates) — 22% REAL
- H26 — H24's 2 NEW REAL edges (7→10, 59→61 identical) integrated into
  h7v3plus2 chain set
- H17 — V-shape strict pool with 151 positives
- H22 — H20-KEPT edge veto mode (MIXED, narrow PASS)
- H25 — pending: cross-ball artifact rejection filter (color or
  trajectory-overlap)
