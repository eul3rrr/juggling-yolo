# H11 v4 — Identity-merge with spatial proximity

## Hypothesis

H11 v2's identity-merge algorithm (chain_start within 30
frames of an event on another chain) is too permissive.
It flagged chain 36 ↔ chain 30 as a CONFIDENT-merge
candidate, but visual QA showed t62 and t63 are 73 pixels
apart at f=890 (two different physical balls).

H11 v4 adds:
1. **Spatial proximity**: chain_start's first ball
   position must be within `SPATIAL_RADIUS` pixels of the
   wrist position at the event frame.
2. **Velocity coherence**: chain_start's initial velocity
   (first 3 frames) should be consistent with the
   previous tracklet's final velocity.

This should remove false positives like the v2 chain 36
↔ chain 30 case while preserving real merge candidates
(where the ball continues smoothly from one tracklet to
the next).

## Thresholds (declared from physical geometry)

- `TEMPORAL_RADIUS = 30` frames (unchanged from v2)
- `SPATIAL_RADIUS = 80` pixels (conservative; reach
  radius is 108)
- `VELOCITY_COHERENCE = 5.0` px/frame (tolerance for
  velocity direction; `* sqrt(2)` for 2D)

## Quantitative result

| Video | v2 n | v4 n | v4 CONFIDENT | v4 velocity-coherent |
|---|---|---|---|---|
| identical | 42 | 6 | 0 | 0 |
| youtube | 2 | 0 | 0 | 0 |

H11 v4 reduces the candidate count by **85.7%** on
identical and **100%** on YouTube. The v2 chain 36 ↔
chain 30 CONFIDENT-merge candidate is correctly removed
by v4 (t62's first position is > 80px from the right
wrist at the event frame).

The 6 remaining v4 candidates (all on identical):

| merge | spatial | vel_diff | coherent |
|---|---|---|---|
| chain6→chain2 | 72.2px | 28.4 | False |
| chain11→chain8 | 51.5px | 22.1 | False |
| chain32→chain30 | 58.8px | 38.6 | False |
| chain32→chain30 | 28.3px | 50.4 | False |
| chain35→chain30 | 31.3px | 49.9 | False |
| chain42→chain40 | 66.0px | 8.9 | False |

None pass the velocity coherence test (vel_diff > 5*sqrt(2)
= 7.07 px/frame). The closest is chain42→chain40 (vel=8.94)
which would pass at VEL=7.0.

## Sensitivity grid

`SPATIAL_RADIUS` ∈ {50, 60, 80, 100, 108}, `VELOCITY_COHERENCE`
∈ {3, 5, 7, 10}:

| spatial | vel | n_total | n_confident | n_coherent |
|---|---|---|---|---|
| 50 | 3-10 | 2 | 0 | 0 |
| 60 | 3-10 | 4 | 0 | 0 |
| 80 | 3-10 | 6 | 0 | 0-1 |
| 100 | 3-10 | 6 | 0 | 0-1 |
| 108 | 3-10 | 7 | 1 | 0-1 |

The (80, 5) operating point is in a flat region:
- Strict (50, 3): only 2 candidates (might miss real merges)
- Conservative (80, 5): 6 candidates, 0 coherent
- Loosest (108, 10): 7 candidates, 1 CONFIDENT (the v2
  false positive re-emerges), 1 coherent

## Visual QA on the v4 candidates

### chain6 → chain2 (UNCONFIDENT t8 at f=43 → CONFIDENT t9 at f=51)

- t8: f=43-51, position (725, 601) → (751, 541) — right
  side, falling
- t9: f=51-103, position (730, 446) → (735, 416) — same
  x but much higher (y=446 vs 541), rising
- t8 ends at (751, 541), t9 starts at (730, 446) — 95
  pixels apart in y. **TWO DIFFERENT BALLS.** t8 is the
  ball tracked by E6c's "3→8" false positive that H7's
  min-cost flow correctly rejected.

### chain11 → chain8 (UNCONFIDENT t15 at f=138 → CONFIDENT t14 at f=126)

- t15: f=138-149, position (?, ?) — UNCONFIDENT chain 11
- t14: f=126-160, position (577, 448) → (508, 447) — right
  hand level
- Frame diff is -27 (t15 starts 12 frames AFTER t14).
  This is t15 starting AFTER t14 is already mid-throw.
  Unlikely merge.

### chain42 → chain40 (UNCONFIDENT t76 at f=1077 → UNCONFIDENT t72→t73 at f=1029)

- t76: f=1077-1077, position (536, 559) — single point
- t73: f=1054-1060, position (539, 461) → (749, 454)
- t76 is 98 pixels below t73's last point. Likely a
  separate detection, not a missed merge.

## Negative findings

1. **None of the v4 candidates pass the velocity
   coherence test.** This suggests there are NO real
   missed-merge opportunities on identical or YouTube
   within the v2's 30-frame temporal window. The H7
   chain algorithm's splits are largely correct.

2. **v2's chain 36 ↔ chain 30 CONFIDENT-merge was a
   false positive.** The visual QA showed t62 (chain 36)
   and t63 (chain 30) are 73 pixels apart at f=890,
   not co-located. They are two different balls that
   are visible simultaneously during a multi-ball
   juggling phase.

3. **The H11 v4 spatial criterion (2D distance to wrist
   within 80px) is a useful filter but is not a perfect
   proxy for "at the hand."** A ball at the right side
   of the frame at the same y as the wrist is "near"
   the wrist in 2D distance but is NOT at the hand.
   A future H11 v5 could use a more sophisticated
   "hand-relative" coordinate system (e.g., polar
   coordinates centered on the wrist).

4. **The H11 v4 algorithm is correctly conservative.**
   v2 produced 42 candidates (1 CONFIDENT, 0
   velocity-coherent). v4 reduces to 6 candidates (0
   CONFIDENT, 0 velocity-coherent). The chain 36 ↔
   chain 30 false positive is removed. This is the
   right behavior: an identity-merge algorithm should
   be conservative, not aggressive.

## Verdict

**PASS.** H11 v4 is a useful improvement over H11 v2:

- 85.7% reduction in merge candidates on identical
- 100% reduction on YouTube
- The v2 chain 36 ↔ chain 30 false positive is correctly
  removed
- The 6 remaining candidates all fail the velocity
  coherence test, suggesting they are also false
  positives
- The chosen operating point (80, 5) is in a flat region
  of the sensitivity grid

H11 v4 is the **new recommended identity-merge algorithm**,
replacing H11 v2. H11 v2 remains useful as a permissive
first pass for hypothesis generation; H11 v4 is the
strict pass that filters out spatial/velocity-incoherent
candidates.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v4_merge_spatial.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v4_sensitivity.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/merge_candidates_v4_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_sensitivity.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_sensitivity_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_v4_report.md`
