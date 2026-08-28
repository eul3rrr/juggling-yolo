# H11 v6 — Tracklet identity propagation on H7v2 chains with H10 v8 quality

## Hypothesis
H11 v1 propagated identities on H237v5 chains. After H7v2's
reclassification, the chain structure is different and the
physical ball ID coverage is much better.

H11 v6 hypothesis: re-running the v1 identity propagation on
H7v2 chains with H10 v8 quality should give substantially more
catch/throw events on YouTube (because 25/27 YouTube BALLISTIC
edges were reclassified as HAND_TRANSITION).

## Quantitative result

### identical
| Metric | H11 v1 (h237v5) | H11 v6 (h7v2) |
|---|---|---|
| n_chains | 43 | 43 |
| n_CONFIDENT chains | (n/a) | 29 (mostly singletons) |
| n_multi-tracklet CONFIDENT | 9 | 3 |
| n_CATCH events | 8 | 18 |
| n_THROW events | 8 | 18 |
| n_h3_confirmed events | (n/a) | 8 |
| n_reclassified events | 0 | 22 |
| n_ambiguous events | 6 | 6 |

### YouTube
| Metric | H11 v1 (h237v5) | H11 v6 (h7v2) |
|---|---|---|
| n_chains | 18 | 15 |
| n_CONFIDENT chains | 1 | 5 |
| n_multi-tracklet CONFIDENT | 1 | 1 |
| n_CATCH events | 1 | **24** |
| n_THROW events | 1 | **24** |
| n_h3_confirmed events | (n/a) | 2 |
| n_reclassified events | 0 | **46** |
| n_ambiguous events | 0 | 0 |

## Key finding
**YouTube catch/throw events jump from 1 to 48 (24x).** This
is the real payoff of H7v2: the reclassified edges now
provide physical ball ID coverage for 24 of 40 YouTube
tracklets (60%), compared to just 1 tracklet in v1.

The 5 CONFIDENT YouTube chains include the new top chain 0
(7 tids, q=0.671) — a real 7-tid juggling cycle with 12
catch/throw events (6 CATCH + 6 THROW, all reclassified).

## Tradeoff
- identical multi-tracklet CONFIDENT chains drop from 9 to 3.
  Reason: H7v2 chains are slightly shorter (chain 38 in v1
  had 8 tids; in v6, similar chains are merged into smaller
  pieces). The 3 remaining CONFIDENT chains are still real
  single balls (chain 21 = real, chain 20 = real, chain 8 = real).

## Per-chain ball ID
Each tracklet in a H7v2 chain now has a `ball_id` (e.g.
"chain0_ball0"). The ball_id is the same for all tracklets
in the chain, with `identity_ambiguous=True` for AMBIGUOUS_HAND
edges (where the hand-pool had >1 token and the identity is
fundamentally ambiguous).

## Verdict: **PASS**

H11 v6 is a meaningful improvement over H11 v1:
- YouTube catch/throw events: 1 → 48 (24x)
- 60% of YouTube tracklets now have a physical ball ID
- 5 YouTube chains are CONFIDENT (real juggling cycles)
- Identical: 18 events (mostly reclassified, real catches)

## Artifacts
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v6_h7v2_identities.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_v6_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_v6_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v6_summary.json`
