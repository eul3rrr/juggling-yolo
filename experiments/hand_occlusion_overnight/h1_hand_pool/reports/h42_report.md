# H42 — H40 v2 enrichment of H36 (L, R, A) state

## Hypothesis

H36 only emits hand-occupancy state at chain events; H40 v2
detects 3-4x more hand-occupancy. A HYBRID state machine that
uses H36 chain events where available and H40 v2 sustained-
occupancy otherwise would give a more complete hand-occupancy
picture.

## Implementation

For each frame f:
1. If H36 has non-zero L+R, use H36 (chain-driven, more accurate)
2. Else if H40 v2 has non-zero L+R, use H40 v2 (continuous fallback)
3. Else, use H36 HOLD state

## Quantitative result

### identical (1079 frames)
- H36 used: 256 (23.7%)
- H40 v2 used: 556 (51.5%)
- HOLD: 267 (24.7%)

### YouTube (900 frames)
- H36 used: 232 (25.8%)
- H40 v2 used: 657 (73.0%)
- HOLD: 11 (1.2%)

The hybrid state fills in the 51-73% of frames where H36 is HOLD
but H40 v2 detects occupancy. YouTube's 1.2% HOLD is much smaller
than identical's 24.7% because H40 v2 saturates at 98.1% on YouTube.

## Hybrid state by H12 v8 pattern (identical)

| Pattern | L% | R% | Both% |
|---|---|---|---|
| FOUNTAIN_3+ | 62.1 | 63.1 | 45.3 |
| TWO_BALL | 40.4 | 48.6 | 12.5 |
| SINGLE_BALL | 7.9 | 47.2 | 4.2 |
| MIXED_3+ | 72.1 | 75.5 | 61.5 |
| CASCADE_3+ | 9.1 | 95.5 | 4.5 |
| TWO_BALL_ONE_HAND | 27.8 | 66.7 | 0.0 |

## Hybrid state by H12 v8 pattern (YouTube)

| Pattern | L% | R% | Both% |
|---|---|---|---|
| MIXED_3+ | 81.5 | 86.4 | 68.9 |
| CASCADE_3+ | 48.1 | 57.4 | 6.2 |
| FOUNTAIN_3+ | 76.4 | 93.6 | 71.8 |
| MIXED_3+_UNCONFIRMED | 95.7 | 81.4 | 77.1 |

## Key findings

1. **The hybrid state inherits H36's "R-handed bias" in some
   patterns.** CASCADE_3+ on identical has R=95.5% but L=9.1%
   in the hybrid state. This is because H36's chain events for
   the CASCADE_3+ phase f=104-122 are mostly R-hand events.
   The hybrid doesn't fix H36's handedness bias — it preserves
   it where H36 has data.

2. **H42 hybrid doesn't improve over H40 v2 for CASCADE/FOUNTAIN
   discrimination.** The both-hands rate is similar to H40 v2
   alone (YouTube FOUNTAIN 71.8% vs H40 v2's 74.5%; CASCADE
   6.2% vs 42.2% — actually H42 is WORSE for CASCADE).

3. **H42 hybrid may be useful for downstream consumers that
   need both chain-driven accuracy and continuous coverage.**
   For example, a per-frame hand-occupancy visualizer.

4. **H42 does NOT solve the H12 v8 FOUNTAIN_3+ problem.** The
   underlying issue is H12 v8's K=4 sliding window, not the
   hand-occupancy signal.

## Negative findings

1. **H42 hybrid doesn't improve CASCADE/FOUNTAIN discrimination.**
   The H36 chain events dominate the L+R decision and carry
   the same handedness bias.

2. **The H42 hybrid state is dominated by H40 v2 (52-73% of
   frames).** This means H42 is essentially "H40 v2 with H36
   overrides" — the H36 chain events are a small correction
   on top of H40 v2.

3. **H42 doesn't enable a better FOUNTAIN_3+ post-filter.**
   The both-hands rate on YouTube is 71.8% (FOUNTAIN) vs 6.2%
   (CASCADE) — a 65 pp difference, much better than H40 v2
   alone (74.5% vs 42.2%, 32 pp). However, on identical, the
   H42 hybrid is WORSE: 45.3% (FOUNTAIN) vs 4.5% (CASCADE)
   is not as useful because the CASCADE_3+ n=22 is too small
   to draw conclusions from.

## Verdict

**MIXED.** H42 hybrid state is technically working but doesn't
significantly improve over H40 v2 for CASCADE/FOUNTAIN
discrimination. H42 is useful as a diagnostic but not as a
filter.

The H42 hybrid state may be more useful for downstream
consumers that need a complete (L, R, A) timeline with
chain-driven accuracy where available and continuous coverage
otherwise.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h42_hybrid_state.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h42_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h42_hybrid_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h42_report.md`
