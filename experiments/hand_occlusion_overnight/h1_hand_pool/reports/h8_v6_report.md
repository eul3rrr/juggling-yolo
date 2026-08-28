# H8 v6 — Per-Bounce Parabolic Fit on Long Tracklets

Date: 2026-08-28 ~08:35 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: NEGATIVE — apex detection too coarse for YouTube.

## Hypothesis

H8 v5's problem on YouTube long tracklets is that the parabolic
fit on the last 8 frames of source and first 8 frames of target
may be at different points in the juggling cycle (rising vs
falling). If we identify the parabolic arc boundaries within
a long tracklet, the tail/head fit would be more accurate.

## Algorithm

1. Find local y-maxima (apexes) in the long tracklet using
   a sliding window. An apex is a frame where y is locally
   maximal in a window of 2*APEX_HALFWIN+1 = 13 frames.
2. Identify parabolic arc boundaries: each arc is from one
   apex to the next (or to the start/end of the tracklet).
3. The "tail" of the tracklet is the last 8 frames of the
   last arc.
4. The "head" of the tracklet is the first 8 frames of the
   first arc.

For the physics check on an edge (src -> tgt):
- If src is long: use tail = last 8 frames of src's last arc.
- If tgt is long: use head = first 8 frames of tgt's first arc.

## Thresholds (declared from physical geometry)

- APEX_HALFWIN = 6
- ARC_N = 8
- MIN_ARC_LEN = 5
- MIN_TRACKLET_PTS = 5
- GRAVITY_PX_PER_FRAME2 = 0.5
- DISCONTINUITY_TOLERANCE = 8.0

## Quantitative Result

### Identical video

|| Method | OK | VIOLATING | INSUFFICIENT |
||---|---|---|---|
|| v5 (whole-tracklet fit) | 12 | 10 | 1 |
|| **v6 (per-bounce fit)** | **13** | **9** | **1** |

v6 catches 1 fewer violation than v5 (38→39 has disc=8.6, just
over the threshold; v5 had disc=9.2). Otherwise mostly the same.

### YouTube video

|| Method | OK | VIOLATING | INSUFFICIENT |
||---|---|---|---|
|| v5 (whole-tracklet fit) | 0 | 23 | 1 |
|| **v6 (per-bounce fit)** | **0** | **23** | **1** |

**v6 doesn't help on YouTube.** The YouTube violations are
dominated by the same phase-change pattern as v5: src_vy is
positive (rising) and tgt_vy is negative (falling).

## Why v6 doesn't help

The apex detection (APEX_HALFWIN=6) only finds the major
apexes — 5 apexes in t4's 415 frames. Within each "arc"
between two detected apexes, the ball can still go up and
down multiple times (due to the juggler's catch-throw-rethrow
motion within the long tracklet). The "tail" of the last arc
(frames 409-416 of t4) shows the ball RISING (y=450 → 507)
even though the arc starts after a major apex (frame 345).

This means the "last arc's tail" is not a clean parabolic
segment — it's still a complex motion that includes catch,
throw, and re-throw. The parabola fit picks up the local
trend (rising), but that's not the relevant physics for
the gap-velocity check.

## Verdict: NEGATIVE

H8 v6's per-bounce segmentation does not solve the YouTube
long-tracklet problem because the apex detection is too coarse
to isolate clean parabolic segments within long tracklets.
The juggler's catch-throw motion within a long tracklet
contaminates any naive parabolic fit on the tail/head.

### What would actually work

A fundamentally different approach is needed for YouTube long
tracklets. Options:
1. **Per-bounce segmentation at frame level** — detect
   individual throw-catch cycles within a long tracklet
   (not just apexes). This requires a more sophisticated
   signal that distinguishes the ball's actual parabolic
   flight from the catch-throw noise.
2. **Drop the physics check for long tracklets** — accept
   that H8 cannot distinguish identity switches from
   phase changes on long tracklets. Use H8 only for short
   tracklets and accept the high YouTube false positive
   rate as a known limitation.
3. **Use 3D ball trajectory estimation** — Ponglertnapakorn
   & Suwajanakorn (2025) used an LSTM trained on simulation
   to predict 3D ball trajectories. Their approach could
   better handle the long-tracklet phase changes.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v6_per_bounce.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v6_per_bounce_summary.json`
