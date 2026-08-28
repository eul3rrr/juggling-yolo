# H237 v5 — Unified Chain Representation with H10 v5 Quality

Date: 2026-08-28 ~08:25 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: PASS

## Hypothesis

The H237 unified chain representation (H2 + H3 + H7) is the
most informative chain representation. By enriching it with
the H10 v5 chain quality score, downstream consumers can use
chain quality directly without recomputing it.

## Algorithm

For each chain in `h237_unified_chains_<stem>.csv`:
1. Look up H10 v3 quality and rank from
   `h10_chain_quality_summary.json`.
2. Look up H10 v5 quality and rank from
   `h10v5_chain_quality_summary.json`.
3. Add columns: `h10_v3_quality`, `h10_v5_quality`,
   `h10_v3_rank`, `h10_v5_rank`, `h10_quality_delta`.

Output: `data/h237v5_unified_chains_<stem>.csv` and
`data/h237v5_unified_summary.json`.

## Quantitative Result

### Identical video (43 chains)

Top 5 chains by v5 quality:
| chain | n_tids | v3 quality | v5 quality | v3 rank | v5 rank |
|---|---|---|---|---|---|
| 21 | 2 | 0.966 | 0.966 | 0 | 0 |
| 36 | 2 | 0.515 | 0.944 | 11 | 1 |
| 19 | 3 | 0.927 | 0.927 | 3 | 2 |
| 20 | 2 | 0.923 | 0.923 | 4 | 3 |
| 2  | 2 | 0.921 | 0.921 | 5 | 4 |

The biggest rank improvement: chain 36 (v3 rank 11 → v5 rank 1,
+10). v5 correctly identifies a real single ball (with 33-frame
gap) that v3 over-penalized.

Bottom 3 chains by v5 quality (all unchanged from v3):
| chain | v3 quality | v5 quality | rank |
|---|---|---|---|
| 42 | 0.429 | 0.429 | 40 |
| 38 | 0.429 (v3=0.353) | 0.353 | 41 |
| 13 | 0.297 | 0.297 | 42 |

### YouTube video (15 chains)

Top 5 chains by v5 quality (only chain 12 changed):
| chain | n_tids | v3 quality | v5 quality | v3 rank | v5 rank |
|---|---|---|---|---|---|
| 6  | 2 | 0.967 | 0.967 | 0 | 0 |
| 12 | 3 | 0.756 | 0.648 | 1 | 1 |
| 3  | 4 | 0.558 | 0.558 | 2 | 2 |
| 1  | 2 | 0.558 | 0.558 | 3 | 3 |
| 8  | 4 | 0.550 | 0.550 | 4 | 4 |

## Verdict: PASS

The H237 v5 unified chain representation makes the v5
quality score directly available per-chain. Downstream
consumers (e.g. a juggling-pattern analyzer) can read
the CSV and use the `h10_v5_quality` column to filter
chains by confidence.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h237v5_unified.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v5_unified_chains_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v5_unified_summary.json`
