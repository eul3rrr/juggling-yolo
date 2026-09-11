# Local juggling-ball annotation (V1)

Development infrastructure for a later detection fine-tuning dataset. This tool mines existing CSVs, serves raw frames locally, and records human boxes. It does **not** run inference, train a model, change tracking/identity repair, generate synthetic images, or send images to external services.

## Ground-truth rules

- Annotate **every visible juggling ball in the full frame**, not only the mined focus ball. Unboxed visible balls would become training false negatives.
- There must be actual ball pixels in the target frame. Temporal neighbors can resolve whether a small patch belongs to a ball. They cannot justify a box on a completely hidden ball.
- For partial occlusion, annotate the estimated **full physical ball extent**, not just the visible crescent, when reasonably inferable. Mark uncertain extent as `uncertain`; do not invent false precision.
- A completed frame may have zero boxes. `no_visible_evidence` describes the focus ball only; other visible balls still need boxes.
- The sole training class is `0: juggling_ball`. All other labels below are metadata.

## Run

Use the existing project virtual environment (OpenCV is the only non-stdlib runtime dependency needed here). Commands are run from the repository root. LosslessCut keeps the original video: its CSV is read as segment provenance and no cut videos are generated.

```bash
.venv/bin/python scripts/annotate_juggling_balls.py mine \
  --video videos/identical_balls_trick_000_018.mp4 \
  --segments videos/identical_balls_trick_000_018.mp4.csv \
  --tracklets detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv \
  --detections detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32.csv \
  --links detections/detector_seg_comparison/identical_balls_trick_000_018_hand_associations.csv \
  --hands detections/identical_balls_trick_000_018_yolo26s-pose-hands.csv \
  --workspace datasets/juggling_ball_v1

.venv/bin/python scripts/annotate_juggling_balls.py serve \
  --workspace datasets/juggling_ball_v1 --host 127.0.0.1 --port 43128
```

Open `http://127.0.0.1:43128`. Quit the server with Ctrl-C; rerun the serve command to resume at the highest-priority pending item. An empty workspace shows a message rather than inventing items.

Repeat `mine` with another video's actual paths and the **same workspace**. Optional `--source-group session-or-juggler-name` preserves recording-level grouping for a future split. Without it, the video content hash is the source group. `--links`, `--hands`, and `--detections` are optional. A detections file should contain the existing **ball-only** predictions, not person/other-class detections. No canonical filename is hard-coded.

For a folder of collected sources, first inspect all matching pairs and their parsed ranges:

```bash
.venv/bin/python scripts/annotate_juggling_balls.py discover \
  --source-dir ~/Downloads/juggling_videos
```

Pairing is exact: `foo.mp4` uses `foo.mp4.csv`. Supported video extensions are mp4, mov, mkv, avi, and webm. CSV headers are case-insensitive `Start,End,Name`; labels are retained. Empty/undefined trailing end rows are ignored, malformed or non-positive ranges are rejected, and ranges are clamped to the measured video duration during `mine`.

Prepare all discovered sources with the existing detector and Norfair scripts, without creating cut videos:

```bash
.venv/bin/python scripts/annotate_juggling_balls.py prepare \
  --source-dir ~/Downloads/juggling_videos \
  --output-root datasets/juggling_ball_v1/preprocessing \
  --batch-size 32
```

Preparation uses `yolo26s.pt`, COCO class 32, confidence 0.15, image size 960, detector batch size 32, Norfair distance threshold 50, and hit-counter-max 15 by default. It runs bounded-memory YOLO batches only on selected frames and gives Norfair a fresh tracker for every selected segment. Outputs are `<safe-video-name>-<video-sha>/detections.csv`, `tracklets.csv`, and `manifest.json`. Batch size is recorded in the manifest. Matching manifests are reported as `already prepared`; changed inputs/configuration require `--force`, which replaces only the known generated preprocessing artifacts in that source directory and preserves unrelated files.

Preparation also runs selected-frame pose extraction and segment-local hand recovery. The small pose settings are explicit:

```bash
.venv/bin/python scripts/annotate_juggling_balls.py prepare \
  --source-dir ~/Downloads/juggling_videos \
  --output-root datasets/juggling_ball_v1/preprocessing \
  --pose-model yolo26s-pose.pt --pose-imgsz 640 --pose-conf 0.25 \
  --device auto --batch-size 32
```

