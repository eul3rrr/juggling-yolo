# Local juggling-ball annotation (V1)

Development infrastructure for a later detection fine-tuning dataset. This tool mines existing CSVs, serves raw frames locally, and records human boxes. It does **not** run inference, train a model, change tracking/identity repair, generate synthetic images, or send images to external services.

## Ground-truth rules

- Annotate **every visible juggling ball in the full frame**, not only the mined focus ball. Unboxed visible balls would become training false negatives.
- There must be actual ball pixels in the target frame. Temporal neighbors can resolve whether a small patch belongs to a ball. They cannot justify a box on a completely hidden ball.
- For partial occlusion, annotate the estimated **full physical ball extent**, not just the visible crescent, when reasonably inferable. Mark uncertain extent as `uncertain`; do not invent false precision.
- A completed frame may have zero boxes. `no_visible_evidence` describes the focus ball only; other visible balls still need boxes.
- The sole training class is `0: juggling_ball`. All other labels below are metadata.

## Run

Use the existing project virtual environment (OpenCV is the only non-stdlib runtime dependency needed here). Commands are run from the repository root.

```bash
.venv/bin/python scripts/annotate_juggling_balls.py mine \
  --video videos/identical_balls_trick_000_018.mp4 \
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

Source identity is SHA-256 of the video bytes. Stable item identity combines that identity and the zero-based source frame. Repeating identical mining inputs does not duplicate frames, replace labels, or resurrect deleted boxes. Input paths/hashes and metadata are pinned: if you change inputs for an already-mined video, use a new workspace rather than silently rewriting an annotated snapshot. Keep source videos at their recorded paths and unchanged while annotating/exporting.

Loopback is the default. For SSH use a tunnel, for example `ssh -N -L 43128:127.0.0.1:43128 user@host`. `--host` permits explicit private-network binding; it is never automatically exposed. There is no authentication: do not expose this server to an untrusted network.

## Mining and provenance

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
| Hand overlap | `none`: no visible hand pixels overlap the physical silhouette; `slight`: small overlap, most ball visible; `moderate`: substantial overlap but clearly identifiable; `heavy`: mostly hand-covered with some genuine ball pixels remaining. This measures overlap, **not proximity**. |
| Visibility | `clear`: full/almost-full ball; `partial`: part visible; `tiny_fragment`: very little surface but real visible evidence. Independent of occluder, so body occlusion can be partial with no hand overlap. |
| Motion blur | `none`, `mild`, `strong`, by visual judgment. |
| Annotation confidence | `certain`, `uncertain`. |

`Ordinary clear ball` sets none / clear / none / certain. Each final box remains class `juggling_ball`. Source detector confidence and original box are immutable audit data, not survey defaults or human truth.

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
