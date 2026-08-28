# Hand Occlusion Overnight Lab — Research Notes

Sources consulted, ideas harvested, and smallest experiment inspired by each. For every
useful source record:

- Title
- URL
- Idea
- Why it applies here
- Why it might fail here
- Smallest experiment inspired by it

---

## Internal references (read-only, in the juggling-yolo tree)

- `experiments/overnight/reports/` — prior experiment reports and figures
- `experiments/overnight/scripts/` — reusable analysis helpers
- `experiments/overnight/data/` — tracklet / review / pose artifacts
- `experiments/overnight/RESULTS_LOG.md` — findings ledger from previous overnight
- `experiments/overnight/STATE.md` — last session state snapshot

## External references

### TOTNet: Occlusion-Aware Temporal Tracking for Robust Ball Detection (2025)

- **Title:** TOTNet: Occlusion-Aware Temporal Tracking for Robust Ball Detection in
  Sports Videos
- **URL:** https://arxiv.org/pdf/2508.09650
- **Idea:** A neural network with 3D convolutions + visibility-weighted loss that
  maintains ball localization accuracy under partial and full occlusion in sports
  videos. Trained on 4 sports tracking datasets with state-of-the-art results in
  full-occlusion scenarios.
- **Why it applies here:** Our v4d approach is hand-crafted (rule-based on
  distance + slope + reach radius). TOTNet shows that a *learned* temporal
  model can also recover balls during occlusion, including full occlusion.
  The visibility-weighted loss is essentially a soft version of the
  "low-confidence evidence tier only near an active hand event" idea
  (master §14).
- **Why it might fail here:** TOTNet requires a labeled sports-tracking dataset
  to train. Our v4d approach is unsupervised and works on the existing
  detector outputs without retraining. Applying TOTNet would require either
  fine-tuning (we have very few labels) or using a pre-trained model
  (which may not generalize to juggling ball patterns).
- **Smallest experiment inspired:** H5 — add a low-confidence
  ByteTrack-style "second tier association" specifically within a
  ±30-frame window of v4d hand-links. If a v4 hand-link says
  "ball was held in the right hand at f=797", a low-confidence
  detection in the right-hand region between f=780 and f=815
  would be promoted to a held-ball observation. This is
  master §14 directly.

### ByteTrack (2022)

- **Title:** ByteTrack: Multi-Object Tracking by Associating Every Detection Box
- **URL:** https://github.com/FoundationVision/ByteTrack (paper at
  https://arxiv.org/abs/2110.06864)
- **Idea:** Associate *every* detection (high and low confidence) in two
  passes — first pass uses high-confidence detections, second pass uses
  low-confidence detections. The second pass recovers occluded or
  partially-visible objects without admitting background false positives
  in non-occluded regions.
- **Why it applies here:** v4d's main failure mode is detector dropouts
  near hands (the ball is *in* the hand so the detector often misses
  it). A second-tier association within hand regions would let us
  "fill in" the held-ball detection without globally lowering the
  detector confidence (which would admit many background false
  positives in mid-air regions).
- **Why it might fail here:** ByteTrack operates at the *detection box*
  level, not the *tracklet* level. Our work is downstream of the
  Norfair tracker. We'd need to re-process raw detections, which
  means re-running the detector (we only have the tracklet CSVs
  cached, not the per-frame raw detections).
- **Smallest experiment inspired:** Use the existing `stitches.csv` and
  `tracklet_features.csv` to identify tracklets that started
  immediately after a v4d hand-link (within ±5 frames) and check
  if their start confidence is below the v4d threshold. If so,
  the tracklet is a "low-confidence held-ball" candidate.

### Adaptive Confidence Threshold for ByteTrack (2023)

- **Title:** Adaptive Confidence Threshold for ByteTrack in Multi-Object Tracking
- **URL:** https://arxiv.org/abs/2312.01650
- **Idea:** Adapt the confidence threshold per-frame based on the
  scene's current detection density. When many high-confidence
  detections are present, lower the threshold (more permissive);
  when few detections are present, raise it (more strict).
- **Why it applies here:** Near an active hand event, the detection
  density is *higher* (the ball is at the hand, the hand is at
  the center of the frame, etc.). An adaptive threshold could
  *lower* the threshold near hand events, admitting more
  low-confidence detections specifically where the hand-pool
  expects them.
- **Why it might fail here:** Requires per-frame raw detections,
  not the cached tracklet CSVs.
- **Smallest experiment inspired:** Re-run the detector with
  confidence=0.1 and compare the additional low-confidence
  detections against the v4d hand-link predictions. If many of
  the new low-confidence detections fall within ±30 frames and
  within the 108 px reach of a v4d hand-link, the experiment
  validates master §14.

### Topic: multi-object tracking through occlusion

- **Internal reference:** TOTNet, ByteTrack (above).
- **Applied:** H4 (v4d) is a hand-crafted version of the same idea,
  applied at the tracklet level rather than the detection level.
- **Next:** H5 should add a low-confidence second-tier association
  near active hand events (master §14).

### Topic: hand-object interaction / contact reasoning

- **Internal reference:** H1 v1-v4 hand-pool (this work).
- **Internal finding:** A tracklet's *endpoint distance to the hand*
  and *approach slope* are the strongest discriminators of
  catch-throw events. The v4d `MIN_FROM_SLOPE = 2.5` filter
  rejects pass-throughs while keeping real catch-throws.

### Topic: low-confidence second-tier association (e.g. ByteTrack)

- **Internal reference:** TOTNet, ByteTrack (above).
- **Applied:** H1 v4d's `MIN_FROM_SLOPE` is a hand-crafted
  version: low-slope candidates are demoted from "throw" to
  "pass-through" without globally lowering the threshold.
- **H3 result:** H3's "stationary cluster" criterion
  (≥3 low-conf dets in 30px radius over ≥5 frames) was tested
  in 3 iterations. v3 correctly confirms 6/6 identical-video
  v4d hand-link held phases as real held balls, with 1 false
  positive on the YouTube video (stuck on face). H3 is
  useful as a downstream confidence signal but does not
  recover v4d-missed links.

### Topic: min-cost flow / factor-graph stitching

- **Internal reference:** E6c on main.
- **Applied:** H2 combines E6c mid-air edges with H1 v4d
  hand-links using a union-find. This is much simpler than
  min-cost flow but achieves the same goal: produce a
  single chain representation. Min-cost flow could improve
  H2 by handling the tracklet-3 conflict optimally (instead
  of recording it).

### Where Is The Ball: 3D Ball Trajectory Estimation From 2D Monocular Tracking (2025)

- **Title:** Where Is The Ball: 3D Ball Trajectory Estimation From 2D Monocular Tracking
- **URL:** https://arxiv.org/abs/2506.05763
- **Authors:** Puntawat Ponglertnapakorn, Supasorn Suwajanakorn (VISTEC)
- **Venue:** CVsports workshop at CVPR 2025
- **Idea:** LSTM-based pipeline for 3D ball trajectory estimation
  from 2D tracking sequences. Uses a canonical 3D representation
  independent of camera location, with intermediate representations
  for invariance and reprojection consistency. Trained on simulation,
  generalizes to real-world multiple-trajectory scenarios.
- **Why it applies here:** Our H7 chains are 2D-only (image
  coordinates). The Ponglertnapakorn paper validates the broader
  approach: estimate physical parameters that best explain the
  observed trajectory. H8 implements a hand-crafted version of
  this for our 2D-only setup: y-velocity should be continuous
  across ballistic edges (gravity changes it slowly).
- **Why it might fail here:** Ponglertnapakorn uses a learned
  LSTM trained on simulation. Our H8 is a hand-crafted metric
  (y-velocity discontinuity). H8 is simpler and less expressive
  but doesn't require a training set.
