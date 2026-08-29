# Human ground-truth labels for the yolo26l / dt50-hc5 / conf=0.15 review pass

**Date:** 2026-08-29
**Branch:** `experiment/detector-segmentation-capacity`
**Commit:** `c632692` (reviewer hardening) + this commit (label pass)
**Video:** `videos/identical_balls_trick_000_018.mp4`
**Stitcher config:** yolo26l, conf=0.15, Norfair dt=50 / hc=5 (stitcher pass-through only — not the focus of this report)

## Files

- Labels CSV: `detections/track_event_review_labels.csv` (19 events, 19 labeled)
- Manifest: `outputs/track_event_review/manifest.csv` (19 events after reviewer hardening)
- Reviewer: `scripts/review_track_events.py` (event generation + clip rendering + HTTP server)
- Tests: `tests/test_review_track_events.py` (regression tests for reviewer hardening)

## Label distribution

```text
Event types:
  u (unclear):         9
  h (hand-mediated):   7
  e (true end):        3
  total:              19

Relation direction:
  successor:   14  (END events)
  predecessor:  5  (ORPHAN START events)

Continuation status:
  selected:          7
  not_applicable:   12
  (no rows with "none" or "ambiguous")
```

## Reviewer behavior used

- Browser over Tailscale; one event per page.
- Speed: 1.0x, 0.5x, 0.25x used as needed.
- `h` = hand-mediated, then `l`/`r`/`u` to pick the hand.
- For `h`/`a`/`n`/`x`, the reviewer then required a numbered continuation choice (`1`..`9`, `0` = none, `?` = ambiguous).
- `e` = true end (no continuation expected).
- `u` = unclear; same prompts shown but no selection forced.
- Save advances automatically to the next unfinished event.

## Note on "unclear"

`u` does not currently auto-send the `notes` text. This is a known reviewer limitation.
The labeled rows below include the operator's free-form notes for every `u` so the
ambiguity is fully captured in the CSV; the operator's own writeup is summarised
here for the report.

## Per-event summary

### END events (14)

| event_key            | track | end frame | type | hand | cont | notes |
|----------------------|-------|-----------|------|------|------|-------|
| `end:3:149`          | 3     | 149       | h    | right | ID 4 | (legitimate cross-arm catch-throw, original "pink one" label) |
| `end:4:217`          | 4     | 217       | h    | right | ID 6 | (legitimate catch-throw, the rank-1 stitch candidate) |
| `end:1:219`          | 1     | 219       | h    | left  | ID 5 | "cross arm catch-throw … hands side" |
| `end:8:486`          | 8     | 486       | u    | —     | n/a  | "same as the last" — background-detector false positive (see below) |
| `end:9:495`          | 9     | 495       | u    | —     | n/a  | "same as the last" — same root cause as `end:8:486` |
| `end:7:498`          | 7     | 498       | u    | —     | n/a  | "same as the last so unclear" — same root cause |
| `end:2:882`          | 2     | 882       | h    | left  | ID 11 | (legitimate hand-mediated transition) |
| `end:5:841`          | 5     | 841       | h    | left  | ID 10 | "cross arm catch again" |
| `end:6:950`          | 6     | 950       | h    | left  | ID 13 | "less about the hand covering the ball but more about it changing its speed and direction" |
| `end:12:936`         | 12    | 936       | u    | —     | n/a  | "same as the other uncertains" — same root cause as the 486/495/498 set |
| `end:11:1078`        | 11    | 1078      | u    | —     | n/a  | "I don't see a track end in the clip maybe it was cut wrong" |
| `end:13:1078`        | 13    | 1078      | u    | —     | n/a  | "again I don't see a track end. maybe the video ends when the track ends?" |
| `end:14:1078`        | 14    | 1078      | u    | —     | n/a  | "I don't really understand much from the way the video was cut. a ball appears and then the clip ends" |
| `end:10:1074`        | 10    | 1074      | h    | right | ID 14 | "again I think it's in the change of motion more than occlusion" |
| (others:             |       |           |      |      |      | no human label) |

The 1078-end "u" cluster (events 11/13/14 by index) is operator-flagged as
**clip-window issues**, not detector failures. The post-seconds default was too
short to show what happens after the ball appears.

