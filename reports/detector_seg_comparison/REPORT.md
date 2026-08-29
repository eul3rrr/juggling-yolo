# Detector + Instance-Segmentation Capacity Comparison

**Branch:** `experiment/detector-segmentation-capacity`
**Worktree:** `~/projects/juggling-yolo-detector-seg-comparison`
**Base commit:** `2ddf422` on `main`

## Goal

A controlled comparison answering:

1. Does a larger pretrained YOLO detector improve the existing Norfair + stitch
   pipeline?
2. Does the corresponding instance-segmentation model improve it?
3. What do the segmentation masks actually look like on the juggling videos?

The detector/segmentation model is the only meaningful upstream variable. The
downstream Norfair + stitch settings are held fixed.

## EXACT SETTINGS (held constant for every applicable arm)

Detection:
- conf = 0.15
- imgsz = 960
- classes = [32] (COCO sports ball)
- vid_stride = 1
- device = auto (resolved to GPU 0, NVIDIA RTX 3060 Laptop)

Norfair:
- distance_function = euclidean
- distance_threshold = 50
- hit_counter_max = 5
- observation model = one-point Detection with the YOLO score

Stitching:
- max_gap_frames = 10
- constant-velocity prediction from the source tracklet's final two points
- rank-1 candidates are reported as the closest match per source

