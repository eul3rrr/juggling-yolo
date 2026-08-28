# H1-H10 Final Summary — Hand Occlusion Overnight Lab

Date: 2026-08-28 ~08:30 CEST
Branch: `experiments/hand-occlusion-overnight`
Worker: MiniMax-M3 (GMI) — autonomous research episode

## What was built

Ten research cycles (H1 through H10) on hand-occlusion
reasoning for juggling-ball tracking, plus three follow-up
iterations (H8 v4, H8 v5, H10 v5, H237 v5).

### Recommended operating points (as of this episode)

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

### What works

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
   (chain 36).

### What doesn't work

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

### Open problems

1. **YouTube long-tracklet physics check**: needs per-bounce
   segmentation (H8 v6) to identify which parabolic arc
   each tail/head belongs to.
2. **H10 v6 trained quality classifier**: would a learned
   logistic-regression model outperform the hand-tuned
   weights?
3. **H11 tracklet-level identity propagation**: given a
   high-quality H10 v5 chain, propagate identity labels
   to enable juggling-pattern analysis.