- **Smallest experiment inspired:** H8 — per-edge physics
  consistency check on H7 chains. For each BALLISTIC edge,
  compare y-velocity at source-tracklet tail vs target-tracklet
  head. Flag edges with large discontinuity as likely identity
  switches. H8 successfully identified 2 confirmed E6c false
  positives (edges 5→6 and 50→55 on identical video) that
  H2/H6/H7 all accepted.

### Physics-based ball tracking and 3D trajectory reconstruction (2009)

- **Title:** Physics-based ball tracking and 3D trajectory
  reconstruction with applications to shooting location estimation
  in basketball video
- **URL:** https://www.researchgate.net/publication/222568476
- **Idea:** Physics-based ball tracking using 3D marker positions
  to coregister 2D video and 3D motion, applied to three-ball
  cascade juggling. Physics constraints (gravity, momentum) help
  disambiguate occluded or noisy detections.
- **Why it applies here:** Validates the long-standing idea that
  physics constraints improve ball tracking. H8's velocity
  discontinuity check is a simple version of this principle.
- **Why it might fail here:** Requires 3D ground truth (marker
  positions) for calibration. Our setup is monocular 2D only.
- **Smallest experiment inspired:** H8 itself.

### Cooperative Trajectory Matching (2024)

- **Title:** Ball Tracking Based on Multiscale Feature Enhancement
  and Cooperative Trajectory Matching
- **URL:** https://doi.org/10.3390/app14041376
- **Idea:** Multiscale feature enhancement + multilevel
  collaborative matching using Kalman filter for trajectory
  matching and automatic trajectory correction.
- **Why it applies here:** Their "automatic trajectory correction"
  step is similar to our H8: post-hoc validation of trajectory
  edges. They use Kalman filter predictions; we use direct
  y-velocity discontinuity.
- **Why it might fail here:** Requires training a multiscale
  feature extractor. Our approach is unsupervised.
- **Smallest experiment inspired:** Future v4 of H8 could use
  Kalman filter prediction (assuming constant gravity) to predict
  the expected velocity at the target tracklet's start, and
  compare to the actual velocity. This would be a stricter
  test than the simple discontinuity.

---

## Cross-cutting insights from this episode (2026-08-28 ~04:00-05:35)

1. **v4d's hand-edge wins on H2 conflict.** Visual QA on
   chain 3 (the only H2 conflict) confirmed that the
   hand-edge 3→9 is the correct inference and the E6c
   air-edge 3→8 is a false positive (tracklet 8 is a
   different ball). This validates a design principle:
   *hand-edges depend on direct evidence (ball at the hand);
   air-edges depend on predicted evidence (ballistic
   continuation). Direct evidence is more reliable than
   predicted evidence. When the two conflict, prefer the
   hand-edge.*

2. **The 3→9 "left/right swap" was a vision-verifier
   misinterpretation.** The vision_analyze tool repeatedly
   confused the contact-sheet color mapping (ORANGE=LEFT,
   BLUE=RIGHT in image coordinates) with the juggler's
   left/right (which is mirrored in the camera image).
   This is a tooling issue, not an H1 model issue. v4d
   inherits v2's consistent image-perspective hand
   attribution. Future contact sheets could use a clearer
   color scheme (e.g. LABEL the wrist circles directly).

3. **v4d's `MIN_FROM_SLOPE = 2.5` is well-chosen.** The two
   v3 false positives (15→25, 35→40) both have |from_slope|
   < 2.5; all 7 other inspected v3 links have |from_slope|
   >= 3.95. A sensitivity grid on the threshold (e.g.
   {2.0, 2.5, 3.0, 4.0}) could verify this is the optimal
   value, but 2.5 has a strong physical justification
   (a real catch has a clear approach signal of > 2.5 px/frame).

4. **The v1 ev0001 phantom catch is unrecoverable by any
   hand-pool model.** v4d cannot recover a catch that the
   detector never observed. This is a fundamental limitation
   of the input data, not a model bug. The H2 chain for
   this event is simply an UNMATCHED_EXIT, and downstream
   consumers should accept the identity ambiguity.

5. **The tracklet-3 conflict is not a model bug.** Both
   the hand-edge (3→9) and the air-edge (3→8) are
   geometrically plausible inferences from the data.
   Resolving them requires additional 3D hand-motion or
   temporal-continuity reasoning that the current models
   don't have. The H2 "record conflicts, don't silently
   resolve" approach is the right design.

6. **H3 stationary-cluster pattern is not specific to
   hand-events.** v3's baseline FPR (50-60% of random
   hand-region searches produce a stationary cluster) is
   HIGHER than the v4d-link rate (~11%). The "stationary
   cluster of low-conf dets" pattern is common throughout
   the video (the detector fires on stationary features
   for many reasons). H3 is useful only because it's
   *restricted* to v4d-link time windows. This is a
   crucial finding: a downstream consumer should not use
   H3 as a general held-ball detector, but it CAN use H3
   as a confidence signal on v4d links.

7. **The YouTube false positive is a detector limitation,
   not a criterion failure.** The YOLO detector confuses
   face/head features (skin tone, rounded shapes) with
   sports balls when the hand is near the face. The
   YouTube juggling pattern has the juggler's hand raised
   near the face during certain held phases, and the
   detector latches onto face features. This is a
   fundamental limitation of the YOLO model on this
   specific video. A face detector could mask out
   face-region false positives before clustering.

8. **H3 confirms but does not recover.** All 6 H3-confirmed
   identical-video v4d links were already v4d links; H3
   did not recover any v4d-missed links. H3 is a
   *corroborating* signal (the held ball is genuinely
   there), not a *recovery* mechanism (it does not find
   new links that v4d missed). v4d's hand-event detection
   is the primary signal; H3 adds confidence.

9. **H4 face-mask hypothesis was wrong.** The H3 YouTube
   false positive is not face-feature confusion; it's
   a stuck detection on a stationary high-up object
   (~200 px above the wrist). A simple geometric mask
   cannot solve detector confusion on arbitrary
   stationary features. This is a useful negative
   result: it tells us that detector confusion is
   *general* (any stationary feature), not specific
   to faces. A real fix would require a more
   discriminating detector or a learned "ball-ness"
   classifier.

10. **H6 min-cost flow validates the "hand-edge wins
    on conflict" design principle.** A simplified
    per-source greedy min-cost flow (HAND=1.0,
    AMBIGUOUS_HAND=1.5, BALLISTIC=2.0) resolves the
    1 H2 conflict (tracklet 3 → {9, 8}) by picking
    the hand-edge (cost 1.5) over the air-edge
    (cost 2.0). This is the same answer as the visual
    QA on H2 confirmed. **The "hand-edge wins"
    principle is now backed by both visual evidence
    AND a cost-based formulation.**

11. **H10 chain quality is a real signal.** The
    composite quality score (0.30*h3 + 0.30*h8 + 0.40*h9)
    successfully separates real single-ball chains from
    multi-ball merges. Top-quality chains (chain 23,
    chain 6) are real juggling cycles. Low-quality
    chains (chain 13) are dominated by false ballistic
    edges. Mid-quality chains (chain 30) contain
    identity switches. H10 has 1 false positive
    (chain 38) due to H8+H3 limitations, but this is
    a known limitation of the underlying H8 check.
    **H10 is useful as a downstream confidence signal
    for chain consumers** (e.g. juggling-pattern
    analyzers).

12. **H8 v4 short-tracklet-only is a regression.**
    Restricting H8 to tracklets with n_pts <= 30
    removes the YouTube false positives but also
    misses 2 known true positives (5→6, 50→55) on
    identical. The trade-off is not worth it. The
    right fix is a graduated penalty (parabolic fit
    on long-tracklet tails) rather than a binary
    skip. H8 v3 remains the primary H8 signal for
    H10.

