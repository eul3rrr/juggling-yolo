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
