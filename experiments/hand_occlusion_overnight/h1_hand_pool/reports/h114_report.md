# H114 — Same-hand large-jump filter for h7v3plus3 hand edges

**Date:** 2026-08-29 (this episode)
**Status:** **NEGATIVE** for chain precision, **PASS** as post-hoc validation tool.
H114 (same-hand variant of H112) does NOT improve chain precision because the
h7v3plus3 chain algorithm already correctly excludes all same-hand wrong
edges. However, the v1 (spatial_jump + end_d + start_d) rule provides a
useful **post-hoc validation signal** that confirms the chain's correct
rejections on 10-23 NOT-in-chain wrong edges without affecting the chain.

## Hypothesis

H112 restricted its cross-hand handoff filter to a single false positive
(22→27 in f=263-312 JUGGLING, 190-px spatial jump, src.end_d=46.7 to LEFT,
tgt.start_d=56.2 to RIGHT). The H112 future-research direction proposed a
same-hand variant at higher threshold to catch additional same-hand
large-jump FPs.

**H114 hypothesis:** a same-hand large-jump filter (no `cross_hand`
requirement) at threshold (T_d, T_j) would catch additional wrong
hand-classified edges that the H112 cross-hand rule missed.

**Physical-geometry justification (per master §15):** a real catch-throw
places the ball within ~30 px of the hand at the catch/throw frame. A
spatial jump > 150 px in 12 frames is physically implausible for a real
catch-throw — the ball would need to teleport from source-end to
target-start, which only happens when the chain algorithm stitched two
unrelated tracklets.

## Method

Two rule variants tested:
- **v1**: reject if `spatial_jump > T_j` AND `end_d > T_d` AND
  `start_d > T_d` (and optionally `cross_hand` filter)
- **v2**: H112 rule without `cross_hand` requirement:
  `end_d > T_d` AND `start_d > T_d`

20 v1 thresholds × {30, 40, 50, 60, 80} × 4 jump levels.
6 v2 thresholds: T_d ∈ {30, 40, 50, 60, 80, 100}.

Evaluation scope: **all 113 manually reviewed pairs**, not just the
h7v3plus3 admitted subset, to test whether the rule is a precision
improvement in general — including the question "would this filter
have caught wrong edges that the chain missed?"

## Quantitative result

### v1 (spatial_jump + end_d + start_d) per-threshold flat region

| T_d | T_j | in-chain wrong caught | in-chain correct dropped (FN) | NOT-in-chain wrong caught |
|----:|----:|----------------------:|------------------------------:|---------------------------:|
| 30  |  80 |                     1 |                             5 |                         23 |
| 30  | 100 |                     1 |                             4 |                         23 |
| 30  | 150 |                     1 |                             3 |                         19 |
| 30  | 200 |                     0 |                             1 |                         17 |
| 40  | 100 |                     1 |                             3 |                         18 |
| 40  | 200 |                     0 |                             1 |                         13 |
| 40  | 250 |                     0 |                             0 |                         10 |
| 50  | 100 |                     0 |                             3 |                         13 |
| 50  | 200 |                     0 |                             1 |                          9 |
| 50  | 250 |                     0 |                             0 |                          7 |
| 60  | 150 |                     0 |                             1 |                          5 |
| 60  | 200 |                     0 |                             1 |                          5 |
| 60  | 250 |                     0 |                             0 |                          4 |
| 60  | 300 |                     0 |                             0 |                          4 |
| 80  | 200 |                     0 |                             0 |                          2 |
| 80  | 250 |                     0 |                             0 |                          2 |
| 80  | 300 |                     0 |                             0 |                          2 |

**Best v1 operating point (T_d=40, T_j=250):** 0 in-chain wrong caught,
0 in-chain correct dropped, 10 NOT-in-chain wrong caught. Pure post-hoc
validation signal — does not change the chain.

**T_d=30, T_j=80 v1 setting (most aggressive):** catches 1 in-chain wrong
(22→27, the H112 FP — but H112 already catches this), but drops 5 in-chain
correct edges (3→8, 7→10, 23→25, 1→6, 4→7). Net precision cost: 5 FN for
0 new in-chain TN. Not a precision improvement.

### v2 (H112 without cross_hand) per-threshold — CATASTROPHIC regression

| T_d | in-chain wrong caught | in-chain correct dropped (FN) |
|----:|----------------------:|------------------------------:|
|  30 |                     1 |                            15 |
|  40 |                     1 |                            12 |
|  50 |                     0 |                            12 |
|  60 |                     0 |                             9 |
|  80 |                     0 |                             7 |
| 100 |                     0 |                             6 |