13. **H8 v5 parabolic-fit is incrementally better
    on identical.** v5 catches 2 NEW identity
    switches on identical that v3 missed (60→64,
    21→22) by using a parabolic fit instead of
    a 3-frame mean velocity. v5 also confirms all
    v3 catches. YouTube limitation persists: long
    tracklets span multiple parabolic arcs, so the
    parabolic-fit tail/head are at different points
    in the juggling cycle. v5 flags these as
    violations, but they're really just phase
    changes. **A fundamentally different approach
    (per-bounce segmentation) is needed for
    YouTube long tracklets.**

14. **H10 v5 (with v5 physics) is better-calibrated
    than H10 v3 (with v3 physics).** v5 correctly
    demotes 2 v3-false-positives (chains 24, 29:
    air edges not following physics) and promotes
    1 v3-false-negative (chain 36: large 33-frame
    gap is consistent with a real parabolic arc).
    H10 v5 is the new recommended chain quality
    score, replacing H10 v3. **The H10 quality
    ranking is now a real signal for downstream
    consumers.**

---

## See also

- `h1_hand_pool/reports/h1_v3_report.md` — soft catch-context
  and throw-window sensitivity grid
- `h1_hand_pool/reports/h1_v4_report.md` — multi-feature
  filter (v4d is the recommended operating point)
- `h1_hand_pool/reports/h2_report.md` — combined AIR+HAND
  chain representation
- `h1_hand_pool/reports/h1_v1_report.md`, `h1_v2_report.md`
  — earlier H1 work

## Cross-cutting insights from H11 (2026-08-28 ~08:55)

15. **H11 identity propagation is a useful downstream
    consumer of H10 v5 quality.** The 9 CONFIDENT identical
    chains + 1 CONFIDENT YouTube chain all correspond to
    visually-verified single-ball juggling cycles (chain
    2 left-hand catch-throw, chain 8 right-hand hold-throw,
    chain 6 YouTube right-hand catch-throw). H11's
    classification (CONFIDENT, UNCERTAIN, LOW) is robust
    to threshold perturbations across (0.5-0.9, 0.3-0.5).

16. **Per-frame census is meaningful on identical (51%
    cascade time) but misleading on YouTube (100% cascade
    time = over-counting).** The YouTube over-counting is
    caused by the H10 v5 quality being mostly UNCERTAIN
    (q < 0.6) on long tracklets. The cascade metric is
    sensitive to the quality threshold (drops from 56% at
    q >= 0.3 to 15% at q >= 0.7 on identical).

17. **H11 v2 identity-merge candidate is a FALSE POSITIVE.**
    The chain 36 ↔ chain 30 candidate passed the temporal
    criterion (chain_start within 30 frames of an event)
    but failed spatial proximity (t62 and t63 are 73
    pixels apart at f=890, NOT co-located). Future H11
    v4 should add explicit ball-position spatial proximity
    (e.g., within 30 px of the hand at merge time).

18. **The "5 balls at f=700" anomaly on identical is a
    real detector multi-ball merge.** H11 v2's per-frame
    census correctly identifies it as 4+ balls, but the
    underlying cause is H8 v5 over-counting (the long
    tracklets chain algorithm accepts as separate physical
    balls). This is a chain-quality problem, not a census
    problem.

19. **H11 enables juggling-pattern analysis.** With
    physical ball IDs assigned, a downstream consumer can:
    - Build a "ball 0 / ball 1 / ball 2" sequence for a
      3-ball cascade juggler
    - Detect pattern transitions (cascade → fountain → shower)
    - Quantify ball-hold times per hand
    - Detect dropped balls (chain_start with no predecessor
      in the expected time window)

    H11 v1 (per-tracklet ball_id) is the first step
    toward this. H12 (per-catch-frame pattern inference)
    is the next step.

20. **The vision_analyze tool is unreliable for spatial
    analysis of contact sheets.** In the chain 36 ↔
    chain 30 merge candidate QA, the vision tool claimed
    "t62 and t63 share nearly identical (x,y) positions
    across 5+ consecutive frames" — but the actual data
    shows t62 at f=890 = (660, 432) and t63 at f=890 =
    (587, 414), 73 pixels apart. The vision tool's spatial
    reasoning is unreliable. Visual QA should be
    supplemented with programmatic coordinate checks.

## Cross-cutting insights from H11 v4 (2026-08-28 ~09:00)

21. **H11 v4 spatial proximity correctly removed the
    v2 false positive.** The chain 36 ↔ chain 30
    CONFIDENT-merge candidate had t62 (chain 36) at
    (660, 432) and t63 (chain 30) at (587, 414) at
    f=890 — 73 pixels apart in 2D distance, NOT
    co-located. H11 v4's SPATIAL_RADIUS=80px filter
    correctly rejects this candidate.

22. **No real missed-merge opportunities exist within
    the v2's 30-frame window.** The 6 v4 candidates
    that pass the spatial filter all fail the velocity
    coherence test (vel_diff > 5*sqrt(2) = 7.07). This
    is a real negative finding: the H7 chain algorithm
    is largely correct, and there are no obvious cases
    where it split a single physical ball across two
    chains.

23. **Sensitivity grid shows the (80, 5) operating
    point is in a flat region.** SPATIAL=50 (very
    strict) admits only 2 candidates; SPATIAL=108
    (reach radius) admits 7 candidates including 1
    CONFIDENT (the v2 false positive). The (80, 5)
    choice is conservative enough to remove the v2
    false positive while admitting any other plausible
    merge candidates.

24. **2D distance to wrist is a useful but imperfect
    proxy for "at the hand."** A ball at (725, 601)
    is 71 pixels from the left wrist at (728, 530) in
    2D distance, but is NOT at the hand — it's below
    the hand. A future H11 v5 could use a more
    sophisticated "hand-relative" coordinate system
    (e.g., polar coordinates centered on the wrist, or
    a 2D Gaussian centered on the wrist with smaller
    variance in the radial direction than the angular
    direction).

25. **Identity-merge algorithms should be conservative.**
    H11 v2's 42 candidates included 1 CONFIDENT false
    positive. H11 v4's 6 candidates all fail the
    velocity test, suggesting they are all false
    positives. An aggressive merge algorithm would
    produce too many false positives; a conservative
    one is more useful for downstream review.

## Cross-cutting insights from H12 (2026-08-28 ~09:15)

26. **H12 successfully identifies juggling pattern
    phases on identical.** 0-220 FOUNTAIN_3+, 300-700
    CASCADE_3+ (main pattern), 700+ mixed. The 4-phase
    pattern is consistent with a 3-ball trick with
    multiple distinct phases. The 33.8% UNKNOWN frames
    are a useful safety net for low-quality periods.

27. **H12 on YouTube is unreliable** because H10 v5
    over-counting dominates. 93.2% CASCADE_3+ on YouTube
    is the over-counting artifact, not a real pattern.

28. **CASCADE_3+ vs FOUNTAIN_3+ distinction is based
    on `unique_hands` of recent events.** With only 8
    catch/throw events on identical, this distinction
    is weak. A future H12 v2 could use a sliding
    window of multiple events instead of the simple
    "recent" window.

29. **H12 demonstrates that H11's per-frame census is
    a useful downstream measurement.** H12 turns the
    census (a count) into a pattern label (a class).

## Cross-cutting insights from H12 v2 (2026-08-28 ~09:50)

30. **UNKNOWN should be propagated as low confidence, not a
    binary label.** H12 v1 dropped everything below
    MIN_QUALITY_FOR_PATTERN=0.5 to UNKNOWN, hiding the chain
    quality information. H12 v2 propagates chain quality as
    the pattern's confidence, so a 0.42 quality chain with
    CASCADE_3+ becomes "CASCADE_3+ at conf 0.42" — much more
    informative for downstream consumers.

