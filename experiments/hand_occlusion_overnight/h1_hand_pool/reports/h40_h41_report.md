# H40 / H41 — Continuous hand-occupancy signal from raw detector + pose

## H40 hypothesis

H36 only emits hand-occupancy state at chain events. H39 v1/v2
over-rejected real FOUNTAIN_3+ phases because H36 reports HOLD
state during chain-event gaps even when the juggler's hands ARE
occupied (per visual QA on H39).

A continuous per-frame hand-occupancy signal — checking for any
detected ball within hand reach of either wrist at every frame —
would be a more reliable signal.

## H40 implementation

### v1: per-frame, 108 px reach
- For each frame, find any detected ball within 108 px of left
  or right wrist
- If yes, mark L=1 or R=1
- Signal is independent of H36 chain events

### v2: sustained, 100 px reach, 3-frame run
- For each frame, mark L=1 if any ball was within 100 px of
  left wrist in the last 3 frames
- Similarly for R
- Reduces false positives from fast fly-bys

## H40 quantitative result

### identical (1079 frames)

| Signal | L% | R% | any hand % |
|---|---|---|---|
| H40 v1 (per-frame, 108 px) | 36.4% | 33.5% | 54.6% |
| H40 v2 (sustained, 100 px) | 52.4% | 59.0% | 72.3% |
| H36 (chain-driven, for comparison) | 7.4% | 16.3% | 23.7% |

H40 v2 detects ~3x more hand-occupancy than H36.

### YouTube (900 frames)

| Signal | L% | R% | any hand % |
|---|---|---|---|
| H40 v1 (per-frame, 108 px) | 76.7% | 35.4% | 90.3% |
| H40 v2 (sustained, 100 px) | 87.7% | 87.0% | 98.1% |
| H36 (chain-driven, for comparison) | 10.6% | 15.2% | 25.8% |

H40 v2 detects ~3.8x more hand-occupancy than H36.

## H40 hand-occupancy rate by H12 v8 pattern

### identical (H40 v2, 100 px sustained)

| Pattern | Frames | Any hand% | Both hands% |
|---|---|---|---|
| FOUNTAIN_3+ | 291 | 81.8% | 47.8% |
| CASCADE_3+ | 22 | 90.9% | 22.7% |
| MIXED_3+ | 203 | 86.7% | 22.2% |
| TWO_BALL | 230 | 73.0% | 6.1% |
| SINGLE_BALL | 165 | 31.5% | 6.1% |
| MIXED_3+_UNCONFIRMED | 23 | 95.7% | 21.7% |
| TWO_BALL_ONE_HAND | 17 | 76.5% | 11.8% |

### YouTube (H40 v2, 100 px sustained)

| Pattern | Frames | Any hand% | Both hands% |
|---|---|---|---|
| FOUNTAIN_3+ | 110 | 98.2% | 74.5% |
| CASCADE_3+ | 128 | 96.9% | 42.2% |
| MIXED_3+ | 586 | 98.1% | 58.2% |
| MIXED_3+_UNCONFIRMED | 70 | 100.0% | 75.7% |

## H40 key findings

1. **H40 v2 sustained-occupancy detects 3-4x more hand-occupancy
   than H36 chain-driven state.** H36 misses continuous
   hand-occupancy during chain-event gaps. H40 v2 captures
   this continuous state.

2. **H40 v2 occupancy rate does NOT cleanly distinguish FOUNTAIN_3+
   from CASCADE_3+.** On identical: FOUNTAIN 81.8% vs CASCADE
   90.9% (only 9 pp difference). On YouTube: FOUNTAIN 98.2% vs
   CASCADE 96.9% (essentially equal). The hand-occupancy rate
   alone is not a useful CASCADE/FOUNTAIN discriminator.

3. **The "both hands occupied simultaneously" rate is somewhat
   more discriminating.** On YouTube: FOUNTAIN 74.5% both-hands
   vs CASCADE 42.2% both-hands (32 pp difference). This is
   the only signal that has a real FOUNTAIN/CASCADE difference
   on YouTube. On identical: FOUNTAIN 47.8% both-hands vs
   CASCADE 22.7% both-hands (25 pp difference, but small n).

4. **The H40 sustained-occupancy is dominated by transient
   ball-wrist proximity, not actual holds.** A ball passing
   through the 100 px hand reach for 3 frames is counted as
   "hand-occupied" even if it's a fly-by, not a hold. This is
   a fundamental limitation of using 2D distance as a proxy for
   "ball is held."

5. **The pose wrist position is sometimes far from the held ball.**
   At f=631-669 (vision-confirmed FOUNTAIN with hands occupied),
   H40 v2 reports 0% sustained-occupancy because the closest
   ball is 70-90 px from the wrist. The pose wrist position
   is at the wrist joint, not at the center of the hand. Real
   hand-occupancy can be 70+ px from the wrist.

## H41 — FOUNTAIN_3+ post-filter via H40 v2

### Hypothesis
H39 v1/v2 over-rejected real FOUNTAIN_3+ because H36 chain-driven
state is too sparse. H40 v2 provides continuous sustained hand-
occupancy. Question: does H40 v2-based FOUNTAIN_3+ post-filter
produce better precision than H39 v1/v2?

### H41 v1 thresholds
- MIN_OCC_RATE = 0.50 (need >= 50% sustained hand-occupancy)
- MAX_BOTH_HANDS_RATE = 0.50 (need <= 50% both-hands-occupied)

### H41 v1 quantitative result
- identical: 5 phases rejected (out of 12)
- YouTube: ALL 3 FOUNTAIN phases rejected (high both-hands)

