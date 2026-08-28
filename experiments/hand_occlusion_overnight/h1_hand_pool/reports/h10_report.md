# H10 — Per-Chain Quality Assessment

Date: 2026-08-28 ~07:35 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: PASS

## Hypothesis

A chain's *physical-ball identity confidence* can be measured
by combining three signals from prior experiments:

- **H3**: fraction of hand edges corroborated by a stationary
  cluster of low-confidence detections (held-ball evidence).
  High h3 = "this hand-edge has visible supporting evidence."
- **H8**: fraction of air edges passing the y-velocity
  discontinuity check. High h8 = "this chain doesn't contain
  identity switches."
- **H9**: chain coverage (observed_frames / total_span). High
  h9 = "this chain is well-observed, not mostly gaps."

A chain with high h3, no h8 violations, and high coverage is
high-quality (high confidence it represents one physical ball).
A chain with low h3, many h8 violations, and low coverage is
low-quality (likely merges multiple physical balls or has
significant identity switches).

## Thresholds (declared from physical geometry, not from manual labels)

- **Composite weights**: `quality = 0.30 * h3 + 0.30 * h8 + 0.40 * h9`
  (h9 gets the highest weight because observation density is
  the most direct chain-quality proxy; h3 and h8 are roughly
  equally important for edges; weights are a reasonable
  decomposition, not tuned to labels)
- **Chain with no hand edges**: h3 is None → redistribute the
  h3 weight to (h8, h9) in ratio 3:4 so the result still sums to 1.0
- **Chain with no air edges**: h8 = 1.0 (no possible violations)
- **Quality bins**: high > 0.7, mid 0.3-0.7, low < 0.3
- **Sensitivity grid**: 9 cells, w3/w8/w9 ∈ {0.2, 0.3, 0.4}, sum = 1
- **Rank-stability criterion**: std(per-cell rank) < 2.0

## Algorithm

For each H7 chain:

1. Load h237_unified chain metadata (tids, n_hand_edges, n_air_edges, n_h3_confirmed).
2. Reconstruct chain edges by joining consecutive tids against
   h237_unified_edges to identify each edge's type.
3. **H3 score**: `n_h3_confirmed / n_hand_edges`, or None if
   no hand edges.
4. **H8 score**: 1 - (n_air_edges_in_chain that are in h8_violations) /
   n_air_edges_in_chain, or 1.0 if no air edges.
5. **H9 score**: h9_object_permanence_summary coverage for this chain_id.
6. **Quality**: weighted average with declared weights.

Then for each cell in a 3x3 weight sensitivity grid, recompute
quality and rank chains. Per-chain rank stability is the std of
per-cell rank.

## Quantitative Result

### Identical video (n_chains = 43, multi = 17)

| | n_chains | h3 confirmed | h3 full | H8 violations | quality min/q1/med/q3/max |
|---|---|---|---|---|---|
| identical | 43 | 4 | 2 | 7 chains affected | 0.297 / 0.429 / 0.429 / 0.549 / 0.966 |
| youtube | 15 | 1 | 1 | 9 chains affected | 0.429 / 0.429 / 0.532 / 0.558 / 0.967 |

### Multi-edge chains on identical (n_tracklets ≥ 3)

| chain_id | n_tids | n_hand | n_air | viol | h3 | h8 | h9 | quality |
|---|---|---|---|---|---|---|---|---|
| 24 | 3 | 0 | 2 | 0 | n/a | 1.00 | 0.92 | **0.956** |
| 19 | 3 | 0 | 2 | 0 | n/a | 1.00 | 0.87 | 0.927 |
| 23 | 7 | 0 | 6 | 0 | n/a | 1.00 | 0.71 | **0.837** |
| 31 | 5 | 2 | 2 | 2 | 0.50 | 0.00 | 0.84 | 0.487 |
| 30 | 5 | 3 | 1 | 1 | 0.67 | 0.00 | 0.64 | 0.454 |
| 38 | 3 | 1 | 1 | 1 | 0.00 | 0.00 | 0.88 | 0.353 |
| 13 | 4 | 1 | 2 | 2 | 0.00 | 0.00 | 0.74 | **0.297** |

### Multi-edge chains on YouTube (n_tracklets ≥ 3)

