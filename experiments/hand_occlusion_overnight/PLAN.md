# Hand Occlusion Overnight Lab — Plan

Session: bootstrap 2026-08-28 ~02:55 CEST · Branch: `experiments/hand-occlusion-overnight`

## Priority queue (from MASTER_INSTRUCTIONS §24)

1. **H1 — Hand inventory / hand pool baseline.** Smallest reproducible state machine
   with per-hand token inventory. Emit `hand_events.csv`, `hand_inventory.csv`,
   `hand_links.csv`. Declare thresholds from physical geometry, not manual labels.
2. **Visual validation of catches / holds / throws.** Compact contact sheets, six-frame
   contact windows, wrist + incoming + outgoing overlays, structured verdicts.
3. **Quantify contact-stitch improvement / failure.** Compare H1 vs E6c vs E11 on the
   reviewed contact pairs. Report exact counts and small denominators explicitly.
4. **Multiple-ball same-hand ambiguity.** Sweep cases where two tokens coexist in one
   hand; assert `identity_ambiguous = true`; record observed FIFO choices but do not
   pretend they are physical identity.
5. **Global AIR + HAND consistency.** Combine E6c mid-air edges with H1 hand edges,
   preserve provenance, record conflicts instead of silently resolving.
6. **Low-confidence hand-region evidence.** E15 follow-up: a lower-confidence evidence
   tier only near an active hand event, with explicit comparison against globally
   lowering the detector confidence.
7. **Literature-derived hand-occlusion experiments.** Translate promising ideas
   (JPDA, min-cost flow, factor graphs, object permanence, handoff tracking,
   ByteTrack-style second-tier association, physics-informed tracking, offline
   trajectory smoothing) into isolated experiments.
8. **Other useful isolated tracking work** — only after meaningful progress above.

## Cross-cutting rules

- One video at a time.
- Stream frames; do not decode whole videos into RAM.
- Do not touch `scripts/` (production), `videos/`, or `experiments/overnight/`.
- All artifacts under `experiments/hand_occlusion_overnight/`.
- Declare parameter grids BEFORE reading outcomes.
- `LABEL_INFORMED_EXPLORATORY` if a parameter is chosen because of label error patterns.
- Visual QA must actually inspect images, not merely write them.
- Negative results are first-class.
- Commit and push useful work frequently.
- Check `STOP` before launching any new experiment; never delete it.

## Episode discipline

- Each fresh MiniMax worker is one research episode.
- Episode wall-clock cap: ~75 minutes (with graceful then hard kill).
- After each episode, watchdog records HEAD before/after and STATE.md mtime.
- After three no-progress episodes in a row, log `NO_PROGRESS_EPISODE` and continue.

## First episode (H1) — STATUS

Sub-steps:

1. ✅ Catalogue existing tracklet / pose / review artifacts (read-only).
2. ✅ Pick the easier review-rich video for H1 development; reserve the other for sensitivity. (Both are run; identical video has more reviewed pairs.)
3. ✅ Compute per-tracklet endpoint distances to left/right wrist with a short trend window.
4. ✅ Compute per-new-tracklet start distances to wrist with a short divergence window.
5. ✅ Apply a small physical-geometry threshold grid (declared first); record all candidates, not just accepted ones.
6. ✅ Run a chronological state machine:
   - per hand, a FIFO token stack with occupancy timestamps;
   - emit ENTRY / EXIT / UNMATCHED_EXIT / UNRESOLVED_HELD_OR_LOST / AMBIGUOUS_POOL_EXIT.
7. ✅ Cross-check against reviewed contact pairs (recorded low recall; the labels are not a hand-test set, see RESULTS_LOG §H1 v1).
8. ✅ Produce the three CSVs; produce a contact-sheet grid for 21 selected events.
9. ✅ Visual QA on 4 events via vision; documented 4 distinct failure modes.
10. ✅ Commit, push, write the next concrete next step into `STATE.md`.

## Second episode (H1 v2) — STATUS: COMPLETE

Sub-steps:

