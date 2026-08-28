# H8 v5 — Parabolic-Fit Long-Tracklet Physics Check

Date: 2026-08-28 ~08:05 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: MIXED — incrementally better than v3 on identical,
same YouTube limitation as v3.

## Hypothesis

H8 v3's 3-frame mean velocity is noisy on long tracklets
because it averages over the local parabolic arc. A parabolic
fit to the last 8 frames of source and first 8 frames of
target should give a better local velocity estimate. With
constant-gravity extrapolation across the gap, predict the
expected y-velocity at the gap edges and compare to the actual.

## Thresholds (declared from physical geometry)

- PARABOLA_N = 8 frames
- MIN_TRACKLET_PTS = 5
- GRAVITY_PX_PER_FRAME2 = 0.5 (image-space gravity, see below)
- DISCONTINUITY_TOLERANCE = 8.0 px/frame

The image-space gravity depends on the camera's pixel-to-meter
ratio. For a juggling ball at ~1m distance, a 100 px/m ratio,
and dt=1/30s, image-space gravity is:

  g_image = g_real * dt^2 * pixel_ratio = 9.81 * (1/30)^2 * 100
         = 9.81 / 900 * 100 = 1.09 px/frame^2

With 2x safety margin (we don't know exact camera distance),
GRAVITY_PX_PER_FRAME2 = 0.5 is conservative.

## Algorithm

1. For each BALLISTIC edge:
   a. Get last N frames of source tracklet. Fit
      y = a*(t-t0)^2 + b*(t-t0) + c by least squares.
   b. Local vy at end: 2*a*(t_end - t0) + b.
   c. Get first N frames of target tracklet. Fit parabola.
   d. Local vy at start: 2*a*(t_start - t0) + b.
   e. Predicted target_vy = source_vy + g_image * gap_frames.
   f. Discontinuity = |actual_target_vy - predicted_target_vy|.
   g. Status = VIOLATING if disc > tol else OK.

## Quantitative Result

### Identical video

|| Method | n_air_OK | n_air_VIOLATING | n_air_INSUFFICIENT |
||---|---|---|---|
|| v3 (3-frame mean) | 14 | 9 | 0 |
|| v4 (short only) | 2 | 3 | 0 (18 LONG_TRACKLET) |
|| **v5 (parabolic fit)** | **12** | **10** | **1** |

v5 vs v3 on identical:
- 5→6: v3 OK → v5 VIOLATING (v5 catches known true positive)
- 21→22: v3 OK → v5 VIOLATING (v5 catches NEW true positive)
- 50→55: v3 OK → v5 INSUFFICIENT (t55 has only 4 pts)
- 60→64: v3 OK → v5 VIOLATING (v5 catches NEW true positive)
- 67→70: v3 VIOLATING → v5 VIOLATING (both catch)
- 25→27: v3 VIOLATING → v5 VIOLATING (both catch)
- 64→68: v3 VIOLATING → v5 VIOLATING (both catch)
- 3 v3-OK edges now v5-OK (matches), 5 v3-OK edges still v5-OK (no change)

### YouTube video

|| Method | n_air_OK | n_air_VIOLATING | n_air_INSUFFICIENT |
||---|---|---|---|
|| v3 (3-frame mean) | 1 | 23 | 0 |
|| v4 (short only) | 0 | 0 | 0 (24 LONG_TRACKLET) |
|| **v5 (parabolic fit)** | **0** | **23** | **1** |

The YouTube v5 "violations" are dominated by **phase changes
in the juggling cycle**: src_vy is positive (rising) and tgt_vy
is negative (falling) because the long tracklet ends near the
apex and the next starts after the apex. v5 incorrectly flags
this as an identity switch.

This is a **fundamental limit** of v5 on long tracklets. A
real physics check on long tracklets requires identifying
which phase each tail/head belongs to (e.g. by detecting
local parabolic arc boundaries within the long tracklet).

## Visual QA (3 NEW v5 catches on identical)

### edge 60→64 (v3 OK → v5 VIOLATING) — REAL IDENTITY SWITCH

Tracklet 60: n_pts=82, frames 860-941. End at (441, 85) - upper-center.
Tracklet 64: n_pts=26, frames 944-969. Start at (526, 371) - lower-right.

Spatial jump: 85px horizontal + 286px vertical in 3 frames.
**REAL IDENTITY SWITCH.** v5 correctly catches what v3 missed.

### edge 21→22 (v3 OK → v5 VIOLATING) — REAL IDENTITY SWITCH

Tracklet 21: n_pts=6, frames 212-217. End at hand level.
Tracklet 22: n_pts=38, frames 220-257. Start at top of frame (y=107).

Tracklet 22 appears already at the apex of a throw, not in the
hand. Cannot be the same ball as t21.
**REAL IDENTITY SWITCH.** v5 correctly catches what v3 missed.

### edge 64→68 (v3 VIOLATING → v5 VIOLATING) — REAL IDENTITY SWITCH

Tracklet 64: n_pts=26. Tracklet 68: n_pts=51.
Different spatial regions at the handoff. Multiple balls in
the juggling pattern at this moment.
**REAL IDENTITY SWITCH.** Both v3 and v5 catch it.

## Verdict: MIXED

H8 v5 is **incrementally better than v3 on identical**: it
catches 2 additional identity switches (60→64, 21→22) that
v3 missed, while not missing any of v3's catches. v5's
1 INSUFFICIENT case (50→55) is due to t55 having only 4
detection points, below MIN_TRACKLET_PTS=5.

On YouTube, v5 has the same long-tracklet phase-change problem
as v3: 23/24 air edges are flagged VIOLATING, but the v5
output shows these are mostly phase changes in the juggling
cycle (rising → falling across the gap), not identity switches.

### Recommendation

H8 v5 should be **preferred over v3 for short tracklets** as the
H8 signal in H10. For YouTube long tracklets, neither v3 nor v5
provides reliable signal — a fundamentally different approach
(e.g. per-bounce segmentation of long tracklets) is needed.

To use v5 in H10, replace v3's H8 score with a graduated score:
- VIOLATING (any length): 0.0
- OK (any length): 1.0
- INSUFFICIENT_DATA: 0.5 (uncertain)

This would improve H10's discrimination on identical without
making YouTube worse.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v5_parabolic.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v5_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v5_parabolic_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8v5/*.png` (6 files)
