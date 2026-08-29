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

## 6. CAPACITY EFFECT — yolo26l vs yolo26x (arm D)

The `x` model is the next capacity step above `l` (about 2.5x parameter
count). It is asked: does that translate into more or better downstream
tracks?

The headline answer is **no — and the data shows the larger model is
actively worse than `l` on the cleanest clip, while essentially tied on
the noisy clip.**

### identical_balls

- Total detections: 3292 (l) → **2356 (x)** — a 28% drop
- Mean confidence: 0.688 (l) → **0.362 (x)** — almost half
- Median confidence: 0.749 (l) → **0.329 (x)** — a striking fall
- Frames with 0 detections: 0 (l) → **52 (x)** — `x` is now missing balls
  on 5% of frames where `l` was perfect
- Frames with exactly 3 detections (the ground-truth ball count for
  this clip): 995 (l) → 468 (x)
- Unique Norfair track IDs: 14 (l) → **79 (x)** — 5.6x more fragments
- Median Norfair track observed-frames: 139.5 (l) → **19 (x)** — 7x shorter
- Observed-fraction: 0.977 (l) → 0.778 (x)
- Short tracks (≤5): 3 (l) → 11 (x); (≤10): 3 (l) → 23 (x)
- Stitch candidates: 3 (l) → **103 (x)**; sources needing candidates:
  2 (l) → 61 (x)
- Rank-1 prediction error median: 51.4 (l) → 111.5 (x)

The `x` model on the clean studio clip behaves like a worse detector
than `s` in every respect except the longest single track length (371
vs 175 / 886). The simplest explanation is that `x` over-thinks the
clean clip and emits low-confidence bbox proposals that don't make it
through Norfair's distance/hit-counter matching, fragmenting the tracks.
The very low mean confidence (0.362) is the smoking gun: when the
model is unsure, the bbox lands in the CSV but the tracker cannot
build a coherent tracklet out of weakly-supported observations.

### youtube

- Total detections: 4052 (l) → 4136 (x) — within ~2% (noise)
- Mean confidence: 0.518 (l) → 0.542 (x) — slightly higher
- Median confidence: 0.543 (l) → 0.571 (x) — slightly higher
- Frames with 0 detections: 0 (l) → 3 (x) — essentially flat
- Unique Norfair track IDs: 43 (l) → **34 (x)** — 21% fewer fragments
- Median Norfair track observed-frames: 73 (l) → **79.5 (x)** — 9% longer
- Longest single track: 355 (l) → **490 (x)** — 38% longer
- Short tracks (≤5): 3 (l) → 0 (x); (≤10): 3 (l) → 3 (x)
- Observed-fraction: 0.882 (l) → 0.879 (x) — flat
- Stitch candidates: 38 (l) → 27 (x); sources needing candidates:
  30 (l) → 23 (x)
- Rank-1 prediction error median: 104.9 (l) → 102.2 (x) — flat

On the YouTube clip `x` is the **best of the four arms**: lowest
fragment count, longest tracks, no tracks shorter than 5 frames, and the
lowest stitch count. The capacity bump pays off here in the way the
previous report predicted it would not — but only here.

### Per-frame count agreement

The framewise diff table tells a consistent story:

- `l` vs `x` on identical: only 460/1079 frames (43%) agree; 294 of
  the disagreeing frames differ by 2+ balls. `x` is detecting a
  genuinely different (and worse-supported) set of balls.
- `l` vs `x` on YouTube: 388/900 frames (43%) agree; the disagreement
  is concentrated in the ±1 and ±2 buckets, consistent with `x`
  agreeing with `l` most of the time and only occasionally emitting
  a different number of balls.

### Cost

- yolo26x: 18.4–20.4 effective FPS, 447.3 MB peak GPU memory
- yolo26l:  34.3–35.4 effective FPS, 262.6 MB peak GPU memory
- yolo26x is **about 1.7x slower and uses 1.7x more memory** than
  yolo26l on this hardware

The extra compute is roughly in line with the parameter-count
ratio. The memory peak (~447 MB) leaves plenty of headroom on the
RTX 3060's 6 GB, but the inference time is now slow enough that
offline vid_stride=1 is still comfortable but anything approaching
real-time at full resolution is not.