**v2 at T_d=30:** catches only the H112-discovered 22→27 FP (cross-hand)
but drops 15 in-chain CORRECT edges including 3→8 (RECLASSIFIED),
7→10 (H26_RECLASSIFIED), 19→20 (BALLISTIC), 23→25 (V_RECLASSIFIED),
28→29 (BALLISTIC). Removing the cross_hand requirement destroys
precision.

**Verdict on v2:** NEGATIVE. The cross_hand requirement is essential;
H112's design is correct as-is.

### Edge-level summary

- The h7v3plus3 chain has **ZERO same-hand wrong edges in its 51 hand-
  classified admitted set**. The chain algorithm's same-hand handling
  is already correct.
- The H114 v1 (T_d=40, T_j=250) post-hoc rule would catch **10 of the
  42 NOT-in-chain wrong edges** without affecting the chain. The other
  17 NOT-in-chain same-hand wrong edges have either small spatial jumps
  (< 80 px) or small end/start distances (< 30 px) — they were
  rejected by the chain for other reasons (cost, capacity, mid-air
  prediction error), not for being implausible jumps.

### Why H114 same-hand filter cannot be a precision improvement

Three reasons:

1. **No same-hand wrong edges are in h7v3plus3.** The chain algorithm's
   cost-based selection and capacity constraints already exclude them.

2. **Many in-chain correct edges have large spatial jumps.** The
   `RECLASSIFIED_HAND_TRANSITION` class in h7v3plus3 explicitly handles
   cases where the detector dropped the ball mid-hold — the source's
   last detection and target's first detection are at very different
   positions because the held phase is invisible. Examples: 3→8
   (sj=227, end=106, start=71), 7→10 (sj=156, end=50, start=72),
   23→25 (sj=101, end=77, start=83), 39→47 (sj=72, end=174, start=109).

3. **The H112 cross_hand restriction is essential.** v2 (H112 without
   cross_hand) drops 15 in-chain correct edges at T_d=30. The reason
   is that real same-hand catch-throws can have large spatial jumps
   when the ball moves between two positions on the same hand (e.g.,
   a thumb-to-palm transfer during a held phase, or a hand-cupping
   adjustment). The ball's distance to the wrist is meaningful only
   for cross-hand handoffs where the source and target hands are
   spatially separated.

## Visual QA (4 contact sheets at `contact_sheets_h114/`)

### 14→18 (WRONG, NOT in chain, sj=321, end=53, start=289) — confirmed false

Vision verdict: "a 321-px jump in 0 frames means **infinite velocity**"
and is not a real catch-throw. The two markers (green at f=160, red at
f=166) are clearly separated by a substantial horizontal/vertical
distance with no intermediate frame showing a ball. This is a tracker
identity swap or occlusion artifact, not a real handoff. The H114 v1
filter correctly catches this edge.

### 3→8 (CORRECT, IN chain, sj=227, RECLASSIFIED_HAND_TRANSITION) —

Vision verdict: "Likely a False Positive" — the ball is far from the
left hand at both endpoints (106 px and 71 px) and the 227-px jump in
6 frames is suspiciously large. The H7 algorithm originally chose
3→9 (hand-edge cost 1.5) over 3→8 (air-edge cost 2.92) as the conflict
resolution; 3→8 is in h7v3plus3 because the H7v2 reclassification logic
downgraded the air-edge to HAND_TRANSITION when it passed through a
hand region. The reviewer marked 3→8 "correct" but the visual evidence
is ambiguous. The H114 v1 filter would drop 3→8 (FN cost), but this
is consistent with the H7 algorithm's own judgment that 3→9 is the
correct successor.

### 7→10 (CORRECT, IN chain, sj=156, H26_RECLASSIFIED) — confirmed real

Vision verdict: "legitimate catch-throw" — the 156-px jump in 2 frames
is the **distance between the two different hands (h7 and h10)** at the
moment of the throw, not the ball traveling. The ball is occluded
during the handoff. The H24 visual QA correctly identified this as
V_SHALLOW — a real catch-throw that the strict h7v2 velocity-based
rule rejected. The H26 chain correction recovered it. The H114 v1
filter at T_j=200 (which is the most permissive setting that catches
3→8 as FP) would NOT drop 7→10.

### 65→69 (WRONG, NOT in chain, sj=231, end=243, start=76) — confirmed false

Vision verdict: "not a real catch-throw" — the 231-px jump in 1 frame
with start_d=76 (ball not at left hand) and end_d=243 (ball very far
from left hand) is physically implausible. The H114 v1 (T_d=50, T_j=200)
filter correctly catches this edge.

## Why H114 is "NEGATIVE for chain precision, PASS as post-hoc validation"