`auto` resolves once to CUDA device `0` when CUDA is available, otherwise `cpu`; the resolved value is passed to detector and pose inference and recorded with the requested value. Pose inference opens the original source, seeks each selected half-open range, writes absolute source `frame` values, and never infers excluded frames. Its centered median buffer is bounded by the smoothing window and reset at every selected segment. The hand boundary, event, and FIFO state are also newly initialized per segment, so a link cannot cross a LosslessCut gap.

Each prepared directory contains these artifacts:

```text
detections.csv                 # existing detector schema; absolute frame
tracklets.csv                  # existing Norfair schema; absolute frame + observed
hands.csv                      # pose schema below; selected frames only
hand_assessments.csv           # existing hand_boundaries assessment schema
hand_events.csv                # existing hand_events logical-event schema
hand_associations.csv          # canonical accepted links schema below
unmatched_hand_events.csv      # FIFO diagnostic schema
hand_state_trace.csv           # FIFO transition trace schema
manifest.json                  # source/segment hashes, settings, artifact list
```

`hands.csv` preserves the historical `*_yolo26s-pose-hands.csv` columns and appends `segment_index` to disambiguate overlapping selected ranges:
`video,frame,time_seconds,person_index,person_confidence,body_scale_shoulder_px`, followed for each of `left_shoulder,right_shoulder,left_elbow,right_elbow,left_wrist,right_wrist` by `x,y,confidence,x_smooth,y_smooth`, then `segment_index`. Raw and smoothed coordinates are pixel coordinates; `frame` is zero-based and absolute in the source video. It has one row per selected-frame/person detection and may have no row when pose detects no person. Segment-local association filters on `segment_index`, so overlapping LosslessCut ranges cannot reuse another segment's independently smoothed pose row.

`hand_associations.csv` preserves the historical accepted-link header exactly:
`source_track_id,target_track_id,source_end_frame,target_start_frame,gap_frames,hold_seconds,association_type,resolved_hand,hand_ambiguous,source_eligible_hand_set,target_eligible_hand_set,source_preferred_hand,target_preferred_hand,source_ambiguous,target_ambiguous,match_rule`. Each row is one accepted same-segment FIFO `HAND` relation from the source track's observed END to the target track's observed START. IDs are the globally unique IDs already emitted by `tracklets.csv`; they are not chain IDs, candidate ranks, or screen-side labels. There are no rows for rejected/unmatched events. `hand_events.csv`, `unmatched_hand_events.csv`, and `hand_state_trace.csv` retain the diagnostic decisions.

The manifest invalidates the cache when source or LosslessCut bytes, segment ranges, detector settings, pose model/settings/device, hand-association version/configuration, the required artifact set, or any generated artifact hash/size changes. A local pose checkpoint is content-fingerprinted; non-local model references are recorded by reference. Without `--force`, a mismatch fails rather than deleting anything. `--force` replaces only the known generated preprocessing artifacts under the matching source directory; it never removes unrelated files, the annotation workspace, SQLite database, source video, or LosslessCut CSV. If a throwaway candidate annotation workspace must be discarded, stop the server, inspect the absolute path, and explicitly remove only that directory, for example `rm -rf -- datasets/juggling_ball_v1/candidate-smoke`; never point cleanup at `datasets/juggling_ball_v1` itself.

For one source, the equivalent explicit commands are:

```bash
.venv/bin/python scripts/detect_video.py \
  ~/Downloads/juggling_videos/foo.mp4 \
  --segments ~/Downloads/juggling_videos/foo.mp4.csv \
  --model yolo26s.pt --conf 0.15 --imgsz 960 --classes 32 --device auto --batch-size 32 \
  --no-output-video --output-csv datasets/juggling_ball_v1/preprocessing/foo/detections.csv

.venv/bin/python scripts/track_norfair.py \
  ~/Downloads/juggling_videos/foo.mp4 \
  datasets/juggling_ball_v1/preprocessing/foo/detections.csv \
  --segments ~/Downloads/juggling_videos/foo.mp4.csv \
  --distance-threshold 50 --hit-counter-max 15 \
  --no-output-video --output-csv datasets/juggling_ball_v1/preprocessing/foo/tracklets.csv
```

