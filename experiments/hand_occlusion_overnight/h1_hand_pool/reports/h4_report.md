# H4 — Face-Masked H3 (Detector Confusion Workaround)

**Date:** 2026-08-28 ~05:50 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** H4 attempted. The face-mask approach does NOT solve
the YouTube H3 false positive. The detector confusion is on a
stationary object ABOVE the wrist, not a face feature.

## 1. Hypothesis

The H3 YouTube false positive (10→12, stuck on face/head) is
caused by YOLO confusing face/head features with sports balls
when the hand is near the face. A simple geometric mask that
excludes detections ABOVE the wrist when the hand is near face
level should eliminate the false positive without affecting the
identical-video clusters (where the hand is below face level
during held phases).

## 2. Implementation

`h1_hand_pool/data/h4_face_masked_summary.json` (computed inline).

**Criterion (declared first):**
- Same as H3 v3 (stationary cluster of ≥3 low-conf dets in
  30px radius over ≥5 frames).
- ADDITIONALLY: for each candidate detection, if the wrist y
  is within 80 px of the *minimum* wrist y over a ±15 frame
  window (= hand is near face level), exclude detections
  where the detection y is more than 20 px ABOVE the wrist y.

The 20-px "above wrist" threshold is a guess: face features
should be at head level (above the wrist when the hand is near
the face), but a held ball is at the wrist level (not above).

## 3. Quantitative result

| Stem | v4d n_links | n_H3_clusters (no mask) | n_H4_clusters (face-mask) |
|---|---|---|---|
| identical | 10 | 6 | 6 (same) |
| youtube  |  1 | 1 | 1 (still 1) |

**The face-mask does NOT remove the YouTube cluster.** The
surviving 10→12 cluster at f=248-253 is at x=611-618, y=205-207
— about 50-80 px to the right of the right wrist (x=553-563,
y=418-449) and ~200 px ABOVE the wrist.

The vision_analyze on the face-masked 10→12 contact sheet
confirms the cluster is in the upper-left/right of the frame,
NOT at the hand. It's a stuck detection on a stationary
high-up feature (possibly a sign, tree, or wall feature), not
on the face.

## 4. Negative findings

- **The H3 YouTube false positive is NOT a face-feature
  confusion.** The detector is latching onto a stationary
  high-up object in the scene, not the juggler's face. A
  face mask doesn't help.
- **The face-mask DOES preserve all 6 identical-video H3
  clusters.** The 11→14 link's second cluster (at f=125-126,
  133, the throw-frame cluster) was reduced from 2 clusters
  to 1 because the throw-frame detection was at the wrist
  level (not above), so it survived. The held-phase cluster
  at f=116-121 is preserved.
- **A simple geometric mask cannot solve the detector
  confusion problem.** The YOLO model can latch onto ANY
  stationary feature, not just faces. A real fix would
  require either (a) a more discriminating detector
  (specifically trained to distinguish balls from non-balls),
  (b) a face detector + body detector to mask out
  person-region false positives, or (c) a learned "ball-ness"
  classifier on the candidate regions.

## 5. Verdict

**FAIL.** H4 face-mask does not solve the H3 YouTube false
positive. The detector confusion is on a stationary high-up
object, not the face. The hypothesis was wrong.

This is a useful negative result: it tells us that the
detector confusion is not easily fixable with simple
geometric masks. Future work would require either a better
detector or a learned classifier.

## 6. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h4_face_masked_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h4_face_masked_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h4/*.png` (7 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h4_report.md` (this report)