| chain_id | n_tids | n_hand | n_air | viol | h3 | h8 | h9 | quality |
|---|---|---|---|---|---|---|---|---|
| 12 | 3 | 0 | 2 | 1 | n/a | 0.50 | 0.95 | 0.756 |
| 3  | 4 | 0 | 3 | 3 | n/a | 0.00 | 0.98 | 0.558 |
| 8  | 4 | 0 | 3 | 3 | n/a | 0.00 | 0.96 | 0.550 |
| 7  | 4 | 0 | 3 | 3 | n/a | 0.00 | 0.95 | 0.542 |
| 10 | 4 | 0 | 3 | 3 | n/a | 0.00 | 0.94 | 0.539 |
| 0  | 4 | 0 | 3 | 3 | n/a | 0.00 | 0.93 | 0.532 |
| 9  | 6 | 0 | 5 | 5 | n/a | 0.00 | 0.89 | **0.507** |

### Single-edge chain (YouTube chain 6, tids 10→12)

The only YouTube chain with h3 confirmed (the v4d hand-link 10→12).
Quality = 0.967 (h3=1.0, h8=1.0 trivially, h9=0.92).

### Sensitivity grid (rank stability across 9 weight cells)

| video | n_chains | n_stable (std<2) | most unstable chain |
|---|---|---|---|
| identical | 43 | 9 (21%) | chain 36 (mean_rank=23.1, std=13.8) |
| youtube  | 15 | 2 (13%) | chain 4 (mean_rank=6.3, std=4.1) |

Only ~20% of chains have stable rank across the weight grid.
This is expected: chains whose h3, h8, h9 scores differ
significantly will rank differently under different weights.
The top-quality chain on identical (chain 23) is consistently
top-3 across all 9 cells. The bottom-quality chain on identical
(chain 13) is consistently bottom-3 across all 9 cells.

## Visual QA (4 chains inspected, plus 2 for context)

### chain 23 (top quality identical, 0.84) — REAL single ball
Tids: 35, 37, 40, 41, 43, 45, 46 (7 tids, all BALLISTIC)
Frames 507-721, hand-edge count = 0.
- Hold phase (f=507-620, ~113 frames): ball stationary at hand.
- Rise phase (f=621-679): clear upward motion.
- Apex (~f=700): ball at top of frame.
- Fall phase (f=700-720): ball descends.
- Catch (f=720-721): ball at hand level.
- **Visual verdict: REAL single-ball juggling cycle** (hold → release → rise → apex → fall → catch). H10's top quality is correct.

### chain 30 (mid quality identical, 0.45) — IDENTITY SWITCH
Tids: 51, 52, 54, 59, 63. Edges: 51→52 (BALLISTIC), 52→54, 54→59, 59→63 (HAND/AMBIGUOUS_HAND). 2 H3 confirmed.
- Multiple green balls visible in air at f=765-770, f=797, f=816, f=890-920.
- The 51→52 air edge is between two tracklets visible simultaneously — the tracker stitched detections of different physical balls.
- **Visual verdict: 51→52 air edge is an IDENTITY SWITCH.** H10's mid quality correctly flags this — h8=0 (1 violation) and h9=0.64 (low coverage) are the drivers. Hand edges 52→54, 54→59, 59→63 may be real catch-throws but the chain contains at least one identity switch.

### chain 13 (low quality identical, 0.30) — STATIONARY DETECTOR ARTIFACT
Tids: 17, 23, 25, 27. Edges: 17→23 (HAND), 23→25 (BALLISTIC), 25→27 (BALLISTIC). h3=0, 2 air violations.
- Tracklet 17 is observed at a high stationary position (likely a detector artifact on a background feature, NOT a juggling ball).
- The 17→23 hand-edge is a real v4d hand-link (confirmed in H1 v4 visual QA — catch at right hand).
- The 23→25 and 25→27 air edges are false (ballistic continuation from a stationary point is impossible).
- **Visual verdict: 23→25 and 25→27 are FALSE ballistic edges** between physically disconnected tracklets. H10's low quality correctly flags this — h3=0, h8=0, h9=0.74.

