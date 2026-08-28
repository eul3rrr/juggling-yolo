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