Then mine using the generated `tracklets.csv` and `detections.csv` paths. The detector/tracker CSVs retain absolute source frame numbers and timestamps, so they can be supplied directly to `mine`.

After preparation, mining remains a separate explicit command and does not run during `prepare`:

```bash
.venv/bin/python scripts/annotate_juggling_balls.py mine \
  --video ~/Downloads/juggling_videos/foo.mp4 \
  --segments ~/Downloads/juggling_videos/foo.mp4.csv \
  --tracklets datasets/juggling_ball_v1/preprocessing/foo-VIDEO_SHA/tracklets.csv \
  --detections datasets/juggling_ball_v1/preprocessing/foo-VIDEO_SHA/detections.csv \
  --hands datasets/juggling_ball_v1/preprocessing/foo-VIDEO_SHA/hands.csv \
  --links datasets/juggling_ball_v1/preprocessing/foo-VIDEO_SHA/hand_associations.csv \
  --workspace datasets/juggling_ball_v1
```

Source identity is SHA-256 of the video bytes. Stable item identity combines that identity and the zero-based source frame. Repeating identical mining inputs does not duplicate frames, replace labels, or resurrect deleted boxes. Input paths/hashes and metadata are pinned: if you change inputs for an already-mined video, use a new workspace rather than silently rewriting an annotated snapshot. Keep source videos at their recorded paths and unchanged while annotating/exporting.

Loopback is the default. For SSH use a tunnel, for example `ssh -N -L 43128:127.0.0.1:43128 user@host`. `--host` permits explicit private-network binding; it is never automatically exposed. There is no authentication: do not expose this server to an untrusted network.

## Mining and provenance

0. Only frames whose absolute source timestamp is inside a selected segment are eligible. A small 0.1-second margin suppresses artifacts at segment edges. Accepted links are used only when both observed endpoints belong to the same segment; no event, interpolation, ordinary control, or context frame crosses a segment boundary. Every item stores segment index/start/end/label and the CSV fingerprint.
1. Accepted linked transitions have first priority. The adapter consumes the current hand association CSV columns `source_track_id`, `target_track_id`, `source_end_frame`, `target_start_frame`, and `association_type`. All columns are preserved. Optional `accepted=false` rows are excluded. Ranked candidate/stitch proposal CSVs are rejected: rank 1 does not mean accepted.
2. Every observed track END and orphan START follows. The existing `review_track_events.py` loaders and event generator are reused unchanged. START/END refer to first/last **observed** rows, not predicted lifespan. An orphan has no other observed END in the preceding reviewer window (one second); this preserves reviewer semantics rather than inventing a new association rule.
3. Ordinary controls come from continuous observed portions, away from all START/END boundaries. Selection is deterministic and spaced by at least a quarter second. The target is 30% ordinary images, capped by available suitable frames; short or fragmented clips may provide less. Add longer ordinary source recordings rather than filling a quota with adjacent near-duplicates.

Boundary offsets are `[-15,-9,-6,-4,-2,-1,0,1,2,4,6,9,15] / 60` seconds, rounded uniquely at the source FPS and clamped to valid frames. Linked gaps of up to 0.2 seconds include every missing frame; longer gaps include near-boundary frames and quarter/midpoint samples. Both linked boundaries are sampled. A frame is stored once, with all overlapping reasons/events and signed distances to relevant boundaries.

Progress/category navigation uses exclusive priority groups (linked / unresolved / ordinary). The mining command also reports overlapping `linked_gap`, `track_end`, `orphan_start`, and `ordinary` reason counts; those are not expected to sum to the unique-image total.

## Annotation UI

