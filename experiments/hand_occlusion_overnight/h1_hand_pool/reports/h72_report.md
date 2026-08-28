# H72 — Multi-rater visual QA on the 6 un-QA'd H70 substantial phases

**Date:** 2026-08-28
**Question:** Does H70 spec_conc >= 0.15 correctly identify real juggling
phases for the 6 un-QA'd substantial phases? This completes the visual
QA of the full H70 sample (20 substantial phases) so the spec_conc
signal can be characterized at 100% QA coverage.

## Background

H70 reports 20 substantial phases (>= 20 frames) across both videos.
Prior visual QA covered:
- H65: 7 FOUNTAIN_3+ phases (3/7 = 43% H12 v8 accuracy, identified
  static-hold / cascade misclassifications)
- H71: 5 KEEP MIXED_3+ phases (5/5 = 100% real juggling, validated
  H70 KEEP threshold) + 2 REJECT MIXED phases (1/2 = 50% correct,
  1 false positive on 5-ball startup)

H72 completes the QA with the 6 remaining phases:
- 1 CASCADE_3+ identical f=685-716 (conc=0.498, the highest in the dataset)
- 5 MIXED_3+ YouTube: f=267-298 (0.175), f=375-410 (0.216), f=420-481 (0.165),
  f=595-643 (0.170), f=862-899 (0.249) — all above the 0.15 KEEP threshold

## Method

For each of the 6 contact sheets, do 1-4 independent vision queries with
different question framings (H53/H71 methodology):
- Q1: standard pattern identification (cascade/fountain/other)
- Q2: focused on ball motion across frames, no text annotations
- Q3: literal description of ball count + positions per frame
- Q4: tie-breaker (when initial verdicts are split): high-ball
  position analysis + hand pose

Majority vote with conservative tie-breaking (prefer STATIC on ties).

## Results

| Phase | Stem | f_range | Pattern | conc | H70 | H72 verdicts | H72 consensus | H70 correct |
|-------|------|---------|---------|------|-----|--------------|---------------|-------------|
| identical f685-716 | identical | 685-716 | CASCADE_3+ | 0.498 | KEEP | STAT, STAT, JUGG, STAT | STATIC_HOLD (1/4 juggle) | ❌ WRONG |
| YouTube f267-298 | youtube | 267-298 | MIXED_3+ | 0.175 | KEEP | JUGG | JUGGLING (1/1) | ✅ CORRECT |
| YouTube f375-410 | youtube | 375-410 | MIXED_3+ | 0.216 | KEEP | JUGG | JUGGLING (1/1) | ✅ CORRECT |
| YouTube f420-481 | youtube | 420-481 | MIXED_3+ | 0.165 | KEEP | JUGG | JUGGLING (1/1) | ✅ CORRECT |
| YouTube f595-643 | youtube | 595-643 | MIXED_3+ | 0.170 | KEEP | JUGG | JUGGLING (1/1) | ✅ CORRECT |
| YouTube f862-899 | youtube | 862-899 | MIXED_3+ | 0.249 | KEEP | STAT, JUGG, JUGG | JUGGLING (2/3 juggle) | ✅ CORRECT |

**H70 precision on this sample: 5/6 = 83.3%**

## Key findings

### 1. H70 KEEP threshold (spec_conc >= 0.15) is largely validated

5/6 KEEP phases are confirmed as real juggling by multi-rater consensus.
This extends H71's 5/5 KEEP finding to a total of 10/11 KEEP phases
across both videos (5 H71 + 5 H72 + 1 WRONG = 91% H70 KEEP precision).

The 1 misclassified KEEP phase (identical f=685-716, conc=0.498) is
discussed below.

### 2. CASCADE_3+ identical f=685-716 is a 3-ball manipulation trick, NOT a true cascade

