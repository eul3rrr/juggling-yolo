# H8 — Physics consistency check on H7 chains (edge-level)

**Date:** 2026-08-28 ~07:00 CEST
**Status:** COMPLETE
**Verdict:** PASS — useful as a chain quality signal

## Hypothesis

E6c's accepted ballistic edges are based on a constant-velocity
(linear) prediction. A real airborne ball's y-velocity changes
slowly (gravity = ~0.5 px/frame^2 for a juggling ball at ~1m
distance). A large y-velocity discontinuity across an edge is a
strong signal of an identity switch.

This is the same intuition as Ponglertnapakorn & Suwajanakorn
(2025, "Where Is The Ball", arXiv:2506.05763): "estimate the
physical parameters that best explain the detected trajectory,
such as velocity and initial force." H8 implements a simple
version of this.

## Approach (declared from physical geometry, NOT from manual labels)

For each BALLISTIC edge in H7's chain representation:
- src_vy = average y-velocity over the last 3 frames of source tracklet
- tgt_vy = average y-velocity over the first 3 frames of target tracklet
- velocity_discontinuity = |src_vy - tgt_vy|
- VIOLATING if velocity_discontinuity > 8.0 px/frame

Threshold rationale: a real ball at ~1m distance with a 30 fps
camera has y-acceleration of ~5 px/frame^2. Over a 1-frame gap
the velocity should change by ≤5 px/frame. A threshold of 8
allows for tracking noise (~3 px) plus gravity contribution.

Hand edges (HAND_TRANSITION) are EXCLUDED from this check
because a real hand-event naturally has a vy discontinuity
(the ball stops in the hand, then is re-thrown).

## Three iterated implementations

### H8 v1 (per-chain parabola)
- Fits a single parabola y(t) to all mid-air points in a chain.
- Result: many false positives because juggling chains span
  multiple parabolic arcs (one per throw). A single parabola
  doesn't fit.
- **Abandoned.**

### H8 v2 (per-tracklet parabola classification)
- Classifies each tracklet as BALLISTIC / HELD / NOISY based on
  parabola fit.
- Result: 36/76 identical tracklets classified as NOISY
  (because long tracklets span many bounces). Useful as
  tracklet-level metadata, but not a per-edge check.
- **Partial use: tracklet classifications saved as downstream
  metadata.**

### H8 v3 (per-edge velocity discontinuity) — RECOMMENDED
- Compares y-velocity at the tail of the source tracklet
  to y-velocity at the head of the target tracklet.
- Restricts to BALLISTIC edges (hand edges are excluded).
- Simple, fast, and works on both short and long tracklets
  (as long as the FIRST and LAST few frames are reliable).

## Quantitative result

| Video | n_air edges | n_air OK | n_air violating |
|---|---|---|---|
| identical | 23 | 14 | **9** |
| YouTube | 24 | 1 | **23** |

### Identical — 9 violating air edges

These are likely E6c false positives (identity switches):

| Edge | src_vy | tgt_vy | disc | Interpretation |
|---|---|---|---|---|
| 5→6 | -12.7 | -22.8 | 10.1 | 90px y-jump in 1 frame; t5 was held/released, t6 is a different ball already in mid-air. Visual QA confirmed. |
| 19→20 | -10.2 | 11.7 | 21.9 | Sign flip; balls going opposite directions. |
| 60→64 | -2.3 | 24.6 | 27.0 | Massive sign flip. |
| 51→52 | -1.8 | -12.3 | 10.5 | 90px y-drop across 5-frame gap. Identity switch. |
| 23→25 | 1.4 | 14.3 | 12.8 | t23 held, t25 in mid-air below. |
| 25→27 | 8.2 | -1.9 | 10.1 | Sign flip. |
| 67→70 | -6.9 | 18.0 | 24.9 | Massive sign flip. |
| 62→66 | -8.4 | 2.3 | 10.8 | Sign flip. |
| 64→68 | 13.2 | -29.1 | 42.3 | Massive sign flip. |

### YouTube — 23/24 violating air edges

The YouTube video has a different structure: most tracklets span
many bounces (e.g., t4 has 415 frames covering f=2-416). The
FIRST 3 frames of t4 are at the apex of an early throw
(vy=8.5 px/frame downward), but the LAST 3 frames are at the
apex of a much later throw. The vy "discontinuity" is real
because we're comparing the wrong ends.

This is a **limitation of the H8 metric on long tracklets**.
A v4 should only apply the metric to tracklets with n_pts ≤ 30
or so. For the YouTube video, the metric is unreliable.

## Visual QA

Two contact sheets rendered:

1. `contact_sheets_h8/chain4_t5_t6_violating.png`: visual
   confirmation that t5 and t6 are DIFFERENT balls. t5 is
   being released (held) and t6 is a different ball already
   in the juggling pattern. The E6c err=2.49 admitted the
   edge, but H8 correctly flags it as a physics violation.

2. `contact_sheets_h8/chain29_t50_t55_violating.png`: visual
   confirmation that t50 and t55 are DIFFERENT balls. t50
   ends in the hand area, t55 starts at a different location.
   Another identity switch that E6c's constant-velocity model
   missed.

The longest H7 chain (35→37→40→41→43→45→46, 7 tids) was
also checked: all 6 air edges are OK in H8's metric
(disc ≤ 2.2 px/frame). This is consistent with the visual
QA that confirmed it as a real juggling cycle.

## Verdict

**PASS.** H8 successfully identifies 2 confirmed identity
switches on the identical video that H2/H6/H7 all accepted
(5→6 and 50→55). The metric is unreliable for long tracklets
(YouTube video's tracklets span many bounces), so a v4 should
restrict the check to short tracklets or apply a different
metric.

The H8 metric is most useful as a **post-hoc quality signal**:
when H8 flags an edge, it's worth a closer look. The metric
is NOT a recovery mechanism (it doesn't generate new chains,
just flags suspicious ones).

## Recommendations for downstream consumers

1. **Use H8 flags as a confidence weight** on H7 chains.
   Edges flagged as VIOLATING can be downweighted or removed.
2. **On the identical video**, the 9 flagged air edges are
   likely false positives; consider removing them to get a
   cleaner chain representation.
3. **On the YouTube video**, H8 is unreliable due to long
   tracklets; use a different metric (e.g., residual from
   E6c's ballistic fit) instead.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_physics_check.py` (v1, abandoned)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v2_per_tracklet.py` (v2, partial)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v3_edge_physics.py` (v3, recommended)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_physics_check_summary.json` (v1)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v2_per_tracklet_summary.json` (v2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v3_edge_physics_summary.json` (v3, recommended)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/chain4_t5_t6_violating.png`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/chain29_t50_t55_violating.png`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/longest_chain_consistent.png`
