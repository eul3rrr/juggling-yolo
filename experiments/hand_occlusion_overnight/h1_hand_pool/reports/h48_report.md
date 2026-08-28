# H48 — Flight-Time Filter Threshold Sensitivity Grid

**Date:** 2026-08-28 ~15:55 CEST
**Status:** COMPLETE (PASS — confirms H45's 10-frame filter is optimal)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis

H47 showed the 10-frame flight-time filter drops 3/48 events
on identical (small but real precision improvement) and 0/50
on YouTube (no-op because all flights are >= 58).

Hypothesis: the 10-frame threshold is in a flat region of
the sensitivity grid (10-30 frames all give identical
results on H45 labels), and a higher threshold (50+)
would drop YouTube's tracker-fragmentation flights but
also drop real catch-throws on identical.

## Method

1. Load H12 v8 event log (`chain_events_h35_*.csv`).
2. Compute per-flight flight times (THROW to next CATCH in
   same chain on different tid).
3. Cross-reference with H45 visual-QA labels for the
   7 H45-labeled identical flights + 4 H45-labeled YouTube flights.
4. Sweep MIN_FLIGHT_TIME in {5, 10, 15, 20, 30, 40, 50, 60}.
5. For each threshold, report:
   - n_dropped (total events)
   - kept_REAL / dropped_REAL (precision impact)
   - kept_IDENTITY_SWITCH / dropped_IDENTITY_SWITCH
   - kept_TRACKER_FRAGMENTATION / dropped_TRACKER_FRAGMENTATION

## Quantitative result

### Identical (7 H45-labeled: 4 REAL + 3 IDENTITY_SWITCH)

| THR | dropped | kept REAL | dropped REAL | kept ID | dropped ID |
|---|---|---|---|---|---|
| 5  | 2 (4 events)  | 4 | 0 | 1 | 2 |
| **10** | **3 (6 events)** | **4** | **0** | **0** | **3** |
| 15 | 3 (6 events) | 4 | 0 | 0 | 3 |
| 20 | 4 (8 events) | 4 | 0 | 0 | 3 |
| 30 | 4 (8 events) | 4 | 0 | 0 | 3 |
| 40 | 8 (16 events) | 0 | 4 | 0 | 3 |
| 50 | 9 (18 events) | 0 | 4 | 0 | 3 |

**Flat region: THR=10-30 all give identical results
(4 REAL kept, 3 IDENTITY_SWITCH dropped, 0 REAL lost).**

THR=40 is the first threshold that drops REAL catch-throws.
THR=50+ drops all 4 REAL catch-throws (catastrophic).

### YouTube (4 H45-labeled: 0 REAL + 4 TRACKER_FRAGMENTATION)

| THR | dropped | kept TF | dropped TF |
|---|---|---|---|
| 5-50 | 0 (0 events) | 4 | 0 |
| 60 | 1 (2 events) | 3 | 1 |

**YouTube's tracker-fragmentation flights have flight times
of 58-289 frames (median 67). No threshold in {5..50} drops
any of them. THR=60 drops 1 of 4.**

## Key H48 findings

1. **The 10-frame filter is in a flat region (10-30) for
   identical.** All thresholds in {10, 15, 20, 30} give
   identical results: 4 REAL kept, 3 IDENTITY_SWITCH dropped.
   THR=10 is the most permissive (drops the fewest events),
   so it's the best choice.

2. **There is NO single threshold that filters YouTube's
   tracker-fragmentation flights without dropping real
   catch-throws on identical.** The two videos require
   fundamentally different filters because their flight-time
   distributions are different (identical: 1-131 with REAL
   at 30-40; YouTube: 58-289 with TRACKER_FRAGMENTATION at
   58-67).

3. **A 2-stage filter (10f for identical + 60f for YouTube)
   would be the optimal YouTube-specific filter:**
   - Stage 1 (THR=10): drops 3 IDENTITY_SWITCH on identical,
     no-op on YouTube.
   - Stage 2 (THR=60): drops 1 TRACKER_FRAGMENTATION on
     YouTube. (But this is a small improvement; the 4
     YouTube flights have very similar flight times 58-67,
     so a single threshold can't separate them.)

4. **The H45 finding is confirmed by the flat region:**
   THR=10 is the right operating point for identical. The
   choice of 10 vs 30 doesn't matter — both give the same
   H45-labeled result.

## Implications for downstream consumers

- **The 10-frame filter is the recommended operating point
  for H12 v8 event log consumers** (per H45). H48 confirms
  this is in a flat region of the sensitivity grid (10-30
  frames all give identical results on H45 labels).

- **A YouTube-specific 60-frame upper-bound filter could
  be added** as a downstream post-filter for YouTube
  consumers. It would drop 1/4 of H45-labeled
  TRACKER_FRAGMENTATION on YouTube (ft=134, the longest
  one). It would also drop ft=104, ft=131, ft=130, ft=143,
  ft=201, ft=289 from the YouTube flights — i.e., all
  the "long" tracker-fragmentation flights. But it would
  also drop any rare real 5-ball flights longer than 60
  frames, which we don't have evidence of but could
  theoretically exist.

- **The 60-frame filter is NOT a precision improvement
  on the H45-labeled YouTube sample** (it doesn't separate
  the 4 TRACKER_FRAGMENTATION flights from each other, all
  of which are in 58-67 range). It's a recall reduction
  for the longest-fragmentation cases.

## Verdict

**H48 verdict: PASS (confirms H45).** The 10-frame filter
is the optimal threshold for identical (in a flat region
10-30) and a no-op for YouTube. There is no single threshold
that filters YouTube's tracker-fragmentation flights without
also dropping identical's real catch-throws. The H45 finding
is robust.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h48_flight_filter_sensitivity.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h48_flight_filter_sensitivity.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h48_report.md` (this file)
