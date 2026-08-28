# H40 v2 — Sustained hand-occupancy signal (orphan hygiene commit)

## Why this report

The H40 v2 sustained hand-occupancy signal was implemented and run in
the episode that produced H40 v1, but the script file
(`scripts/h40v2_sustained_hand_occupancy.py`) and its data outputs
(`data/h40v2_continuous_*.csv`, `data/h40v2_summary.json`) were never
committed. The H40+H41 combined report
(`reports/h40_h41_report.md`) summarises both H40 v1 and H40 v2
quantitatively, so the signal itself is documented — but the script
itself was an untracked file at the start of this episode.

This report exists solely to make the orphan work reproducible from
the committed artifacts: it points to the script, the data, and
records the H40 v2 quantitative result so a future reader can find it.

## H40 v2 hypothesis (recap from h40_h41_report.md)

H36 only emits hand-occupancy state at chain events. H39 v1/v2
over-rejected real FOUNTAIN_3+ phases because H36 reports HOLD state
during chain-event gaps even when the juggler's hands ARE occupied
(per visual QA on H39).

A continuous per-frame hand-occupancy signal that requires
sustained wrist-proximity (≥ 3 consecutive frames within 100 px)
should give a more reliable signal than H40 v1's per-frame 108 px.

## H40 v2 implementation (recap)

- `HAND_REACH_SUSTAINED = 100.0` px
- `MIN_RUN_FRAMES = 3`
- For each frame f, mark `L40v2 = 1` if any ball was within 100 px
  of the left wrist in frames [f-2, f]. Similarly for R.
- Uses raw detector output (`detections/<stem>_norfair_dt50_hc5.csv`)
  + YOLO-Pose wrists (`detections/<stem>_yolo26s-pose.csv`) — NOT
  chain events.
- Cross-references H12 v8 pattern labels.

## H40 v2 quantitative result (reproduced from data/h40v2_summary.json)

### identical (958 frames)

| Metric | Value |
|---|---|
| L40v2 frames | 502 (52.4%) |
| R40v2 frames | 565 (59.0%) |
| Any-hand frames | 693 (72.3%) |
| FOUNTAIN_3+ any-hand | 81.8% |
| CASCADE_3+ any-hand | 90.9% |
| FOUNTAIN_3+ pure single-hand | 34.0% |

### YouTube (894 frames)

| Metric | Value |
|---|---|
| L40v2 frames | 784 (87.7%) |
| R40v2 frames | 778 (87.0%) |
| Any-hand frames | 877 (98.1%) |
| FOUNTAIN_3+ any-hand | 98.2% |
| CASCADE_3+ any-hand | 96.9% |
| FOUNTAIN_3+ pure single-hand | 23.6% |

H40 v2 detects ~3x more hand-occupancy than H36 on identical
(72.3% vs 23.7%) and ~3.8x more on YouTube (98.1% vs 25.8%). As
noted in the H40+H41 combined report, H40 v2 does NOT cleanly
distinguish FOUNTAIN_3+ from CASCADE_3+ — both have similar
any-hand rates on each video. The "pure single-hand" rate is
slightly higher for FOUNTAIN on identical (34.0% vs h40_h41
report's 47.8% both-hands) but the discrimination is weak.

## Verdict

H40 v2 is a useful diagnostic signal (independent of chain events)
but the H40+H41 combined verdict still applies: H40 v2 is a PASS
as a diagnostic, NEGATIVE as a FOUNTAIN_3+ post-filter. H43
(H12 v8 confidence < 0.55) is the recommended FOUNTAIN_3+ filter
instead.

This commit only restores the orphan script to the repository —
it does not change the experimental finding.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h40v2_sustained_hand_occupancy.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_continuous_identical_balls_trick_000_018.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_continuous_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv`
- See also: `reports/h40_h41_report.md` (H40 v1 + v1 comparison).
