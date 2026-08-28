# H33 — Tracklet-time overlap multi-ball detector (NEGATIVE)

**Date:** 2026-08-28 ~12:35 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE**

## Hypothesis

A single physical ball cannot be at two different positions at the
same time. If two tracklets in the same chain overlap temporally
(frame i is in both tracklets' time range), they MUST be from
different physical balls (or a single ball was detected twice during
occlusion).

H32 visual QA found 5/7 chains are MULTI_BALL_MERGE. H33
hypothesis: a simple tracklet-time overlap check should be a
deterministic signal for this.

## Quantitative result

| Video | n_chains | n_multi | MULTI_BALL_HIGH | MULTI_BALL_LOW | SINGLE_BALL_CAND |
|---|---|---|---|---|---|
| identical | 42 | 18 | **0** | **0** | 18 |
| YouTube | 15 | 9 | **0** | **0** | 9 |

**No chain in the h7v3plus2 set has any tracklet-time overlap.**

## Why H33 fails

The h7v3plus2 chain construction (H7v2 + H15v2 + H21 + H26) is
by construction temporally sequential:
- Hand-edges (HAND_TRANSITION, RECLASSIFIED, V_RECLASSIFIED,
  H26_RECLASSIFIED) require a catch-throw, which means source ends
  before target starts.
- BALLISTIC edges link two tracklets that are temporally adjacent
  (one ends, next starts).
- AMBIGUOUS_HAND_TRANSITION edges are temporally sequenced.

So the chain has no tracklet overlap even when it represents
multiple physical balls. The *content* of the tracklets (which
physical ball) doesn't follow the chain's structure, but the
*temporal ordering* does.

## Cross-check with H32 visual QA

| Chain | H32 verdict | Vision verdict | H33 verdict | Agree? |
|---|---|---|---|---|
| 22 identical | CASCADE_LIKE | MULTI_BALL_MERGE | SINGLE_BALL_CAND | NO (H33 missed) |
| 30 identical | FOUNTAIN_LIKE | MULTI_BALL_MERGE | SINGLE_BALL_CAND | NO (H33 missed) |
| 29 identical | UNKNOWN | UNKNOWN_OK | SINGLE_BALL_CAND | YES (both say not-multi) |
| 15 identical | SINGLE_CATCH | SINGLE_CATCH_WRONG | SINGLE_BALL_CAND | YES (both say not-multi) |
| 0 YouTube | CASCADE_LIKE | MULTI_BALL_MERGE | SINGLE_BALL_CAND | NO (H33 missed) |
| 3 YouTube | FOUNTAIN_LIKE | MULTI_BALL_MERGE | SINGLE_BALL_CAND | NO (H33 missed) |
| 1 YouTube | SINGLE_CATCH | MULTI_BALL_MERGE | SINGLE_BALL_CAND | NO (H33 missed) |

H33 misses ALL 5 vision-confirmed MULTI_BALL_MERGE chains. The
agreement is "not-multi" (negative) agreement, not "multi"
(positive) agreement. H33 is a useless signal because it
fails to detect any multi-ball merges.

## Verdict

**NEGATIVE.** Tracklet-time overlap is not a useful signal for
multi-ball detection in the h7v3plus2 chain set. The chain
construction produces temporally sequential tracklets by design.
Multi-ball merges happen because the *physical ball identity* of
each tracklet doesn't match the chain's structure, not because
the tracklets overlap in time.

## Recommendation

- H33 is not a useful signal
- H32's hand-alternation pattern_verdict is confounded by
  multi-ball merges (5/7 vision-QA confirmed)
- H10 v10 quality is a real but imperfect signal
- H11 v7 CONFIDENT filter is the most accurate single-ball
  filter

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h33_chain_overlap.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_chain_overlap_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_visual_qa_check.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h33_report.md` (this file)