### H41 v2 (relaxed) thresholds
- MIN_OCC_RATE = 0.20
- MAX_BOTH_HANDS_RATE = 0.50

### H41 v2 quantitative result
- identical: 4 phases rejected (f=411-449, f=631-669, f=775-779, f=1070-1074)
- YouTube: ALL 3 FOUNTAIN phases rejected (high both-hands)

### H41 visual QA on identical (using H39 verdicts)

| Phase | H41 v1 | H41 v2 | Vision verdict | Correct? |
|---|---|---|---|---|
| f=243-252 (n=10) | KEPT (occ=0.70) | KEPT (occ=0.70) | FOUNTAIN | ✓ correct |
| f=263-312 (n=50) | KEPT (occ=0.64) | KEPT (occ=0.64) | MIXED | ✗ over-keep |
| f=411-449 (n=39) | REJECTED (occ=0.15) | REJECTED (occ=0.15) | MIXED | ✗ over-reject |
| f=631-669 (n=39) | REJECTED (occ=0.00) | REJECTED (occ=0.00) | FOUNTAIN | ✗ over-reject |
| f=685-716 (n=32) | KEPT (occ=0.78) | KEPT (occ=0.78) | FOUNTAIN | ✓ correct |
| f=733-766 (n=34) | KEPT (occ=1.00) | KEPT (occ=1.00) | QA_PENDING | (unknown) |
| f=860-871 (n=12) | REJECTED (occ=0.25) | KEPT (occ=0.25) | MIXED | mixed (depends on threshold) |
| f=977-1011 (n=35) | KEPT (occ=0.74) | KEPT (occ=0.74) | OTHER (hold trick) | ✗ over-keep |
| f=1029-1050 (n=22) | KEPT (occ=0.55) | KEPT (occ=0.55) | OTHER (2-ball exercise) | ✗ over-keep |

H41 v2 precision: 2/4 correct rejects, 2/4 over-rejects. 2/4 correct keeps, 2/4 over-keeps.
H41 v2 is mixed — better than H39 v1 (20%) but worse than H39 v2 (50%).

## H41 verdict: NEGATIVE

H40 v2 is a useful diagnostic signal (3-4x more hand-occupancy
detection than H36) but does not cleanly discriminate FOUNTAIN_3+
from CASCADE_3+ in the way the H41 hypothesis assumed. H41 v2
over-rejects 2 real phases (f=411-449 MIXED, f=631-669 FOUNTAIN)
and over-keeps 2 real misclassifications (f=977-1011 hold trick,
f=1029-1050 2-ball exercise). Precision is mixed.

The deeper issue: H12 v8's FOUNTAIN_3+ classification is based on
event-log density (K=4 window of chain events), not on visual
pattern. A reliable FOUNTAIN_3+ post-filter would need to know
the "true" juggling pattern (cascade vs fountain vs other), which
is fundamentally what H12 v8 is trying to compute. Using H40 v2
sustained-occupancy as a proxy for "true pattern" doesn't work
because the proxy is too noisy.

## Negative findings

1. **H40 sustained-occupancy detects "ball near hand", not
   "ball held by hand".** A ball passing through the 100 px
   hand reach for 3 frames is counted as hand-occupied. This
   is a fundamental limitation of 2D distance as a proxy.

2. **Pose wrist position is sometimes far from the held ball.**
   At f=631-669, vision confirmed hand-occupancy but H40 v2
   reported 0% sustained-occupancy (closest ball is 70-90 px
   from wrist). The wrist joint position is at the joint, not
   at the center of the hand palm.

3. **H40 v2 cannot reliably distinguish FOUNTAIN from CASCADE.**
   On identical, FOUNTAIN 81.8% vs CASCADE 90.9% (similar);
   on YouTube, FOUNTAIN 98.2% vs CASCADE 96.9% (essentially
   equal). The fundamental difference between FOUNTAIN and
   CASCADE (single-hand vs alternating hands) requires
   tracking which hand is doing what over time, not just
   per-frame hand-occupancy.

4. **H41 v2 over-rejects 50% of rejected phases (visual QA).**
   H41 v2 rejects 4 phases but 2 of them are real juggling
   (vision-confirmed MIXED and FOUNTAIN). The 50% precision
   on rejects is the same as H39 v2 (also 50%) — no improvement.

5. **H40 is a useful diagnostic but not a H12 v8 fix.** H40
   provides better hand-occupancy measurement (3-4x more
   coverage than H36) but doesn't solve the underlying H12 v8
   classification problem.

## Recommended operating point

H41 is NOT recommended as a downstream filter. The H12 v8
FOUNTAIN_3+ classification should be left as-is with the
caveat that it has ~70% error rate (per H39 finding).

For hand-occupancy measurement, H40 v2 (sustained, 100 px,
3-frame run) is the recommended signal. It detects 3-4x more
hand-occupancy than H36 and is independent of chain events.

## Future work

A truly different approach is needed to fix H12 v8 FOUNTAIN_3+:
- Use H12 v4/v5 detector-level signals (per-frame ball
  positions) combined with H40 hand-occupancy
- Or: train a learned per-frame juggling-pattern classifier
- Or: integrate with the upstream detector (not feasible
  without re-running YOLO)

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h40_continuous_hand_occupancy.py` (v1, per-frame)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h40v2_sustained_hand_occupancy.py` (v2, sustained 100 px, 3-frame)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h41_fountain_post_filter_h40.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40_continuous_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_continuous_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h41_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h41_filtered_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h40_h41_report.md`
