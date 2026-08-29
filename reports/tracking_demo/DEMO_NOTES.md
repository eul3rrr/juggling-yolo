# Demo notes and caveats

Frozen research SHA: `ea17fb541a6998d0c4f0e63bd9cb4e38e40c19b5`.
Main/pre-overnight reference: `2ddf422` (E6c baseline lineage).
Demo branch is based exactly on the frozen SHA.

## Definitions

AUTO uses the frozen `h7v3pure` admitted edges: H1 v4d/H7v2 hand-aware reclassification plus H15v2 V-shape reclassification, with the H7 greedy cost-ordered one-to-one selector. It excludes the explicit H22 and H26 interventions.

RESEARCH-TUNED uses `h7v3plus3`: AUTO lineage plus H22's YouTube 16→21 veto/20→21 replacement and H26's two development-video-reviewed identical-video additions. It is coherent, but **DEV-TUNED / DEVELOPMENT-VIDEO INFORMED**.

H125 is shown as candidate proposals only. H125 v4 is a union/filter evaluation and does not re-enforce one successor/predecessor constraints; it is not a tracker.

T1/T2-style labels are logical graph chain IDs, not permanent physical ball IDs. The demo uses T<number> only and never calls them Ball A/B/C.

## What actually improved

### TRACKING TOPOLOGY IMPROVEMENT

The meaningful improvements are new source→target pairs in the coherent AUTO edge set compared with E6c, and fewer baseline links when a different successor is selected. The dashboard and event queue distinguish additions/removals from semantic relabeling.

### SEMANTIC / HAND-STATE IMPROVEMENT

Many H7v2/H15 changes preserve the exact source and target but reinterpret an E6c AIR/BALLISTIC edge as HAND_TRANSITION. That improves event provenance and makes the hidden interval understandable; it does not change correspondence.

### CONFIDENCE / QUALITY IMPROVEMENT

H10/H11 outputs are downstream annotations. `end_pose_conf` and `start_pose_conf` are omitted because source code fills them from tracklet/detector confidence, not wrist-pose confidence.

### DOWNSTREAM-ONLY IMPROVEMENT

Pattern labels are deliberately absent from the main screen. They were repeatedly revised and are not presented as unseen-data validation.

## What did not improve / remains unsolved

Physical identity through multi-ball hand occupancy remains unknown. A graph-connected chain can merge multiple physical balls; the demo marks this as ambiguity rather than drawing a fake continuous ball identity. Candidate-pair labels also allow multiple alternatives to be “correct”, so the 113-pair recall is not one-to-one physical trajectory recall.

The H125 fit/cost quantities are internal scores, not calibrated physical uncertainty. AIR connectors are minimal model approximations because a unique saved intermediate parabola is not present for every edge. The two source videos are local-only assets and are symlinked into `assets/`; the symlink target is documented in README_DEMO.md.

The first clip contains normal/slow-motion/normal playback regime changes. This demo does not interpret those regime changes as tracker quality changes; all panels use the exact same source frame.

## Review scope

The curated queue intentionally mixes new bridges, semantic changes, AIR links, H125 alternatives, and failures from both clips. The failure gallery is not another research queue. No H126/H127 or later experiment is started by this demo.
