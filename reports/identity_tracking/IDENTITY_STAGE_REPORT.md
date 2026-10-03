# Identity stage: first run

Date: 2026-10-02. Code: `src/tracking/`, `scripts/track_identities.py`,
`scripts/render_ball_states.py`.

## What changed

The earlier pipeline accepted airborne stitches one at a time from a constant-velocity
prediction, then repaired hand transitions at tracklet boundaries. This stage solves
identity per segment in one step: tracklets are linked by a flight arc, a brief
dropout, a shared hand, or an unexplained ("hidden") gap, and a min-cost flow picks at
most N identities. Each identity then gets a state on every frame: `AIRBORNE`, `HELD`
(with the hand) or `HIDDEN`.

## Results

All runs use stock `yolo26l` tracklets (Norfair dt50, hc5) and `yolo26s-pose` wrists.
The ball count was estimated in every case, not supplied.

| Video | Segments | Tracklets | Identities | Links (hand / flight / near / hidden) | Not used |
|-------|----------|-----------|------------|----------------------------------------|----------|
| identical_balls (18 s) | 1 | 14 | 3 | 6 / 0 / 0 / 0 | 3 tracklets (4 frames), 2 clutter |
| youtube 5-ball (15 s) | 1 | 43 | 5 | 29 / 1 / 0 / 6 | 2 tracklets (2 frames) |
| lemons (141 s selected) | 28 | 493 | 3 in 25 segments, 1 in 2, 6 in 1 | 152 / 3 / 4 / 148 | 452 observed frames |

Only identical_balls has ground truth. Six of its seven human-labelled handovers
(3→4, 4→6, 1→5, 5→10, 2→11, 6→13) fall inside one identity each, and the two static
background tracks (7, 8) are removed as clutter. The seventh label, 10→14, points at a
two-frame tracklet in the clip's last frames; it is left unassigned because two
observations do not pay for a link. `tests/test_tracking_identities.py` pins this.

The youtube and lemons numbers describe what the solver did, not whether it was right.
Nothing there has been checked against labels. On lemons almost half of the links are
hidden links, the weakest kind: they are chosen by elimination, distance and time
only.

## Findings while building it

- **identical_balls contains slow motion.** Frames ~250–780 play about four times
  slower, so the apparent gravity falls from about 2.0 to about 0.12 px/frame². A
  single gravity value classified nine seconds of flight as "held far from any hand".
  Gravity is now estimated over time within a segment.
- **Gravity tracks the performer's size in frame.** Across lemons segments the ratio of
  gravity to shoulder width is nearly constant, so a segment with too little flight
  borrows that ratio.
- **Tracklets on lemons are roughly one flight each.** They end as the hand covers the
  ball, so identity there is decided almost entirely at the hands. Flight links matter
  little on these tracklets; the flight model matters for telling flight from carry and
  for extending an arc to the wrist it reaches.
- **The simultaneous-tracklet count underestimates N** when one ball stays in a hand
  undetected. Segments are therefore floored at the video's most common estimate, and N
  is a ceiling for the solver, not a quota.

## Known limits

- Link costs in `LinkCostConfig` were set by eye on these three videos. They are not
  validated on held-out footage.
- A tracklet that already contains an identity switch inside Norfair is never split.
- Two balls hidden at the same time cannot be told apart by elimination.
- A hand link does not check that a hand holds a plausible number of balls.
- Wrists hidden behind the body read as "no hand", which pushes those handovers into
  hidden links.
- Lemons segments 17 and 21 are short and nearly detection-free (5 and 2 tracklets);
  they yield one identity each. Segment 15 is estimated at 6 balls.
- The live UI does not use this stage.

## Review

`scripts/review_identities.py --identity-dir outputs/identity_tracking/<video>` serves
a local site: the rendered review video, a per-ball state timeline, the per-segment
summary and the link list with hidden links first. Each link can be marked correct /
wrong / unclear with a note; labels go to `review_labels.csv` in the same directory and
are the input for tuning `LinkCostConfig`.
