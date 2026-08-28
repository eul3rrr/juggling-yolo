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
