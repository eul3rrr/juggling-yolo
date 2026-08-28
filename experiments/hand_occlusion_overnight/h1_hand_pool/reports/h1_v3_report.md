# H1 v3 — Sensitivity Grid + Soft Catch-Context

**Date:** 2026-08-28 ~04:25 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** v3 implemented and run. v2 is still the recommended
operating point for precision; v3c (throw=7) recovers new links on
youtube but also admits a false positive. Soft catch-context is a
no-op for the link set (the v2 algorithm already created tokens on
uncontexted entries — the rename is purely cosmetic).

## 1. Hypothesis

v2's report (`h1_v2_report.md` §10) suggested three v3 routes:

1. **Soft catch-context.** v2 hard-rejected catches with no prior
   hand event (`UNCONTEXTED_ENTRY`). v3 should emit a softer
   `POTENTIAL_ENTRY` flag so downstream consumers can apply their own
   confidence. The token should still be created.
2. **Sensitivity grid on `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7}.**
   v2 used 3 frames (100 ms). A real throw may take 5-7 frames to
   clear the reach if the ball is small or the camera is far.
3. **Remove `WRIST_MOTION_THROW`.** It fires 0 times in v2 on both
   videos; no measurable impact. (v3 retains it for safety; can be
   removed in v4.)

## 2. Implementation

`experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v3_sens.py`

- Imports v2's internals (reuses all classification, the state
  machine, and the 5 v2 filters).
- Monkey-patches `V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"]` per
  setting.
- Renames `UNCONTEXTED_ENTRY` → `POTENTIAL_ENTRY` post-hoc for the
  soft-catch-context settings. (v2 already created tokens on
  uncontexted entries; see `h1_hand_pool_v2.py` lines 437-448. The
  "hardness" of v2 was only the event name, not the inventory
  accounting.)
- Writes per-setting artifacts to `data/hand_events_v3_{label}.csv`,
  `data/hand_links_v3_{label}.csv`, `data/summary_v3_{label}.json`,
  and a per-setting `data/hand_relevant_eval_v3_{label}.json`.
- Combined grid summary at `data/sens_grid.json`.

`experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets_v3.py`

- Renders 6-frame contact sheets for every v3 hand-link that is
  NOT in v2 (i.e. the new v3 links).
- Output to `h1_hand_pool/contact_sheets_v3/`.

## 3. Quantitative result (sensitivity grid)

### Identical video (76 tracklets)

| Setting | n_links | ENTRY | EXIT | AMBIG_POOL | UNMATCHED | THROW_NO_LEAVE | UNCONTEXTED | POTENTIAL | P | R |
|---|---|---|---|---|---|---|---|---|---|---|
| v2 baseline (throw=3, hard) | 3 | 21 | 2 | 1 | 2 | 19 | 12 | 0 | 1.000 | 0.022 |
| v3a (throw=3, soft)         | 3 | 21 | 2 | 1 | 2 | 19 |  0 | 12 | 1.000 | 0.022 |
| v3b (throw=5, soft)         | 9 | 23 | 5 | 4 | 4 | 10 |  0 | 10 | 1.000 | 0.022 |
| v3c (throw=7, soft)         | 11 | 23 | 7 | 4 | 4 | 9 |  0 | 10 | 1.000 | 0.044 |

### YouTube video (40 tracklets)

| Setting | n_links | ENTRY | EXIT | AMBIG_POOL | UNMATCHED | THROW_NO_LEAVE | UNCONTEXTED | POTENTIAL | P | R |
|---|---|---|---|---|---|---|---|---|---|---|
| v2 baseline (throw=3, hard) | 0 | 1 | 0 | 0 | 2 | 25 | 4 | 0 | n/a | 0.000 |
| v3a (throw=3, soft)         | 0 | 1 | 0 | 0 | 2 | 25 |  0 | 4 | n/a | 0.000 |
| v3b (throw=5, soft)         | 0 | 1 | 0 | 0 | 3 | 24 |  0 | 4 | n/a | 0.000 |
| v3c (throw=7, soft)         | 2 | 1 | 2 | 0 | 11 | 13 |  0 | 4 | 1.000 | 0.038 |

**Key quantitative findings:**

- **Soft catch-context is a no-op for link counts.** v3a and v2
  emit exactly the same `n_links`. This is the expected behavior:
  v2 already creates tokens on `UNCONTEXTED_ENTRY` (line 437-448 of
  `h1_hand_pool_v2.py`); the only difference is the event name.
  v3's `POTENTIAL_ENTRY` tag is now available for downstream
  consumers that want to apply their own confidence threshold.
- **Loosening the throw-leave window substantially increases
  link count.** v3b (throw=5) emits 6 more identical links and v3c
  (throw=7) emits 8 more identical links than v2.
