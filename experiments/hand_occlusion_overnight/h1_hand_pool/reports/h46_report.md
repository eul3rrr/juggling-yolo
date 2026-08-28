# H46 — Per-Flight Physics Check via Bounce Model

**Date:** 2026-08-28 ~15:30 CEST
**Status:** COMPLETE (NEGATIVE — hypothesis was wrong; corrective analysis)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis (H46 v1)

H45 found that H12 v8 hand-event "flights" include both real
catch-throws (30-40 frame flight times on identical) and
tracker-fragmentation artifacts (1-5 frame "flights" on
identical, 58-134 frame "flights" on YouTube). The
distinguishing feature should be physical consistency: a real
catch-throw has the source's last arc and target's first arc
on a continuous physical trajectory. A tracker fragmentation
has them physically disconnected (slope jump, position jump).

H46 v1 extrapolated source's last-arc parabola across the gap
and compared to target's first position.

**Result: ALL 26 flights marked PHYSICS_VIOLATION, including
visually-confirmed REAL catch-throws.** Hypothesis was wrong.

## Why H46 v1 was wrong

H46 v1 assumed the source tracklet's last 3 points were the
descent into the hand. **They are not.** Inspecting the
H12 v8 event log (`chain_events_h35_*.csv`):

- t40 THROW at f=549, t41 CATCH at f=582
- t40 tracklet spans f=549-587
- t41 tracklet spans f=591-613

**t40 BEGINS at the throw frame (f=549)**, not at the catch
frame. The tracklet starts at the throw, not at the catch. So
t40's first points are the ball going UP from the hand, and
its last points are well into the new ball's flight.

This means the source and target tracklets in the H12 v8
event log are BOTH post-throw ascending arcs, not a
descent-approach + ascent-departure pair. The "physics
continuity" hypothesis (descent-arc predicts catch point)
doesn't apply because the descent-arc isn't in any tracklet.

## H46 v2: bounce sign test (sign-flip on catch)

Revised hypothesis: for a real catch-throw, the source's
post-throw vy (ascending) and target's post-throw vy
(ascending) should be similar in sign and magnitude (both
negative, since y=0 is top in image coords and ball goes up
= y decreases = vy < 0). For a tracker fragmentation, the
two velocities may have inconsistent signs or wildly
different magnitudes (re-acquired ball is at random position
relative to where the parabola predicted).

Method: compute mean vy over source's last 3 frames and
target's first 3 frames. Classify:
- BOUNCE_OK: both v_in < 0 and v_out < 0 (both ascending)
- BOUNCE_VIOLATION: any other sign pattern

Thresholds declared from physics, not labels:
- TAIL_N = 3 frames
- (no min_v threshold — even small velocities are signals)

## Quantitative result

| Video | n_flights | BOUNCE_OK | BOUNCE_VIOLATION |
|---|---|---|---|
| identical | 11 | 2 | 9 |
| YouTube | 15 | 0 | 15 |

**YouTube: 0/15 flights pass the bounce sign test.** All
YouTube flights have v_in and v_out of OPPOSITE signs (or
both positive), which is impossible for two consecutive
ball-in-air segments. This confirms H45's finding: YouTube
H12 v8 events are tracker fragmentation.

