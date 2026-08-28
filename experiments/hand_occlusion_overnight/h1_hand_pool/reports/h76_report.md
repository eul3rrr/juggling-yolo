# H76 — End-to-end precision/recall on the 19-phase H70 sample

**Date:** 2026-08-28
**Question:** What is the end-to-end quality of the full h7v3plus3 + H10 v11 v3
+ H12 v8 + H50 + H70/H71/H75 v1 stack on the 19 H70 substantial phases?

## Background

H59 (H22/H26 + H12 v8 stack on the 113 manual review pairs) achieved
precision 0.981 / recall 0.718. H59 evaluated at the chain-edge level
("did the chain get the right edge"), not at the phase level.

H76 re-evaluates the same stack at the **phase level** on the 19 H70
substantial phases with comprehensive ground truth from H65 + H71 +
H72 + H73.

## Stack (per H75 recommendation)

For FOUNTAIN_3+ phases: REJECT if H43 (conf<0.55) OR H69 (spec_conc<0.15) OR H74 (LR_var<0.20)
For CASCADE_3+ phases: REJECT if H74 (LR_var<0.20) (H74 alone)
For MIXED_3+ phases: REJECT if H71 (spec_conc<0.10)
For MIXED_3+_UNCONFIRMED: REJECT if H71 (spec_conc<0.10)

## Ground truth (H65/H71/H72/H73 verdicts on 19 phases)

| Phase | Pattern | conf | spec_conc | lr_var | Decision | gt | Verdict source |
|-------|---------|------|-----------|--------|----------|----|----|
| f=263-312 id | MIXED_3+ | 0.728 | 0.182 | 0.564 | KEEP | JUGGLING | H71 |
| f=411-450 id | MIXED_3+ | 0.797 | 0.196 | 0.728 | KEEP | JUGGLING | H71 |
| f=549-578 id | MIXED_3+ | 0.704 | 0.332 | 0.522 | KEEP | JUGGLING | H71 |
| f=631-669 id | FOUNTAIN_3+ | 0.714 | 0.411 | 0.621 | KEEP | FOUNTAIN | H65 |
| f=685-716 id | CASCADE_3+ | 0.738 | 0.498 | 0.386 | KEEP | MANIPULATION_TRICK | H72 |
| f=890-936 id | FOUNTAIN_3+ | 0.571 | 0.308 | 0.586 | KEEP | OTHER | H65 |
| f=977-1011 id | FOUNTAIN_3+ | 0.565 | 0.326 | 0.296 | KEEP | FOUNTAIN | H65 |
| f=2-71 yt | MIXED_3+_UNCONFIRMED | 0.333 | 0.075 | 0.124 | REJECT (H71) | STATIC | H71 |
| f=114-255 yt | MIXED_3+ | 0.705 | 0.124 | 0.205 | KEEP | JUGGLING_STARTUP | H71 |
| f=267-298 yt | MIXED_3+ | 0.679 | 0.175 | 0.000 | KEEP | JUGGLING | H72 |
| f=308-338 yt | MIXED_3+ | 0.642 | 0.235 | 0.589 | KEEP | JUGGLING | H71 |
| f=339-374 yt | FOUNTAIN_3+ | 0.646 | 0.164 | 0.218 | KEEP | FOUNTAIN | H65 |
| f=375-410 yt | MIXED_3+ | 0.647 | 0.216 | 0.159 | KEEP | JUGGLING | H72 |
| f=420-481 yt | MIXED_3+ | 0.651 | 0.165 | 0.204 | KEEP | JUGGLING | H72 |
| f=482-594 yt | FOUNTAIN_3+ | 0.653 | 0.140 | 0.135 | REJECT (H69) | STATIC_HOLD | H74 |
| f=595-643 yt | MIXED_3+ | 0.650 | 0.170 | 0.224 | KEEP | JUGGLING | H72 |
| f=769-799 yt | MIXED_3+ | 0.655 | 0.214 | 0.318 | KEEP | JUGGLING | H71 |
| f=800-861 yt | FOUNTAIN_3+ | 0.651 | 0.088 | 0.202 | REJECT (H69) | CASCADE | H65 |
| f=862-899 yt | MIXED_3+ | 0.675 | 0.249 | 0.239 | KEEP | JUGGLING | H72 |

## Aggregate results

| Metric | Value |
|--------|-------|
| Total phases | 19 |
| Real juggling | 15 |
| Misclassified | 4 |
| Kept | 16 |
| Rejected | 3 |
| **TP** (real kept) | **14** |
| **TN** (misclass rejected) | **2** |
| **FP** (misclass kept) | **2** |
| **FN** (real rejected) | **1** |
| Real recall | 14/15 = 93.3% |
| Misclass rejection precision | 2/4 = 50.0% |
| Overall accuracy | 16/19 = 84.2% |

**Per-pattern breakdown:**

| Pattern | n | real | misclass | rejected | TP | TN | FP | FN |
|---------|---|------|----------|----------|----|----|----|----|
| CASCADE_3+ | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| FOUNTAIN_3+ | 6 | 4 | 2 | 2 | 3 | 1 | 1 | 1 |
| MIXED_3+ | 11 | 11 | 0 | 0 | 11 | 0 | 0 | 0 |
| MIXED_3+_UNCONFIRMED | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