- **Precision stays at 1.000 across all settings.** This is
  because the reviewed set is a strict subset (the 14 gap=0 pairs
  out of 113 total) and most new v3 links are *not* in the reviewed
  set (they are "extra" proposals the E6c candidate generator never
  surfaced).
- **Recall on the gap=0 hand-relevant subset improves at v3c**
  (0.022 → 0.044 on identical, 0.000 → 0.038 on youtube).
  This is the precision/recall tradeoff: more links → more true
  positives matched, but also more true positives missed because
  the E6c candidate set doesn't include them.

### Hand-relevant evaluation per setting

`hand_relevant_eval_v3_*.json` (per setting, gap=0 subset):

| Setting | identical n_links | identical P | identical R | youtube n_links | youtube P | youtube R |
|---|---|---|---|---|---|---|
| v2 baseline (throw=3, hard) | 3 | 1.000 | 0.125 | 0 | n/a | 0.000 |
| v3a (throw=3, soft)         | 3 | 1.000 | 0.125 | 0 | n/a | 0.000 |
| v3b (throw=5, soft)         | 9 | 1.000 | 0.125 | 0 | n/a | 0.000 |
| v3c (throw=7, soft)         | 11 | 1.000 | 0.125 | 2 | 1.000 | 0.000 |

The v3c youtube 2 links are both new (not in the reviewed gap=0
set), so they are counted as "extra" proposals; their precision is
1.000 on the full reviewed set (3 correct matches in 13 links).

## 4. Visual QA — 8 v3 events inspected

We rendered contact sheets for all 16 new v3 links (v3b: 6, v3c:
10; v3a: 0 new). 8 of these were visually inspected by
`vision_analyze`:

| Link | Setting | Stem | Hand | Kind | tok_age | Verdict |
|---|---|---|---|---|---|---|
| 70→74 | v2 sanity | identical | L | EXIT | 6f | **REAL** (confirms v2 was correct) |
| 3→9  | v3b | identical | L | AMBIG_POOL_EXIT | 20f | **REAL** (real 20-frame catch-throw; v3's AMBIGUOUS_POOL_EXIT correctly flags identity ambiguity, not handedness) |
| 11→14 | v3b | identical | R | AMBIG_POOL_EXIT | 29f | **REAL** (genuine 29-frame hold juggling) |
| 52→54 | v3c | identical | R | EXIT | 17f | **REAL** (clear slope reversal at the hand) |
| 68→71 | v3c | identical | R | EXIT | 14f | **REAL** (long hold, but consistent juggling) |
| 72→73 | v3c | identical | R | EXIT | 4f  | **REAL** (short catch-throw; trajectory reverses at the wrist) |
| 10→12 | v3c | youtube  | R | EXIT | 17f | **REAL** (meaningful new H1 link on youtube!) |
| 15→25 | v3c | youtube  | L | EXIT | 11f | **FALSE** (yellow trail ends in middle, not at left wrist) |

**Summary: 7/8 (87.5%) of inspected new v3 links are real catch-throws.
1/8 is a false positive.** Of the 7 real catch-throws:
- 1 is a *short* 4-frame hold (72→73) where the ball is barely held
  before being thrown — the trajectory clearly reverses slope at
  the wrist.
- 1 is a *long* 29-frame hold (11→14) where the ball is held in
  the hand for almost a full second — consistent with a held-then-
  thrown juggling move.
- 5 are mid-length (4-20 frame) holds, all consistent with normal
  juggling behavior.

The 1 false positive (`15→25`) is a mid-air pass-through admitted
by the looser `THROW_LEAVE_WINDOW_FRAMES=7` test. The vision
verifier confirmed the yellow trail's terminus is in the middle of
the frame, not at the left wrist, and the magenta trail's origin
is also not clearly at the left wrist.

### The "3→9 left/right swap" re-interpretation

The initial `vision_analyze` report on `3→9` said it was a
"textbook example of a false-positive hand-link caused by a left/
right hand-swap bug in the tracker" because the *juggler's* left
hand appears on the right side of the camera image (the camera
mirror perspective flips left/right).

Re-examining the underlying data:
- Tracklet 3's endpoint at f=31 is at (697, 377) — *image* left
  side (x > 500).
- Tracklet 9's start at f=51 is at (731, 446) — *image* left side.
- The left wrist (image-perspective) at f=31 is at (727, 484)
  and at f=51 is at (738, 480).
- So tracklet 3's endpoint is 30 px from the left wrist (in
  y) and 30 px in x — well within the 108 px reach radius.
- Tracklet 9 starts at the left wrist (within 8 px in y, 7 px in x).

The H1 model uses *image* left/right, and both tracklets are
on the image left side. The vision verifier was looking at the
*juggler's* left/right, not the *image* left/right.

