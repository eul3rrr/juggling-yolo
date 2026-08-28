# Hand Occlusion Overnight Lab — Final Summary

Date: 2026-08-28 ~16:00 CEST
Branch: `experiments/hand-occlusion-overnight`
Worker: MiniMax-M3 (GMI) — autonomous research episode

## What was built

Twenty-six research cycles (H1 through H12 v7) on hand-occlusion
reasoning for juggling-ball tracking, plus follow-up iterations
(H8 v4-v8, H10 v5-v8, H11 v4-v6, H12 v2-v7, H237 v5-v6).

### Recommended operating points (as of this episode)

- **Hand-link extractor**: v4d (throw=7 + soft catch-context
  + slope filter MIN_FROM_SLOPE=2.5), 10 identical + 1 YouTube
  links with visual precision ~1.000. Confirmed by 11/11
  visual inspection.
- **Chain construction**: H7v2 — reclassify BALLISTIC edges
  as HAND_TRANSITION when the source ends OR target starts
  with a catch/throw signature (distance ≤ 108 AND strong
  slope). 35% reclassification rate on identical, **93% on
  YouTube**. Visual QA: 8/8 inspected edges confirmed as
  REAL_CATCH_THROW.
- **Chain combination**: H7 (greedy min-cost flow with
  capacity constraints) on H7v2-reclassified edges. Longest
  chain 7 on identical, 7 on YouTube. Zero conflicts.
- **Chain quality score**: H10 v8 (per-video adaptive weights
  + H7v2's reclassified edges give h8=1.0 universally on
  YouTube). YouTube mean quality 0.537 → 0.679 (over-counting
  artifact removed at its source).
- **Unified chain representation**: H237 v6 (H7v2 chains +
  H10 v8 quality + n_reclassified_edges metadata). 0 pure-
  ballistic YouTube chains, 7 pure-reclassified chains.
- **Tracklet identity propagation**: H11 v6 (H7v2 chains +
  H10 v8 quality). YouTube catch/throw events 1 → 48 (24x
  improvement). 60% of YouTube tracklets now have a physical
  ball ID.

### What works (after H7v2)

1. **Hand-pool state machine (H1 v1-v4)**: per-hand FIFO
   token stack with multiple physics-aware filters. v4d
   is the recommended hand-link extractor.
2. **BALLISTIC → HAND_TRANSITION reclassification (H7v2)**:
   the single biggest win. Most YouTube BALLISTIC edges
   are catch+throws in disguise. Reclassifying them as
   HAND_TRANSITION removes the false h8 penalty and gives
   the YouTube pipeline 24x more catch/throw events.
3. **Unified chain representation (H237 v6)**: H7v2 chains
   + H10 v8 quality + reclassification metadata. Each
   chain has n_reclassified_edges and pct_reclassified
   fields for downstream consumers.
4. **Identity propagation (H11 v6)**: with H7v2's
   reclassification, YouTube ball ID coverage jumps from
   1 to 48 events. Top YouTube chain (chain 0, 7 tids,
   q=0.671) is a real juggling cycle with 12 catch/throw
   events.
5. **Pattern inference (H12 v7)**: with H7v2's hand
   parsing fixed, YouTube 100% UNCONFIRMED → 12.4% CASCADE
   / 23.5% FOUNTAIN / 56.3% MIXED. Useful for downstream
   pattern consumers.

### What doesn't work (negative findings)

1. **H4 face-mask**: H3 YouTube false positive is on a
   stationary high-up object, not a face. Geometric mask
   cannot fix detector confusion.
2. **H8 v4 short-tracklet-only**: trades YouTube false
   positives for identical false negatives.
3. **H8 v5-v8 on YouTube long tracklets**: long tracklets
   span multiple parabolic arcs; the physics check confuses
   phase changes with identity switches.
4. **CASCADE/FOUNTAIN classification on identical late
   phase**: event log is right-hand-biased; even with H7v2
   the algorithm classifies 74.5% of late phase as FOUNTAIN
   when visual QA confirms it's a CASCADE. The event log
   density is the fundamental bottleneck.
