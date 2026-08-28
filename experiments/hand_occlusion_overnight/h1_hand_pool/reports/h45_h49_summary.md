# H45-H49 Episode Summary Report

**Date:** 2026-08-28 ~16:20 CEST
**Episodes:** H45, H46, H47, H48, H49 (5 episodes in one session)
**Status:** COMPLETE

---

## Overview

This report summarizes 5 research episodes that built on the
H43 finding (FOUNTAIN_3+ post-filter) to explore the
H12 v8 hand-event log in more depth.

The series discovered that the H12 v8 event log has
different characteristics on the two videos:
- **identical (3-ball cascade)**: 30-40 frame flight
  times are real catch-throws; < 10 frame flights are
  identity switches.
- **YouTube (5-ball cascade)**: 58-67 frame flight times
  are uniformly tracker fragmentation (not real throws).

The 10-frame flight-time filter is the actionable downstream
post-filter for H12 v8 event log consumers.

## Per-episode summary

### H45 — Per-chain flight-time / siteswap analysis (NEGATIVE with insight)

- Siteswap analysis is infeasible with the H12 v8 event log:
  only 2/13 identical chains and 1/10 YouTube chains have
  n_flights >= 3 (the minimum needed for any CV estimate).
- Per-flight distribution revealed:
  - identical 30-40 frame flights = real catch-throws
  - identical < 10 frame flights = identity switches
  - YouTube 58-67 frame flights = tracker fragmentation
- Visual QA on all 11 flights in 3 multi-flight chains
  confirmed the per-flight labels.
- 11 contact sheets rendered to `contact_sheets_h45/`.

### H46 — Per-flight physics check via bounce model (NEGATIVE)

- H46 v1 (parabola extrapolation) was wrong: source
  tracklet's last points are NOT the descent into the hand.
  They are the post-throw ascent (tracklet starts at the
  throw frame, not the catch frame).
- H46 v2 (bounce sign test): 0/15 YouTube flights pass the
  sign test (confirms H45's YouTube finding). 2/11 identical
  flights pass (too restrictive on identical).

### H47 — H12 v8 with 10-frame flight-time filter (PASS, narrow scope)

- Applies H45's 10-frame filter to H12 v8 event log.
- Drops 3/48 events on identical (6.2%) — all 3 are
  identity switches confirmed by H45 visual QA.
- No-op on YouTube (0/50 events dropped because all flights
  are >= 58 frames).

### H48 — Flight-time filter threshold sensitivity grid (PASS, confirms H45)

- Sweeps MIN_FLIGHT_TIME in {5, 10, 15, 20, 30, 40, 50, 60}.
- THR=10 is in a flat region (10-30 all give identical
  results on H45 labels). THR=40 first drops REAL catch-
  throws. THR=50+ drops all REAL catch-throws.
- YouTube: no threshold in {5..50} drops any of the 4
  TRACKER_FRAGMENTATION flights. THR=60 drops 1/4.
- There is NO single threshold that filters YouTube's
  tracker-fragmentation flights without dropping identical's
  real catch-throws.

### H49 — 10-frame filter impact on per-frame pattern (NEGATIVE for impact measurement)

- K=4-only re-classification rate: 45.2% identical, 15.9% YouTube.
- This is an UPPER BOUND on actual H12 v8 impact because
  the K=4-only classifier doesn't apply H12 v8's full
  pipeline (census + chain quality + n_total balls).
- A proper measurement would require re-running H12 v8
  with the filtered event log.

## Most important finding

**The 10-frame flight-time filter is a useful, validated,
and well-justified post-filter for H12 v8 event log
consumers.** It drops identity switches on identical
without affecting real catch-throws. The choice of THR=10
is in a flat region of the sensitivity grid (THR 10-30 all
give identical H45-labeled results).

Recommended H12 v8 event log pre-filter (per video):
- **identical**: drop (CATCH, THROW) pairs with flight
  time < 10 frames. Drops 3/48 events, all identity switches.
- **YouTube**: no effective filter at the event-log level
  (all flights are >= 58 frames). A different signal is
  needed for YouTube.

## Why YouTube is fundamentally different

The YouTube video is 5-ball cascade, faster than identical's
3-ball cascade. The detector can't keep up with the 5-ball
motion, producing fragmented tracklets that H12 v8 re-
stitches with 50-130 frame gaps. A real 5-ball cascade
flight is ~15-25 frames; YouTube's H12 v8 events show
58-67 frame "flights" because the tracker has a consistent
minimum re-acquisition delay.

A faster detector (e.g., YOLOv9) or higher frame rate
(60 fps) would help YouTube but are out of scope for this
autonomous lab. Within the current data, the YouTube H12
v8 event log is fundamentally not a clean signal for
flight-time analysis.

## Next research direction

**H50: re-run H12 v8 with the 10-frame filter applied to
the event log, and measure the actual impact on the per-
frame pattern labels.** This would close the H49 negative
result and provide a final, validated H12 v8 + 10-frame
filter operating point.

Implementation: modify `build_catch_throw_timeline` in
H12 v8 to drop (CATCH, THROW) pairs with gap_frames < 10.
Re-run the pattern inference on both videos. Compare the
new pattern distribution to the H12 v8 baseline.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_siteswap_digits.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_flight_time_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h46_per_flight_physics.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h47_h12v8_flight_time_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h48_flight_filter_sensitivity.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h49_filter_impact.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h45_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h46_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h47_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h48_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h49_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h45_h49_summary.md` (this file)