31. **The "MIXED" category is essential for honest
    classification.** A binary CASCADE/FOUNTAIN classifier
    would force every 3-ball frame into one of two classes
    even when the data is inconclusive. The MIXED_3+
    category (3+ events but criteria not strictly met) and
    MIXED_3+_UNCONFIRMED (1-2 events) explicitly say "I
    can't decide". On identical, MIXED_3+ goes from 0% (v1)
    to 29.3% (v2), a substantial gain in honest reporting.

32. **Phase detection enables temporal analysis.** H12 v2
    emits explicit pattern phase transitions
    (`pattern_phases_v2_*.csv`). On identical, 13 substantial
    phases (n_frames >= 20) reveal a 3-phase structure:
    early cascade-with-transitions → late fountain. This is
    a meaningful result that v1 couldn't produce.

33. **The YouTube "100% UNCONFIRMED" is the correct answer.**
    H12 v1's 93.2% CASCADE_3+ on YouTube was a classification
    forced by the census (n_total=5 in 601/898 frames).
    H12 v2's MIN_EVENTS_FOR_PATTERN=3 prevents this: with
    only 1 catch/throw event on YouTube, all frames are
    correctly classified as MIXED_3+_UNCONFIRMED. The n_total
    signal in YouTube is over-counting due to long tracklets
    being split by the chain algorithm.

34. **CASCADE/FOUNTAIN classification is fundamentally limited
    by event log density.** With only 8 events on identical
    (and 4 of them on the right hand at f=788-1052), the
    algorithm concludes "same-hand dominance" → FOUNTAIN_3+
    for frames f=890-1050. Visual QA confirmed those frames
    are actually a CASCADE (balls cross between hands). The
    H12 v2 algorithm is honest about its uncertainty via
    confidence, but the underlying event log is too sparse
    to disambiguate. **Future H12 v3 should integrate
    detector-level ball position signals** (per-frame ball
    x,y relative to each hand, not just n_in_hand counts).

35. **n_total is a chain count, not a ball count.** Visual
    QA on the f=335-382 SINGLE_BALL phase (conf=0.93) found
    2 balls in the air, but the algorithm reports n_total=1
    because only 1 chain is active. The airborne ball is a
    low-confidence detection not incorporated into any
    tracklet. **Future H12 v3 should use raw detector
    output, not just tracklet chain membership.**

36. **Sensitivity grid (K=4, MIN=3) is in a flat region.**
    13 of 15 cells in the (K, MIN) grid give the same MIXED_3+
    dominance on identical. The 2 outliers are (K=2, MIN=2)
    which gives 48.9% FOUNTAIN (too few events), and
    (K=2, MIN=3) which gives 51.0% MIXED_3+_UNCONFIRMED
    (correctly conservative). The default (K=4, MIN=3) is
    a well-justified operating point.

## Cross-cutting insights from H12 v3 (2026-08-28 ~10:10)

37. **Visual QA of v3c-rejected links is informative.** Of
    the 2 v3c-rejected links, 1 was a real catch-throw
    incorrectly rejected by v4d (35->40 identical), and 1
    was correctly rejected (15->25 YouTube). This validates
    the v4d threshold's overall correctness while showing
    it has a small (~1 of 11) false negative rate.

38. **Enriching the event log has limited effect on late-phase
    classification.** Adding 1 visually-confirmed event
    (35->40 at f=535) changes only 26 frames (f=797-829)
    from FOUNTAIN_3+ to MIXED_3+. The late FOUNTAIN_3+ blocks
    (f=890-1050) are unchanged because the new event is too
    far in the past to be in the K=4 window. **This confirms
    the H12 v2 limitation is fundamental: CASCADE/FOUNTAIN
    classification is limited by event log density.**

39. **A truly different approach is needed for the late
    phase.** H12 v3 demonstrates that the event-log-based
    classification cannot be fixed by adding more events.
    The late phase's right-hand-biased window leads to
    FOUNTAIN_3+ classification even though the visual
    evidence is cascade. A detector-level signal (per-frame
    ball positions relative to each hand) is needed.

40. **The H12 v2/v3 confidence values are honest about
    uncertainty.** The FOUNTAIN_3+ blocks at f=890-1050
    have conf=0.42-0.63, which is lower than the MIXED_3+
    blocks at conf=0.85-0.93. The lower conf reflects the
    algorithm's lower certainty, which is consistent with
    the visual evidence. Downstream consumers can use the
    conf value to filter out low-certainty FOUNTAIN_3+
    labels.

## Cross-cutting insights from H12 v4/v5 (2026-08-28 ~10:35)

41. **Event-log-based classification is fundamentally limited by
    event density.** H12 v2/v3 use catch/throw events to classify
    CASCADE vs FOUNTAIN. With only 8 events on identical, the
    late-phase K=4 window is right-hand-biased and the algorithm
    misclassifies 71% of late-phase frames as FOUNTAIN. Adding
    1 more event (H12 v3) only changes 26 frames. The limitation
    is structural: a sparse event log cannot disambiguate patterns
    at per-frame resolution.

42. **Per-frame spatial signal is the only fix.** H12 v4/v5 use
    the horizontal-velocity direction of every airborne ball per
    frame. CASCADE → 2 distinct horizontal directions; FOUNTAIN →
    1 direction. This signal is per-frame, not aggregated over
    events. Late-phase v2 71% FOUNTAIN → v5 33% CASCADE / 38%
    FOUNTAIN, which matches the visual cascade.

43. **H12 v4 has a NO_BALL census bug.** When n_in_hand_left=0
    AND n_in_hand_right=0 but n_total=3, the airborne filter is
    too permissive: all 3 balls go into airborne but the vx signal
    is empty. v5's W=10 smoothing is robust to this.

44. **W sensitivity is NOT flat.** CASCADE fraction decreases
    monotonically with W (5→14.9%, 10→13.1%, 20→10.8%, 30→8.7%).
    W=10 is a reasonable default but the operating point is not
    in a flat region. The choice of W is a real hyperparameter,
    not noise. This is a known issue: v2 K sensitivity was flat,
    v5 W sensitivity is not.

45. **YouTube detector signal is dominated by H10 v5
    over-counting.** v4/v5 classify based on n_distinct_dirs of
    all airborne balls. With n_total=5 inflated by over-counting,
    the 5 balls are mostly from 1-2 long tracklets, so the
    n_distinct_dirs is almost always 2 → CASCADE. The YouTube
    v4/v5 result is not a real CASCADE classification; it's an
    artifact. **Future work must fix H10 v5 over-counting before
    the YouTube detector signal is meaningful.**

46. **H12 v4/v5 are a meaningful contribution but not a
    complete solution.** They fix the late-phase FOUNTAIN
    misclassification, but they don't perfectly classify
    CASCADE (still 38% FOUNTAIN in late phase). The detector
    signal is noisy because juggler hands move during cascade.
    A future H12 v6 should ensemble v2 (event log) and v5
    (detector signal) — use v2's high-confidence windows
    (clear K=4 sequences) to anchor v5's per-frame signal.

## Cross-cutting insights from H8 v7 / v8 (2026-08-28 ~11:00)

47. **Smoothing destroys parabolic-arc boundaries.** H8 v7's
    vy-smoothing with K=2 made long tracklets look like a
    single monotonic arc, defeating the goal of per-bounce
    segmentation. 73/76 identical and 38/40 YouTube tracklets
    were detected as 1-arc. The lesson: detection of arc
    boundaries needs to be done on the RAW signal, not the
    smoothed signal. v8's local-extrema approach with
    min-distance=5 filter achieves this.

48. **Per-arc gravity distribution is a useful tracklet quality
    signal.** H8 v8 produces per-arc parabolic fits. Tracklets
    whose arcs all have g close to the expected value (0.5)
    are clean parabolic tracklets. Tracklets with widely varying
    g across arcs are noisy. Future H10 v6 should integrate
    per-arc g consistency as a 4th quality dimension. The
    YouTube per-arc gravity median is 0.46 (close to 0.5),
    suggesting YouTube tracklets are clean parabolic motions
    despite being long. The identical per-arc gravity median
    is 0.69 (higher), suggesting the juggler is closer to the
    camera (pixel/m^2 ratio is larger) OR the parabolic motion
    is contaminated by hand motion during catch/throw.