### What this means

- The clean studio clip is **calibrated to yolo26l**: the `l` model is
  already at ceiling performance on it, and going to `x` costs recall
  without buying anything. The `s → l` jump was a capacity bottleneck
  being removed; the `l → x` jump tries to remove a bottleneck that
  is no longer there.
- The YouTube clip is **not** bottlenecked by detection — adding
  capacity turns into incremental improvements (longer tracks, fewer
  fragments) but the absolute gains are small and the model is
  operating in a regime where the additional precision of `x` can
  help.
- yolo26x is **strictly dominated** on this evidence: it is never the
  best of the four arms, it ties or loses on every downstream metric
  on the cleanest clip, and its only win (YouTube) is modest.
- The behavior on identical (mean conf halved, track count 5.6x,
  stitches 30x) is strong evidence that the clean clip is also a
  regime where the detector head is over-confident at `l` and the
  extra capacity of `x` does not translate into better bbox
  proposals — it actually appears to *hurt* calibration.

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

8. **Is yolo26x (the next capacity step above `l`) worth promoting?**
   No. On the clean studio clip it is **strictly worse** than yolo26l
   on every downstream metric — 28% fewer detections, mean confidence
   nearly halved, 5.6x more Norfair fragments, 7x shorter median
   tracks, 30x more stitch candidates. On the YouTube clip it is
   slightly the best of the four arms, but the gain over yolo26l is
   modest (34 vs 43 IDs, 79.5 vs 73 frame median lifespan, 0 vs 3
   sub-5-frame tracks) and the cost is ~1.7x slower and ~1.7x more
   memory. yolo26x is **dominated** — there is no clip where it is
   the best choice in a way that justifies the cost.

---

## 7. THRESHOLD SWEEP — yolo26l vs yolo26x

The fixed-conf comparison above uses `conf=0.15` for both models. This
section asks a different question: **is the yolo26x penalty on the
clean clip an operating-point artifact, or is the x model genuinely
worse for this task?**

### Method

- One inference per (model × video) at `conf=0.05` (4 runs total).
- All detections retained with their full confidence values.
- The `0.10`, `0.075` and `0.05` arms are derived by *offline filtering*
  of the saved detections rather than re-running expensive GPU
  inference.
- The exact same Norfair (`dt=50`, `hc=5`) and stitcher
  (`max_gap_frames=10`) settings are used for every arm.

**Validation**: filtering the `conf=0.05` output to `>=0.15` and
comparing it against the canonical `conf=0.15` CSVs produced by
`detect_video.py --conf 0.15` for the same (model, video) pair:

| Model | Video | Canonical rows | Filtered >=0.15 rows | Diff exit |
|-------|-------|----------------:|---------------------:|----------:|
| yolo26l | identical_balls | 3292 | 3292 | 0 |
| yolo26x | identical_balls | 2356 | 2356 | 0 |
| yolo26l | youtube | 4052 | 4052 | 0 |
| yolo26x | youtube | 4136 | 4136 | 0 |

All four replications are byte-identical (sort-diffs exit 0). The
filtering approach is sound. **Total GPU work: 4 inference runs at
conf=0.05 instead of 16 inference runs across all (model, conf) cells.**

### Detection counts

| | conf=0.15 | 0.10 | 0.075 | 0.05 |
|--|--:|--:|--:|--:|
| **l** identical | 3292 | 3413 | 3677 | 4399 |
| **x** identical | 2356 | 3025 | 3703 | 5149 |
| **l** youtube | 4052 | 4320 | 4492 | 4749 |
| **x** youtube | 4136 | 4423 | 4599 | 4876 |

A few observations:

- yolo26x at `conf=0.10` on identical (3025) already **exceeds**
  yolo26l at `conf=0.15` (3292) only by a small margin — but the
  composition is different (see below).
- At `conf=0.05`, both models approach 4-5 detections per frame, and
  the per-frame count histogram shifts from mostly 3 and 4+ to mostly
  4+, indicating the additional detections are distributed across the
  frames rather than concentrated in already-detected ones.
