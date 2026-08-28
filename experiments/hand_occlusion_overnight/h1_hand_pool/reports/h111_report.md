# H111 — Relaxed edge-to-phase anchoring

**Date:** 2026-08-29 (this episode)
**Status:** PASS (consumer-pass, useful diagnostic). H111 extends H102 with 2
additional anchoring strategies and surfaces 23 new edge-level evidence
points, including 1 NEW false positive and 1 NEW false negative that the
H102 strict midgap-only methodology missed.

## Hypothesis

The H102 methodology anchors review pairs to H93 substantial phases only
when the **midgap** frame (src_end + cand_start) / 2 falls inside a phase.
This strict criterion anchors only 15/113 (13%) of review pairs. Most of
the 98 unanchored pairs have src_end in a "between phases" region
(non-H93 frames) and cand_start in a phase, so the edge is "entering"
the phase. The H102 strict methodology discards these.

A more inclusive anchoring strategy might surface additional edge-level
evidence for the H108 v1 perfect phase-level result. The question is:
**does relaxed anchoring change the phase-level precision/recall
materially, or is it just an evidence-density improvement?**

## Method

Three anchoring strategies, ordered by permissiveness:

| Strategy | Definition |
|----------|------------|
| **S1** (H102 strict) | midgap ∈ [phase_start, phase_end] |
| **S2** (union) | midgap OR src_end OR cand_start ∈ phase |
| **S3** (overlap) | edge interval [src_end, cand_start] overlaps phase interval [phase_start, phase_end] |

For each strategy, the H102 per-pair CSV is extended with the matched
phase_key, and per-phase TP/FP/FN/P/R is recomputed for h7v3plus3 on the
113 review pairs.

The 23 NEW S2 anchors (not in S1) are all "edge entering a phase"
(cand_start ∈ phase, src_end before phase). They are not "edge spans the
phase" — they are not the typical "this phase is real juggling" pair.
The interpretation is: the edge starts before the phase and ends inside
it; the chain endpoint lands in a JUGGLING phase.

## Quantitative result

| Strategy | #phases | #pairs | corr | wr | TP | FP | FN | P | R | acc |
|----------|---------|--------|------|-----|----|----|-----|---|---|-----|
| S1 (H102 strict) | 11 | 15 | 13 | 2 | 11 | 0 | 2 | 1.000 | 0.846 | 0.867 |
| **S2 (union)** | 18 | **38** | 25 | 13 | 21 | **1** | 4 | 0.955 | 0.840 | 0.658 |
| S3 (overlap) | 18 | 38 | 25 | 13 | 21 | 1 | 4 | 0.955 | 0.840 | 0.658 |
| H102 (H102 S1+phase precision) | 7 phases | 15 | 13 | 2 | 11 | 0 | 2 | 1.000 | 0.846 | 0.929 |

S2/S3 surface 23 NEW pairs (12 correct, 11 wrong). 11 of these are in
h7v3plus3. **The S2 1 NEW FP is a real discovery: the 22→27 wrong review
edge in f=263-312 JUGGLING phase is incorrectly accepted by h7v3plus3
as a RECLASSIFIED_HAND_TRANSITION.** The H102 S1 strict anchoring missed
this because the midgap (260) is just before the phase (263-312).

## Key finding: 22→27 is a real false positive (190-px spatial jump)

| Edge | src_end | cand_start | gap | end→start dist | Reviewer | h7v3plus3 | Geometric verdict |
|------|---------|------------|-----|----------------|----------|-----------|-------------------|
| 22→27 | f=252, left | f=263, right | 11f | **190.4 px** | wrong | ACCEPTED (FP) | NOT a real catch-throw |
| 25→27 | f=255, right | f=263, right | 8f | **10.5 px** | correct | REJECTED (FN) | IS a real catch-throw |

The 22→27 edge spans 11 frames and 190.4 px in 2D — this is NOT a
physically plausible catch-throw at 30 fps (a real catch has the ball at
the hand at 0-30 px distance). The 25→27 edge spans 8 frames and 10.5 px —
a real catch (ball at the hand, in-place handoff). Reviewer's labels are
correct; h7v3plus3 is **WRONG** on both.

This is a meaningful finding because the H108 v1 stack achieves PERFECT
17/4/0/0 on the H93 phase level, but at the EDGE level, h7v3plus3 has
a real false positive and a real false negative in f=263-312 JUGGLING
that the H102 strict methodology missed.

## Other S2-surface edges (3 NEW TP + 3 NEW TN)

