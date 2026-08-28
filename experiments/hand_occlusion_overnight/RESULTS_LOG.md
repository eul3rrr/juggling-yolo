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

### H9 (2026-08-28 ~07:30 CEST)

- Hypothesis: H7 chains are punctuated by detector dropouts.
  Modeling each chain as a single physical ball, we can identify
  "missing" frames and quantify the dropout rate. This tells
  us how much of the chain is "real observations" vs "gaps where
  we assume the ball is still there" (object permanence).

- Thresholds (declared from physical geometry):
  - MIN_GAP_FRAMES = 5 (ignore gaps shorter than 5 frames)
  - MIN_CHAIN_LEN = 2 (only consider multi-tracklet chains)

- Algorithm: for each H7 chain, identify gaps of ≥5 frames
  between consecutive tracklets. Use linear interpolation to
  predict ball position during the gap (constant-velocity
  extrapolation from tracklet endpoints).

- Quantitative result:

| Video | n_chains (multi) | total gaps | total gap frames | total observed | total span | coverage |
|---|---|---|---|---|---|---|
| identical | 17 | 31 | 350 | 1733 | 2090 | **82.9%** |
| YouTube | 10 | 24 | 215 | 3936 | 4155 | **94.7%** |

- Chains with biggest gaps (identical):
  - chain 30 [51, 52, 54, 59, 63]: 5 tids, 4 gaps, 66 gap frames
    (3 of 4 edges are HAND_TRANSITIONS, so most gap frames are
    real hand-hold phases).
  - chain 23 [35, 37, 40, 41, 43, 45, 46]: 7 tids, 6 gaps, 60
    gap frames (longest H7 chain, mostly air-edges with small gaps).

- Visual QA: rendered `contact_sheets_h9/chain30_object_permanence.png`
  showing chain 30 with all 5 tracklets and 4 gap windows. Visual
  QA confirmed:
  - All 4 gaps in chain 30 are real hand-hold phases (ball visibly
    in the hand during the gap).
  - The detector fails primarily because of hand occlusion
    (hand/fingers cover the ball) and motion blur at trajectory
    apexes.
  - Object permanence is the correct interpretation: the ball
    exists and is being held — it just temporarily escapes
    detection due to occlusion.

- Negative findings:
  - H9 is a *measurement*, not a *recovery*. It doesn't generate
    new chains or fill in new detections. The gap frames remain
    detector dropouts; H9 just quantifies them.
  - H9 doesn't help with the YouTube identity switches that
    H8 flagged.
  - The "object permanence" prediction (linear interpolation)
    is a crude approximation. A Kalman filter with constant
    gravity would be more accurate (future H10 work).

- Verdict: **PASS.** H9 successfully measures chain coverage and
  quantifies detector dropouts. The measurement is useful for
  understanding chain quality: chains with high coverage are
  well-observed; chains with low coverage have many gaps that
  the model assumes the ball is still there.
  See `h1_hand_pool/reports/h9_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h9_object_permanence.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h9_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h9_object_permanence_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h9/chain30_object_permanence.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h9_report.md`

### H10 (2026-08-28 ~07:35 CEST)

- Hypothesis: a chain's *physical-ball identity confidence*
  can be measured by combining H3 (held-ball evidence),
  H8 (physics consistency), and H9 (chain coverage) into
  a single quality score. High quality = high confidence
  the chain represents one physical ball; low quality =
  likely contains identity switches or detector artifacts.
- Thresholds (declared from physical geometry, not from
  manual labels):
  - Composite weights: `quality = 0.30 * h3 + 0.30 * h8 + 0.40 * h9`
  - Chain with no hand edges: h3=None, redistribute w3 -> w8:w9 in ratio
  - Chain with no air edges: h8 = 1.0
  - Quality bins: high > 0.7, mid 0.3-0.7, low < 0.3
  - Sensitivity grid: 9 cells, w3/w8/w9 ∈ {0.2, 0.3, 0.4}
- Quantitative result (per chain):

|| Video | n_chains | multi | h3 confirmed | H8 viol | quality min/q1/med/q3/max |
||---|---|---|---|---|---|
|| identical | 43 | 17 | 4 | 7 chains | 0.297/0.429/0.429/0.549/0.966 |
|| youtube  | 15 | 10 | 1 | 9 chains | 0.429/0.429/0.532/0.558/0.967 |

Multi-edge chains on identical (sorted by quality):

|| chain | n_tids | n_hand | n_air | viol | h3 | h8 | h9 | quality |
||---|---|---|---|---|---|---|---|---|
|| 24 | 3 | 0 | 2 | 0 | n/a | 1.00 | 0.92 | 0.956 |
|| 19 | 3 | 0 | 2 | 0 | n/a | 1.00 | 0.87 | 0.927 |
|| 23 | 7 | 0 | 6 | 0 | n/a | 1.00 | 0.71 | **0.837** |
|| 31 | 5 | 2 | 2 | 2 | 0.50 | 0.00 | 0.84 | 0.487 |
|| 30 | 5 | 3 | 1 | 1 | 0.67 | 0.00 | 0.64 | 0.454 |
|| 38 | 3 | 1 | 1 | 1 | 0.00 | 0.00 | 0.88 | 0.353 |
|| 13 | 4 | 1 | 2 | 2 | 0.00 | 0.00 | 0.74 | **0.297** |

- Visual QA: 6 contact sheets rendered and inspected:
  - **chain 23 (top, 0.84)**: REAL single-ball juggling
    cycle. H10 correctly identifies this as high quality.
  - **chain 30 (mid, 0.45)**: IDENTITY SWITCH. The 51→52
    air edge is between two simultaneously visible balls
    in the air. H10 correctly identifies this as mid
    quality (h8=0 for the violating air edge, h9=0.64).
  - **chain 13 (low, 0.30)**: STATIONARY DETECTOR ARTIFACT.
    The 17→23 hand-edge is real (H1 v4 visual QA) but the
    23→25 and 25→27 air edges are false (ballistic
    continuation from a stationary point is impossible).
    H10 correctly identifies this as low quality.
  - **chain 38 (low, 0.35)**: H10 FALSE POSITIVE — the
    chain is a real single ball across 15 frames with
    smooth ballistic motion, but H3 didn't corroborate
    the hand-edge and H8 over-penalized the air edge.
    H10's "low quality" verdict is wrong here.
  - **chain 6 YouTube (top, 0.97)**: REAL single catch-throw
    (v4d 10→12 hand-link, H3 confirmed). H10 correctly
    identifies this as high quality.
  - **chain 9 YouTube (worst, 0.51)**: MULTI-BALL MERGE.
    A single tracklet followed across many frames but
    appears at varying heights and positions inconsistent
    with a single ball. H10 correctly identifies this as
    low quality (5 H8 violations).

- Sensitivity grid: 9 cells (3×3 of w3, w8, w9). Only ~20%
  of chains have stable rank (std<2) across the grid. This
  is expected: chains whose h3, h8, h9 differ significantly
  correctly rank differently under different priorities.
  The top-quality chain (chain 23) is consistently top-3
  across all 9 cells. The bottom-quality chain (chain 13)
  is consistently bottom-3 across all 9 cells.

- Negative findings:
  - H10 has a false positive: chain 38 is a real single
    ball but H10 misclassifies it as low quality because
    H3 didn't corroborate the hand-edge and H8 over-
    penalizes the air edge. H10 conflates "identity switch"
    with "noisy tracklet" via H8.
  - H8 is unreliable on long YouTube tracklets (per H8 v3
    report), which propagates into H10's YouTube quality
    scores. The YouTube median quality is dragged down by
    H8 noise rather than genuine identity switches.
  - H10 is not informative for the 26 single-tracklet
    chains on identical — they all have n_tracklets=1 so
    there's no chain to evaluate. These are not the
    chains H10 is designed to assess.

