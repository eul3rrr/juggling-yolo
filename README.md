# Juggling YOLO Detection Experiment

This isolated experiment evaluates a pretrained Ultralytics YOLO26 COCO model on
juggling videos. It includes frame-local detection and generic tracker comparisons;
there is no custom association, physics, HSV filtering, hand events, training, or
fine-tuning.

## Layout

- `videos/`: short input videos
- `outputs/`: annotated videos with boxes, class names, and confidence scores
- `detections/`: one pixel-coordinate CSV per run
- `scripts/detect_video.py`: streaming Python inference script
- `scripts/track_video.py`: streaming generic tracking comparison script
- `scripts/track_norfair.py`: Norfair center-point tracklet baseline using existing CSV detections
- `configs/`: ByteTrack and BoT-SORT tracker configurations
- `.venv/`: isolated Python environment

## Environment

The environment was created with Python 3.14 and CUDA-enabled PyTorch for the
machine's NVIDIA GPU. Recreate it with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130
.venv/bin/python -m pip install ultralytics==8.4.123
```

## Run unfiltered COCO detection

This reveals which COCO classes YOLO assigns to juggling balls and other objects:

```bash
.venv/bin/python scripts/detect_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --device auto
```

The executable script also finds and uses the project's `.venv` automatically,
so from the `scripts/` directory the equivalent form is:

```bash
./detect_video.py ../videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --device auto
```

## Run sports-ball detection

COCO class 32 is `sports ball`:

```bash
.venv/bin/python scripts/detect_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 \
  --classes 32 --device auto
```

`--device auto` selects GPU 0 when CUDA is available and otherwise uses CPU.
Every frame is processed with `vid_stride=1`, and Ultralytics results are consumed
with `stream=True` to avoid retaining the complete video in memory.

CSV columns are: `video`, `frame`, `time_seconds`, `class_id`, `class_name`,
`confidence`, `x1`, `y1`, `x2`, `y2`, `center_x`, `center_y`, `width`, and
`height`. Bounding-box values are pixel coordinates in the original video.

## Compare trackers

Run the same sports-ball input with each installed-default tracker configuration:

```bash
.venv/bin/python scripts/track_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --classes 32 \
  --tracker configs/bytetrack.yaml --tracker-label bytetrack --device auto
```

```bash
.venv/bin/python scripts/track_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --classes 32 \
  --tracker configs/botsort.yaml --tracker-label botsort --device auto
```

```bash
.venv/bin/python scripts/track_video.py \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --classes 32 \
  --tracker configs/botsort_reid.yaml --tracker-label botsort-reid --device auto
```

The executable script also finds the project's `.venv` when run directly. Tracker
IDs are tracklets: they are useful for comparing tracker behavior, but are not
guaranteed permanent identities for a particular ball through occlusions or ID
switches. Each run reports ReID status, device, frame count, tracked row count,
unique IDs, and output paths. Tracking CSV columns include `tracker` and `track_id`.

## Norfair center-point baseline

Run Norfair on an existing sports-ball YOLO detection CSV without invoking YOLO:

```bash
.venv/bin/python scripts/track_norfair.py \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_yolo26s_classes-32.csv \
  --distance-threshold 50 --hit-counter-max 15
```

The script also re-executes with the project's `.venv` when run directly. It uses
`Tracker(distance_function="euclidean", distance_threshold=50,
hit_counter_max=15)` by default. Both parameters are exposed as CLI options so
small conservative sweeps can be run without changing tracking logic. The script
writes an annotated MP4 under `outputs/` plus a six-column CSV under `detections/`.
CSV rows contain current initialized Norfair estimates, including predicted
estimates on frames without a detection; `confidence` is the last associated YOLO
confidence. These IDs are local tracklets, not permanent identities, and may
change after occlusions or ambiguous crossings.

## Stitch Norfair tracklets

Rank possible continuations from an existing Norfair CSV without rerunning tracking:

```bash
.venv/bin/python scripts/stitch_tracklets.py \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5.csv \
  --max-gap-frames 10
```

The command writes a ranked candidate CSV under `detections/` and an annotated MP4
under `outputs/` by default. The baseline uses only the old tracklet's final
two center points, frame gap, and predicted-position error. It does not merge or
change tracklet IDs. The annotated MP4 is a side-by-side comparison: the left
`ORIGINAL NORFAIR TRACKLETS` panel shows only the original thin colored trails and
active ID labels, while the right `STITCH VIEW` panel adds rank-1 proposed bridges.
Tracklets disappear 15 frames after their final CSV point. Bridges are thick
yellow/orange lines with endpoint markers and labels; their moving markers are
hypothetical interpolations during missing frames, clamped at the candidate
endpoint briefly afterward, and never observed tracklet points.
