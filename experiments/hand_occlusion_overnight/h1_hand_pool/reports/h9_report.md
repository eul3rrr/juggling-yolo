# H9 — Object permanence: bridge detector dropouts in H7 chains

**Date:** 2026-08-28 ~07:25 CEST
**Status:** COMPLETE
**Verdict:** PASS — useful as a chain quality measurement

## Hypothesis

H7 chains are punctuated by detector dropouts (the detector misses
the ball for some frames, then picks it up again). By modeling the
chain as a single physical ball, we can identify "missing" frames
and quantify the dropout rate. This tells us how much of the chain
is "real observations" vs "gaps where we assume the ball is still
there."

## Approach (declared from physical geometry, not from manual labels)

For each H7 chain:
1. Compute the timeline of tracklet coverage (frame ranges).
2. Identify GAPS: periods of ≥5 frames where no tracklet is active
   in the chain.
3. For each gap, use a constant-velocity linear interpolation
   between the source tracklet's last point and the target
   tracklet's first point. This is the "object permanence"
   prediction.
4. Report chain coverage: (observed frames) / (total span).

The metric is a *measurement*, not a *recovery*. H9 doesn't
generate new chains — it measures how much of each chain is
real observation vs gap.

## Quantitative result

| Video | chains (multi) | total gaps | total gap frames | total observed | total span | coverage |
|---|---|---|---|---|---|---|
| identical | 17 | 31 | 350 | 1733 | 2090 | **82.9%** |
| YouTube | 10 | 24 | 215 | 3936 | 4155 | **94.7%** |

Identical has more gap frames per chain (350/17 = 20.6 vs 215/10 = 21.5
per chain — actually similar) but a lower overall coverage because
the chains are shorter (less time for the same number of gaps).

The identical video's lower coverage (82.9% vs 94.7%) reflects
that the identical video is more dynamic (more hand events, more
detector dropouts during holds).

## Chains with biggest gaps (identical)

| Chain ID | tids | n_tids | span | observed | gaps | gap frames |
|---|---|---|---|---|---|---|
| 30 | 51, 52, 54, 59, 63 | 5 | 181 | 115 | 4 | **66** |
| 23 | 35, 37, 40, 41, 43, 45, 46 | 7 | 210 | 150 | 6 | 60 |
| 31 | 53, 60, 64, 68, 71 | 5 | 284 | 239 | 4 | 45 |
| 13 | 17, 23, 25, 27 | 4 | 148 | 110 | 3 | 38 |
| 8 | 11, 14 | 2 | 74 | 46 | 1 | 28 |

Chain 30 has 3 HAND_TRANSITIONS in its 4 edges — most of its gap
frames are real hand-hold phases. This is the kind of chain
where object permanence is most useful: the ball is in the
hand, the detector can't see it, but the chain is still valid.

## Visual QA

Rendered `contact_sheets_h9/chain30_object_permanence.png`
showing chain 30 with all 5 tracklets and the 4 gap windows.
Visual QA confirmed:
- All 4 gaps in chain 30 are real hand-hold phases (ball
  visibly in the hand during the gap).
- The detector fails primarily because of hand occlusion
  (hand/fingers cover the ball) and motion blur at the
  apex of trajectories.
- Object permanence is the correct interpretation: the
  ball exists and is being held — it just temporarily
  escapes detection due to occlusion.

## Negative findings

- H9 is a *measurement*, not a *recovery*. It doesn't generate
  new chains or fill in new detections. The gap frames remain
  detector dropouts; H9 just quantifies them.
- The YouTube video's higher coverage (94.7%) reflects that
  YouTube tracklets are very long (some 415 frames) — most of
  the chain time is in-tracklet, not in gaps.
- H9 doesn't help with the YouTube identity switches (e.g.,
  4→18, 1→9, etc.) that H8 flagged. Those are E6c-level
  false positives, not detector dropouts.
- The "object permanence" prediction (linear interpolation)
  is a crude approximation. A more accurate prediction would
  use a Kalman filter with constant gravity (H8 v2 idea).

## Verdict

**PASS.** H9 successfully measures chain coverage and quantifies
detector dropouts. The measurement is useful for understanding
chain quality: chains with high coverage are well-observed;
chains with low coverage have many gaps that the model assumes
the ball is still there.

For chain 30 (the worst case on identical), 36.5% of the chain
time is gap frames — but visual QA confirmed all gaps are real
hand-hold phases, so object permanence is the correct
interpretation. The chain is valid; it just relies on more
assumptions than a chain with higher coverage.

## Future work (recommended for H10 or later)

- Apply Kalman filter prediction (assuming constant gravity) to
  fill gap frames with predicted positions, and check if the
  predicted position is consistent with the actual detector
  observations in nearby windows.
- Use H9's gap statistics as a per-chain confidence score:
  chains with high coverage are more reliable; chains with
  many gaps should be reviewed manually.
- Combine H8 (physics consistency) and H9 (coverage) into a
  per-chain quality score that downstream consumers can use
  to filter or rank chains.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h9_object_permanence.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h9_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h9_object_permanence_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h9/chain30_object_permanence.png`