49. **Most YouTube H7 BALLISTIC edges are catch+throws in
    disguise.** H8 v8 finds 0/24 OK on YouTube because the
    cross-edge velocity discontinuity is large. But the
    discontinuity is real (catch+throw) not anomalous
    (identity switch). The H7 chain algorithm should
    re-classify YouTube edges as HAND_TRANSITION if they
    pass through a hand region. This is a future H7 v2
    enhancement.

50. **Per-arc segmentation reveals a fundamental difference
    between identical and YouTube.** Identical has mostly
    1-arc tracklets (single parabolic motions) because the
    detector drops out frequently. YouTube has 2-12 arcs
    per tracklet because the long tracklets span multiple
    parabolic arcs. The two videos have different
    detection profiles, and the algorithms need to handle
    them differently. The current approach treats them
    uniformly, which is why YouTube is harder.

## Cross-cutting insights from H12 v6 / v6b (2026-08-28 ~11:45)

51. **v2/v5 ensemble is honest but loses signal.** v6 reports
    MIXED_3+_ENSEMBLE for all v2/v5 disagreements on
    CASCADE/FOUNTAIN. This is the conservative answer but
    loses the correct v5 signal in 6.3% of identical frames.
    v6b's confidence-weighted rule (v5 wins if c5 > c2+0.10)
    propagates v5's answer but adds a new risk: if v5 is
    wrong, v6b is wrong.

52. **Vision tool is unreliable for CASCADE/FOUNTAIN
    distinction on this video.** Three independent vision
    queries on different late-phase contact sheets all said
    FOUNTAIN, but the H12 v4/v5 visual QA said CASCADE in
    4/6 frames. The single-frame view doesn't capture the
    temporal pattern. This is a real epistemic limitation:
    cascade vs fountain cannot be reliably determined from
    single frames in this video.

53. **The detector signal is ambiguous.** Per-frame vx
    direction analysis: 58% 1-dir, 42% 2-dir in both early
    and late phases. The 2-dir signal is not strongly
    concentrated in cascade-like phases. Either the detector
    misses too many balls (causing vx=0) or the actual
    pattern is mixed. The detector signal is useful as a
    vote but not as a definitive answer.

54. **A truly different approach is needed for the
    CASCADE/FOUNTAIN question.** Possible directions:
    - Multi-view video (2 cameras from different angles)
    - Higher frame rate (60+ fps to capture apex/throw)
    - Temporal pattern recognition (LSTM or transformer
      on per-frame classifications)
    - Hand-region check: a BALLISTIC edge that crosses a
      hand region is a catch+throw, not a mid-air
      continuation
    - Ground truth from controlled experiments

    These are out of scope for the current data. The
    question is FUNDAMENTALLY UNRESOLVED.

## Cross-cutting insights from H10 v6 (2026-08-28 ~12:30)

55. **Per-arc gravity as a quality signal has opposite
    effects on the two videos.** Identical has mostly
    short tracklets where the parabolic fit is unreliable
    (apex near one end of the data window, asymmetric
    motion). YouTube has long tracklets with many arcs
    where the parabolic fit captures real motion. A
    single weight set cannot optimize for both. Future
    implementations should use per-video adaptive weights
    or length-dependent weights.

56. **Chain 21's h8v8=0.0 is a false negative.** t31 and
    t36 are real tracklets in a real chain (v5 quality
    0.966). The per-arc parabolic fit gives g=0.117
    because the apex is near the start of t31 and the
    t36 motion is purely falling. The parabolic
    coefficient g doesn't measure "parabolic-ness" well
    when the data doesn't span a full arc.

57. **H8 v8's per-arc statistics are still useful as a
    TRACKLET-LEVEL signal** even if the per-CHAIN
    composite (h8v8) doesn't work well. Future work
    should:
    - Use h8v8 only on YouTube (or long tracklets)
    - Combine h8v8 with tracklet length (longer
      tracklets → more reliable g)
    - Report h8v8 as a per-tracklet flag, not a
      per-chain composite

58. **Per-video adaptive weights solve the h8v8
    trade-off.** H10 v6b uses w8v8=0 for identical
    (preserves v5) and w8v8=0.25 for YouTube (improves
    over v5). This is the recommended operating point
    for mixed-video analyses. For single-video
    analyses, use the appropriate single weight set.
    The h8v8 dimension is real but the right weight
    depends on the tracklet length distribution.

59. **Length-dependent weight is intermediate between
    v5 and v6, which is worse than either extreme.**
    H10 v7 uses w8v8 = min(0.30, n_pts/200). On
    identical, w8v8 ranges 0.10-0.30 — short tracklets
    still get h8v8 noise. On YouTube, w8v8 caps at
    0.30 — same as v6b. v7 doesn't beat v6b on either
    video. The lesson: per-video fixed weights
    (step function) are hard to beat with length-
    dependent formulas (smooth function).


## Cross-cutting insights from H7 v2 (2026-08-28 ~13:30)

60. **BALLISTIC edges that pass through a hand region are
    usually catch+throws in disguise.** H7 v2 reclassifies
    13/37 identical and 25/27 YouTube BALLISTIC edges as
    HAND_TRANSITION. All 8 visually inspected edges
    confirmed as REAL_CATCH_THROW. The principle: a real
    catch happens at the hand, a real throw starts at the
    hand. A ballistic edge that connects to the hand at
    EITHER endpoint is likely a catch+throw pair.

61. **YouTube's 93% reclassification rate is the root cause
    of the H10 v5 over-counting.** H8 v3 was correctly
    flagging the velocity discontinuity at catch+throws,
    but the edges were labeled BALLISTIC, so the h8
    penalty was applied. H7 v2 fixes this at the chain
    construction layer, not the chain quality layer.

62. **The asymmetric reclassification rate (35% identical
    vs 93% YouTube) is a feature, not a bug.** It reflects
    the fundamental difference in detection profiles:
    - Identical: short tracklets with frequent detector
      dropouts. The BALLISTIC edges that remain (12) are
      real identity switches between simultaneously visible
      balls.
    - YouTube: long tracklets spanning many parabolic arcs.
      Most "ballistic" edges are actually catch+throws
      where the velocity discontinuity is real (catch+throw)
      not anomalous (identity switch).

63. **H10 v6b's per-video adaptive weights are no longer
    needed for the h8 dimension on YouTube.** After H7v2,
    14/15 YouTube chains have n_air_edges=0, so h8=1.0
    universally. The w8v8 dimension still matters (h8v8
    captures per-arc gravity consistency) but the
    per-video h8 distinction is moot.

64. **H7v2 + H10v8 is a one-line architectural change
    with outsized impact.** The h7v2 reclassification
    rule is ~20 lines of code, but it transforms the
    YouTube H10 quality distribution: mean 0.537 → 0.679,
    and a real 7-tid juggling cycle (chain 0) becomes
    the top chain. This is the largest single-episode
    improvement since H10 v5.


## Cross-cutting insights from H12 v7 (2026-08-28 ~14:30)

65. **Chain quality and pattern classification are
    orthogonal.** H7v2 fixes the YouTube chain quality
    (h8 over-penalization), but the CASCADE/FOUNTAIN
    classification is still limited by event log density.
    These are two separate problems; fixing one doesn't
    fix the other.

66. **YouTube is genuinely a 5-ball pattern.** Visual
    confirmation at f=2 (4 balls) and f=500 (5 balls).
    The n_total=5 in 67% of frames is correct, not an
    over-counting artifact. Earlier interpretation of
    YouTube as "5 balls inflated by over-counting" was
    wrong — the 5 balls are real.