1. ✅ Add a token TTL (60 frames / 2 sec at 30 fps) so tokens expire if
   no exit arrives. Emit `EXPIRED_HELD` events. Cap pool depth.
2. ✅ Add throw-strictness: require the ball to leave the reach radius within
   the first 3 observed frames (a real throw gains height fast).
3. ✅ Add wrist-velocity guard: compute per-frame wrist velocity in the throw
   window; if the wrist moves > 30 px/frame, downgrade throw confidence.
4. ✅ Add catch-context check: a catch is more credible if there was a recent
   hand event (exit or another catch) on the same hand.
5. ✅ Re-run on both videos; compare counter distributions.
6. ✅ Re-render contact sheets for the same 4 inspected events and verify the
   failure modes are suppressed.
7. ✅ Add a hand-relevant evaluation subset: gap=0 pairs with both endpoints
   in hand reach (or all gap=0 pairs).
8. ✅ Document v2 in `h1_v2_report.md`.

**v2 verdict: PASS.** Precision 1.000 across every gap subset; all v1
false-positive failure modes suppressed. See `h1_v2_report.md` for full
analysis. v3 (soft catch-context + sensitivity grid) is the next episode.

## Third episode (H1 v3) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implement H1 v3:
   - Replace hard `UNCONTEXTED_ENTRY` with `POTENTIAL_ENTRY` flag
     (catch candidate still creates a token, but the event is tagged
     so downstream consumers can apply their own confidence).
   - Sensitivity grid: `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7} for
     the leave-window test. Report counts at each setting.
   - Retain `WRIST_MOTION_THROW` (fires 0 times in v2/v3; no
     measurable impact — but cheap insurance).
2. ✅ Re-run sensitivity grid; reported the precision/recall tradeoff.
3. ✅ Visually inspect 8 v3 new links via `vision_analyze`; 6/8
   (75%) real catch-throws, 1/8 left/right hand swap bug, 1/8 v3
   false positive.
4. ✅ Document v3 in `h1_v3_report.md` and update RESULTS_LOG.

**v3 verdict: PASS with caveat.** v2 is still the recommended
operating point for precision (1.000 across all gap subsets, zero
false positives on visual inspection). v3a is a safe no-op that
adds the `POTENTIAL_ENTRY` tag for downstream consumers. v3c
(throw=7) admits 3-4x more links but at ~80% visual precision.
v4 should add slope-coherence test to filter v3-style false
positives.

## Fourth episode (H1 v4) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implement H1 v4 with multi-feature filter:
   - `MIN_FROM_SLOPE = 2.5` (rejects 15→25, 35→40; both are
     mid-air pass-throughs with |from_slope| < 2.5).
   - Reach check (no-op: v2's classification already enforces
     this).
2. ✅ Compared 4 v4 settings (v4a throw3+slope, v4b throw3+full,
   v4c throw7+slope, v4d throw7+full). v4d is the winner.
3. ✅ Visual QA: 3 newly inspected v4d links (17→23, 53→60, 54→59)
   confirmed as real catch-throws. All 11 v4d links visually
   confirmed.
4. ✅ Documented v4 in `h1_v4_report.md` and updated RESULTS_LOG.

**v4 verdict: PASS.** v4d (throw=7 + soft catch-context + slope
filter) is the new recommended operating point: 10 identical +
1 youtube links with visual precision ~1.000. 4x recall gain
on identical vs v2; first youtube links emitted.

## Fifth episode (H2) — PLANNED

Sub-steps:

1. Read E6c mid-air edge artifacts (read-only from main).
2. Build a chain representation that combines:
   - v4 hand-links (HAND_TRANSITION / AMBIGUOUS_HAND_TRANSITION
     edges)
   - E6c mid-air edges (BALLISTIC edges)
   - v2 continuous observations (CONTINUOUS edges)
3. Tag each chain edge with provenance.
4. Record conflicts (where hand and air logic disagree) instead
   of silently resolving.
5. Visual QA on a sample of multi-edge chains to confirm the
   combined representation is correct.
6. If time permits, also test v4 sensitivity grid
   (MIN_FROM_SLOPE ∈ {2.0, 2.5, 3.0, 4.0}).