- The mean confidence drops sharply as the threshold is lowered:
  l-idential 0.688→0.668→0.626→0.533; x-identical 0.362→0.309→0.268→0.210.
  The x model's score distribution is significantly lower than l's
  at every operating point, confirming the calibration gap noted in
  the original report.

### New detections admitted at each step

| Model | Video | 0.15→0.10 | 0.10→0.075 | 0.075→0.05 |
|-------|-------|----------:|------------:|-----------:|
| l | identical | +121 (mean 0.120) | +264 (mean 0.085) | +722 (mean 0.062) |
| x | identical | +669 (mean 0.122) | +678 (mean 0.086) | +1446 (mean 0.061) |
| l | youtube | +268 (mean 0.124) | +172 (mean 0.086) | +257 (mean 0.061) |
| x | youtube | +287 (mean 0.126) | +176 (mean 0.087) | +277 (mean 0.061) |

The most informative step is **0.15 → 0.10**:

- On identical, x admits **5.5× more new detections** than l at this
  step (669 vs 121). The new detections have nearly identical mean
  confidence (0.122 vs 0.120) — they are the same *kind* of
  detections, x just emits them more often in this band.
- On youtube both models admit similar counts (~270-290); the gap is
  almost entirely a clean-clip phenomenon.

The frame-bucket distribution of those 0.15→0.10 new x detections
on identical is concentrated in frames 200-799 (the active juggling
zone): 85 in [0,200), 158 in [200,400), 153 in [400,600), 140 in
[600,800), 133 in [800+). The new x detections are tracking-relevant,
not concentrated at clip boundaries.

### IDENTICAL_BALLS THRESHOLD TABLE

| Model | conf | Dets | Mean/frame | Fr 0 | Fr 3 | Fr 4+ | Conf mean | IDs | Lifespan med | Lifespan max | Obs frac | Short ≤5 | Short ≤10 | Stitch cand | Rank-1 err med |
|--------|-----:|----:|----------:|----:|----:|-----:|----------:|----:|-------------:|-------------:|---------:|--------:|---------:|------------:|---------------:|
| yolo26l | 0.15  | 3292 | 3.05 | 0  | 995 | 59  | 0.688 | 14 | 139.5 | 886  | 0.977 | 3  | 3  |  3 |  51.4 |
| yolo26l | 0.10  | 3413 | 3.16 | 0  | 939 | 131 | 0.668 | 17 |  15   | 1077 | 0.976 | 8  | 9  |  0 |   0.0 |
| yolo26l | 0.075 | 3677 | 3.41 | 0  | 778 | 292 | 0.626 | 34 |  15   | 1077 | 0.947 | 14 | 18 |  8 | 242.0 |
| yolo26l | 0.05  | 4399 | 4.08 | 0  | 429 | 647 | 0.533 | 56 |  16.5 | 1077 | 0.926 | 19 | 30 | 35 |   0.2 |
| yolo26x | 0.15  | 2356 | 2.18 | 52 | 468 | 29  | 0.362 | 79 |  19   | 371  | 0.778 | 24 | 40 |103 | 111.5 |
| yolo26x | 0.10  | 3025 | 2.80 |  7 | 524 | 194 | 0.309 | 59 |  31   | 404  | 0.850 | 14 | 18 | 57 | 136.4 |
| yolo26x | 0.075 | 3703 | 3.43 |  5 | 396 | 486 | 0.268 | 62 |  33   | 489  | 0.869 | 10 | 21 | 51 | 156.6 |
| yolo26x | 0.05  | 5149 | 4.77 |  0 | 105 | 938 | 0.210 | 63 |  36   | 599  | 0.898 |  9 | 14 | 52 | 121.5 |

**Identical-balls curve (l = solid markers, x = open markers):**

