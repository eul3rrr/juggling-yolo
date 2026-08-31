# Juggling Ball Trajectory Tracking

A research codebase for detecting juggling balls in video, building short tracklets, and reconstructing longer trajectories across missed detections and occlusions.

The project started as a YOLO detector comparison and now includes generic tracker baselines, Norfair center-point tracking, manual stitch review, trajectory-feature analysis, physics-informed association experiments, and diagnostic visualizations. It is an experimental pipeline rather than a production tracker.

## Current status

The main-branch experiments support these components of a precision-first,
offline association strategy:

- use raw detector centers for observed points;
- use constant-acceleration motion during local association;
- score wider tracklet gaps with a ballistic fit;
- calibrate acceptance gates per video and gap length;
- solve successor links globally instead of accepting each source greedily.

The ballistic wide-gap/global-assignment experiment removed assignment conflicts
and accepted no manually labeled wrong links on the two development clips. In a
separate motion-model experiment, constant-acceleration association reduced
fragmentation and exporting raw centers improved synthetic recovery. These pieces
have not yet been validated together in one end-to-end integration run. Recall
also remains limited around catches, throws, and long hand occlusions.

Detector forensics found that lower-confidence association and hand-state
modeling are more important next steps than simply changing the detector
backbone.

Detailed experiment results and negative findings are preserved in [`experiments/overnight/RESULTS_LOG.md`](experiments/overnight/RESULTS_LOG.md).

## Pipeline

1. `detect_video.py` runs frame-by-frame Ultralytics YOLO inference and exports pixel-coordinate detections.
2. `track_video.py` compares ByteTrack and BoT-SORT baselines.
3. `track_norfair.py` turns existing ball detections into local center-point tracklets.
4. `stitch_tracklets.py` ranks possible continuations without changing the original track IDs.
5. `review_stitches.py` creates looping review clips and records `correct`, `wrong`, or `unclear` labels.
6. `analyze_stitch_features.py` measures ballistic-fit and wrist-proximity features on reviewed hypotheses.
7. `reconstruct_stitched_video.py` renders a descriptive high-confidence reconstruction from reviewed outputs.

The scripts under `experiments/overnight/scripts/` contain the later physics, global-assignment, hand-event, motion-model, and detector-headroom investigations. They intentionally remain separate from the baseline pipeline.

## Repository layout

- `scripts/` — runnable baseline detection, tracking, review, analysis, and reconstruction tools
- `configs/` — ByteTrack and BoT-SORT configurations
- `tests/` — unit and CLI smoke tests
- `detections/` — reproducible CSV/JSON/Markdown research inputs and results
- `experiments/overnight/` — experiment code, reports, and compact result artifacts
- `videos/` — local input videos (ignored by Git)
- `outputs/` — generated videos and review clips (ignored except compact manifests)

Model weights, source videos, caches, and generated MP4 files are intentionally not versioned.

## Setup

Python 3.14 was used for the current environment. Create a virtual environment and install a PyTorch build appropriate for your machine. For the CUDA 13.0 setup used during development:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130
.venv/bin/python -m pip install -r requirements.txt
```

CPU-only and other CUDA installations should use the matching command from the [PyTorch installation guide](https://pytorch.org/get-started/locally/) before installing `requirements.txt`.

Place input clips in `videos/`. The examples below use:

- `videos/identical_balls_trick_000_018.mp4`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4`

## Quick start

### Detect sports balls

COCO class 32 is `sports ball`:

```bash
.venv/bin/python scripts/detect_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 \
  --classes 32 --device auto
```

`--device auto` selects GPU 0 when CUDA is available and otherwise uses CPU. Detection CSVs contain frame/time, class, confidence, bounding-box, center, width, and height values in original-video pixels.

### Compare generic trackers

```bash
.venv/bin/python scripts/track_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --classes 32 \
  --tracker configs/bytetrack.yaml --tracker-label bytetrack --device auto
```

Use `configs/botsort.yaml` or `configs/botsort_reid.yaml` for the other baselines. Their IDs are local tracklets, not guaranteed permanent ball identities.

### Build Norfair tracklets

```bash
.venv/bin/python scripts/track_norfair.py \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_yolo26s_classes-32.csv \
  --distance-threshold 50 --hit-counter-max 5
```

The output distinguishes observed detector matches from predicted Norfair states. Downstream experiments use observed points when fitting trajectories.

### Rank and review candidate stitches

```bash
.venv/bin/python scripts/stitch_tracklets.py \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5.csv \
  --max-gap-frames 10

.venv/bin/python scripts/review_stitches.py prepare \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5.csv \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5_stitches.csv

.venv/bin/python scripts/review_stitches.py review \
  detections/stitch_review_labels.csv
```

The review player loops the current clip until a decision is made. Controls are `c` (correct), `w` (wrong), `u` (unclear), `s` (skip), and `q` (quit). Existing labels are preserved when review assets are regenerated.

### Analyze reviewed hypotheses

Generate pose detections, then enrich the reviewed labels:

```bash
.venv/bin/python scripts/analyze_stitch_features.py pose \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s-pose.pt

.venv/bin/python scripts/analyze_stitch_features.py enrich \
  detections/stitch_review_labels.csv \
  --output-csv detections/stitch_review_features.csv \
  --summary-json detections/stitch_review_feature_summary.json
```

The trajectory model is `x=a+b*t`, `y=c+d*t+e*t²`. These features are descriptive and do not automatically alter tracklets or acceptance thresholds.

Every executable in `scripts/` also locates the project `.venv` when run directly. Use `--help` on any command for its complete argument list.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The test suite covers CSV contracts, observed/predicted semantics, stitch ranking, review-state behavior, feature analysis, tracker configuration, and direct CLI execution.

## Scope and limitations

- The repository currently targets offline analysis of short juggling clips.
- COCO sports-ball detections include false positives and often weaken near hands.
- Tracklet stitching proposes or renders associations; it does not establish physical ball identity as ground truth.
- The experiment reports include negative results intentionally so failed approaches are not repeated.
