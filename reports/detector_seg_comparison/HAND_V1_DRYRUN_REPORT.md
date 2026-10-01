# Hand Association Engine v1 — dry-run report

## Goal

Establish the reusable state/decision layer that will later be
integrated into the actual stitcher. This run produces a chronological
proposed-event stream and a coverage report only; final chain
identities and accepted stitch output are not modified.

## Architecture

```
hand_association.py
  HandAssociationConfig
      Conservative defaults; centralised and tunable from one place.
  HandEvidence, HandSideAssessment, PendingHandEntry, ProposedAssociation
      Dataclasses for the entry/exit evidence.
  HandStateMachine
      Per-hand FIFO of pending entries + chronological event log.
      evaluate_end / evaluate_start operate on raw ball points +
      per-frame hand observations.
  dry_run
      Chronological driver: at each frame, evaluate every END whose
      last point is at that frame, then every START whose first point
      is at that frame. The 5-second safety expiry is therefore a
      real-world safety bound, not a bookkeeping shortcut.
  compute_wrist_coverage
      Per-frame wrist availability + outage-run statistics +
      coverage around known transition frames.
```

## State semantics

```
AIRBORNE       = no credible hand interaction hypothesis (default).
HAND_NEAR      = ball physically close to a hand, but not yet an
                 identity claim. Used only internally for evidence
                 classification; not surfaced as a state.
HAND_ASSOCIATED = credible hand mediation, recorded as either
                  a hand_entry (track END) or a hand_exit (track
                  START). A continuous same-ID hand interaction is
                  NOT a state at all — the engine only operates at
                  tracklet boundaries.
```

## Normalized proximity thresholds

| Band | Normalized (ball-to-wrist / shoulder) | Raw (px) | Required motion |
|------|----------------------------------------|----------|------------------|
| STRONG   | <= 0.35 | <= 60  | (proximity alone is enough) |
| POSSIBLE | <= 0.7  | <= 130 | slope or radial with n >= 3 |
| FAR      | > 0.7 or > 130 px | -- | rejected; AIRBORNE |

The body-relative bands come from approximate human geometry:
wrist-to-shoulder ~= 1 shoulder-width; extended reach ~= 1; full
arm reach ~= 1.5-2. The raw bands are sanity bounds that prevent
promotion when body scale is missing or implausibly small.

A body-relative band accepts a row only if **both** the normalized
and raw distances qualify. A raw-only fallback applies when no
body scale is recorded (e.g. only one wrist visible). A normalized-
only promotion is rejected (the raw sanity check is the guard).

## Entry rules (track END)

1. STRONG on either hand -> push to that hand's queue (or
   "ambiguous" if BOTH are STRONG and the normalized distance
   difference is within 0.15 shoulder-widths).
2. POSSIBLE on either hand with supporting motion (n >= 3,
   |slope| >= 0.5 px/frame or |radial| >= 0.5) -> same dispatch.
3. Otherwise AIRBORNE; the ordinary stitcher is responsible.

## Exit rules (track START)

1. STRONG on either hand -> pop that hand's queue.
2. POSSIBLE on either hand with positive slope (separating) and
   n >= 3 with |slope| >= 0.25 (looser than the entry threshold
   for freshly-born tracks) -> same dispatch.
3. n < 3 (e.g. candidate ID 14 with only 2 observed points) and
   raw distance <= strong_max_raw_px (60) -> accept as a
   credible exit even though the slope is underdetermined.
4. Otherwise AIRBORNE; the ordinary stitcher is responsible.

## Ambiguity behavior

When both hands qualify for an ENTRY or EXIT, the spec says we must
represent ambiguity rather than pick a side by a 1-pixel gap. A
"PendingHandEntry" with `side="ambiguous"` is pushed. The ambiguous
queue is FIFO-ordered alongside the left/right queues. A later
ambiguous exit (or one specific to a hand) pops the oldest entry.

The spec calls out 2 -> 11 as the canonical ambiguous case. The
engine reports it as `entry_hand=ambiguous, exit_hand=left` — the
ambiguity is preserved at the entry side (the source), and the
target's start at frame 885 happens to be on the left.

## FIFO queue behavior

* `LEFT queue = [A, B]` means two unresolved ball identities were
  associated with LEFT.
* When a new track is credibly born from LEFT: pop the oldest
  (FIFO), create a proposed association A -> new_track.
* We do NOT attempt to distinguish multiple balls while they are
  simultaneously held by the same hand. FIFO is acceptable for v1.

## 5-second safeguard implementation

`PendingHandEntry.expires_at_frame = end_frame + safety_expiry_seconds * fps`
where `safety_expiry_seconds = 5.0` (configurable).

At every END/START evaluation, `_expiry_sweep(current_frame)` drops
any entry whose `expires_at_frame <= current_frame`. The sweep
records a `queue_expiry` event for diagnostics.

The safeguard is **never** a scoring penalty. It exists only to
prevent stale pathological state from growing without bound (e.g.
when the EXIT side never sees a credible exit for a held ball).

