# H1 — Hand-Pool Baseline: First-Pass Findings

**Date:** 2026-08-28 ~03:40 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** Baseline implementation completed and committed. Visual QA performed.

## 1. Hypothesis

> A simple per-hand FIFO token stack driven by `nearest-hand distance` + a
> 5-frame approach/divergence slope can identify credible catch/throw
> transitions, and the resulting `hand_links.csv` should overlap with
> hand-involved pairs in the existing reviewed stitch labels.

This is the smallest reproduction allowed by master instruction §8.

## 2. First-stage thresholds (declared from physical geometry, not labels)

| Symbol | Value | Rationale |
|---|---|---|
| `WRIST_CONF_MIN` | 0.5 | Existing pose-convention floor (E7a/E7b). |
| `HAND_REACH_PX_RATIO` | 0.15 × image_height = 108 px | Adult hand-palm radius in image, generous boundary. |
| `CATCH_SLOPE_PX_PER_FRAME` | ≤ −1.0 | A 5-frame window (~167 ms) should drop ≥ 5 px if ball is moving INTO a hand. |
| `THROW_SLOPE_PX_PER_FRAME` | ≥ +1.0 | Same magnitude in opposite direction. |
| `SLOPE_WINDOW` | 5 frames | Long enough for a real trend, short enough not to miss fast throws. |
| `MIN_SLOPE_SAMPLES` | 3 of 5 | Allow up to 2 missing-pose frames in window. |
| `MIN_TRACKLET_LEN` | 3 obs | Need ≥3 observed points to fit a meaningful slope. |

These are the **first** implementation's thresholds. The master instruction
forbids tuning to manual labels at this stage (§15). The sensitivity grid is
declared up front and is the same on every video.

## 3. Implementation

`experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool.py`

- Per-tracklet features: end-window (catch) and start-window (throw) hand
  distance + slope + nearest-side + sample count + pose conf.
- Per-frame chronological state machine with two `HandState` instances
  (left, right) holding FIFO token stacks.
- For each frame: process all throw candidates first, then all catch
  candidates; record inventory snapshot.
- At end of video: any unconsumed tokens become `UNRESOLVED_HELD_OR_LOST`.

Outputs:

- `data/hand_events.csv` (per-frame events: ENTRY/EXIT/UNMATCHED_EXIT/AMBIGUOUS_POOL_EXIT/UNRESOLVED_HELD_OR_LOST)
- `data/hand_inventory.csv` (per-frame L/R pool depth + token IDs)
- `data/hand_links.csv` (from_tid, to_tid, hand, frames, slopes, ambiguity)
- `data/tracklet_features.csv` (per-tracklet end/start summary)
- `data/summary.json` (counters, conflicts, evaluation vs reviewed labels)

## 4. Quantitative result (v1, first pass)

| Video | ENTRY | EXIT | UNMATCHED_EXIT | AMBIG_POOL_EXIT | UNRESOLVED | n_links | pred_conflicts |
|---|---|---|---|---|---|---|---|
| identical_balls_trick_000_018 | 33 | 1 | 2 | 22 | 10 | 23 | 0 |
| youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090 | 5 | 5 | 22 | 0 | 0 | 5 | 0 |

vs reviewed labels (H1-hand-link overlap only):

| Video | Reviewed | Matched correct | Matched wrong | Missed correct | Missed wrong | P | R |
|---|---|---|---|---|---|---|---|
| identical | 85 | 1 | 1 | 44 | 39 | 0.500 | 0.022 |
| youtube | 28 | 2 | 0 | 24 | 2 | 1.000 | 0.077 |

**WARNING:** the reviewed labels are an E6c candidate set (gap ≤ 10 from a
wide universe), most of which are **mid-air** pairs NOT involving hands.
Matching H1 to the full set is not the right test — H1 is intentionally a
hand-only extractor. See §5.

## 5. Visual QA — verified failure modes

Contact sheets rendered to `contact_sheets/`. Four inspected via vision:

| Event | Vision verdict | Failure mode |
|---|---|---|
| ev0002 ENTRY hand=left f=31 tid=3 dist=106 slope=-23.6 | **Questionable**: ball doesn't clearly disappear; slope unrealistically steep; vision thought the trajectory was on the right hand. | Catch criteria fires on a transient that may not be a real catch. |
| ev0006 AMBIG_POOL_EXIT hand=left f=51 tid=9 | **Likely false positive**: divergence is steep (slope=24) but the tracklet endpoint is below the hand; vision thinks the algorithm is tracking **hand motion** not ball motion. | Throw detector latches onto a tracklet whose center moves away because the **hand is moving** (not the ball). |
| ev0001 UNMATCHED_EXIT hand=right f=27 tid=6 | **False positive**: ball is already airborne (rising), passing near the hand. | Throw detector fires on a mid-air ball crossing the reach radius. |
| ev0004 ENTRY hand=left f=102 (youtube) | **False positive**: no visible ball in approach frames. | Tracklet simply *starts* near the hand without a real approach trajectory. |

## 6. Negative findings (v1)

These are first-class results and inform v2.

- **FIFO bookkeeping alone is not enough.** When the pool is held at depth
  ≥ 2, oldest-token consumption can pair a current throw with a catch from
  many seconds ago (e.g. identical `tid 3 → 9` consumed token from frame 31
  at throw frame 51, gap=20; `tid 7 → 40` consumed token from frame 56 at
  throw frame 549, gap=493). The resulting "link" has no physical
  plausibility even though both endpoints individually pass H1's rules.
- **The throw criteria is dominated by hand motion, not ball motion.** A
  thrown ball diverges because the hand accelerates; a *not-thrown* ball can
  also appear to diverge from the wrist if the wrist itself is moving. A
  stationary-ball-held-against-moving-hand test is required.
- **Catch criteria fires on tracklets that happen to terminate near a
  hand.** The "ball disappears" signature can be a detection dropout, not a
  catch. Distinguishing a real catch from a dropout needs additional
  evidence (e.g., a hand event in the same window, low-confidence detentions
  near the hand, E15-style second-tier evidence — see master §14).
- **The pool grows without bound** for the identical video: final pre_depth
  = 7 (left) + 4 (right). All end-of-video tokens are `UNRESOLVED`.
  This means **the algorithm over-detects entries and under-detects exits**,
  which is a sign that the entry bar is too lax relative to the exit bar.

## 7. Verdict

**PARTIAL PASS.** The baseline state machine runs and produces structured
artifacts (events, inventory, links, features, contact sheets). Visual QA
reveals four distinct failure modes that the master explicitly asks us to
record. Numerical recall against the reviewed labels is misleadingly low
because the labels are not a hand-test set.

## 8. Next concrete step (v2)

A TTL-bounded hand pool with stricter physics-aware filters:

1. **Token TTL**: a token that is not consumed by an exit within N frames
   of its arrival expires as `EXPIRED_HELD`. (Cap pool depth.)
2. **Stale-token rejection**: when a throw pops a token older than M frames,
   downgrade to `STALE_TOKEN_THROW` and treat the throw as
   `UNMATCHED_EXIT` for hand-link purposes.
3. **Throw strictness**: require the ball to leave the reach radius
   within the first 3 observed frames (a real throw gains height fast; a
   mid-air ball passing by does not).
4. **Wrist-movement guard**: compute the per-frame wrist velocity in the
   throw window; if the wrist moves > V px/frame, downgrade throw
   confidence (hand motion is not ball motion).
5. **Catch strictness**: require a hand event in the same hand within the
   previous W frames; an entry with no prior hand activity is suspicious.
6. Re-run on the same two videos, re-evaluate vs the gap=0 correct labels
   (which are the only ones plausibly hand-involved), and re-render
   contact sheets for the same events to verify the new filters fix the
   observed failure modes.

## 9. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_events.csv` (100 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_inventory.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_links.csv` (28 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_features.csv` (116 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets/*.png` (21 PNGs)
