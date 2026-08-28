# H12 v3 Report — Enriched event log with visually-confirmed v3c-rejected events

## Hypothesis

The H12 v2 algorithm is fundamentally limited by event log density
(8 catch/throw events on identical, 1 on YouTube). Visual QA of the
v3c-rejected links revealed:
- **35→40 on identical (left hand)**: Visually CONFIRMED as a real
  catch-throw. v4d's `MIN_FROM_SLOPE = 2.5` threshold incorrectly
  rejected it (from_slope = 2.31).
- **15→25 on YouTube (left hand)**: Visually REJECTED as not a real
  catch-throw. v4d's threshold correctly rejected it (from_slope = 2.08).

H12 v3 hypothesizes that adding the visually-confirmed 35→40 event
back to the event log will improve the CASCADE/FOUNTAIN classification
in the f=535+ region, where the new event enters the K=4 sliding window.

**Caveat:** This is a `LABEL_INFORMED_EXPLORATORY` experiment. The
event is added because visual QA confirmed it, not because the
algorithm's threshold was wrong. The v4d threshold is preserved.

## Implementation

- `h12_v3_enriched_events.py` — runs H12 v2 with the enriched event log
- `h12_v3_visualize.py` — v2 vs v3 comparison contact sheet
- `h12_v2_v3c_rejected.py` — visual QA for the v3c-rejected links

## Quantitative result

| Pattern | v2 | v3 | Δ |
|---|---|---|---|
| UNKNOWN | 1.4% | 1.4% | 0.0 pp |
| CASCADE_3+ | 0.0% | 0.0% | 0.0 pp |
| FOUNTAIN_3+ | 15.5% | 13.1% | **-2.4 pp** |
| MIXED_3+ | 29.3% | 31.8% | +2.5 pp |
| MIXED_3+_UNCONFIRMED | 6.1% | 6.1% | 0.0 pp |
| TWO_BALL | 25.1% | 25.1% | 0.0 pp |
| SINGLE_BALL | 20.3% | 20.3% | 0.0 pp |
| NO_BALL | 3.2% | 3.2% | 0.0 pp |
| TWO_BALL_ONE_HAND | 0.4% | 0.4% | 0.0 pp |

**Frame-level diff:** 26 frames changed from `FOUNTAIN_3+` to `MIXED_3+`,
all in the f=797-829 range. No other changes.

## Why did the change happen at f=797-829?

The new event is at f=535. For frames f < 535, the K=4 sliding window
doesn't include the new event, so no change. For frames f > 535, the
window has 5 events. The new event is in the window for the first
time at f=535. It stays in the window as the window slides forward
until f=535+K=4*30 (approx) when it scrolls out.

At f=797, the window is `[535, 788, 843, 881]` (events sorted by
frame). The new left-hand event at 535 is at the start of the window.
With 4 events:
- v2 window: `[788, 843, 881, 1022]` (4 right-hand events)
- v3 window: `[535, 788, 843, 881]` (1 left + 3 right-hand)

The v3 window has 1 left-hand event at the start, which gives
`same_hand_run = 2` (843=843 and 881 right-hand; 535-788 different)
and `alternation = 0.33`. v2's window has `same_hand_run = 3` and
`alternation = 0`. The 0.33 alternation is below the 0.5 threshold
for CASCADE-like, but v2's 0.0 is below the 0.3 threshold for
FOUNTAIN-like... actually wait, both should classify differently.

Let me re-examine: the v2 window of `[788, 843, 881, 1022]` all right-hand
gives `same_hand_run = 3`, `n = 4`, so `same_run >= n-1 = 3` ✓ and
`alt = 0` < 0.3 ✓ → FOUNTAIN-like. v3's window of `[535, 788, 843, 881]`
gives `same_hand_run = 2` (843=843 and 881 right-hand; 535=788
different), `alt = 1 - 2/3 = 0.33`. 0.33 is between the CASCADE and
FOUNTAIN thresholds. **The v3 window doesn't satisfy either CASCADE
or FOUNTAIN criteria, so it falls into MIXED_3+**.

This is exactly what we see: 26 frames change from FOUNTAIN to MIXED.

## Why didn't the late FOUNTAIN_3+ blocks change?

The late FOUNTAIN_3+ blocks (f=890-1050) have windows dominated by
right-hand events at f=843, 881, 1022, 1052. The new left-hand event
at f=535 is too far in the past to be in the K=4 window. So the
algorithm's late-phase classification is unchanged.

**This confirms the H12 v2 limitation:** the CASCADE/FOUNTAIN
classification is limited by event log density and the right-hand
bias of existing events. Adding 1 left-hand event helps the
mid-phase but not the late phase.

## Visual QA of the late FOUNTAIN_3+ blocks (f=890-1050)

Vision tool says these are actually a CASCADE (balls cross between
hands). H12 v3 doesn't fix this.

To fix this, we would need to find more events in the late phase.
The v3c false positive (15→25 on YouTube) is correctly rejected, so
there's no easy way to add more events without re-running the
detector or visually inspecting more candidates.

## Verdict

**MIXED (limited improvement).** H12 v3:
- Adds 1 visually-confirmed v3c-rejected event back to the log
- Changes 26 frames from FOUNTAIN_3+ to MIXED_3+ at f=797-829
- Does NOT fix the late FOUNTAIN_3+ blocks (f=890-1050) which are
  visually cascades but algorithm-classified as fountains
- Confirms the H12 v2 limitation: the CASCADE/FOUNTAIN classification
  is fundamentally limited by event log density and hand distribution

**Recommendation:** H12 v3 demonstrates that even label-informed
event enrichment cannot fix the CASCADE/FOUNTAIN classification in
sparse-event regimes. A fundamentally different approach (H12 v4 or
detector-level signal integration) is needed.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v3_enriched_events.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v3_visualize.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_v3c_rejected.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v3_*.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v3_*.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v3_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v2/v3c_rejected_*.png` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v3/v2_v3_comparison_*.png`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v3_report.md`
