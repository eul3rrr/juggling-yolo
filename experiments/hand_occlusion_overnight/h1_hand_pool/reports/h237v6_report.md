# H237 v6 — Unified chain representation based on H7v2 chains with H7v2 reclassification metadata

## Purpose
The h237v5 unified representation used H7 chains (union-find with
H2 BALLISTIC edges) and H10 v5 quality. After H7v2's reclassification,
the chain structure is different and the H10 v5 quality over-penalizes
chains with many "BALLISTIC" edges that are really catch+throws.

H237 v6 fixes this by using H7v2 chains (reclassified BALLISTIC
edges as HAND_TRANSITION) and H10 v8 quality. It also adds explicit
`n_reclassified_edges` and `pct_reclassified` per chain, which are
useful for downstream consumers wanting to distinguish "mostly
hand-edge" vs "mostly ballistic" chains.

## Output
- `data/h237v6_unified_chains_<stem>.csv` (2 files)
- `data/h237v6_unified_summary.json`
- `scripts/h237v6_unified.py`

## Per-chain fields
- `chain_id`, `n_tracklets`, `first_frame`, `last_frame`, `tids`
- `n_hand_edges`: total hand edges (HAND + AMBIGUOUS + RECLASSIFIED)
- `n_reclassified_edges`: subset of n_hand_edges that were reclassified
- `n_ballistic_edges`: edges that remain BALLISTIC (true identity switches)
- `n_ambiguous_hand_edges`: AMBIGUOUS_HAND_TRANSITION edges
- `pct_reclassified`: 100 * n_reclassified / n_hand
- `n_h3_confirmed`, `h3_score`, `h8_score`, `h9_score`, `h8v8_score`
- `h10_v8_quality`, `h10_v8_rank`

## Quantitative result

### identical (43 chains, 17 multi-tracklet)
- 4 chains are pure-ballistic (no hand edges, only BALLISTIC edges):
  - These are likely the "true" identity switches that the H7v2
    reclassification correctly preserved
- 3 chains are pure-reclassified (all hand edges were reclassified):
  - These are catch+throws in disguise that v6 correctly attributes
    to hand interactions
- Top 5 multi-tracklet chains:
  - chain 21 (2 tids, 1 ballistic): q=0.908
  - chain 20 (2 tids, 1 ballistic): q=0.867
  - chain 8 (2 tids, 1 hand): q=0.836
  - chain 29 (2 tids, 1 ballistic): q=0.668
  - chain 4 (2 tids, 1 hand + 1 reclassified): q=0.668

### YouTube (15 chains, 9 multi-tracklet)
- 0 chains are pure-ballistic: all multi-tracklet YouTube chains
  are now correctly attributed to hand interactions
- 7 chains are pure-reclassified (all hand edges were reclassified):
  - Real juggling cycles
- Top 5 multi-tracklet chains:
  - chain 6 (2 tids, 1 hand): q=0.841
  - chain 3 (4 tids, 3 hand all reclassified): q=0.680
  - chain 8 (4 tids, 3 hand all reclassified): q=0.676
  - **chain 0 (7 tids, 6 hand all reclassified): q=0.671** —
    real 7-tid juggling cycle
  - chain 7 (4 tids, 3 hand all reclassified): q=0.616

## Verdict: **PASS**

H237 v6 provides a cleaner unified chain representation:
- All YouTube multi-tracklet chains are correctly attributed
  to hand interactions (no pure-ballistic chains)
- identical still has 4 pure-ballistic chains (true identity
  switches preserved)
- The `n_reclassified_edges` field gives downstream consumers
  a clear signal of which chains are "mostly hand interactions
  in disguise"

## Artifacts
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h237v6_unified.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v6_unified_chains_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v6_unified_summary.json`