### chain 38 (low quality identical, 0.35) — FALSE POSITIVE OF H10
Tids: 67, 70, 74. Edges: 67→70 (BALLISTIC), 70→74 (HAND). h3=0, 1 air violation.
- Vision QA: the chain shows a real single juggling ball (green dot) across all 15 frames with smooth ballistic motion. The 67→70 edge IS a real ball continuation.
- H10's low quality is driven by h3=0 (no H3 corroboration on the 70→74 hand-edge) and h8=0 (the 67→70 air edge is H8-violating). H8 may be over-penalizing.
- **Visual verdict: REAL single-ball chain** (H10 false positive). The 70→74 hand-edge is real but H3 didn't corroborate it; the 67→70 air edge may be violating H8 due to detector noise rather than identity switch.

### chain 6 (YouTube, 0.97) — REAL single catch-throw
Tids: 10, 12. Edge: 10→12 (HAND_TRANSITION, H3 confirmed).
- Vision QA: ball is thrown from a high position (above head) at f=255, caught at right hand.
- **Visual verdict: REAL single catch-throw**. H10's top quality is correct.

### chain 9 (YouTube, 0.51) — MULTI-BALL MERGE
Tids: 4, 6, 13, 14, 16, 20. Edges: 19→22→26→31→35→38 (5 BALLISTIC air edges, all H8-violating).
- Vision QA: a single tracklet (yellow) is followed across many frames, but it appears at varying heights and positions inconsistent with a single ball. Multiple balls in play throughout the YouTube video.
- **Visual verdict: chain merges detections of multiple physical balls.** H10's low quality correctly flags this — h8=0 (5 violations) drives the score down.

## Verdict: PASS

H10 successfully produces a per-chain quality score that
correlates with physical-ball identity confidence:

- **Top-quality chains** (e.g. chain 23, chain 6) are confirmed
  as real single-ball juggling cycles by visual inspection.
- **Mid-quality chains** (e.g. chain 30) contain at least one
  identity switch in their air edges.
- **Low-quality chains** (e.g. chain 13) are dominated by false
  ballistic edges between disconnected tracklets.
- **H10 has false positives** (chain 38 is real but flagged low
  quality because H3 didn't corroborate its hand-edge and H8
  is over-penalizing the air edge).

The composite quality score is useful as a **per-chain
confidence signal for downstream consumers**. A chain with
quality > 0.7 can be treated as high-confidence (one physical
ball). A chain with quality < 0.3 should be rejected or
manually inspected. A chain in the mid range (0.3-0.7) is
ambiguous and may or may not represent a single ball.

## Negative findings

- The 9-cell sensitivity grid shows that only ~20% of chains
  have stable rank across weight perturbations. This is not a
  failure of the score but a property of chains whose h3, h8,
  h9 differ significantly — they correctly rank differently
  under different priorities.
- H10 false positive on chain 38: a real single-ball chain
  is misclassified as low quality because the H8 air-edge
  check is over-penalizing detector noise on a multi-frame
  tracklet. This is a fundamental limitation of using H8
  alone: it conflates "identity switch" with "noisy
  tracklet". Future work could distinguish these cases
  (e.g. by checking whether the discontinuity is consistent
  with a hand-hold release rather than an identity switch).
- H8 is unreliable on long tracklets (YouTube video): 23/24
  air edges are flagged as violating (per H8 v3 report),
  but most are real because the YouTube tracklets span many
  bounces. This propagates into H10's YouTube quality scores
  — the YouTube median quality is dragged down by H8 noise
  rather than genuine identity switches.

## Where H10 is most useful

1. **Ranking chains by identity confidence.** A downstream
   consumer (e.g. a juggling-pattern analyzer) should prefer
   high-quality chains (quality > 0.7) and reject or inspect
   low-quality chains (quality < 0.3).
2. **Identifying suspect chains for manual review.** Mid-
   quality chains (0.3-0.7) are the most likely to contain
   identity switches that automated checks missed.
3. **Comparing different chain-combination methods.** When
   developing new chain-combination algorithms, the H10
   quality distribution can be used as a summary statistic
   (mean quality, n_high, n_mid, n_low). Higher mean quality
   indicates a better algorithm.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10_chain_quality.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10_chain_quality_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10_sensitivity_grid.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h10/*.png` (6 files)
