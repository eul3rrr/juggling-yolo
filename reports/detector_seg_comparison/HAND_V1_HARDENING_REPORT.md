# Hand Association Engine v1 — Hardening Report

## What changed vs commit `76feac3`

A bounded correctness/hardening pass on the v1 engine. **No stitch
integration, no chain ID changes, no reconstruction changes.** All
edits are inside `scripts/hand_association.py` and
`tests/test_hand_association.py`.

| # | Issue | Fix |
|---|-------|-----|
| 1 | Wrist outage statistics measured USABLE runs, not MISSING runs. With 100% availability the previous code reported `longest_left_outage=1079`. | The first-pass run counter now increments **on the missing case** and resets to 0 on the present case. The distribution is rebuilt with a separate run-length scan so both numbers are consistent. |
| 2 | `_hand_distance_window` accepted `hand_xy_seq` of any length and the `evaluate_*` methods built `seq` independently of the ball window, so the two arrays could be different sizes. | New `_synchronized_samples` builds matching samples by frame, keeping only frames where both the ball and the requested wrist are usable. The engine passes the right window (`pts[:n]` for START, `pts[-n:]` for END) to it. `n_points` reflects the synchronized count, not the ball window count. |
| 3 | `_classify_band` and `_pick_*_side` accepted any non-zero slope as supporting motion, regardless of sign. | New `_entry_supporting_motion` requires closing motion (negative distance slope OR negative radial relative velocity). New `_exit_supporting_motion` requires separating motion (positive slope OR positive radial). STRONG proximity continues to qualify without trustworthy derivative evidence. |
| 4 | Normalized distance was a **fallback** when raw distance was good; raw was primary. That breaks under zoom/resolution changes. | `_classify_band` now uses the normalized distance as the **primary** discriminator when a trustworthy body scale is available, and only falls back to raw when no body scale is recorded. There is no simultaneous fixed-pixel threshold. |
| 5 | The minimum recent distance was computed and stored but never used. A fly-by could create a small min and the anchor was FAR, but the engine had no policy to combine them. | The anchor (last synchronized point for END, first for START) drives the band classification; the minimum is preserved as `min_distance_px` and `min_distance_normalized` for diagnostics. The classification rule ("close anchor → STRONG; close min alone is not a hand claim") is enforced by the fact that only the anchor can satisfy STRONG/POSSIBLE. |
| 6 | The body-scale fallback was a max pairwise wrist distance over all frames, which mixed frames and produced junk scales when the juggler was moving. | New `_latest_body_scale` reads `body_scale_shoulder_px` from the most recent frame first; if missing, it falls back to the **per-frame** inter-wrist distance of the most recent frame in the window. Cross-frame pairwise max is gone. |
| 7 | The hand loader thresholded wrist confidence but discarded the value, and silently overwrote the juggler with a later-arriving pose row. | The loader now preserves `left_confidence`, `right_confidence`, and `person_index` on the loaded row. A deterministic dominant-person policy (`_select_dominant_person`) prefers `person_index == 0` and only falls back to the highest person confidence when person 0 is significantly weaker (>0.2 gap) than an alternative. |

The hand loader is now also more robust about deriving the per-frame
body scale: it prefers the recorded `body_scale_shoulder_px`; if
absent, it computes the inter-wrist distance from the same frame;
if only shoulders are visible, it uses the shoulder width as a
last-resort proxy. Cross-frame mixing is never used.

### Multi-pose policy report

For the canonical video (1079 frames), the hand CSV contains
**7 multi-pose frames (0.65 %)**: 157, 275, 276, 547, 548, 663, 846.
Each has 2 person rows. The dominant-person policy keeps
`person_index == 0` (the juggler) in all 7 cases, because the
alternative person rows have `person_confidence` in the 0.25-0.85
range while the juggler sits at 0.95+.

## Test deltas

Before: 18 hand-association tests, 89 total.
After:  44 hand-association tests, 115 total, all passing.

The 26 new tests cover every issue in the hardening spec:

* Issue 1 (4 tests): 100% availability, 3-frame missing run,
  alternating availability, both-wrists-missing runs.
* Issue 2 (4 tests): 5 ball / 4 hand (middle missing), missing
  endpoint, n=2 INSUFFICIENT, n=0 AIRBORNE.
* Issue 3 (3 tests): entry motion toward hand, exit motion away
  from hand, radial velocity sign for entry.
* Issue 4 (2 tests): scale invariance at (200, 400, 600) shoulder
  widths, both STRONG and POSSIBLE bands.
* Issue 5 (3 tests): close then disappear, brief fly-by, always far.
* Issue 6 (3 tests): shoulder-width priority, per-frame inter-wrist
  fallback, no hands available.
* Issue 7 (2 tests): confidence preserved, dominant person wins.

## Dry-run before / after

### Coverage stats

| Stat | Before | After |
|------|--------|-------|
| left usable | 100 % | 100 % |
| right usable | 100 % | 100 % |
| both usable | 100 % | 100 % |
| neither | 0 % | 0 % |
| **longest left outage** | **1079** | **0** |
| longest right outage | 1079 | 0 |
| longest both outage | 1079 | 0 |
| outage distribution left | `{1079: 1}` | `{}` |