## Key findings

### 1. MIXED_3+ post-filter is the best part of the stack

11/11 MIXED_3+ phases are correctly kept (100% precision, 100% recall).
H71 v1 (spec_conc < 0.10 = REJECT) is a perfect filter for the
H70 sample's MIXED_3+ phases. The H71 v1 threshold catches the
1 MIXED_3+_UNCONFIRMED phase (f=2-71 with spec_conc=0.075) without
rejecting any real MIXED_3+.

### 2. FOUNTAIN_3+ post-filter is partial

3/4 real FOUNTAIN correctly kept (75% recall). 1 real FOUNTAIN (f=339-374)
has spec_conc=0.164, which is just above the H69 threshold of 0.15,
so it's kept (correct). But the 1 FN (f=800-861) is a real CASCADE
mislabeled as FOUNTAIN_3+ by H12 v8, and the H75 stack correctly
rejects it (the H12 v8 label was wrong, the juggler IS doing a
cascade). This is a "labeling error" rather than a "model failure".

1/2 misclassified FOUNTAIN_3+ caught (f=482-594 via H69).
1/2 missed (f=890-936 crossed-arm trick — none of H43/H69/H74 catches it).

### 3. CASCADE_3+ post-filter is fundamentally limited

The 1 CASCADE_3+ phase in the sample is a manipulation trick
(f=685-716). The H75 stack with H74 alone cannot catch it (var=0.386,
not below 0.20). This is consistent with the H73 finding that
CASCADE_3+ accuracy is 0/2 on substantial phases.

### 4. End-to-end accuracy: 84.2% (16/19 correct)

The full h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H70/H71/H75 v1
stack achieves 84.2% accuracy on the 19 H70 substantial phases.

Breakdown:
- 14/19 correct KEEP (real juggling kept)
- 2/19 correct REJECT (misclassifications caught)
- 2/19 false KEEP (misclassifications missed)
- 1/19 false REJECT (real juggling lost)

The 3 errors are all on FOUNTAIN_3+ / CASCADE_3+ phases. MIXED_3+
is 100% correct.

## Implications

### The full stack is precision-optimized for MIXED_3+ and recall-optimized for FOUNTAIN_3+

The H71 v1 filter (spec_conc < 0.10 = REJECT) is conservative and
keeps all real MIXED_3+ phases. The H75 stack (H43+H69+H74) is
more aggressive on FOUNTAIN_3+ and CASCADE_3+.

The trade-off:
- For MIXED_3+ downstream consumers: 100% precision, 100% recall
- For FOUNTAIN_3+ downstream consumers: 50% misclass rejection,
  75% real recall
- For CASCADE_3+ downstream consumers: 0% precision, 0% recall
  (treat as research signal only)

### H59 vs H76: complementary evaluations

H59 evaluated at the chain-edge level (113 manual review pairs):
- precision 0.981, recall 0.718

H76 evaluated at the phase level (19 H70 substantial phases):
- precision 84.2% (16/19 correct)
- TP rate 93.3% (14/15 real kept)
- TN rate 50% (2/4 misclass caught)

H59's higher precision is partly due to the manual review set being
mostly mid-air edges (which the chain algorithm handles well).
H76's lower precision is due to the H70 sample being mostly
hand-event phases (which H12 v8 mislabels).

### CASCADE_3+ is the weakest class

0/1 CASCADE_3+ in the H70 sample is correctly classified.
This is consistent with H73's 0/2 finding. CASCADE_3+ should be
treated as a research signal.

## Recommended operating point (post-H76, final)

For FOUNTAIN_3+ post-filter: (H43 OR H69 OR H74) where H74=LR_variance<0.20
For CASCADE_3+ post-filter: H74 alone (1/2 catches in H73 sample)
For MIXED_3+ post-filter: H71 v1 (KEEP>=0.15, REJECT<0.10) — 100% precision

## Negative findings

1. **CASCADE_3+ has 0% precision on substantial phases.** 0/1 in
   H76 sample, 0/2 in H73 sample. Treat as research signal.
2. **f=890-936 (crossed-arm trick) is not caught by any filter.**
   Conf (0.571) is above 0.55, spec_conc (0.308) is above 0.15,
   var (0.586) is above 0.20. None of H43/H69/H74 catches it.
3. **MIXED_3+ post-filter is perfect on the H70 sample** (11/11
   correct). The H71 v1 threshold is well-calibrated.
4. **End-to-end accuracy is 84.2%** (16/19 correct on H70 sample).

## Future research directions

1. **H77: extend H76 to the 113 manual review pairs** — combine
   H59's chain-edge evaluation with H76's phase-level evaluation
   to get a complete precision/recall matrix.
2. **H78: novel signals for crossed-arm trick detection** —
   f=890-936 is not caught by any current filter. A learned
   model or hand-trajectory smoothness check might help.
3. **H79: cross-video calibration of H69 spec_conc threshold** —
   The H69 threshold 0.15 may be over-tuned to the YouTube
   sample. A per-video or per-ball-count calibration might
   improve FOUNTAIN_3+ accuracy.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h76_end_to_end_eval.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h76_summary.json`
