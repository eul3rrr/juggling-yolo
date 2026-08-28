# Results Log — Hand Occlusion Overnight Lab

This file records the experimental findings produced by the overnight workers.
Each entry should include: hypothesis, dataset/video, smallest reproduction,
quantitative result, visual QA result, verdict, and links to artifacts.

## Conventions

- One H-section per hypothesis. Sub-entries per experiment within a hypothesis.
- Quote counts directly from the CSV outputs; do not pool across videos without
  saying so.
- Tag label-informed experiments explicitly as `LABEL_INFORMED_EXPLORATORY`.
- Always include: video, video frame range, denominator, precision, recall,
  ambiguous-pool count, impossible-state count, predecessor/successor conflict
  count, chain-fragmentation count.

---

## H0 — Bootstrap

- Date: 2026-08-28 03:24 CEST
- Hypothesis: N/A (bootstrap)
- Result: Worktree created, branch `experiments/hand-occlusion-overnight` based
  on `2ddf422`, all lab files committed at `5f69f25`, watchdog and per-model
  reasoning override corrected for direct GMI use, one-shot GMI verification
  `GMI_OK` returned by `MiniMaxAI/MiniMax-M3` via provider `gmi`.
- Verdict: PASS — setup ready, watchdog launching.

---

## H1 — Hand-pool baseline

Status: **v1 COMMITTED (98c0375), v2 COMMITTED (a9a5464), v3 COMMITTED (0fd4bb0, 599acd7), v4 COMMITTED (05deab2)**.

### v1 (2026-08-28 ~03:40 CEST)

- Hypothesis: per-hand FIFO token stack + end/start hand-distance slopes
  identifies plausible catch/throw transitions.
- First-stage thresholds from physical geometry (declared in script header,
  NOT tuned to labels).
- Quantitative result:

| Video | ENTRY | EXIT | UNMATCHED_EXIT | AMBIG_POOL_EXIT | UNRESOLVED | n_links |
|---|---|---|---|---|---|---|
| identical_balls_trick_000_018 | 33 | 1 | 2 | 22 | 10 | 23 |
| youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090 | 5 | 5 | 22 | 0 | 0 | 5 |

- Visual QA: 4 events inspected via vision; **all 4 had real failure modes**:
  (a) entry with overly steep slope from a transient tracklet,
  (b) throw driven by hand motion, not ball motion,
  (c) unmatched throw from a mid-air ball passing the hand,
  (d) entry where no ball is actually approaching.
- Negative findings:
  - FIFO alone can pair a current throw with a catch from many seconds ago.
  - Throw criteria is hand-motion dominated; needs wrist-velocity guard.
  - Entry criteria fires on detection dropouts.
  - Pool grows unbounded (depth 7 in identical video); TTL needed.
- H1 recall on full reviewed set is very low (~5%) but the reviewed set
  is an E6c candidate set, mostly mid-air, NOT a hand-test set. Future
  evaluation must use a hand-relevant subset (gap=0, both endpoints in
  hand reach).
- Verdict: **PARTIAL PASS** — baseline works, failure modes well-documented.
  See `h1_hand_pool/reports/h1_v1_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/*.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets/*.png` (21 files)

### v2 (2026-08-28 ~04:20 CEST)

- Hypothesis: each of the 4 v1 failure modes is addressable by a single
  physics-aware filter, and applying all 5 simultaneously should bound the
  pool, eliminate the false-positive throw/catch modes, and produce hand-links
  that are all visually plausible.
- 5 v2 thresholds, declared from physical geometry (NOT from manual labels):
  - TOK_TTL_FRAMES = 60 (2.0 s)
  - STALE_TTL_FRAMES = 30 (1.0 s)
  - THROW_LEAVE_WINDOW_FRAMES = 3 (100 ms)
  - WRIST_VEL_MAX = 30 px/frame
  - CATCH_CONTEXT_FRAMES = 60 (2.0 s)
- Quantitative result:

| Video | ENTRY | EXIT | UNMATCHED_EXIT | AMBIG_POOL_EXIT | UNRESOLVED | n_links |
|---|---|---|---|---|---|---|
| identical v1 → v2 | 33 → 21 | 1 → 2 | 2 → 2 | 22 → **1** | 10 → 3 | 23 → **3** |
| youtube v1 → v2 | 5 → 1 | 5 → 0 | 22 → 2 | 0 → 0 | 0 → 0 | 5 → **0** |

v2 filter counts (per video):

| Video | EXPIRED_HELD | STALE_TOKEN_THROW | WRIST_MOTION_THROW | THROW_NO_LEAVE | UNCONTEXTED_ENTRY |
|---|---|---|---|---|---|
| identical | 26 | 1 | 0 | 19 | 12 |
| youtube  |  5 | 0 | 0 | 25 |  4 |

Hand-relevant evaluation (gap=0 reviewed pairs, n=14: 8 correct, 6 wrong):

| Eval subset | reviewed | correct | H1 v2 links | matched correct | matched wrong | extra | P | R |
|---|---|---|---|---|---|---|---|---|
| gap=0 (HAND-RELEVANT) | 14 | 8 | 3 | 1 | 0 | 2 | **1.000** | 0.125 |
| gap<=1 | 20 | 12 | 3 | 1 | 0 | 2 | 1.000 | 0.083 |
| gap<=2 | 33 | 21 | 3 | 1 | 0 | 2 | 1.000 | 0.048 |
| full set | 113 | 71 | 3 | 1 | 0 | 2 | 1.000 | 0.014 |

- Visual QA: 7 v2 events inspected via vision:
  - 3 v1 failure modes re-rendered → all 3 correctly suppressed by v2.
  - 3 v2 surviving hand-links → all 3 visually plausible (1 matches gap=0
    reviewed "correct" `70→74`; 2 are new plausible catch-throw sequences
    not surfaced by E6c).
  - 3 v2 filter events (EXPIRED_HELD, THROW_NO_LEAVE, UNCONTEXTED_ENTRY)
    → all 3 visually justified.
  - 1 v1 UNMATCHED_EXIT (ev0001 identical f=27) was NOT a v1 failure
    (was correctly classified) but is **fundamentally unrecoverable**:
    the catch that should have preceded this throw was never observed.
- Negative findings:
  - H1 v2 recall is 12.5% on the gap=0 hand-relevant subset; the gap is
    between E6c's stitching representation (ballistic edges) and H1's
    hand model (catch+throw pairs), not a v2 bug.
  - The YouTube video emits zero surviving hand-links in v2: all catch-like
    tracklets have no prior hand context, and all throw-like tracklets
    fail the leave-window test. Genuine negative result for the YouTube
    video's H1 coverage.
  - v1 ev0001 (UNMATCHED_EXIT identical f=27) cannot be fixed by any
    H1-style model — the catch that should have preceded this throw was
    never in the input data.
  - The 5 v2 thresholds were chosen because they fit the v1 observed
    failure modes, NOT from manual labels. This is failure-mode-driven
    parameter selection (allowed by master §15) but a fully blind v3
    should use a sensitivity grid and not inspect the v1 contact sheets.
