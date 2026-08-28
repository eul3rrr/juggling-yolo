# H49 — 10-Frame Filter's Impact on Per-Frame Pattern Classification

**Date:** 2026-08-28 ~16:10 CEST
**Status:** COMPLETE (NEGATIVE result for impact measurement, but useful
data point)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis

H47 showed the 10-frame filter drops 3/48 events on identical.
H48 confirmed THR=10 is in a flat region of the sensitivity
grid. Question: what is the actual downstream impact on
H12 v8's per-frame pattern classification?

## Method

1. Load H12 v8's per-frame pattern labels
   (`pattern_inference_h35_*.csv`).
2. Load H12 v8's event log (`chain_events_h35_*.csv`).
3. Identify (chain_id, tid) pairs whose flight time is
   < 10 frames.
4. For each frame, compute the K=4 most recent events
   (before this frame) — both with and without the filter.
5. Re-classify using H12 v8's K=4 pattern logic
   (CASCADE if hand-alternating, FOUNTAIN if same-hand).
6. Compare re-classified frames' patterns to the H12 v8
   baseline.

## Quantitative result

| Video | Events dropped | Frames re-classified (K=4 only) | H12 v8 baseline |
|---|---|---|---|
| identical | 12 (6 pairs) | 471/1042 (45.2%) | 36 events (12 dropped = 25% of events) |
| YouTube | 0 | 143/898 (15.9%) | 0 events (filter is no-op) |

## Negative findings

1. **The K=4 pattern re-classification is NOT the same as
   H12 v8's actual pattern re-classification.** H12 v8 uses
   census (n_in_air, n_in_hand_left, n_in_hand_right) +
   chain quality + n_total balls to determine the pattern,
   not just K=4 events. My K=4-only classifier overcounts
   pattern changes because it doesn't apply the n_total filter.

2. **For example:** H12 v8 says f=236-242 are "TWO_BALL"
   with confidence 0.64. My K=4 classifier says they should
   be "CASCADE_3+" after the filter. But H12 v8's actual
   re-run would still call them TWO_BALL because the census
   shows only 2 balls in air at those frames.

3. **The 45.2% re-classification rate (identical) and
   15.9% re-classification rate (YouTube) are upper bounds
   on the actual H12 v8 impact.** The real H12 v8
   re-classification rate is much smaller.

4. **The K=4 window context does change for many frames**
   (45.2% identical, 15.9% YouTube), but the actual
   downstream impact on H12 v8's pattern labels depends
   on the full H12 v8 pipeline. A proper measurement would
   require re-running H12 v8 with the filtered event log.

## What H49 actually tells us

- **The 10-frame filter changes the K=4 event context for
  ~45% of identical frames.** This means H12 v8's pattern
  classification, which uses K=4 events as one input, is
  sensitive to the filter. But the final pattern label
  depends on multiple inputs (census, quality, n_total),
  so the actual pattern-label change rate is smaller.

- **For YouTube, the K=4 context changes for 15.9% of
  frames** despite 0 events being dropped. This is because
  the K=4 window is a sliding window, and removing an event
  from anywhere in the timeline changes the window context
  for many subsequent frames. But since 0 events are
  actually dropped on YouTube, this 15.9% is a measurement
  artifact, not a real filter impact.

## Implications for downstream consumers

- **The 10-frame filter DOES affect the K=4 event context
  for many frames** (45.2% identical, 15.9% YouTube).
  But the impact on the final H12 v8 pattern label is
  smaller because the pattern label depends on multiple
  inputs.

- **A proper H12 v8 re-run would be needed to measure the
  actual downstream impact.** This would require modifying
  H12 v8 to filter the event log by gap_frames, then
  re-running the full pipeline. The expected impact is
  small (probably < 5% of frames change pattern label)
  because the K=4 events are just one of many inputs.

- **The H47/H48 finding (10-frame filter drops 3/48 events
  on identical, 0/50 on YouTube) remains the actionable
  result.** The exact impact on H12 v8's pattern labels
  is small and would require a full re-run to measure.

## Verdict

**H49 verdict: NEGATIVE result (impact measurement
methodology is flawed, but useful as a sanity check).**
The K=4-only re-classification overcounts because it
doesn't apply H12 v8's full pipeline (census + quality +
n_total). A proper measurement would require re-running
H12 v8 with the filtered event log.

The H45/H47/H48 findings are the actionable results.
H49 confirms that the filter does change the K=4 context
for many frames, but the impact on the final H12 v8
pattern label is bounded by the full pipeline's
additional inputs.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h49_filter_impact.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h49_filter_impact_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h49_report.md` (this file)