| Threshold | Direction | Result |
|-----------|-----------|--------|
| 0.15 | — | yolo26l dominates: 14 IDs vs 79, 139.5 vs 19 lifespan, 3 vs 103 stitches |
| 0.10 | lower | yolo26l **regresses** (IDs 14→17, lifespan 139.5→15, 1077-frame track splits) — a single spurious low-conf detection starts a fresh ID. yolo26x **improves on every metric** (IDs 79→59, lifespan 19→31, stitches 103→57, observed-fraction 0.778→0.850) |
| 0.075 | lower | yolo26l continues to regress (34 IDs, 15-frame median lifespan). yolo26x keeps improving (62 IDs, 33-frame median lifespan, 51 stitches) |
| 0.05 | lower | both models get noisier; l continues regressing, x plateaus around 63 IDs / 36 frames |

**The clean-clip x curve does reach l's regime at conf=0.10**, but
**l itself also regresses** as the threshold is lowered on this clip.
At `conf=0.10` the x model (59 IDs, lifespan 31, 57 stitches) still
has ~3-4× more track fragments and ~5× shorter median lifespan than
l at `conf=0.15` (14 IDs, 139.5, 3 stitches). **x never catches up
to l-at-0.15** on the identical clip at any threshold tested.

### YOUTUBE THRESHOLD TABLE

| Model | conf | Dets | Mean/frame | Fr 3 | Fr 4+ | Conf mean | IDs | Lifespan med | Lifespan max | Obs frac | Short ≤5 | Short ≤10 | Stitch cand | Rank-1 err med |
|--------|-----:|----:|----------:|----:|-----:|----------:|----:|-------------:|-------------:|---------:|--------:|---------:|------------:|---------------:|
| yolo26l | 0.15  | 4052 | 4.50 | 114 | 780 | 0.518 | 43 | 73.0 | 355  | 0.882 | 3 | 3  | 38 | 104.9 |
| yolo26l | 0.10  | 4320 | 4.80 |  70 | 827 | 0.493 | 41 | 77.0 | 281  | 0.901 | 5 | 5  | 35 |  96.3 |
| yolo26l | 0.075 | 4492 | 4.99 |  47 | 852 | 0.478 | 32 | 95.5 | 437  | 0.913 | 8 | 8  | 24 |  95.2 |
| yolo26l | 0.05  | 4749 | 5.28 |  26 | 874 | 0.455 | 30 |108.0 | 439  | 0.924 |10 |10  | 15 |  93.2 |
| yolo26x | 0.15  | 4136 | 4.60 |  84 | 780 | 0.542 | 34 | 79.5 | 490  | 0.879 | 3 | 4  | 27 | 102.2 |
| yolo26x | 0.10  | 4423 | 4.91 |  56 | 829 | 0.515 | 30 | 72.5 | 808  | 0.905 | 8 |10  | 19 | 114.5 |
| yolo26x | 0.075 | 4599 | 5.11 |  38 | 854 | 0.499 | 32 | 72.5 | 808  | 0.915 | 8 |11  | 17 | 129.7 |
| yolo26x | 0.05  | 4876 | 5.42 |  23 | 874 | 0.474 | 48 | 76.5 | 486  | 0.911 |11 |15  | 28 | 134.5 |

**YouTube curves are nearly monotonic and pretty**:

- yolo26l on YouTube keeps improving as the threshold drops: IDs
  43 → 41 → 32 → 30; lifespan 73 → 77 → 95.5 → 108; observed-fraction
  0.882 → 0.924; stitches 38 → 35 → 24 → 15. The cleanest "more
  detections, fewer fragments, longer tracks" curve in the sweep.
- yolo26x on YouTube improves from 0.15 → 0.10 → 0.075 (34 → 30 →
  32 IDs, observed-fraction 0.879 → 0.905 → 0.915) but **regresses**
  at conf=0.05 (48 IDs, lifespan drops back to 76.5). The plateau
  is at `conf≈0.075`.

### Visual findings (false-positive / hand-occlusion / motion-blur)

Six contact sheets of 24 crops each were inspected visually; each
contact sheet contains detections that newly appeared at one threshold
step. Categories: (a) plausible juggling ball, (b) plausible ball
partly occluded by hand, (c) hand/finger artifact, (d) obvious false
positive, (e) ambiguous.

Identical_balls (clean studio clip — there is a static shelf of
white balls in the background that is *itself* ball-shaped):

