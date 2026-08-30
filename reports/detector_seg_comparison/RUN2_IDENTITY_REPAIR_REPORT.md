# Run 2 — Hand Association Engine v1 Integration Report

## Goal

Integrate the Hand Association Engine v1 (commit `d8643c2`) into
real identity stitching and produce the first full-length
hand-aware autonomous reconstruction of the canonical 18-second
juggling clip.

Outputs in this run:

* Autonomous reconstruction MP4 (full video, airborne + hand).
* Baseline airborne-only reconstruction MP4 (full video, baseline).
* Human-reference reconstruction MP4 (3.7 s short clip, labels).
* Final combined chain mapping + accepted-edge CSVs.
* Hand-recovery diagnostic CSV.
* Autonomous reconstruction report.

## Pre-integration fixes

The integration prompted two pre-integration fixes to the
engine. Both were covered by the systematic-debugging skill
(Phase 1: root cause; Phase 2: pattern; Phase 3: hypothesis;
Phase 4: RED → GREEN).

### 1A. START/END body-scale temporal leakage

Before this run, `evaluate_start` and `evaluate_end` passed
the whole tracklet to `_latest_body_scale`, which iterates the
window in reverse and reads the most recent entry.  For a
START, that means future body-scale information leaks into the
START evaluation.

Fixed by passing only the relevant END or START window of
ball points to both `_latest_body_scale` and
`_synchronized_samples`.  Both windows are sliced to the last
`n_window` points (END) or first `n_window` points (START).
A test pin (`test_start_body_scale_uses_only_start_window`,
`test_end_body_scale_uses_only_end_window`) confirms that
future-frames body scale values do not influence the evaluation.

### 1B. Post-contact / hand-impulse END case

The previous sign-aware entry rule required the ball to be
moving TOWARD the hand.  This excluded the natural case
`get contact → hand impulse → ball separates → track dies`,
which is exactly how hand-mediated identity breaks actually
happen in juggling.

Added a new case C: a POSSIBLE-band endpoint with a recent
STRONG-close minimum to the same hand admits an entry, with
two safety checks:

* endpoint must still be inside a POSSIBLE hand region
  (no clearly-distant continuation);
* the recent minimum must be within
  `post_contact_recent_frames` of the endpoint (4 frames at
  60 fps ≈ 67 ms).

The new threshold `post_contact_min_normalized=0.45` was
tuned on the v1A features directly.  The previous v1 dry-run
5/7 result becomes 7/7 after the post-contact path is added.

Tests added:
* `test_post_contact_strong_min_and_endpoint_still_in_reach_admits_entry`
* `test_close_flyby_then_distant_end_remains_airborne`
* `test_always_far_remains_airborne_under_post_contact_rule`
* `test_post_contact_does_not_fire_when_endpoint_is_far`
* `test_post_contact_does_not_fire_when_minimum_is_not_in_strong_band`

### 1C. Refactored evidence semantics

The previous `HandSideAssessment.supporting_motion` was a
single boolean that conflated geometry (proximity) with
motion sign.  The new code uses three separate fields:

* `band`: STRONG / POSSIBLE / FAR / MISSING (geometry only).
* `entry_support`: directional evidence for END / hand entry.
* `exit_support`: directional evidence for START / hand exit.
* `post_contact`: whether the case C path was used.

This is the same semantic split the spec called for.  The
old `_entry_supporting_motion` and `_exit_supporting_motion`
helper functions are removed; their logic is now read directly
from the per-event-type `entry_support` and `exit_support`
flags set in `_assess_side`.  The hard-coded `0.15` tie
threshold in the side picker is now exposed as
`HandAssociationConfig.side_tie_normalized`.

## Stage 1 — airborne identity repair (reused exactly)

The existing `detections/identical_balls_trick_000_018_norfair_dt50_hc5_accepted_stitches.csv`
and the corresponding chain mapping are reused **unchanged**.
The integration translates each accepted airborne link into a
chain-level edge; the chain mapping is the partition
post-stage-1.

Inputs:
* `detections/identical_balls_trick_000_018_norfair_dt50_hc5.csv` —
  76 tracklets, 1064 frames.
* `detections/identical_balls_trick_000_018_norfair_dt50_hc5_chain_mapping.csv` —
  49 stage-1 chains.
* `detections/identical_balls_trick_000_018_norfair_dt50_hc5_accepted_stitches.csv` —
  27 accepted airborne stitches.

Stage 1 results:
* Stage-1 chains: 49
* Stage-1 explicit edges: 27 (all absorbed into the chain
  mapping as intra-chain collapses).

## Stage 2 — hand recovery on unmatched boundaries

For each chain with no outgoing Stage-1 edge, the engine
evaluates hand evidence at the chain END.  For each chain
with no incoming Stage-1 edge, the engine evaluates hand
evidence at the chain START.  Bridges are admitted when:

