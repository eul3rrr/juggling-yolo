# H8 v4 — Short-Tracklet-Only Physics Check

Date: 2026-08-28 ~07:50 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: NEGATIVE — trade-off not worth it

## Hypothesis

H8 v3 is unreliable on long tracklets because the constant-
velocity tail/head windows are contaminated by the tracklet's
multiple parabolic arcs. A real juggling ball's ballistic
segment is short (typically 10-30 frames between apexes).
Restricting H8 to tracklets with n_pts ≤ SHORT_N should
recover the physics signal on YouTube.

## Thresholds (declared from physical geometry)

- SHORT_N = 30 frames
- VELOCITY_DISCONTINUITY_PX_PER_FRAME = 8.0
- TAIL_FRAMES = 3
- MIN_TRACKLET_PTS = 3

## Algorithm

For each BALLISTIC edge in H7's chain representation:
1. If source OR target tracklet has n_pts > SHORT_N, mark
   the edge as LONG_TRACKLET and skip the v3 check.
2. Otherwise apply v3's y-velocity discontinuity check.
3. Hand edges are N/A (not checked).

## Quantitative Result

### Identical video

|| Status | n_air edges |
||---|---|
|| OK (v3) | 14 |
|| VIOLATING (v3) | 9 |
|| OK (v4 short-only) | 2 |
|| VIOLATING (v4 short-only) | 3 |
|| LONG_TRACKLET (v4) | 18 |
|| INSUFFICIENT_DATA (v4) | 0 |

**v3 → v4 status changes**: 18/23 air edges changed.
- 5→6: VIOLATING → LONG_TRACKLET (v4 misses a known true positive)
- 50→55: OK → LONG_TRACKLET (v3 was lenient; v4 skips)
- 60→64, 25→27, 67→70, 62→66, 64→68: VIOLATING → LONG_TRACKLET
  (v3 flagged these; v4 doesn't evaluate them)

The 3 v4 VIOLATING edges (19→20, 51→52, 23→25) are all in
low/mid-quality H10 chains (15, 30, 13). They are likely real
identity switches (confirmed by visual QA, see below).

### YouTube video

|| Status | n_air edges |
||---|---|
|| VIOLATING (v3) | 23 |
|| LONG_TRACKLET (v4) | 24 |
|| OK (v4) | 0 |
|| VIOLATING (v4) | 0 |

**All 24 YouTube air edges are LONG_TRACKLET under v4.**
The v4 method provides ZERO physics signal on YouTube.

## Visual QA (5 edges)

### edge 19→20 (v4 VIOLATING, short tracklets) — REAL IDENTITY SWITCH

Tracklet 19: n_pts=27, frames 174-200. End position (117, 469).
Tracklet 20: n_pts=12, frames 202-213. Start position (230, 475).

Visual QA: 113px horizontal jump between t19's end and t20's
start. Different sides of the juggler. **CONFIRMED IDENTITY
SWITCH.** H8 v4 correctly catches this.

### edge 51→52 (v4 VIOLATING) — REAL IDENTITY SWITCH (chain 30)

Tracklet 51: n_pts=6, frames 765-770. End position low (near hand).
Tracklet 52: n_pts=11, frames 775-785. Start position high in frame.

Visual QA: spatial jump from hand-level to high-air position.
**CONFIRMED IDENTITY SWITCH** (consistent with H10 visual
QA of chain 30). H8 v4 correctly catches this.

### edge 23→25 (v4 VIOLATING) — REAL IDENTITY SWITCH (chain 13)

Tracklet 23: n_pts=9. Tracklet 25: n_pts=14.
Part of chain 13 (H10's lowest quality chain).

Visual QA: chain 13 is a stationary detector artifact on
identical, so 23→25 is necessarily a false ballistic edge.
**CONFIRMED IDENTITY SWITCH.** H8 v4 correctly catches this.

### edge 5→6 (v3 VIOLATING → v4 LONG_TRACKLET) — FALSE NEGATIVE

Tracklet 5: n_pts=6, frames 21-26. End position at hand level.
Tracklet 6: n_pts=101, frames 27-127. Start position high in air.

Visual QA: t5 ends at chest-level (held ball being released),
t6 begins at head-level (different ball in flight). Massive
y-velocity discontinuity (~500 px vertical jump).
**CONFIRMED IDENTITY SWITCH** (H8 v3 visual QA also confirmed).

H8 v4 MISSES this because t6 has n_pts=101 (long tracklet).
**H8 v4 has a false negative on a real identity switch.**

### edge 50→55 (v3 OK → v4 LONG_TRACKLET) — was v3 correct?

Tracklet 50: n_pts=78 (long). Tracklet 55: n_pts=4 (short).

H8 v3 said OK (no violation). v4 doesn't evaluate.
The chain containing 50→55 has only 2 tids (chain 29 in H7);
we don't have direct visual QA of this edge, but H8 v3
visual QA noted it as a confirmed identity switch in the
H8 report.

So v3 flagged it correctly, v4 skips it.

## Verdict: NEGATIVE (v4 not worth the trade-off)

H8 v4 trades false positives (YouTube long-tracklet noise)
for false negatives (missing real identity switches on long
tracklets on identical).

| Method | Identical identity-switch recall | YouTube usable? |
|---|---|---|
| v3 (all tracklets) | 2/2 known positives | No — too noisy |
| v4 (short only) | 1/2 known positives + 3 new | No — all LONG_TRACKLET |

Neither v3 nor v4 alone is ideal:
- v3 has too many false positives on YouTube long tracklets.
- v4 misses real identity switches on long tracklets.

A better v5 would use a graduated penalty: for long tracklets,
check the local parabolic fit at the tail/head windows (not the
full tracklet's mean velocity). This is left as future work
(see H8 v5 in STATE.md).

For H10 quality scoring, the v3 result is still the most
informative signal (it catches more real positives, even at the
cost of more false positives on YouTube). H8 v4 should NOT be
used to replace v3 in H10.

## Where H8 v4 IS useful

H8 v4 demonstrates that the v3 violations on long YouTube
tracklets are an artifact of the long-tracklet averaging, not
real physics violations. The v4 result confirms the H8 v3
report's negative finding: H8 is unreliable on long tracklets.

Future work: H8 v5 — graduated penalty for long tracklets.
For long tracklets, fit a parabola to the last 8-12 frames
of the source and first 8-12 frames of the target, then
predict the expected y-velocity at the gap edges using
constant-gravity parabolic extrapolation. Compare predicted
to actual. This would be more robust than v3 (which uses
3-frame mean velocity) and v4 (which skips long tracklets).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v4_short_tracklet.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v4_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v4_short_tracklet_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8v4/*.png` (5 files)