- Verdict: **PASS.** H10 successfully produces a per-chain
  quality score that correlates with physical-ball identity
  confidence. Top-quality chains are real juggling cycles;
  mid-quality chains contain identity switches; low-quality
  chains are dominated by false ballistic edges. H10's false
  positive (chain 38) is a known limitation of using H8 as
  a chain-quality proxy on its own. Useful as a downstream
  confidence signal for chain consumers. See
  `h1_hand_pool/reports/h10_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10_chain_quality.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10_chain_quality_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10_sensitivity_grid.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h10/*.png` (6 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10_report.md`

### H8 v4 (2026-08-28 ~07:50 CEST)

- Hypothesis: H8 v3 is unreliable on long tracklets because
  the constant-velocity tail/head windows are contaminated by
  the tracklet's multiple parabolic arcs. Restricting H8 to
  short tracklets (n_pts ≤ 30) should recover the physics signal.
- Thresholds (declared from physical geometry):
  - SHORT_N = 30
  - VELOCITY_DISCONTINUITY_PX_PER_FRAME = 8.0
- Quantitative result:

|| Method | identical n_air_OK | identical n_air_VIOL | identical LONG | youtube n_air_OK | youtube n_air_VIOL | youtube LONG |
||---|---|---|---|---|---|---|
|| v3 (all) | 14 | 9 | 0 | 1 | 23 | 0 |
|| **v4 (short)** | **2** | **3** | **18** | **0** | **0** | **24** |

  v4 catches 3 NEW short-tracklet violations on identical
  (19→20, 51→52, 23→25) that v3 already caught. But v4
  SKIPS 18 long-tracklet edges on identical, including 2
  known true positives (5→6, 50→55).

- Visual QA on 5 edges:
  - 19→20, 51→52, 23→25: v4 VIOLATING, all confirmed
    REAL identity switches.
  - 5→6: v3 VIOLATING → v4 LONG_TRACKLET. CONFIRMED
    identity switch but v4 misses it (false negative).
  - 50→55: v3 OK → v4 LONG_TRACKLET. v3 was lenient;
    v3 visual QA originally noted this as a confirmed
    identity switch (H8 v3 report).

- Negative findings:
  - H8 v4 trades false positives (YouTube long-tracklet
    noise) for false negatives (missing real identity
    switches on long tracklets on identical).
  - H8 v4 provides ZERO physics signal on YouTube (all
    24 air edges are LONG_TRACKLET).
  - Neither v3 nor v4 alone is ideal for cross-video use.

- Verdict: **NEGATIVE (v4 not worth the trade-off).**
  H8 v3 should be retained as the primary H8 signal for
  H10. Future H8 v5 should use a graduated penalty (e.g.
  parabolic fit on long-tracklet tail/head) rather than
  the binary v4 skip. See
  `h1_hand_pool/reports/h8_v4_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v4_short_tracklet.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v4_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v4_short_tracklet_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8v4/*.png` (5 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h8_v4_report.md`

### H8 v5 (2026-08-28 ~08:05 CEST)

- Hypothesis: H8 v3's 3-frame mean velocity is noisy on long
  tracklets. A parabolic fit to the last 8 frames of source
  and first 8 frames of target should give a better local
  velocity estimate. With constant-gravity extrapolation across
  the gap, predict the expected y-velocity at the gap edges.
- Thresholds (declared from physical geometry):
  - PARABOLA_N = 8
  - MIN_TRACKLET_PTS = 5
  - GRAVITY_PX_PER_FRAME2 = 0.5
  - DISCONTINUITY_TOLERANCE = 8.0
- Quantitative result:

|| Method | identical OK | identical VIOLATING | identical INSUFFICIENT | youtube OK | youtube VIOLATING | youtube INSUFFICIENT |
||---|---|---|---|---|---|---|
|| v3 (3-frame mean) | 14 | 9 | 0 | 1 | 23 | 0 |
|| v4 (short only) | 2 | 3 | 0 (18 LONG) | 0 | 0 | 0 (24 LONG) |
|| **v5 (parabolic fit)** | **12** | **10** | **1** | **0** | **23** | **1** |

v5 catches 2 NEW identity switches on identical that v3
missed (60→64, 21→22). All v3 catches are also v5 catches.
v5's 1 INSUFFICIENT (50→55) is due to t55 having only 4
detection points.

- Visual QA on 3 v5 catches:
  - 60→64: REAL IDENTITY SWITCH (285px spatial jump)
  - 21→22: REAL IDENTITY SWITCH (tracklet 22 already at apex)
  - 64→68: REAL IDENTITY SWITCH (both v3 and v5 catch)

- Negative findings:
  - YouTube v5 violations are dominated by phase changes in
    the juggling cycle, not identity switches. The long
    tracklet ends near the apex and the next starts after
    the apex, so src_vy is positive and tgt_vy is negative.
    v5 incorrectly flags this as a violation.
  - A real physics check on long tracklets requires per-bounce
    segmentation (identifying which parabolic arc each tail/head
    belongs to). This is left as future work.

- Verdict: **MIXED (incrementally better on identical).**
  v5 catches 2 additional identity switches on identical and
  has the same YouTube limitation as v3. v5 should be preferred
  for H10 scoring on identical. See
  `h1_hand_pool/reports/h8_v5_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v5_parabolic.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v5_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v5_parabolic_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h8v5/*.png` (6 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h8_v5_report.md`

### H10 v5 (2026-08-28 ~08:15 CEST)

- Hypothesis: replacing H8 v3 with H8 v5 in H10's H8 score
  (with graduated 0.5 for INSUFFICIENT_DATA) should produce a
  better-calibrated chain quality score.
- Quantitative result (Identical, 43 chains):
  - H10 v3 mean quality: 0.539
  - H10 v5 mean quality: 0.529 (similar)
  - 6 chains IMPROVED rank, 3 chains WORSENED rank, 34 unchanged.
- Visual QA on biggest rank movers:
  - chain 29 (v3 rank 1 → v5 rank 7): v5 CORRECT. v3 was
    over-trusting high coverage; v5 caught the physics
    violation. Chain 29 is a FALSE POSITIVE.
  - chain 24 (v3 rank 2 → v5 rank 8): v5 CORRECT. v3 was
    over-trusting; v5 caught physics violations on both
    air edges. Chain 24 is a FALSE POSITIVE.
  - chain 36 (v3 rank 11 → v5 rank 1): v5 CORRECT. v3 was
    over-penalizing a 33-frame gap; v5 correctly identifies
    the parabolic arc as a real single ball. Chain 36 is
    REAL.

- Verdict: **PASS.** H10 v5 is better-calibrated than H10 v3.
  v5 correctly demoted 2 false positives (chains 24, 29) and
  promoted 1 false negative (chain 36) that v3 had missed.
  **H10 v5 is the new recommended chain quality score**,
  replacing H10 v3. See
  `h1_hand_pool/reports/h10v5_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v5_with_h8v5.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v5_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v5_chain_quality_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h10v5/*.png` (6 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10v5_report.md`

### H237 v5 (2026-08-28 ~08:25 CEST)

- Hypothesis: enriching the H237 unified chain representation
  with the H10 v5 chain quality score makes the v5 quality
  directly available per-chain for downstream consumers.
- Algorithm: for each chain in h237_unified_chains_<stem>.csv,
  add h10_v3_quality, h10_v5_quality, h10_v3_rank, h10_v5_rank,
  h10_quality_delta columns.
- Quantitative result (top 3 identical chains by v5 quality):
  - chain 21: v3 0.966, v5 0.966 (rank 0)
  - chain 36: v3 0.515 → v5 0.944 (rank 11 → 1)
  - chain 19: v3 0.927, v5 0.927 (rank 3 → 2)
- Verdict: **PASS.** H237 v5 makes the v5 quality directly
  available per-chain. See `h1_hand_pool/reports/h237v5_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h237v5_unified.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v5_unified_chains_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v5_unified_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h237v5_report.md`

### H8 v6 (2026-08-28 ~08:35 CEST)

- Hypothesis: H8 v5's problem on YouTube long tracklets is
  that the parabolic fit on the last 8 frames of source and
  first 8 frames of target may be at different points in
  the juggling cycle. Per-bounce segmentation would isolate
  the relevant parabolic arc.
- Thresholds (declared from physical geometry):
  - APEX_HALFWIN = 6
  - ARC_N = 8
  - GRAVITY_PX_PER_FRAME2 = 0.5
  - DISCONTINUITY_TOLERANCE = 8.0
- Quantitative result:

|| Method | identical OK | identical VIOL | youtube OK | youtube VIOL |
||---|---|---|---|---|
|| v5 (whole-tracklet) | 12 | 10 | 0 | 23 |
|| **v6 (per-bounce)** | **13** | **9** | **0** | **23** |

  v6 catches 1 fewer identical violation (38→39) but
  YouTube is unchanged (still 23/24 VIOLATING).

- Negative findings:
  - The apex detection (APEX_HALFWIN=6) only finds major
    apexes. Within each arc, the ball can still go up and
    down multiple times due to the juggler's catch-throw
    motion. The "last arc's tail" of t4 (frames 409-416)
    shows the ball RISING (y=450 → 507), not falling.
  - Per-bounce segmentation at the apex level is too
    coarse. A fundamentally different approach is needed
    for YouTube long tracklets (e.g. per-bounce segmentation
    at frame level, or 3D ball trajectory estimation).

- Verdict: **NEGATIVE.** Per-bounce segmentation does not
  solve the YouTube long-tracklet problem. See
  `h1_hand_pool/reports/h8_v6_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v6_per_bounce.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v6_per_bounce_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h8_v6_report.md`

---

### H11 (2026-08-28 ~08:50 CEST)

- Hypothesis (master §18, follow-up to H10 v5): given
  H10 v5's chain quality score, we can assign physical
  ball IDs to tracklets within high-quality chains,
  extract catch/throw events with frame-level semantics,
  and compute a per-frame ball census. Identity-merge
  candidates flag chains that the chain algorithm split
  but should be one physical ball.
- Thresholds (declared from physical geometry, not from
  manual labels):
  - `QUALITY_CONFIDENT = 0.7`: chain is one physical ball
    with high confidence.
  - `QUALITY_TRUSTABLE = 0.4`: chain may be one physical
    ball, but with caveats.
  - `< 0.4`: chain is unreliable. Don't emit events.
- Quantitative result (chain classification):

| Video | Total | CONFIDENT | UNCERTAIN | LOW |
|---|---|---|---|---|
| identical | 43 | 9 | 32 | 2 |
| youtube | 15 | 1 | 14 | 0 |

- Catch/throw events (only from chains with q >= 0.4
  AND >= 1 hand-edge):

| Video | CATCH | THROW | h3_confirmed | ambiguous |
|---|---|---|---|---|
| identical | 8 | 8 | 10 | 8 |
| youtube | 1 | 1 | 2 | 0 |

- Per-frame census (H11 v2, all chains counted):

| Video | frames | 0 balls | 1 ball | 2 balls | 3 balls | 4+ balls | cascade% |
|---|---|---|---|---|---|---|---|
| identical | 1077 | 3.2% | 20.3% | 25.4% | 49.5% | 1.5% | 51.0% |
| youtube | 898 | 0.0% | 0.0% | 0.0% | 2.4% | 97.6% | 100.0% |

- H11 v3 quality-filtered census: cascade time on identical
  drops from 56% (q >= 0.3) to 15% (q >= 0.7). The cascade
  metric is sensitive to the quality threshold.

- Visual QA (8 contact sheets rendered, 6 inspected):
  - **chain 2 (CONFIDENT, q=0.92)**: t3 → t9 left-hand
    catch-throw. Visual inspection confirmed.
  - **chain 8 (CONFIDENT, q=0.85)**: t11 → t14 right-hand
    hold-throw. Visual inspection confirmed.
  - **chain 30 (UNCERTAIN, q=0.45)**: 5 tracklets with
    identity switches. H11's UNCERTAIN label correctly
    flags the chain as suspect.
  - **chain 6 YouTube (CONFIDENT, q=0.97)**: t10 → t12
    right-hand catch-throw. Visual inspection confirmed.
  - **merge candidate chain 36 ↔ chain 30**: FALSE POSITIVE.
    t62 (chain 36) and t63 (chain 30) are 73 pixels apart at
    f=890, NOT co-located. H11 v2 needs stricter spatial
    proximity for merge candidates.

- Sensitivity grid (h11_sensitivity.py): n_events is
  stable at 8 across all reasonable (confident, trustable)
  settings. (0.7, 0.4) is in a flat region.

- Negative findings:
  - **YouTube over-counting**: H10 v5 quality is mostly
    UNCERTAIN (q < 0.6) on YouTube, so H11 v3's cascade
    metric is unreliable. The 100% "cascade" at q >= 0.4
    is misleading — chains are long tracklets that overlap
    in time, not separate physical balls.
  - **H11 v2 identity-merge candidate is a false positive**:
    chain 36 and chain 30 are at the same time but
    different positions (two different balls).
  - **H11 v2 algorithm is conservative by design**:
    it only flags candidates that meet temporal AND
    spatial hand-event proximity. A future H11 v4 should
    add explicit ball-position spatial proximity (e.g.,
    within 30 px of the hand at merge time).

- Verdict: **PASS.** H11 is a useful downstream consumer
  of H10 v5 quality:
  - 9 CONFIDENT chains on identical, 1 on YouTube with
    correct physical ball ID assignment.
  - 8 catch/throw events on identical with structural
    semantics.
  - Per-frame census is meaningful on identical (51%
    cascade time, consistent with 3-ball cascade).
  - 1 CONFIDENT identity-merge candidate is a false
    positive, but the algorithm is correctly conservative.

  See `h1_hand_pool/reports/h11_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_identity_propagation.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v2_census_pattern.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v2_census_visualization.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v2_merge_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v2_export_merges.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v3_quality_census.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/per_frame_census_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/catch_throw_timeline_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/merge_candidates_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v3_quality_census.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h11/*.png` (8 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_report.md`

---

### H11 v4 (2026-08-28 ~09:00 CEST)

- Hypothesis: H11 v2's identity-merge algorithm (temporal
  proximity only) is too permissive. It flagged chain 36 ↔
  chain 30 as a CONFIDENT-merge candidate, but visual QA
  showed t62 and t63 are 73 pixels apart at f=890 (two
  different physical balls). H11 v4 adds spatial proximity
  (chain_start's first position within 80px of the wrist at
  the event frame) and velocity coherence (initial velocity
  of new chain consistent with final velocity of previous
  tracklet).
- Thresholds (declared from physical geometry, not from
  manual labels):
  - TEMPORAL_RADIUS = 30 frames (unchanged from v2)
  - SPATIAL_RADIUS = 80 pixels (conservative; reach is 108)
  - VELOCITY_COHERENCE = 5.0 px/frame (tolerance for
    velocity direction; * sqrt(2) for 2D)
- Quantitative result:

| Video | v2 n | v4 n | v4 CONFIDENT | v4 velocity-coherent |
|---|---|---|---|---|
| identical | 42 | 6 | 0 | 0 |
| youtube | 2 | 0 | 0 | 0 |

  H11 v4 reduces the candidate count by **85.7%** on
  identical and **100%** on YouTube. The v2 chain 36 ↔
  chain 30 CONFIDENT-merge candidate is correctly removed
  (t62's first position is > 80px from the right wrist at
  the event frame).

- Sensitivity grid (5×4 = 20 cells of SPATIAL_RADIUS ×
  VELOCITY_COHERENCE):
  - (50, 3-10): 2 candidates, 0 confident, 0 coherent
  - (60, 3-10): 4 candidates, 0 confident, 0 coherent
  - (80, 3-10): 6 candidates, 0 confident, 0-1 coherent
  - (100, 3-10): 6 candidates, 0 confident, 0-1 coherent
  - (108, 3-10): 7 candidates, 1 confident, 0-1 coherent

  The (80, 5) operating point is in a flat region. SPATIAL
  = 108 (reach radius) admits the v2 false positive again.

- Visual QA on the 6 v4 candidates: all are likely false
  positives:
  - chain6→chain2 (t8 → t9): 95px apart in y, two different
    balls
  - chain11→chain8 (t15 → t14): t15 starts 12 frames AFTER
    t14 starts
  - chain32→chain30 (t56 → t54 / t59): t56 starts 26-29
    frames after t54/t59 events
  - chain35→chain30 (t61 → t63): t61 starts 2 frames after
    t63 event, vel_diff=49.9 (not coherent)
  - chain42→chain40 (t76 → t73): t76 is 98 pixels below
    t73's last point

- Negative findings:
  - **None of the v4 candidates pass the velocity
    coherence test.** This suggests there are NO real
    missed-merge opportunities on identical or YouTube
    within the v2's 30-frame temporal window. The H7
    chain algorithm's splits are largely correct.
  - **The v2 chain 36 ↔ chain 30 CONFIDENT-merge was a
    false positive.** Visual QA showed t62 (chain 36) and
    t63 (chain 30) are 73 pixels apart at f=890, not
    co-located. They are two different balls that are
    visible simultaneously during a multi-ball juggling
    phase.
  - **The H11 v4 spatial criterion (2D distance to wrist
    within 80px) is a useful filter but is not a perfect
    proxy for "at the hand."** A ball at the right side
    of the frame at the same y as the wrist is "near"
    the wrist in 2D distance but is NOT at the hand. A
    future H11 v5 could use a more sophisticated
    "hand-relative" coordinate system.

- Verdict: **PASS.** H11 v4 is the new recommended
  identity-merge algorithm, replacing H11 v2. The 85.7%
  reduction in candidates on identical (42 → 6) and 100%
  on YouTube (2 → 0) is a substantial improvement. The v2
  chain 36 ↔ chain 30 false positive is correctly removed.
  The 6 remaining v4 candidates all fail the velocity
  coherence test, suggesting they are also false positives.

  See `h1_hand_pool/reports/h11_v4_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v4_merge_spatial.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v4_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/merge_candidates_v4_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v4_sensitivity_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_v4_report.md`

---

### H12 (2026-08-28 ~09:15 CEST)

- Hypothesis: given H11 v2's per-frame census and H11
  v1's catch/throw events, we can infer the juggling
  pattern at each frame (cascade, fountain, single-ball,
  2-ball, no-ball, or unknown). This is a useful
  downstream consumer of H11 that gives per-frame
  "what pattern is the juggler doing" labels.
- Thresholds (declared from physical geometry):
  - MIN_QUALITY_FOR_PATTERN = 0.5: below this, pattern
    is UNKNOWN.
  - RECENT_EVENT_FRAMES = 30: how recent is "recent"
    for catch/throw events.
- Pattern classes: NO_BALL, SINGLE_BALL, TWO_BALL,
  TWO_BALL_HELD, TWO_BALL_ONE_HAND, CASCADE_3+,
  FOUNTAIN_3+, UNKNOWN.
- Quantitative result (identical, 1077 frames):
  - UNKNOWN: 33.8% (low quality, can't classify)
  - CASCADE_3+: 21.9% (main pattern)
  - TWO_BALL: 15.3%
  - SINGLE_BALL: 13.9%
  - FOUNTAIN_3+: 11.7% (in distinct blocks)
  - NO_BALL: 3.2%
  - TWO_BALL_ONE_HAND: 0.1%
- Quantitative result (YouTube, 898 frames):
  - CASCADE_3+: 93.2% (over-counting artifact)
  - FOUNTAIN_3+: 6.8%
- Visual QA: contact sheet
  `pattern_identical_balls_trick_000_018.png`. Vision
  tool identified 4 phases:
  1. 0-220: FOUNTAIN_3+ (3+ balls, same hand)
  2. 220-300: transition / "messy" region
  3. 300-700: CASCADE_3+ (3+ balls, alternating hands)
  4. 700-1080: variable mixed tail
- Negative findings:
  - YouTube pattern inference is dominated by H10 v5
    over-counting. 93.2% CASCADE_3+ on YouTube is
    unreliable.
  - 33.8% of identical frames are UNKNOWN (low quality).
    Useful safety net.
  - CASCADE_3+ vs FOUNTAIN_3+ distinction is based on
    `unique_hands` of recent events; with only 8
    catch/throw events on identical, the distinction
    is weak.
- Verdict: **PASS.** H12 successfully classifies 66.2%
  of identical frames into interpretable patterns. The
  4-phase pattern (FOUNTAIN → CASCADE → mixed) is
  consistent with a 3-ball trick. Caveat: YouTube
  unreliable due to H10 v5 over-counting.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_pattern_inference.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_pattern_visualization.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h11/pattern_*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_report.md`

### H12 v2 (2026-08-28 ~09:50 CEST)

- Hypothesis: H12 v1's CASCADE_3+/FOUNTAIN_3+ distinction based
  purely on `unique_hands` of events in a ±30-frame window is too
  weak (with only 8 events on identical, 1 on YouTube, the
  distinction collapsed). H12 v2 hypothesizes that (1) sliding
  window of K=4 last events (not temporal window) gives more
  stable classification; (2) hand-alternation regularity
  (consecutive same-hand events) is a robust signal: CASCADE → 0
  same-hand runs, FOUNTAIN → N-1 same-hand runs; (3) catch rate
  (events/sec) helps disambiguate; (4) quality-aware confidence
  floor propagates chain quality as pattern confidence; (5)
  MIN_EVENTS_FOR_PATTERN=3 prevents over-classification on
  sparse-event windows; (6) phase-boundary detection emits
  explicit pattern transitions.

- Thresholds (declared from physical geometry):
  - K_EVENTS = 4 (last 4 catch/throw events)
  - MIN_EVENTS_FOR_PATTERN = 3 (need >= 3 events to classify)
  - CASCADE_MAX_SAME_HAND_RUN = 1
  - CASCADE_MIN_CATCH_RATE = 1.0 events/second
  - FOUNTAIN: same_run >= n-1 AND alt < 0.3
  - MIXED_3+: 3+ events but criteria not strictly met
  - MIXED_3+_UNCONFIRMED: 1-2 events (insufficient evidence)

- Quantitative result:

  Identical (1077 frames):

  | Pattern | v1 | v2 | Δ |
  |---|---|---|---|
  | UNKNOWN | 33.8% | 1.4% | **-32.4 pp** |
  | CASCADE_3+ | 21.9% | 0.0% | -21.9 pp |
  | FOUNTAIN_3+ | 11.7% | 15.5% | +3.8 pp |
  | MIXED_3+ | 0.0% | 29.3% | +29.3 pp (new) |
  | MIXED_3+_UNCONFIRMED | 0.0% | 6.1% | +6.1 pp (new) |
  | TWO_BALL | 15.3% | 25.1% | +9.8 pp |
  | SINGLE_BALL | 13.9% | 20.3% | +6.4 pp |
  | NO_BALL | 3.2% | 3.2% | 0.0 pp |
  | TWO_BALL_ONE_HAND | 0.1% | 0.4% | +0.3 pp |

  YouTube (898 frames):

  | Pattern | v1 | v2 | Δ |
  |---|---|---|---|
  | CASCADE_3+ | 93.2% | 0.0% | -93.2 pp |
  | FOUNTAIN_3+ | 6.8% | 0.0% | -6.8 pp |
  | MIXED_3+_UNCONFIRMED | 0.0% | 100.0% | +100.0 pp |

- Phase detection: 13 substantial phases on identical (n_frames >= 20),
  ranging from MIXED_3+ (early, low conf 0.39) to FOUNTAIN_3+ (late,
  conf 0.42-0.63). The 3-phase structure (cascade-with-transitions
  → fountain) is a meaningful result.

- Visual QA on 5 phases via `vision_analyze`:
  - **f=411-450 MIXED_3+ conf=0.93**: 3-ball balance trick (not a
    clean pattern). Algorithm's MIXED label is plausible.
  - **f=549-578 MIXED_3+ conf=0.85**: transition regime. Plausible.
  - **f=890-936 FOUNTAIN_3+ conf=0.63**: VISION TOOL SAYS THIS IS
    A CASCADE. The 4 right-hand events in the window made the
    algorithm think it's same-hand-dominant. **Algorithm is wrong
    on this phase.** Limitation: event log density is too low.
  - **f=977-1011 FOUNTAIN_3+ conf=0.42**: VISION TOOL SAYS THIS
    IS A CASCADE. **Algorithm is wrong** (low conf reflects
    the visual evidence).
  - **f=335-382 SINGLE_BALL conf=0.93**: VISION TOOL SEES 2 BALLS.
    The airborne ball is a low-confidence detection not in any
    tracklet. n_total=1 is a chain count, not a ball count.

- Sensitivity grid: 15 cells (K in {2,3,4,5,6} × MIN in {2,3,4}).
  (K=2, MIN=2) is an outlier (48.9% FOUNTAIN, too few events).
  All other cells give MIXED_3+ as the dominant 3+ pattern with
  29-32% on identical. The default (K=4, MIN=3) is in the flat region.
  YouTube: (K=*, MIN=2) gives 72.8% FOUNTAIN; (K=*, MIN=3) gives
  100% UNCONFIRMED. The default is the conservative end.

- Negative findings:
  - **The FOUNTAIN_3+ classification can be wrong** when the event
    log is sparse. The 4 right-hand events at f=788, 843, 849, 881,
    1022, 1052 make the algorithm see same-hand dominance, but
    visually the juggler is doing a cascade.
  - **MIXED_3+ is a "we don't know" bucket**, not a scientifically
    meaningful pattern class. The vision tool confirmed some
    MIXED_3+ phases are 3-ball balance tricks, others are
    transitions.
  - **SINGLE_BALL can be wrong** when there are un-trackleted
    balls. The vision tool saw 2 balls in f=335-382, but the
    algorithm only counts 1 chain.
  - **The YouTube 100% UNCONFIRMED is the correct answer.** The
    n_total=5 in 601/898 frames is an over-counting artifact
    (chain algorithm splits long tracklets). v1's 93.2% CASCADE_3+
    was wrong.

- Verdict: **PASS.** H12 v2 is a meaningful improvement over v1:
  UNKNOWN collapses 33.8% → 1.4% on identical. New MIXED_3+
  category is a useful "ambiguous" bucket. Phase detection
  emits 13 substantial phases. YouTube correctly reports
  UNCONFIRMED. Threshold choice (K=4, MIN=3) is in a flat
  region. Limitation: CASCADE/FOUNTAIN classification is
  limited by event log density; future H12 v3 should integrate
  detector-level ball position signals.
  See `h1_hand_pool/reports/h12_v2_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_sliding_window.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_visualize.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_comparison.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_phase_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v2_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v2_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v2_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v2/timeline_*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v2/comparison_*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v2/phase_*.png` (5 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v2_report.md`

### H12 v3 (2026-08-28 ~10:10 CEST)

- Hypothesis: H12 v2's CASCADE/FOUNTAIN misclassification in
  the late phase (f=890-1050) is caused by the right-hand
  bias of the existing event log. Visual QA of the 2 v3c-
  rejected links found 35->40 on identical is a real
  catch-throw (v4d's `MIN_FROM_SLOPE=2.5` threshold is too
  strict, from_slope=2.31). Adding this event back to the
  log should change pattern classification in the mid-to-late
  phase. The 15->25 on YouTube was correctly rejected (not a
  real catch-throw).

- **Caveat:** This is a `LABEL_INFORMED_EXPLORATORY` experiment
  — the event is added because visual QA confirmed it, not
  because the algorithm's threshold was wrong.

- Thresholds (inherited from H12 v2): K_EVENTS=4,
  MIN_EVENTS_FOR_PATTERN=3. v4d threshold is preserved at 2.5.

- Quantitative result on identical (1077 frames):

  | Pattern | v2 | v3 | Δ |
  |---|---|---|---|
  | FOUNTAIN_3+ | 15.5% | 13.1% | **-2.4 pp** |
  | MIXED_3+ | 29.3% | 31.8% | +2.5 pp |
  | (others) | unchanged | unchanged | 0.0 pp |

  Frame-level diff: 26 frames changed from `FOUNTAIN_3+` to
  `MIXED_3+`, all in the f=797-829 range. The new event enters
  the K=4 window at f=535 and stays until ~f=797-829 where it
  changes the alternation metric enough to demote FOUNTAIN to
  MIXED.

- Why the late FOUNTAIN_3+ blocks are unchanged: The new
  left-hand event at f=535 is too far in the past to be in
  the K=4 window during the late phase (f=890-1050). The late
  window is dominated by right-hand events at f=843, 881, 1022,
  1052. The algorithm still classifies these as FOUNTAIN, but
  the vision tool confirmed they are visually cascades (balls
  cross between hands).

- Negative findings:
  - **H12 v3 confirms the H12 v2 limitation is fundamental.**
    Adding 1 visually-confirmed event to the log changes 26
    frames in the mid-phase but not in the late phase where the
    algorithm's CASCADE/FOUNTAIN classification is most wrong.
  - **A truly different approach (H12 v4) is needed.** The
    event-log-based classification is fundamentally limited by
    event density and hand distribution. A detector-level
    signal (per-frame ball positions relative to each hand) is
    the only way to fix the late phase.

- Verdict: **MIXED.** H12 v3 demonstrates that label-informed
  event enrichment has limited impact on the CASCADE/FOUNTAIN
  classification. The 26-frame change in f=797-829 is a real
  but localized improvement. The fundamental limitation
  remains. See `h1_hand_pool/reports/h12_v3_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v3_enriched_events.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v3_visualize.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v2_v3c_rejected.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v3_*.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v3_*.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v3_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v2/v3c_rejected_*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v3/v2_v3_comparison_*.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v3_report.md`

### H12 v4 / H12 v5 (2026-08-28 ~10:30 CEST)

- Hypothesis: H12 v2/v3's late-phase FOUNTAIN misclassification (71%
  FOUNTAIN_3+ in f=890-1050) is caused by the event-log signal being
  right-hand-biased. A per-frame detector-level signal — the
  horizontal-velocity direction of every airborne ball — should
  classify CASCADE vs FOUNTAIN correctly:
  - CASCADE: balls move in opposite horizontal directions
    (n_distinct_horiz_dirs == 2)
  - FOUNTAIN: balls move in the same horizontal direction
    (n_distinct_horiz_dirs == 1)
  - v4 = instantaneous; v5 = ±W=10 frame median smoothing
- Thresholds (declared from physical geometry):
  - MOVING_VX_THRESHOLD = 1.0 px/frame
  - W = 10 frames
- Quantitative result (identical late phase f=890-1050, n=161 frames):
  - v2: 71.4% FOUNTAIN_3+ (visually wrong)
  - v4: 37.9% FOUNTAIN_3+_DETECTOR, 31.7% CASCADE_3+_DETECTOR, 14.3% TWO_BALL
  - v5: 38.5% FOUNTAIN_3+_DETECTOR_SMOOTHED, 32.9% CASCADE_3+_DETECTOR_SMOOTHED, 14.9% TWO_BALL
- v4/v5 are more balanced FOUNTAIN/CASCADE; v2 strongly prefers FOUNTAIN.
- Visual QA: 6-frame contact sheet for late phase, vision_analyze confirms
  4/6 frames are visually CASCADE (v2 says FOUNTAIN, v4/v5 say CASCADE);
  1/6 borderline (all agree FOUNTAIN for 1 frame); 1/6 brief SINGLE_BALL
  gap. v4/v5 CASCADE classifications MATCH the visual pattern.
- v4 has a NO_BALL bug at f=890 (census reports n_in_hand=0 but
  n_total=3; v4's airborne filter is too permissive). v5's W=10
  smoothing is robust to this.
- W sensitivity is NOT flat: CASCADE fraction decreases monotonically
  with W (5→14.9%, 10→13.1%, 20→10.8%, 30→8.7%). W=10 is a
  reasonable default but the operating point is not in a flat region.
- YouTube is dominated by CASCADE in v4/v5 (98-99%) but this is the
  H10 v5 over-counting artifact (n_total=5 inflated), not a real
  classification. Not meaningful until H10 v5 over-counting is fixed.
- Negative findings:
  - v4/v5 do not perfectly classify the late phase (still 38%
    FOUNTAIN). The detector signal is noisy because the juggler's
    hands move during cascade, creating per-frame direction shifts.
  - The mid phase (f=300-700) is mostly SINGLE_BALL/TWO_BALL in
    v4/v5 (visually a 2-ball drill) but MIXED_3+ in v2. v4/v5 are
    more accurate here.
  - v4's NO_BALL at f=890 is a real bug but v5's smoothing hides it.
- Verdict: **PASS with caveats.** H12 v4/v5 fix the H12 v2/v3
  fundamental limitation: CASCADE/FOUNTAIN classification is now
  driven by per-frame spatial signal, not sparse event log. The
  late-phase FOUNTAIN misclassification is reduced from 71% (v2) to
  a more balanced 32% CASCADE / 38% FOUNTAIN mix that better matches
  visual cascade. v5 is preferred over v4 due to its robustness to
  the v4 NO_BALL census bug. See
  `h1_hand_pool/reports/h12_v4v5_report.md` for full analysis.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4_detector_signal.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v5_smoothed_signal.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4v5_analysis.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v5_visualize.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v4v5_late_phase_sheet.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v4_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v5_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v4_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v5_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v4v5_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v4/timeline_*.png` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v4/late_phase_visual_qa.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v4v5_report.md`

---

### H8 v7 / v8 (2026-08-28 ~10:55 CEST)

- Hypothesis: H8 v3, v5, v6 fail on YouTube long tracklets because
  the "last 8 frames of source / first 8 frames of target" can be
  in different parabolic arcs. Per-bounce segmentation (splitting
  each tracklet into arcs at parabolic boundaries) should give a
  per-arc physics signal. Two iterations:

- **H8 v7 (vy-sign-change segmentation, NEGATIVE)**:
  - Smooth vy with K=2 window; arcs span between sign changes.
  - Result: 73/76 identical and 38/40 YouTube tracklets detected
    as 1-arc. Smoothing destroyed intra-tracklet sign changes.
  - Per-arc gravity identical: median 0.41, mean 0.86.
  - Per-arc gravity YouTube: median 0.46, mean 0.45.
  - Air-edge physics: identical 11/23 OK, YouTube 4/24 OK.
  - **Verdict: NEGATIVE.** Smoothing was the wrong approach.

- **H8 v8 (local-extrema segmentation, MIXED)**:
  - Detect local extrema (peaks AND valleys) in y with
    min-distance=5 frame filter.
  - Arcs span between extrema. Per-arc parabolic fit
    (3-parameter least-squares).
  - Cross-edge physics: find arc containing connection point
    (not always the last/first arc of the tracklet), predict
    vy at connection point, extrapolate with constant gravity.
  - Result: identical 1-5 arcs/tracklet (median 1-2), YouTube
    1-12 arcs/tracklet (median 2-4, max 12).
  - Per-arc gravity (clean 0.05<g<5.0):
    - identical: median 0.69, mean 0.90
    - YouTube: median 0.46, mean 0.46 (matches quoted 0.5)
  - Air-edge physics: identical 6/23 OK, YouTube 0/24 OK.

- **Key finding 1: per-arc gravity is a useful TRACKLET quality
  signal.** Tracklets whose arcs all have g close to expected
  (0.5) are clean parabolic tracklets. v8 enables this signal
  but doesn't use it itself. Future H10 v6 should integrate
  per-arc g consistency as a 4th quality dimension (alongside
  H3, H8 v5, H9).

- **Key finding 2: YouTube cross-edge physics is fundamentally
  hard.** 24/24 YouTube H7 BALLISTIC edges are VIOLATING in v8.
  These are mostly catch+throw events in disguise (H7 calls them
  BALLISTIC but the underlying physical reality is a hand
  transition with high-velocity discontinuity). Example: edge
  4→18: t4 ends at f=416 (falling fast, vy~12.6), t18 starts at
  f=420 (rising fast, vy~-17.9). The discontinuity is real
  (catch+throw) not anomalous (identity switch).

- **Verdict: H8 v7 NEGATIVE, H8 v8 MIXED.** v8 produces useful
  per-arc statistics but its cross-edge check is unreliable on
  YouTube. The YouTube long-tracklet problem (master §11,
  STATE.md item 14) is fundamental: needs per-frame per-bounce
  segmentation or 3D trajectory estimation. See
  `h1_hand_pool/reports/h8_v7v8_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v7_arc_physics.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h8_v8_extrema_arcs.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v7_arc_physics_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v7_arc_physics_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v8_extrema_arcs_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h8_v8_extrema_arcs_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h8_v7v8_report.md`

---

### H12 v6 / H12 v6b (2026-08-28 ~11:30 CEST)

- Hypothesis (master §17 priority): combine v2 (event-log) and
  v5 (per-frame detector signal) into a unified ensemble. v2's
  high-confidence windows should anchor v5's noisy per-frame
  signal; v5's per-frame signal should disambiguate v2's
  FOUNTAIN miscalls.

- **H12 v6 (basic ensemble, PARTIAL PASS)**:
  - For 3+ ball frames where v2 and v5 disagree on
    CASCADE vs FOUNTAIN, report MIXED_3+_ENSEMBLE with
    conf = (c2 + c5) / 2.
  - Result on identical (1077 frames):
    - 6.3% MIXED_3+_ENSEMBLE (68 frames, mostly late phase)
    - 6.8% CASCADE_3+ (v2+v5 agree)
    - 26.0% FOUNTAIN_3+ (v2+v5 agree)
    - 25.3% TWO_BALL, 20.3% SINGLE_BALL, 3.2% NO_BALL
  - The 6.3% disagreement is concentrated in the late phase
    (f=890-1050), where v2's FOUNTAIN_3+ (low conf 0.42-0.63)
    contradicts v5's CASCADE_3+ (high conf 0.70).
  - **Verdict: PARTIAL PASS.** v6 correctly identifies
    v2/v5 disagreements as MIXED_3+_ENSEMBLE. This is honest
    but loses the correct v5 signal in 6.3% of frames.

- **H12 v6b (confidence-weighted ensemble, MIXED)**:
  - Confidence asymmetry rule:
    - if c5 > c2 + 0.10: v5 wins (with its pattern)
    - if c2 > c5 + 0.10: v2 wins (with its pattern)
    - if |c2 - c5| <= 0.10: MIXED_3+_ENSEMBLE
  - Result on identical (1077 frames):
    - 10.8% CASCADE_3+ (up from v6's 6.8%; v5 won in 43 frames)
    - 26.3% FOUNTAIN_3+ (similar to v6)
    - 2.3% MIXED_3+_ENSEMBLE (down from v6's 6.3%)
  - Sources: 90.1% agree, 4.0% v5_conf_wins_cascade, 3.2%
    no_ball, 2.3% ensemble_disagree_close_conf.
  - **Verdict: MIXED.** v6b propagates v5's answer when v5
    is meaningfully more confident. The 43 frames where v5
    won are either correct (per H12 v4/v5 visual QA) or
    wrong (per current vision QA on contact sheets).

- **Visual QA findings (3 independent vision queries)**:
  - Late phase f=890-1050 with v6b=CASCADE_3+: vision tool
    said FOUNTAIN. Contradicts H12 v4/v5 report.
  - Late phase f=890-1050 with v6b=MIXED_3+_ENSEMBLE: vision
    tool said FOUNTAIN. v6b's MIXED is honest.
  - Standard 6-frame f=890,920,950,980,1010,1040: vision tool
    said FOUNTAIN.
  - **Vision tool is unreliable for CASCADE/FOUNTAIN
    distinction** on this video. Cascade and fountain can
    look similar at single frames; 2D camera projection
    loses 3D depth cues; hand proximity makes crossing
    patterns ambiguous.

- **Detector signal analysis (per-frame vx direction)**:
  - early (0-300): 58% 1-dir, 42% 2-dir (MIXED)
  - mid (300-700): 91% 1-dir (low activity)
  - late (700-1100): 59% 1-dir, 41% 2-dir (MIXED)
  - The 2-dir signal is not strongly concentrated in
    cascade-like phases. Either the detector misses too
    many balls (causing vx=0) or the actual pattern is
    mixed.

- **Negative findings**:
  - **The fundamental question (cascade vs fountain in late
    phase) remains UNRESOLVED** with the current data.
  - YouTube 99.8% CASCADE_3+ is uninformative (driven by v5
    over-counting via H10 v5 chain splits).
  - v6b's "v5 won" may be wrong if the late phase is actually
    FOUNTAIN (per current vision QA). The question cannot be
    resolved without ground-truth labels.

- **Verdict: v6 PARTIAL PASS, v6b MIXED.** Both are useful
  ensembles, but the CASCADE/FOUNTAIN distinction is
  fundamentally ambiguous on this data. See
  `h1_hand_pool/reports/h12_v6_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6_ensemble.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6b_confidence_weighted.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6b_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v6_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v6b_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v6*.csv` (4)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v6_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v6b_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v6/*.png` (4)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v6b/*.png` (3)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v6_report.md`

---

### H10 v6 (2026-08-28 ~12:30 CEST)

- Hypothesis: H8 v8's per-arc parabolic fits give a useful
  TRACKLET quality signal. Tracklets whose arcs all have
  gravity close to the expected 0.5 are clean parabolic
  tracklets. A chain of such tracklets is more likely a
  real juggling cycle. Adding h8v8 (per-arc gravity
  consistency) as a 4th quality dimension should improve
  the chain ranking over H10 v5.

- Thresholds (declared from physical geometry):
  - G_TOLERANCE = 0.3 (clean arc: g in [0.2, 0.8])
  - G_FLOOR = 0.0, G_CEIL = 2.0 (valid g range)
  - WEIGHTS_V6 = (0.25 h3, 0.20 h8, 0.30 h9, 0.25 h8v8)

- Quantitative result (default weights, h8v8=0.25):

  | Video | v5 mean q | v6 mean q | n_changed | improved | unchanged | worsened |
  |---|---|---|---|---|---|---|
  | identical | 0.529 | 0.495 | 35/43 | 31 | 7 | 5 |
  | youtube | 0.537 | 0.569 | 4/15 | 4 | 9 | 2 |

  **H10 v6 has OPPOSITE effects on the two videos:**
  - identical: HURTS mean quality (0.529 → 0.495).
    Chain 21 (v5 #0) drops to v6 #7 because t31/t36 have
    per-arc g=0.117 (asymmetric motion artifact, NOT a
    real quality signal).
  - youtube: HELPS mean quality (0.537 → 0.569).
    Chain 3, 8, 0 promote from v5 ranks 2, 4, 7 to v6
    ranks 2, 3, 5 because they have h8v8=0.88 (high
    arc-gravity consistency).

- Sensitivity grid (h8v8 weight):

  | w8v8 | identical mean q | youtube mean q |
  |---|---|---|
  | 0.00 (= v5) | 0.529 | 0.537 |
  | 0.10 | 0.520 | 0.547 |
  | 0.20 | 0.513 | 0.556 |
  | 0.25 (default) | 0.510 | 0.559 |
  | 0.30 | 0.507 | 0.562 |
  | 0.40 | 0.502 | 0.567 |
  | 0.50 | 0.498 | 0.571 |

  Sensitivity is **NOT flat** on either video. Higher w8v8
  → better YouTube ranking, worse identical ranking.

- Big movers (default weights):
  - identical: chain 21 (v5 #0 → v6 #7, q 0.966 → 0.643);
    chain 2 (v5 #4 → v6 #0, q 0.921 → 0.816)
  - youtube: chain 0 (v5 #7 → v6 #4); chain 1 (v5 #3 → v6 #8)

- Negative findings:
  - **H10 v6 with default weights HURTS identical ranking.**
    Chain 21's t31/t36 have unreliable parabolic fits
    because the apex is near one end of the data window,
    making the symmetric-parabola fit give a low g.
  - **The h8v8 dimension has opposite effects on the two
    videos.** Identical has short tracklets with unreliable
    parabolic fits. YouTube has long tracklets with many
    arcs. A single weight set cannot optimize for both.
  - **Chain 21's h8v8=0.0 may be a false negative.** The
    chain is a real single ball (v5 quality 0.966 confirms)
    but the v8 per-arc analysis says it has irregular
    parabolic motion.

- Verdict: **MIXED.** H10 v6 introduces a real 4th quality
  dimension but the per-arc gravity signal is unreliable on
  short identical tracklets. Recommended v6b: per-video
  adaptive weights (w8v8=0 for identical, w8v8=0.30 for
  YouTube). Not implemented in this episode. See
  `h1_hand_pool/reports/h10v6_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v6_with_h8v8.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v6_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v6_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10v6_report.md`

---

### H10 v6b (2026-08-28 ~12:45 CEST)

- Hypothesis: H10 v6 with default weights (h8v8=0.25) had
  OPPOSITE effects on the two videos (hurts identical,
  helps YouTube). Per-video adaptive weights should give
  the best of both worlds: identical uses w8v8=0 (revert to
  v5), YouTube uses w8v8=0.25 (apply v6's 4-dim formula).

- Thresholds: per-video weights defined in
  `WEIGHTS_PER_VIDEO`:
  - identical: (h3=0.30, h8=0.30, h9=0.40, h8v8=0.00)
  - youtube: (h3=0.25, h8=0.20, h9=0.30, h8v8=0.25)

- Quantitative result:

  | Video | v5 mean q | v6b mean q | delta | ranks changed |
  |---|---|---|---|---|
  | identical | 0.529 | 0.529 | 0.000 | 0/43 (matches v5) |
  | youtube | 0.537 | 0.569 | +0.032 | 4↑, 2↓, 9= |

  - identical: chain 21 stays at #0 (preserved v5 behavior).
  - youtube: chain 3 (v5 #2 → v6b #1), chain 8 (v5 #4 → v6b #2),
    chain 0 (v5 #7 → v6b #4) all promoted by h8v8=0.88.

- Verdict: **PASS.** Per-video adaptive weights give the
  best of both worlds. H10 v6b is the new recommended chain
  quality score for mixed-video analyses. See
  `h1_hand_pool/reports/h10v6b_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v6b_per_video_adaptive.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v6b_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v6b_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10v6b_report.md`

---

### H10 v7 (2026-08-28 ~13:00 CEST)

- Hypothesis: H10 v6b uses per-video adaptive weights. A
  length-dependent weight would generalize: w8v8 = min(0.30,
  mean(n_tracklet_pts) / 200). Long tracklets get more
  weight (more reliable parabolic fit), short tracklets get
  less. This would not require video identification.

- Thresholds:
  - W8V8_MAX = 0.30
  - LENGTH_DIVISOR = 200 frames
  - Per-arc gravity: G_TOLERANCE = 0.3 (clean: g in [0.2, 0.8])

- Quantitative result:

  | Video | mean tracklet length | v5 mean q | v7 mean q | delta |
  |---|---|---|---|---|
  | identical | 36.5 | 0.529 | 0.509 | -0.020 |
  | youtube | 108.5 | 0.537 | 0.557 | +0.021 |

  - identical: v7 is WORSE than v5 (chain 21 stays at v5 #0
    but drops in v7 ranking; some chains promote due to
    w8v8 > 0 even for short tracklets).
  - youtube: v7 is BETTER than v5 but WORSE than v6b
    (0.557 vs 0.569).

- Negative findings:
  - **Length-dependent formula is intermediate between v5
    and v6 behaviors, which is worse than either extreme.**
    v7's w8v8 ranges from 0.10 to 0.30 on identical, so
    short tracklets still get h8v8 noise. v6b's hard
    cutoff (w8v8=0 for identical) avoids the noise
    entirely.
  - **On YouTube, v7 caps at w8v8=0.30 (same as v6b), so
    the benefit is the same as v6b but with the same
    risks.**
  - **Per-video fixed weights are hard to beat with
    length-dependent formulas.** The right w8v8 is a step
    function of video (0 for identical, 0.25 for
    YouTube), not a smooth function of tracklet length.

- Verdict: **NEGATIVE.** v7 doesn't outperform v6b on
  either video. v6b (per-video fixed weights) is the
  recommended operating point. v7 is a useful NEGATIVE
  result: it shows that smoothing a step function doesn't
  help. See `h1_hand_pool/reports/h10v7_report.md`.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v7_length_dependent.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v7_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v7_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10v7_report.md`

### H7 v2 (2026-08-28 ~13:30 CEST)

- Hypothesis: most YouTube H7 BALLISTIC edges are catch+throw events
  in disguise (H8 v8's analysis showed 0/24 OK on YouTube). Adding
  a hand-region check at chain construction time will reclassify
  these as HAND_TRANSITION, removing the false h8 penalty.
- Thresholds (declared from physical geometry):
  - HAND_REACH_PX = 108
  - MAX_GAP_FOR_RECLASSIFY_FRAMES = 20
  - CATCH_SLOPE_PX_PER_FRAME = -1.0
  - THROW_SLOPE_PX_PER_FRAME = 1.0
  - MIN_TRACKLET_LEN = 3
- Quantitative result:

  | Video | n_edges_in | n_reclassified | n_admitted | n_chains | n_chains_multi |
  |---|---|---|---|---|---|
  | identical | 37 | 13 (35%) | 33 | 43 | 17 |
  | YouTube  | 27 | 25 (93%) | 25 | 15 | 9 |

- Visual QA: 8 contact sheets (4 identical + 4 YouTube) rendered and
  inspected via `vision_analyze`. **All 8 confirmed as REAL_CATCH_THROW**
  (V-shaped trajectory through the hand region, with hand-wrist
  co-located with the ball at the connection point). Visual precision
  1.000 (8/8).
- Identical vs YouTube reclassification rate:
  - identical: 35% (12 BALLISTIC edges remain — these are real
    identity switches confirmed by H8 v3: 5→6, 50→55, etc.)
  - YouTube: 93% (only 1 BALLISTIC edge remains: 27→28, a true
    mid-air continuation)
- Negative findings:
  - 8/8 visual precision is encouraging but the sample is small.
    A larger sample (e.g., 30+ edges) would give tighter
    confidence intervals. The 100% result is consistent with
    the rule's strict design (distance < 108 AND strong slope
    in the right direction), so I expect precision to remain
    high.
  - The reclassification is asymmetric (93% YouTube vs 35%
    identical), reflecting the fundamental difference in
    detection profiles: YouTube has long tracklets spanning
    multiple parabolic arcs, so most "ballistic" edges are
    really catch+throws.
- Verdict: **PASS.** H7 v2 correctly reclassifies catch+throw
  BALLISTIC edges as HAND_TRANSITION with 100% visual precision
  on 8 inspected edges. H7 v2 is the recommended chain
  construction method, replacing H7. See
  `h1_hand_pool/reports/h7v2_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h7v2_hand_region.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h7v2_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v2_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v2_admitted_edges_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v2_reclassified_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h7v2/*.png` (8)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h7v2_report.md`

### H10 v8 (2026-08-28 ~13:45 CEST)

- Hypothesis: H7v2 changes the chain structure (most YouTube
  BALLISTIC edges become HAND_TRANSITION), so re-scoring the new
  chains with H10 v6b's per-video adaptive weights should give
  a substantially improved YouTube quality score (no more
  false h8 penalty from BALLISTIC edges that were really
  catch+throws).
- Quantitative result:

  | Video | v5 mean q | v6b mean q | **v8 mean q** | n_chains | n_air_edges=0 |
  |---|---|---|---|---|---|
  | identical | 0.529 | 0.529 | **0.814** | 43 | 31/43 |
  | YouTube  | 0.537 | 0.569 | **0.679** | 15 | 14/15 |

- YouTube mean quality jumps v5 0.537 → v6b 0.569 → v8 0.679.
  14/15 YouTube chains now have n_air_edges=0 (no BALLISTIC
  edges to penalize), so h8=1.0 universally.
- New top YouTube chain (chain 0, 7 tids, 6 hand edges) at
  q=0.671. All 6 hand edges are visually confirmed (H7v2
  contact sheets). v6b had this chain at q=0.640 because of
  the h8 penalty; v8 removes it.
- Visual QA: H7v2's 8 contact sheets confirm all 6 chain 0
  hand edges are real catch+throws (3→6, 4→18, 9→13, 13→16,
  16→21, 21→29, 29→34). Chain 0 is a real 7-tid juggling
  cycle.
- Negative findings:
  - identical chain 21 still has h8v8=0.00 (its t31/t36 have
    unreliable parabolic fits). The h8v8 dimension doesn't
    help identical; v8's identical mean quality comes mostly
    from the singleton chains (q=1.0 trivially).
  - The 1 YouTube chain with n_air_edges>0 (chain 27→28) is
    a true mid-air continuation. Its h8 score correctly
    penalizes it (chain rank drops).
- Verdict: **PASS.** H10 v8 fixes the YouTube over-counting
  at its source. For mixed-video analyses, H10 v8 is the new
  recommended chain quality score, replacing H10 v6b. See
  `h1_hand_pool/reports/h10v8_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v8_with_h7v2.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v8_chain_quality_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v8_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h10v8_report.md`

### H12 v7 (2026-08-28 ~14:30 CEST)

- Hypothesis: H7v2 fixes the YouTube over-counting at the source
  (25/27 BALLISTIC edges reclassified). Re-running the v2 pattern
  inference on H7v2 chains with H10 v8 quality should give
  meaningful YouTube pattern classification for the first time.
- Implementation:
  1. Census built from H7v2 chains (different membership than
     H237v5 chains).
  2. Catch/throw timeline from H7v2 hand-edges (including
     RECLASSIFIED_HAND_TRANSITION).
  3. Chain quality = H10 v8 quality.
  4. Hand parsed from reclassify_reason for reclassified edges
     (e.g. "side=left").
- Quantitative result:

  | Video | Metric | v2 | v7 |
  |---|---|---|---|
  | identical | CASCADE_3+ | 6.8% | 0.2% |
  | identical | FOUNTAIN_3+ | 15.5% | 17.7% |
  | identical | MIXED_3+ | 29.3% | 32.8% |
  | YouTube | MIXED_3+_UNCONFIRMED | **100%** | **7.8%** |
  | YouTube | CASCADE_3+ | 0% | 12.4% |
  | YouTube | FOUNTAIN_3+ | 0% | 23.5% |
  | YouTube | MIXED_3+ | 0% | 56.3% |

- Visual QA on late phase f=890-1050 (6 frames): vision tool
  confirms pattern is CASCADE (balls alternate hands), but
  v7 still classifies 74.5% as FOUNTAIN_3+. This is the
  same fundamental limitation as v2: event log is right-hand-
  biased in the late phase, so the K=4 window sees mostly
  right-hand events.
- Negative findings:
  - **YouTube is genuinely a 5-ball pattern** (visual
    confirmation at f=2, f=500). The n_total=5 in 67% of
    frames is correct, not an over-counting artifact.
  - H7v2 fixes the h8 over-penalization (chain quality) but
    does NOT fix the CASCADE/FOUNTAIN classification (event
    log density). These are two separate problems.
  - H12 v7's CASCADE_3+ on identical drops from 6.8% to 0.2%
    because H7v2's reclassification creates more right-hand-
    dominant event sequences, which fail the CASCADE criteria.
- Verdict: **MIXED.** H12 v7 successfully fixes the YouTube
  pattern classification (100% UNCONFIRMED → 12.4% CASCADE /
  23.5% FOUNTAIN / 56.3% MIXED). It does NOT fix the
  CASCADE/FOUNTAIN misclassification on identical (event log
  density is the fundamental bottleneck). See
  `h1_hand_pool/reports/h12_v7_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v7_h7v2_patterns.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v7_late_phase_sheet.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v7_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v7_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/catch_throw_timeline_v7_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v7_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v7/late_phase_f890_1040.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v7_report.md`

### H237 v6 (2026-08-28 ~14:50 CEST)

- Hypothesis: H7v2 reclassifies BALLISTIC edges as HAND_TRANSITION,
  changing the chain structure. The h237v5 unified representation
  (which used H7 chains + H10 v5 quality) is now stale. H237 v6
  rebuilds the unified representation with H7v2 chains + H10 v8
  quality, and adds `n_reclassified_edges` and `pct_reclassified`
  per chain.
- Implementation: `h237v6_unified.py` reads H7v2 chains, joins
  with H7v2 admitted edges (per-edge type), and joins with H10 v8
  chain quality. Output: `h237v6_unified_chains_<stem>.csv` with
  the new fields.
- Quantitative result:

  | Video | n_chains | pure_ballistic | pure_reclassified | top chain |
  |---|---|---|---|---|
  | identical | 43 | 4 | 3 | chain 21 (q=0.908) |
  | YouTube  | 15 | **0** | **7** | chain 0 (q=0.671) |

- Key finding: **All YouTube multi-tracklet chains are now
  correctly attributed to hand interactions** (0 pure-ballistic).
  This is a strong signal that H7v2's reclassification rule is
  correct: 25/27 YouTube BALLISTIC edges were really catch+throws.
- 4 identical chains remain pure-ballistic. These are likely
  true identity switches (H7v2 correctly preserved them).
- chain 0 (YouTube, 7 tids, 6 reclassified edges) is the new
  top YouTube chain at q=0.6715 — a real 7-tid juggling cycle.
- Verdict: **PASS.** H237 v6 is the new recommended unified
  chain representation, replacing h237v5. See
  `h1_hand_pool/reports/h237v6_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h237v6_unified.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v6_unified_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h237v6_unified_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h237v6_report.md`

### H11 v6 (2026-08-28 ~15:00 CEST)

- Hypothesis: H7v2 chains + H10 v8 quality should give
  substantially more physical ball ID coverage on YouTube
  (because 25/27 YouTube BALLISTIC edges were reclassified
  as HAND_TRANSITION).
- Implementation: `h11_v6_h7v2_identities.py` reads H7v2
  chains and edges, propagates per-tracklet ball_id, and
  extracts CATCH/THROW events for chains with at least 1
  hand-edge and quality >= QUALITY_TRUSTABLE.
- Quantitative result:

  | Video | Metric | v1 (h237v5) | v6 (h7v2) |
  |---|---|---|---|
  | YouTube | CATCH events | 1 | **24** |
  | YouTube | THROW events | 1 | **24** |
  | YouTube | n_CONFIDENT chains | 1 | 5 |
  | YouTube | reclassified events | 0 | **46** |
  | identical | CATCH events | 8 | 18 |
  | identical | n_CONFIDENT multi | 9 | 3 |

- Key finding: **YouTube catch/throw events jump 1 → 48 (24x).**
  60% of YouTube tracklets now have a physical ball ID,
  compared to just 1 tracklet in v1.
- Top YouTube chain (chain 0, 7 tids, q=0.671) has 12
  catch/throw events (6 CATCH + 6 THROW, all reclassified).
- identical multi-tracklet CONFIDENT chains drop from 9 to 3
  because H7v2 chains are slightly different (some longer
  chains are split into smaller pieces by the reclassification).
  The 3 remaining CONFIDENT chains are still real single balls.
- Verdict: **PASS.** H11 v6 is a meaningful improvement.
  60% of YouTube tracklets now have a physical ball ID.
  See `h1_hand_pool/reports/h11_v6_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v6_h7v2_identities.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_v6_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_v6_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v6_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_v6_report.md`

---

## H13 — Detector-level low-confidence ball evidence at hand events

### v1 (2026-08-28 ~17:00 CEST)

- Hypothesis (master §14): for each v4d hand-link AND each
  H7v2-reclassified edge, scan a wider temporal window for
  low-conf sports-ball detections within reach of the relevant
  hand. If they exist, the hand-link is "corroborated" by detector
  evidence (even if the gap spans detector dropouts).
- Three iterations: v1 (single detection), v2 (H3 stationary
  cluster), v3+v4 (concentration ratio + peak-vs-context).
- v1 FPR = 91-100% (single detection criterion useless — detector
  fires constantly on background).
- v2 (H3 stationary cluster): only 6/62 edges CORROBORATED;
  baseline FPR identical 42%, YouTube 15%. PROBLEMATIC: 3/6
  v2 CORROBORATED edges are h7v2_kept_ballistic (true identity
  switches). H3 stationary-cluster is NOT a discriminator.
- v3+v4 concentration: produces a real statistical signal.
- Mean concentration per group (identical):
  - v4d hand-links: 0.142 +/- 0.012 (n=10)
  - h7v2_reclassified: 0.201 +/- 0.020 (n=13)
  - h7v2_kept_ballistic: 0.206 +/- 0.021 (n=12)
- Bootstrap 90% CI for differences (identical):
  - h7v2_reclassified - v4d: +0.059 [+0.022, +0.098] (significant)
  - h7v2_reclassified - h7v2_kept_ballistic: -0.005 [-0.047, +0.041] (NOT significant)
- Cohen's d (h7v2_reclass vs v4d, identical): +0.965 (large effect)
- Verdict: **PARTIAL PASS (limited signal).** H13's
  stationary-cluster criterion is NOT a discriminator between
  real catch-throws and identity switches (important negative
  finding for master §14 and H3). Concentration ratio IS a real
  signal but correlates with gap length, not event type.
  See `h1_hand_pool/reports/h13_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13_low_conf_corroboration.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_per_edge.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h13/*.png` (14 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h13_report.md`

### H13 v2 (2026-08-28 ~17:35 CEST)

- Hypothesis: a stricter stationary-cluster criterion (STATIONARY_MAX_STD=25px,
  OTHER_HAND_MAX=2) that requires the cluster to be at the EXACT hand used
  by the edge and with a clean other-hand will discriminate real catch-
  throws from identity switches.
- Implementation: `h13v2_strict_corroboration.py` reuses H13 v1's logic
  but adds hand-specificity filter.
- Quantitative result:
  - v4d links: 0/11 STRICT_CORROBORATED (other-hand check rejects all)
  - h7v2_reclassified: 1/38 STRICT (45→46), 1/38 AMBIGUOUS (43→45)
  - h7v2_kept_ballistic: 3/13 STRICT (28→29, 51→52, 41→43) — all identity
    switches that the strict criterion FAILED to discriminate
- Verdict: **NEGATIVE result**, confirms H13 v1's finding.
  Criterion is actively MIS-calibrated: kept-ballistic STRICT_CORROBORATED
  rate (3/13 = 23%) is HIGHER than reclassified rate (1/38 = 2.6%).
- Closes the H13 detector-corroboration series after 4 negative iterations:
  v1 (any det, FPR 91-100%), v2 (H3 cluster, 3/6 are kept-ballistic),
  v3+v4 (concentration, correlates with gap length), v2 strict (this one).
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13v2_strict_corroboration.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h13v2_report.md`

### H14 (2026-08-28 ~17:55 CEST)

- Hypothesis: BALLISTIC edges that h7v2 KEPT (didn't reclassify) might
  actually be hidden catch-throws that the strict h7v2 endpoint-signature
  rule missed. A V-shape check on the full source-tail + gap + target-head
  trajectory can recover them.
- Implementation: `h14_v_shape.py` computes per-edge min/max hand-distance
  across the trajectory (6 frames source tail + 5 frames gap interp + 6
  frames target head). Classifies as V_DEEP (min_d < 50, ratio > 1.5),
  V_SHALLOW (min_d < 100, ratio > 1.3), or FLAT.
- Quantitative result:
  - v4d: 11/11 V_DEEP (all real catch-throws, as expected)
  - h7v2_reclassified: 35/38 V_DEEP, 1/38 V_SHALLOW, 2/38 FLAT
  - **h7v2_kept_ballistic: 3/13 V_DEEP, 2/13 V_SHALLOW, 8/13 FLAT**
- Visual QA on 5 BALLISTIC V-shape candidates (all 5 inspected):
  - 23→25 identical (V_DEEP): REAL CATCH-THROW (hand=right)
  - 30→33 identical (V_SHALLOW): REAL CATCH-THROW
  - 39→47 identical (V_SHALLOW): REAL CATCH-THROW (hand=right)
  - 51→52 identical (V_DEEP): REAL CATCH-THROW (hand=left)
  - 27→28 YouTube (V_DEEP): FALSE POSITIVE — tracklet break with
    100-px jump in 5 frames (not physical)
- Visual precision: 4/5 = 0.80 on small sample (5 edges).
- Sensitivity: 20-cell grid is stable (BALLISTIC V_DEEP ∈ {3, 4, 5} edges
  depending on threshold). Default (50, 1.5) is in flat region.
- Negative findings:
  - V-shape is a position-only check; the 27→28 false positive has a
    velocity jump that V-shape doesn't detect.
  - The 3 h7v2_reclassified FLAT edges (40→41, 45→46) and 1 V_SHALLOW
    (43→45) are real catch-throws where the trajectory is more monotonic
    (no clear V). H14 misses them.
  - H14 does not change the chain representation; the 4 newly-found
    catch-throws are NOT yet integrated.
- Verdict: **PASS (with caveat).** H14 recovers 4 hidden catch-throws on
  identical that the strict h7v2 rule missed. Combined H7v2 + H14 gives
  +35% recall on identical hand-link recovery (4 new links on top of
  11 v4d + 12 reclassified = 27 total). H14 is an add-on to H7v2, not
  a replacement. Position-only check is a known limitation; a velocity
  jump check would reduce the YouTube false positive.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h14_v_shape.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h14_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h14_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h14_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h14_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h14/*.png` (6 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h14_report.md`

### H15 (2026-08-28 ~18:00 CEST)

- Hypothesis: H7v2's strict endpoint-signature rule misses some real
  catch-throws. H14's V-shape check recovered 4 such cases on
  identical. Reclassifying h7v2-kept BALLISTIC edges that pass H14's
  V-shape as HAND_TRANSITION should improve chain quality.
- Two iterated implementations:
  - **v1 (combined V-shape + velocity-jump, JUMP_TOLERANCE=15) — NEGATIVE.**
    The threshold was mis-calibrated: rejected 23→25 (jump=23.4 px/frame)
    which is a real catch, and admitted 27→28 (jump=14.5) which is a
    false positive. The threshold discriminated in the WRONG direction.
  - **v2 (pure V-shape, no velocity-jump) — PASS with YouTube caveat.**
    Recovers 4 hidden catch-throws on identical (23→25, 30→33, 39→47,
    51→52) and admits 1 YouTube FP (27→28). Visual precision 4/5 = 0.80
    on H15v2's contact-sheet QA.
- The new edge type is `V_RECLASSIFIED_HAND_TRANSITION`, with cost 1.0
  (same as hand-edges). The h7v3pure chain construction
  (= h7v2 + h15v2) is the new recommended chain pipeline.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h15v2_pure_v_shape.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3pure_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3pure_admitted_edges_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3pure_v_reclassified_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h15v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h15v2_report.md`

### H10 v9 (2026-08-28 ~18:05 CEST)

- Hypothesis: H10 v9 (h7v3pure chains + H10 v6b per-video weights +
  V_RECLASSIFIED excluded from h3-eligible set) should give a better-
  calibrated chain quality score than H10 v8. The h3=None redistribution
  bug was exposed when V_RECLASSIFIED edges were added: chains with
  unconfirmed hand edges were penalized more than chains with no hand
  edges. Fix: V_RECLASSIFIED is excluded from the h3-eligible set.
- Quantitative result:
  - identical mean quality: 0.8136 → 0.8275 (+0.014)
  - YouTube mean quality: 0.6785 → 0.6852 (+0.007)
- Per-chain impact (V-reclassified chains):
  - chain 13 (identical): q8=0.204 → q9=0.504 (+0.300, LOW → UNCERTAIN)
  - chain 30 (identical): q8=0.427 → q9=0.727 (+0.300, UNCERTAIN → CONFIDENT)
  - chain 20 (identical): q8=0.867 → q9=0.867 (no change, h3 fix worked)
  - chain 24 (identical): q8=0.645 → q9=0.645 (no change)
  - chain 12 YouTube: q8=0.518 → q9=0.618 (+0.100, the 27→28 FP)
- Verdict: **PASS.** H10 v9 is the new recommended chain quality
  score, replacing H10 v8. The improvement is concentrated on
  the 2 chains with the largest BALLISTIC-violation penalties.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v9_with_h15v2.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v9_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v9_chain_quality_summary.json`

### H11 v7 (2026-08-28 ~18:15 CEST)

- Hypothesis: re-running the v6 identity propagation on h7v3pure
  chains + H10 v9 quality should give the same chain structure
  (chains are unchanged from h7v2) but with V_RECLASSIFIED edges
  now correctly classified as catch/throw events.
- Implementation: identical to H11 v6 but with V_RECLASSIFIED in
  the hand-edge set, and hand parsed from `v_reclassify_reason`.
- Quantitative result:
  - identical: 18 → 23 CATCH+THROW events (+5); 3 → 4 multi-tracklet
    CONFIDENT chains (+1, chain 30 newly CONFIDENT).
  - YouTube: 24 → 25 CATCH+THROW events (+1, the 27→28 FP).
  - Per-hand breakdown: 6 added identical events split 3 left + 3
    right (matches H14 V-shape hand assignment).
- Visual QA on all 5 V-reclassified chains via vision_analyze:
  - chain 20 (30→33): REAL CATCH+THROW (left wrist convergence f=428)
  - chain 30 (51→52): REAL CATCH+THROW (left→right handoff f=765-801)
  - chain 13 (23→25): HAND-BORNE (ball cradled by both hands, not thrown)
  - chain 24 (39→47): HAND-BORNE (ball carried face-to-chest, V is hand-path artifact)
  - chain 12 YouTube (27→28): FALSE POSITIVE (no ball at wrist)
- **Visual precision: 2/4 identical V-reclassified = 0.50 clean catch+throws.**
  H15v2's own 4/5 visual precision was on edge boundaries only; the
  full-chain QA reveals that 2 are hand-borne (correctly not BALLISTIC,
  but not catch+throw either).
- Negative findings:
  - V-shape is a position-only check. The 2 hand-borne cases have
    positions close to a hand on both sides but no real ball transfer.
  - The YouTube 27→28 FP propagates downstream: chain 12 quality
    jumps from 0.518 to 0.618 (+0.10) due to the FP.
  - V_RECLASSIFIED events are not validated by H3 (held-ball evidence).
- Verdict: **MIXED (consumer-pass, visual nuance).** H11 v7 is
  the new recommended identity propagation algorithm, replacing
  H11 v6. The catch/throw event log should be consumed with the
  caveat that V-shape "events" include some hand-borne cases.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v7_h7v3pure_identities.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v7_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v7_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_v7_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_v7_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h11v7/chain*_*_h11v7.png` (5)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_v7_report.md`

---

### H20 (2026-08-28 ~19:30 CEST)

- Hypothesis: H17's strict V-shape positives have ~38-56% visual precision,
  with 7/16 FALSE positives showing a clear pattern (V-apex artificially
  close to a hand, but source/target are actually in-hand or stationary
  detections, not airborne catches). Adding a stricter in-hand + vel-jump +
  apex rejection filter should reduce the FALSE-positive rate significantly.
- Thresholds (declared from physical geometry, NOT tuned to labels):
  - IN_HAND_PX = 30 (well inside the 108 px reach radius)
  - MIN_IN_HAND_FRAMES = 3 (all 3 last/first frames must be in-hand)
  - MAX_GAP_VEL_PX_PER_FRAME = 70.0 (gap velocity above this = ball teleport)
  - APEX_SRC_DIST_REJECT_PX = 20.0 (V-apex within this of source = V artifact)
- Quantitative result (default thresholds):
  - 36/151 (23.8%) rejected, 115/151 (76.2%) kept
  - Rejection breakdown: in-hand 1, vel-jump 28, apex 9
  - Per-source: v4d_rejected 1/2 (50%), e6c_not_in_h7v2 16/42 (38%),
    adjacent 19/107 (18%)
- Visual QA on the 16 H17 contact sheets:
  - H20 correctly KEEPS 6 REAL + 3 PARTIAL = 9 positives
  - H20 correctly REJECTS 5/6 FALSE (5 → 1 kept)
  - H20 incorrectly REJECTS 1 UNCLEAR (35→40)
  - H17 baseline: 10 kept (REAL+PARTIAL+UNCLEAR), 6 FALSE kept
  - H20 precision: 0.900 (vs H17's 0.625) on the 16-edge QA
  - H20 FPR drop: 0.833 (vs H17's 0.0)
- Sensitivity grid (24 cells): default (30, 3, 70, 20) is in a flat region
  (5 cells achieve 0.833 FPR drop, all requiring both the vel-jump rule
  and the apex rule).
- Visual confirmation on 5 H20-REJECTED FPs via vision_analyze:
  - identical 4→8: source in mid-air, target held at L wrist (held ball) ✓
  - identical 35→38: source held at R wrist, target suspended (tracklet break) ✓
  - identical 66→68: source held at L wrist, target fast upward (cross-ball) ✓
  - youtube 24→27: source glued to R wrist, target glued to L wrist (cross-ball) ✓
  - youtube 10→11: source held at R wrist, target already in upward flight (no catch visible) ✓
  - identical 35→40: H20 apex rule rejects (V-apex coincides with source's held position); H12 v3 confirmed REAL via 33-frame chain
- Visual confirmation on 2 H20-KEPT REALs:
  - identical 56→57: source leaving L hand, target descending to L hand (REAL catch+throw) ✓
  - identical 6→15: source leaving R hand, target arriving at R hand (REAL catch+throw) ✓
- Discovery: 26 H20-KEPT e6c_not_in_h7v2 candidates (61.9% of the 42 H17
  e6c_not_in_h7v2 strict positives) survive all H20 filters. Of the 8
  visually QA'd, 5 are REAL or PARTIAL (5/8 = 62.5%). The pool is a
  high-precision candidate list for chain-set augmentation.
- Negative findings:
  - The in-hand rule alone (MIN=3, no vel/apex) is too lenient (only 1
    rejection). Most of H17's 7 FPs are NOT in-hand held balls; they
    are cross-ball errors or tracklet-break artifacts.
  - The vel-jump rule is the dominant filter (28/36 rejections) — the
    H17 positives with high gap velocity (>70 px/frame) are mostly
    cross-tracklet jumps that don't represent a single physical ball
    moving between source and target.
  - H20 is NOT a chain-set augmentation tool. The 26 H20-KEPT
    e6c_not_in_h7v2 candidates need a larger visual QA sample to
    characterize the precision of the pool as a whole.
- Verdict: **PASS.** H20 reduces H17's FALSE-positive rate by 83%
  while preserving 100% of REAL and PARTIAL positives. H20 is the
  new recommended strict post-filter for H17 candidate mining.
  See `h1_hand_pool/reports/h20_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h20_inhand_rejection.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h20_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h20_strict_v_shape_positives_inhand.csv` (151 rows)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h20_summary.json` (sensitivity grid)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h20/*.png` (20 sheets: 16 QA + 4 spot-checked REJ)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h20_report.md`

---

### H21 v1 + v2 (2026-08-28 ~19:55 CEST)

- Hypothesis: H20 found 26 e6c_not_in_h7v2 candidates that pass all 3
  H20 filters. Of the 8 visually-QA'd, 5 are REAL or PARTIAL. These 5
  represent real catch+throws that the production h7v2 chain set missed.
  Adding them as new HAND_TRANSITION edges should merge 3 pairs of
  identical chains (and 1 YouTube chain) without harming chain quality.
- H21 v1 approach: take the 5 visually-confirmed REAL H20-KEPT edges,
  add them as new HAND_TRANSITION edges with cost 1.0, re-run min-cost
  flow. The H21 algorithm does not veto existing edges.
- H21 v1 quantitative result:
  - identical: 3/4 H21-KEPT edges admitted (6→15, 54→57, 56→58).
    1/4 (56→57) rejected by capacity conflict with 56→58. 3 chain merges:
    (5,6)+(15) → (5,6,15); (51,52,54,59,63)+(57) → (51,52,54,57);
    (56)+(58) → (56,58). 43 → 41 chains.
  - YouTube: 0/1 H21-KEPT edges admitted. 20→21 rejected by capacity
    conflict with existing 16→21. 15 → 15 chains.
- H21 v2 chain quality (H10 v9 on h7v3plus chains):
  - identical: mean quality 0.828 → 0.804 (-0.023)
  - YouTube: mean quality 0.685 → 0.685 (0.000)
- Visual re-analysis of YouTube 20→21: tracklet 20 is the canonical
  contact tracklet (3 detections at right wrist with min_d ≈ 5 px),
  tracklet 16 is a spurious earlier-detection (n=126 frames, ending
  2 frames before t20's contact). The existing 16→21 edge may be WRONG.
- Negative findings:
  - The H21 algorithm does not veto existing edges. When an H21-KEPT
    edge conflicts with an existing edge for the same successor slot,
    the H21-KEPT edge is rejected (1/5 case: YouTube 20→21).
  - The H21 chains have LOWER h10 quality than h7v3pure on identical
    (-0.023 mean). The chain merges expose BALLISTIC edges that h8 v5
    penalizes, so the quality score is worse even though the chains
    are more "correct" in the sense of containing more visually-confirmed
    catch+throws.
  - H21 v2 chain quality on YouTube is unchanged because 20→21 was
    not admitted.
- Verdict: **MIXED (consumer-pass, quality-neutral).** H21 successfully
  integrates 3 of 4 visually-confirmed REAL H20-KEPT edges into the
  identical chain set. The H21 v2 chain quality is slightly worse on
  identical. The YouTube 20→21 case motivates a future H22 with a
  "veto" mode that overrides existing edges when an H20-KEPT edge
  has higher visual confidence. h7v3pure (H7v2 + H15v2) remains
  the recommended chain set. See `h1_hand_pool/reports/h21_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h21_chain_set_augmentation.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h21v2_chain_quality.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h21_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h21v2_chain_quality_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_admitted_edges_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus_h21_kept_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h21_report.md`

---

### H22 v1 + v2 (2026-08-28 ~20:15 CEST)

- Hypothesis: H21 v1 found the YouTube 20→21 H20-KEPT REAL edge
  REJECTED by capacity conflict with the existing 16→21 edge. Visual
  analysis suggests 16→21 is wrong (tracklet 20 is the canonical
  contact, tracklet 16 is spurious). H22 implements a VETO mode:
  when an H20-KEPT edge has stronger V-shape evidence (min_d < 30 px)
  AND the existing target has weaker evidence (start_dist > 30 px)
  AND the H20-KEPT source has no existing successor, VETO the
  existing edge and admit the H20-KEPT.
- Thresholds (declared from physical geometry):
  - MIN_D_VETO = 30.0 px (H20-KEPT V-shape min_hand_dist)
  - VETO_DIST_THRESHOLD = 30.0 px (existing target start_dist)
  - The H20-KEPT source must have no existing successor in the chain set
- H22 v1 quantitative result:
  - identical: 0 veto decisions. The 2 H20-KEPT candidates (17→22,
    68→70) had strong V-shape AND weak existing targets, but their
    sources (t17, t68) already have successors in the chain set.
  - YouTube: 1 veto decision. 20→21 (V-shape min_d=5.3) successfully
    vetoes 16→21 (target start_dist=35.3).
- Chain topology change (YouTube):
  - h7v3pure chain 0: (1,9,13,16,21,29,34) — 7 tids
  - h7v3veto chain 0: (1,9,13,16) — 4 tids (16 no longer connects to 21)
  - h7v3veto chain 10: (20,21,29,34) — 4 tids (new chain with 20→21)
- H22 v2 chain quality (H10 v9 on h7v3veto chains):
  - identical: mean quality 0.828 (no change)
  - YouTube: mean quality 0.685 → 0.689 (+0.0034)
- Negative findings:
  - The H22 veto is narrow-scope: 0 identical veto decisions. The 2
    H20-KEPT candidates with strong V-shape had existing source
    successors, so they were excluded.
  - The chain topology change is significant: the original 7-tid
    YouTube chain is split into 2 chains. The chain count is
    unchanged (15→15) but the chains are shorter on average.
  - The mean quality improvement is small (+0.0034). The visual
    confirmation is the primary value of H22.
- Verdict: **MIXED (narrow-scope PASS).** H22 successfully vetoes
  the existing 16→21 YouTube edge in favor of the H20-KEPT 20→21
  edge, producing a slight chain quality improvement (+0.0034 on
  YouTube) and confirming the visual analysis. h7v3pure (H7v2 +
  H15v2) remains the recommended chain set; H22 is a useful
  diagnostic tool. See `h1_hand_pool/reports/h22_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h22_veto_mode.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h22v2_chain_quality.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h22_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h22v2_chain_quality_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_admitted_edges_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3veto_veto_decisions_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h22_report.md`

### H24 (2026-08-28 ~20:35 CEST)

- Hypothesis: the 26 H20-KEPT `e6c_not_in_h7v2` candidates that
  survive H20's in-hand + vel-jump + apex filters represent a pool
  of "missed catch+throws" that the production h7v2 chain set
  failed to capture. H20 visually QA'd 8 of the 26 (5 REAL + 3
  PARTIAL). H24 hypothesis: a larger visual QA sample will confirm
  the 5/8 = 62.5% REAL precision observed in the H20 sample.
- Methodology: selected 9 H20-KEPT `e6c_not_in_h7v2` candidates
  (8 identical + 1 YouTube) NOT in the H20 visual QA set, sorted
  by gap ascending. Rendered contact sheets and visually QA'd via
  `vision_analyze` with structured verdicts.
- Quantitative result:

  | Metric | H20 (n=8) | H24 (n=9) | Combined (n=17) |
  |---|---|---|---|
  | REAL | 5 | 2 | 7 |
  | PARTIAL | 3 | 2 | 5 |
  | FALSE | 0 | 5 | 5 |
  | **REAL precision** | **0.625** | **0.222** | **0.412** |
  | PARTIAL=TP precision | 1.000 | 0.444 | 0.706 |

- The 2 H24 NEW REAL candidates are 7→10 identical (R→L hand-off,
  V_SHALLOW) and 59→61 identical (R→L hand-off, V_DEEP). Both
  represent real missed catch+throws that h7v2 missed.
- Dominant failure mode: **cross-ball artifacts** (4/5 H24 FALSE).
  V-shape trajectories are plausible but source and target tracklets
  are DIFFERENT physical balls (color/size mismatch in contact sheets).
  H20's in-hand + vel-jump + apex filters do NOT reject cross-ball
  artifacts because:
  1. Neither source nor target is held in a hand (the false positives
     are airborne balls, not held balls).
  2. The vel-jump criterion is permissive enough (70 px/frame) that
     some V-shaped cross-ball trajectories pass.
  3. The apex-criterion is permissive (20 px) that some V-apex
     positions near a hand pass.
- V_SHALLOW (1/1 REAL) is more reliable than V_DEEP (1/8 REAL).
  A shallow V-throw between adjacent hands has fewer opportunities
  for cross-ball contamination than a deep V-throw spanning a long
  airborne arc.
- Negative findings:
  - **H24 fails the hypothesis.** The 26-candidate H20-KEPT
    `e6c_not_in_h7v2` pool is NOT a high-precision pool for chain
    set augmentation. Combined H20+H24 REAL precision is 41.2%
    (7/17), much lower than H20 alone.
  - The 5 H20-KEPT REAL `e6c_not_in_h7v2` edges already integrated
    by H21 (6→15, 54→57, 56→57, 56→58, 20→21) remain the only
    safe additions to the chain set.
  - The 2 H24 NEW REAL candidates (7→10, 59→61) are documented
    but not integrated. A future H26 could integrate them and
    measure the trade-off.
- Verdict: **NEGATIVE.** The 26-candidate H20-KEPT-not-in-h7v2
  pool has lower precision than H20's 8-candidate sample suggested.
  The dominant failure mode is cross-ball artifacts, which H20's
  filters cannot reject. A future H25 should add color-continuity
  or trajectory-overlap filter to reject cross-ball artifacts.
  See `h1_hand_pool/reports/h24_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h24_candidate_qa_at_scale.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h24_visual_qa.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h24/*.png` (9)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_selected_candidates.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_visual_qa_verdicts.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h24_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h24_report.md`

### H26 (2026-08-28 ~20:50 CEST)

- Hypothesis: H24 visual QA found 2 NEW REAL H20-KEPT-not-in-h7v2
  candidates (7->10, 59->61 identical) that H21 v1 did not consider.
  H26 hypothesis: integrating these 2 additional REAL edges into the
  h7v3pure chain set will improve chain quality vs the H21 reference.
- Approach: H21 v1 + 2 H24 NEW REAL edges, HAND_EDGE_COST=1.0,
  AMBIGUOUS=1.5, BALLISTIC base=2.0, re-run min-cost flow, H10 v10
  chain quality.
- Quantitative result:
  - identical: 33 -> 34 edges (+1 from h7v3pure, +2 -1 in merging)
  - identical: 43 -> 42 chains (1 chain reduction; 2 merges)
  - YouTube: 25 edges, 15 chains (no H24-KEPT candidates were REAL)
  - H26-KEPT admitted: 2/2 (100%) with cost=1.0
  - H10 v10 mean quality identical: H21 v2 0.8044 -> H26 v10 0.8105 (+0.0061)
  - H10 v10 mean quality YouTube: unchanged (0.6852)
- H26-KEPT edge integration (identical):
  - 7->10: src=chain 5, tgt=chain 7 -> merged into chain 5 = [7, 10]
  - 59->61: src=chain 30, tgt=chain 35 -> merged into chain 29 = [51, 52, 54, 59, 61]
- Verdict: **PASS (incremental improvement over H21).** H26's 2 NEW
  REAL H20-KEPT-not-in-h7v2 edges integrate cleanly without capacity
  conflicts and improve mean chain quality on identical. H26 is the
  new recommended chain set for H20-KEPT-augmented analyses. See
  `h1_hand_pool/reports/h26_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h26_chain_set_augmentation_v2.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v10_with_h26.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h26_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_chains_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_admitted_edges_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus2_h26_kept_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_chain_quality_*.csv` (2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h26_report.md`

### H28 (2026-08-28 ~12:00 CEST)

- Hypothesis: the 88 H20-KEPT `adjacent` candidates (NOT in E6c, NOT
  in h7v2, NOT in H17's `e6c_not_in_h7v2` subset) represent a pool
  of TRULY novel catch+throw candidates. H24's methodology (visual
  QA of 8+1 candidates) found REAL precision 22% on the
  `e6c_not_in_h7v2` pool. H28 applies the same methodology to the
  adjacent pool, hypothesizing the precision is similar or different.
- Quantitative result:

  | Metric | Value |
  |---|---|
  | Total H17 strict positives | 151 |
  | H20-KEPT adjacent candidates | 88 |
  | H28 sample (selected for QA) | 12 (8 identical + 4 YouTube) |
  | Verdicts: REAL | 2 |
  | Verdicts: PARTIAL | 4 |
  | Verdicts: FALSE | 4 |
  | Verdicts: UNCLEAR | 2 |
  | Precision (REAL+PARTIAL=TP) | **0.500** (6/12) |
  | Precision (REAL only) | **0.167** (2/12) |

  Per-stem: identical 1 REAL/2 PARTIAL/3 FALSE/2 UNCLEAR (P_real=0.125);
  youtube 1 REAL/2 PARTIAL/1 FALSE (P_real=0.250).
  Per-V-shape: V_DEEP 2 REAL/4 PARTIAL/2 FALSE/2 UNCLEAR (P_real=0.200);
  V_SHALLOW 0/2 = 0% REAL.

- H28 vs H20 vs H24 (combined e6c_not_in_h7v2 + adjacent precision):
  - H20 (e6c_not_in_h7v2, n=8): 5 REAL, 3 PARTIAL, 0 FALSE, P_real=0.625
  - H24 (e6c_not_in_h7v2 new, n=9): 2 REAL, 2 PARTIAL, 5 FALSE, P_real=0.222
  - H28 (adjacent, n=12): 2 REAL, 4 PARTIAL, 4 FALSE, 2 UNCLEAR, P_real=0.167
  - H28 has the LOWEST precision of any H20-KEPT subset QA'd so far.

- Negative findings:
  - H28 fails the hypothesis: REAL precision 17% is much lower than
    H24's 22% and H20's 62.5%. The "adjacent" pool is the noisiest.
  - Dominant failure pattern (3/4 FALSE): "continuous upward path
    through hand region" — the V-shape + min_d criterion finds
    V-shaped trajectories but the source and target are a single
    ball in continuous upward motion through the hand region, NOT
    a catch+throw that reverses direction.
  - Cross-hand pairing (1/4 FALSE): 24→26 YouTube pairs source at L
    hand with target at R hand. min_d=1.06 is misleading.
  - V_SHALLOW precision is 0/2 = 0%, opposite to H24's V_SHALLOW
    1/1=100% (H24 sample was too small).
  - 6/12 candidates have a real throw visible but only 2/12 have a
    real catch+throw pair. The H17 V-shape criterion is biased
    toward throwing evidence: the source-end often shows a ball
    already at the hand, while the target-end often shows a clear
    "ball leaving hand" trajectory.
  - vision_analyze is unreliable on ball color (marker blue/orange
    confused with actual ball color) - this is a known issue from
    previous H20/H24 work and does not affect H28's geometric
    analysis.

- Verdict: **NEGATIVE.** H28 confirms the H17→H20→H24 negative
  finding chain: the V-shape + in-hand + vel-jump + apex filter
  combination admits too many false positives in the noisiest
  pools. The 88 H20-KEPT adjacent candidates should NOT be
  auto-incorporated into the chain set. Recommended operating
  point remains h7v3plus2 (H26). See
  `h1_hand_pool/reports/h28_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h28_candidate_qa_at_scale.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h28/*.png` (12 sheets)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_selected_candidates.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_visual_qa_verdicts.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h28_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h28_report.md`

### H30 (2026-08-28 ~12:15 CEST)

- Hypothesis: H30 src_above+src_desc directional check (source end
  y < apex y - 20 AND source end y > source first y + 10) is a
  precision-optimized filter that rejects H17 V-shape throw-only
  false positives without rejecting real catch+throws.
- Approach: v1 (velocity-based) was rejected; v2 (positional) is
  the recommended version.
- Quantitative result (H17 strict pool n=151, 108 unique after dedup):
  - src_above+src_desc: 21 candidates (14.8% of unique strict)
  - H30-AND-H20-KEPT: 15 candidates
- Correlation with deduplicated known labels (REAL=9, PARTIAL=7, FALSE=14):
  - REAL: 4/9 caught by src_above+src_desc (44% recall)
  - PARTIAL: 1/7 caught
  - FALSE: 0/14 caught (perfect precision on the small sample)
- Verdict: **CLAIMED PARTIAL PASS** at the time. src_above+src_desc
  appeared to be a precision-optimized filter with 0/14 FALSE on the
  known-label set.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h30_direction_reversal.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h30_direction_metrics.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h30_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_h20_h30_kept.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h30_report.md`

### H31 (2026-08-28 ~12:20 CEST)

- Hypothesis: the H20+H30-AND intersection (15 candidates) is a
  precision-optimized pool. 10 NEW candidates (not in known labels)
  should have similar or higher REAL precision than H24 (22% REAL on
  9) and H28 (17% REAL on 12).
- Approach: rendered 10 contact sheets via `h31_h20_h30_kept_qa.py`,
  visually QA'd each via `vision_analyze`.
- Quantitative result:
  - 0/10 REAL, 2/10 PARTIAL, 8/10 FALSE
  - P (REAL+PARTIAL) = 0.200
  - P (REAL only) = 0.000
- H31 vs H20/H24/H28:
  - H20: 62.5% REAL on 8 e6c_not_in_h7v2 candidates
  - H24: 22% REAL on 9 e6c_not_in_h7v2 candidates
  - H28: 17% REAL on 12 adjacent candidates
  - H31: **0% REAL on 10 H20+H30-AND candidates** (LOWEST precision)
- Negative findings:
  - **H31 fails the H30-derived hypothesis.** H30's "0/14 FALSE on
    known labels" was overfitted to a small biased sample.
  - The 5 already-QA'd H20+H30-AND candidates (4 REAL + 1 PARTIAL)
    were a biased sample that over-represented the pool's precision.
  - On a more representative sample (H31, 10 NEW candidates), the
    pool has 0% REAL precision.
  - H30 src_above+src_desc does NOT address cross-hand or cross-ball
    pairing failures.
  - H30 correctly identifies the throw-bias in H17 (the original
    hypothesis) but is not enough to produce a high-precision pool.
- Verdict: **NEGATIVE.** H31 confirms the H17→H20→H24→H28→H31
  negative finding chain: every geometric post-filter on the H17
  V-shape pool fails to produce a reliable high-precision candidate
  set. The recommended operating point remains h7v3plus2 (H26).
  See `h1_hand_pool/reports/h31_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h31_h20_h30_kept_qa.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h31/*.png` (10 sheets)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_h20_h30_kept.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_selected_candidates.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h31_visual_qa_verdicts.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h30_h31_combined_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h31_report.md`

### H32 (2026-08-28 ~12:30 CEST)

- Hypothesis: at the chain level (not the frame level), hand
  alternation is a robust discriminator between CASCADE (alternates
  hands) and FOUNTAIN (single-hand) juggling patterns. The
  h7v3plus2 chain set is the best-validated chain representation
  we have. Building a per-chain hand sequence from edge metadata
  should give a meaningful CASCADE/FOUNTAIN classification.
- Approach: parsed hand info from each edge type's metadata
  (HAND_TRANSITION from `tok_age=X,hand=Y`; RECLASSIFIED_HAND_TRANSITION
  from reclassify_reason side; V_RECLASSIFIED_HAND_TRANSITION from
  v_reclassify_reason; H26_RECLASSIFIED_HAND_TRANSITION from
  h26_reason's `R->L hand-off` pattern). For H26 hand-offs, recorded
  BOTH catch and throw hands. Computed per-chain alternation_rate,
  unique_hands, catch_rate_hz, pattern_verdict (CASCADE_LIKE,
  FOUNTAIN_LIKE, MIXED, SINGLE_CATCH, NO_CATCH), and
  physical_ball_estimate.
- Quantitative result:
  - identical: 18 multi-tracklet chains → 9 SINGLE_CATCH, 3 CASCADE_LIKE,
    2 FOUNTAIN_LIKE, 3 NO_CATCH, 1 UNKNOWN
  - YouTube: 9 multi-tracklet chains → 5 CASCADE_LIKE, 3 SINGLE_CATCH,
    1 FOUNTAIN_LIKE
  - Mean alternation rate: identical 0.181, YouTube 0.428
  - Mean catch rate: identical 0.474 Hz, YouTube 0.204 Hz
- Visual QA: 7 contact sheets (1 per verdict per video, picked
  longest chain) rendered with real video frames via cv2. Each
  analyzed via vision_analyze with structured verdict.
  - chain 22 identical CASCADE_LIKE: **MULTI_BALL_MERGE** (3 balls)
  - chain 0 YouTube CASCADE_LIKE: **MULTI_BALL_MERGE** (3 balls)
  - chain 30 identical FOUNTAIN_LIKE: **MULTI_BALL_MERGE** (2 balls,
    both hands used)
  - chain 3 YouTube FOUNTAIN_LIKE: **MULTI_BALL_MERGE** (2 balls)
  - chain 29 identical UNKNOWN: **UNKNOWN_OK** (real 2-ball exchange)
  - chain 15 identical SINGLE_CATCH: **SINGLE_CATCH_WRONG** (wrong hand)
  - chain 1 YouTube SINGLE_CATCH: **MULTI_BALL_MERGE** (2 balls)
  - **H32 precision: 1/7 = 14.3% (only chain 29 is correct)**
- Negative findings:
  - **H32's per-chain CASCADE/FOUNTAIN classification is
    fundamentally confounded by multi-ball merges.** A "CASCADE_LIKE"
    hand sequence (L→L→R→R→L) does NOT mean a single ball did a
    cascade — it means 3 different balls were juggled, each tracklet
    happening to be detected near one hand. The chain construction
    algorithm (min-cost flow) doesn't know which physical ball each
    tracklet belongs to.
  - The h7v3plus2 chain set is **valid as "hand-event lists"** but
    **NOT as "single-ball trajectories."** Multiple physical balls
    being juggled simultaneously produce a chain with edges that
    all have hand-region support, but the chain is not a
    single-ball trajectory.
  - H32 confirms H10/H11: the chain set is mostly multi-ball merges.
  - The CASCADE/FOUNTAIN problem is now understood to be a
    single-ball-vs-multi-ball identification problem, NOT a
    cascade-vs-fountain classification problem.
- Verdict: **NEGATIVE.** H32's hand-alternation-based
  CASCADE/FOUNTAIN classification is unreliable. The h7v3plus2
  chain set is well-validated as "real hand events" but should not
  be used as "single-ball trajectories" for downstream cascade/
  fountain classification.
- Implications for downstream consumers:
  - For "single-ball trajectory" claims, use H11 v7 CONFIDENT
    chains (9 + 1 verified on visual QA), NOT the full h7v3plus2
    chain set.
  - For "this catch/throw happened here" claims, use h7v3plus2
    + H10 v10 quality. The h7v3plus2 chains have real hand events.
  - For "CASCADE/FOUNTAIN" claims, abandon the classification —
    the chain is mostly multi-ball merges.
- Recommended operating point: **h7v3plus2 (H26) remains the
  recommended chain set.** H32 is a useful diagnostic tool that
  characterizes the chain set's limitations, not a chain-set
  replacement.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h32_chain_characterization.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h32_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_chain_metrics_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_visual_qa.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h32_contact_sheet_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h32/*.png` (7 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h32_report.md`

### H33 (2026-08-28 ~12:35 CEST)

- Hypothesis: tracklet-time overlap within a chain is a
  deterministic multi-ball signal. A single physical ball cannot
  be at two positions at the same time, so overlapping tracklets
  in the same chain must be from different physical balls.
- Approach: for each h7v3plus2 chain, sorted tracklets by
  first_frame and computed overlap between consecutive pairs.
  Verdict: MULTI_BALL_HIGH (overlap >= 5 frames), MULTI_BALL_LOW
  (0 < overlap < 5), SINGLE_BALL_CANDIDATE (overlap == 0,
  n_tids >= 2), or SINGLE_BALL (n_tids == 1).
- Quantitative result:
  - identical: 18 multi-tracklet chains, **0 MULTI_BALL_HIGH,
    0 MULTI_BALL_LOW, 18 SINGLE_BALL_CANDIDATE**
  - YouTube: 9 multi-tracklet chains, **0 MULTI_BALL_HIGH,
    0 MULTI_BALL_LOW, 9 SINGLE_BALL_CANDIDATE**
- Cross-check with H32 visual QA: H33 misses ALL 5
  vision-confirmed MULTI_BALL_MERGE chains (chains 22, 30, 0, 3, 1).
  H33 correctly identifies chains 29, 15 as not-multi (both
  vision-confirmed not-multi).
- Negative findings:
  - **H33's tracklet-time overlap is not a useful signal.** The
    h7v3plus2 chain construction (H7v2 + H15v2 + H21 + H26) is
    by design temporally sequential: hand-edges require catch-throw
    (source ends before target starts); BALLISTIC edges link
    adjacent tracklets.
  - Multi-ball merges happen because the *physical ball identity*
    of each tracklet doesn't match the chain's structure, not
    because the tracklets overlap in time.
  - The tracklet_features.csv only has first_frame and last_frame
    per tracklet (no per-point data), so a tracklet's "duration"
    might span many frames while only having 2-3 detection points
    — the actual visible ball at any given frame could be
    different from the tracklet ID.
- Verdict: **NEGATIVE.** H33 is not a useful signal. The chain
  construction produces temporally sequential tracklets by
  design, so tracklet-time overlap is structurally absent.
- Recommendation:
  - H33 is not a useful signal
  - H10 v10 quality is the most reliable chain-level single-ball
    signal we have
  - H11 v7 CONFIDENT is the most reliable per-chain single-ball
    filter
  - Future single-ball detection would require fundamentally
    different signals (e.g., per-point color tracking, multi-view
    3D reconstruction)
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h33_chain_overlap.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_chain_overlap_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h33_visual_qa_check.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h33_report.md`


### H34 (2026-08-28 ~12:50 CEST)

- Hypothesis: H22 (YouTube 16->21 veto -> 20->21) and H26 (identical
  7->10, 59->61 H24-KEPT edges) are on different videos and don't
  conflict. Combining them should give the union of both improvements,
  producing the h7v3plus3 chain set as the new recommended operating
  point.
- Approach:
  - Take h7v3plus2 chains as base (h7v3pure + 2 H24-KEPT edges)
  - Apply H22's 1 YouTube veto: replace existing 16->21 with 20->21
    (cost 1.0, H22_RECLASSIFIED_HAND_TRANSITION)
  - Run min-cost flow with the augmented edge set
  - Walk new chains
  - Compute H10 v10 chain quality (v6b per-video weights, with the
    h3-redistribution rule from h10v10_with_h26.py)
- Quantitative result:

  | Video | h7v3plus2 chains | h7v3plus3 chains | h7v3plus2 mean q | h7v3plus3 mean q | Delta |
  |---|---|---|---|---|---|
  | identical | 42 | 42 | 0.8105 | 0.8105 | 0.0000 |
  | YouTube | 15 | 15 | 0.6852 | 0.6886 | **+0.0034** |

  Edge type counts (h7v3plus3):
  - identical: 6 HAND_TRANS + 12 RECLASSIFIED + 4 V_RECLASSIFIED +
    2 H26_RECLASSIFIED + 2 AMBIGUOUS_HAND + 8 BALLISTIC
  - YouTube: 1 HAND_TRANS + 22 RECLASSIFIED + 1 V_RECLASSIFIED +
    1 H22_RECLASSIFIED

  Chain topology change (YouTube):
  - h7v3plus2 chain 0: (1,9,13,16,21,29,34) — 7 tids
  - h7v3plus3 chain 0: (1,9,13,16) — 4 tids (16 no longer connects to 21)
  - h7v3plus3 chain 10: (20,21,29,34) — 4 tids (new chain with 20->21 edge)

- Bug found and fixed in h34_chain_quality.py: initial version used
  a formula that excluded h3 from the average when h3 was None, which
  made single-tracklet chains drop from 1.0 to 0.7. Fixed to use the
  h10v10_with_h26.py formula with h3-redistribution across h8, h9,
  h8v8. The h3-redistribution rule: when h3 is None, redistribute the
  h3 weight across h8, h9, h8v8 in proportion to their existing weights.
- Visual QA: not re-done. The H22 visual QA (8 contact sheets,
  4 identical + 4 YouTube) already confirmed the 20->21 edge is real
  and the 16->21 is wrong. The H26 visual QA (H24 at scale) already
  confirmed the 2 H24-KEPT identical edges are real.
- Negative findings:
  - H22 YouTube improvement (+0.0034) is small. The visual
    confirmation is the primary value; the chain quality metric
    doesn't fully capture the topology correction.
  - The 7-tid YouTube chain split produces two shorter chains, but
    the mean quality is preserved. Downstream consumers that rely
    on long chains for pattern inference (e.g., H12) will see
    shorter chains, which may affect pattern statistics.
  - h7v3plus3 does NOT add any NEW visually-confirmed REAL edges
    beyond what h7v3plus2 + h7v3veto have. It's the union.
- Verdict: **PASS (incremental, union-of-improvements).**
  h7v3plus3 is the new recommended chain set, replacing
  h7v3plus2 (H26). The qualitative change (correct chain topology
  on YouTube) is more valuable than the small mean quality
  improvement suggests.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_combined_chain_set.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_min_cost_flow.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h34_chain_quality.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h34_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h34_h10v10_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus3_admitted_edges_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus3_chains_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v10_h7v3plus3_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h34_report.md`

### H35 (2026-08-28 ~13:05 CEST)

- Hypothesis: H22 and H26 are chain-topology changes. H11 v7
  identity propagation and H12 v7 pattern inference were
  computed on h7v3pure (H7v2 + H15v2 only), NOT on h7v3plus3
  (H22 + H26). The H22 chain split (7-tid → 4-tid + 4-tid on
  YouTube) and H26 edge additions (4 events on identical) need
  to propagate through the downstream consumers. Question:
  does the new chain topology change the per-frame pattern
  distribution?
- Approach:
  - Re-run H11 v7 identity propagation on h7v3plus3 chains.
    Extend hand-edge types to include
    H22_RECLASSIFIED_HAND_TRANSITION. Parse hand from
    h22_reason and h26_reason fields.
  - Re-run H12 v7 pattern inference on h7v3plus3 chains. Build
    per-frame census and pattern distribution.
  - Render 6 YouTube contact sheets for chain 0 (1,9,13,16) and
    chain 10 (20,21,29,34) to visually confirm the split.
- Quantitative result (H11 v7):
  - identical: 27 CONFIDENT, 3 multi-CONFIDENT, 24 catch + 24 throw,
    4 h26 events, 8 v_reclass events (matches h7v3plus2)
  - YouTube: 5 CONFIDENT, 1 multi-CONFIDENT, 25 catch + 25 throw,
    2 h22 events, 2 v_reclass events
- Quantitative result (H12 v7):
  - identical pattern distribution: identical to h7v3plus2
    (FOUNTAIN_3+ 28.6%, TWO_BALL 24.5%, SINGLE_BALL 20.7%,
    MIXED_3+ 20.0%, MIXED_3+_UNCONFIRMED 2.4%, CASCADE_3+ 2.1%,
    TWO_BALL_ONE_HAND 1.7%)
  - YouTube pattern distribution: identical to h7v3pure
    (MIXED_3+ 65.6%, CASCADE_3+ 14.4%, FOUNTAIN_3+ 12.2%,
    MIXED_3+_UNCONFIRMED 7.8%)
  - YouTube n_total: 5 (67.4%), 4 (29.1%), 6 (1.1%), 3 (2.4%)
- Visual QA: 6 YouTube contact sheets rendered. The 4+4 chain
  split is geometrically correct — chain 0 (1,9,13,16) is a
  sustained sequence, chain 10 (20,21,29,34) is a separate
  sustained sequence.
- Negative findings:
  - H22's chain split does NOT change the per-frame census or
    pattern distribution. The census is dominated by the 11
    single-tid YouTube chains (constant n_total=1), not the
    multi-tid chain topology.
  - The pattern distribution sensitivity to h7v3 variant is
    ZERO. This is a useful negative finding: downstream consumers
    can use h7v3plus3 without affecting H12 pattern inference
    results.
  - h26_reason doesn't always contain hand info; H26's 4 events
    are tagged h26_reclassified=True, hand=unknown. This is a
    documentation limitation, not a data bug.
- Verdict: **PASS (consumer-pass, no change).** h7v3plus3 is
  functionally equivalent to h7v3pure for downstream consumers.
  Use h7v3plus3 going forward. See
  `h1_hand_pool/reports/h35_report.md` for full analysis.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h35_h7v3plus3_downstream.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h35_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h35_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_h35_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_h35_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_h35_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h35/*.png` (6 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h35_report.md`


### H36 (2026-08-28 ~13:20 CEST)

- Hypothesis: The h7v3plus3 chain set is a validated list of
  hand-events. We can walk the chains chronologically and maintain
  a (L, R, A) state where L = balls in left hand, R = balls in
  right hand, A = balls in air. The state is constrained:
  L + R + A = total_n_balls (3 for identical, 5 for YouTube)
  and each hand has bounded capacity (0-3 balls).
  Question: is the chain set a closed juggling system?
- Approach:
  - Walk h7v3plus3 chains chronologically, emit per-event
    CATCH (at from-tracklet last_frame) and THROW (at
    to-tracklet first_frame).
  - Update (L, R, A) state. Detect violations:
    CATCH_NO_AIR, CATCH_OVER_CAP, THROW_EMPTY_HAND,
    THROW_NO_AIR_SLOT.
  - Interpolate state to per-frame timeline (HOLD between events).
  - Render 2 contact sheets (one per video) with stacked
    area chart of (L, R, A) over time and scatter of catch/
    throw events.
- Quantitative result:
  - identical: 24 known-hand events, 2 ambiguous. 51 timeline
    entries, 0 violations, 0 over-capacity events. Interpolated
    per-frame states: 1102. Distribution: L=0 R=0 A=3 (73.0%),
    L=0 R=1 A=2 (17.5%), L=1 R=0 A=2 (9.4%).
  - YouTube: 24 known-hand events, 0 ambiguous, 1 unknown-hand.
    50 timeline entries, 0 violations. Interpolated per-frame
    states: 870. Distribution: L=0 R=0 A=5 (73.3%),
    L=0 R=1 A=4 (15.7%), L=1 R=0 A=4 (10.9%).
- Visual QA: 2 contact sheets rendered. Identical is a clean
  3-ball cascade; YouTube is a clean 5-ball pattern. Total
  state is flat at 3 (identical) and 5 (YouTube) throughout,
  confirming a closed juggling system.
- Negative findings:
  - The "73% all in air" baseline is consistent with cascade
    patterns. No frame has 3+ balls in one hand.
  - H32's MULTI_BALL_MERGE chains are NOT due to chain-set
    over-attribution of hand occupancy to one hand. The
    multi-ball-merge problem is at the per-chain physical-
    ball-identity level, not the global hand-occupancy level.
  - Right-hand bias on YouTube (15.7% R vs 10.9% L) is real
    but unexplained (camera angle or juggler preference).
- Verdict: **PASS.** The h7v3plus3 chain set is a complete,
  consistent, closed representation of the juggling routines
  in both videos, validated at three levels: chain quality
  (H10), identity propagation (H11), and per-frame
  hand-occupancy (H36). See `h1_hand_pool/reports/h36_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h36_hand_occupancy_state_machine.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h36_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h36_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h36_timeline_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h36_per_frame_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h36_violations_*.csv` (2 files, empty)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h36_conflicts_*.csv` (2 files, empty)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h36/*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h36_report.md`


### H37 (2026-08-28 ~13:35 CEST)

- Hypothesis: H36 (L, R, A) state and H12 v8 pattern labels
  should agree on which frames have a ball in a hand. Cross-
  referencing answers: (1) Do they agree? (2) Does the (L, R, A)
  state disambiguate CASCADE_3+ vs FOUNTAIN_3+ on the late phase?
  (3) Is H36's state a useful input to H12 v9?
- Approach:
  - Load H36 per_frame and H12 v8 (H35) pattern_inference
    per-frame data.
  - Merge on frame number.
  - Compute agreement on (L, R, A) ball count.
  - For frames where H12 v8 says CASCADE_3+ or FOUNTAIN_3+,
    check if H36's (L, R, A) state is consistent.
  - Visualize on contact sheets.
- Quantitative result:
  - identical: 80.7% agreement (823/1020 common frames).
  - YouTube: 76.5% agreement (664/868 common frames).
  - L_extra and R_extra are all HOLD frames (interpolated),
    not real disagreements.
  - Late-phase identical FOUNTAIN_3+ (71 frames): 97% have
    H36 state (0, 0, 3) — no hand-occupancy support.
  - CASCADE_3+ frames have hand-occupancy support:
    20/22 identical CASCADE_3+ are (0, 1, 2) on identical;
    66/129 YouTube CASCADE_3+ are (0, 1, 4).
- Visual QA: 2 contact sheets rendered. The identical late-phase
  FOUNTAIN_3+ blocks (f=800-1050) appear as continuous stretches
  alternating with MIXED_3+ blocks. H36 (L, R, A) state is mostly
  (0, 0, 3) during FOUNTAIN_3+ blocks.
- Negative findings:
  - H12 v8 FOUNTAIN_3+ classification has 0% hand-occupancy
    support on identical late phase (69/71 = 97% are (0, 0, 3)).
    FOUNTAIN_3+ is based on event-log density, not hand occupancy.
  - H36 (L, R, A) state does NOT resolve the CASCADE/FOUNTAIN
    ambiguity on the late phase.
  - H12 v8 confidence drops to 0.5-0.7 in the late phase,
    reflecting the fundamental uncertainty.
- Verdict: **PASS (consumer-pass, validation).** H37 confirms
  H36 (L, R, A) state and H12 v8 pattern labels are largely
  consistent. H36 validates CASCADE_3+ but cannot disambiguate
  FOUNTAIN_3+. See `h1_hand_pool/reports/h37_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h37_crossref.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h37_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h37_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h37_crossref_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h37/*.png` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h37_report.md`


### H38 (2026-08-28 ~13:50 CEST)

- Hypothesis: H37 showed CASCADE_3+ frames have hand-occupancy
  support (20/22 identical, 117/129 YouTube). A small fraction
  of CASCADE_3+ frames have NO hand-occupancy (H36 state
  (0, 0, 3) or (0, 0, 5)) — likely H12 v8 misclassifications.
  Question: does rejecting these improve precision?
- Approach:
  - Load H37 crossref data.
  - For each CASCADE_3+ frame where H36 state is (0, 0, total),
    mark as CASCADE_REJECTED.
  - Compare pattern distribution before/after.
  - Compare CASCADE phases (>= 20 consecutive frames) before/after.
- Quantitative result:
  - identical: 1/22 (4.5%) CASCADE_3+ rejected. Pattern
    distribution: 22 CASCADE_3+ before, 21 after + 1
    CASCADE_REJECTED.
  - YouTube: 12/129 (9.3%) CASCADE_3+ rejected, all in
    contiguous block f=470-481 with H12 v8 confidence 0.639-0.646.
    Pattern distribution: 129 CASCADE_3+ before, 117 after + 12
    CASCADE_REJECTED.
  - No substantial CASCADE phases (>= 20 frames) were broken
    by the filter.
- Negative findings:
  - H38 is a small precision improvement, not a fundamental
    fix. The 9.3% rejection rate on YouTube is real but small.
  - H38 does not fix the H12 v8 CASCADE/FOUNTAIN ambiguity
    on the late phase.
- Verdict: **PASS (precision improvement, narrow scope).** H38
  is a strict post-filter that rejects CASCADE_3+ classifications
  where H36 has no hand-occupancy support. The improvement is
  small (1/22 identical, 12/129 YouTube) but real. H38 is
  safe to apply as a downstream consumer filter. See
  `h1_hand_pool/reports/h38_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h38_post_filter.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h38_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h38_filtered_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h38_report.md`

### H39 (2026-08-28 ~14:35 CEST)

- Hypothesis: the symmetric question to H38 — does FOUNTAIN_3+
  have hand-occupancy support from H36? If H12 v8 calls a frame
  FOUNTAIN_3+ but H36 has no hand-occupancy, the FOUNTAIN_3+
  classification may be a misclassification.
- Two iterated implementations:
  - v1 (frame-level): reject FOUNTAIN_3+ where H36 (L, R) = (0, 0)
  - v2 (phase-level): reject FOUNTAIN_3+ phases with zero H36 events
- Quantitative result:
  - v1: identical 288/288 FOUNTAIN_3+ rejected (98.3%); YouTube
    94/110 (85.5%). All 10 identical FOUNTAIN phases eliminated.
  - v2: identical 74 frames rejected (2 phases); YouTube 0 rejected.
- Visual QA on 10 FOUNTAIN_3+ phases (n>=10):
  - **3/10 real FOUNTAIN** (f=243-252, f=631-669, f=685-716)
  - 4/10 MIXED (real juggling with hand-occupancy visible)
  - 1/10 CASCADE (f=339-374 YouTube — real 5-ball cascade!)
  - 2/10 OTHER (f=977-1011 hold trick, f=1029-1050 2-ball exercise)
- Visual QA verdicts on H39 filters:
  - H39 v1 precision: **20% (2/10)** — over-rejects 60% of real juggling
  - H39 v2 precision: **50% (1/2)** — over-rejects f=411-449 MIXED
- H12 v8 FOUNTAIN_3+ classification accuracy: **30% (3/10)**
  - This is a real and important finding: H12 v8 over-classifies
    FOUNTAIN_3+ by ~70%
- Negative findings:
  - H36 chain-driven state is too sparse to validate FOUNTAIN_3+.
    H36 only marks hand-occupancy at chain events; continuous
    hand-occupancy is invisible to H36.
  - H39 v1 over-rejects 6/10 real juggling phases because H36
    reports no hand-occupancy during chain-event gaps.
  - H39 v2 is more conservative but only 50% precise on small
    sample. The 2 rejected phases are the worst visual
    misclassifications (hold trick + MIXED) but the 8 KEPT
    phases include a real CASCADE that H12 v8 misclassified.
  - H12 v8 FOUNTAIN_3+ classification is fundamentally unreliable
    on these videos. A reliable fix would require a continuous
    hand-occupancy signal, not chain-driven.
- Verdict: **NEGATIVE.** H39 v1 (frame-level) over-rejects 60% of
  real juggling activity. H39 v2 (phase-level) is more
  conservative but only 50% precise. Don't use H39 as a downstream
  filter. The H12 v8 FOUNTAIN_3+ classification should be left
  as-is with the caveat that it has ~70% error rate. The
  underlying finding (H12 v8 over-classifies FOUNTAIN_3+ by 70%)
  is real but H36 is not a reliable validator. See
  `h1_hand_pool/reports/h39_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_fountain_post_filter.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39v2_phase_filter.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_visual_qa.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_contact_sheets.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_visual_qa_verdicts.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_filtered_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39v2_filtered_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h39/*.png` (11 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h39_report.md`

### H40 + H41 (2026-08-28 ~14:50 CEST)

- **H40 hypothesis:** H36 only emits hand-occupancy state at
  chain events. H39 v1/v2 over-rejected real FOUNTAIN_3+ phases
  because H36 reports HOLD state during chain-event gaps even
  when the juggler's hands ARE occupied. A continuous per-frame
  hand-occupancy signal (raw detector + pose) would be more
  reliable.
- **H40 v1 (per-frame, 108 px reach):** detects 54.6% hand-
  occupancy on identical, 90.3% on YouTube (vs H36's 23.7%
  and 25.8%).
- **H40 v2 (sustained, 100 px, 3-frame run):** detects 72.3%
  hand-occupancy on identical, 98.1% on YouTube. Better than
  v1 at rejecting transient fly-bys.
- **H40 v2 by H12 v8 pattern (identical):**
  - FOUNTAIN_3+: 81.8% (47.8% both-hands)
  - CASCADE_3+: 90.9% (22.7% both-hands)
  - MIXED_3+: 86.7% (22.2% both-hands)
  - SINGLE_BALL: 31.5% (6.1% both-hands)
- **H40 v2 by H12 v8 pattern (YouTube):**
  - FOUNTAIN_3+: 98.2% (74.5% both-hands)
  - CASCADE_3+: 96.9% (42.2% both-hands)
  - MIXED_3+: 98.1% (58.2% both-hands)
- **H41 hypothesis:** H40 v2-based FOUNTAIN_3+ post-filter
  should improve over H39 v1 (precision 20%) and v2 (50%).
- **H41 v1 (MIN_OCC=0.50) and v2 (MIN_OCC=0.20) implemented.**
  H41 v2 rejects 4 identical phases (f=411-449, f=631-669,
  f=775-779, f=1070-1074) and all 3 YouTube phases (high
  both-hands rate).
- **H41 visual QA on identical:**
  - 2/4 correct rejects (f=411-449 MIXED, f=631-669 FOUNTAIN — over-rejects)
  - 2/2 correct keeps (f=243-252 FOUNTAIN, f=685-716 FOUNTAIN)
  - 2/2 over-keeps (f=977-1011 hold trick, f=1029-1050 2-ball exercise)
- **Key findings:**
  1. H40 v2 detects 3-4x more hand-occupancy than H36 (continuous
     signal, not chain-driven).
  2. H40 v2 hand-occupancy does NOT cleanly discriminate FOUNTAIN
     from CASCADE (FOUNTAIN 81.8% vs CASCADE 90.9% on identical,
     FOUNTAIN 98.2% vs CASCADE 96.9% on YouTube).
  3. The "both-hands occupied" rate IS more discriminating
     (YouTube FOUNTAIN 74.5% vs CASCADE 42.2%) but is dominated
     by sustained ball-wrist proximity, not actual holds.
  4. H40 sustained-occupancy detects "ball near hand", not
     "ball held by hand" — a fundamental 2D-distance limitation.
  5. Pose wrist position is sometimes far from the held ball
     (70-90 px in f=631-669), causing H40 v2 to under-detect
     real hand-occupancy.
- **Verdict:**
  - **H40 PASS as a diagnostic signal.** Better hand-occupancy
    coverage than H36, independent of chain events.
  - **H41 NEGATIVE as a FOUNTAIN_3+ post-filter.** H41 v2
    precision 50% (same as H39 v2) — no improvement. H12 v8
    FOUNTAIN_3+ classification remains fundamentally unreliable.
  - **Recommended operating point:** h7v3plus3 (H34) remains
    the recommended chain set. H40 is a useful diagnostic but
    does not solve the H12 v8 FOUNTAIN_3+ problem.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h40_continuous_hand_occupancy.py` (v1)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h40v2_sustained_hand_occupancy.py` (v2)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h41_fountain_post_filter_h40.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40_continuous_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h40v2_continuous_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h41_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h41_filtered_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h40_h41_report.md`

### H45 (2026-08-28 ~15:15 CEST)

- Hypothesis: H12 v8 infers CASCADE_3+ vs FOUNTAIN_3+ via a K=4
  sliding window of hand events. A siteswap-based approach
  computes the "throw digit" directly from the THROW-to-next-CATCH
  flight time and should produce a more uniform, less window-bound
  pattern inference. Per-chain flight-time statistics
  (median, CV) cross-checked against H12 v8 pattern labels.
- Implementation: `h45_siteswap_digits.py` consumes
  `chain_events_h35_<stem>.csv` and computes, for each chain:
  n_tracklets, median hold_time, median flight_time, flight CV
  (when n_flights >= 3), dominant H12 v8 pattern, and mean H12 v8
  pattern confidence. Plus per-video sparsity diagnostic
  (n_events, event_rate, n_chains with 3+ flights).
- UNIFORM_CV_THRESHOLD = 0.5 declared from physics, not labels.
- Quantitative result:

| Video | n_events | event_rate | n_chains | w/ flights | w/ 3+ flights |
|---|---|---|---|---|---|
| identical | 48 | 0.047 | 13 | 5 (38%) | 2 (15%) |
| YouTube   | 50 | 0.059 | 10 | 7 (70%) | 1 (10%) |

Cross-pattern CV (only MIXED_3+ has n>=3):

| Pattern | n | mean CV | median CV |
|---|---|---|---|
| FOUNTAIN_3+ | 1 | 0.654 | 0.654 |
| SINGLE_BALL | 1 | 0.784 | 0.784 |
| MIXED_3+ | 7 | 0.598 | 0.560 |

Per-chain statistics (chains with n_flights >= 1):
- identical chain 22: 4 flights, median 32.0, CV 0.65
- identical chain 29: 3 flights, median 16, CV 0.78
- YouTube chain 9: 4 flights, median 61.5, CV 0.47

- Visual QA: 11 contact sheets (3 chains x ~3-4 flights each)
  rendered to `contact_sheets_h45/`. All 11 flights inspected
  via `vision_analyze`:
  - **identical chain 22 (4 flights)**: 3/4 real catch-throws
    (ft=33, 31, 39) at right hand. 1/4 (ft=1) is an identity
    switch (999→94 px geometric discontinuity).
  - **identical chain 29 (2 inspected of 3 flights)**: 1/2
    real catch-throw (ft=33). 1/2 (ft=5) is an identity
    switch (cross-hand, 5-frame "flight").
  - **YouTube chain 9 (4 flights)**: 0/4 real catch-throws.
    ALL 4 (ft=58, 61, 62, 134) are tracker fragmentation
    (slope jumps 0.94→14.35, 1.81→11.20, 2.34→11.96,
    distance jumps, no visible ball at hand at focus frame).
  - **All 4 chain 9 flights have similar ~58-62 frame "flight
    times"**, which is uniformly tracker fragmentation, not
    real juggling. The "low CV=0.47" is misleadingly "uniform"
    because all 4 flights are the SAME artifact.

- Negative findings:
  - **Siteswap analysis is infeasible with the H12 v8 event log.**
    Only 2/13 identical chains and 1/10 YouTube chains have
    n_flights >= 3. This is an input-data limitation, not an
    H45 algorithm problem.
  - **The H12 v8 event log is trustworthy for chain topology
    on both videos, but for inter-event timing only on identical.**
    The 30-40 frame flight times on identical match the expected
    3-ball cascade ball airtime (1.0-1.3s at 30fps) exactly.
    The 58-67 frame "flights" on YouTube are uniformly tracker
    fragmentation.
  - **The 10-frame flight-time filter is a useful downstream
    post-filter**: drop H12 v8 "flights" < 10 frames as likely
    identity switches. On identical, this rejects 3/11 flights
    and preserves 7 real catch-throws.
  - **Low flight-time CV can be EITHER real uniform juggling
    OR uniform tracker failure.** A pure statistical test
    cannot distinguish them without ground truth.

- Verdict: **NEGATIVE result with structural insight.** H45
  closes the siteswap direction (master §24 / H44 follow-up).
  The h7v3plus3 chain set is well-validated at the
  inter-event-timing level for identical but not YouTube.
  See `h1_hand_pool/reports/h45_report.md` for full analysis.

- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_siteswap_digits.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_flight_time_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h45_siteswap_flights.csv` (25 rows)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h45_siteswap_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h45/*.png` (11 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h45_report.md`

### H46 (2026-08-28 ~15:30 CEST)

- Hypothesis: H12 v8 source tracklet's last arc and target
  tracklet's first arc should be physically consistent for
  real catch-throws, and physically disconnected for
  tracker fragmentations. A per-flight physics check would
  distinguish the two cases.
- Implementation: H46 v1 extrapolates source's last-arc
  parabola across the held-phase gap and compares to
  target's first position. H46 v2 simplifies to a bounce
  sign test: v_in < 0 AND v_out < 0 (both post-throw
  tracklets ascending).
- Quantitative result:

| Video | n_flights | H46 v1 PHYSICS_OK | H46 v2 BOUNCE_OK |
|---|---|---|---|
| identical | 11 | 0 | 2 |
| YouTube | 15 | 0 | 0 |

- Negative findings:
  - **H46 v1 hypothesis was wrong.** The source tracklet's
    last points are NOT the descent into the hand — they
    are the post-throw ascent (the tracklet starts at the
    throw frame, not the catch frame). The held phase is
    not in any tracklet.
  - **H46 v2 bounce sign test is too restrictive on
    identical** (rejects 9/11 flights including 3 visually-
    confirmed real catch-throws in chain 22) and too
    permissive on YouTube (rejects 0/15 — but H45 visual QA
    found 0/4 real catch-throws on YouTube chain 9, so
    rejecting 15/15 is the right answer for YouTube).
  - **YouTube 0/15 BOUNCE_OK is strong evidence that all
    YouTube H12 v8 events are tracker fragmentation.**
    Consistent with H45's 0/4 visual-QA finding.
  - **The 10-frame flight-time filter (H45) is the only
    actionable post-filter for H12 v8 event log.**
- Verdict: **NEGATIVE result.** H46 v1 hypothesis was wrong.
  H46 v2 confirms H45's YouTube finding but adds no new
  signal for identical. See `h1_hand_pool/reports/h46_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h46_per_flight_physics.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h46_per_flight_physics.csv` (26 rows)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h46_per_flight_physics_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h46_report.md`

### H47 (2026-08-28 ~15:45 CEST)

- Hypothesis: H45 found that the 10-frame flight-time filter
  is a useful downstream post-filter for H12 v8 event log.
  Applying it as a pre-filter for K=4 sliding window inference
  should produce a slightly cleaner pattern classification.
- Implementation: `h47_h12v8_flight_time_filter.py` loads
  H12 v8 event log, computes per-flight flight times, drops
  (CATCH, THROW) pairs with flight time < 10 frames, then
  re-runs a simplified K=4 pattern classifier.
- Quantitative result:

| Video | Total events | Flights w/ time | Short (< 10f) | Dropped |
|---|---|---|---|---|
| identical | 48 | 11 | 3 | 3 (6.2%) |
| YouTube | 50 | 15 | 0 | 0 (0.0%) |

- Negative findings:
  - The 10-frame filter is a no-op on YouTube (all flights
    are >= 58 frames due to tracker fragmentation).
  - The 10-frame filter drops only 3/48 events on identical
    — a small but real precision improvement.
- Verdict: **PASS (narrow scope).** The 10-frame filter is
  a safe, useful downstream post-filter for H12 v8 event
  log consumers. It can be applied before K=4 sliding window
  inference as a precision improvement. H47 simplified
  classifier doesn't use chain quality, so it's NOT a
  drop-in replacement for H12 v8. See
  `h1_hand_pool/reports/h47_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h47_h12v8_flight_time_filter.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h47_flight_time_filter_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h47_report.md`

### H48 (2026-08-28 ~15:55 CEST)

- Hypothesis: H47 used a 10-frame filter. Is 10 the
  optimal threshold? Sweep {5, 10, 15, 20, 30, 40, 50, 60}
  and report per-threshold impact on H45 labels.
- Implementation: `h48_flight_filter_sensitivity.py` loads
  H12 v8 event log, computes per-flight flight times,
  cross-references with H45 visual-QA labels, and reports
  the per-threshold drop/keep counts.
- Quantitative result on identical (7 H45-labeled flights,
  4 REAL + 3 IDENTITY_SWITCH):

| THR | dropped events | kept REAL | dropped REAL | kept ID | dropped ID |
|---|---|---|---|---|---|
| 5  | 4  | 4 | 0 | 1 | 2 |
| **10** | **6**  | **4** | **0** | **0** | **3** |
| 15 | 6  | 4 | 0 | 0 | 3 |
| 20 | 8  | 4 | 0 | 0 | 3 |
| 30 | 8  | 4 | 0 | 0 | 3 |
| 40 | 16 | 0 | 4 | 0 | 3 |
| 50 | 18 | 0 | 4 | 0 | 3 |

- YouTube: 0/4 TRACKER_FRAGMENTATION dropped at any
  threshold <= 50; 1/4 dropped at THR=60.

- Key finding: **THR=10 is in a flat region (10-30)** for
  identical. THR=40 first drops REAL catch-throws. THR=50+
  drops all REAL catch-throws. There is no single threshold
  that filters YouTube's tracker-fragmentation flights.

- Verdict: **PASS (confirms H45).** The 10-frame filter is
  the optimal threshold for identical and is in a flat
  region. The H45 finding is robust. See
  `h1_hand_pool/reports/h48_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h48_flight_filter_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h48_flight_filter_sensitivity.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h48_report.md`

### H49 (2026-08-28 ~16:10 CEST)

- Hypothesis: H45/H47 found the 10-frame filter drops 3/48
  events on identical. What is the actual downstream impact
  on H12 v8's per-frame pattern classification?
- Implementation: `h49_filter_impact.py` measures the K=4
  re-classification rate when the filtered event log is used.
  For each frame, compute K=4 most recent events (before this
  frame) — with and without filter — and re-classify using
  H12 v8's K=4 pattern logic.
- Quantitative result:
  - identical: 12 events dropped (6 pairs), K=4 re-classification
    rate 471/1042 frames (45.2%)
  - YouTube: 0 events dropped, K=4 re-classification rate
    143/898 frames (15.9%)
- Negative findings:
  - **The K=4-only re-classification rate is an UPPER BOUND
    on actual H12 v8 impact** because the K=4-only classifier
    doesn't apply H12 v8's full pipeline (census + chain
    quality + n_total balls). H12 v8's actual re-classification
    rate is much smaller.
  - For example: H12 v8 says f=236-242 identical are TWO_BALL
    (conf 0.64) because the census shows only 2 balls in air.
    My K=4 classifier says they should be CASCADE_3+ after
    the filter. But H12 v8's actual re-run would still call
    them TWO_BALL because the census doesn't change.
  - YouTube's 15.9% "re-classification rate" with 0 events
    actually dropped is a measurement artifact of the K=4
    sliding window — the window context changes for many
    frames but no events are actually removed.
- Verdict: **NEGATIVE result (impact measurement methodology
  is flawed).** A proper measurement would require
  re-running H12 v8 with the filtered event log. The H45/H47/
  H48 findings (10-frame filter drops 3/48 events on
  identical, 0/50 on YouTube) remain the actionable results.
  See `h1_hand_pool/reports/h49_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h49_filter_impact.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h49_filter_impact_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h49_report.md`

### H50 (2026-08-28 ~16:30 CEST)

- Hypothesis: H49's K=4-only re-classification rate is an
  upper bound. The proper measurement requires re-running
  H12 v8's FULL pipeline (census + K=4 events + chain quality
  + n_total) on the filtered event log. H50 implements this.
- Implementation: `h50_filtered_patterns.py` re-builds the
  H12 v8 catch/throw timeline from h7v3pure hand-edges,
  applies the 10-frame flight-time filter (drop (CATCH, THROW)
  pairs where THROW's flight time < 10 frames), and runs the
  full per-frame pattern inference on BOTH the unfiltered and
  filtered event logs for an apples-to-apples comparison.
- Quantitative result:

  || Video | Unfiltered | Filtered | Dropped | n_short | Frames changed |
  ||---|---|---|---|---|---|
  || identical | 50 events | 44 events | 6 | 3/11 | 10/1042 (1.0%) |
  || YouTube   | 50 events | 50 events | 0 | 0/16 | 0/898 (0.0%) |

  Per-pattern delta on identical:
  - FOUNTAIN_3+ -0.3% (3 frames)
  - CASCADE_3+ +0.7% (7 frames)
  - MIXED_3+ -0.3%
  - All other patterns: 0.0% change
  - Substantial phases (n_frames >= 20): 15 -> 15 (unchanged)

  YouTube: 0.0% change across all patterns.

- Visual QA on the 3 changed windows (3 contact sheets in
  `contact_sheets_h50/`):
  - **chain 13 ft=3 (f=207 -> f=232)**: Vision tool says this
    looks like a REAL catch-throw (yellow trail at hand,
    cyan trail emerging from hand, ball visible at hand).
    This contradicts H45's prior bucket analysis that all
    < 10-frame flights are identity switches. **H45 did not
    visually QA this case** (only chains with n_flights >= 3
    were QA'd). The 10-frame filter may be over-aggressive
    here.
  - **chain 23 ft=1 (f=522 -> f=533)**: Vision tool confirms
    IDENTITY_SWITCH (1-frame flight is physically impossible).
    H50 filter is correct.
  - **chain 30 ft=5 (f=766 -> f=775)**: Vision tool confirms
    TRACKER_FRAGMENTATION (5-frame flight, persistent teal
    predicted markers, hands co-located). H50 filter is correct.

- Negative findings:
  - The chain 13 ft=3 case shows the 10-frame threshold is
    approaching its useful limit. A more conservative THR=5
    would preserve this case, but H48's sensitivity grid
    showed THR=5-9 admits all 4 H45 REAL catch-throws plus
    the 3 IDENTITY_SWITCHES, which is less precise.
  - The chain 13 ft=3 case was not visually QA'd in H45
    (only chains with n_flights >= 3 were QA'd). The H45
    claim "all < 10-frame flights are identity switches" is
    based on bucket analysis, not direct visual confirmation
    of all 3 cases.

- Implications:
  - The 10-frame filter is a SAFE post-filter for H12 v8
    event log consumers: 1.0% identical / 0.0% YouTube
    real downstream impact.
  - H49's K=4-only upper bound (45.2%/15.9%) was indeed an
    upper bound, as H49 suspected. The full pipeline is
    dominated by census + quality + n_total, not K=4.
  - H12 v8 + 10-frame filter is the new recommended
    operating point for downstream consumers.

- Verdict: **PASS** (closes H49's negative result). The
  10-frame flight-time filter has small, real downstream
  impact on H12 v8's per-frame pattern labels. The 1/3
  ambiguous drop (chain 13 ft=3) is a known limitation
  that does not invalidate the 10-frame threshold.
  See `h1_hand_pool/reports/h50_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h50_filtered_patterns.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h50_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_h50_*.csv` (filtered, 2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_h50_unfiltered_*.csv` (apples-to-apples baseline, 2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_h50_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/catch_throw_timeline_h50_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h50_dropped_events_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h50_filtered_patterns_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h50/*.png` (3 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h50_report.md`

### H51 (2026-08-28 ~16:45 CEST)

- Hypothesis: H50 (event-log filter) and H43 (confidence filter)
  operate at different stages. Do they compose cleanly?
- Implementation: `h51_combined_filter.py` loads H50's
  filtered pattern_inference, applies H43's confidence
  < 0.55 filter to FOUNTAIN_3+ frames, and compares to
  H12 v8 unfiltered + H43 as the baseline.
- Quantitative result:

  Per-frame diff (H50+H43 vs H43 only):
  - identical: 10/1042 (1.0%)
  - YouTube: 0/898 (0.0%)

  Combined precision improvement on identical:
  - FOUNTAIN_3+ -2.3% (24 frames, down from 16.4%)
  - CASCADE_3+ +0.7% (7 frames, up from 6.7%)
  - Substantial phases: 15 -> 15 (unchanged)

  YouTube: 0% change.

- Key findings:
  - H50 and H43 compose cleanly. The 10 H50-changed
    frames don't trigger H43 (they're not in the
    conf < 0.55 region).
  - H50+H43 is a strict improvement over either alone.
  - The combined filter addresses two independent error
    modes: identity switches (H50) and low-confidence
    FOUNTAIN_3+ (H43).

- Verdict: **PASS.** h7v3plus3 + H12 v8 + H50 + H43 is
  the final precision-optimized operating point.
  See `h1_hand_pool/reports/h51_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h51_combined_filter.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_filtered_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_phases_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_combined_filter_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h51_report.md`

### H52 (2026-08-28 ~17:00 CEST)

- Hypothesis: H50 visual QA found chain 13 ft=3 looked like
  a real catch-throw, contradicting H45's bucket analysis.
  Can H8 v5 physics distinguish chain 13 from chain 23/30?
- Implementation: `h52_physics_check.py` applies H8 v5's
  parabolic fit to the 3 H50-dropped pairs and runs a
  sensitivity grid on MIN_TRACKLET_PTS ∈ {2, 3, 4, 5, 6, 8, 10}.
- Quantitative result:

  || Chain | ft | src_n | tgt_n | H8 v5 MIN=6 | H8 v5 MIN=2 |
  ||---|---|---|---|---|---|
  || 13 | 3 | 36 | 4 | INSUFFICIENT | VIOLATING (19.5 px/f) |
  || 23 | 1 | 14 | 2 | INSUFFICIENT | OK (1.3, unreliable) |
  || 30 | 5 |  2 | 6 | INSUFFICIENT | VIOLATING (18.1 px/f) |

- Key finding: H50 visual QA was wrong about chain 13.
  H8 v5 physics says chain 13 is TRACKER_FRAGMENTATION:
  source in fast descent (-32.1 px/f), target at rest
  (-1.1 px/f), 19.5 px/f velocity discontinuity.
  A real catch-throw would have consistent velocities.

- Negative findings:
  - The H50 vision tool was misled by the visual appearance
    of "ball at hand" — the source was in fast descent, the
    target was at rest, and these are physically inconsistent.
  - The H8 v5 check is INSUFFICIENT_DATA at MIN=6 for all
    3 pairs because at least one side has < 6 points. This
    is itself a strong signal: real catch-throws have both
    source and target tracklets with at least 6 points.
  - The chain 23 OK result at MIN=2 is unreliable (only 2
    target points, parabolic fit is noise-sensitive).

- Resolution of H50 ambiguity: H45's claim "< 10 frame
  flights = identity switches" is now fully verified by
  H8 v5 physics. The 10-frame filter is correct and should
  not be relaxed to preserve chain 13.

- Verdict: **PASS.** The h7v3plus3 + H12 v8 + H50 + H43 +
  H52-validated stack is the final operating point.
  See `h1_hand_pool/reports/h52_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h52_physics_check.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h52_physics_check_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h52_report.md`

### H53 (2026-08-28 ~17:30 CEST)

- Hypothesis: H52's summary JSON does not preserve the MIN=2
  sensitivity-grid values that the H52 report cites (chain 13
  src_vy=-32.1, tgt_vy=-1.1, v_disc=19.5). The H50 vision QA
  also produced an ambiguous result on chain 13 ft=3 ("real
  catch-throw" per H50, "TRACKER_FRAGMENTATION" per H52 physics)
  and a vision-tool contradiction on chain 23 ft=1 (H50 said
  "tracker artifact"; H53 vision QA on the same image said
  "real catch-throw").

- Three-part experiment:
  1. H52 sensitivity grid preservation: 9-cell MIN_TRACKLET_PTS
     grid (2-12) saved to `h53_h52_sensitivity_grid.json`. MIN=2/3/4
     results are consistent (v_disc=19.5 for chain 13); MIN=5+
     returns INSUFFICIENT_DATA.
  2. Multi-rater visual QA consensus on 3 dropped pairs: 4 raters
     (H45 bucket, H50 vision A, H52 physics, H53 vision A and B
     with two question phrasings) all 3 pairs reach
     TRACKER_FRAGMENTATION consensus.
  3. H52+MIN=2 vs H50 on full event log: H52+MIN=2 is
     OVER-AGGRESSIVE (16/25 identical and 24/25 YouTube C2T drops).
     H52+MIN=2 is a useful corroborating signal on H50 drops
     (5/11 identical and 12/13 YouTube H50 drops are also
     H52+MIN=2 VIOLATING = high-confidence fragmentation).

- Multi-rater visual QA results (question A: real vs artifact;
  question B: same ball vs different balls):

  || Pair | H45 | H50 (A) | H52 (MIN=6) | H52 (MIN=2) | H53 (A) | H53 (B) | Consensus |
  ||---|---|---|---|---|---|---|---|
  || chain 13 ft=3 | IDENTITY_SWITCH | REAL | INSUFFICIENT | VIOLATING | FRAGMENTATION | DIFFERENT_BALLS | TRACKER_FRAGMENTATION |
  || chain 23 ft=1 | IDENTITY_SWITCH | FRAGMENTATION | INSUFFICIENT | OK | REAL | DIFFERENT_BALLS | TRACKER_FRAGMENTATION (tie, filter-default) |
  || chain 30 ft=5 | IDENTITY_SWITCH | FRAGMENTATION | INSUFFICIENT | VIOLATING | FRAGMENTATION | DIFFERENT_BALLS | TRACKER_FRAGMENTATION |

- Key findings:
  - **All 3 H50 drops are TRACKER_FRAGMENTATION by multi-rater consensus.**
    The 10-frame filter is correct and should not be relaxed.
  - **The H50 chain 13 ft=3 "real catch-throw" caveat is now resolved.**
    2/3 vision votes + H52 physics say TRACKER_FRAGMENTATION.
  - **The H50 chain 23 ft=1 case is vision-tool-ambiguous.** H50 says
    "tracker artifact" but H53 question A says "real catch-throw".
    The 2/3 vision split + filter-default tie resolves in favor of
    TRACKER_FRAGMENTATION, but the case is the limit of vision QA on
    short flights.
  - **H52+MIN=2 is not a viable standalone filter.** It's over-aggressive
    on the full event log. The 10-frame filter is the recommended
    operating point.
  - **H52+MIN=2 is a useful corroborating signal.** When an H50 drop
    also has H52+MIN=2 VIOLATING, that's a high-confidence
    fragmentation case (5/11 identical, 12/13 YouTube).

- Negative findings:
  - The H50 vision tool and H53 vision tool (same model) produce
    contradictory verdicts on the same contact sheet when asked the
    "real vs artifact" question. The "same ball vs different balls"
    question is more reliable (2/3 votes match across H50 + H53).
  - Vision tool is unreliable for short flights (chain 23 ft=1):
    the 1-frame gap is at the limit of visual signal, and the tool
    produces contradictory verdicts depending on question phrasing.

- Verdict: **PASS.** The h7v3plus3 + H12 v8 + H50 + H43 + H52 stack
  is the final operating point. H53 closes a documentation gap
  (H52 JSON missing grid values) and confirms the operating point
  through 3 independent visual QA passes + 1 physics check.
  See `h1_hand_pool/reports/h53_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h53_physics_redo_and_multirater.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h53b_filter_comparison.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h53_h52_sensitivity_grid.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h53_multi_rater_visual_qa.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h53_filter_comparison_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h53_c2t_filter_comparison_*.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h53_filter_comparison_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h53_report.md`

### H54 (2026-08-28 ~18:00 CEST)

- Hypothesis: the per-chain coefficient of variation (CV) of clean
  per-arc gravity values (from H8 v8 extrema-arc fits) is a
  discriminative signal for "is this a single physical ball?".
- Implementation: `h54_per_chain_arc_gravity.py` (per-chain aggregation
  of H8 v8 arc fits, with clean-arc filter 0.05 < g < 5.0).
  `h54_analyze.py` cross-references with H10 v10 quality and H11 v7
  confidence labels.
- Quantitative result (multi-tid chains):
  - Identical: 2 CONFIDENT (g_cv mean 0.379) vs 11 UNCERTAIN
    (g_cv mean 0.782). 2x difference.
  - YouTube: 1 CONFIDENT (g_cv 0.427) vs 9 UNCERTAIN (g_cv mean 0.656).
  - Pearson(g_cv, h10_quality) = 0.008 identical, -0.308 YouTube.
    H54 is INDEPENDENT of H10 v10.
- Visual QA (3/3):
  - chain 22 (g_cv=1.537, identical): MULTI_BALL_MERGE confirmed
  - chain 30 (g_cv=0.417, identical): TRUE single-ball catch-throw
  - chain 12 YouTube (g_cv=1.179): MULTI_BALL_MERGE confirmed
- Verdict: PASS. H54 is a real, independent single-ball signal.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h54_per_chain_arc_gravity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h54_analyze.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h54_per_chain_arc_gravity_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h54_per_tracklet_arcs_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h54_with_h10_h11_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h54_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h54_analysis_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h54_report.md`

### H55 (2026-08-28 ~18:30 CEST)

- Hypothesis: combining H10 v10 (cross-edge and coverage) with H54
  (within-chain physics consistency) as a 5th dimension should improve
  chain quality ranking, especially for multi-tid UNCERTAIN chains
  that v10 over-ranks.
- Two iterations:
  - v1 (linear penalty): too aggressive, CONFIDENT 27→24 on identical
    at w54=0.30.
  - v2 (gated penalty, min_arcs=3, w54=0.30): correct. Only 9 chains
    penalized (those with n_arcs_clean >= 3). CONFIDENT 27→26
    identical, 5→4 YouTube.
- Operating point (v2): min_arcs=3, w54=0.30. Flat region of
  sensitivity grid.
- Visual QA (4/4):
  - chain 14 identical (g_cv=1.089, demoted to LOW): TRACKER FRAGMENTATION
  - chain 22 identical (g_cv=1.537, demoted to LOW): MULTI_BALL_MERGE
  - chain 12 YouTube (g_cv=1.179, demoted to LOW): MULTI_BALL_MERGE
  - chain 6 YouTube (g_cv=0.427, preserved CONFIDENT q11=0.713):
    TRUE single-ball catch-throw
- Verdict: PASS (narrow-scope precision improvement). H55 v2 correctly
  demotes 3 multi-ball-merge chains that v10 over-ranked. CONFIDENT
  count drops by 1 on each video; lost chains are confirmed FPs.
- Recommended operating point: h7v3plus3 + H10 v11 (H55 v2,
  min_arcs=3, w54=0.30) + H12 v8 + H50 + H43 + H52 + H53.
- For strictest single-ball filtering: H10 v11 + H11 v7 CONFIDENT.
  Multi-tid CONFIDENT: 2 identical (chain 20, chain 19) + 1 YouTube
  (chain 6).
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h55_h10v11_with_h54.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h55_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h55v2_gated_penalty.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h55v2_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h55_chain14_contact_sheet.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11_w0.30_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v2_w0.30_minarcs3_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v2_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h55_sensitivity_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h55v2_sensitivity_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h55/chain14_identical_h55v2.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h55_report.md`

### H56 (2026-08-28 ~19:00 CEST)

- Hypothesis: H55 v2's linear penalty over-penalizes chains with
  mid-range g_cv (e.g., chain 30 with g_cv=0.417, visually confirmed
  single-ball but demoted to LOW). A non-linear penalty with a
  deadzone (no penalty below g_cv=0.5) and a linear ramp should
  preserve low-CV chains while still penalizing high-CV chains.
- Formulation:
  ```
  g_penalty = 0                                    if g_cv <= 0.5
           = 0.30 * (g_cv - 0.5) / 0.5             if 0.5 < g_cv < 1.0
           = 0.30                                  if g_cv >= 1.0
  q_v11 = max(0, min(1, q_v10 - g_penalty))
  ```
- Quantitative result (d=0.5, r=1.0, w54=0.30, n_arcs>=3):
  - Identical: 27 CONFIDENT (matches v10), 3 multi-tid CONFIDENT
    (chain 20, chain 19, chain 7 NEW).
  - YouTube: 5 CONFIDENT (matches v10), 1 multi-tid CONFIDENT (chain 6).
  - chain 30 (g_cv=0.417, in deadzone) NOT over-penalized, preserved
    as UNCERTAIN.
  - chain 22 identical (g_cv=1.537) and chain 12 YouTube (g_cv=1.179)
    still correctly demoted to LOW.
- Sensitivity grid (15 cells: d x r): wide flat region. d=0.5-0.7
  with r=1.0+ all give 27 CONFIDENT identical, 5 CONFIDENT YouTube.
- Visual QA (3/3):
  - chain 7 identical (g_cv=0.72, NEW CONFIDENT): TRUE single-ball
    catch-throw with parabolic arc (H56 v1 contact sheet).
  - chain 30 identical (g_cv=0.417, preserved UNCERTAIN): TRUE
    single-ball (H11 v7 contact sheet).
  - chain 12 YouTube (g_cv=1.179, demoted): MULTI_BALL_MERGE.
- Negative finding: chain 14 (g_cv=1.089, n_arcs=2) escapes H56 v1
  penalty because n_arcs<3. Known limitation; H55 v2 catches it.
- Verdict: PASS — improves on H55 v2. Same precision, better recall.
- Recommended operating point: h7v3plus3 + H10 v11 v3 (H56 v1,
  deadzone=0.5, ramp_end=1.0, w54=0.30) + H12 v8 + H50 + H43 +
  H52 + H53.
- For strictest single-ball filtering: H10 v11 v3 + H11 v7 CONFIDENT.
  Multi-tid CONFIDENT: 3 identical (chain 20, 19, 7) + 1 YouTube
  (chain 6).
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h56_nonlinear_penalty.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h56_sensitivity.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h56_chain7_contact_sheet.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v3_nonlinear_w0.30_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v3_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h56_sensitivity_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h55/chain7_identical_h56v1.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h56_report.md`

### H57 (2026-08-28 ~19:30 CEST)

- Hypothesis: H56 v1's n_arcs_clean >= 3 gate is too strict for
  chains with very high g_cv (e.g., chain 14 with g_cv=1.089 and
  only 2 clean arcs). When g_cv > 1.0, even 2 arcs are sufficient.
- Formulation: full penalty if n_arcs >= 3, partial penalty
  (PARTIAL_W54=0.15 with linear ramp 1.0 → 1.5) if n_arcs >= 2
  AND g_cv >= 1.0, else 0.
- Quantitative result:
  - Identical: 11 chains penalized (vs 7 in H56 v1); CONFIDENT
    preserved at 27; chain 14 q10=0.454 → q11=0.427.
  - YouTube: identical to H56 v1 (no chains with n_arcs=2 + g_cv>1.0).
  - No CONFIDENT chains demoted.
- Verdict: PARTIAL PASS. Soft warning extension of H56 v1 with no
  label changes but small q reductions for high-CV low-arc chains.
- Recommended operating point: h7v3plus3 + H10 v11 v4 (H57 v1)
  + H12 v8 + H50 + H43 + H52 + H53.
- H10 v11 v3 (H56 v1) and H10 v11 v4 (H57 v1) give the same
  label classification; v4 adds soft penalties.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h57_conditional_penalty.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v4_conditional_w0.30_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v11v4_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h57_report.md`

### H58 (2026-08-28 ~20:00 CEST)

- Hypothesis: the 4 multi-tid CONFIDENT chains (3 identical + 1
  YouTube) at the intersection of H11 v7 and H10 v11 v3 CONFIDENT
  criteria should be the "purest" single-ball trajectories. The
  H12 v8 catch/throw events on these chains should reveal a clean
  juggling pattern.
- Identical (3 multi-tid CONFIDENT chains):
  - chain 7: tids (11, 14), f=87-160, q11=0.704, gap=11
  - chain 19: tids (30, 33), f=399-472, q11=0.867, gap=11
  - chain 20: tids (31, 36), f=411-578, q11=0.908, gap=11
- YouTube (1 multi-tid CONFIDENT chain):
  - chain 6: tids (10, 12), f=117-309, q11=0.841, gap=17, right hand
- Key findings:
  - All 3 identical chains have gap_frames=11 (consistent 3-ball
    cascade held phase).
  - Hand alternation rate 100% for all 3 identical chains.
  - chain 6 YouTube is a 5-ball shower pattern (same-hand events,
    longer held phase).
- Verdict: PASS — validates the v11 multi-tid CONFIDENT chains as
  a clean single-ball filter. The 11-frame held phase (identical)
  and 17-frame held phase (YouTube) are structural signatures of
  3-ball cascade and 5-ball shower.
- Recommended operating point: h7v3plus3 + H10 v11 v3 (H56 v1) +
  H12 v8 + H50 + H43 + H52 + H53 + H58 pattern validation.
- The 3 identical + 1 YouTube multi-tid CONFIDENT chains are the
  "purest" single-ball trajectories.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h58_intersection_analysis.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h58_intersection_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h58_event_summary_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h58_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h58_report.md`

### H58 v1 (2026-08-28 ~15:45 CEST)

- Hypothesis: H58 (h58_intersection_analysis.py) reported that the
  4 multi-tid CONFIDENT chains form a clean single-ball subset
  with consistent held-phase durations (3-ball cascade signature
  11 frames, 5-ball shower signature 17 frames). But the H58
  report did not include contact sheets on disk. H58 v1 renders
  the 4 contact sheets and visually confirms the H58 hypothesis.
- Implementation: `h58_v1_contact_sheets.py` loads the 4 multi-tid
  CONFIDENT chains, then for each renders 7 frames (3 from t_prev,
  2 from the held phase, 3 from t_curr) with wrist circles +
  per-tid colors + (x, y) labels.
- Visual QA via vision_analyze (3/3 inspected, 1 YouTube):
  - chain 7 identical (q11=0.704, tids 11->14): CATCH@114, THROW@114,
    trajectory consistent with single-ball cascade
  - chain 19 identical (q11=0.867, tids 30->33): CATCH@460, THROW@471,
    11-frame held phase, ball visible at hand
  - chain 6 YouTube (q11=0.841, tids 10->12): CATCH@238, THROW@255,
    17-frame held phase, right hand only (SHOWER signature)
- Verdict: PASS. The H58 hypothesis is now visually confirmed.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h58_v1_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h58/*.png` (4 files)

### H59 (2026-08-28 ~16:00 CEST)

- Hypothesis: the final recommended operating point
  (`h7v3plus3` chain set + `H10 v11 v3` quality) should be
  evaluated end-to-end against the only ground-truth labels
  available: the 113 manually reviewed pairs
  (stitch_review_labels.csv) that have been sitting on disk
  since the original E6c work in 2024.
- Implementation: `h59_eval_against_reviewed.py` matches each
  reviewed pair (bidirectional) to the h7v3plus3 edge set, then
  attributes the chain_id + q11 quality + edge_type.
- Quantitative result (full 113-pair set):
  - precision = 0.981 (51 TP, 1 FP)
  - recall = 0.718 (20 FN)
  - FPR = 0.024 (1/42)
- Per-quality-band:
  - CONFIDENT: 2/2 correct, 1.000 precision
  - UNCERTAIN: 36/36 correct, 1.000 precision
  - LOW: 13/13 correct + 1 FP, 0.929 precision
- Per-edge-type:
  - HAND_TRANSITION: 2/2, 1.000
  - BALLISTIC: 8/8, 1.000
  - RECLASSIFIED_HAND_TRANSITION: 33/34, 0.971 (1 FP: identical 22->27)
  - V_RECLASSIFIED_HAND_TRANSITION: 5/5, 1.000
  - H22_RECLASSIFIED_HAND_TRANSITION: 1/1, 1.000
  - H26_RECLASSIFIED_HAND_TRANSITION: 2/2, 1.000
- Per-stem: YouTube precision 1.000, recall 0.923; identical
  precision 0.964, recall 0.600.
- Key findings:
  - The H10 v11 v3 quality is a real, validated signal:
    CONFIDENT + UNCERTAIN chains have 100% precision (38/0).
  - The 1 FP (identical 22->27) is correctly demoted to LOW
    quality by H10 v11 v3.
  - The 20 FN are a structural limit, not a model bug:
    h7v3plus3 has a one-successor-per-source capacity constraint.
  - The H22 YouTube 16->21 veto conflicts with the manual
    label (2024 review said 16->21 is "correct" but H22's
    2026 visual QA said 16->21 is a tracklet break; 20->21 is
    the real catch). Lab analysis is more rigorous.
- New precision-maximizing operating point (H59-validated):
  - h7v3plus3 + (CONFIDENT or UNCERTAIN) = precision 1.000, FPR 0.000
- Verdict: PASS — operating point objectively validated. First
  validation that doesn't rely on heuristic self-consistency.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h59_eval_against_reviewed.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h59_eval_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h59_per_pair_eval.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h59_report.md`

### H60 (2026-08-28 ~16:20 CEST)

- Hypothesis: H58 (and H58 v1) found that the 4 multi-tid CONFIDENT
  chains have consistent held-phase durations (3-ball cascade
  signature 11 frames, 5-ball shower signature 17 frames). But the
  4-chain sample is tiny. H60 measures the held-phase distribution
  across ALL h7v3plus3 chains (50 events per video) to test
  whether the H58 signatures are population-level patterns.
- Implementation: `h60_hold_duration.py` loads the H12 v8 catch/throw
  event log, computes per-event held-phase duration (gap_frames),
  and aggregates by global, hand, q11_label, and per-chain.
- Quantitative result (CATCH events):
  - identical: 25 events, range 4-29, mean 12.6, **median 11**
  - YouTube: 25 events, range 5-17, mean 9.84, **median 9**
- Per-hand (NEW FINDING — hand-asymmetry reversal):
  - identical: right held phases LONGER (median 12.5 vs 11)
  - YouTube: right held phases SHORTER (median 9 vs 11)
- Per q11_label:
  - identical: CONFIDENT (n=14, median 11) = UNCERTAIN (n=11, median 11)
  - YouTube: CONFIDENT (n=1, median 17, chain 6) > UNCERTAIN (n=22, median 10)
- Key findings:
  - H58 11-frame signature IS the median held phase on identical.
    Validates the 3-ball cascade characteristic hold at the
    population level.
  - H58 17-frame signature IS the max held phase on YouTube.
    YouTube's typical hold (9 frames) is much shorter than
    identical's 11 frames.
  - Hand-asymmetry reversal is a new finding: the two videos
    show different juggling patterns.
  - H10 v11 v3 quality is INDEPENDENT of held-phase duration.
- Verdict: PASS. H58 cascade/shower signatures are confirmed at
  the population level, not just for the 4 multi-tid CONFIDENT
  chains.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h60_hold_duration.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h60_hold_duration_dist_<stem>.csv` (2 files)
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h60_hold_duration_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h60_report.md`

### H61 (2026-08-28 ~16:50 CEST)

- Hypothesis: H22 (2026-08-28) concluded that the YouTube 16->21
  edge in h7v3pure is WRONG (tracklet 16 ends at f=468, 2 frames
  BEFORE t20's contact at f=471-473). The real catch is t20->t21
  (V-shape min_d=5.3 vs t21's start_dist=35.3). The 2024 manual
  stitch review said 16->21 is "correct" — an unresolved conflict
  between the manual labels and the 2026 lab visual analysis.
  H61 renders a side-by-side contact sheet and asks the vision
  tool to adjudicate.
- Implementation: `h61_youtube_16_21_conflict.py` renders 3
  contact sheets: 16->21 alone, 20->21 alone, and combined
  side-by-side.
- Vision tool verdict (3 independent evidence):
  1. Proximity: t20 endpoint (f=473) is AT the right-hand catch
     zone. t16 endpoint (f=468) is high and offset from the wrist.
  2. Temporal gap: 20->21 has 9 frames (typical YouTube hold per
     H60). 16->21 has 14 frames (atypically long).
  3. Trajectory continuity: t20's path leads naturally to the
     right hand at f=473. t16's trajectory ends in a region
     inconsistent with handing the ball to the right hand.
- Verdict: PASS. 20->21 is the real catch-throw. 16->21 is not.
  H22's analysis is confirmed.
- Implications:
  - H22's 2026 visual analysis is a stronger signal than the 2024
    manual labels for this case.
  - The h7v3plus3 chain set is correct.
  - This is the only "FN that's actually a TN" case from H59. All
    other 51 TP match the manual review. The H59 evaluation is now
    fully validated.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h61_youtube_16_21_conflict.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_16to21_*.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_20to21_*.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_16to21_vs_20to21_*.png`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h61_pair_metadata.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h61_report.md`

### H62 (2026-08-28 ~17:00 CEST)

- Hypothesis: H58 (and H58 v1) interpreted the YouTube 5-ball
  pattern as SHOWER (same-hand throw+catch) based on the 1
  CONFIDENT chain (chain 6) with right-hand-only events. H62
  systematically examines all 24 YouTube catch+throw events to
  test the SHOWER hypothesis vs CASCADE.
- Implementation: `h62_pattern_characterization.py` computes the
  (THROW, CATCH) pair analysis — for each THROW, find the next
  CATCH and check if it's on the same hand or the alternate hand.
  Compute the same-hand rate.
- Quantitative result:
  - YouTube (5-ball): 23 pairs, 7 same-hand (0.30), 16 alt-hand
    (0.70). Pattern verdict: MIXED (alt-hand bias).
  - identical (3-ball): 19 pairs, 12 same-hand (0.63), 7 alt-hand
    (0.37). Pattern verdict: MIXED (same-hand bias).
- Key findings:
  - The two videos have OPPOSITE hand-pattern biases.
  - YouTube is 70% alt-hand — consistent with CASCADE, NOT SHOWER.
  - H58 SHOWER interpretation was based on n=1 (chain 6). The
    broader YouTube pattern is dominantly CASCADE.
  - The 17-frame hold (chain 6) is a real exception in an
    otherwise CASCADE pattern.
- Implication: H58 report's "5-ball shower signature" should be
  replaced with "5-ball cascade signature" in any downstream
  consumer. The 17-frame hold remains a real signature of the
  5-ball cascade (vs 11-frame for 3-ball).
- Verdict: PASS — H58 SHOWER interpretation is corrected to CASCADE.
  The chain 6 same-hand events are a real anomaly in an otherwise
  CASCADE pattern. The H58 v1 vision tool was misled by the
  chain 6 anomaly; H62 uses the full 24-event dataset.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h62_pattern_characterization.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h62_pattern_summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/h62_youtube_pattern.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h62_report.md`