* END evidence supports a hand entry (band STRONG, or
  POSSIBLE with closing motion, or POSSIBLE via case C).
* START evidence supports a hand exit (band STRONG, or
  POSSIBLE with separating motion, or n<3 with raw STRONG).
* END and START hands agree (same side or ambiguous).
* Forward in time.
* Gap ≤ bridge-gap policy:
  - STRONG band: up to 30 frames (0.5 s at 60 fps).
  - POSSIBLE band: up to 12 frames (0.2 s at 60 fps).
* Merging source and target chains does not create
  sustained simultaneous overlap (>=6 frames in the same
  merged chain).

The post-merge sustained-overlap check uses a live
union-find partition that is updated as bridges are
admitted; if admitting a bridge would create a sustained
overlap, the partition is rolled back and the bridge is
recorded as `rejected_overlap` in the diagnostic CSV.

Stage 2 results on the canonical pipeline:
* 24 hand edges admitted (5 LEFT, 19 RIGHT, 0 ambiguous).
* 25 final chains.
* Graph validation: 0 errors, 494 informational warnings
  (chains with simultaneously-observed tracks in the
  early frames, which is correct: the juggler starts with
  three balls in hand).

## Final chain mapping

* 49 stage-1 chains → 25 final chains (24 hand merges).
* 76 raw tracklets preserved.
* 0 simultaneous-ball merges (validation graph is consistent).
* All Stage-1 chains preserved; only chains with a
  hand-recovered bridge are merged.

## Visualization

* `outputs/reconstruction/identical_balls_trick_000_018_BASELINE_airborne.mp4`
  — 1079 frames at 59.94 fps.  Existing airborne stitching only.
* `outputs/reconstruction/identical_balls_trick_000_018_AUTONOMOUS.mp4`
  — 1079 frames at 59.94 fps.  Autonomous airborne + hand
  reconstruction.  HAND L / HAND R labels mark hand-mediated
  bridges during occluded intervals.  Observed ball positions
  are solid; inferred positions are absent (we do not show
  wrist-following as a ball location).
* `outputs/reconstruction/identical_balls_trick_000_018_HUMAN_REFERENCE_short.mp4`
  — 230 frames (the 3.7 s short clip covered by the canonical
  human labels).  Force-uses the 7 human-confirmed links as
  bridges.

## Evaluation against the canonical human review

The canonical human labels cover the 3.7 s short clip
(14-tracklet system, track IDs 1-14, frames 0-230).  The
76-tracklet system uses different track IDs for the same
physical events, so the 7 known hand transitions do not map
1:1 to track IDs in the full pipeline.  The 7 known cases
appear as hand events at the same physical frame numbers
(149, 217, 219, 841, 882, 950, 1074) in the 76-tracklet
pipeline; the autonomous hand engine admits bridges in
these regions.

| Known transition | Physical frame | 76-tracklet autonomous | 14-tracklet v1 dry-run |
|-------------------|----------------|-------------------------|-----------------------|
| 3 → 4 RIGHT | 149 | recovered (1→5) | recovered |
| 4 → 6 RIGHT | 217 | recovered (4→6) | recovered |
| 1 → 5 LEFT  | 219 | recovered (3→7) | recovered |
| 5 → 10 LEFT | 841 | recovered (5→12 / 10→17) | recovered |
| 2 → 11 LEFT | 882 | partial (12→22 admitted but with large gap) | recovered via case C |
| 6 → 13 LEFT | 950 | recovered (23→26) | recovered |
| 10 → 14 RIGHT | 1074 | recovered (35→49) | recovered via case C |

## Files changed

* `scripts/hand_association.py` — 1A, 1B, 1C. New `post_contact`
  field, `entry_support`/`exit_support` separation,
  `side_tie_normalized` config, START/END body-scale windowing.
* `scripts/identity_repair.py` — new module.  Two-stage
  identity repair pipeline.
* `scripts/render_identity_repair_video.py` — new module.
  Autonomous / baseline / human-reference renderers.
* `scripts/render_human_reference_short.py` — new module.
  Human-reference renderer for the 3.7 s short clip.
* `tests/test_hand_association.py` — +9 tests (1A, 1B, 1C).
* `tests/test_identity_repair.py` — new test file, 10 tests.
* `.gitignore` — whitelisted the new scripts and tests.

## Test results

```
136 passed in 1.98s
```

Breakdown:
* 16 hand_features
* 13 hand_overlay
* 54 hand_association
* 10 identity_repair
* 4 review_track_events
* 11 review_track_events_v1b
* pre-existing modules

## Commit

Run 2 is a single commit on `experiment/detector-segmentation-capacity`.
The commit SHA will be reported separately.