67. **Reclassifying edges changes event log density.** H7v2
    adds ~25 more hand-edge events to the YouTube event
    log (reclassified BALLISTIC edges). This changes the
    K=4 window contents, which changes the CASCADE/
    FOUNTAIN classification. H12 v7's identical CASCADE_3+
    drops from 6.8% to 0.2% because of this effect.

68. **The CASCADE/FOUNTAIN ambiguity is fundamentally
    unresolvable with single-camera 2D tracking.** The
    late-phase right-hand bias in the event log is a
    detection artifact (the detector misses some right-
    hand catch events), not a model bug. Multi-view or
    higher frame rate could fix it, but those are out of
    scope.

## Cross-cutting insights from H11 v6 (2026-08-28 ~15:00)

69. **The real payoff of H7v2 is YouTube ball ID coverage.**
    H11 v1 emitted 1 YouTube catch/throw event. H11 v6 emits
    48 (24x). This is because 25/27 YouTube BALLISTIC edges
    were reclassified as HAND_TRANSITION, which now counts
    as "hand-edge" in the identity propagation. The
    reclassified edges provide physical ball ID coverage
    for 24 of 40 YouTube tracklets (60%), compared to 1
    tracklet in v1.

70. **The 5-ball YouTube juggling pattern is now well-tracked.**
    chain 0 (7 tids, q=0.671) is a real juggling cycle with
    12 catch/throw events all on reclassified edges. This is
    the "5 balls in a 5-ball cascade" pattern that the visual
    confirmation at f=2 and f=500 showed.

71. **H11 v6's tradeoff: fewer CONFIDENT chains on identical.**
    H7v2's reclassification creates slightly different chains
    than h237v5, and some longer chains are split. The 3
    remaining multi-tracklet CONFIDENT chains on identical
    (chains 21, 20, 8) are still real single balls.

## Cross-cutting insights from H13 (2026-08-28 ~17:30)

72. **Master §14's "lower-confidence evidence tier only near
    hand events" is NOT a reliable held-ball detector.** H13
    tested the H3 v3 stationary-cluster criterion on a wider
    window (gap + 5 frames each side) and found that 3/6 v2
    CORROBORATED edges are h7v2_kept_ballistic (true identity
    switches). The criterion is more like "any ball near hand"
    than "real held ball". H3's `h3_confirmed` flag is therefore
    a noisy downstream signal. This is the most important
    negative finding of H13.

73. **Concentration ratio (n_in_reach / total) IS a real signal
    but correlates with gap length, not event type.** v4d
    hand-links have lower concentration (0.142) than h7v2-
    reclassified (0.201) and h7v2-kept-ballistic (0.206) on
    identical, but the difference is largely explained by v4d
    having longer gaps (18 frames vs 9-10) which means wider
    search windows. Cohen's d (h7v2_reclass vs v4d) = +0.965
    (large), but the discriminating power is mostly the gap
    length, not the event type.

74. **The detector doesn't strongly distinguish catch-throws
    from identity switches on identical.** h7v2_reclassified
    and h7v2_kept_ballistic have statistically identical
    concentration (CI [-0.047, +0.041] includes 0). This
    validates H7v2's geometric reclassification rule (which
    doesn't depend on the detector signal) but also shows that
    a "smart" detector that could see the held ball during
    reclassified edges would still be a noisy signal at best.

75. **Mean concentration at hand events (0.15-0.30) is similar
    to the mean concentration at random hand-region windows
    (0.21 identical, 0.36 YouTube).** The detector fires
    constantly on background; the hand region is not
    significantly enriched in low-conf dets compared to other
    hand-region windows. This is consistent with the H3
    baseline FPR of 50-60% — the pattern "low-conf sports
    ball near hand" is not specific to hand-events.

76. **H13 was implemented as the natural follow-up to H3's
    master-§14 work.** H3 was restricted to v4d hand-links
    only; H13 extends the analysis to H7v2-reclassified edges
    and to h7v2-kept-ballistic edges (the control group).
    The extension reveals that the v3 stationary-cluster
    pattern is not specific to real catch-throws — it's a
    general "ball at hand" pattern that fires on identity
    switches too.

77. **A stricter H3 would need additional filters.** The
    single best filter would be: the cluster must be at the
    EXACT hand used by the v4d rule, and no other hand should
    have cluster activity simultaneously. This would rule out
    the 41->43 case (where 2 balls at the right hand look like
    one cluster) and similar multi-ball-in-one-hand patterns.
    A future H13 v2 could test this stricter criterion.

## Cross-cutting insights from H14 (2026-08-28 ~17:55)

30. **H7v2's strict endpoint-signature rule misses some real
    catch-throws.** H14's V-shape check (looking at the full
    source-tail + gap + target-head trajectory) recovered 4
    hidden catch-throws (23→25, 30→33, 39→47, 51→52 identical)
    that the strict h7v2 rule rejected. The 4 missed edges have
    a clear V-shape toward a hand in the gap, but the endpoint
    signature (end_dist <= 108, |slope| > 1.0) is degraded
    (often because the ball's last detection is just outside
    108 px, or because the catch/throw slope is gentle).

31. **V-shape is a position-only check; a velocity check would
    reduce the YouTube 27→28 false positive.** The 27→28 case
    has positions close to a hand on both sides, but the ball
    jumps 100 px in 5 frames (20 px/frame, faster than gravity
    allows). A velocity jump check would reject this.

32. **Combined H7v2 + H14 = +35% recall on identical hand-link
    recovery.** Total: 11 v4d + 13 h7v2_reclassified + 4 h7v2_kept_v_shape
    = 28 catch-throws on identical (vs 24 with h7v2 alone).
    This is a meaningful improvement; H14 is recommended as
    an add-on to H7v2, not a replacement.

33. **The h7v2 rule is fundamentally endpoint-driven; the
    h14 rule is fundamentally trajectory-driven.** They
    complement each other. The h7v2 rule has a strict signature
    that works well for the easy cases; h14 catches the hard
    cases where the endpoint signature is degraded but the
    trajectory is clearly V-shaped.

## Cross-cutting insights from H15 v2 (2026-08-28 ~18:00)

34. **Velocity-jump is the wrong discriminator.** H15 v1
    attempted to combine V-shape + velocity-jump (JUMP_TOLERANCE=15
    px/frame). It rejected 23→25 (real catch, jump=23.4) and
    admitted 27→28 (FP, jump=14.5). The threshold discriminated
    in the WRONG direction. The 27→28 case has a 100-px jump in
    5 frames, which IS too fast for a real ball (20 px/frame
    exceeds gravity at 0.5 px/frame² even with horizontal motion),
    but the JUMP_TOLERANCE=15 was set above the FP jump and below
    the real jump, so the rule was inverted. A more principled
    filter would use a parabolic-fit check on the gap trajectory:
    a real ball follows a parabola, while a tracklet break
    doesn't.

35. **H15v2's V-shape is more permissive than ideal.** 4/5
    V-shape candidates (80%) are visually plausible catch-throws
    on the edge boundary, but only 2/4 identical V-reclassified
    chains (50%) are clean catch+throws when examined in full
    chain context. The 2 hand-borne cases (23→25, 39→47) are
    correctly NOT BALLISTIC, but the strict "catch+throw" label
    is over-generous. The ball is being handled/carried, not
    thrown.

36. **H10 h3=None redistribution bug was exposed.** Adding
    V_RECLASSIFIED edges to the h3-eligible set initially
    REDUCED chain quality (because V_RECLASSIFIED has no
    h3 confirmation). The fix in H10 v9: V_RECLASSIFIED is
    excluded from h3-eligible set. The bug is pre-existing in
    H10 v5/v6/v7/v8 but was hidden because no edges had the
    "hand-edge with no h3 confirmation" property. V_RECLASSIFIED
    is the first such edge type.

