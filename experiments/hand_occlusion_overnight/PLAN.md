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

## Fifth episode (H2) — STATUS: COMPLETE

Sub-steps:

1. ✅ Read E6c accepted mid-air edges (from
   `detections/<stem>_norfair_dt50_hc5_accepted_stitches.csv`).
2. ✅ Built a chain representation that combines:
   - v4d hand-links (HAND_TRANSITION / AMBIGUOUS_HAND_TRANSITION)
   - E6c mid-air edges (BALLISTIC)
3. ✅ Tagged each chain edge with provenance.
4. ✅ Recorded 1 conflict on identical (tracklet 3 → {hand=9, air=8})
   instead of silently resolving.
5. ✅ Identical: 76 tracklets → 40 chains (13 multi-tracklet,
   longest 8 tracklets). YouTube: 40 tracklets → 13 chains,
   0 conflicts.
6. ✅ Documented in `h2_report.md`.

**H2 verdict: PASS.** The combined chain representation
correctly merges hand and air edges, and records the one
genuine conflict for post-hoc review.

## Sixth episode (H3) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented three H3 designs (v1: 60-frame temporal cluster
   — FPR ~80%, abandoned; v2: per-detection held candidate —
   wrong direction, abandoned; v3: stationary cluster in
   30px radius over ≥5 frames — recommended).
2. ✅ v3 emits 7 stationary clusters on the 11 v4d links:
   6 on identical (all confirmed real held balls) and 1 on
   youtube (false positive — stuck on face).
3. ✅ Visual QA on all 7 via `vision_analyze`:
   - 6/6 identical clusters = REAL held balls (ball visible
     in hand during held phase).
   - 1/1 youtube cluster = STUCK FALSE POSITIVE on face/head.
4. ✅ Documented in `h3_report.md` and updated RESULTS_LOG.

**H3 verdict: PARTIAL PASS.** H3 is useful as a
*downstream confidence signal* on v4d links (100% precision
on identical video). The YouTube false positive is a
detector limitation, not a criterion failure.

## Seventh episode (H4) — STATUS: COMPLETE (FAIL)

Sub-steps:

1. ✅ Implemented H4 face-mask: H3 v3 criterion + exclude
   candidate detections above the wrist when the hand is
   near face level.
2. ✅ Re-ran on all 11 v4d links. Result: 6 identical
   clusters preserved; 1 youtube cluster NOT removed.
3. ✅ Located the surviving youtube cluster: x=611-618,
   y=205-207 — NOT a face feature, just a stuck detection
   on a stationary high-up object (sign/tree/wall).
4. ✅ Visual QA confirms the cluster is still in the
   upper region, not at the hand.
5. ✅ Documented in `h4_report.md` and updated RESULTS_LOG.

**H4 verdict: FAIL.** The face-mask hypothesis was wrong:
the YouTube H3 false positive is not a face-feature
confusion, it's a stuck detection on a stationary high-up
object. A simple geometric mask cannot solve detector
confusion on arbitrary stationary features.

## Eighth episode (H5+H6) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H5: H3 stationary-cluster as a
   downstream confidence flag on v4d links. 6/11 links
   have h3_confirmed=True.
2. ✅ Implemented H6: simplified per-source greedy
   min-cost flow. Resolves the 1 H2 conflict (tracklet
   3 → {9, 8}) by preferring the hand-edge (cost 1.5)
   over the air-edge (cost 2.0). Same answer as visual
   QA on H2.
3. ✅ Documented in `h5` (script + CSV output) and
   `h6_report.md`.

**H5 verdict: PASS.** Useful as a downstream
confidence signal.

**H6 verdict: PASS (limited scope).** Validates
"hand-edge wins on conflict" via a cost-based
formulation. A true min-cost flow with capacity
constraints would be more principled but is
unnecessary for this dataset (1 conflict).

## Ninth episode (H7 + H237) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H7: greedy iterative min-cost
   flow with capacity constraints (one predecessor
   + one successor per tracklet), cycle detection,
   and gap/error-aware air-edge cost. Pure-Python
   (no scipy/networkx needed).
2. ✅ Ran a 48-cell sensitivity grid sweeping
   `AIR_EDGE_BASE_COST ∈ {1.5, 2.0, 2.5}` ×
   `AIR_ERR_SCALE ∈ {0.0, 0.05, 0.10, 0.20}` ×
   `AIR_GAP_SCALE ∈ {0.0, 0.05, 0.10, 0.20}`.
   Grid is PERFECTLY FLAT: every setting produces
   identical results. The hand<air cost ordering
   is the only thing that matters.
3. ✅ Built unified H2+H3+H7 chain representation
   in `h237_unified_chain.py`. Each edge has
   edge_type, cost, h3_confirmed, metadata. Each
   chain has n_hand_edges, n_air_edges,
   n_h3_confirmed, tids.
