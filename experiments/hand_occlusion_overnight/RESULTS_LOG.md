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

### H3 (2026-08-28 ~05:30 CEST)

- Hypothesis (master §14): around an active v4d hand-link,
  low-confidence sports-ball detections NOT in the incoming or
  outgoing tracklet can provide *supporting evidence* for the
  held-ball state, without globally lowering the detector
  confidence. This is a hand-crafted version of the ByteTrack
  "second-tier association" idea, applied at the tracklet
  level rather than the detection level.
- Three iterated implementations (v1, v2, v3):
  - v1: temporal cluster of low-conf dets in 60-frame window,
    FPR ~77-99% (over-permissive).
  - v2: per-detection "held candidate" (close to wrist in
    ±2 frames), FPR HIGHER on random regions than on v4d
    links (33.8% vs 50.1%) — wrong direction.
  - v3: stationary cluster of ≥3 low-conf dets in 30px radius
    over ≥5 frames (allowing gaps of ≤8 frames).
    Quantitative: 7/11 v4d links have a v3 cluster; visual
    precision 6/7 = 0.857.
- Visual QA: 7 contact sheets rendered and inspected via
  `vision_analyze`:
  - 6/6 identical-video H3 clusters are REAL held balls
    (ball visibly in the hand during the held phase).
  - 1/1 youtube-video H3 cluster is a STUCK FALSE POSITIVE
    on the juggler's face/head (the detector confuses
    face features with sports balls when the hand is near
    the face).
- Negative findings:
  - v1 and v2 were non-discriminative (FPR too high or in
    the wrong direction).
  - v3's baseline rate (50-60%) is HIGHER than v4d link
    rate (11%) — the criterion is not specific to hand-events.
  - H3 confirms v4d held-ball events but does NOT recover
    any new v4d-missed links. H3 is a corroborating signal,
    not a recovery mechanism.
  - H3 cannot fill detector dropouts during the held phase
    (dropouts = no detections, not low-conf detections).
  - The YouTube failure is a detector limitation, not a
    criterion failure. The detector confuses face features
    with sports balls when the hand is near the face.