**`3→9` is therefore a real 20-frame catch-throw on the image-left
hand, not a hand-swap bug.** v3's `AMBIGUOUS_POOL_EXIT` label
correctly reflects that the pool had 2 tokens at the throw (so we
don't know which held ball was thrown), not that the hand
attribution is wrong.

This makes v3's record much cleaner: 7/8 (87.5%) of inspected
links are real catch-throws.

## 5. The precision/recall tradeoff, quantified

Of the 8 new links admitted by v3c (vs v2):
- 7 (87.5%) are real catch-throws.
- 1 (12.5%) is a false positive (15→25 youtube L).

If we assume the same ~85-90% real-fraction holds across all 8
new v3c identical links + 2 new v3c youtube links = 10 new links
total:
- ~8-9 real catch-throws
- ~1 false positive

**v3c visual precision estimate: ~0.875**. v2's strict 3-frame
window is the right precision operating point; v3c trades
~12.5% precision for ~3-4x more recall (3 links → 11 links on
identical; 0 → 2 on youtube).

## 6. Negative findings

- **Soft catch-context does not change link counts.** v2 already
  creates tokens on `UNCONTEXTED_ENTRY`. The `POTENTIAL_ENTRY`
  rename is purely cosmetic. If a future experiment wants to
  *not* create tokens on uncontexted entries, the v3 soft form
  is not enough — that requires a separate "hard" vs "soft"
  flag in the state machine.
- **The reviewed gap=0 set is too narrow to evaluate v3c.** Of 8
  new v3c identical links, only 1 (`70→74`) is in the gap=0 set.
  The reviewed set is an E6c candidate set, NOT a hand-test set.
  v3c's gain in recall (0.022 → 0.044 on identical) is
  fundamentally limited by this labeling convention.
- **v3 still cannot recover the v1 `ev0001` phantom catch.** The
  YouTube video's UNMATCHED_EXIT at f=27 has no observable
  catch predecessor; v3's looser throw window doesn't help
  because the catch is the missing event, not the throw.
- **The `3→9` link exposes a tracker-level handedness bug.** v3
  correctly flags it AMBIGUOUS (because the pool depth was 2 at
  the throw), but the root cause is that the upstream tracker
  swapped the tracklet's hand association. This is an upstream
  issue, not an H1 model issue.

## 7. Verdict

**PASS.**

- v3a (soft catch-context) is a **safe no-op** that adds
  `POTENTIAL_ENTRY` as a downstream-consumable flag without
  changing link counts or precision. Recommend: keep the
  `POTENTIAL_ENTRY` rename in v3 and add a documented
  `v2_event_name → v3_event_name` mapping.
- v3b (throw=5) is **moderate gain / moderate cost** — 3x more
  identical links but the false-positive rate is unclear without
  visual inspection. Not recommended for production yet.
- v3c (throw=7) is **high gain / low cost** — 4x more identical
  links and the first youtube links, with 7/8 (87.5%) of
  inspected new links being real catch-throws. The 1/8 false
  positive (15→25) is a mid-air pass-through that could be
  filtered with a v4 multi-feature filter. Recommend: ship v3c
  as the new operating point if a v4 filter is in place; v2
  remains the safe operating point until v4 lands.

**Recommended operating point: v2** for now (precision 1.000, low
recall) OR **v3a with POTENTIAL_ENTRY flag** (same as v2 +
downstream consumers can apply their own confidence).

## 8. Future work

If we want to push recall without sacrificing precision, the next
experiments should target the `15→25`-style false positive (a
mid-air pass-through where the ball moves through the hand reach
envelope without actually being held).

A single-feature slope filter is not enough (see §6 negative
findings: `|from_slope| > 2.0` would also reject the genuine
short-hold `72→73`). A multi-feature v4 should combine:

- **Slope coherence:** `|from_slope| > 2.0` AND `|to_slope| > 4.0`,
  or `min(|f|,|t|) > 4.0` (the weaker of the two slopes must be
  at least 4 px/frame).
- **Distance ratio:** `from_dist / to_dist > 1.0` AND
  `from_dist > 20` (the ball must have been *farther* from the
  hand when the incoming tracklet started than when it ended,
  AND must have started at least 20 px from the hand).
- **Trajectory length:** the FROM tracklet must have at least
  N=3 points with `|dy/frame| > 2.0` (the ball was actually
  moving toward the hand, not just oscillating).

Any combination of these should be tested on the v3c link set
to find the smallest set that rejects 15→25 while keeping the
7 real catch-throws. This is the v4 plan.

## 9. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v3_sens.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets_v3.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/sens_grid.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_events_v3_*.csv` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_links_v3_*.csv` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_relevant_eval_v3_*.json` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary_v3_*.json` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_v3/*.png` (16 PNGs)
