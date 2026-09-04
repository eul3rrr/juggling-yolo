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
- `scripts/stitch_tracklets.py`: rank constant-velocity matches between Norfair tracklets
- `scripts/review_stitches.py`: manual review of proposed stitch candidates
- `scripts/analyze_stitch_features.py`: descriptive feature analysis for reviewed stitches
- `scripts/segment_video.py`: yolo26l-seg instance segmentation with mask/bbox/centroid export
- `scripts/compare_arms.py`: detection / Norfair / stitch / mask-diagnostics comparison
- `scripts/build_side_by_side.py`: synchronized side-by-side comparison MP4s
- `scripts/build_contact_sheets.py`: PNG contact sheets for seg visual review
- `scripts/measure_runtime.py`: model-only inference timing
- `scripts/run_arm_triple.sh`: sequential runner for the three perception arms
- `configs/`: ByteTrack and BoT-SORT tracker configurations
- `reports/`: per-experiment reports and structured summaries
- `.venv/`: isolated Python environment

## Detector + segmentation capacity comparison

Three arms are compared on the same two clips with the same downstream
Norfair + stitch settings (distance_threshold=50, hit_counter_max=5,
max_gap_frames=10):

  A. yolo26s.pt — sports-ball detection, tracking point = bbox center
  B. yolo26l.pt — sports-ball detection, tracking point = bbox center
  C. yolo26l-seg.pt — instance segmentation, tracking point = instance
     bbox center (mask centroid is computed and saved but is NOT the
     tracking point)

The full report is in
`reports/detector_seg_comparison/REPORT.md`. Headline finding: promote
`yolo26l` to the next core perception baseline; the segmentation model
is not better than the plain large detector for this pipeline.

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

## Review proposed stitches

Prepare one short review clip per row in a stitch candidate CSV:

```bash
.venv/bin/python scripts/review_stitches.py prepare \
  videos/identical_balls_trick_000_018.mp4 \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5.csv \
  detections/identical_balls_trick_000_018_norfair_dt50_hc5_stitches.csv
```

Clips are written under `outputs/stitch_review/<video-stem>` and labels under
`detections/stitch_review_labels.csv` by default. Preparing again preserves
existing labels and does not duplicate candidates. Review unlabeled clips with
`c` (correct), `w` (wrong), `u` (unclear), `s` (skip), or `q` (quit):
each clip repeats from the beginning until you choose one of those keys.
The labels CSV stores the full values `correct`, `wrong`, or `unclear`.
Manifest and label paths are stored relative to the repository when generated
inside it.

## Analyze reviewed stitches

The analysis layer can fit a free projectile-like curve to the reviewed source
and candidate fragments and measure proximity to pretrained pose wrists. It does
not modify Norfair, candidate generation, or tracklet IDs. First run the pose
model on each reviewed source video:

```bash
.venv/bin/python scripts/analyze_stitch_features.py pose \
  videos/identical_balls_trick_000_018.mp4 \
  --model yolo26s-pose.pt

.venv/bin/python scripts/analyze_stitch_features.py pose \
  videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 \
  --model yolo26s-pose.pt
```

Then enrich the existing manually reviewed labels:

```bash
.venv/bin/python scripts/analyze_stitch_features.py enrich \
  detections/stitch_review_labels.csv \
  --output-csv detections/stitch_review_features.csv \
  --summary-json detections/stitch_review_feature_summary.json
```

The trajectory fit is `x=a+b*t`, `y=c+d*t+e*t^2` with pixel RMSE over the
last/first ten tracklet points. Wrist distances use only wrist keypoints at or
above the configured confidence and are left unavailable otherwise. These
features are descriptive only; they are not used as acceptance thresholds.
The `pose` command also writes a local annotated overlay video under
`outputs/pose_overlay/` by default. It shows Ultralytics person boxes, confidence
labels, and the full pose skeleton/keypoints. Override the location with
`--output-video`; these MP4s remain ignored by Git.

```bash
.venv/bin/python scripts/review_stitches.py review \
  detections/stitch_review_labels.csv
```