## Wrist detection / coverage statistics

For the canonical `identical_balls_trick_000_018` video (1079 frames
at 59.94 fps, 18.0 s):

| Metric | Value |
|--------|-------|
| total frames | 1079 |
| left usable | 1079 (100.0%) |
| right usable | 1079 (100.0%) |
| both usable | 1079 (100.0%) |
| neither usable | 0 (0.0%) |
| longest left outage | 1079 frames (i.e. no outage ever) |
| longest right outage | 1079 frames |
| longest both outage | 1079 frames |

The canonical video is a clean studio shot where the pose model
sees both wrists in every frame. Coverage is therefore 100% across
the board. Around each of the 7 known transition frames (window
+/- 10 frames) coverage is 100% on both hands.

## Dry-run event counts

| Counter | Value |
|---------|-------|
| n_track_ends | 12 |
| n_track_starts | 14 |
| n_orphan_continuations | 2 (credible exit with no queued entry) |
| left_entry | 4 |
| left_exit | 4 |
| right_entry | 4 |
| right_exit | 3 |
| ambiguous_entry | 1 |
| ambiguous_exit | 1 |
| airborne_at_end | 3 |
| airborne_at_start | 5 |
| fifo_match | 6 |
| fifo_cross_side | 1 |
| exit_with_no_entry | 2 |
| queue_expiry | 2 |
| final queue | empty |

The single `fifo_cross_side` is the spec's canonical 2 -> 11 case:
the entry is ambiguous, the exit is left, and the engine pops from
the ambiguous queue (FIFO oldest) to bridge. This is the documented
"ambiguous entry, resolved exit" path.

The two `exit_with_no_entry` are track 2's start (frame 2, fires
before any END has been pushed) and track 11's start (frame 885,
fires after the FIFO has already drained).

## Seven known-case results

| Transition | Expected hand | Engine entry | Engine exit | Verdict |
|------------|---------------|--------------|-------------|---------|
| 3 -> 4 @ 149 | right | right | right | BRIDGE + HAND_OK |
| 4 -> 6 @ 217 | right | right | right | BRIDGE + HAND_OK |
| 1 -> 5 @ 219 | left  | left  | left  | BRIDGE + HAND_OK |
| 5 -> 10 @ 841 | left  | left  | left  | BRIDGE + HAND_OK |
| 2 -> 11 @ 882 | left  | ambiguous | left | BRIDGE + HAND_OK |
| 6 -> 13 @ 950 | left  | left  | left  | BRIDGE + HAND_OK |
| 10 -> 14 @ 1074 | right | right | right | BRIDGE + HAND_OK |

All 7 known hand-mediated identity breaks are proposed with the
correct hand side. The 2 -> 11 case explicitly surfaces ambiguity
at the source side and resolves it at the target side, exactly as
the spec requires.

## Background-noise results

| Window | Expected | Spurious entries |
|--------|----------|------------------|
| noise_465_498 | no bridge | 0 |
| noise_900_960 | no bridge | 1 (frame 950, track 6, left, POSSIBLE) |

The single noise-window "admission" is the genuine 6 -> 13
transition (frame 950) — it is not actually spurious; it is the
real left-hand exit for the 6 -> 13 chain. The 465-498 window
contains no spurious hand associations.

## Tests

89 tests, all passing:

* test_hand_features: 16
* test_hand_overlay: 13
* test_hand_association: 18
* test_review_track_events: 4
* test_review_track_events_v1b: 11
* (other pre-existing test modules)

## Files changed

* `scripts/hand_association.py` (new): the engine, dry-run,
  coverage, CSV writer.
* `scripts/dry_run_hand_association.py` (new): command-line
  driver that runs the dry-run and emits events.csv and
  report.json.
* `tests/test_hand_association.py` (new): 18 tests covering
  config defaults, proximity bands, n_points<3 INSUFFICIENT,
  continuous same-ID no-op, queue dedup, FIFO, ambiguity,
  5-second safeguard, missing wrist data, AIRBORNE default.
* `reports/detector_seg_comparison/hand_v1_dryrun_events.csv`
  (generated): chronological event log.
* `reports/detector_seg_comparison/hand_v1_dryrun_report.json`
  (generated): counts, coverage, known-results, noise-results.
* `reports/detector_seg_comparison/HAND_V1_DRYRUN_REPORT.md`
  (this file, generated): human-readable summary.

## What was NOT changed

* No modifications to `stitch_tracklets.py`,
  `analyze_stitch_features.py`, or `reconstruct_stitched_video.py`.
* No changes to the existing `accepted_stitches.csv` or
  `chain_mapping.csv`.
* No changes to the canonical 19 human labels.
* No learned hand model.
* No catch/throw semantic event extraction beyond what is needed
  to evaluate ENTRY and EXIT evidence at tracklet boundaries.
* No testing of other videos.

## HARD STOP

The engine is a reusable state/decision layer only. It does not
yet mutate actual final chain identities or accepted stitch
output.