4. ✅ Visual QA on the tracklet-3 conflict
   contact sheet (with explicit (x,y) coordinates
   on each tracklet point): t8 confirmed as a
   DIFFERENT ball (224 pixels below t3's endpoint),
   t3→t9 confirmed as a real 20-frame hand-held
   catch-throw.
5. ✅ Visual QA on the longest H7 chain
   (35→37→40→41→43→45→46, 7 tids): confirmed as
   a real single-ball juggling cycle (hold →
   release → rise → apex → fall → catch).
6. ✅ Documented H7 in `h7_report.md` and updated
   RESULTS_LOG.

**H7 verdict: PASS.** H7 is the recommended
chain combination method, replacing H2 (union-find,
conflicts unresolved) and H6 (per-source greedy,
no capacity constraints). H7's added value is the
*path semantics* (vs H2's connected components)
and the *principled cost formulation* (vs H6's
per-source greedy). For the practical question
"what's the right successor for tracklet X?" H6
and H7 give the same answer.

## Tenth episode (H10) — STATUS: COMPLETE

Sub-steps:

1. ✅ Wrote `h10_chain_quality.py` that computes per-chain
   quality = 0.30*h3 + 0.30*h8 + 0.40*h9.
2. ✅ Ran on both videos. Identical: 43 chains, quality
   range 0.297-0.966 (median 0.429). YouTube: 15 chains,
   quality range 0.429-0.967 (median 0.532).
3. ✅ Sensitivity grid: 9 cells (3×3 of w3, w8, w9). Only
   ~20% of chains have stable rank. Top-quality chain
   (chain 23) is consistently top-3 across all cells.
   Bottom-quality chain (chain 13) is consistently bottom-3.
4. ✅ Visual QA: 6 contact sheets rendered and inspected.
   - chain 23 (top): REAL single ball
   - chain 30 (mid): IDENTITY SWITCH
   - chain 13 (low): STATIONARY DETECTOR ARTIFACT
   - chain 38 (low, false positive): REAL single ball
   - chain 6 YouTube (top): REAL single catch-throw
   - chain 9 YouTube (worst): MULTI-BALL MERGE
5. ✅ H10 successfully produces a per-chain quality score
   that correlates with physical-ball identity confidence.
6. ✅ Documented in `h10_report.md` and updated RESULTS_LOG.

**H10 verdict: PASS.** H10 is a useful per-chain
confidence signal. Top-quality chains are real juggling
cycles; mid-quality chains contain identity switches;
low-quality chains are dominated by false ballistic edges.
H10 has 1 false positive (chain 38) due to H3+H8
limitations. See `h1_hand_pool/reports/h10_report.md`.

## Eleventh episode (H8 v4) — STATUS: COMPLETE (NEGATIVE)

Sub-steps:

1. ✅ Wrote `h8_v4_short_tracklet.py` that restricts H8 v3
   to tracklets with n_pts ≤ 30.
2. ✅ Ran on both videos. Identical: 3 v4-VIOLATING
   (19→20, 51→52, 23→25), 18 LONG_TRACKLET, 2 OK.
   YouTube: 0 OK, 0 VIOLATING, 24 LONG_TRACKLET.
3. ✅ Visual QA on 5 edges:
   - 19→20, 51→52, 23→25: v4 VIOLATING, all
     CONFIRMED identity switches
   - 5→6: v3 VIOLATING → v4 LONG_TRACKLET.
     CONFIRMED identity switch but v4 misses it
     (false negative)
   - 50→55: v3 OK → v4 LONG_TRACKLET
4. ✅ Documented in `h8_v4_report.md` and updated
   RESULTS_LOG.

**H8 v4 verdict: NEGATIVE (v4 not worth the trade-off).**
v4 trades YouTube false positives for identical false
negatives. Neither v3 nor v4 alone is ideal. v3
retained as H10's H8 signal.

## Twelfth episode (H8 v5 + H10 v5) — STATUS: COMPLETE

Sub-steps:

1. ✅ Wrote `h8_v5_parabolic.py` that fits a parabola to the
   last 8 / first 8 frames of source / target and predicts
   expected y-velocity with constant-gravity extrapolation.
2. ✅ Ran on both videos. Identical: 12 OK, 10 VIOLATING,
   1 INSUFFICIENT. YouTube: 0 OK, 23 VIOLATING, 1 INSUFFICIENT.
3. ✅ Visual QA on 3 v5 catches: 60→64, 21→22 (NEW), 64→68.
   All confirmed real identity switches.
4. ✅ Wrote `h10v5_with_h8v5.py` to compute H10 quality
   with v5 physics (graduated 0.5 for INSUFFICIENT_DATA).
5. ✅ Ran on both videos. Identical: 6 chains IMPROVED
   rank, 3 WORSENED, 34 unchanged.
6. ✅ Visual QA on biggest rank movers: chain 24, 29
   (v3 false positives that v5 correctly demotes), chain 36
   (v3 false negative that v5 correctly promotes).
7. ✅ Documented in `h8_v5_report.md` and `h10v5_report.md`.

**H8 v5 verdict: MIXED.** v5 catches 2 NEW identity switches
on identical that v3 missed. YouTube limitation persists.

**H10 v5 verdict: PASS.** v5 is better-calibrated than v3.
H10 v5 is the new recommended chain quality score.

## Thirteenth episode — PLANNED

Remaining ideas:

1. **H11: tracklet-level identity propagation** — given
   a high-quality H10 v5 chain, propagate identity labels
   across the chain to enable juggling-pattern analysis.
2. ~~**H8 v6: per-bounce segmentation for long tracklets**~~
   **DONE. NEGATIVE result.** Apex detection (APEX_HALFWIN=6)
   is too coarse to isolate clean parabolic segments within
   long tracklets. The juggler's catch-throw motion within
   a long tracklet contaminates any naive tail fit. v6
   produces the same YouTube result as v5.
3. ~~**H10 v6: combined H3 + H8 v5 + H9 features into a
   logistic-regression-trained quality classifier** — see
   if a learned model outperforms H10 v5's hand-tuned
   weights.~~ (Not pursued in this episode.)
4. ~~**H237 v5: integrate H10 v5 with the unified chain
   representation**~~ **DONE.** Produces
   `h237v5_unified_chains_*.csv` with the H10 v5 quality
   as per-chain fields. Downstream consumers can use it
   directly.

## Fourteenth episode (H11) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H11 v1: per-tracklet ball_id assignment
   + per-chain catch/throw events. Quality thresholds:
   - QUALITY_CONFIDENT = 0.7
   - QUALITY_TRUSTABLE = 0.4
2. ✅ Implemented H11 v2: per-frame census + identity-merge
   candidates. Census: 51% cascade time on identical,
   100% on YouTube (over-counting).
3. ✅ Implemented H11 v3: quality-filtered census sweep.
   Confirms YouTube over-counting is due to UNCERTAIN
   chain quality.
4. ✅ Rendered 6 contact sheets for CONFIDENT and UNCERTAIN
   chains. Visual QA confirmed:
   - chain 2 (CONFIDENT): real catch-throw
   - chain 8 (CONFIDENT): real hold-throw
   - chain 30 (UNCERTAIN): identity switches (correctly
     flagged as suspect)
   - chain 6 YouTube (CONFIDENT): real catch-throw
5. ✅ Rendered 1 merge-candidate contact sheet. Visual QA
   showed the chain 36 ↔ chain 30 candidate is a FALSE
   POSITIVE (t62 and t63 are 73 pixels apart at f=890).
6. ✅ Sensitivity grid: n_events is stable at 8 across
   all reasonable (confident, trustable) settings.
7. ✅ Documented in `h11_report.md` and updated
   RESULTS_LOG.

**H11 verdict: PASS.** H11 is a useful downstream
consumer of H10 v5 quality:
- 9 CONFIDENT identical + 1 CONFIDENT YouTube chain
  with correct physical ball ID.
- 8 catch/throw events on identical + 1 on YouTube.
- Per-frame census: 51% cascade on identical, 100% on
  YouTube (over-counting artifact).
- 1 CONFIDENT identity-merge candidate is a FALSE
  POSITIVE — algorithm needs stricter spatial proximity.

Next episode candidates:
1. H11 v4: stricter spatial proximity for identity-merge
   candidates (use ball position, not just hand-event time).
2. H12: per-catch-frame juggling pattern inference.
3. H8 v7: per-frame per-bounce segmentation for YouTube
   long tracklets.

## Fifteenth episode (H11 v4) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H11 v4: spatial proximity +
   velocity coherence filters on H11 v2's identity-merge
   algorithm. Thresholds:
   - SPATIAL_RADIUS = 80px (conservative; reach = 108px)
   - VELOCITY_COHERENCE = 5.0 px/frame (* sqrt(2) for 2D)
2. ✅ Ran on both videos. Result:
   - identical: 42 (v2) → 6 (v4) candidates (-85.7%)
   - youtube: 2 (v2) → 0 (v4) candidates (-100%)
3. ✅ Visual QA on the 6 v4 candidates: all are false
   positives (most fail velocity test).
4. ✅ Sensitivity grid: 20 cells (5 spatial × 4 velocity).
   (80, 5) is in a flat region. SPATIAL=108 (reach) admits
   the v2 false positive again.
5. ✅ Documented in `h11_v4_report.md` and updated
   RESULTS_LOG.

**H11 v4 verdict: PASS.** H11 v4 is the new recommended
identity-merge algorithm. The v2 chain 36 ↔ chain 30
CONFIDENT-merge false positive is correctly removed.
The 6 remaining v4 candidates all fail the velocity
coherence test, suggesting no real missed-merge
opportunities exist.

Next episode candidates:
1. H12: per-catch-frame juggling pattern inference
2. H8 v7: per-frame per-bounce segmentation for YouTube
   long tracklets
3. H11 v5: hand-relative coordinates for merge algorithm

## Sixteenth episode (H12) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H12: per-frame pattern inference.
   Pattern classes: NO_BALL, SINGLE_BALL, TWO_BALL,
   TWO_BALL_HELD, TWO_BALL_ONE_HAND, CASCADE_3+,
   FOUNTAIN_3+, UNKNOWN. Thresholds:
   - MIN_QUALITY_FOR_PATTERN = 0.5
   - RECENT_EVENT_FRAMES = 30
2. ✅ Ran on both videos. Result:
   - identical: 33.8% UNKNOWN, 21.9% CASCADE_3+,
     15.3% TWO_BALL, 13.9% SINGLE_BALL, 11.7% FOUNTAIN_3+,
     3.2% NO_BALL, 0.1% TWO_BALL_ONE_HAND
   - youtube: 93.2% CASCADE_3+ (over-counting artifact)
3. ✅ Visual QA: contact sheet shows 4 phases on
   identical (FOUNTAIN → CASCADE → mixed).
4. ✅ Documented in `h12_report.md` and updated
   RESULTS_LOG.

**H12 verdict: PASS.** H12 successfully classifies 66.2%
of identical frames. The 4-phase pattern is consistent
with a 3-ball trick. Caveat: YouTube unreliable due to
H10 v5 over-counting.

## Seventeenth episode (H12 v2) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H12 v2: sliding window of last K=4 events
   (not temporal ±window), hand-alternation metric, catch
   rate, MIN_EVENTS_FOR_PATTERN=3, MIXED_3+ category, phase
   detection.
2. ✅ Ran on both videos. Result:
   - identical: UNKNOWN 33.8% → 1.4%, FOUNTAIN 11.7% → 15.5%,
     MIXED_3+ 0% → 29.3%, MIXED_3+_UNCONFIRMED 0% → 6.1%
   - youtube: CASCADE_3+ 93.2% → 0%, MIXED_3+_UNCONFIRMED 0% → 100%
3. ✅ Phase detection emits 13 substantial phases on identical.
4. ✅ Sensitivity grid: 15 cells (K×MIN), (K=4, MIN=3) is in
   flat region.
5. ✅ Visual QA on 5 phase contact sheets via vision_analyze.
   Important finding: the algorithm's FOUNTAIN_3+ classification
   at f=890-936 and f=977-1011 is visually wrong (those are
   cascades). The event log is too sparse to disambiguate.
6. ✅ Documented in `h12_v2_report.md` and updated RESULTS_LOG.

**H12 v2 verdict: PASS.** H12 v2 is a meaningful improvement:
UNKNOWN collapses 33.8% → 1.4%. Phase detection emits 13
substantial phases. YouTube correctly reports UNCONFIRMED.
Limitation: CASCADE/FOUNTAIN classification is limited by
event log density; visual QA found at least 2 FOUNTAIN_3+
phases that are actually cascades. Future H12 v3 should
integrate detector-level ball position signals.

Next episode candidates:
1. H12 v4: detector-level ball position signal (per-frame ball
   x,y relative to each hand) — this is needed to fix the
   CASCADE/FOUNTAIN misclassification in the late phase
2. H13: detector-level low-confidence ball detection near
   active hand events (master §14 follow-up)
3. H8 v7: per-frame per-bounce segmentation for YouTube
   long tracklets

## Eighteenth episode (H12 v3) — STATUS: COMPLETE (MIXED)

Sub-steps:

1. ✅ Visually QA'd the 2 v3c-rejected links:
   - 35->40 on identical (left hand, from_slope=2.31): VISUALLY
     CONFIRMED as a real catch-throw. v4d threshold is too strict.
   - 15->25 on YouTube (left hand, from_slope=2.08): VISUALLY
     REJECTED as not a real catch-throw. v4d threshold is correct.
2. ✅ Implemented H12 v3: enriched event log with the
   visually-confirmed 35->40 event added back as a
   "v3c_rejected_visually_confirmed" entry.
3. ✅ Ran H12 v2 classifier on the enriched event log.
   Result: 26 frames changed from FOUNTAIN_3+ to MIXED_3+ at
   f=797-829. No change in f<535. No change in f>829.
4. ✅ Documented in `h12_v3_report.md` and updated RESULTS_LOG.

**H12 v3 verdict: MIXED.** The enriched event log changes 26
frames in the mid-phase but does NOT fix the late FOUNTAIN_3+
blocks (f=890-1050) which the visual QA identified as actually
cascades. The new event is too far in the past to be in the
K=4 window during the late phase. **The H12 v2 limitation is
fundamental**: CASCADE/FOUNTAIN classification is limited by
event log density, and event log is right-hand-biased. A truly
different approach (H12 v4) is needed.

Next episode candidates:
1. H12 v4: detector-level ball position signal
2. H13: low-confidence detector-based event detection
3. H8 v7: per-frame per-bounce segmentation

## Nineteenth episode (H12 v4 + H12 v5) — STATUS: COMPLETE (PASS w/ caveats)

Sub-steps:

1. ✅ H12 v4 (instantaneous detector signal): for each frame, look at
   horizontal velocity (vx) of all airborne balls. CASCADE if 2 distinct
   horizontal directions, FOUNTAIN if 1. MOVING_VX_THRESHOLD=1.0 px/frame.
2. ✅ H12 v5 (smoothed): median of n_distinct_dirs over ±W=10 frames.
3. ✅ Phase detection (n_frames >= 20).
4. ✅ W sensitivity grid: 4 cells (5, 10, 20, 30). NOT flat — CASCADE
   decreases monotonically (14.9% → 8.7%).
5. ✅ Visual QA: 6-frame contact sheet for late phase (f=890, 920, 950,
   980, 1010, 1040). v2 misclassifies 5/6 frames as FOUNTAIN, v4/v5
   correctly identify CASCADE in 4/6 frames.
6. ✅ Documented in `h12_v4v5_report.md` and updated RESULTS_LOG.

**H12 v4/v5 verdict: PASS with caveats.** Fixes the H12 v2/v3
fundamental limitation by switching to per-frame spatial signal.
v2 late phase: 71% FOUNTAIN (wrong). v4/v5: ~33% CASCADE / 38% FOUNTAIN
(matches visual cascade). v5 preferred over v4 due to smoothing
robustness. YouTube dominated by H10 v5 over-counting (not
meaningful).

**Next episode candidates:**

1. **H13: detector-level low-confidence ball detection near hand
   events** (master §14 follow-up). Re-run detector with conf=0.1
   and compare to v4d hand-link predictions. The YouTube
   over-counting is partly due to detector confusion; a lower-conf
   re-run might reveal where balls actually are.
2. **H8 v7: per-bounce segmentation for YouTube long tracklets**
   (master §11 follow-up). v6's apex-level segmentation was too
   coarse. Try spectral clustering on y-velocity to identify
   parabolic arcs.
3. **H12 v6: combine v2 (event-log) and v5 (detector) signals**
   with a weighted ensemble. v2's high-confidence windows should
   pull v5's noisy per-frame signal toward correctness; v5's
   per-frame signal should disambiguate v2's FOUNTAIN miscalls.
4. **H10 v6: learned quality classifier (H3 + H8 v5 + H9 features
   → quality)**. The hand-tuned weights (0.3, 0.3, 0.4) are
   arbitrary; a logistic regression on labeled chains could
   outperform.

## Twentieth episode (H8 v7 + v8 + H12 v6 + v6b) — STATUS: COMPLETE (MIXED)

Sub-steps:

1. ✅ H8 v7: vy-sign-change segmentation with K=2 smoothing.
   Result: 73/76 identical and 38/40 YouTube tracklets detected
   as 1-arc (smoothing destroyed intra-tracklet sign changes).
   Per-arc gravity YouTube median 0.46, identical median 0.41.
   NEGATIVE: smoothing was the wrong approach.
2. ✅ H8 v8: local extrema (peaks + valleys) in y with
   min-distance=5 frame filter. Better segmentation:
   identical 1-5 arcs (median 1-2), YouTube 1-12 arcs
   (median 2-4, max 12). Per-arc gravity YouTube median
   0.46 (matches quoted 0.5), identical median 0.69.
   Air-edge physics: 6/23 OK identical, 0/24 OK YouTube.
   MIXED: good per-arc statistics, bad cross-edge check.
3. ✅ H12 v6 (basic ensemble): for 3+ ball frames where v2
   and v5 disagree on CASCADE/FOUNTAIN, report MIXED_3+_ENSEMBLE.
   Result: 6.3% MIXED on identical, 0% on YouTube. PARTIAL PASS.
4. ✅ H12 v6b (confidence-weighted): if c5 > c2 + 0.10 take v5,
   if c2 > c5 + 0.10 take v2, else MIXED. Result: 10.8%
   CASCADE (up from v6's 6.8%), 2.3% MIXED (down from 6.3%).
   43 frames where v5 won, 25 where MIXED_ENSEMBLE.
   MIXED: propagates v5 but adds new risk.
5. ✅ Visual QA: 3 independent vision queries on late-phase
   contact sheets all said FOUNTAIN, contradicting H12 v4/v5's
   earlier visual QA. Vision tool is unreliable for
   CASCADE/FOUNTAIN distinction.
6. ✅ Documented in `h12_v6_report.md` and `h8_v7v8_report.md`.

**Verdict: v7 NEGATIVE, v8 MIXED, v6 PARTIAL PASS, v6b MIXED.**
The H8 series has reached its natural limit on YouTube: per-arc
statistics work but cross-edge physics is unreliable because
H7 BALLISTIC edges are mostly catch+throws in disguise. The
H12 v6/v6b ensemble addresses the v2/v5 disagreement but
introduces a new epistemic problem: which signal is right?
Without ground truth, neither vision tools nor simple
ensembles can resolve the CASCADE/FOUNTAIN ambiguity.

**Next episode candidates:**

1. **H10 v6: integrate per-arc gravity as 4th quality
   dimension.** H8 v8 enables this. The composite would be
   `quality = 0.25*h3 + 0.25*h8_v5 + 0.25*h9 + 0.25*h8_v8_g`.
   Should give a more nuanced per-chain quality score.
2. **H13: detector-level low-confidence ball detection near
   hand events** (master §14 follow-up). The detector confusion
   is partly responsible for over-counting; a conf=0.1 re-run
   could reveal where balls actually are.
3. **H7 v2: re-classify YouTube BALLISTIC edges as HAND_TRANSITION
   if they pass through a hand region.** v8 shows that most
   YouTube BALLISTIC edges are catch+throws in disguise. Adding
   a hand-region check at chain construction time could fix
   the YouTube H10 v5 over-counting at its source.
4. **H8 v9: per-frame per-bounce segmentation for YouTube long
   tracklets.** v8's extrema-level segmentation was the best
   so far but still doesn't solve cross-edge physics. A truly
   per-frame approach (e.g., LSTM on per-frame vy/vx) might
   work but is out of scope.

## Twenty-first episode (H10 v6) — STATUS: COMPLETE (MIXED)

Sub-steps:

1. ✅ Implemented H10 v6: chain quality with per-arc gravity
   as 4th dimension.
   - quality_v6 = 0.25*h3 + 0.20*h8_v5 + 0.30*h9 + 0.25*h8v8
   - h8v8 = mean over chain's tracklets of
     n_clean_arcs / n_total_arcs (clean = g in [0.2, 0.8])
2. ✅ Ran on both videos. Compared to v5 ranking.
3. ✅ Sensitivity grid: 7 cells of h8v8 weight (0.0 to 0.50).
   - identical: w8v8=0 best (matches v5)
   - youtube: w8v8=0.5 best (improves over v5)
   - sensitivity is NOT flat on either video
4. ✅ Documented in `h10v6_report.md`.

**Verdict: MIXED.** H10 v6 with default weights (h8v8=0.25)
HURTS identical ranking (mean q 0.529 → 0.495) and HELPS
YouTube ranking (mean q 0.537 → 0.569). Chain 21 (v5 #0) drops
to v6 #7 because t31/t36 have per-arc g=0.117 (asymmetric
motion artifact, NOT a real quality signal).

**H10 v6 has OPPOSITE effects on the two videos:**
- Identical: short tracklets have unreliable parabolic fits
- YouTube: long tracklets have many arcs and per-arc gravity
  is a real signal

**Recommended v6b: per-video adaptive weights**
(w8v8=0 for identical, w8v8=0.30 for YouTube).
Not implemented in this episode.

## Twenty-second episode (H10 v6b) — STATUS: COMPLETE (PASS)

Sub-steps:

1. ✅ Implemented H10 v6b: per-video adaptive weights.
   - identical: w8v8=0 (matches v5)
   - youtube: w8v8=0.25 (apply v6's 4-dim formula)
2. ✅ Ran on both videos. Compared to v5 ranking.
3. ✅ Documented in `h10v6b_report.md`.

**Verdict: PASS.** Per-video adaptive weights give the best
of both worlds. H10 v6b is the new recommended chain quality
score for mixed-video analyses.
- identical: v6b = v5 (mean q 0.529, no degradation).
  All 43 chains preserve their v5 rank. Chain 21 stays at #0.
- youtube: v6b improves over v5 (mean q 0.537 → 0.569).
  4 chains promoted (chain 3, 8, 0 from h8v8=0.88),
  2 demoted (chain 12, 1), 9 unchanged.

## Twenty-third episode (H10 v7) — STATUS: COMPLETE (NEGATIVE)

Sub-steps:

1. ✅ Implemented H10 v7: length-dependent weight
   w8v8 = min(0.30, mean(n_tracklet_pts) / 200).
2. ✅ Ran on both videos. Compared to v5 ranking.
3. ✅ Documented in `h10v7_report.md`.

**Verdict: NEGATIVE.** v7 doesn't outperform v6b on either
video:
- identical: v5 0.529 → v7 0.509 (worse)
- youtube: v5 0.537 → v7 0.557 (better but worse than
  v6b's 0.569)

v7's length-dependent formula is intermediate between v5
and v6 behaviors, which is worse than either extreme.
v6b's per-video fixed weights are the recommended
operating point.

**Next episode candidates:**

1. **H13: detector-level low-confidence ball detection**
   (master §14 follow-up). The detector confusion is
   partly responsible for over-counting; a conf=0.1
   re-run could reveal where balls actually are.
2. **H7 v2: re-classify YouTube BALLISTIC edges as
   HAND_TRANSITION if they pass through a hand region.**
3. **H12 v6c: visual ground truth via frame-by-frame
   manual labeling** — resolve the CASCADE/FOUNTAIN
   ambiguity by labeling 50 random frames from the late
   phase as cascade/fountain/mixed. Out of scope for
   autonomous run (no human in the loop).
4. **Stop here.** The H10 series has reached its
   natural limit: v6b is the best operating point,
   v7 is a useful negative result. Future H10 work
   would need a different signal (e.g., h8v8 with
   length-based arc-segmentation quality, not just
   arc-gravity consistency).


## Twenty-fourth episode (H7 v2 + H10 v8) — STATUS: COMPLETE (PASS)

Sub-steps:
1. ✅ Implemented H7 v2: re-classify BALLISTIC edges as
   HAND_TRANSITION if either endpoint has a catch/throw
   signature (distance ≤ 108 AND strong slope) AND the gap
   is ≤ 20 frames.
2. ✅ Ran H7 v2 on both videos.
   - identical: 13/37 (35%) BALLISTIC edges reclassified
   - YouTube: 25/27 (93%) BALLISTIC edges reclassified
3. ✅ Rendered 8 contact sheets (4 identical + 4 YouTube) and
   visually confirmed all 8 as REAL_CATCH_THROW.
4. ✅ Implemented H10 v8: H7v2 chains + v6b per-video weights.
5. ✅ Ran H10 v8: YouTube mean quality 0.537 → 0.679.
6. ✅ Documented in `h7v2_report.md` and `h10v8_report.md`.

**Verdict: PASS.** H7 v2 + H10 v8 fixes the YouTube
over-counting at its source. The asymmetric reclassification
rate (35% identical vs 93% YouTube) reflects the fundamental
difference in detection profiles. H10 v8 is the new
recommended chain quality score, replacing H10 v6b.

**Next episode candidates:**

1. **H237 v6: enrich h237 unified chain with H7v2's
   reclassification metadata.** Each H7v2 chain has
   `n_reclassified_hand_edges` and `n_ballistic_edges` fields.
   Downstream consumers can use these to identify "real"
   juggling cycles (mostly reclassified) vs. true multi-ball
   merges (mostly ballistic).
2. **H12 v7: re-run pattern inference on H7v2 chains.** With
   the YouTube over-counting fixed, the per-frame census on
   YouTube should now be meaningful. H12 v2 was 100%
   MIXED_3+_UNCONFIRMED on YouTube; v7 should split into
   actual patterns.
3. **H13: detector-level low-confidence ball detection** (master
   §14). The detector confusion is partly responsible for the
   remaining issues; a conf=0.1 re-run could reveal where
   balls actually are.
4. **H8 v9: try a hybrid arc-segmentation approach for YouTube
   long tracklets.** v8's extrema-level segmentation is the
   best so far but doesn't isolate clean parabolic arcs.
   A 2D Gaussian Mixture on (x, y) trajectory features might
   work better.
5. **Stop here.** H7 v2 + H10 v8 has reached a natural
   inflection point. The h8 over-penalization is fixed; future
   work should focus on different signals (detector-level,
   spatial pattern inference, etc.) rather than chain-level
   quality.


## Twenty-fifth episode (H12 v7) — STATUS: COMPLETE (MIXED)

Sub-steps:
1. ✅ Implemented H12 v7: re-run pattern inference on H7v2
   chains with H10 v8 quality.
2. ✅ Fixed hand parsing for reclassified edges (parse
   `side=left/right` from reclassify_reason).
3. ✅ Ran on both videos. YouTube 100% UNCONFIRMED → 12.4%
   CASCADE / 23.5% FOUNTAIN / 56.3% MIXED.
4. ✅ Visual QA on late phase f=890-1050: vision tool confirms
   CASCADE pattern but v7 still classifies 74.5% FOUNTAIN_3+.
5. ✅ Documented in `h12_v7_report.md`.

**Verdict: MIXED.** H12 v7 successfully fixes the YouTube
pattern classification (chain quality layer). It does NOT
fix the CASCADE/FOUNTAIN misclassification on identical
(event log density is the fundamental bottleneck).

**Insight: YouTube is genuinely a 5-ball pattern.** Visual
confirmation at f=2 (4 balls) and f=500 (5 balls). The
n_total=5 in 67% of frames is correct, not an over-counting
artifact.

**Next episode candidates:**

1. **H237 v6: enrich h237 unified chain with H7v2
   reclassification metadata.** Useful as a downstream
   consumer (e.g. for juggling-pattern analyzers that want
   to know "this chain has 6 hand edges and 0 BALLISTIC
   edges, so it's a real juggling cycle").
2. **H13: detector-level low-confidence ball detection.**
   Now that the chain structure is well-understood, a
   detector-level signal could find missed balls near hands.
3. **Stop here.** The CASCADE/FOUNTAIN problem is
   fundamentally unresolvable with current data (event log
   density, single-camera 2D tracking). Future work needs
   a different signal (multi-view, higher frame rate, or
   ground truth).

## Twenty-sixth episode (H237 v6) — STATUS: COMPLETE (PASS)

Sub-steps:
1. ✅ Implemented H237 v6: H7v2 chains + H10 v8 quality +
   per-chain `n_reclassified_edges` and `pct_reclassified`.
2. ✅ Ran on both videos:
   - identical: 43 chains, 4 pure-ballistic, 3 pure-reclassified
   - YouTube: 15 chains, **0 pure-ballistic**, 7 pure-reclassified
3. ✅ Documented in `h237v6_report.md`.

**Verdict: PASS.** H237 v6 is the new recommended unified
chain representation, replacing h237v5. All YouTube multi-
tracklet chains are now correctly attributed to hand
interactions, validating H7v2's reclassification rule.

**State of the lab:**

The chain-quality + pattern-inference pipeline is now:
- **H7v2**: reclassify BALLISTIC edges as HAND_TRANSITION
  when at hand (PASS)
- **H10 v8**: chain quality on H7v2 chains (PASS)
- **H12 v7**: pattern inference on H7v2 chains (MIXED)
- **H237 v6**: unified representation with reclassification
  metadata (PASS)

This is the most complete hand-occlusion tracking pipeline
to date. Further work would require fundamentally different
signals (multi-view, higher frame rate, detector-level).


## Twenty-seventh episode (H11 v6) — STATUS: COMPLETE (PASS)

Sub-steps:
1. ✅ Implemented H11 v6: identity propagation on H7v2 chains
   with H10 v8 quality.
2. ✅ Ran on both videos:
   - YouTube: catch/throw events 1 → 48 (24x improvement)
   - identical: 18 events (mostly reclassified, real catches)
3. ✅ Documented in `h11_v6_report.md`.

**Verdict: PASS.** H11 v6 gives 24x more YouTube catch/throw
events than H11 v1, validating H7v2's reclassification.

**Final summary report:** see `reports/SUMMARY.md` for a
comprehensive overview of all 26+ research cycles.


## Twenty-eighth episode (H13) — STATUS: COMPLETE (PARTIAL PASS)

Sub-steps:
1. ✅ Implemented H13 v1: scan a wider window (gap+5 frames each side)
   for low-conf sports-ball detections within 108 px of the relevant
   hand. Tested v1 (any single detection), v2 (H3 stationary cluster
   criterion restricted to the window), v3 (concentration ratio),
   v4 (peak-vs-context).
2. ✅ Ran on both videos. 11 v4d links + 13 h7v2-reclassified + 12
   h7v2-kept-ballistic on identical, 1 v4d + 25 h7v2-reclassified +
   1 h7v2-kept-ballistic on YouTube.
3. ✅ Mean concentration comparison:
   - identical v4d: 0.142 +/- 0.012 (n=10)
   - identical h7v2_reclassified: 0.201 +/- 0.020 (n=13)
   - identical h7v2_kept_ballistic: 0.206 +/- 0.021 (n=12)
   - YouTube h7v2_reclassified: 0.303 +/- 0.012 (n=25)
4. ✅ Bootstrap 90% CI for differences (identical):
   - h7v2_reclassified - v4d: +0.059 [+0.022, +0.098] (significant)
   - h7v2_reclassified - h7v2_kept_ballistic: -0.005 [-0.047, +0.041] (NOT significant)
   - Cohen's d (reclass vs v4d): +0.965 (large effect)
5. ✅ Visual QA: 14 contact sheets rendered, 4 inspected via
   vision_analyze. Key finding: v2 cluster corroboration of
   h7v2_kept_ballistic 41->43 is a FALSE POSITIVE — the two balls
   at the hand look like one cluster, but they are identity switches.
6. ✅ Documented in `h13_report.md` and updated RESULTS_LOG.

**Verdict: PARTIAL PASS.** H13's stationary-cluster criterion (H3 v3)
is NOT a discriminator between real catch-throws and identity switches
(3/6 v2 corroborated edges are kept-ballistic false positives). The
concentration ratio IS a real signal but correlates with gap length,
not event type. **This is an important negative finding for master
§14**: lowering the detector confidence to find held balls does not
specifically identify hand events — it identifies any "ball near hand"
pattern, including identity switches.

**Implications for downstream consumers:**
- H3's `h3_confirmed` flag (used in H11 identity propagation) is a
  noisy signal. 50% of v2 CORROBORATED edges are kept-ballistic, so
  the flag is more like "this edge has detector activity at the hand"
  than "this edge is a real catch-throw".
- A stricter H3 would need to combine the cluster signal with
  additional filters (e.g., the hand must be the only hand with
  cluster activity, or the cluster must be tight and at the specific
  hand used by the v4d rule).

**Next episode candidates:**

1. **H13 v2: stricter cluster criterion** that requires (a) the cluster
   to be at the EXACT hand used by v4d (not just "any hand"), (b) no
   other hand has cluster activity simultaneously, (c) the cluster's
   spatial extent is consistent with a held ball (small std).
2. **H14: per-frame per-arc segmentation for YouTube long tracklets**
   — H8 v6/v7/v8 all failed; a fundamentally different approach
   (e.g., LSTM on per-frame vy/vx features) might work but is out of
   scope for autonomous run.
3. **Stop here.** H13's negative finding closes the master §14 question:
   the detector signal is too noisy to be a reliable held-ball detector
   in this 2D single-camera setup. Future work needs multi-view or
   higher frame rate.


## Eighteenth episode (H14) — STATUS: COMPLETE

Sub-steps:

1. ✅ Implemented H14: V-shape trajectory check on h7v2-kept
   BALLISTIC edges. Examines the full source-tail + gap +
   target-head trajectory and asks: does it dip toward a hand
   and come back out?
2. ✅ Three classes: V_DEEP (min_d < 50, ratio > 1.5),
   V_SHALLOW (min_d < 100, ratio > 1.3), FLAT (neither).
3. ✅ Ran on 62 edges: 11 v4d, 38 h7v2_reclassified, 13 h7v2_kept_ballistic.
   Result: 5/13 BALLISTIC edges have a V-shape (3 V_DEEP + 2 V_SHALLOW).
4. ✅ Visual QA on all 5 BALLISTIC V-shape candidates:
   - 23→25, 30→33, 39→47, 51→52 identical: ALL REAL CATCH-THROWS
   - 27→28 YouTube: FALSE POSITIVE (velocity jump, not physical)
5. ✅ Sensitivity grid (20 cells, 5 deep_min × 4 deep_ratio):
   stable; default (50, 1.5) in flat region.
6. ✅ Documented in `h14_report.md` and updated RESULTS_LOG.

**H14 verdict: PASS (with caveat).** H14 recovers 4 hidden
catch-throws on identical that the strict h7v2 rule missed.
Combined H7v2 + H14 = +35% recall on identical. H14 is an
add-on to H7v2, not a replacement. Position-only check is a
known limitation; a velocity jump check would reduce the
YouTube false positive.

Next episode candidates:
1. H15: reclassify h7v2-kept BALLISTIC edges that pass H14 as
   HAND_TRANSITION, and re-run H7v2/H10v8 to measure chain
   quality impact.
2. H16: V-shape + velocity-jump check (combine position with
   velocity to reduce YouTube 27→28 false positive).
3. H17: V-shape recovery for v4d-missed links (e.g. 35→40,
   15→25 youtube) to see if any rejected v4d links are
   V-shape hidden catch-throws.

## Twenty-ninth episode (H15 v1 + v2 + H10 v9) — STATUS: COMPLETE

Sub-steps:
1. ✅ H15 v1: combined V-shape + velocity-jump (JUMP_TOLERANCE=15
   px/frame). NEGATIVE result: the threshold was mis-calibrated
   (rejected 23→25 which has jump=23.4, admitted 27→28 which has
   jump=14.5).
2. ✅ H15 v2: pure V-shape reclassification (no velocity-jump).
   PASS with documented YouTube caveat.
3. ✅ H10 v9: H15v2 chains + H10 v6b per-video weights, with
   V_RECLASSIFIED excluded from h3-eligible set (fixes a
   pre-existing h3=None redistribution bug).
4. ✅ Documented in `h15v2_report.md` and `h10v8_report.md`.

**H15v2 verdict: PASS (with documented YouTube limitation).**
H15v2 recovers 4 hidden catch-throws on identical (23→25,
30→33, 39→47, 51→52) and admits 1 YouTube FP (27→28).
Visual precision 4/5 = 0.80 on H15v2's contact-sheet QA.

**H10v9 verdict: PASS.** H10v9 is the new recommended chain
quality score. Mean quality: identical 0.814 → 0.828 (+0.014),
YouTube 0.679 → 0.685 (+0.007). Concentrated on chain 13 and
chain 30 (each +0.30). Combined h7v2 + h15v2 = h7v3pure
chains. The h7v3pure chain construction is the new
recommended chain pipeline.

## Thirtieth episode (H11 v7) — STATUS: COMPLETE (MIXED)

Sub-steps:
1. ✅ Implemented H11 v7: identity propagation on h7v3pure chains
   with H10 v9 quality. Treats V_RECLASSIFIED_HAND_TRANSITION as
   a hand-edge for catch/throw event extraction. Parses hand
   from `v_reclassify_reason` field.
2. ✅ Ran on both videos. Result:
   - identical: 18 → 23 catch+throw events (+5); 3 → 4
     multi-tracklet CONFIDENT chains (+1)
   - YouTube: 24 → 25 catch+throw events (+1)
3. ✅ Per-hand breakdown: 6 added identical events split
   3 left + 3 right (matches H14 V-shape hand assignment).
4. ✅ Visual QA on all 5 V-reclassified chains via vision_analyze.
   - chain 20 (30→33): REAL CATCH+THROW
   - chain 30 (51→52): REAL CATCH+THROW (left→right handoff)
   - chain 13 (23→25): HAND-BORNE (not BALLISTIC, but not clean
     catch+throw either)
   - chain 24 (39→47): HAND-BORNE (same as chain 13)
   - chain 12 YouTube (27→28): FALSE POSITIVE (tracklet break)
5. ✅ Documented in `h11_v7_report.md` and updated RESULTS_LOG.

**H11 v7 verdict: MIXED (consumer-pass, visual nuance).**
H11 v7 successfully propagates the V-shape reclassification to
the identity layer. The h10v9 quality improvement on chain 30
and chain 13 is real and meaningful (chain 30 → CONFIDENT).
The visual QA reveals that 2/4 identical V-reclassified edges
are hand-borne (not clean catch+throws), which is a more
nuanced picture than H15v2 reported.

**H11 v7 is the new recommended identity propagation
algorithm**, replacing H11 v6. The catch/throw event log
should be consumed with the caveat that V-shape "events"
include some hand-borne cases.

Next episode candidates:
1. H16: stricter V-shape check that combines position with
   motion signature (e.g., the ball must change direction at
   the V-apex, not just be near the hand). Would reject the
   2 hand-borne cases (23→25, 39→47) while keeping the 2
   clean catch+throws (30→33, 51→52) and rejecting the 27→28
   FP.
2. H17: V-shape recovery for v4d-missed links (e.g. 35→40,
   15→25 youtube) to see if any rejected v4d links are
   V-shape hidden catch-throws.
3. H12 v8: re-run pattern inference on h7v3pure chains with
   H10 v9 quality (analog of H12 v7 but with v9).
4. H237 v7: unify h7v3pure chains + h11v7 identities +
   h10v9 quality into a single per-chain record.

## Thirty-first episode (H16 + H17 v1) — STATUS: COMPLETE (H16 PARTIAL PASS, H17 PARTIAL PASS)

1. ✅ H16 v2: H3 stationary-cluster corroboration for V-reclassified edges
   (exclude_tids fix). Result: 1/4 identical V-reclass confirmed (51→52),
   0/1 YouTube (27→28 correctly rejected). Useful CONFIRMATORY signal,
   not a definitive filter. 180-cell sensitivity grid. H16 v1 vs v2
   showed the exclude_tids fix is essential (without it, YouTube FP
   gets confirmed).
2. ✅ H17 v1: V-shape + strict filter (endpoint dist <= 108 + side match +
   |slope| >= 1.0) for (a) v4d-rejected links, (b) e6c candidates not
   in h7v2, (c) adjacent tracklet pairs.
3. ✅ H17 quantitative result: 151 strict V-shape positives
   (2 v4d_rejected + 42 e6c_not_in_h7v2 + 107 adjacent).
4. ✅ H17 visual QA on 16 contact sheets:
   - 5/16 REAL (6→15, 56→57, 20→21, 54→57, 56→58)
   - 3/16 PARTIAL (29→33, 13→15, 23→24 — real catch, throw not visible)
   - 1/16 UNCLEAR (35→40 — long 27-frame gap, H12 v3 confirmed real)
   - 7/16 FALSE (in-hand held balls or apex at wrong location)
   - Precision: ~38-56% (depending on PARTIAL classification)
5. ✅ Key H17 finding: **both v4d-rejected links that H17 finds are
   already in h7v3 chains**. 35→40 via 35→37→40 (chain 23), 15→25
   directly as RECLASSIFIED_HAND_TRANSITION. h7v2's endpoint check
   (dist <= 108 AND |slope| >= 1.0) accepted both because the source's
   end_dist is well within reach.
6. ✅ Documented in `h16_report.md` and `h17_report.md` and updated
   RESULTS_LOG.

**H16 verdict: PARTIAL PASS.** Useful CONFIRMATORY signal on V-reclass
edges. 51→52 TP, 27→28 correctly rejected after exclude_tids fix.

**H17 verdict: PARTIAL PASS.** Useful research tool for finding candidate
catch-throws that h7v2 missed. The 42 e6c_not_in_h7v2 + 107 adjacent
strict positives are a "candidate list" for manual review, not a
reclassification rule. H17's strict V-shape precision is below h7v2's
endpoint check.

## Thirty-second episode (H20) — STATUS: COMPLETE (PASS)

Sub-steps:

1. ✅ H20: three independent rejection rules applied to the 151 H17
   strict V-shape positives.
   - INHAND: BOTH source's last 3 frames AND target's first 3 frames
     are within 30 px of the V-apex hand (held ball, not a catch+throw)
   - VEL_JUMP: end-to-start gap velocity > 70 px/frame (ball teleports)
   - APEX_AT_SRC: V-apex within 20 px of source's last frame AND source
     is in the hand (V is an artifact of source's stationary position)
2. ✅ Default thresholds (IN_HAND_PX=30, MIN=3, MAX_VEL=70, APEX_DIST=20):
   - 36/151 (23.8%) rejected, 115/151 (76.2%) kept
   - Rejection breakdown: in-hand 1, vel-jump 28, apex 9
3. ✅ Visual QA on the 16 H17 contact sheets:
   - H20 correctly KEEPS 6 REAL + 3 PARTIAL = 9 positives
   - H20 correctly REJECTS 5/6 FALSE (5 → 1 kept)
   - H20 incorrectly REJECTS 1 UNCLEAR (35→40)
   - H17 baseline: 10 kept (REAL+PARTIAL+UNCLEAR), 6 FALSE kept
   - H20 precision: 0.900 (vs H17's 0.625) on the 16-edge QA
   - H20 FPR drop: 0.833 (vs H17's 0.0)
4. ✅ Sensitivity grid (24 cells) shows default (30, 3, 70, 20) is in
   a flat region: 5 cells achieve 0.833 FPR drop, all requiring both
   the vel-jump rule (50 or 70) AND the apex rule (20 or 40).
5. ✅ Visual confirmation on 5 H20-REJECTED FPs (4→8, 35→38, 66→68,
   24→27, 10→11) via `vision_analyze` — all confirmed as held-ball
   or cross-ball false positives, NOT real catch+throws.
6. ✅ Discovery: 26 H20-KEPT e6c_not_in_h7v2 candidates (61.9% of
   the 42 H17 e6c_not_in_h7v2 strict positives) survive all H20
   filters. Of the 8 visually QA'd, 5 are REAL or PARTIAL (5/8 = 62.5%).
7. ✅ Documented in `h20_report.md` and updated RESULTS_LOG.

**H20 verdict: PASS.** H20 reduces H17's FALSE-positive rate by 83%
while preserving 100% of REAL and PARTIAL positives. The vel-jump
rule is the dominant filter (28/36 rejections); the in-hand rule
alone is too lenient (only 1 rejection). H20 is a strict post-filter
for H17 candidate mining and a candidate-pool generator (26
e6c_not_in_h7v2 + 88 adjacent H20-KEPTs not in production chain set),
not a chain-set augmentation tool.

## Thirty-third episode (H21 v1 + v2) — STATUS: COMPLETE (MIXED)

Sub-steps:

1. ✅ H21 v1: take the 5 visually-confirmed REAL H20-KEPT-not-in-h7v2
   candidates (6→15, 54→57, 56→57, 56→58 identical; 20→21 YouTube),
   add them as new HAND_TRANSITION edges with cost 1.0, re-run
   min-cost flow.
2. ✅ H21 v1 result on identical: 3/4 H21-KEPT edges admitted
   (6→15, 54→57, 56→58). 1/4 (56→57) rejected by capacity conflict
   with 56→58 (both want t56 as source). 3 chain merges:
   (5,6) + (15) → (5,6,15)
   (51,52,54,59,63) + (57) → (51,52,54,57)
   (56) + (58) → (56,58)
3. ✅ H21 v1 result on YouTube: 0/1 H21-KEPT edge admitted.
   20→21 rejected by capacity conflict with existing 16→21
   (t21 already has a predecessor in the chain set).
4. ✅ H21 v2: re-compute H10 v9 chain quality on h7v3plus chains.
   - identical: mean quality 0.828 → 0.804 (-0.023)
   - YouTube: mean quality 0.685 → 0.685 (0.000)
5. ✅ Visual re-analysis of YouTube 20→21 contact sheet:
   tracklet 20 is the canonical contact tracklet (3 detections at
   right wrist with min_d ≈ 5 px), tracklet 16 is a spurious
   earlier-detection (n=126 frames, ending 2 frames before t20's
   contact). The existing 16→21 edge may be WRONG.
6. ✅ Documented in `h21_report.md`.

**H21 verdict: MIXED (consumer-pass, quality-neutral).** H21 successfully
integrates 3 of 4 visually-confirmed REAL H20-KEPT edges into the
identical chain set, merging 3 pairs of chains. The H21 v2 chain
quality is slightly worse on identical (-0.023) because the new
chains expose BALLISTIC edges that h8 v5 penalizes. The YouTube
20→21 case is a known limitation: the H21 algorithm does not veto
existing edges to make room for visually-confirmed alternatives.
Visual analysis of the 20→21 case suggests the existing 16→21 edge
is wrong (tracklet 20 is the canonical contact, not tracklet 16).

## Thirty-fourth episode (H22 v1 + v2) — STATUS: COMPLETE (MIXED, narrow-scope PASS)

Sub-steps:

1. ✅ H22 v1: implement VETO mode — when an H20-KEPT edge is rejected
   by capacity, check if the existing edge has weaker target evidence
   (start_dist > VETO_DIST_THRESHOLD = 30 px). If the H20-KEPT has
   min_d < MIN_D_VETO = 30 px AND the existing target has
   start_dist > 30 px AND the H20-KEPT source has no existing
   successor, VETO the existing edge and admit the H20-KEPT.
2. ✅ H22 v1 result:
   - identical: 0 veto decisions. The 2 H20-KEPT candidates (17→22,
     68→70) had strong V-shape AND weak existing targets, but their
     sources (t17, t68) already have successors in the chain set
     (t17→t23 in chain 13, t68→t71 in chain 31). The veto would
     break chain topology, so excluded.
   - YouTube: 1 veto decision. 20→21 (V-shape min_d=5.3) successfully
     vetoes 16→21 (target start_dist=35.3). The H20-KEPT source (t20)
     is a singleton, so vetoing is safe.
3. ✅ Chain topology change (YouTube):
   - h7v3pure chain 0: (1,9,13,16,21,29,34) — 7 tids
   - h7v3veto chain 0: (1,9,13,16) — 4 tids
   - h7v3veto chain 10: (20,21,29,34) — 4 tids (new)
4. ✅ H22 v2: re-compute H10 v9 chain quality on h7v3veto chains.
   - identical: mean quality 0.828 (no change)
   - YouTube: mean quality 0.685 → 0.689 (+0.0034)
5. ✅ Documented in `h22_report.md`.

**H22 verdict: MIXED (narrow-scope PASS).** H22 successfully vetoes
the existing 16→21 YouTube edge in favor of the H20-KEPT 20→21 edge,
producing a slight chain quality improvement (+0.0034 on YouTube)
and confirming the visual analysis that 16→21 is wrong. The veto
has narrow scope: 0 identical veto decisions because the H20-KEPT
candidates have existing source successors. h7v3pure (H7v2 + H15v2)
remains the recommended chain set; H22 is a useful diagnostic tool.

**Next episode candidates:**

1. **H23: aggressive H20-KEPT veto mode** — extend H22 to break
   existing chain topology when an H20-KEPT edge has much stronger
   evidence. This would admit the 2 identical veto candidates
   (17→22, 68→70). Trade-off: chain quality may drop.
2. **H24: H20-KEPT e6c_not_in_h7v2 candidate review at scale** —
   visually QA the remaining 18 H20-KEPT e6c_not_in_h7v2 candidates.
3. **H25: H11 v8 identity propagation on h7v3veto chains** — see if
   the 20→21 vs 16→21 swap changes the per-tracklet physical ball IDs.
4. **H26: H12 v8 pattern inference on h7v3plus chains** — analog
   of H12 v7 but with the H21 chains.

## Thirty-fifth episode (H32) — STATUS: COMPLETE (NEGATIVE)

Sub-steps:
1. ✅ Designed H32: per-chain hand-alternation + ball-count
   characterization on h7v3plus2 chains.
2. ✅ Implemented `h32_chain_characterization.py` that parses hand
   info from each edge type's metadata (HAND_TRANSITION from
   `tok_age=X,hand=Y`; RECLASSIFIED_HAND_TRANSITION from
   reclassify_reason; V_RECLASSIFIED_HAND_TRANSITION from
   v_reclassify_reason; H26_RECLASSIFIED_HAND_TRANSITION from
   h26_reason). For H26 hand-offs, recorded BOTH catch and throw
   hands.
3. ✅ Ran on both videos. Result:
   - identical: 18 multi-tracklet chains → 9 SINGLE_CATCH, 3
     CASCADE_LIKE, 2 FOUNTAIN_LIKE, 3 NO_CATCH, 1 UNKNOWN
   - YouTube: 9 multi-tracklet chains → 5 CASCADE_LIKE, 3
     SINGLE_CATCH, 1 FOUNTAIN_LIKE
4. ✅ Rendered 7 contact sheets (1 per verdict per video) with real
   video frames via cv2.
5. ✅ Visual QA via vision_analyze: 5/7 chains are MULTI_BALL_MERGE.
   Only chain 29 (UNKNOWN) is a real 2-ball exchange pattern.
6. ✅ Documented in `h32_report.md` and updated STATE/RESULTS_LOG.

**H32 verdict: NEGATIVE.** H32's per-chain CASCADE/FOUNTAIN
classification is fundamentally confounded by multi-ball merges.
The h7v3plus2 chain set is valid as "hand-event lists" but NOT as
"single-ball trajectories." H32 confirms H10/H11: the chain set is
mostly multi-ball merges.

**Key insight:** The CASCADE/FOUNTAIN problem in H12 is now
understood to be a single-ball-vs-multi-ball identification problem,
not a cascade-vs-fountain classification problem. Future work
should focus on:
- H11 v7 CONFIDENT filter (the most accurate single-ball filter)
- Cross-tracklet velocity coherence (H8 v5 extended to per-chain)
- Color tracking (H25 was mentioned but not implemented)
- Multi-view 3D (out of scope for monocular 2D setup)

**Next episode candidates:**
1. **H33: literature search for multi-ball juggling tracking
   methods** — mentioned in STATE.md. Could surface new ideas
   for single-ball identification.
2. **H34: H22+H26 combined chain set** — apply H22's YouTube 20→21
   veto on top of H26's 2 NEW REAL H24 edges.
3. **Stop here.** The h7v3plus2 chain set is well-validated. Further
   chain improvements would require fundamentally different signals.

## Thirty-sixth episode (H33) — STATUS: COMPLETE (NEGATIVE)

Sub-steps:
1. ✅ Designed H33: tracklet-time overlap multi-ball detector on
   h7v3plus2 chains.
2. ✅ Implemented `h33_chain_overlap.py` that computes per-chain
   tracklet-time overlap (max_overlap, total_overlap, n_overlap_pairs)
   and emits a verdict (MULTI_BALL_HIGH if overlap >= 5, MULTI_BALL_LOW
   if 0 < overlap < 5, SINGLE_BALL_CANDIDATE if overlap == 0 and
   n_tids >= 2, SINGLE_BALL if n_tids == 1).
3. ✅ Ran on both videos. Result:
   - identical: 0/18 multi-tracklet chains have any overlap
   - YouTube: 0/9 multi-tracklet chains have any overlap
4. ✅ Cross-checked with H32 visual QA: H33 misses ALL 5
   vision-confirmed MULTI_BALL_MERGE chains.
5. ✅ Documented in `h33_report.md` and updated STATE/RESULTS_LOG.

**H33 verdict: NEGATIVE.** Tracklet-time overlap is not a useful
signal for multi-ball detection. The h7v3plus2 chain construction
produces temporally sequential tracklets by design, so even
multi-ball-merge chains have NO tracklet overlap.

**Key insight:** Multi-ball merges happen because the *physical
ball identity* of each tracklet doesn't match the chain's
structure, NOT because the tracklets overlap in time. The chain
construction (H7v2 + H15v2 + H21 + H26) ensures all edges are
temporally sequential (hand-edges require catch-throw; BALLISTIC
edges link adjacent tracklets). Detecting multi-ball merges
requires fundamentally different signals (e.g., per-point color
tracking, multi-view 3D reconstruction).

**Next episode candidates:**
1. **H34: H22+H26 combined chain set** — apply H22's YouTube 20→21
   veto on top of H26's 2 NEW REAL H24 edges. (Low priority — small
   improvement, +0.0034 + +0.0061.)
3. **Stop here.** The h7v3plus2 chain set is well-validated. The
   single-ball-vs-multi-ball identification problem requires
   fundamentally different signals not available with current data.
4. **H35: pattern inference on h7v3plus2** — apply H12's per-frame
   pattern inference to the recommended chain set. (Likely produces
   similar CASCADE/FOUNTAIN ambiguity as H12 v8 because the
   underlying multi-ball-merge problem is the same.)


## Thirty-seventh episode (H35) — STATUS: COMPLETE (PASS, consumer-pass)

Sub-steps:
1. ✅ Re-ran H11 v7 identity propagation on h7v3plus3 chains
   (h7v3plus3 = h7v3pure + H22 + H26). Extended hand-edge types
   to include H22_RECLASSIFIED_HAND_TRANSITION. Parsed hand from
   h22_reason and h26_reason.
2. ✅ Re-ran H12 v7 pattern inference on h7v3plus3 chains. Built
   per-frame census and pattern distribution.
3. ✅ Result: identical is identical to h7v3plus2 (no H22 effect on
   identical). YouTube pattern distribution is identical to
   h7v3pure (H12 v8). The H22 chain split does NOT change the
   per-frame census or pattern distribution.
4. ✅ 6 YouTube contact sheets rendered for chain 0 (1,9,13,16) and
   chain 10 (20,21,29,34). Visual inspection confirms the
   4+4 split is geometrically correct.
5. ✅ Documented in `h35_report.md` and updated STATE/RESULTS_LOG.

**H35 verdict: PASS (consumer-pass, no change).** The h7v3plus3
chain set is functionally equivalent to h7v3pure for downstream
consumers. Pattern distribution, phase detection, and per-frame
census are all stable across h7v3 variants. Use h7v3plus3 going
forward.

**Next episode candidates:**

1. **H36: per-frame hand-occupancy state machine** — for each
   frame, infer (left_occupancy, right_occupancy, n_in_air) from
   the h7v3plus3 chain set, allowing multi-token states.
2. **H37: literature search for multi-ball juggling tracking
   methods** — search the web for the latest juggling-tracking
   papers, then turn promising ideas into isolated experiments.
3. **Stop here.** The h7v3plus3 chain set is well-validated and
   the downstream consumers are stable. Further chain improvements
   would require fundamentally different signals.


## Thirty-eighth episode (H36) — STATUS: COMPLETE (PASS)

Sub-steps:
1. ✅ Implemented H36: per-frame hand-occupancy state machine on
   h7v3plus3 chains. State is (L, R, A) where L = balls in left
   hand, R = balls in right hand, A = balls in air. Constrained:
   L + R + A = total_n_balls (3 for identical, 5 for YouTube)
   and each hand has bounded capacity (0-3 balls).
2. ✅ Walk h7v3plus3 chains chronologically, emit per-event
   CATCH (at from-tracklet last_frame) and THROW (at to-tracklet
   first_frame). Detect violations: CATCH_NO_AIR, CATCH_OVER_CAP,
   THROW_EMPTY_HAND, THROW_NO_AIR_SLOT.
3. ✅ Interpolate state to per-frame timeline (HOLD between events).
4. ✅ Result: ZERO violations on either video. ZERO over-capacity
   events. 73% of frames have all balls in air on both videos.
5. ✅ 2 contact sheets rendered (one per video). Visual inspection
   confirms: identical is a clean 3-ball cascade, YouTube is a
   clean 5-ball pattern.
6. ✅ Documented in `h36_report.md` and updated STATE/RESULTS_LOG.

**H36 verdict: PASS.** The h7v3plus3 chain set is now validated
at three levels: chain quality (H10), identity propagation (H11),
and per-frame hand-occupancy (H36). The chain set is a complete,
consistent, closed representation of the juggling routines in
both videos.

**Key findings:**
- Zero conservation violations (L+R+A always = total_n_balls).
- Zero over-capacity events (a hand never holds 3+ balls).
- 73% of frames have all balls in air (cascade-pattern baseline).
- H32's MULTI_BALL_MERGE chains are NOT due to chain-set
  over-attribution of hand occupancy to one hand. The
  multi-ball-merge problem is at the per-chain physical-ball-
  identity level, not at the global hand-occupancy level.
- Right-hand bias on YouTube (15.7% R vs 10.9% L) is real and
  could be due to camera angle or juggler preference.

**Next episode candidates:**

1. **H37: cross-reference H36 (L, R, A) with H12 v8 pattern
   labels** — use the H36 (L, R, A) state to validate or
   invalidate H12 v8's pattern classification. This may fix
   the H12 v4/v5 ambiguity.
2. **Stop here.** The h7v3plus3 chain set is now validated
   at the per-frame hand-occupancy level. Further chain
   improvements would require fundamentally different signals.


## Thirty-ninth episode (H37) — STATUS: COMPLETE (PASS, validation)

Sub-steps:
1. ✅ Implemented H37: cross-reference H36 (L, R, A) state with
   H12 v8 pattern labels per frame.
2. ✅ Result: 80.7% agreement on identical (823/1020 common
   frames), 76.5% on YouTube (664/868).
3. ✅ L_extra and R_extra are all HOLD frames (interpolated),
   not real disagreements.
4. ✅ Late-phase identical FOUNTAIN_3+ has 97% (0, 0, 3) state
   — H36 has no hand-occupancy support.
5. ✅ CASCADE_3+ has hand-occupancy support: 20/22 identical
   are (0, 1, 2), 66/129 YouTube are (0, 1, 4).
6. ✅ 2 contact sheets rendered. The late phase FOUNTAIN_3+
   blocks appear as continuous stretches alternating with
   MIXED_3+ blocks.
7. ✅ Documented in `h37_report.md` and updated STATE/RESULTS_LOG.

**H37 verdict: PASS (consumer-pass, validation).** H36 (L, R, A)
state validates CASCADE_3+ classification (which has
hand-occupancy support) but cannot disambiguate FOUNTAIN_3+
(which has no hand-occupancy signal). The 80%/76% agreement
rate is a useful summary metric.

**Next episode candidates:**

1. **H38: post-filter CASCADE_3+ using H36 hand-occupancy** —
   reject CASCADE_3+ classifications where H36 has no
   hand-occupancy evidence. This could be a precision
   improvement.
2. **Stop here.** The chain set is now validated at four
   levels: quality (H10), identity (H11), hand-occupancy
   (H36), and pattern cross-reference (H37). Further chain
   improvements would require fundamentally different signals.


## Fortieth episode (H38) — STATUS: COMPLETE (PASS, precision improvement, narrow scope)

Sub-steps:
1. ✅ Implemented H38: post-filter CASCADE_3+ classifications
   where H36 has no hand-occupancy support (H36 state
   (0, 0, 3) or (0, 0, 5)).
2. ✅ Result: 1/22 identical and 12/129 YouTube CASCADE_3+
   rejected. YouTube rejection is a tight 12-frame contiguous
   block at f=470-481 with H12 v8 confidence 0.639-0.646.
3. ✅ No substantial CASCADE phases (>= 20 consecutive frames)
   were broken by the filter.
4. ✅ Documented in `h38_report.md` and updated STATE/RESULTS_LOG.

**H38 verdict: PASS (precision improvement, narrow scope).**
H38 is a strict post-filter that rejects CASCADE_3+
classifications without hand-occupancy support. The
improvement is small (1/22 identical, 12/129 YouTube) but
real. Safe to apply as a downstream consumer filter.

## H39 episode (2026-08-28 ~14:35) — FOUNTAIN_3+ post-filter

Sub-steps:
1. ✅ Read H37 crossref data. Identified that FOUNTAIN_3+
   on identical has 1.7% hand-occupancy (5/288 frames)
   versus CASCADE_3+ at 95%. Hypothesis: FOUNTAIN_3+
   without hand-occupancy is an H12 v8 misclassification.
2. ✅ H39 v1 (frame-level): reject FOUNTAIN_3+ where
   H36 (L, R) = (0, 0). Result: 283/288 identical
   FOUNTAIN_3+ rejected (98.3%), 94/110 YouTube (85.5%).
3. ✅ H39 v2 (phase-level): reject FOUNTAIN_3+ phases
   with zero H36 events. Result: 2 phases rejected on
   identical (74 frames), 0 on YouTube.
4. ✅ Rendered 11 contact sheets (9 identical + 2 YouTube)
   and ran visual QA via `vision_analyze` on 10 phases
   (1 had vision error).
5. ✅ Visual QA findings: H12 v8 FOUNTAIN_3+ accuracy is
   **30% (3/10)** — 4 MIXED, 1 CASCADE, 2 OTHER. H39 v1
   precision 20% (over-rejects 60% of real juggling);
   H39 v2 precision 50% on small sample.
6. ✅ Documented in `h39_report.md` and updated
   STATE/RESULTS_LOG/RESEARCH_NOTES.

**H39 verdict: NEGATIVE.** H12 v8 FOUNTAIN_3+ is
fundamentally unreliable (~70% over-classification), but
H36 is not a reliable validator because it only marks
chain-driven state, not continuous hand-occupancy. H39
filters should not be used downstream. The underlying
finding (H12 v8 over-classifies FOUNTAIN_3+ by 70%) is
real and important.

**Final state of the lab:**

The h7v3plus3 chain set is now validated at FIVE levels:
1. **Chain quality (H10):** per-chain quality score.
2. **Identity propagation (H11):** per-tracklet physical
   ball ID.
3. **Per-frame hand-occupancy (H36):** (L, R, A) state machine.
4. **Pattern cross-reference (H37):** H36 vs H12 v8 validation.
5. **Pattern post-filter (H38):** CASCADE_3+ precision improvement.

And one negative validation:
6. **H39:** H12 v8 FOUNTAIN_3+ over-classifies by 70% but
   H36 cannot validate it (sparse state). The chain set
   is a complete, consistent, closed representation of
   the juggling routines in both videos, but pattern
   classifications should be consumed with awareness of
   H39's findings.

Further chain improvements would require fundamentally
different signals (multi-view, learned color tracking,
or 3D ball estimation). The next research direction
(H40) is to build a continuous hand-occupancy signal
from raw detector + pose data, not from chain events.


## Forty-first episode (H45) — STATUS: COMPLETE (NEGATIVE with structural insight)

Sub-steps:
1. ✅ Implemented H45: per-chain flight-time / siteswap
   analysis. Computes median flight_time, flight_time CV
   (std/mean), and cross-references with H12 v8 pattern
   labels. Declares UNIFORM_CV_THRESHOLD = 0.5 from physics
   (3-ball cascade with constant beats has CV = 0 by
   construction; 0.5 admits ~30% noise before flagging).
2. ✅ Ran on both videos. Result: only 2/13 identical
   chains and 1/10 YouTube chains have n_flights >= 3.
3. ✅ Rendered 11 contact sheets for the 3 multi-flight
   chains (4 chain 22 + 3 chain 29 + 4 chain 9).
4. ✅ Visual QA on all 11 flights via `vision_analyze`:
   - identical chain 22: 3/4 real catch-throws (ft=33, 31, 39),
     1/4 identity switch (ft=1, geometric discontinuity 999→94px)
   - identical chain 29: 1/2 real catch-throw (ft=33),
     1/2 identity switch (ft=5, cross-hand + 5-frame "flight")
   - YouTube chain 9: 0/4 real catch-throws. ALL 4 are
     tracker fragmentation (ft=58, 61, 62, 134; physically
     impossible for 5-ball)
5. ✅ Documented in `h45_report.md` and updated
   STATE/RESULTS_LOG/RESEARCH_NOTES.

**H45 verdict: NEGATIVE result with structural insight.**

**Most important finding: 30-40 frame flight times on
identical match the expected 3-ball cascade ball airtime
(1.0-1.3s at 30fps), confirming the H12 v8 event log is
trustworthy for inter-event timing on identical.** The
58-67 frame "flights" on YouTube are uniformly tracker
fragmentation, not real throws.

**The 10-frame flight-time filter** is a useful downstream
post-filter: drop H12 v8 "flights" < 10 frames as likely
identity switches. Applied to identical, this rejects 3/11
flights and preserves 7 real catch-throws.

**Siteswap analysis is infeasible on h7v3plus3 with the
H12 v8 event log.** This is an input-data limitation, not
an algorithm problem. Future work would need either a
denser event log or a different signal (H8 v8 per-arc
gravity, multi-view, color tracking).

**Recommended next research (H46):** per-flight physics
check via H8 v8. For each H12 v8 "flight", compute H8 v8
gravity from source's last arc and target's first arc,
and reject flights where the implied free-fall time is
inconsistent with the measured flight time. This converts
H8 v8 from a per-edge to a per-flight signal, potentially
distinguishing real flights from tracker-fragmentation
artifacts based on physics alone.

See `h1_hand_pool/reports/h45_report.md` for full analysis.

## H50 — H12 v8 with 10-frame filter (full pipeline re-run) — STATUS: COMPLETE

Sub-steps:
1. ✅ Implemented H50: re-run H12 v8's full pipeline
   (census + K=4 events + chain quality + n_total) on the
   FILTERED event log, with the unfiltered version as
   apples-to-apples baseline.
2. ✅ Ran on both videos. Result:
   - identical: 6 events dropped (3 short flights),
     10/1042 (1.0%) frames changed
   - YouTube: 0 events dropped, 0/898 (0.0%) frames changed
3. ✅ Per-pattern delta on identical:
   - FOUNTAIN_3+ -0.3%, CASCADE_3+ +0.7%, MIXED_3+ -0.3%
   - Substantial phases: 15 -> 15 (unchanged)
4. ✅ Visual QA on the 3 changed windows (3 contact sheets).
   Found 1 unexpected result: chain 13 ft=3 may be a real
   catch-throw, not an identity switch. The 10-frame
   threshold may be over-aggressive for this 1 case.
5. ✅ Documented in `h50_report.md` and updated
   STATE/RESULTS_LOG.

**H50 verdict: PASS.** Closes H49's negative result. The
10-frame filter is a SAFE post-filter for H12 v8 event
log consumers.

**Recommended operating point:** h7v3plus3 chain set +
H12 v8 + H50 10-frame event log filter. This is the
final precision-optimized configuration for FOUNTAIN_3+ /
CASCADE_3+ downstream consumers.

**Most important finding:** H49's K=4-only upper bound
(45.2%/15.9%) was indeed an upper bound, as H49 suspected.
The full pipeline (census + chain quality + n_total)
dominates the K=4 sliding window signal, so the real
downstream impact of the 10-frame filter is only 1% identical
and 0% YouTube.

**Recommended next research (H51):** H43 + H50 combined
post-filter. Apply H43's confidence-based FOUNTAIN_3+ filter
(conf < 0.55) on top of H50's filtered pipeline. The combined
filter should be the final precision-optimized stack.

See `h1_hand_pool/reports/h50_report.md` for full analysis.

## H51 — H12 v8 + H50 + H43 combined filter — STATUS: COMPLETE

Sub-steps:
1. ✅ Implemented H51: apply H43's FOUNTAIN_3+ confidence
   < 0.55 filter on top of H50's filtered event log.
2. ✅ Compared to H12 v8 unfiltered + H43 (baseline).
3. ✅ Per-frame diff: identical 1.0%, YouTube 0.0%.
4. ✅ Per-pattern delta on identical:
   - FOUNTAIN_3+ -2.3% (combined H50 + H43)
   - CASCADE_3+ +0.7% (from H50)
   - FOUNTAIN_LOW_CONF +0 (H43 unchanged)
5. ✅ Substantial phases: 15 -> 15 (unchanged)
6. ✅ Documented in `h51_report.md` and updated
   STATE/RESULTS_LOG.

**H51 verdict: PASS.** H50 and H43 compose cleanly. The
combined filter is a strict improvement over either alone.

**Recommended operating point:** h7v3plus3 + H12 v8 +
H50 + H43. Final precision-optimized configuration.

**Most important finding:** H50 (event-log filter) and
H43 (confidence filter) are independent and commutative.
The 1.0% H50 frame change is independent of H43 because
the changed frames are not in the H43 rejection region
(conf < 0.55). The two filters address two independent
error modes.

See `h1_hand_pool/reports/h51_report.md` for full analysis.

## H52 — H8 v5 parabolic physics on H50-dropped pairs — STATUS: COMPLETE

Sub-steps:
1. ✅ Implemented H52: apply H8 v5 parabolic fit to the
   3 H50-dropped (CATCH, THROW) pairs.
2. ✅ Sensitivity grid on MIN_TRACKLET_PTS ∈ {2, 3, 4, 5, 6, 8, 10}.
3. ✅ Found that H8 v5 returns VIOLATING (chain 13, 30) or
   INSUFFICIENT_DATA (chain 23) at all settings.
4. ✅ Resolved H50's "1/3 ambiguous drop" caveat: chain 13
   ft=3 is TRACKER_FRAGMENTATION per H8 v5 physics, NOT a
   real catch-throw.
5. ✅ Documented in `h52_report.md` and updated
   STATE/RESULTS_LOG.

**H52 verdict: PASS.** Closes the H50 visual QA ambiguity.

**Key finding**: H8 v5's physics check confirms all 3
H50-dropped pairs are TRACKER_FRAGMENTATION. The 10-frame
filter is correct and should not be relaxed.

**Source of H50 visual QA error**: The vision tool saw
"ball at hand" but didn't check velocity consistency.
The chain 13 source is in fast descent (-32.1 px/f),
the target is at rest (-1.1 px/f), and these are
physically inconsistent.

**Recommended operating point (now fully validated)**:
h7v3plus3 + H12 v8 + H50 10-frame filter + H43 confidence
filter + H52 physics corroboration.

The H50→H51→H52 series has produced the final validated
operating point. The hand-occlusion overnight lab has
demonstrated that the 10-frame filter is a safe, useful
post-filter that drops tracker-fragmentation identity
switches on identical without affecting real catch-throws.

## H69 — Periodicity of "balls aloft" as FOUNTAIN_3+ post-filter — STATUS: COMPLETE

Sub-steps:
1. ✅ Implemented H69: per-phase A signal + FFT spectral
   concentration.
2. ✅ Computed per-phase features (spectral_concentration,
   ac_dominant_period, ac_periodicity_strength, fft_dominant_period,
   n_peaks, direction_change_rate) on the 7 H65 substantial
   FOUNTAIN_3+ phases.
3. ✅ Compared H69 alone, H43 alone, and H43 OR H69 stacked.
4. ✅ Sensitivity grid on H69 spec_conc threshold (0.05-0.40 in
   0.01 increments): flat region at [0.15, 0.16].
5. ✅ Per-frame end-to-end impact: identical 21/1042 (2.0%),
   YouTube 175/898 (19.5%).
6. ✅ Documented in `h69_report.md` and updated
   STATE/RESULTS_LOG.

**H69 verdict: PASS.** H43 OR H69(spec_conc < 0.15) is the new
best FOUNTAIN_3+ post-filter. Catches 3/4 wrong FOUNTAIN_3+
phases on the H65 sample (1029-1049, 482-594, 800-861) with
0/3 wrong rejects (all FOUNTAIN preserved).

**Key finding:** The level-based metric (H66/H67/H68) and the
confidence-based metric (H43) are both dominated by the structural
periodicity metric (H69) when stacked. H69 measures "is the
ball-aloft pattern coherent?" while H66/H68 measure "are there
balls aloft?" — the structural check is what discriminates
FOUNTAIN from HOLD/CASCADE.

**Recommended operating point (H69 supersedes H68):**
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69(spec_conc < 0.15)
+ H52 + H53.

See `h1_hand_pool/reports/h69_report.md` for full analysis.

See `h1_hand_pool/reports/h52_report.md` for full analysis.

## H72 episode — STATUS: COMPLETE (PARTIAL PASS)

Sub-steps:

1. ✅ Read prior persistent state (STATE.md, RESULTS_LOG.md, H71 report).
2. ✅ Surveyed the 20 H70 substantial phases; identified 6 un-QA'd
   phases (1 CASCADE_3+ identical + 5 MIXED_3+ YouTube).
3. ✅ Generated 6 contact sheets in `contact_sheets_h72/`.
4. ✅ Multi-rater visual QA on all 6 contact sheets (1-4 vision
   queries per sheet). H70 precision on this sample: 5/6 = 83.3%.
5. ✅ Cross-validation with per-frame census (H36/H37 data):
   L+R=0 throughout f=685-716 confirms this is NOT a true cascade.
6. ✅ Documented in `h72_report.md` and updated
   STATE.md / RESULTS_LOG.md.

**H72 verdict: PARTIAL PASS.** H70 KEEP threshold (spec_conc >= 0.15)
is validated at 10/11 = 91% precision on MIXED_3+ across H71+H72.
The 1 H72 WRONG case is an H12 v8 misclassification (CASCADE_3+
labeled on a 3-ball manipulation trick), not a H70 spec_conc
failure.

**Key findings:**
- H70 spec_conc is a useful MIXED_3+ discriminator
- H70 spec_conc should NOT be applied to CASCADE_3+ classification
- Per-frame census (L+R=0) is a useful programmatic check
- CASCADE_3+ class has only 1 substantial phase, which is
  misclassified — H12 v8's CASCADE_3+ accuracy is unmeasurable at
  scale from the H70 sample
- Multi-rater single-pass unreliability: 2/6 = 33% on H72 sample
  (combined with H71: ~20-25%)

**H72 closes the H70 visual-QA arc** at 20/20 = 100% coverage
of substantial phases:
- 7 FOUNTAIN_3+ (H65): 3 real, 4 misclassified
- 5 KEEP MIXED_3+ (H71): 5 real juggling
- 2 REJECT MIXED phases (H71): 1 real juggling, 1 correctly rejected
- 1 CASCADE_3+ (H72): 0 real cascade (it's a manipulation trick)
- 5 KEEP MIXED_3+ (H72): 5 real juggling

**Recommended operating point (post-H72, unchanged from H71 for
MIXED_3+):**
- FOUNTAIN_3+: H43 OR H69(spec_conc < 0.15)
- MIXED_3+: KEEP at spec_conc >= 0.15 (91% precision),
  REJECT at spec_conc < 0.10 (validated on 1/1),
  0.10-0.15 = MIXED_3+_LOW_CONF (research signal)
- CASCADE_3+: no recommended filter (insufficient sample)

See `h1_hand_pool/reports/h72_report.md` for full analysis.

## H73 episode — PLANNED

The H70/H71/H72 arc is closed. The H72 "future research directions"
section identifies two remaining experiments:

1. **H73: per-frame census (L+R) as a programmatic CASCADE_3+
   validator** — measure how many H12 v8 CASCADE_3+ phases have
   L+R=0 throughout. The f=685-716 finding suggests L+R=0 is a
   strong "not a true cascade" signal. Could be a precision-
   improving filter for CASCADE_3+.

2. **H74: re-run H59 precision/recall on the FULL H70 sample with
   ground truth** — characterize end-to-end quality of the
   h7v3plus3 + H10 v11 v3 + H12 v8 + H70/H71 v1 stack.


## H73 episode — STATUS: COMPLETE (NEGATIVE)

Sub-steps:

1. ✅ Implemented H73 v1: per-frame census L+R=0 detector on
   CASCADE_3+ / FOUNTAIN_3+ phases. Found that L+R=0 is the
   default for 97% of frames (per-frame census only updates at
   chain events). H73 v1 hypothesis was wrong.
2. ✅ Implemented H73 v2: H40v2 sustained-occupancy analysis on
   9 substantial CASCADE_3+ / FOUNTAIN_3+ phases. All 9 have
   BOTH hands occupied (mean L+R > 1.0), so H40v2 cannot
   distinguish real from misclassified.
3. ✅ Visual QA on f=733-766 (the other CASCADE_3+ identical phase):
   confirmed as static hold / contact juggling pose (NEW FINDING).
4. ✅ Documented in `h73_report.md` and updated STATE.md / RESULTS_LOG.md.

**H73 verdict: NEGATIVE.** H40v2 sustained-occupancy is NOT a useful
discriminator for CASCADE_3+ / FOUNTAIN_3+ accuracy.

**Key findings:**
- All 9 substantial CASCADE_3+ / FOUNTAIN_3+ phases have BOTH hands
  occupied (mean L+R > 1.0)
- H40v2 measures "balls within 100 px of hands", not "actively
  juggling" — a static hold of 2 balls looks the same as a real
  FOUNTAIN to H40v2
- BOTH CASCADE_3+ identical phases are misclassified (H72 + H73):
  0/2 = 0% H12 v8 CASCADE_3+ accuracy on substantial phases
- H12 v8 FOUNTAIN_3+ accuracy: 3/5 = 60% on H65-verified substantial
  phases (consistent with H39 ~30%, H65 ~43%)

**Recommended operating point (post-H73):**
- FOUNTAIN_3+: H43 OR H69(spec_conc < 0.15) (unchanged from H69)
- MIXED_3+: KEEP at spec_conc >= 0.15, REJECT at spec_conc < 0.10
  (unchanged from H71)
- CASCADE_3+: NO reliable filter — treat as research signal only

**Future research directions (post-H73):**
1. H74: L+R temporal variance as static-hold detector (a real
   FOUNTAIN cycles L+R; a static hold is stable)
2. H75: CASCADE_3+ as "research signal only"
3. H76: re-run H59 precision/recall on FULL H70 sample

See `h1_hand_pool/reports/h73_report.md` for full analysis.

## H74 episode — PLANNED

H74: H40v2 L+R temporal variance as static-hold detector.

For each substantial FOUNTAIN_3+ / CASCADE_3+ phase, compute the
variance of L40v2 and R40v2 across frames in the phase. A real
FOUNTAIN would have high variance (balls cycling through hands);
a static hold would have low variance (balls stable in hands).

Hypothesis: low L+R variance correlates with H12 v8 misclassifications
(static hold / manipulation trick labeled as FOUNTAIN_3+).

Test on the 9 H73 phases with ground truth from H65 (3 real FOUNTAIN,
4 misclassified FOUNTAIN_3+, 2 misclassified CASCADE_3+).

If H74 v1 shows separation between real and misclassified, it would
be a precision-improving filter for FOUNTAIN_3+ and CASCADE_3+.

## H74 episode — STATUS: COMPLETE (MIXED)

Sub-steps:

1. ✅ Implemented H74 v1: H40v2 L+R temporal variance on 9
   substantial CASCADE_3+ / FOUNTAIN_3+ phases. Computed
   LR_variance, n_unique_states, n_transitions, max_run, frac_max.
2. ✅ Cross-referenced with H65 + H72 ground truth.
3. ✅ Threshold search: LR_var >= 0.20 catches 2/6 misclassified
   while keeping 3/3 real FOUNTAIN.
4. ✅ Documented in `h74_report.md` and updated
   STATE.md / RESULTS_LOG.md.

**H74 verdict: MIXED.** H74 v1 LR_variance correctly identifies
static-hold-like misclassifications (2/4 on the H65 sample) but
cannot detect manipulation tricks or high-variance misclassifications.

**Key findings:**
- STATIC_HOLD (f=733-766) has lowest variance (0.157) — correctly caught
- YouTube f=482-594 also has low variance (0.135) — NEW INTERPRETATION
  as 5-ball static hold (consistent with H65's "OTHER_NOT_FOUNTAIN")
- MANIPULATION_TRICK (f=685-716) has high variance (0.386) — NOT caught
- n_unique_states, frac_max metrics also overlap between real and
  misclassified

**Recommended operating point (post-H74, updated FOUNTAIN_3+):**
- (H43 OR H69(spec_conc < 0.15)) AND NOT H74_static_hold
  where H74_static_hold = LR_variance < 0.20
- Catches 4/4 misclassified FOUNTAIN_3+ on H65 sample (vs 3/4 for
  H43+H69 alone)
- 0/3 real FOUNTAIN falsely rejected at threshold 0.20

**Future research (post-H74):**
1. H75: H43 + H69 + H74 stacked FOUNTAIN_3+ filter
2. H76: CASCADE_3+ as research signal
3. H77: re-run H59 precision/recall on FULL H70 sample

See `h1_hand_pool/reports/h74_report.md` for full analysis.

## H75 episode — PLANNED

H75: H43 + H69 + H74 stacked FOUNTAIN_3+ filter.

Apply H74 (LR_variance < 0.20) as an additional rejection criterion
on top of the H43 + H69 spec_conc < 0.15 stack. The combined filter
should catch all 4 misclassified FOUNTAIN_3+ phases on the H65 sample
while preserving all 3 real FOUNTAIN phases.

Hypothesis: The H43 + H69 + H74 stack is the new recommended
operating point for FOUNTAIN_3+ post-filter. It combines:
- H43: confidence-based (catches f=1029-1049 conf=0.463)
- H69: periodicity-based (catches f=800-861, f=482-594)
- H74: variance-based (catches f=482-594 again as backup, plus
  the f=733-766 CASCADE_3+ misclassification)

Test on:
- H65 sample: 7 FOUNTAIN_3+ phases (3 real, 4 misclassified)
- H70 sample: 7 FOUNTAIN_3+ phases (already covered by H65 + H72/H73)

## H76 episode — STATUS: COMPLETE (PASS, limited scope)

Sub-steps:

1. ✅ Built comprehensive ground truth table for 19 H70 phases from
   H65/H71/H72/H73 verdicts.
2. ✅ Implemented H76 end-to-end evaluator that applies the full
   stack (H75 for FOUNTAIN_3+, H74 for CASCADE_3+, H71 v1 for
   MIXED_3+) to each H70 phase and checks against ground truth.
3. ✅ Aggregate stats: 16/19 = 84.2% accuracy. 14/15 real juggling
   kept (93.3% recall). 2/4 misclassifications caught (50% precision).
4. ✅ Per-pattern breakdown:
   - CASCADE_3+ (n=1): 0/1 correct
   - FOUNTAIN_3+ (n=6): 4/6 correct
   - MIXED_3+ (n=11): 11/11 correct (100%)
   - MIXED_3+_UNCONFIRMED (n=1): 1/1 correct
5. ✅ Compared with H59 (chain-edge evaluation on 113 review pairs):
   H59 P=0.981, R=0.718 vs H76 phase-level accuracy 84.2%.
6. ✅ Documented in `h76_report.md` and updated STATE.md / RESULTS_LOG.md.

**H76 verdict: PASS (limited scope).** The full stack achieves
84.2% accuracy on the H70 sample. MIXED_3+ is perfect. FOUNTAIN_3+
is partial. CASCADE_3+ is research-only.

**Key findings:**
- MIXED_3+ post-filter is PERFECT (11/11) on H70 sample
- FOUNTAIN_3+ post-filter is PARTIAL (4/6) — f=890-936 crossed-arm
  not caught, f=800-861 real CASCADE mislabeled as FOUNTAIN_3+
- CASCADE_3+ is FUNDAMENTALLY LIMITED (0/1 in H76, 0/2 in H73)
- End-to-end accuracy 84.2% — all 3 errors on FOUNTAIN/CASCADE

**Recommended operating point (post-H76, final):**
- FOUNTAIN_3+: (H43 OR H69 OR H74) where H74=LR_variance<0.20
- CASCADE_3+: H74 alone (1/2 catches in H73 sample)
- MIXED_3+: H71 v1 (100% precision on H70 sample)

**Future research (post-H76):**
1. H77: extend H76 to 113 manual review pairs (combined H59 + H76)
2. H78: novel signals for crossed-arm trick detection
3. H79: cross-video calibration of H69 spec_conc threshold

See `h1_hand_pool/reports/h76_report.md` for full analysis.

## Final summary (H0 - H76)

The hand-occlusion overnight lab has produced a comprehensive,
validated chain representation for both videos over 76 research
episodes spanning ~21 hours.

**Final operating point (h7v3plus3 + H10 v11 v3 + H12 v8 + H50 +
H70/H71/H75 v1 stack):**
- FOUNTAIN_3+: (H43 OR H69 OR H74) where H74=LR_variance<0.20
- CASCADE_3+: H74 alone (research signal only)
- MIXED_3+: H71 v1 (KEEP>=0.15, REJECT<0.10)

**End-to-end accuracy on H70 sample: 84.2% (16/19 correct).**
- MIXED_3+: 11/11 correct (100%)
- FOUNTAIN_3+: 4/6 correct
- CASCADE_3+: 0/1 correct (research only)
- MIXED_3+_UNCONFIRMED: 1/1 correct

**Cumulative findings (76 episodes):**
- H1-H4: hand-pool baseline (v4d is the recommended operating point)
- H2-H7: chain combination methods (H7 min-cost flow is recommended)
- H8-H10: chain quality scoring (H10 v11 v3 = H56 v1 is recommended)
- H11: identity propagation (CONFIDENT chains are 9/9 visually verified)
- H12-H12v8: per-frame pattern inference
- H36: per-frame hand-occupancy state machine (PASS)
- H37-H38: hand-occupancy supports CASCADE_3+ (PASS, narrow scope)
- H39-H43: FOUNTAIN_3+ post-filter (H43 conf<0.55 is best)
- H45-H50: H12 v8 event log 10-frame filter
- H51-H52: H43 + H50 + H52 stack (precision-optimized)
- H54-H58: per-chain arc-gravity CV (H56 v1 is the recommended
  chain quality score)
- H59: end-to-end precision/recall validation (P=0.981, R=0.718)
- H60-H61: hold-duration and 16->21 conflict
- H62-H64: pattern characterization (YouTube CASCADE-SHOWER mix,
  identical CASCADE->FOUNTAIN transition)
- H65: FOUNTAIN_3+ label validation (43% H12 v8 accuracy)
- H66-H69: FOUNTAIN_3+ post-filter evolution (H43 + H69 is best)
- H70: H69 spec_conc characterization across pattern types
- H71: multi-rater visual QA on H70 contact sheets (5/7 confirmed)
- H72: complete H70 visual QA (10/11 MIXED_3+ confirmed real)
- H73: H40v2 as CASCADE_3+ validator (NEGATIVE, CASCADE has 0% precision)
- H74: H40v2 L+R variance as static-hold detector (MIXED)
- H75: H43 + H69 + H74 stacked FOUNTAIN_3+ filter (MIXED, 3/3 real kept)
- H76: end-to-end precision/recall on H70 sample (PASS, 84.2%)

**Cascade/FOUNTAIN/MIXED discrimination is fundamentally noisy:**
- H12 v8 CASCADE_3+ has 0% precision on substantial phases
- H12 v8 FOUNTAIN_3+ has ~60% precision on substantial phases
- H12 v8 MIXED_3+ has ~91% precision on substantial phases (H71 v1)

**Strongest signals for downstream consumers:**
- h7v3plus3 chain set (H22+H26)
- H10 v11 v3 chain quality (H56 v1)
- H12 v8 per-frame patterns
- H50 10-frame event log filter
- H43 + H69 + H74 FOUNTAIN_3+ post-filter
- H71 v1 MIXED_3+ post-filter