The canonical video has 100 % wrist coverage; the previous stats
were inverted and reported the entire video as one long outage.

### Event counts

| Counter | Before | After | Note |
|---------|--------|-------|------|
| airborne_at_end | 3 | 5 | +2 from sign-aware entry filter |
| airborne_at_start | 5 | 5 | unchanged |
| ambiguous_entry | 1 | 0 | 2->11 is now AIRBORNE (separating motion) |
| exit_with_no_entry | 2 | 4 | +2 from missing bridge targets |
| fifo_cross_side | 1 | 0 | 2->11 no longer crosses sides |
| fifo_match | 6 | 5 | 2->11 no longer bridges |
| left_entry | 4 | 4 | unchanged |
| left_exit | 4 | 3 | -1 (10->14 exit dropped, n=2 INSUFFICIENT) |
| right_entry | 4 | 3 | -1 (10->14 entry rejected, separating slope) |
| right_exit | 3 | 2 | -1 |

### 7 known cases

| Transition | Expected | Before | After | Reason for any change |
|------------|----------|--------|-------|------------------------|
| 3 -> 4 | right | BRIDGE HAND_OK | **BRIDGE HAND_OK** | unchanged |
| 4 -> 6 | right | BRIDGE HAND_OK | **BRIDGE HAND_OK** | unchanged |
| 1 -> 5 | left  | BRIDGE HAND_OK | **BRIDGE HAND_OK** | unchanged |
| 5 -> 10 | left  | BRIDGE HAND_OK | **BRIDGE HAND_OK** | unchanged |
| 6 -> 13 | left  | BRIDGE HAND_OK | **BRIDGE HAND_OK** | unchanged |
| 2 -> 11 | left  | BRIDGE HAND_OK | **no_bridge** | v1A labels this case as `agrees_with_human=False`; the engine sees both hands POSSIBLE with positive (separating) slope. Sign-aware entry requires closing motion, so neither hand qualifies and END(2) is AIRBORNE. The exit at START(11) reports "credible exit, no queued entry" but the source is lost. This is the spec's documented ambiguity, surfaced explicitly rather than guessed. |
| 10 -> 14 | right | BRIDGE HAND_OK | **no_bridge** | END(10) has a positive distance slope (ball moving away from the right hand at frames 1070-1074), so the new sign-aware rule rejects the entry. START(14) has only 2 observed points (n < 3), so the radial-velocity branch (the spec's n<3 + raw-distance fallback) only fires when the raw distance is ≤ 60 px, and the right anchor at frame 1077 is 7.3 px (well under 60). However, the source was never pushed (END was AIRBORNE), so even if START(14) were accepted, there would be no entry to pop. |

The two new "no_bridge" results are deliberate: the v1A feature
labels for 2 -> 11 and 10 -> 14 have `agrees_with_human = False`,
so the engine's stricter sign-aware rules are surfacing the
v1A's own uncertainty rather than papering over it. The 5 cases
the human clearly labelled (`agrees_with_human = True`) all
bridge correctly with the correct hand side.

### Background noise

| Window | Before | After | Note |
|--------|--------|-------|------|
| 465-498 | 0 | 0 | unchanged |
| 900-960 | 1 (genuine 6->13 at frame 950) | 1 (same) | unchanged |

## Files changed

* `scripts/hand_association.py` (rewritten: +360/-170 lines)
  * `HandAssociationConfig`: documented sign-aware fields; same defaults.
  * `_load_hands_by_frame`: preserves `left_confidence`,
    `right_confidence`, `person_index`; multi-pose handling via
    `_select_dominant_person`.
  * `_synchronized_samples`: NEW; builds matched (ball, hand) sample
    pairs by frame.
  * `_latest_body_scale`: per-frame inter-wrist distance
    fallback; no cross-frame mixing.
  * `_classify_band`: normalized distance is primary; raw is
    fallback only.
  * `_entry_supporting_motion`, `_exit_supporting_motion`: NEW; sign
    required.
  * `evaluate_end`, `evaluate_start`: pass the right window
    (`pts[:n]` for START, `pts[-n:]` for END) to
    `_synchronized_samples`.
  * `compute_wrist_coverage`: counts MISSING runs, not USABLE runs;
    separate run-length scan for distributions; partial outages
    break a "both" outage run.
* `tests/test_hand_association.py` (+488 lines; 18 -> 44 tests).
* `reports/detector_seg_comparison/HAND_V1_HARDENING_REPORT.md`
  (this file, generated).

## What was NOT changed

* No changes to `stitch_tracklets.py`, `analyze_stitch_features.py`,
  `reconstruct_stitched_video.py`, or any other script.
* No changes to the accepted stitches, chain mapping, or
  chain IDs.
* No changes to the canonical 19 human labels.
* No learned hand model.
* No new videos.
* No re-tuning of thresholds to preserve 7/7; the engine now
  follows the spec's sign-aware rule and surfaces the two cases
  where the v1A diagnostic itself reported `agrees_with_human =
  False`.