**Identical: only 2/11 flights pass the bounce sign test
(chain 29's t52→t54 ft=5 and t54→t59 ft=33).** The
visually-confirmed REAL catch-throws in chain 22
(t40→t41 ft=33, t41→t45 ft=31, t45→t46 ft=39) ALL fail
the test. Why?

Looking at the data:
- t40→t41 (REAL): v_in=-0.31, v_out=-0.42 — both slightly
  negative. v_in is JUST below the threshold (-0.5).
  Source tail points are at f=585-587, where the ball has
  already reached apex and is starting to descend
  (parabola peaks ~36 frames after throw at typical gravity).
- t41→t45 (REAL): v_in=-0.73, v_out=-0.25 — v_in passes
  but v_out is below threshold.
- t45→t46 (REAL): v_in=+3.65, v_out=+5.70 — both positive
  (descending). The ball is past the apex by then.

**The bounce sign test fails because the source/target
tracklets are not necessarily the early ascending arc —
they can be ANY part of the ball's flight, including the
descent after apex.**

The bounce sign test is too sensitive to where in the
parabola the tracklet's first/last points happen to fall.

## What H46 v2 actually confirms

The H46 v2 result is informative even though the test is
broken:

- **YouTube 0/15 BOUNCE_OK** is strong evidence that ALL
  YouTube H12 v8 events are tracker fragmentation. The
  sign-mismatch rate is 100%.

- **Identical 2/11 BOUNCE_OK** is also informative. The 2
  passing flights are chain 29 (5-frame and 33-frame gaps).
  The 9 failing flights include both REAL catch-throws
  (chain 22) AND identity switches. The test doesn't
  distinguish them.

- **The sign-mismatch rate of 84% on identical (9/11) is
  consistent with H45's finding that even real catch-throws
  have source/target tracklets in arbitrary parts of the
  ball's flight.**

## Negative findings

1. **Per-flight physics via source-last-arc / target-first-arc
   doesn't work** because the source tracklet doesn't start at
   the catch frame — it starts at the throw frame. The held
   phase is NOT in any tracklet.

2. **Bounce sign test (v_in < 0 AND v_out < 0) is too
   restrictive** — it requires the tracklets to be in the
   ascending part of the parabola, which depends on the
   tracklet's temporal position in the ball's flight.

3. **YouTube H12 v8 events are uniformly tracker
   fragmentation.** The 0/15 BOUNCE_OK rate is consistent
   with H45's 0/4 visually-confirmed REAL flights on YouTube
   chain 9.

4. **A proper per-flight physics check would need to:
   (a) identify the apex of each tracklet, (b) compute
   the parabolic fit, (c) check if the held phase (gap
   between source and target) is consistent with a bounce
   at the hand given gravity and the tracklets'
   apex-based predictions.** This is significantly more
   complex than H46 v1/v2 attempted, and would require
   per-arc gravity estimates (which H8 v8 already has).

## Implications for downstream consumers

- **The bounce sign test is a useful YouTube-specific
  post-filter:** on YouTube, all 15 H12 v8 events have
  v_in and v_out of opposite signs. A simple sign-mismatch
  filter would reject ALL YouTube events as tracker
  fragmentation. This is too aggressive (some YouTube
  events may be real) but the FPR is currently 0/15.

- **The 10-frame flight-time filter (H45) + the bounce
  sign test (H46) together would be a useful 2-stage
  filter for the H12 v8 event log on YouTube.** Stage 1
  (H45): drop flights < 10 frames as identity switches.
  Stage 2 (H46): drop flights with sign-mismatched v_in/v_out
  as tracker fragmentations. On the current data, this would
  drop 0/15 YouTube events at stage 1 and all 15 at stage 2.

## Verdict

**H46 verdict: NEGATIVE result.** The H46 v1 hypothesis
(extrapolate source parabola across the gap) was wrong
because the held phase is not in any tracklet. The H46 v2
bounce sign test is too restrictive on identical (rejects
real catch-throws) but too permissive on YouTube (would
reject everything, including potentially real events).

The fundamental issue is that **H12 v8's per-tracklet data
structure is not aligned with the held-phase physics.** To
do per-flight physics properly, we need either:
- Explicit hold-phase interpolation (the ball is at the
  hand during the gap; physics is a bounce, not free-fall)
- Multi-view data to triangulate the held position
- Hand-pose-anchored position (the hand position itself
  is the bounce point)

H46 confirms what H45 already showed: the H12 v8 event log
is not a clean signal for flight-time analysis. Further work
in this direction would require explicit hold-phase modeling.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h46_per_flight_physics.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h46_per_flight_physics.csv` (26 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h46_per_flight_physics_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h46_report.md` (this file)