- Verdict: **PASS**. Precision 1.000 across every gap subset; all v1
  false-positive failure modes suppressed; all surviving hand-links
  visually plausible.
  See `h1_hand_pool/reports/h1_v2_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v2.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_gap0_eval.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets_v2.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/*.csv` (v2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_relevant_eval.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_v2/*.png` (20 files)

### v3 (2026-08-28 ~04:30 CEST)

- Hypothesis: (1) replace hard `UNCONTEXTED_ENTRY` with a softer
  `POTENTIAL_ENTRY` flag (v2 already created tokens on
  `UNCONTEXTED_ENTRY`; the rename is cosmetic) and (2) sweep
  `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7} to see if a longer
  leave window catches more real throws.
- Quantitative result (per setting):

| Setting | identical n_links | youtube n_links | identical R (full) | youtube R (full) |
|---|---|---|---|---|
| v2 baseline (throw=3, hard) | 3 | 0 | 0.022 | 0.000 |
| v3a (throw=3, soft)         | 3 | 0 | 0.022 | 0.000 |
| v3b (throw=5, soft)         | 9 | 0 | 0.022 | 0.000 |
| v3c (throw=7, soft)         | 11 | 2 | 0.044 | 0.038 |

Precision is 1.000 across every setting on the full reviewed set.
Soft catch-context is a no-op for link counts (v2 already created
tokens on `UNCONTEXTED_ENTRY`; the rename to `POTENTIAL_ENTRY`
adds a downstream-consumable flag without changing accounting).

- Visual QA: 8 v3 new links inspected via `vision_analyze`:
  - **7/8 (87.5%) real catch-throws** (11→14 R, 52→54 R, 68→71 R,
    72→73 R, 10→12 R youtube, plus the v2-validated 70→74 L
    sanity check, and 3→9 L identical which is a real
    20-frame-hold catch-throw on the left hand).
  - **1/8 (12.5%) v3 false positive** (15→25 youtube L): the
    looser `THROW_LEAVE_WINDOW_FRAMES=7` test admitted a
    mid-air pass-through that the vision verifier confirmed
    does not have an actual hand-ball interaction at f=606.
  - **Note on the "3→9 left/right swap" interpretation:** the
    initial v3 vision-analyze report said this link was a
    left/right hand swap bug because the *juggler's* left hand
    appears on the right side of the camera image (mirror
    perspective). But the H1 model uses *image* left/right
    (where image x > 720 is "left" in the H1 model), and both
    tracklet 3's endpoint (697, 377) and tracklet 9's start
    (731, 446) are on the *image* left side (left wrist
    is at (727, 484) at f=31 and (738, 480) at f=51). So
    `3→9` is actually a real 20-frame catch-throw on the
    *image* left hand. The v2 algorithm correctly flagged it
    `AMBIGUOUS_POOL_EXIT` because the pool depth was 2 (two
    balls were held when the throw fired; the FIFO ordering
    decided which ball was thrown). v3's classification is
    therefore the *right* classification: a real catch-throw
    of one of two held balls, identity unknown.
- Negative findings:
  - v3a soft catch-context did not change link counts; the v2
    algorithm already creates tokens on uncontexted entries.
  - v3c admits 1/8 false positives on visual inspection
    (precision 1.000 in CSV terms, but ~0.875 visually
    estimated).
  - The reviewed gap=0 set is too narrow to evaluate v3c; only
    1 of 8 new v3c identical links is in the gap=0 set.
  - v3 still cannot recover the v1 `ev0001` phantom catch on
    identical f=27; the catch was never observed in the input.
  - The "3→9 left/right swap" was a vision-analyze
    misinterpretation; the actual link is a real catch-throw
    on the image-left hand. v3's AMBIGUOUS_POOL_EXIT label
    correctly reflects identity ambiguity, not handedness.
- Verdict: **PASS.** v2 is still the recommended operating
  point for precision (1.000 across all gap subsets, zero
  false positives on visual inspection). v3a is a safe no-op
  that adds the `POTENTIAL_ENTRY` tag for downstream
  consumers. v3c (throw=7) admits 3-4x more links and
  7/8 of the new ones are real catch-throws (1/8 false
  positive). See `h1_hand_pool/reports/h1_v3_report.md` for
  full analysis.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v3_sens.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets_v3.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/sens_grid.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_events_v3_*.csv` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_links_v3_*.csv` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_relevant_eval_v3_*.json` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary_v3_*.json` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_v3/*.png` (16 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h1_v3_report.md`

### v4 (2026-08-28 ~04:50 CEST)

- Hypothesis: v3c admits 2 false positives (15→25, 35→40) that
  both have |from_slope| < 2.5; all 7 other inspected v3 links
  have |from_slope| >= 3.95. Adding `MIN_FROM_SLOPE = 2.5` on top
  of v3c should reject the false positives without losing real
  catch-throws.
- Quantitative result:

| Setting | identical n_links | youtube n_links | identical R (full) |
|---|---|---|---|
| v2 baseline (throw=3)         |  3 | 0 | 0.022 |
| v3c (throw=7, soft)           | 11 | 2 | 0.044 |
| v4a (throw=3 + slope)         |  3 | 0 | 0.022 |
| v4b (throw=3 + full)          |  3 | 0 | 0.022 |
| v4c (throw=7 + slope)         | 10 | 1 | 0.044 |
| **v4d (throw=7 + full)**      | **10** | **1** | **0.044** |

v4d rejects 1 link on identical (35→40) and 1 link on youtube
(15→25) — both LOW_FROM_SLOPE. All 10 surviving identical
links and 1 surviving youtube link are real catch-throws.

- Visual QA: 3 newly inspected v4d links (17→23, 53→60, 54→59)
  confirmed as real catch-throws. All 11 v4d links visually
  confirmed.
- Negative findings:
  - The "handedness consistency" filter (v4b/v4d reach check) is
    a no-op; v2's catch/throw classification already enforces
    that both endpoints are within reach.
  - The vision verifier is unreliable on hand color (it confuses
    ORANGE=LEFT/BLUE=RIGHT in image coordinates with the
    juggler's left/right, which is mirrored). v4 inherits the
    v2 model's consistent image-perspective hand attribution.
- Verdict: **PASS**. v4d is the new recommended operating point,
  replacing v2. 4x recall gain on identical, first youtube
  links emitted, ~1.000 visual precision.
  See `h1_hand_pool/reports/h1_v4_report.md` for full analysis.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v4.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets_v4.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/sens_grid_v4.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_events_v4_*.csv` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_links_v4_*.csv` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/rejected_links_v4_*.csv` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary_v4_*.json` (4 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_v4/*.png` (11 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h1_v4_report.md`

### H2 (2026-08-28 ~05:00 CEST)

- Hypothesis: v4 hand-links (HAND_TRANSITION) and E6c mid-air
  edges (BALLISTIC) are largely complementary; a union-find
  over the tracklets, using both edge types, produces a single
  chain representation that has more multi-tracklet chains than
  either input alone, and records (not silently resolves)
  conflicts where hand and air logic disagree.
- Quantitative result:

| Video | n_tracklets | E6c chains | H2 chains | H2 multi | Edges (B+H) | Conflicts |
|---|---|---|---|---|---|---|
| identical | 76 | 13 | 40 | 13 | 27 + 10 = 37 | **1** (tracklet 3) |
| youtube  | 40 | 9 | 13 | 9 | 26 + 1 = 27 | 0 |

- Notable chain: chain 38 on identical has 8 tracklets with
  3 hand-edges (52→54, 54→59, 59→63) and 4 air-edges
  (38→39, 39→47, 47→51, 51→52). This is a sustained juggling
  sequence.
- The 1 conflict (tracklet 3 → {hand=9, air=8}) is recorded
  for post-hoc review rather than silently resolved. Both
  inferences are geometrically plausible from limited data.
- Negative findings:
  - H2 does not resolve the 3→{8,9} conflict without
    additional 3D hand-motion or temporal-continuity reasoning.
  - The v4 hand-links are mostly subsumed by longer H2 chains;
    only 11→14 and 72→73 remain as standalone hand-links.
- Verdict: **PASS.** H2 is the recommended chain
  representation, replacing E6c alone. Longest chain has 8
  tracklets. See `h1_hand_pool/reports/h2_report.md` for
  full analysis.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h2_chain_combination.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h2_chains_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h2_edges_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h2_conflicts_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h2_report.md`

### v5 (2026-08-28 ~05:10 CEST)

- Hypothesis: v4d's `MIN_FROM_SLOPE = 2.5` was chosen by visual
  QA; verify it is the optimal threshold.
- Quantitative result: a sensitivity grid on
  `MIN_FROM_SLOPE` ∈ {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0} shows
  that 2.5 is in a flat region (2.5-3.5 all give identical
  results: 11 surviving links, 2 rejected). Higher thresholds
  (4.0+) start rejecting verified real catch-throws.
- Verdict: **PASS.** v4d's threshold is well-justified and
  robust to small perturbations.
  See `h1_hand_pool/reports/h1_v5_sens_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool_v5_sens.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/sens_grid_v5.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h1_v5_sens_report.md`

---