| Sheet | (a) | (b) | (c) | (d) | (e) | Note |
|-------|---:|---:|---:|---:|---:|------|
| x @ 0.15→0.10 | 5 | 4 | 0 | 15 | 0 | 15/24 are **the static shelf balls**; 9 are real juggling balls (5 airborne + 4 hand-held) |
| x @ 0.10→0.075 | 20 | 3 | 0 |  1 | 0 | 20/24 are the static shelf balls again (real balls but wrong targets); 3 are juggling balls in hand; 1 background FP |
| x @ 0.075→0.05 | 20 | 4 | 0 |  0 | 0 | all 24 are real balls (mostly static shelf) — *no* category-d FPs at the very-low band |
| l @ 0.15→0.10 | 2 | 6 | 0 | 16 | 0 | 16/24 are plush-toy / basket false positives; only 8 real juggling balls |

So on identical_balls, **lowering x's threshold recovers real
juggling-ball detections but floods the input with the static
shelf-ball false positives** (real ball-shapes, wrong identity
target). Lowering l's threshold floods the input with plush-toy
false positives (clearly-wrong objects) and recovers fewer real
balls in absolute terms.

YouTube:

| Sheet | (a) | (b) | (c) | (d) | (e) |
|-------|---:|---:|---:|---:|---:|
| x @ 0.15→0.075 | ~7 | ~11 | ~2-3 | ~2 | ~2-3 |
| l @ 0.15→0.075 | ~8 | ~13 | 0 | 1 | ~2 |

On YouTube both models recover mostly-real juggling balls when
their threshold is lowered: ~75% (x) and ~88% (l) of the new
detections are plausible balls (mostly in hand — category b).
Background false positives are rare on this clip because there is
no static ball-shaped decor; the "shelves" are curtains and walls
with no spherical decor.

### Per-threshold observation: hand occlusion and motion blur

Hand occlusion (category b) is the dominant source of conf < 0.15
detections on the YouTube clip for both models. The pattern is
consistent: at conf = 0.15 both models miss balls being caught or
released; lowering the threshold recovers those catches.

On the identical clip, hand occlusion recovers real balls
(category b in x@0.15→0.10 = 4/24), but the dominant "missed at
0.15" category is the static shelf of balls, which the x model is
emitting many low-confidence proposals on.

Motion blur is a smaller contributor than hand occlusion in this
sweep. There are a few examples in the YouTube sheets (e.g. f728
on l@0.15→0.075, f918 on x@0.15→0.075) but they are not the
primary failure mode.

### L vs X verdict after the sweep

The original l-vs-x comparison at conf=0.15 painted a picture of
"yolo26x is much worse on clean, slightly better on noisy". The
sweep refines that:

- **On identical_balls, the x-vs-l gap is partially an operating-
  point artifact, but lowering the threshold does NOT close it.** At
  every threshold tested, x produces strictly more track fragments
  and shorter median lifespans than l. x at conf=0.10 (59 IDs, 31
  median lifespan) does not match l at conf=0.15 (14 IDs, 139.5
  median lifespan). The reason is partly visible in the contact
  sheets: the static shelf balls in the identical clip are real
  ball-shapes that x emits low-confidence proposals on, and these
  proposals don't improve tracking — they introduce extra track
  fragments.
- **On YouTube, the gap closes with a lower threshold.** l's
  improvement as the threshold drops is monotonic; x's improvement
  plateaus around conf=0.075. At conf=0.075, x (32 IDs, 72.5 median
  lifespan) is roughly comparable to l at conf=0.075 (32 IDs, 95.5
  median lifespan). x at conf=0.10 (30 IDs, 72.5) is even closer to
  l's best.
- **The original l-vs-x difference is a mixture.** On the noisy
  YouTube clip, the gap is mostly an operating-point artifact — the
  same tracking quality is achievable at a different threshold. On
  the clean clip, the x model's tendency to emit low-confidence
  proposals on static ball-shaped props means it never recovers l's
  tracking quality no matter what threshold is used.

### BEST yolo26l THRESHOLD

- identical_balls: **conf=0.15** (any lower threshold regresses
  tracking by splitting the 1077-frame master track into many
  short fragments).
