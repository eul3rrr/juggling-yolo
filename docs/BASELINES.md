# Historical detection and review workflow

These are the earlier YOLO26s baseline and manual-review commands, not the YOLO26l hand-repair path shown in the frozen demo. They remain here for reference; start with [the current README](../README.md) for the demo. Run these commands from the repository root.

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

Use `.venv/bin/python` for these commands. Run a script with `--help` for its complete argument list.