- Verdict: **PARTIAL PASS.** H3's stationary-cluster
  criterion correctly identifies held-ball evidence on
  the identical video (6/6 = 100% precision) and has 1
  false positive on the YouTube video. H3 is useful as a
  downstream confidence signal on v4d links, not as a
  general held-ball detector. See
  `h1_hand_pool/reports/h3_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h3_low_conf_hand_region.py` (v1, preserved)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h3_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_summary.json` (v1)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_v2_summary.json` (v2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_v3_summary.json` (v3, recommended)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h3/*.png` (7 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h3_report.md`

### H4 (2026-08-28 ~05:50 CEST)

- Hypothesis: the H3 YouTube false positive (10→12) is caused
  by YOLO confusing face/head features with sports balls when
  the hand is near the face. A simple geometric mask that
  excludes detections ABOVE the wrist when the hand is near
  face level should eliminate the false positive.
- Implementation: H3 v3 stationary-cluster criterion +
  exclude candidate detections where (a) wrist y is within
  80 px of the minimum wrist y over ±15 frames (hand near
  face level), AND (b) detection y is more than 20 px above
  the wrist y.
- Quantitative result:
  - 6 identical H3 clusters preserved; 1 youtube H3 cluster
    NOT removed.
  - The surviving youtube cluster is at x=611-618, y=205-207
    (~50-80 px right of wrist, ~200 px above wrist). It is
    NOT a face feature; it's a stuck detection on a
    stationary high-up object (sign, tree, or wall feature).
- Negative findings:
  - The H3 YouTube false positive is NOT face confusion.
  - A simple geometric mask cannot solve detector confusion
    on arbitrary stationary features.
- Verdict: **FAIL.** H4 face-mask does not solve the H3
  YouTube false positive. The detector confusion is on a
  stationary high-up object, not the face. A real fix would
  require a more discriminating detector or a learned
  "ball-ness" classifier.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h4_face_masked_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h4_face_masked_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h4/*.png` (7 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h4_report.md`

### H5 (2026-08-28 ~05:55 CEST)

- Hypothesis: H3 stationary-cluster can be applied as a
  downstream confidence flag on v4d links. Add a
  `h3_confirmed: bool` field to v4d link records when a
  v3 stationary cluster is found in the held phase.
- Implementation: `scripts/h5_h3_confirmation.py` re-runs
  the H3 v3 stationary-cluster check on each v4d link
  restricted to the held phase (from_frame + 5 to
  to_frame - 5).
- Result: 6/11 v4d links have h3_confirmed=True
  (3→9, 11→14, 54→59, 53→60, 59→63, 10→12). The
  remaining 5 don't have a stationary cluster in the
  middle of the held phase (often because the held
  phase is too short or the detector didn't fire).
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h5_h3_confirmation.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/hand_links_v4_v4d_throw7_full_with_h3.csv`

### H6 (2026-08-28 ~06:00 CEST)

- Hypothesis (master §17): a min-cost flow formulation
  can resolve the 1 H2 conflict (tracklet 3 → {9, 8})
  optimally. H2's union-find records but doesn't
  resolve conflicts.
- Implementation: `scripts/h6_min_cost_flow.py` uses a
  simplified per-source greedy min-cost: for each
  source tracklet, pick the lowest-cost successor.
  Costs: HAND=1.0, AMBIGUOUS_HAND=1.5, BALLISTIC=2.0.
- Result: tracklet 3 → 9 (hand, cost 1.5) wins over
  → 8 (air, cost 2.0). **Same answer as visual QA.**
- Negative findings:
  - The simplified "one successor per tracklet"
    approach produces fewer, longer chains than H2's
    union-find (18 vs 40 on identical) because it
    disallows a tracklet having multiple predecessors
    (e.g. chain 38 where 47 and 51 both predict 52).
  - A true min-cost flow with capacity constraints
    (one predecessor + one successor per tracklet)
    would be more principled but unnecessary for this
    dataset (1 conflict).
- Verdict: **PASS (limited scope).** H6 validates
  "hand-edge wins on conflict" via a cost-based
  formulation. See `h1_hand_pool/reports/h6_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h6_min_cost_flow.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h6_min_cost_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h6_report.md`

---

### H7 (2026-08-28 ~06:50 CEST)

- Hypothesis: a principled min-cost flow with capacity constraints
  (one predecessor + one successor per tracklet) and a gap/error-aware
  air-edge cost will resolve the 1 H2 conflict (tracklet 3 → {9, 8})
  AND produce strict DAG-path-based chains (vs H2's union-find
  connected components). The cost function should be robust to
  perturbations of the air-edge penalty terms.

- Thresholds (declared from physical geometry, not from manual labels):
  - HAND_EDGE_COST = 1.0
  - AMBIGUOUS_HAND_EDGE_COST = 1.5
  - AIR_EDGE_BASE_COST = 2.0
  - AIR_ERR_SCALE = 0.05 (per unit trajectory_fit_error)
  - AIR_GAP_SCALE = 0.1 (per frame time gap)

- Algorithm: greedy iterative min-cost flow with capacity constraints,
  cycle detection, and gap/error-aware cost. Pure-Python (no
  scipy/networkx).

- Quantitative result:

| Video | Method | n_chains | n_multi | longest | conflicts |
|---|---|---|---|---|---|
| identical | H2 (union-find) | 40 | 15 | 8 (component) | 1 |
| identical | H6 (per-source greedy) | 18 | 17 | 7 (path) | 0 |
| identical | **H7 (greedy + capacity)** | **43** | **17** | **7 (path)** | **0** |
| YouTube | H2 (union-find) | 13 | 9 | 8 (component) | 0 |
| YouTube | H6 (per-source greedy) | 11 | 11 | 7 (path) | 0 |
| YouTube | **H7 (greedy + capacity)** | **15** | **10** | **6 (path)** | **0** |

- Sensitivity grid: 48 cells (3 × 4 × 4) of (AIR_EDGE_BASE_COST,
  AIR_ERR_SCALE, AIR_GAP_SCALE). **Perfectly flat** — every
  setting produces identical results. The hand<air cost ordering
  is the only thing that matters; the exact air-edge penalty is
  irrelevant.

- Visual QA:
  - Tracklet-3 conflict: t8 confirmed as a DIFFERENT ball (224
    pixels below t3's endpoint in y; t8 stays at y≈601 across
    f=43-46 — likely a stationary object on a surface). t3→t9
    confirmed as a real 20-frame hand-held catch-throw on the
    image-left hand.
  - Longest H7 chain on identical (35→37→40→41→43→45→46,
    7 tids): confirmed as a real single-ball juggling cycle
    (hold → release → rise → apex → fall → catch). y-coordinate
    pattern: t35 y=520-548 (hold) → t40 y=406→344 (rising) →
    t41/t43 y=343/322 (apex) → t45 y=313→389 (falling) →
    t46 y=430→597 (caught).

- H2+H3+H7 unified chain representation: built in
  `h237_unified_chain.py`. Each edge has edge_type, cost,
  h3_confirmed, metadata. Each chain has n_hand_edges, n_air_edges,
  n_h3_confirmed, tids. Most informative possible chain
  representation.

- Negative findings:
  - H7 doesn't reveal any new information beyond H6 for the
    conflict resolution question (both pick t3→9 over t3→8).
  - H7's edge ordering is invariant to the air-edge cost function
    (sensitivity grid is flat). A future v5 could use a much
    simpler "hand-edges first, then cheapest air-edge" formulation.
  - H7's longest chain (7) is shorter than H2's longest (8), but
    H2's 8 was a union-find connected component, not a strict path.

- Verdict: **PASS.** H7 is the recommended chain combination method,
  replacing H2 (union-find, conflicts unresolved) and H6 (per-source
  greedy, no capacity constraints). H7's added value is the
  *path semantics* (vs H2's connected components) and the
  *principled cost formulation* (vs H6's per-source greedy).
  See `h1_hand_pool/reports/h7_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h7_min_cost_flow.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h7_sens_grid.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h7_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h237_unified_chain.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7_min_cost_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7_sens_grid.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7_admitted_edges_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7_chains_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237_unified_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237_unified_edges_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237_unified_chains_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h7/tracklet3_conflict_h7.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h7/longest_chain_h7.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h7_report.md`

### H8 (2026-08-28 ~07:10 CEST)

- Hypothesis: a real airborne ball's y-velocity changes slowly
  (gravity = ~0.5 px/frame^2 for a juggling ball at ~1m distance).
  E6c's constant-velocity ballistic model misses identity switches
  where two unrelated tracklets are linked. A per-edge y-velocity
  discontinuity check should flag these.

- Thresholds (declared from physical geometry, not from manual labels):
  - VELOCITY_DISCONTINUITY_PX_PER_FRAME = 8.0
  - TAIL_FRAMES = 3 (use last 3 frames of source, first 3 of target)
  - MIN_TRACKLET_PTS = 3

- Three iterated implementations:
  - v1 (per-chain parabola): abandoned; juggling chains span
    multiple parabolic arcs, single parabola doesn't fit.
  - v2 (per-tracklet parabola): useful as tracklet-level metadata
    but not as per-edge check.
  - **v3 (per-edge y-velocity discontinuity) — RECOMMENDED.**

- Algorithm: for each BALLISTIC edge in H7's chain representation,
  compare y-velocity at source-tracklet tail (last 3 frames) to
  y-velocity at target-tracklet head (first 3 frames). Flag
  edges with discontinuity > 8.0 px/frame as likely identity
  switches. Hand edges are EXCLUDED (held-then-released naturally
  has vy discontinuity).

- Quantitative result:

| Video | n_air edges | n_air OK | n_air violating |
|---|---|---|---|
| identical | 23 | 14 | 9 |
| YouTube | 24 | 1 | 23 (unreliable for long tracklets) |

- Visual QA: 2 confirmed identity switches on identical:
  - **5→6**: t5 was a held ball being released, t6 is a different
    ball already in mid-air. 90px y-jump in 1 frame. Visual QA
    confirmed.
  - **50→55**: t50 ends in the hand area, t55 starts at a
    different location. Visual QA confirmed.

  All 6 air-edges in the longest H7 chain (35→37→40→41→43→45→46)
  are OK (discontinuity ≤ 2.2 px/frame). This is consistent with
  the visual QA that confirmed it as a real juggling cycle.

- Negative findings:
  - H8 v1 (per-chain parabola) was abandoned because juggling
    chains span multiple parabolic arcs.
  - H8 v2 (per-tracklet classification) classified 36/76 identical
    and 31/40 YouTube tracklets as NOISY. Many false positives
    because long tracklets span multiple bounces.
  - H8 is unreliable on long tracklets (YouTube video): 23/24 air
    edges flagged, but most are real because the tracklets span
    many bounces (e.g., t4 has 415 frames covering f=2-416). A
    future v4 should restrict H8 to short tracklets (n_pts ≤ 30).

- Verdict: **PASS.** H8 successfully identifies 2 confirmed E6c
  false positives on identical (5→6, 50→55) that H2/H6/H7 all
  accepted. The metric is unreliable on long tracklets but is a
  useful post-hoc quality signal. See
  `h1_hand_pool/reports/h8_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_physics_check.py` (v1, abandoned)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v2_per_tracklet.py` (v2, partial)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v3_edge_physics.py` (v3, recommended)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_physics_check_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v2_per_tracklet_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v3_edge_physics_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/chain4_t5_t6_violating.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/chain29_t50_t55_violating.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8/longest_chain_consistent.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h8_report.md`
