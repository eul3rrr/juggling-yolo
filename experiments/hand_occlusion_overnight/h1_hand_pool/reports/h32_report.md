# H32 — Per-chain pattern characterization on h7v3plus2 chains

**Date:** 2026-08-28 ~12:30 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE** (H32's CASCADE/FOUNTAIN classification is fundamentally confounded by multi-ball merges)

## Hypothesis

H12's per-frame CASCADE/FOUNTAIN inference has fundamental reliability
issues (H20 visual QA: FOUNTAIN misclassification at f=890-1050; vision
tool inconsistencies on CASCADE/FOUNTAIN distinction). The h7v3plus2
chain set (H7v2 + H15v2 + H21 + H26 = 42 identical, 15 YouTube) is the
best-validated chain representation we have.

H32 hypothesis: at the CHAIN level (not the frame level), hand
alternation is a robust discriminator between CASCADE (alternates
hands) and FOUNTAIN (single-hand) juggling patterns. The h7v3plus2
chains each have an edge_type metadata that encodes which hand was
used for each catch/throw, so we can build a per-chain hand sequence.

A chain-level CASCADE/FOUNTAIN classification based on hand alternation
should be:
- Immune to per-frame pattern noise (H12 v4/v5 vx-signal is per-frame)
- Based on the validated h7v3plus2 chain set (not the noisy H17
  V-shape pool)
- Operating at chain granularity (each chain is a clear unit of
  analysis)

## Approach (declared from physical geometry, not tuned to labels)

For each h7v3plus2 chain, compute:
1. **hand_sequence**: chronological list of hands parsed from edge
   metadata. For each hand-edge, record the catch hand; for H26
   hand-offs, record BOTH hands.
2. **n_hand_events**: count of hand-edge entries
3. **alternation_rate**: fraction of consecutive hand-event pairs that
   alternate L↔R
4. **unique_hands**: 1, 2, or 0
5. **catch_rate_hz**: n_catches / chain_duration_seconds
6. **pattern_verdict**:
   - `CASCADE_LIKE`: alternation_rate >= 0.5 AND unique_hands == 2
   - `FOUNTAIN_LIKE`: unique_hands == 1 AND n_catches >= 2
   - `MIXED`: not CASCADE_LIKE and not FOUNTAIN_LIKE, n_catches >= 3
   - `SINGLE_CATCH`: n_catches == 1
   - `NO_CATCH`: n_catches == 0
7. **physical_ball_estimate**: heuristic based on chain length and
   pattern_verdict

## Quantitative result

### Per-chain verdicts (multi-tracklet chains only)

**identical** (18 multi-tracklet chains):

| Verdict | n_chains |
|---|---|
| NO_CATCH | 3 |
| SINGLE_CATCH | 9 |
| CASCADE_LIKE | 3 |
| FOUNTAIN_LIKE | 2 |
| UNKNOWN | 1 |

Mean alternation rate (multi-tracklet): **0.181**
Mean catch rate (multi-tracklet): **0.474 Hz**
Total ball_estimate: **51** balls (across 42 chains)

**YouTube** (9 multi-tracklet chains):

| Verdict | n_chains |
|---|---|
| NO_CATCH | 0 |
| SINGLE_CATCH | 3 |
| CASCADE_LIKE | 5 |
| FOUNTAIN_LIKE | 1 |
| UNKNOWN | 0 |

Mean alternation rate (multi-tracklet): **0.428**
Mean catch rate (multi-tracklet): **0.204 Hz**
Total ball_estimate: **23** balls (across 15 chains)

## Visual QA (7 contact sheets, all confirmed via vision_analyze)

Selected the longest chain per verdict per video:

| Chain | Video | n_tids | H32 verdict | Hand sequence | Vision verdict | Reason |
|---|---|---|---|---|---|---|
| 22 | identical | 7 | CASCADE_LIKE | L→L→R→R→L | **MULTI_BALL_MERGE** | 3 distinct balls visible; L→L→R→R→L reflects 3 different balls per tracklet, not 1-ball cascade |
| 0 | YouTube | 7 | CASCADE_LIKE | L→L→R→R→L→R | **MULTI_BALL_MERGE** | 2-3 yellow balls visible; pattern is blocky (LLL then RRRR) |
| 30 | identical | 5 | FOUNTAIN_LIKE | R→R→R | **MULTI_BALL_MERGE** | Frame f=960/1017 show balls on LEFT hand; 2-ball juggling pattern mislabeled |
| 3 | YouTube | 4 | FOUNTAIN_LIKE | R→R→R | **MULTI_BALL_MERGE** | 2 yellow balls visible in most frames; right hand correct but multi-ball |
| 29 | identical | 5 | UNKNOWN | L→R→R→l→r | **UNKNOWN_OK** | Real 2-ball exchange pattern; 2 balls visible; L→R→R same-hand repeat is legitimate |
| 15 | identical | 3 | SINGLE_CATCH | L | **SINGLE_CATCH_WRONG** | Visual shows RIGHT hand dominant, not left as labeled |
| 1 | YouTube | 2 | SINGLE_CATCH | R | **MULTI_BALL_MERGE** | ball_est=1 is wrong; 2 yellow balls visible in air simultaneously |

**Precision of H32 hand-alternation classification: 1/7 = 14.3%**
(Multi-ball merge rate: 5/7 = 71.4%)

## Key negative finding

**H32's CASCADE_LIKE / FOUNTAIN_LIKE classifications are fundamentally
confounded by multi-ball merges.** A "CASCADE_LIKE" hand sequence
(L→L→R→R→L) does NOT mean a single ball did a cascade — it means 3
different balls were juggled, each tracklet happening to be detected
near one hand. The chain is not a single-ball trajectory; it is a
collection of tracklets from multiple physical balls, all on the same
hand (because both hands are juggling at the same time).

This is consistent with H11 (identity propagation) findings:
- H11 v1 found 9 CONFIDENT identical chains and 1 CONFIDENT YouTube
  chain with "correct physical ball ID"
- H11 v2 found per-frame census shows 51% cascade time on identical
  (over-counting due to UNCERTAIN chains) and 100% on YouTube
- The 4 "5-ball at f=700" anomaly on identical was confirmed as a real
  detector multi-ball merge

The h7v3plus2 chain set is, at the chain level, mostly multi-ball
merges. The hand-alternation pattern in a multi-ball chain is an
artifact of *which hand each ball happened to be near*, not a real
single-ball pattern.

## Why the multi-ball merge is invisible at the chain level

- H1 v4d hand-edge: confirmed real catch+throw (precision ~1.000 on
  identical)
- H7v2: reclassifies BALLISTIC edges that pass through a hand region
  as HAND_TRANSITION
- H15v2: V-shape reclassification for h7v2-kept BALLISTIC edges
- H21 + H26: add 7 visually-confirmed REAL H20-KEPT edges

All these layers add HAND_TRANSITION edges to chains. But the SOURCE
and TARGET tracklets of these edges can be from DIFFERENT physical
balls. The chain construction algorithm (min-cost flow) doesn't know
which physical ball each tracklet belongs to — it only knows which
tracklets are temporally adjacent and which edges have hand-region
support. Multiple physical balls being juggled simultaneously
produces a chain with edges that all have hand-region support, but
the chain is not a single-ball trajectory.

The h7v3plus2 chains are:
- **VALID as "events"**: each hand-edge is a real catch+throw event
- **NOT VALID as "single-ball trajectories"**: the chain's tracklets
  are not all the same physical ball

## Chain 29 (UNKNOWN) — the one good case

Chain 29 (identical, 5 tids, hand sequence L→R→R→l→r) is the only
H32 verdict that visual QA confirmed as a real single-pattern juggling
sequence. The 2-ball exchange pattern is correctly identified as
UNKNOWN because the hand sequence has the same-hand repeat (R→R) that
isn't clean cascade. This is a useful case study: when a chain has
n_tids=5 and the hand sequence has BOTH L→R alternation AND same-hand
repeats, AND the visual evidence shows 2 balls, the pattern is
likely a 2-ball passing/exchange pattern.

## Cross-cutting insight

**H32 confirms H10/H11: the h7v3plus2 chain set is mostly
multi-ball merges, not single-ball trajectories.** The h10v10 quality
score is a real signal for "how much this chain looks like a single
ball," but even high-quality chains (h10q > 0.7) can be multi-ball
merges (e.g., chain 30 has h10q=0.405 and is a clear multi-ball merge;
chain 0 YouTube has h10q=0.671 and is a clear 3-ball merge).

The chain construction pipeline (H1 v4d → H7v2 → H15v2 → H21 → H26)
correctly identifies "real hand events" but does NOT track physical
ball identity. H11 v1-v7 made progress on identity propagation but
found that CONFIDENT physical ball ID is rare (9 identical, 1 YouTube
CONFIDENT chains).

## Implication for downstream consumers

**Do not use h7v3plus2 chains as single-ball trajectories.** Use them
as:
- A list of "hand events" (each hand-edge is a real catch+throw)
- A list of "ball cycles" only for CONFIDENT chains (H11 v7 quality
  threshold)
- A "ball presence" signal (some chain near a hand at some time) for
  general juggling analysis

For "this chain is a single physical ball" claims, use the H11 v7
CONFIDENT/UNCERTAIN/LOW classification, not the chain structure
itself.

## Verdict

**NEGATIVE.** H32's hand-alternation-based CASCADE/FOUNTAIN
classification is fundamentally confounded by multi-ball merges. The
h7v3plus2 chains are mostly multi-ball merges with real hand events,
not single-ball trajectories. The one chain (29) that visual QA
confirmed as a real 2-ball exchange pattern is correctly identified
as UNKNOWN, but this is the exception, not the rule.

## Recommendation

- h7v3plus2 remains the recommended chain set
- H32's per-chain pattern_verdict is **NOT** a useful signal because
  it confuses single-ball patterns with multi-ball merges
- The CASCADE/FOUNTAIN problem in H12 is now understood to be a
  multi-ball-vs-single-ball identification problem, not a
  cascade-vs-fountain classification problem
- Future work on juggling-pattern analysis should focus on
  distinguishing single-ball from multi-ball chains (H11 CONFIDENT
  filter), NOT on cascade-vs-fountain classification

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h32_chain_characterization.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h32_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_chain_metrics_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_visual_qa.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_contact_sheet_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h32/*.png` (7 files)

## Cross-references

- H1 v4d — hand-pool (real catch+throw detection, ~11 links per video)
- H7v2 — reclassifies BALLISTIC edges through hand region
- H15v2 — V-shape reclassification
- H21, H26 — visually-confirmed REAL H20-KEPT chain-set augmentation
- H10 v10 — chain quality score (real but imperfect signal)
- H11 v1-v7 — identity propagation (CONFIDENT/UNCERTAIN/LOW classification)
- H12 v1-v8 — per-frame CASCADE/FOUNTAIN inference (fundamental
  limitations)
- H17→H20→H24→H28→H31 — negative finding chain on V-shape pool
  filtering
