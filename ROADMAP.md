# Roadmap

Ideas and unfinished directions. One entry per idea: what it is, why it might help,
and what already exists. Move an entry to "Tried and dropped" with the reason when
an experiment ends, so the conclusion is not lost with the branch.

## Next

- **Ground-truth benchmark.** Per-frame ball identity that does not depend on any
  tracker, so every pipeline can be scored against the same answer. Two sources:
  clips filmed with differently coloured balls (colour gives identity for free), and
  hand-corrected tracker output for identical-ball footage. A first test clip showed
  the filming needs more light and smooth, saturated balls.

## To try

- **Body segmentation for body occlusion.** Run a person-segmentation model on the
  juggler and use the body mask to know when and where a ball can be hidden behind
  the body, instead of treating every unexplained gap as a generic "hidden" link.
  The earlier segmentation experiment segmented the balls, not the body; this is a
  different use.
- **Vision model as stitch judge.** Show a vision model the frames around a tracklet
  end and the candidate successors and ask which is the same ball. A 20-event pilot
  exists (`scripts/vision_stitch_judge.py`) but none of its verdicts were checked
  against a human, so its accuracy is unknown.
- **Detector fine-tune for domain shift.** Teach the detector what a juggling ball
  looks like when clearly visible (small, blurred, non-sports-ball appearance), with
  frames from several videos. The annotation tool and training scripts exist.
- **Live UI revamp.** The live tracker predates the identity stage and does not use
  it. Worth rebuilding as the project demo once offline identity is solid.

## Tried and dropped

- **Ball instance segmentation as the detector** (Aug 2026). `yolo26l-seg` was no
  better than plain `yolo26l` for this pipeline; `yolo26l` became the detector. See
  `reports/detector_seg_comparison/REPORT.md`.
- **Fine-tune that labels partially hidden balls** (Sep 2026). Labelling balls mostly
  covered by fingers, hoping to recover barely visible ones, made the detector fire
  far too often: about 8 detections per frame against 2.5 on held-out footage, and
  twice the tracklets. The 0.95 mAP50 on its own validation set hid this because the
  validation labels followed the same rule.