- Full-frame SVG editor: drag to add; click to select; drag inside to move; drag corner handles to resize; delete unwanted boxes. Coordinates always remain in the original full frame.
- Context crop and raw temporal neighbors are annotation aids. Crops include focus, nearest wrist/arm/shoulder when pose exists, with generous margins. Without pose, a large frame-relative crop is used. Linked-gap interpolation guides only the subtle focus marker/crop, never boxes. Standalone boundaries use the observed endpoint as a hint, not a hidden-ball prediction.
- Click a temporal thumbnail to enlarge it. The target frame does **not** change. Context closes explicitly; there is no autoplay or EOF-driven advance.
- The first/highest-priority provenance entry identifies the focus event for a deduplicated item. Other overlapping event keys remain visible and exported. Select focus status and, when identifiable, a focus box. Ordinary-only frames use `not_applicable`.
- `Hide hints` removes all overlays (including preannotations and event guidance) for raw inspection; editing is disabled until hints are shown again.
- `Save draft` persists incomplete work as pending. `Save & Next` completes only after every retained box has a survey, event focus status is set, and the annotator explicitly confirms that all visible balls are boxed. `Skip` persists a skipped item, excluded from export. Navigation warns before discarding unsaved edits.
- Shortcuts outside form controls: N/Right next, P/Left previous, A add, Delete/Backspace delete, Enter complete and next, H hints, Escape cancel drawing/action. Form controls retain their normal keys. Controls are locked while a request is in flight.

### Per-ball survey

| Field | Values and meaning |
| --- | --- |
| Occluder | `none`, `hand`, `body`, `other_object`, `mixed`. Do not use `other_ball`; overlapping balls are annotated as separate ordinary boxes. |
| Occlusion | `none`, `slight`, `moderate`, `heavy`, describing meaningful non-ball coverage. |
| Visibility | `clear`: full/almost-full ball; `partial`: part visible; `tiny_fragment`: very little surface but real visible evidence. Independent of occluder, so body occlusion can be partial with no hand overlap. |
| Motion blur | `none`, `mild`, `strong`, by visual judgment. |
| Annotation confidence | `certain`, `uncertain`. |

`Ordinary clear ball` sets `occluder=none`, `occlusion=none`, `visibility=clear`, `motion_blur=none`, `annotation_confidence=certain`. Each final box remains class `juggling_ball`. Source detector confidence and original box are immutable audit data, not survey defaults or human truth.

## Persistence and export

SQLite lives at `<workspace>/annotations.sqlite3`:

- `sources`: stable source ID and JSON video metadata/group/input fingerprints.
- `items`: unique source/frame, priority, status, revision, and JSON provenance/crop/focus/notes.
- `boxes`: full-frame coordinates, one class, survey and immutable prediction relation in JSON.
- `predictions`: unchanged original detector boxes/confidences, even after deletion. Read/export marks whether each prediction was retained or deleted.
- `saves`: revision snapshots and timestamps, including previous boxes. Transactions, foreign keys, and revision checks prevent partial writes and stale-tab overwrites. Back up the workspace with the server stopped.

```bash
.venv/bin/python scripts/annotate_juggling_balls.py export-yolo \
  --workspace datasets/juggling_ball_v1 \
  --output datasets/juggling_ball_v1/export-001
```

The output must not already exist. Export takes a consistent completed-item snapshot, stages files, and publishes the finished directory. It contains:

```text
images/unassigned/<item-id>.jpg   # raw FULL frame, no baked hints
labels/unassigned/<item-id>.txt  # 0 xc yc width height, normalized
metadata.jsonl                   # image, source/frame/group, boxes/IDs/surveys,
                                 # detector audit, focus, crop and all provenance
unassigned.txt
data.yaml                        # sole class; deliberately no train/val split
```

All boxes from completed frames are included; pending and skipped frames are excluded. Zero-box images have empty label files. Crop images are **not exported as training samples**.

**Do not randomly split frames.** Before training, assign whole videos, recording sessions, jugglers, or source groups to train/validation. Adjacent frames from one recording in both splits would leak nearly identical examples. `data.yaml` deliberately remains unassigned rather than pretending this export is ready for training.

## Tests and smoke workspaces

```bash
.venv/bin/python -m pytest -q tests/test_annotation_*.py
.venv/bin/python -m pytest -q
node --check web/annotation/app.js
```

Generated datasets, SQLite databases, browser caches, and exported images are not versioned. Only code, tests, and this guide belong in Git. The development `datasets/annotation_smoke` workspace contains mechanical test edits explicitly marked **NOT HUMAN GROUND TRUTH**; never use its export for training. Browser smoke checks were performed locally without sending frames to a model/service.