Use `--include-labeled` to revisit completed rows, `--start-index` to begin at
an item, or `--only-video` to filter the combined labels file.

## Review track-lifecycle events (browser-based)

The capacity comparison revealed that even yolo26l on the clean studio clip
still has ~14 Norfair track IDs. Before re-tuning stitching, this reviewer
exposes every track end (and every orphan start that the current stitcher
misses) for manual classification. It is a diagnostic tool only — it does
not modify the detector, Norfair, or stitcher.

Events are derived from the **observed** frame of each track (the
`observed == 1` rows in the Norfair CSV); trailing prediction-only rows
are ignored.

There are two review event kinds:

- `end` — one per track's last observed frame
- `orphan_start` — a track whose first observed frame has no predecessor
  ending within the normal 1.0-second END review window. The reviewer then
  looks backward 4.5 seconds (configurable with `--orphan-lookback`) and
  presents earlier ended tracks as numbered possible predecessors. This is
  a human-review window, not a stitch gate.

Rank-1 stitch information remains visible in END events. Redundant separate
`existing_stitch` events are no longer added when the END event already
covers the same break, candidate, and frames.

### One command, then open the printed URL on your laptop

```bash
./.venv/bin/python scripts/review_track_events.py serve \
  --video videos/identical_balls_trick_000_018.mp4 \
  --tracklets detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv \
  --detections detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32.csv \
  --stitches detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5_stitches.csv
```

The tool prepares the manifest + H.264 review clips if they don't exist
yet, then starts a small local HTTP server.

The terminal prints something like:

```
Reviewer running (19 events).

Open on your laptop:
  http://100.x.y.z:43127
```

If Tailscale is not detected it binds to localhost only and prints an
SSH-tunnel command instead. The server tries ports 43127, 43128, ...
until one is free and prints the actual selected port.

### Keyboard controls

The reviewer is an explicit three-mode state machine: `viewing`,
`choosing_hand`, `choosing_continuation`. Each mode only responds to
its keys; other keys are ignored without side effects.

#### Viewing mode

| Key | Action |
|-----|--------|
| space | pause / play |
| r | restart current clip (keeps selected playback speed) |
| ← / → | seek -1 s / +1 s |
| - / = | slower / faster playback (0.25x / 0.5x / 0.75x / 1.0x / 1.5x / 2.0x) |
| h | HAND-MEDIATED BREAK → enter `choosing_hand` |
| a | AIRBORNE BREAK → enter `choosing_continuation` |
| n | NORFAIR ASSOCIATION FAILURE → enter `choosing_continuation` |
| x | ID SWITCH / WRONG MERGE → enter `choosing_continuation` |
| e | TRUE END (save immediately, no continuation) |
| f | FALSE-POSITIVE TRACK (save immediately, no continuation) |
| u | UNCLEAR / AMBIGUOUS (save immediately) |
| s | SKIP for now (no save, advance) |
| ] | next event |
| p | previous event |
| q | quit safely (server stops) |
| Esc | (no effect in viewing mode) |

#### `choosing_hand` mode (after `h`)

| Key | Action |
|-----|--------|
| l | hand = left → enter `choosing_continuation` |
| r | hand = right → enter `choosing_continuation` |
| u | hand = unknown → enter `choosing_continuation` |
| Esc | cancel pending, return to viewing |
| anything else | ignored (does NOT save) |

`r` selects right hand here; video restart is suppressed.

#### `choosing_continuation` mode (after `a` / `n` / `x`, or after the
hand is set when starting with `h`)

| Key | Action |
|-----|--------|
| 1..9 | pick numbered nearby candidate (saves immediately and advances) |
| 0 | no identifiable continuation (saves and advances) |
| ? | ambiguous continuation (saves and advances) |
| Esc | cancel pending, return to viewing |
| anything else | ignored |

Pressing `1` saves the actual track id of candidate 1 — the displayed
number is the candidate's index, not its track id. The visible
candidate map (`1 → ID X @ frame Y`) is shown in the pending panel so
you never have to memorize the mapping.