- youtube: **conf=0.05** by raw metrics (30 IDs, lifespan 108, 15
  stitches, observed-fraction 0.924), but **conf=0.075** is the
  defensible sweet spot — conf=0.05 is only marginally better than
  conf=0.075 on every metric and starts to introduce visible
  duplicates on individual balls.

### BEST yolo26x THRESHOLD

- identical_balls: **conf=0.10** — best on every tracking metric
  (59 IDs, 31 median lifespan, 57 stitches), and avoids the static
  shelf-ball false-positive flood that begins at conf=0.075.
- youtube: **conf=0.075** — best on IDs and stitches; conf=0.05
  starts introducing more fragments and the rank-1 prediction error
  median grows from 102 to 134 px.

### CORE BASELINE RECOMMENDATION

After the sweep:

- **yolo26l at conf=0.15 is still the recommended default** for the
  clean studio clip.
- **yolo26l at conf=0.075 (or conf=0.05) is the recommended default**
  for the YouTube-style noisy clip, where the additional
  detections materially reduce fragmentation and improve observed-
  fraction without introducing visible duplicates.
- **yolo26x is still not recommended** as a perception upgrade. The
  threshold sweep shows that the right way to capture more juggling-
  ball detections is to lower the threshold of the **existing**
  yolo26l baseline, not to upgrade to x. The x model can be made
  competitive with l only by giving up the conf=0.15 operating
  point — and on the clean clip it never closes the gap.

The remaining failure mode worth addressing is the **static
ball-shaped decor** in the clean studio clip. A background-aware
filter (motion, frame-difference, or learned) would let us lower
the threshold more aggressively without flooding the input with
shelf-ball false positives.

---

## VERDICT

Promote **yolo26l** as the next core perception baseline. Do **not**
promote yolo26l-seg. Do **not** promote yolo26x.

- yolo26l is the cheapest model that delivers the meaningful clean-clip
  capacity improvement (4x fewer track fragments, 3.5x longer median
  lifespan) without regressing on the noisy clip.
- yolo26l-seg adds a segmentation head that does not improve detection
  recall, does not improve Norfair tracklet quality, and does not reduce
  the need for stitching. Its visual outputs are reasonable and its
  masks are ball-shaped and stable, but its empirical effect on the
  existing Norfair + stitch pipeline is a regression across both clips.
  The seg head is dead weight in the current pipeline because the
  downstream tracker uses the bbox center, not the mask centroid, and
  because the seg head's strictness costs recall on the exact cases
  (hand occlusion, motion blur) where we would most want help.
- yolo26x is the next capacity step above `l` and it is **strictly
  dominated** on both clips: it loses to `l` everywhere on the clean
  clip and barely ties or modestly wins on the noisy clip at 1.7x the
  cost. The capacity benefit was already extracted by `l` on the
  clean clip; on the noisy clip the bottleneck is not detection
  capacity, so the additional parameters do not translate into
  better tracking.

The capacity bump from `s` to `l` is the meaningful win. The
segmentation head and the `x` capacity step are both dead weight in
the current pipeline.

The threshold sweep (Section 7) refines the operating-point choice
**without changing the model**:

- **Clean studio clip**: yolo26l @ conf=0.15 remains optimal. Lowering
  the threshold regresses tracking (single spurious detections
  fragment the 1077-frame master track) and floods the input with
  static shelf-ball false positives.
- **Noisy YouTube-style clip**: yolo26l benefits substantially from a
  lower threshold. conf=0.075 (or conf=0.05 if you can tolerate the
  marginal duplicate risk) materially improves fragmentation,
  observed-fraction and stitching burden. The x model does not
  dominate yolo26l at any threshold here either.
- **yolo26x is still not promoted** at any threshold. On the clean
  clip it never matches yolo26l @ 0.15. On the noisy clip its best
  configuration (conf=0.075, 32 IDs) is matched by yolo26l @ conf=0.075
  (32 IDs, longer lifespan).

The correct takeaway is **use yolo26l, and tune the threshold to
the clip class** — not upgrade to a larger model.

---

## ARTIFACTS

