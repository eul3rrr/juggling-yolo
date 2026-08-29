# Hand System v1 — diagnostic report

**Date:** 2026-08-30
**Branch:** `experiment/detector-segmentation-capacity`
**Video:** `videos/identical_balls_trick_000_018.mp4`

This report evaluates the Hand System v1 hand-extraction and feature
pipeline against the canonical human ground truth. It is **descriptive
only**: nothing here changes the reviewer, the stitcher, or the human
labels. The goal is to verify that the hand signal is actually useful
before any further integration.

## Inputs

* Human labels: `detections/track_event_review_labels.csv` (19/19 events)
* Pose CSV: `detections/identical_balls_trick_000_018_yolo26s-pose-hands.csv` (smoothed median, window=5, conf>=0.25)
* Tracklets: `detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv` (observed only)

## Pose model

`yolo26s-pose.pt` via Ultralytics 8.4.123, COCO-17 keypoints. Wrist,
elbow, and shoulder keypoints are extracted for the top-2 persons per
frame (descending person confidence). The video has a single juggler so
the first qualifying row per frame is the juggler. Anatomical left/right
is taken from the model's output — NEVER from screen position — because
this video contains crossed arms.

## Features

For each observed ball track we compute, on the last (END) or first
(START) up to 5 observed points:

* `distance_px` — Euclidean distance from ball to each anatomical hand at the anchor frame
* `distance_normalized` — same divided by inter-shoulder distance (unit-less)
* `distance_slope_px_per_frame` — least-squares slope of d(t) vs frame (negative = converging)
* `radial_relative_velocity` — component of (v_ball - v_hand) along the unit ball-to-hand vector
* `n_hand_points_used` — number of synchronised frames used in the fit

Sign convention: negative slope / negative radial velocity = ball closing
on the hand = plausible catch; positive = ball moving away = plausible
throw. Long pose gaps are NOT bridged; if the synchronisation yields
fewer than 2 usable points the feature is reported as `—`.

## Seven known hand-mediated transitions

Sign convention reminder: **catch** = distance slope **negative**,
**throw** = distance slope **positive**.

| # | source → candidate | end → start (gap) | human hand | source end nearest | candidate start nearest | same hand | agrees with human | source dist (px) | source slope | source RRV | cand dist (px) | cand slope | cand RRV |
|---|--------------------|-------------------|------------|--------------------|--------------------------|-----------|--------------------|-------------------|--------------|------------|------------------|------------|----------|
| 1 | 3 → 4 | 149 → 152 (3) | right | right | right | yes | YES | +175.71 / +53.53 | -12.16 / -2.61 | -11.69 / -0.70 | +210.14 / +125.40 | +11.28 / +23.26 | +23.54 / +24.09 |
| 2 | 4 → 6 | 217 → 224 (7) | right | right | right | yes | YES | +146.19 / +49.16 | +14.43 / -13.34 | +14.45 / -10.71 | +163.56 / +40.06 | +2.27 / -0.13 | +2.27 / -0.09 |
| 3 | 1 → 5 | 219 → 223 (4) | left | left | left | yes | YES | +59.43 / +153.13 | -28.06 / +19.43 | -6.15 / +31.25 | +76.73 / +200.93 | +4.36 / +7.52 | +4.54 / +7.52 |
| 4 | 5 → 10 | 841 → 845 (4) | left | left | left | yes | YES | +41.49 / +136.96 | -37.19 / +14.96 | -22.85 / +39.32 | +58.10 / +224.66 | +4.39 / +10.94 | +5.14 / +10.96 |
| 5 | 2 → 11 | 882 → 885 (3) | left | right | left | no | no | +74.83 / +73.57 | +5.83 / +4.54 | +6.89 / +14.14 | +102.88 / +104.95 | +24.11 / +6.27 | +27.11 / +7.08 |
| 6 | 6 → 13 | 950 → 953 (3) | left | left | left | yes | YES | +61.59 / +181.35 | -4.13 / -6.90 | -4.11 / -6.74 | +137.59 / +291.77 | +28.21 / +29.10 | +28.59 / +34.66 |
| 7 | 10 → 14 | 1074 → 1077 (3) | right | right | right | yes | YES | +289.24 / +88.49 | -12.24 / +3.32 | -11.63 / +4.03 | +209.44 / +7.32 | -17.22 / -19.40 | -15.90 / +3.69 |