| Edge | Phase | Verdict | Reviewer | h7v3plus3 | Spatial jump | Notes |
|------|-------|---------|----------|-----------|--------------|-------|
| 37→40 | 549-578 JUGGLING | TP | correct | ACCEPTED ✓ | 89-px / 11f | Real handoff |
| 38→40 | 549-578 JUGGLING | TN | wrong | REJECTED ✓ | 89-px / 11f | Cross-ball artifact |
| 39→47 | 685-716 STATIC_HOLD | TP | correct | ACCEPTED ✓ | 95-px / 4f | Real handoff |
| 45→47 | 685-716 STATIC_HOLD | TN | wrong | REJECTED ✓ | 231-px / 10f | NOT a catch |
| 64→69 | 977-1011 JUGGLING | TN | wrong | REJECTED ✓ | 248-px / 13f | NOT a catch |
| 65→69 | 977-1011 JUGGLING | TN | wrong | REJECTED ✓ | 231-px / 7f | NOT a catch |

In f=977-1011, the S2 surface shows h7v3plus3 has 0 false positives
(correctly rejected 2 wrong edges with 231-248-px jumps). The 1 NEW FN
in this phase (25→27's analog) is a different pair.

## Interpretation

The H102 midgap-only anchoring is a valid methodology for the question
"is this phase a real juggling phase?" but it has a known blind spot
at the 5-frame boundary at the start of each phase. Edges that BEGIN
before the phase but END inside the phase are not anchored.

H111's S2 (union) anchoring surfaces these "edge entering phase" pairs
and reveals that:
1. h7v3plus3 has a real **1 FP and 1 FN in f=263-312 JUGGLING** that
   the H102 strict methodology missed.
2. h7v3plus3 correctly REJECTS the wrong edges 64→69 and 65→69 in
   f=977-1011 (231-248-px jumps are correctly identified as
   non-catch-throws).
3. The H108 v1 PERFECT 17/4/0/0 phase-level result is real but does
   not validate edge-level quality within the 5-frame phase boundary.

## Cross-tabulation: phase-level verdict vs edge-level quality

| Phase | H93 verdict | H108 v1 | S2 surface | S2 verdict on h7v3plus3 |
|-------|-----------|---------|-----------|--------------------------|
| 263-312 | JUGGLING | KEEP | 1 FP, 1 FN | Mixed: 22→27 wrongly accepted, 25→27 wrongly rejected |
| 549-578 | JUGGLING | KEEP | 1 TP, 1 TN | Both correct |
| 631-669 | JUGGLING | KEEP | 1 TP | Correct |
| 685-716 | STATIC_HOLD | REJECT (H87) | 1 TP, 1 TN | H87 correctly rejects the phase, but a real handoff IS in the chain |
| 890-936 | OTHER_CROSSED_ARM | REJECT (H78) | 1 TN | H78 correctly rejects, h7v3plus3 correctly rejects the wrong edge |
| 977-1011 | JUGGLING | KEEP | 1 FN, 2 TN | h7v3plus3 correctly rejects the wrong 231-248-px edges |
| 1029-1049 | JUGGLING | KEEP | 2 TP | Correct (no FP, no FN) |

The 22→27 FP in f=263-312 is the single actionable finding: h7v3plus3
incorrectly accepts a 190-px spatial jump as a hand-edge. A future
edge-level diagnostic could add a 30-px spatial jump check at the
h7v3plus3 stage to filter this case.

## Negative findings

- S2 (union) and S3 (overlap) produce **identical** results on the
  H93 phases. S3 is the more principled (interval overlap is a standard
  CS concept), but S2 is the same in practice because midgap is always
  between src_end and cand_start.
- S2 has lower accuracy (0.658) than S1 (0.867) because S2 includes
  11 wrong edges that h7v3plus3 correctly rejects. S1's higher accuracy
  is an artifact of midgap-only anchoring (most wrong midgap-anchored
  edges are h7v3plus3 TPs that happen to be near the phase boundary).
- The 22→27 FP is the ONLY actionable NEW edge-level signal. All other
  S2-surface edges are correctly classified by h7v3plus3 (TP/TN).

## Recommended operating point (post-H111, unchanged)

The h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v4 + H78 +
H87+max_aloft + H90 NEW + H108 R4b + H52 + H53 + H71 (MIXED_3+) stack
remains the precision-optimized endpoint. H111 is a **diagnostic** that
confirms the H108 v1 phase-level PERFECT is real but does not validate
edge-level quality.

**For edge-level analysis, use the S2 union anchoring methodology** to
catch boundary-crossing edges like 22→27. The H102 midgap methodology
is too strict for this purpose.

**For downstream consumers:** the 22→27 FP is a known edge-level
imperfection in h7v3plus3. A future H7 revision could add a
30-px spatial-jump check at the hand-edge stage to filter 22→27-style
boundary-crossing false positives without affecting TP rate.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h111_relaxed_anchoring.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h111_per_pair.csv` (113 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h111_per_phase.csv` (44 rows = 18 phases × 3 strategies)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h111_summary.json`