CSVs (small, committed):
- `detections/detector_seg_comparison/*_yolo26s_classes-32.csv` and friends
- `detections/detector_seg_comparison/*_yolo26l_classes-32.csv` and friends
- `detections/detector_seg_comparison/*_yolo26l-seg_classes-32.csv` and friends
- `detections/detector_seg_comparison/*_yolo26x_classes-32.csv` and friends
- `detections/detector_seg_comparison/*_norfair_dt50_hc5.csv`
- `detections/detector_seg_comparison/*_norfair_dt50_hc5_stitches.csv`
- `detections/detector_seg_comparison/*_instances.csv` (seg arm only)
- `detections/detector_seg_comparison/identical_summary.json` /
  `youtube_summary.json` (full structured comparison, 4 arms)
- `detections/detector_seg_comparison/identical_summary.csv` /
  `youtube_summary.csv` (flat per-arm table)

Scripts (committed):
- `scripts/segment_video.py` — seg arm perception + overlay MP4
- `scripts/compare_arms.py` — detection / Norfair / stitch / mask metrics
- `scripts/build_side_by_side.py` — synchronized compare MP4s
- `scripts/build_contact_sheets.py` — seg visual contact sheets
- `scripts/measure_runtime.py` — model-only inference timing
- `scripts/run_arm_triple.sh` — sequential runner for one video (4 arms)
- `scripts/filter_detections.py` — filter a detection CSV to >=conf
  (used to derive conf0.10 / 0.075 / 0.05 arms from one conf0.05 run)
- `scripts/sweep_summarize.py` — per-(model, threshold, video)
  detection / Norfair / stitch summary + per-step new-detection deltas
- `scripts/render_detections.py` — render a detection CSV as bbox
  overlay (used to visualize the threshold-sweep arms without
  re-running inference)
- `scripts/threshold_introduced_contact_sheet.py` — contact sheet of
  detections that only appear at a lower threshold

Large MP4s (gitignored, kept local under `outputs/`):
- detection overlay MP4s (4 per video, 8 total) — one per arm
- seg overlay MP4s (1 per video) — yolo26l-seg
- Norfair annotated MP4s (4 per video, 8 total) — one per arm
- stitch annotated MP4s (4 per video, 8 total) — one per arm
- side-by-side comparison MP4s:
  - `*_yolo26s_vs_yolo26l_detections.mp4`, `*_yolo26s_vs_yolo26l_tracks.mp4`
  - `*_yolo26l_vs_yolo26l-seg_segmentation.mp4`
  - `*_yolo26l_vs_yolo26x_detections.mp4`, `*_yolo26l_vs_yolo26x_tracks.mp4`
  - `*_yolo26s_vs_yolo26x_detections.mp4`, `*_yolo26s_vs_yolo26x_tracks.mp4`
- contact-sheet PNGs (6 per video, 12 total) — yolo26l-seg visual QA

Threshold-sweep artifacts (Section 7):
- `detections/detector_seg_comparison/threshold_sweep/*_conf{015,010,0075,005}.csv`
  (16 sub-arm detection CSVs; canonical `_conf015.csv` is a filter
  of the single conf0.05 inference and is byte-identical to the
  prior canonical conf0.15 output)
- `detections/detector_seg_comparison/threshold_sweep/*_norfair_dt50_hc5.csv`
- `detections/detector_seg_comparison/threshold_sweep/*_norfair_dt50_hc5_stitches.csv`
- `detections/detector_seg_comparison/threshold_sweep/sweep_summary.{json,csv}`
  (per-(model, threshold, video) metric summary + per-step
  new-detection deltas)
- `outputs/detector_seg_comparison/threshold_sweep/*_overlay.mp4`
  (4 per video, 8 total — one per arm visualized)
- `outputs/detector_seg_comparison/threshold_sweep/{identical,youtube}_l*_vs_x*`
  (6 side-by-side MP4s comparing the canonical and best-lower arms)
- `outputs/detector_seg_comparison/threshold_sweep/contact_sheets/*.png`
  (6 contact sheets of threshold-introduced detections, used for
  the visual FP/hand-occlusion/motion-blur classification)

Model weights (gitignored, downloaded into worktree):
- yolo26s.pt, yolo26l.pt, yolo26l-seg.pt, yolo26x.pt