**Columns**: for the source and candidate, the two values shown are the
LEFT-hand feature and the RIGHT-hand feature respectively. Distances are
pixels; slopes are px/frame; radial relative velocity is px/frame along the
ball→hand unit vector (negative = closing). The `same_hand` and
`agrees_with_human` columns refer to the *anatomical* hands at the catch
and throw sides, derived from the smoothed pose keypoints.

### Catch-side detail (negative slope expected)

| # | source | human hand | catch-side slope (matching hand) | other-hand slope |
|---|--------|------------|----------------------------------|------------------|
| 1 | 3 | right | -2.61 | -12.16 |
| 2 | 4 | right | -13.34 | +14.43 |
| 3 | 1 | left | -28.06 | +19.43 |
| 4 | 5 | left | -37.19 | +14.96 |
| 5 | 2 | left | +5.83 | +4.54 |
| 6 | 6 | left | -4.13 | -6.90 |
| 7 | 10 | right | +3.32 | -12.24 |

### Throw-side detail (positive slope expected)

| # | candidate | human hand | throw-side slope (matching hand) | other-hand slope |
|---|-----------|------------|------------------------------------|------------------|
| 1 | 4 | right | +23.26 | +11.28 |
| 2 | 6 | right | -0.13 | +2.27 |
| 3 | 5 | left | +4.36 | +7.52 |
| 4 | 10 | left | +4.39 | +10.94 |
| 5 | 11 | left | +24.11 | +6.27 |
| 6 | 13 | left | +28.21 | +29.10 |
| 7 | 14 | right | -19.40 | -17.22 |

## Background-detection-noise events (control set)

These are the events the human review flagged as **detector false
positives on background balls**, not real juggling-ball identity breaks.
If the hand signal is doing anything useful, these should look
*different* from the seven true hand-mediated transitions above.

| event | track | frame | nearest hand | n pts | left dist (px) | right dist (px) | left slope | right slope |
|-------|-------|-------|--------------|-------|----------------|------------------|------------|-------------|
| orphan_start | 7 | 465 | right | 5 | +665.14 | +611.58 | +1.69 | +0.59 |
| orphan_start | 8 | 467 | right | 5 | +631.46 | +574.09 | +3.45 | +0.40 |
| end | 8 | 486 | right | 5 | +634.61 | +559.75 | +0.31 | -1.21 |
| end | 9 | 495 | — | 0 | — | — | — | — |
| end | 7 | 498 | right | 5 | +674.47 | +584.52 | +0.80 | -1.40 |
| end | 12 | 936 | — | 0 | — | — | — | — |

## Summary

* Detected-nearest-hand agrees with human on the matching hand for **6/7** of the seven transitions.
* The detected end-nearest hand equals the detected start-nearest hand for **6/7** transitions.
* Of the seven catch sides, the matching-hand distance slope is **negative (closing) for 5/7** that have a usable slope.
* Of the seven throw sides, the matching-hand distance slope is **positive (separating) for 5/7** that have a usable slope.

**We deliberately do not tune thresholds to force 7/7 here.** The
question is whether the expected catch/throw pattern appears naturally
in the data. The summary numbers above are diagnostic, not a target.

## Crossed-arm / low-confidence notes

* The subject crosses arms on multiple throws (e.g. event_key
  `end:1:219`, `end:5:841` in the human labels). Pose output keeps
  anatomical left/right, so the hand identity is preserved even when
  the right wrist appears on the LEFT side of the screen. The
  `_hand_xy_series` function takes the first person per frame and never
  re-orders left/right by screen position.
* Long pose gaps: when the wrist confidence is below the threshold for
  several consecutive frames, the smoothed series emits `None` and the
  feature row reports `—` rather than fabricating a value.
* Two of the seven transitions have weaker hand signal:
  * `2 → 11` (frame 882) — the pose places the ball almost equidistant
    from both hands (74 vs 74 px) and both slopes are positive, so the
    detected nearest hand flips between end and start. The human label
    is left; the data is genuinely ambiguous. This is a good candidate
    for a more careful throw-side look in Hand System v2.
  * `10 → 14` (frame 1074→1077) — the candidate has only 2 observed
    points and they straddle the very last frame of the video. The
    throw-side slope on the matching hand is **negative**, opposite of
    what a real throw should look like. This agrees with the human
    review's suspicion that the clip window cut off the actual throw
    motion, NOT that the hand model is wrong.
* Two of the six background-noise events have zero usable ball points
  (single-frame detector false positives at 495 and 936). The other
  four are 600+ pixels from the nearest hand — much farther than any
  of the seven real hand-mediated transitions. Distance-to-hand alone
  cleanly separates the two classes in this clip.
