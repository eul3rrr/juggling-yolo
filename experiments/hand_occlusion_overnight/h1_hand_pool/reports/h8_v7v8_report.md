# H8 v7 / v8 — Per-bounce arc segmentation for long tracklets

## Motivation (master §11, STATE.md items 14, 17)

H8 v3, v5, v6 all rely on the last 3-8 frames of source and first
3-8 frames of target for physics checks. This works for short
tracklets but fails on long YouTube tracklets (n_pts > 100), where
the "last 8 frames" might be in a completely different parabolic
arc than the "first 8 frames of the next tracklet".

H8 v7 and v8 attempt per-bounce segmentation: split each tracklet
into parabolic arcs, then do physics checks between adjacent arcs.

## H8 v7: vy-sign-change segmentation (NEGATIVE)

Approach:
- Smooth vy with K=2 window.
- Find vy sign changes; arcs span between sign changes.

Result on identical (76 tracklets):
- 73 tracklets with 1 arc (smoothing destroyed intra-tracklet
  sign changes).
- Per-arc gravity (clean 0.05<g<5.0): mean=0.86, median=0.41.
- Air-edge physics: 11/23 OK, 11/23 VIOLATING, 1 INSUFFICIENT.
- Same as v5: smoothing was the wrong approach.

Result on YouTube (40 tracklets):
- 38 tracklets with 1 arc.
- Per-arc gravity: mean=0.45, median=0.46 (matches quoted 0.5).
- Air-edge physics: 4/24 OK, 19/24 VIOLATING, 1 INSUFFICIENT.
- Same as v5: smoothing still wrong.

Verdict: NEGATIVE. v7 doesn't actually segment long tracklets.

## H8 v8: local-extrema segmentation (MIXED)

Approach:
- Detect local extrema in y with min-distance=5 frame filter
  (peaks AND valleys).
- Split tracklet into arcs at extrema boundaries.
- Per-arc parabolic fit (3-parameter least-squares).
- Cross-edge physics check: find the arc containing the
  connection point (NOT always the last/first arc of the
  tracklet), predict vy at connection point, extrapolate
  with constant gravity, compare to target's vy at its
  connection point.

Result on identical (76 tracklets):
- 1-5 arcs per tracklet (median 1-2, max 5)
- Per-arc gravity (clean): mean=0.90, median=0.69
- Air-edge physics: 6/23 OK, 7/23 VIOLATING, 10/23 INSUFFICIENT

Result on YouTube (40 tracklets):
- 1-12 arcs per tracklet (median 2-4, max 12)
- Per-arc gravity (clean): mean=0.46, median=0.46
- Air-edge physics: 0/24 OK, 23/24 VIOLATING, 1 INSUFFICIENT

## Key finding 1: per-arc gravity statistics

| Video | n_arcs | per-arc g (clean) |
|---|---|---|
| identical | 76 | median 0.69, mean 0.90 |
| YouTube | 128 | median 0.46, mean 0.46 |

The YouTube per-arc gravity is well-calibrated to the quoted
0.5. The identical per-arc gravity is HIGHER than 0.5. This
could be because:
- The juggler in the identical video is closer to the camera
  so gravity in pixels is larger (pixel/m^2 depends on
  apparent size).
- The juggler in the identical video uses hand motion during
  throws/catches, contaminating the parabolic fit.
- The identical video tracklets are shorter, so each arc
  captures less of the parabolic motion (less averaging).

**The per-arc gravity distribution is a useful TRACKLET
QUALITY signal** that H10 v6 could use as a 4th quality
dimension (alongside H3, H8 v5, H9).

## Key finding 2: cross-edge physics is hard on YouTube

v8's air-edge check fails on YouTube (0/24 OK). The reason:
most YouTube H7 BALLISTIC edges are actually catch+throw events
in disguise. H7's chain algorithm classifies them as
BALLISTIC because they don't have a hand-edge annotation, but
the underlying physical reality is a hand transition with
high-velocity discontinuity.

For example, edge 4→18 on YouTube:
- t4 ends at f=416 (bottom of arc, falling fast at vy~12.6).
- t18 starts at f=420 (top of arc, rising fast at vy~-17.9).
- The velocity change is large but the transition is physical:
  catch at f=416, throw at f=420.

v8 correctly identifies the discontinuity but misinterprets
it as an identity switch when it's really a catch+throw.

**v8 is NOT useful as a YouTube air-edge quality signal.**
A future v9 should combine physics + hand-region checks to
distinguish catch+throws from identity switches.

## Verdict

**v7: NEGATIVE** (smoothing was wrong approach).
**v8: MIXED** (good per-arc statistics, bad cross-edge check).

**Useful contribution**: per-arc gravity distribution as a
tracklet-quality signal. Future H10 v6 should integrate
this as a 4th quality dimension.

**YouTube long-tracklet problem is fundamental**:
- v3: fails due to long-tail contamination
- v4: fails due to skipping all long tracklets
- v5: marginally better (parabolic fit on whole tracklet)
- v6: fails due to coarse apex detection
- v7: fails due to smoothing destroying sign changes
- v8: best per-arc statistics, but cross-edge check
  doesn't work because H7's BALLISTIC edges are mostly
  catch+throws in disguise.

A truly different approach is needed for YouTube long
tracklets. Candidates:
- Per-frame per-bounce segmentation at the FRAME level
  (not just extrema)
- 3D ball trajectory estimation (Ponglertnapakorn &
  Suwajanakorn 2025)
- Hand-region check: a BALLISTIC edge that crosses a
  hand region is likely a catch+throw, not a mid-air
  continuation

## Artifacts

- `scripts/h8_v7_arc_physics.py`
- `scripts/h8_v8_extrema_arcs.py`
- `data/h8_v7_arc_physics_*.csv` (2 files)
- `data/h8_v7_arc_physics_summary.json`
- `data/h8_v8_extrema_arcs_*.csv` (2 files)
- `data/h8_v8_extrema_arcs_summary.json`