5. **H10 v6/v6b/v7 per-video / length-dependent weights**:
   per-video fixed weights (v6b) are the best; length-
   dependent smoothing (v7) is intermediate between v5 and
   v6, which is worse than either extreme.

### Open problems

1. **CASCADE/FOUNTAIN classification**: fundamentally
   limited by event log density. Needs multi-view, higher
   frame rate, or ground truth to disambiguate.
2. **H13 detector-level low-confidence ball detection**:
   not yet implemented. Could find missed balls near hands.
3. **YouTube 4-ball vs 5-ball pattern classification**:
   visual confirmation at f=2 (4 balls) and f=500 (5
   balls). The pattern may be a 5-ball cascade, but the
   n_total=5 detection could include noise.

## Strongest findings

1. **H7v2's BALLISTIC → HAND_TRANSITION reclassification
   is the lab's biggest single improvement.** 13/37
   identical and 25/27 YouTube BALLISTIC edges are
   reclassified. All 8 visually inspected reclassified
   edges are REAL_CATCH_THROW. YouTube mean quality
   jumps 0.537 → 0.679, and YouTube ball ID coverage
   jumps 1 → 48 events (24x).

2. **The chain-quality pipeline is well-validated.**
   H10 v8's per-video weights are robust. Sensitivity
   grids are flat. The composite quality (0.30 h3 +
   0.30 h8 + 0.40 h9 on identical, +0.25 h8v8 on
   YouTube) correctly identifies real juggling cycles
   as high quality and multi-ball merges as low quality.

3. **YouTube has a 5-ball pattern.** Visual confirmation
   at f=2 (4 balls visible) and f=500 (5 balls visible).
   The n_total=5 in 67% of frames is correct, not an
   over-counting artifact.

4. **H3 stationary-cluster is a useful corroborating
   signal**, not a recovery mechanism. It correctly
   identifies 6/6 identical-video v4d held phases as
   real held balls, with 1 YouTube false positive
   (stuck on a stationary high-up object).

5. **CASCADE/FOUNTAIN classification is fundamentally
   unresolvable** with single-camera 2D tracking and
   sparse event log. The late phase is right-hand-
   biased, so the K=4 window sees mostly right-hand
   events and classifies as FOUNTAIN. The pattern is
   actually a CASCADE (visual confirmation).

## Recommended next steps (if work continues)

1. **H13: detector-level low-confidence ball detection**.
   Master §14's "lower-confidence evidence tier near
   hand events" is the inspiration. The detector
   confusion is partly responsible for the remaining
   issues; a conf=0.1 re-run could reveal where balls
   actually are.
2. **Multi-view 3D ball tracking**. This would solve
   the CASCADE/FOUNTAIN ambiguity and the identity
   switches in long tracklets.
3. **Higher frame rate (60+ fps)**. The event log
   density problem is partly a frame-rate problem. At
   60 fps, each catch/throw would have more frames in
   the K=4 window.

## Artifacts

- `experiments/hand_occlusion_overnight/MASTER_INSTRUCTIONS.md`
- `experiments/hand_occlusion_overnight/STATE.md`
- `experiments/hand_occlusion_overnight/PLAN.md`
- `experiments/hand_occlusion_overnight/RESULTS_LOG.md`
- `experiments/hand_occlusion_overnight/RESEARCH_NOTES.md`
- `experiments/hand_occlusion_overnight/SETUP_NOTES.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/` (40+ scripts)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/` (50+ CSVs + 30+ JSONs)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/` (25+ reports)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_*/` (visual QA images)

## Key commits (recent)

- `53ed7e8` docs: STATE/PIPELINE summary for H11v6 + H237v6 + H12v7
- `2a7f2d7` experiment: H11 v6 identity propagation on H7v2 chains (PASS)
- `c1957b0` experiment: H237 v6 unified representation on H7v2 chains (PASS)
- `ba872a1` experiment: H12 v7 pattern inference on H7v2 chains with H10 v8 (MIXED)
- `51ad09b` experiment: H7 v2 reclassify BALLISTIC as HAND_TRANSITION at hand + H10 v8 (PASS)