### ORPHAN START events (5)

| event_key              | track | first frame | type | cont | notes |
|------------------------|-------|-------------|------|------|-------|
| `orphan_start:7:465`   | 7     | 465         | u    | n/a  | "freak case of the detector seeing a juggling ball in the background for a moment … comes and goes" |
| `orphan_start:8:467`   | 8     | 467         | u    | n/a  | "similar to last one" |
| `orphan_start:1:2`     | 1     | 2           | e    | n/a  | "beginning of the clip so I put in true end" |
| `orphan_start:2:2`     | 2     | 2           | e    | n/a  | "same as before" |
| `orphan_start:3:2`     | 3     | 2           | e    | n/a  | "same as the last" |

The 465/467 "u" pair is operator-flagged as **background-detection noise**: a
real ball is briefly detected in the background, the detector picks it up, the
track ends on its own within a handful of frames, and the orphan-start fires
when there is no legitimate predecessor. There is nothing wrong with the
Norfair/stitcher pipeline on these — they are detector false positives.

The 1:2 / 2:2 / 3:2 "e" triplet is operator-flagged as **clip-window issues**:
the tracks already existed at frame 0, so the reviewer showed only the first
second of the video. The operator treated them as "track was already present
when the clip started" and labeled them `e` (true end) to mean "this is not a
real new physical event in the visible window".

## Operator narrative (verbatim, lightly trimmed)

> "In the beginning I put in a few unclears because the detector detected some
> random juggling balls in the background. It's not exactly a mistake but it
> just detects it for a quick moment and disappears. It's irrelevant, just
> background. Then there was I guess 3 clips where it belonged to the
> beginning of the clip so I put in `e` in them. And then there were some
> more unclears towards the end, but it was also because of the clip I guess
> because I only saw a track appear and the video finished very quickly and
> I wasn't even sure what it asked me."

## Three distinct "unclear" causes observed

The review surfaced three different causes of `u` (unclear). They are
*different classes of label* and downstream code should not treat them as the
same thing.

1. **Background detection noise** — detector fires on a real-but-distant
   ball for a few frames. Events:
   - `orphan_start:7:465`
   - `orphan_start:8:467`
   - `end:8:486`
   - `end:9:495`
   - `end:7:498`
   - `end:12:936`

2. **Clip window too short on the trailing side** — the track ends (or
   appears) right at the edge of the visible clip window so the human can't
   tell whether the lifecycle event is real. Events:
   - `end:11:1078`
   - `end:13:1078`
   - `end:14:1078`

3. **Clip window too short on the leading side** — the track already exists
   at the start of the visible window. Events:
   - `orphan_start:1:2`
   - `orphan_start:2:2`
   - `orphan_start:3:2`
   (these are labeled `e`, not `u`, but the *cause* is the same class of
   boundary problem)

## Downstream recommendations

1. **Increase default `--post-seconds` (and possibly `--pre-seconds`)** to
   cover the trailing edge. The 1078 cluster would have been classifiable
   with a longer window. Current default is 1.0s; 2.0s would have helped.
2. **Mark "boundary" events differently in the UI** so the human is told
   "track already exists at frame 0" / "track ends at last visible frame"
   instead of being asked a normal classification question. The `boundary`
   flag is already on `ReviewEvent` but is not surfaced.
3. **Filter background-detection events before they reach the human** by
   suppressing orphan-starts whose first observed frame is in a clearly
   background region, or by requiring a minimum number of observed frames
   before an orphan-start can fire (currently it's 1 frame).
4. **The remaining `h` labels (7) are consistent and trustworthy**. They
   are all "cross arm" / "change of motion" / "throw by hand" cases — i.e.
   the human is identifying real, classic throw-catch failures of the
   detector, not artifacts.

## Counts after operator pass

- Total events: 19
- Labelled as clear handler (`h`): 7
- Labelled as true end (`e`): 3 (all boundary orphan-starts)
- Labelled unclear (`u`): 9
  - background noise: 6
  - clip window too short: 3
- No "none" or "ambiguous" continuations recorded.
