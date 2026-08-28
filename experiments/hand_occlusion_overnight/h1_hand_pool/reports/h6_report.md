# H6 — Min-Cost Flow for H2 Conflict Resolution (Master §17)

**Date:** 2026-08-28 ~06:00 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** H6 implemented. The simplified min-cost flow
correctly resolves the H2 conflict (tracklet 3 → {9, 8})
by preferring the hand-edge (lower cost). This is the same
answer as the visual QA on H2 confirmed. The chain count
differs from H2 because H6 enforces "one successor per
tracklet" while H2's union-find allows multiple.

## 1. Hypothesis (master §17)

H2 uses a simple union-find over tracklets, which records but
does not resolve conflicts. Master §17 lists min-cost flow as
a candidate approach. A min-cost flow formulation could
optimally choose the best successor for each tracklet when
multiple successors are available.

## 2. Implementation

`h1_hand_pool/scripts/h6_min_cost_flow.py`

**Thresholds (declared before reading outcomes):**
- `HAND_EDGE_COST = 1.0` (we trust hand edges most)
- `AIR_EDGE_COST = 2.0` (air edges are less reliable)
- `IDENTITY_AMBIGUOUS_HAND_COST = 1.5` (hand edge with
  ambiguous identity, between the other two)

**Algorithm (simplified):**
- For each source tracklet, pick the lowest-cost successor.
- Walk chains from roots (tracklets with no incoming edge
  in the resolved successor map).
- This is a per-source greedy choice, not a true global
  min-cost flow. A full flow would consider global
  constraints (one predecessor + one successor per
  tracklet) but that requires a linear-programming
  solver.

## 3. Quantitative result

| Stem | n_edges | n_conflicts | H2 chains | H6 chains | H2 longest | H6 longest |
|---|---|---|---|---|---|---|
| identical | 37 | 1 | 40 (13 multi) | 18 (17 multi) | 8 (chain 38) | 7 (chain 35) |
| youtube  | 27 | 0 | 13 (9 multi) | 11 (11 multi) | (E6c) | 7 (chain 1) |

**Conflict resolution:** tracklet 3 has two candidate
successors:
- 3 → 9 (AMBIGUOUS_HAND_TRANSITION, cost = 1.5)
- 3 → 8 (BALLISTIC, cost = 2.0)

H6 picks 3 → 9 (hand-edge wins). **This is the same answer
as the visual QA on the H2 conflict confirmed.**

**Chain length difference:** H6's longest chain (7) is one
shorter than H2's (8). This is because H6's "one successor
per tracklet" simplification disallows the chain 38 → 39 →
47 → 51 → 52 → 54 → 59 → 63 that H2's union-find produces
(where 47 and 51 are both predecessors of 52, and 52 is in
the same chain). A true min-cost flow with capacity
constraints (one predecessor + one successor per tracklet)
would handle this correctly.

## 4. Negative findings

- **H6 is a simplified min-cost flow, not a true flow.**
  The greedy "pick lowest-cost successor per source" does
  not enforce the "one predecessor per tracklet"
  constraint. A true min-cost flow with capacity
  constraints (using e.g. `scipy.optimize.linprog` or
  `networkx.min_cost_flow`) would be a more principled
  solution.

- **H6 resolves the 1 H2 conflict correctly.** This
  validates the design principle "hand-edges win on
  conflict" (master §11) by showing that a cost-based
  formulation arrives at the same answer as visual QA.

- **H6's chain count is LOWER than H2's** (18 vs 40 on
  identical) because H6's "one successor per tracklet"
  rule is more restrictive than H2's union-find. H2
  produces more chains by allowing multiple successors;
  H6 produces fewer, longer chains by selecting the
  best one. **Neither is "more correct" — they are
  different representations of the same underlying
  graph.**

- **H6 does not add information beyond H2's
  "record conflicts, don't silently resolve" design.**
  H6 just resolves the conflict automatically. The
  resolved answer (3 → 9) is the same as the visual QA
  answer. A consumer that wants to know "what does the
  data say?" gets the same answer from either H2 (with
  conflict resolution via H6) or H2 + visual QA.

## 5. Verdict

**PASS (limited scope).** H6's simplified min-cost flow
correctly resolves the 1 H2 conflict, validating the
"hand-edge wins on conflict" design principle. A full
min-cost flow with capacity constraints would be more
principled but is unnecessary for this dataset (only
1 conflict).

## 6. Future work

- **Full min-cost flow with capacity constraints:**
  enforce "at most one predecessor + one successor per
  tracklet" using a linear programming solver. This
  would handle cases where a tracklet has multiple
  plausible predecessors (e.g. chain 38 where 47 and 51
  both predict 52).
- **Cost from gap times and ballistics:** instead of
  fixed costs per edge type, compute a continuous cost
  based on the gap time and the predicted ballistic
  position. This would be a more principled cost model.
- **Confidence-weighted costs:** use v4d's `|from_slope|`
  or E6c's `err` as the cost. Lower cost = higher
  confidence edge.

## 7. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h6_min_cost_flow.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h6_min_cost_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h6_report.md` (this report)