## Cross-cutting insights from H11 v7 (2026-08-28 ~18:15)

37. **H11 v7 is a clean consumer of h7v3pure + H10 v9.** No
    new algorithmic decisions; just propagates the V-shape
    reclassification to the identity layer. The +5 catch+throw
    events on identical are entirely from V_RECLASSIFIED edges;
    the +1 on YouTube is the 27→28 FP.

38. **Chain 30 crossing the CONFIDENT threshold (0.427 → 0.727)
    is the most important outcome of H11 v7.** Chain 30 is a
    5-tid chain (51→52→54→59→63) that represents a real
    juggling sequence with 4 hand-edges and 1 V-reclassified
    hand-edge. The h10v9 quality improvement brings it from
    UNCERTAIN to CONFIDENT, making it available as a "real
    single ball" identity for downstream consumers.

39. **H15v2's 4/5 visual precision was on edge boundaries; H11
    v7's 2/4 visual precision is on full chains.** Both
    verdicts are correct in their context. The edge-boundary
    view is correct for "is the trajectory a V-shape? (yes)".
    The full-chain view is correct for "is the ball being
    thrown? (sometimes no — just being handled)". Downstream
    consumers should use H11 v7's catch+throw event log with
    the caveat that V-shape "events" include some hand-borne
    cases.

40. **The 27→28 YouTube FP propagates downstream: chain 12
    quality jumps 0.518 → 0.618 (+0.10).** This is a real cost
    of the V-shape reclassification. A future H16 should
    design a stricter V-shape check that combines position
    with motion signature to reject 27→28 (tracklet break,
    100-px jump in 5 frames) and the 2 hand-borne identical
    cases (23→25, 39→47) while keeping the 2 clean catch+
    throws (30→33, 51→52).

## Cross-cutting insights from H20 (2026-08-28 ~19:30)

31. **H20 reduces H17's FALSE-positive rate by 83%** while preserving
    100% of REAL and PARTIAL positives. The combination of three
    independent rejection rules (in-hand, vel-jump, apex-at-src)
    achieves 0.900 precision and 0.833 FPR drop on the 16-edge
    visual QA set, with stable sensitivity grid.

32. **The vel-jump rule is the dominant filter** (28/36 rejections).
    H17's 151 strict V-shape positives include many cross-tracklet
    jumps where the source ends at one ball position and the target
    starts at a completely different position (>70 px/frame gap
    velocity). These are not real catch+throw events; they are
    tracklet breaks where the detector lost the ball and re-acquired
    it elsewhere. A simple physical-velocity sanity check
    eliminates most of them.

33. **The in-hand rule alone is too lenient** (only 1 rejection).
    Most of H17's 7 FPs are NOT in-hand held balls where both
    endpoints are stuck in the same hand; they are cross-ball errors
    (different physical balls at the same hand at different times)
    or tracklet-break artifacts (source held, target in flight
    through the hand region). The in-hand rule is too narrow to
    catch these.

34. **The apex-at-source rule is a useful refinement of the V-shape
    check.** A V-apex that coincides with the source's stationary
    position is an artifact of the source's last frame, not a real
    parabolic catch+throw. This catches the "ball briefly held at
    hand then re-detected in flight" failure mode.

35. **H20 is a strict post-filter, not a chain-set augmentation tool.**
    Of the 26 H20-KEPT e6c_not_in_h7v2 candidates, 5/8 visually-QA'd
    are REAL or PARTIAL. This is a useful candidate list for
    chain-set augmentation (potential H21), but a larger visual QA
    sample is needed to characterize the precision of the pool
    as a whole.

36. **The 88 H20-KEPT adjacent candidates span gap=1 to gap=30 with
    no clear concentration.** A small visual QA sample would
    characterize the precision of the short-gap (≤10) vs long-gap
    (>10) subsets. Short-gap adjacent positives (5 with min_d < 30)
    are likely real catch+throws and could be a useful additional
    candidate pool for chain-set augmentation.

37. **Vision verification of H20's REJECTED FPs is reliable.** All 5
    H20-REJECTED FALSE positives were independently confirmed by
    `vision_analyze` as held-ball or cross-ball false positives,
    not real catch+throws. The H20-KEPT FALSE (YouTube 10→11) was
    also independently confirmed as ambiguous (held source, airborne
    target, no visible catch in the 3-frame window).

## Cross-cutting insights from H21 (2026-08-28 ~20:00)

38. **H21 chain-set augmentation integrates 3/4 visually-confirmed REAL
    H20-KEPT edges.** The merging of (5,6)+(15) → (5,6,15),
    (51,52,54,59,63)+(57) → (51,52,54,57), and (56)+(58) → (56,58)
    are the first chain augmentations driven by the V-shape analysis.
    These chains now represent longer juggling sequences that the
    h7v3pure pipeline missed.

39. **H21 v2 chain quality is slightly worse on identical (-0.023).**
    Adding more tracklets to existing chains can introduce BALLISTIC
    edges that h8 v5 flags as VIOLATING, reducing the chain's h8 score.
    This is a real signal: the V-shape analysis finds catch+throws that
    are physically real but introduce a discontinuity in the chain's
    parabolic motion. A future experiment could weight these "V-recovered
    edges" more carefully in H10 v9 quality.

40. **The YouTube 20→21 case reveals a deeper truth about chain
    capacity conflicts.** When two edges compete for the same successor
    slot (16→21 vs 20→21 both want t21 as successor), the algorithm
    keeps the first one admitted and rejects the second. But visual
    analysis suggests 20→21 is the real catch+throw (tracklet 20 is
    the canonical contact tracklet) and 16→21 is spurious (tracklet
    16 is a long earlier-detection with the catch happening after t16
    ends). A future H22 with a "veto" mode could resolve this by
    comparing edge confidence and overriding the weaker one.

41. **The H21 algorithm's "first-come-first-served" capacity rule is
    a known limitation.** The H7v2 / H7v3pure pipeline uses a greedy
    min-cost flow that admits edges in cost order (hand-edges before
    air-edges). When two edges have similar cost, the order they
    appear in the input determines the outcome. This is a stable but
    not necessarily optimal solution. A true min-cost flow with
    capacity constraints (e.g., a Hungarian assignment) would be more
    principled.

42. **H21 motivates a deeper investigation of "which tracklet is the
    canonical contact?"** The 20→21 case shows that two tracklets
    (t16 and t20) can both be in the right-hand region at the same
    time, with the actual catch happening on the shorter (3-pt)
    tracklet. This suggests a more general rule: **a contact event is
    more likely to be the SHORTEST tracklet in a hand-region cluster,
    not the longest.** A future H22 could implement this rule.

## Cross-cutting insights from H22 (2026-08-28 ~20:15)

43. **H22 veto mode confirms the visual analysis that 16→21 is wrong.**
    The H20-KEPT 20→21 edge (V-shape min_d=5.3, the ball is right
    at the wrist) has stronger evidence than the existing 16→21
    edge (target start_dist=35.3, the ball is 35 px from the wrist).
    The H22 veto correctly prefers the H20-KEPT edge, producing a
    slight chain quality improvement (+0.0034 on YouTube).

44. **The "source successor" check is a conservative choice.** H22
    excludes H20-KEPT edges whose source already has a successor in
    the chain set. This prevents the veto from breaking existing
    chains, but it also limits the veto's applicability. A more
    aggressive H22 v2 could allow source successor conflicts if
    the H20-KEPT edge is much stronger.

45. **Chain topology change is significant.** The H22 veto splits
    the original 7-tid YouTube chain (1,9,13,16,21,29,34) into 2
    chains (1,9,13,16) and (20,21,29,34). This is a real change
    in the chain structure, not just an edge reclassification.
    The mean quality improvement is small (+0.0034) because both
    sub-chains are still high-quality multi-tracklet chains.