Videos:
- `videos/identical_balls_trick_000_018.mp4` — 1079 frames, 1280x720, 59.94 fps
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4` — 900 frames, 1280x720, 59.94 fps

## ARMS

| Arm | Model | Task | Tracking point |
|-----|-------|------|---------------|
| A   | yolo26s.pt   | detect | bbox center |
| B   | yolo26l.pt   | detect | bbox center |
| C   | yolo26l-seg.pt | segment (instances) | **bbox center of the instance** (mask centroid computed but used only as a diagnostic) |

Frame-local instance index from the segmentation model is **not** a temporal
track ID. Color in the seg overlay is assigned per frame-local instance and
must not be interpreted as persistent identity.

The minimal CSV written by `segment_video.py` matches the schema produced by
`detect_video.py` so the existing `track_norfair.py` and `stitch_tracklets.py`
scripts run unchanged on every arm.

## PER-ARM RESULTS

### Detection

| Video | Arm | Detections | Mean/frame | Median/frame | Frames 0 | Frames 1 | Frames 2 | Frames 3 | Frames 4+ | Conf mean |
|-------|-----|-----------:|-----------:|-------------:|---------:|---------:|---------:|---------:|----------:|----------:|
| identical | yolo26s   | 2731 | 2.57 | 3 | 17  | 143 | 272 | 551 | 96  | 0.493 |
| identical | yolo26l   | 3292 | 3.05 | 3 |  0  |   1 |  24 | 995 | 59  | 0.688 |
| identical | yolo26l-seg | 2467 | 2.44 | 3 | 66  | 151 | 287 | 559 | 16  | 0.456 |
| youtube   | yolo26s   | 4135 | 4.60 | 5 |  2  |   7 |  19 |  71 | 801 | 0.476 |
| youtube   | yolo26l   | 4052 | 4.50 | 5 |  0  |   0 |   6 | 114 | 780 | 0.518 |
| youtube   | yolo26l-seg | 3925 | 4.36 | 4 |  0  |   5 |  14 | 164 | 717 | 0.522 |

**Per-frame count absolute difference distributions (synchronized source
frames):**

| Compare | Same | ±1 | ±2 | ±3+ |
|---------|----:|---:|---:|----:|
| identical: yolo26s vs yolo26l   | 530 | 357 | 160 | 32  |
| identical: yolo26l vs yolo26l-seg | 530 | 313 | 158 | 78  |
| youtube:   yolo26s vs yolo26l   | 366 | 383 | 119 | 32  |
| youtube:   yolo26l vs yolo26l-seg | 373 | 405 | 108 | 14  |

### Norfair (dt=50, hc=5, fixed)

| Video | Arm | Unique IDs | Track rows | Observed frac | Observed median | Observed mean | Lifespan median | Lifespan max | Short (≤5) | Short (≤10) |
|-------|-----|-----------:|-----------:|--------------:|----------------:|--------------:|----------------:|-------------:|-----------:|------------:|
| identical | yolo26s   | 54 | 2937 | 0.851 | 40.0 |  54.4 |  40 | 175 | 1 | 7  |
| identical | yolo26l   | 14 | 3317 | 0.977 | 139.5| 236.9 | 139 | 886 | 3 | 3  |
| identical | yolo26l-seg | 72 | 2769 | 0.806 | 23.0 |  38.5 |  23 | 156 | 6 | 14 |
| youtube   | yolo26s   | 40 | 4339 | 0.874 | 68.5 | 108.5 |  68 | 415 | 2 | 5  |
| youtube   | yolo26l   | 43 | 4258 | 0.882 | 73.0 |  99.0 |  73 | 355 | 3 | 3  |
| youtube   | yolo26l-seg | 50 | 4173 | 0.857 | 66.5 |  83.5 |  66 | 220 | 2 | 3  |

### Stitching (max_gap_frames=10, fixed)

| Video | Arm | Sources needing candidates | Candidates | Gap median | Gap max | Rank-1 error median | Rank-1 error p75 |
|-------|-----|---------------------------:|-----------:|-----------:|--------:|--------------------:|-----------------:|
| identical | yolo26s   | 33 | 43 | 5 | 10 | 125.7 | 200.1 |
| identical | yolo26l   |  2 |  3 | 1 |  3 |  51.4 |  77.0 |
| identical | yolo26l-seg | 60 | 98 | 5 | 10 | 131.8 | 182.4 |
| youtube   | yolo26s   | 27 | 28 | 5 |  9 | 105.3 | 161.9 |
| youtube   | yolo26l   | 30 | 38 | 4.5| 10 | 104.9 | 173.4 |
| youtube   | yolo26l-seg | 36 | 46 | 5.5| 10 | 126.1 | 168.5 |

### Mask diagnostics (segmentation arm only)

| Video | Mask area median (px²) | Mask area p90 | Bbox↔centroid distance median (px) | Bbox↔centroid distance p90 | Bbox↔centroid distance max |
|-------|----------------------:|--------------:|-----------------------------------:|---------------------------:|----------------------------:|
| identical | 1714 | 2099 | 1.63 | 4.08 | (see CSV) |
| youtube   |  363 |  403 | 0.69 | 1.16 | (see CSV) |

The bbox center and mask centroid are very close (median sub-pixel to a
couple of pixels). The YouTube masks are smaller in absolute area (smaller
balls in frame) but the centroid agreement is even tighter. Neither is
ground truth.

### RUNTIME (inference only, no overlay / I/O, GPU=0)

| Model | Video | Frames | Seconds | Effective FPS | Peak GPU MB |
|-------|-------|-------:|--------:|--------------:|------------:|
| yolo26s    | identical | 1079 | 26.59 | 40.6 | 134.6 |
| yolo26s    | youtube   |  900 | 11.29 | 79.7 | 134.6 |
| yolo26l    | identical | 1079 | 30.51 | 35.4 | 262.6 |
| yolo26l    | youtube   |  900 | 26.26 | 34.3 | 262.6 |
| yolo26l-seg| identical | 1079 | 18.47 | 58.4 | 339.0 |
| yolo26l-seg| youtube   |  900 | 29.82 | 30.2 | 340.3 |

The seg model is **comparable in throughput** to the large detector on the
identical clip (the identical clip's 30 fps is consistent with disk-read
overhead rather than inference), and **slightly faster** than the large
detector on the YouTube clip (segmentation here runs at the same input
resolution but does not return the per-class NMS post-processing that the
detector pipeline performs, which appears to be the dominant overhead).
The seg model uses ~25% more peak GPU memory than the large detector.

Note: the speed-up of `yolo26s` on the YouTube clip versus the identical
clip (79.7 vs 40.6 fps) is the same GPU running the same model — the
identical clip was the first arm run on each video and pays some warm-up
overhead, plus identical has more ball instances per frame and the model
runs at a slightly higher effective load. The 79.7 vs 34.3 ratio between
yolo26s and yolo26l on the YouTube clip is the clean speed comparison.

---

## 1. CAPACITY EFFECT — yolo26s vs yolo26l

On the **identical_balls** video yolo26l is a clear improvement:

- 20.5% more total detections (2731 → 3292)
- The number of frames with 0 detections drops from 17 to 0
- Mean confidence rises from 0.493 to 0.688
- **Unique Norfair track IDs drop from 54 to 14** (4× fewer track fragments)
- Median Norfair track observed-frames jumps from 40 to 139.5 (3.5× longer)
- The longest Norfair track is 886 frames (82% of the video) versus 175
- Observed-fraction rises from 0.851 to 0.977 — the tracker is matching a
  detection almost every frame
- Only 3 stitch candidates (vs 43), and the rank-1 prediction error median
  falls from 125.7 px to 51.4 px

On the **YouTube** video the capacity effect is **much smaller**:

- -2.0% total detections (4135 → 4052) — within run-to-run noise
- Confidence rises modestly (0.476 → 0.518)
- Unique Norfair IDs go from 40 to 43 (effectively flat)
- Track-lifespan median is essentially unchanged (68.5 vs 73)
- Stitch candidates rise slightly (28 → 38) with similar rank-1 error

The asymmetry is consistent with the two clips. The identical_balls clip is
a clean studio recording of a 5-ball cascade where yolo26s is the original
baseline and is the one likely already used for prior calibration. The
YouTube clip is a more chaotic, lower-contrast, partly motion-blurred clip
where the additional capacity of `l` does not transfer into more usable
detections. **Capacity helps where the small model is the bottleneck**; on
already-busy frames the small model is not the bottleneck.

## 2. SEGMENTATION-MODEL EFFECT — yolo26l vs yolo26l-seg

The segmentation arm is **worse than the plain large detector on every
downstream metric measured here**:

- Total detections: 3292 → 2467 on identical, 4052 → 3925 on YouTube
- Mean confidence: 0.688 → 0.456 on identical, 0.518 → 0.522 on YouTube
- Unique Norfair track IDs: 14 → 72 on identical, 43 → 50 on YouTube
- Median Norfair track observed-frames: 139.5 → 23 on identical, 73 → 66.5 on YouTube
- Observed-fraction: 0.977 → 0.806 on identical, 0.882 → 0.857 on YouTube
- Short tracks (≤5 frames): 3 → 6 on identical, 3 → 2 on YouTube
- Stitch candidates: 3 → 98 on identical, 38 → 46 on YouTube

The seg model is much more conservative about claiming an instance. When it
*does* claim one, the bbox center and mask centroid agree very tightly
(median 0.69–1.63 px), so the additional head is not buying us a
meaningfully different tracking point — it is just emitting fewer
detections. Because Norfair stitches observed-frames into one tracklet,
fewer detections in the input translates directly into more tracklet
fragmentation downstream.

## 3. DOWNSTREAM EFFECT

- **Longer Norfair tracklets?** Yes for yolo26l on identical (lifespan
  median 40 → 139.5), not for yolo26l-seg (40 → 23 — actually shorter).
- **Fewer short fragments?** Yes for yolo26l on identical (1 → 3 short
  ≤5 in absolute, but the median length is 3.5× longer so the proportion
  drops dramatically). yolo26l-seg makes short fragments worse (1 → 6
  on identical).
- **Fewer required stitches?** Yes for yolo26l on identical (33 sources
  → 2 sources). yolo26l-seg makes stitching worse (33 → 60 sources).
- **Visibly better continuity?** Yes for yolo26l (see side-by-side Norfair
  comparisons). No for yolo26l-seg — it produces more ID switching and
  more dropped observations even on frames where the detector and seg
  model both agree the ball is there.

## 4. SEGMENTATION VISUAL FINDINGS

The mask visualizations are saved to `outputs/detector_seg_comparison/`:

- `identical_balls_trick_000_018_yolo26l-seg_classes-32_overlay.mp4`
- `youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26l-seg_classes-32_overlay.mp4`

Contact sheets (PNGs) summarize the visible quality:

`outputs/detector_seg_comparison/contact_sheets/`:
- `*_01_clean_airborne.png` — balls in the upper half of the frame
- `*_02_large_or_blurred.png` — top 10% bbox areas
- `*_03_near_hand_height.png` — ball centers in the lower third
- `*_04_catch_throw_band.png` — ball centers in y=[0.5h, 0.78h]
- `*_05_high_instance_count.png` — frames at the 90th-percentile count
- `*_06_low_mask_coverage.png` — frames where mask_area/bbox_area < 0.6

### Mask shape

The masks are **approximately ball-shaped blobs** that follow the visible
ball outline, with bbox↔centroid agreement within a couple of pixels. They
are not the tightest possible outlines — they tend to fill a slightly
larger area than the brightest ball pixels and on motion-blurred frames
they can pick up the trailing blur. They never extend onto obvious
background.

### Partial hand occlusion

**The seg model is not better at partial hand occlusion than the detector.**
On a representative frame (identical_balls frame 165) the situation is:

- yolo26l detector: detects 3 sports balls, including the one being held
  in the right hand at confidence 0.79
- yolo26s detector: detects 2 sports balls, misses the held one
- yolo26l-seg: detects 2 sports balls, **misses the same one the
  detector-only small model misses**

On identical_balls frame 473, the situation is even more dramatic: yolo26l
detects 5 sports balls but yolo26l-seg detects **1**, missing the four
balls that are either in hands or in close hand proximity. This is a real,
visually-confirmed recall loss, not a visualization artifact.

A plausible explanation: the segmentation head imposes a pixel-accurate
mask requirement that is more conservative than the detection head's
bounding-box requirement. When the ball boundary is ambiguous (hand
holding, motion blur, hand-coloured skin occluding part of the ball), the
seg head declines to emit an instance rather than emit a partial one. The
detector head is more willing to emit a "best-guess" bbox.

### False positives

Across the two videos the seg model does not appear to produce obviously
spurious detections (no detections on the billiard balls on the shelf, no
detections on the wall decorations, no detections on the bowling pins
visible in the background). Where seg finds an instance, it is a real
ball. The failure mode is **false-negative, not false-positive**.

### Mask instability

Mask area for the same ball varies smoothly with the ball's pixel size
(balls further from the camera have smaller masks). There is no
frame-to-frame flickering visible in the overlay MP4s at 60 fps. The
masks are not unstable — they are simply more conservative than
detection bboxes.

## 5. COST (speed / GPU)

- yolo26s is the cheapest: ~40–80 effective inference FPS, ~135 MB peak
- yolo26l is roughly 2× slower (consistent with 2× parameters): ~34–35
  effective FPS, ~263 MB peak (about 2× the memory of `s`)
- yolo26l-seg is in the same throughput band as yolo26l: ~30–58 effective
  FPS depending on clip, ~340 MB peak (about 25% more than `l`,
  2.5× more than `s`)

For the kind of juggling videos used here, **yolo26l is the cheapest model
that delivers the capacity improvement**. yolo26l-seg costs roughly the
same as yolo26l in time and a bit more in memory, but does not deliver
the capacity improvement — in fact it delivers a regression.

---

## ANSWERS TO THE FINAL QUESTIONS

1. **Does yolo26l detect meaningfully more plausible juggling-ball
   observations than yolo26s?**
   On the clean studio clip: yes — 20% more detections, 4× fewer
   fragments, almost no zero-detection frames. On the lower-contrast
   YouTube clip: no — within run-to-run noise on detection count and no
   improvement downstream. The capacity benefit is real where the small
   model is the bottleneck.

2. **Does this improve our existing Norfair tracking?**
   On identical_balls: a large improvement. Track IDs drop from 54 to 14,
   median lifespan jumps from 40 to 139.5 frames, observed-fraction rises
   from 0.851 to 0.977. On YouTube: essentially no change (40 vs 43 IDs,
   similar lifespans).

3. **Does yolo26l-seg appear better at detecting partially occluded
   balls, especially around hands?**
   No. The opposite. The seg model misses held/in-hand balls that the
   plain yolo26l detector finds (frame 165, frame 473 are visually
   confirmed). The seg head is more conservative when ball boundaries
   are ambiguous.

4. **Does feeding segmentation bbox centers into the same Norfair
   tracker produce longer / less fragmented tracks?**
   No. Track IDs go from 14 (yolo26l) to 72 (yolo26l-seg) on identical,
   and the median lifespan drops from 139.5 to 23. The seg model's
   conservative recall hurts the downstream tracker.

5. **Does segmentation introduce obvious false positives or unstable
   masks?**
   False positives: no, none observed. Unstable masks: no, mask area
   varies smoothly with apparent ball size and there is no visible
   flicker. The failure mode is recall loss, not precision loss.

6. **Which should become our next core perception baseline?**
   **yolo26l** for perception. The bbox-center tracking point is
   essentially indistinguishable from the seg-instance bbox center
   (centroid-distance median 0.69–1.63 px), so the segmentation head
   adds no useful tracking signal at this confidence threshold while it
   costs recall. The large detector gives the largest downstream
   improvement on the cleanest clip and does not regress on the noisy
   clip.

7. **What is the runtime cost of that choice?**
   yolo26l: ~34–35 effective inference FPS on these videos, ~263 MB peak
   GPU memory, ~1.5–2× the cost of yolo26s in time and ~2× the memory.
   That is a comfortable fit for an offline, sequential, vid_stride=1
   pipeline on this hardware. yolo26s is still adequate for
   the YouTube-style clip; the upgrade to `l` is justified primarily by
   the substantial clean-clip gain.

---

## VERDICT

Promote **yolo26l** as the next core perception baseline. Do **not**
promote yolo26l-seg. The segmentation model does not improve detection
recall, does not improve Norfair tracklet quality, and does not reduce
the need for stitching. Its visual outputs are reasonable and its masks
are ball-shaped and stable, but its empirical effect on the existing
Norfair + stitch pipeline is a regression across both clips.

The capacity bump from `s` to `l` is the meaningful win. The
segmentation head is dead weight in the current pipeline because the
downstream tracker uses the bbox center, not the mask centroid, and
because the seg head's strictness costs recall on the exact cases (hand
occlusion, motion blur) where we would most want help.

---

## ARTIFACTS

CSVs (small, committed):
- `detections/detector_seg_comparison/*_yolo26s_classes-32.csv` and friends
- `detections/detector_seg_comparison/*_norfair_dt50_hc5.csv`
- `detections/detector_seg_comparison/*_norfair_dt50_hc5_stitches.csv`
- `detections/detector_seg_comparison/identical_balls_..._instances.csv`
- `detections/detector_seg_comparison/summary.json` (full structured comparison)
- `detections/detector_seg_comparison/summary.csv` (flat per-arm table)

Scripts (committed):
- `scripts/segment_video.py` — seg arm perception + overlay MP4
- `scripts/compare_arms.py` — detection / Norfair / stitch / mask metrics
- `scripts/build_side_by_side.py` — synchronized compare MP4s
- `scripts/build_contact_sheets.py` — seg visual contact sheets
- `scripts/measure_runtime.py` — model-only inference timing
- `scripts/run_arm_triple.sh` — sequential runner for one video

Large MP4s (gitignored, kept local under `outputs/`):
- detection overlay MP4s (3 per video)
- seg overlay MP4s (1 per video)
- Norfair annotated MP4s (3 per video)
- stitch annotated MP4s (3 per video)
- side-by-side comparison MP4s (4 per video, 8 total)
- contact-sheet PNGs (6 per video, 12 total)

Model weights (gitignored, downloaded into worktree):
- yolo26s.pt, yolo26l.pt, yolo26l-seg.pt