Mouse buttons (next / prev / quit) exist as accessibility fallbacks;
the primary workflow is keyboard-only.

### Saved labels

The labels CSV has a `continuation_status` field that captures whether
the human selected a continuation, declined to choose, marked the
choice ambiguous, or marked it not applicable. Allowed values:

- `selected` — `selected_continuation_track_id` is filled with the real
  track id
- `none` — human pressed `0` or left the field empty
- `ambiguous` — human pressed `?`
- `not_applicable` — event type was `e` (true end) or `f`

## Web live tracker with CUDA

Start the browser UI from the project root:

```bash
./.venv/bin/python scripts/live_app.py --device auto --model yolo26l.pt
```

Choose `Webcam`, camera `0`, and `auto (CUDA if available)` in the UI. Use
`CUDA 0` to require the first NVIDIA GPU, or `CPU` for a deliberate fallback.
The live diagnostics panel reports the resolved device, model, CUDA status,
processing FPS, and any inference error. The server also exposes the same probe
at `http://127.0.0.1:8000/api/health`.

The model checkpoint must exist in the repository (the default `yolo26l.pt` is
included). Verify the environment before starting:

```bash
nvidia-smi
./.venv/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
  (false-positive track), no continuation applies

The server validates that any `selected` track id is actually present in
that event's nearby-candidate list before writing the CSV.

### Output

- Review clips (H.264 / yuv420p, browser-compatible): `outputs/track_event_review/`
- Per-event CSV manifest: `outputs/track_event_review/manifest.csv`
- Labels (one row per event, saved after every review): `detections/track_event_review_labels.csv`

The labels CSV columns:

| Column | Meaning |
|--------|---------|
| `event_key` | stable structural identity (`end:<id>:<frame>` or `orphan_start:<id>:<frame>`) |
| `event_type` | one of `h`, `a`, `n`, `x`, `e`, `f`, `u`, or empty |
| `hand` | for `h`: `left` / `right` / `unknown`; empty otherwise |
| `relation_direction` | `successor` for END events; `predecessor` for ORPHAN START events |
| `continuation_status` | `selected` / `none` / `ambiguous` / `not_applicable` |
| `selected_related_track_id` | actual selected successor or predecessor ID |
| `selected_related_frame` | first-observed successor frame or last-observed predecessor frame |
| `selected_continuation_track_id` | the actual track id (when status is `selected`) |
| `selected_continuation_start_frame` | the manifest's first observed frame for that track |
| `notes` | free-form notes from the textarea |

Re-running the same `serve` command reuses the existing manifest + clips
and resumes from the first unsaved event.

## Juggling Tracker Live UI V1

Install the small web-app dependency set into the existing environment with
`./.venv/bin/python -m pip install -r requirements-live.txt`, then run:

```bash
./.venv/bin/python scripts/live_app.py --video videos/identical_balls_trick_000_018.mp4
```

Open the printed localhost URL. The controls support prerecorded replay,
restart/pause/stop, webcam index selection, Clean/Research/Raw overlay
presets, and per-overlay switches. Webcam capture is owned by OpenCV (no
browser camera permission); it requests 1280x720 at 60 FPS, but the actual
resolution and observed FPS are reported because hardware may differ.
Webcam inference uses the selected local checkpoint (default `yolo26l.pt`)
to reduce live latency and passes the selected device explicitly to Ultralytics.

HID is the current hand-system display identity, not a final physical-ball
identity. Live boundary decisions are provisional while delayed track-end
information arrives; END uses the final observed point, not the later
discovery frame. Proximity zones use the existing hand classifier's
normalized/raw fallback thresholds. Dashed hand bridges are identity
annotations, not physical trajectories. Body-occlusion and airborne
stitching are deliberately not implemented in V1.

Recorded sessions are stored under `outputs/live_sessions/YYYYMMDD_HHMMSS/`
with the unannotated `source.mp4` and `live_state.jsonl` when recording is
enabled. The V1 exporter is intentionally extensible; additional canonical
CSV writers can be added without changing the WebSocket protocol.