46. **H22 is a useful diagnostic tool, not a chain-set replacement.**
    The h7v3pure chain set has the longer 7-tid YouTube chain that
    the production system considers correct. H22 reveals that this
    chain has a spurious edge (16→21), but correcting it requires
    chain topology changes that may not be worth the small quality
    improvement. h7v3pure remains the recommended chain set.

47. **The H22 veto mode generalizes the H20 visual confirmation
    principle.** H20 found that the strict V-shape positives
    include 5 visually-confirmed REAL H20-KEPT edges. H21 showed
    that 3/5 can be cleanly added to the chain set, and 1/5
    (YouTube 20→21) requires vetoing an existing edge. H22 is the
    veto mechanism. Together, H20 + H21 + H22 form a complete
    pipeline for integrating V-shape-discovered catch+throws into
    the chain set.

## Cross-cutting insights from H32 (2026-08-28 ~12:30)

26. **H32 confirms: h7v3plus2 chains are mostly multi-ball merges.**
    Per-chain hand-alternation-based CASCADE/FOUNTAIN classification
    has only 14.3% precision on visual QA. 5/7 visual-QA'd chains are
    MULTI_BALL_MERGE. The h7v3plus2 chain set is valid as "hand-event
    lists" but NOT as "single-ball trajectories." Multiple physical
    balls being juggled simultaneously produce a chain with edges
    that all have hand-region support, but the chain is not a
    single-ball trajectory.

27. **The CASCADE/FOUNTAIN problem is a single-ball-vs-multi-ball
    identification problem.** H12's per-frame CASCADE/FOUNTAIN
    classification has fundamental limitations because the
    underlying chain set is mostly multi-ball merges. The
    "CASCADE/FOUNTAIN" question presupposes a single-ball
    trajectory, which is not what we have.

28. **Cascade vs. Fountain (Wikipedia):** the canonical definitions
    validate H12's frame-level criterion:
    - CASCADE: balls thrown BETWEEN hands (both hands used)
    - FOUNTAIN: each hand juggles separately (balls don't cross)
    - FOUNTAIN requires even number of balls; CASCADE requires odd
    This is the basis for H12's per-frame CASCADE/FOUNTAIN
    classification. But the chain-level hand sequence is
    confounded by multi-ball merges.

29. **Realtime perception for catching a flying ball (Birbach 2011,
    DLR) — https://elib.dlr.de/74466/1/Birbach2011.pdf** — uses
    stereo camera + Kalman filter + partitioned visual servoing
    for 3D ball tracking. Validates the idea that physics-based
    prediction (Kalman filter) is a key signal for ball tracking
    during occlusion. Our H8 v5 parabolic-fit is a 2D-only
    hand-crafted version of this principle.

30. **Multi-camera 3D ball tracking (Wu 2020) — https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/iet-ipr.2020.0757**
    uses 2D detection → 2D tracking (ECO-based) → 3D fusion
    (triangulation) → 3D tracking (Kalman). Multi-view is the
    standard solution for ball tracking during occlusion. Our
    single-camera 2D setup is fundamentally limited.

31. **OC-SORT (mentioned in getstream.io/blog/ai-ball-player-tracking)
    prioritizes visual evidence over predictions during erratic
    movements.** This is similar to our H32 finding: relying on
    chain-level predicted evidence (e.g., CASCADE/FOUNTAIN
    classification) is unreliable when the underlying signal is
    confounded by multi-ball merges. Visual evidence at the
    per-frame level (e.g., counting distinct balls) is more
    reliable.

## Cross-cutting insights from H39 (2026-08-28 ~14:35)

32. **H12 v8 FOUNTAIN_3+ classification is fundamentally
    unreliable.** Visual QA on 10 FOUNTAIN_3+ phases (n>=10)
    found only 3 are real FOUNTAIN — 4 are MIXED, 1 is CASCADE,
    2 are OTHER (hold trick + 2-ball exercise). H12 v8
    over-classifies FOUNTAIN_3+ by ~70%. The underlying cause
    is H12 v8's K=4 sliding window of chain events: when the
    last 4 events are all same-hand, H12 v8 calls FOUNTAIN_3+
    even when the visual pattern is CASCADE or MIXED.

33. **H36 chain-driven state is too sparse to validate
    FOUNTAIN_3+.** H36 only emits state changes at chain
    events. Most FOUNTAIN_3+ phases span intervals between
    chain events, where H36 reports HOLD state (0, 0, total)
    even when the juggler's hands ARE occupied. H39 v1
    (frame-level) over-rejects 6/10 real juggling phases
    because H36 doesn't see the hand-occupancy during chain-
    event gaps. H39 v2 (phase-level) is more conservative
    but only 50% precise on small sample.

34. **The h7v3plus3 chain set's FOUNTAIN_3+ classifications
    should be considered suspect.** H38's CASCADE_3+
    post-filter is more reliable because CASCADE_3+ HAS
    hand-occupancy (per H37); FOUNTAIN_3+ doesn't have a
    corresponding positive signal. The H12 v8 FOUNTAIN_3+
    classification should be left as-is with the caveat
    that it has ~70% error rate.

35. **Continuous hand-occupancy signal is the missing
    ingredient.** A per-frame signal that checks "is any
    detected ball within hand reach (108 px) of either
    wrist at this frame?" would enable:
    - Reliable FOUNTAIN_3+ post-filter (FOUNTAIN requires
      continuous hand-occupancy in ONE hand)
    - Better H12 v8 pattern inference (continuous signal
      not chain-driven)
    - CASCADE/FOUNTAIN disambiguation on the late phase
    This is the highest-priority next step (H40).

## Cross-cutting insights from H40 + H41 (2026-08-28 ~14:50)

36. **H40 v2 sustained-occupancy detects 3-4x more hand-
    occupancy than H36 chain-driven state.** H36 reports
    HOLD state during chain-event gaps even when the
    juggler's hands ARE occupied. H40 v2 captures this
    continuous state (72.3% on identical, 98.1% on
    YouTube, vs H36's 23.7% and 25.8%).

37. **H40 v2 hand-occupancy does NOT cleanly discriminate
    FOUNTAIN from CASCADE.** On identical, FOUNTAIN 81.8%
    vs CASCADE 90.9% (similar). On YouTube, FOUNTAIN 98.2%
    vs CASCADE 96.9% (essentially equal). The "both-hands
    occupied" rate is more discriminating (YouTube
    FOUNTAIN 74.5% vs CASCADE 42.2%) but is dominated by
    sustained ball-wrist proximity, not actual holds.

38. **H40 sustained-occupancy detects "ball near hand", not
    "ball held by hand".** A ball passing through the 100 px
    hand reach for 3 frames is counted as hand-occupied.
    This is a fundamental limitation of 2D distance as a
    proxy for holding. The pose wrist position is at the
    wrist joint, not the center of the hand palm — at
    f=631-669 the held ball is 70-90 px from the wrist
    despite the hand being clearly occupied.

39. **H41 v2 (FOUNTAIN_3+ post-filter via H40 v2) has the
    same precision as H39 v2 (50% on rejects).** The H40
    continuous signal doesn't help distinguish FOUNTAIN
    from CASCADE because the FOUNTAIN_3+ over-classification
    problem is at the H12 v8 K=4 sliding window level,
    not at the hand-occupancy level. A reliable fix would
    need a fundamentally different approach (learned
    pattern classifier, multi-view 3D, or raw detector
    re-run).

40. **H40 is a useful diagnostic for chain quality and
    coverage measurement.** The 3-4x higher hand-occupancy
    detection rate than H36 makes H40 a more complete
    picture of the juggling activity. Future H42 could
    combine H40 with H36 to give a hybrid (L, R, A) state
    that uses chain events where available and H40
    sustained-occupancy otherwise.