| Aspect | H114 v1 (T_d=40, T_j=250) | H114 v1 (T_d=30, T_j=80) | H114 v2 (T_d=30, NO cross) |
|--------|---------------------------:|-------------------------:|----------------------------:|
| In-chain wrong caught | 0 | 1 | 1 |
| In-chain correct dropped (FN) | 0 | 5 | **15** |
| In-chain precision change | 0 | -0.10 (5/46) | -0.30 (15/46) |
| NOT-in-chain wrong caught | 10 | 23 | 24 |
| Status | POST-HOC PASS | NEGATIVE | NEGATIVE |

**The (T_d=40, T_j=250) operating point is a pure post-hoc validation
signal:** it catches 10 wrong edges that the chain already rejected,
without dropping any chain-correct edges. The (T_d=30, T_j=80) and v2
settings are precision-negative (FN cost > FP reduction).

**Recommended operating point (post-H114):** unchanged from H112.
H112 is the recommended cross-hand filter (1 FP caught, 0 FN added).
H114 v1 at (T_d=40, T_j=250) is recommended as a **diagnostic tool**
to confirm that the chain's same-hand rejections are physically
justified by large spatial jumps.

## Why the h7v3plus3 chain's same-hand handling is correct

The chain algorithm distinguishes:
- **HAND_TRANSITION** (same hand, ball at hand, < 30 px reach): real
  catch-throw on the same hand.
- **AMBIGUOUS_HAND_TRANSITION** (same hand, ball at hand, FIFO
  ambiguous): real catch-throw but identity ambiguous.
- **RECLASSIFIED_HAND_TRANSITION** (originally BALLISTIC air-edge,
  reclassified because it passes through a hand region during the
  gap): catch-throw where the detector dropped the ball during the
  held phase.
- **V_RECLASSIFIED_HAND_TRANSITION** (V-shape trajectory check
  upgraded from BALLISTIC): catch-throw that the chain would have
  classified as mid-air but the V-shape check confirms the trajectory
  dipped into a hand region.
- **H26_RECLASSIFIED_HAND_TRANSITION** (H24/H26 visual-QA-upgraded
  from BALLISTIC): visually-confirmed real catch-throw that the
  strict h7v2 rule missed.

The chain's handling of same-hand large-spatial-jump edges is correct
because these edge types are PHYSICALLY REAL: the ball was caught and
re-thrown, but the detector's mid-hold dropout makes the endpoints
appear far apart. A naive same-hand large-jump filter would
incorrectly reject these.

## Recommended operating point (unchanged from H112)

```
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v4 + H78 +
H87+max_aloft + H90 NEW + H108 R4b + H52 + H53 + H71 (MIXED_3+) +
H112 (cross_hand AND end>30 AND start>30)
```

- 21 H93 phases: 17/4/0/0, P=1.000, R=1.000, acc=1.000 (unchanged)
- 113 review pairs: P=1.000, R=0.718, FPR=0.000 (unchanged from H112)
- H114 v1 (T_d=40, T_j=250) is a **recommended diagnostic**:
  for any future chain revision, run this filter on the candidate
  edges and verify that the 10 NOT-in-chain wrong edges it catches
  are real (i.e., the chain is correctly rejecting them).

## Future research directions (post-H114)

1. **H115: H114 v1 as a candidate generator.** The 10 NOT-in-chain
   wrong edges caught by H114 v1 (T_d=40, T_j=250) are all edges
   the chain already rejected. A H115 experiment could take a
   DIFFERENT chain algorithm (e.g., H21 v1, which uses H20-KEPT
   edges) and check whether H114 v1 catches wrong edges in that
   chain set. H21 v1 admits H20-KEPT edges with weaker geometric
   constraints; H114 might surface wrong edges in H21 v1 that are
   not in h7v3plus3.
2. **H116: H114 v1 on 3rd video (weave).** The 3rd video (H101
   weave) has no manual review labels, but it has chain edges
   from h7v3plus3-equivalent processing. H114 v1 would be a
   pure-diagnostic check: do any weave h7v3+ edges trigger the
   H114 v1 same-hand large-jump rule? If yes, those edges deserve
   visual QA.
3. **Stop here.** H112 + H114 confirm that the cross-hand vs
   same-hand distinction is essential for hand-edge geometric
   filters. The h7v3plus3 chain's edge-type-specific handling
   (RECLASSIFIED, V_RECLASSIFIED, H26_RECLASSIFIED) is correct.
   Further edge-level precision improvements would require
   fundamentally different signals (3D ball estimation, learned
   color tracking, or a re-trained chain algorithm).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h114_same_hand_jump_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h114_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h114_per_edge.csv` (113 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h114_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h114/h114_*.png` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h114_report.md` (this file)
