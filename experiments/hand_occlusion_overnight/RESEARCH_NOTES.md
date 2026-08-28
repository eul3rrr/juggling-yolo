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

### Topic: min-cost flow / factor-graph stitching

- **Internal reference:** E6c on main.
- **Applied:** H2 combines E6c mid-air edges with H1 v4d
  hand-links using a union-find. This is much simpler than
  min-cost flow but achieves the same goal: produce a
  single chain representation. Min-cost flow could improve
  H2 by handling the tracklet-3 conflict optimally (instead
  of recording it).

### Topic: object permanence / handoff tracking

- **Internal reference:** None directly.
- **Next:** A v5 hand-pool could explicitly model "object
  permanence" — once a ball is held in the hand, the model
  maintains a belief that the ball still exists even when
  no detection is present. The current v4d model is
  *implicitly* object-permanent (it creates a token on
  entry and the token persists for 60 frames), but a v5
  could make this explicit and use it to fill detector
  dropouts.

---

## Cross-cutting insights from this episode (2026-08-28 ~04:00-05:10)

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
