# H1-H12 Final Summary — Hand Occlusion Overnight Lab

Date: 2026-08-28 ~08:35 CEST
Branch: `experiments/hand-occlusion-overnight`
Worker: MiniMax-M3 (GMI) — autonomous research episode

## What was built

Ten core research cycles (H1 through H10) on hand-occlusion
reasoning for juggling-ball tracking, plus six follow-up
iterations (H8 v4, H8 v5, H10 v5, H237 v5, H8 v6, summary).

## Recommended operating points (as of this episode)

- **Hand-link extractor**: v4d (throw=7 + soft catch-context
  + slope filter), 10 identical + 1 YouTube links with
  visual precision ~1.000.
- **Chain combination**: H7 (greedy min-cost flow with
  capacity constraints), longest chain 7 on identical,
  6 on YouTube. Resolves the 1 H2 conflict.
- **Chain quality score**: H10 v5 (parabolic-fit H8 + H3 +
  H9 with graduated 0.5 for INSUFFICIENT_DATA). Top
  chains are real juggling cycles; low-quality chains
  contain identity switches.

## What works

1. **Hand-pool state machine (H1 v1-v4)**: per-hand
   FIFO token stack with multiple physics-aware filters.
   v4d is the new operating point.
2. **Unified chain representation (H2 + H7)**: combines
   hand and air edges with principled cost formulation.
3. **H8 v5 parabolic-fit physics**: catches 2 NEW
   identity switches on identical that v3 missed
   (60→64, 21→22).
4. **H10 v5 chain quality**: real signal for downstream
   consumers. v5 correctly demotes 2 v3-false-positives
   (chains 24, 29) and promotes 1 v3-false-negative
   (chain 36: real single ball with 33-frame gap that
   v3 over-penalized).
5. **H237 v5 enriched chain representation**: makes
   the v5 quality directly available per-chain for
   downstream consumers.

## What doesn't work

1. **H4 face-mask**: the H3 YouTube false positive is
   not a face confusion; it's a stuck detection on a
   stationary high-up object. Geometric mask can't fix
   detector confusion.
2. **H8 v4 short-tracklet-only**: trades YouTube false
   positives for identical false negatives. The trade-off
   is not worth it.
3. **H8 v5 on YouTube long tracklets**: 23/24 air edges
   flagged VIOLATING because long tracklets span multiple
   parabolic arcs. v5 confuses phase changes with identity
   switches.
4. **H8 v6 per-bounce segmentation**: apex detection is
   too coarse to isolate clean parabolic segments within
   long tracklets. The juggler's catch-throw motion
   within a long tracklet contaminates any naive tail
   fit. v6 produces the same YouTube result as v5.

## Open problems

1. **YouTube long-tracklet physics check**: needs either
   (a) per-bounce segmentation at frame level (not just
   apexes), (b) 3D ball trajectory estimation
   (Ponglertnapakorn & Suwajanakorn 2025), or (c) accept
   the limitation and use H8 only for short tracklets.
2. **H10 v6 trained quality classifier**: would a learned
   logistic-regression model outperform the hand-tuned
   weights (0.30*h3 + 0.30*h8 + 0.40*h9)?
3. **H11 tracklet-level identity propagation**: given a
   high-quality H10 v5 chain, propagate identity labels
   to enable juggling-pattern analysis (downstream
   consumer of H10 v5 quality).
4. **Detector headroom revisit (master §14)**: E15 noted
   low-confidence detections may contain useful
   information. A second-tier ByteTrack-style association
   near active hand events could fill some detector
   dropouts. H3 explored this and found a stationary-
   cluster pattern (useful for held-ball confirmation but
   not for recovery).

## Episode summary

This autonomous episode completed 6 research cycles
(H10, H8v4, H8v5, H10v5, H237v5, H8v6) plus the
final summary. All committed and pushed to
`origin/experiments/hand-occlusion-overnight`. Two of
the six cycles were positive (H10, H10v5, H237v5),
two were mixed (H8v5), and two were negative (H8v4,
H8v6) — all negative results documented with
clearer-than-before failure modes for future researchers.