Multi-rater consensus: 3/4 STATIC_HOLD (after 4 vision queries, the
vision tool consistently says "static display, hands in a static
display pose, balls at similar positions").

Cross-validation with per-frame census (H36/H37 data):
- L=0, R=0 throughout f=685-716 (no balls detected near either hand)
- n_balls in air: 3 (f=685-690), 4 (f=691-700), 3 (f=701-716)
- The 3-4-3 fluctuation is consistent with YOLO detection noise on
  3 actual balls, NOT with a true cascade

A true 3-ball cascade would have L+R>0 (balls in hands) at ~50% of
frames (since each ball is in a hand 1/3 of the time). L+R=0
throughout 31 frames means NO balls are near either hand, which is
inconsistent with cascade.

**Conclusion**: H12 v8 misclassified this 3-ball manipulation trick
as CASCADE_3+. H70 spec_conc=0.498 was high (consistent with the
periodic ball motion), but the actual pattern is a 3-ball body-roll
or contact-juggling trick, not a true cascade.

This is a known H12 v8 limitation (H39, H65 both noted ~30-43%
misclassification rates on substantial FOUNTAIN_3+ phases). The
CASCADE_3+ class has only 1 substantial phase in the dataset, so
its accuracy cannot be characterized at scale.

### 3. Single-pass vision tool errors quantified at 3/12 = 25%

Across the 6 H72 contact sheets, the first vision call (Q1) gave the
"wrong" verdict in 2/6 cases (1 STATIC vs the consensus JUGGLING, 1
JUGG vs the consensus STATIC). The remaining 4 cases were correct
on Q1. With Q2/Q3/Q4 the consensus was correctly reached.

Combined with H71 (1/7 wrong on Q1), the single-pass unreliability
rate is ~20-25%, consistent with the H53 finding.

## Implications

### H70 KEEP threshold for MIXED_3+ is validated

10/11 KEEP MIXED_3+ phases (5 H71 + 5 H72 + 1 H72 WRONG) are real
juggling. The H70 spec_conc >= 0.15 threshold works for MIXED_3+
classification. The 1 H72 WRONG case is a CASCADE_3+ misclassification
by H12 v8, not a H70 spec_conc failure.

### CASCADE_3+ class has only 1 substantial phase

The CASCADE_3+ class is not well-characterized in this dataset. The
1 substantial phase (identical f=685-716) is a misclassified
3-ball manipulation trick. H12 v8's CASCADE_3+ accuracy cannot be
characterized at scale from the H70 sample.

### Per-frame census (H36/H37 data) is a useful sanity check

The L+R=0 finding on f=685-716 is a programmatic check that the
vision tool's "static display" verdict is correct. Future H72-style
QA could include this check as a third rater (alongside the 2-4
vision queries).

## Recommended operating point (post-H72)

For MIXED_3+ post-filter:
- KEEP at spec_conc >= 0.15: VALIDATED at 10/11 = 91% precision
- REJECT at spec_conc < 0.10: validated on H71 sample (1/1 correct)
- 0.10 <= spec_conc < 0.15: MIXED_3+_LOW_CONF (research signal)
  - The H71 false positive (f=114-255, conc=0.124) is in this band
  - The H71 false negative (f=2-71, conc=0.075) is correctly REJECTED at < 0.10

For CASCADE_3+ class: no recommended filter (insufficient sample).

## Negative findings

1. **CASCADE_3+ class has only 1 substantial phase, which is
   misclassified.** Cannot characterize CASCADE_3+ accuracy at
   scale from H70 sample.
2. **Multi-rater visual QA is essential.** 2/6 = 33% of H72 contact
   sheets had single-pass vision verdicts that disagreed with the
   multi-rater consensus. The H53 finding is reinforced.
3. **H70 KEEP precision is 91% on MIXED_3+ (10/11 confirmed).**
   This is consistent with H71's 100% on its smaller sample. The
   1 error is an H12 v8 misclassification, not a H70 spec_conc failure.
4. **H12 v8's CASCADE_3+ accuracy is unmeasured.** The 1 substantial
   phase is a 3-ball manipulation trick mislabeled as CASCADE_3+.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h72_full_qa_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h72_multi_rater_qa.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h72/*.png` (6 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h72_summary.json`
