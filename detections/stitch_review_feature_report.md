# Reviewed stitch feature analysis

This is descriptive analysis only. It does not modify Norfair, candidate generation, tracklet IDs, or acceptance thresholds.

## Features

- `trajectory_fit_error`: pixel RMSE from fitting `x=a+b*t` and `y=c+d*t+e*t^2` to the last/first ten available tracklet points.
- Wrist distances: minimum Euclidean distance from the source endpoint, candidate start, and linearly interpolated gap positions to confident COCO wrists. Wrist confidence threshold was 0.30.
- The pretrained `yolo26s-pose.pt` model was used on both reviewed videos; no training or fine-tuning was performed.

## Overall correct versus wrong

| label | n | fit mean px | fit median px | hand mean px | hand median px | hand available |
|---|---:|---:|---:|---:|---:|---:|
| correct | 71 | 19.29 | 15.65 | 59.43 | 32.86 | 71/71 |
| wrong | 42 | 57.59 | 56.40 | 43.24 | 33.24 | 42/42 |

### Interpretation

- Correct stitches generally have lower trajectory-fit error in this reviewed sample (median 15.65 px versus 56.40 px for wrong). This supports using the fit as an analysis feature, but not as an automatic decision rule yet.
- Wrist proximity is not a clean global separator. Wrong stitches have mean/median nearest-wrist distance 43.24/33.24 px versus 59.43/32.86 px for correct, but the per-video breakdown is strongly affected by the label balance and scene composition.
- All 113 reviewed rows had at least one wrist available at the configured confidence threshold; this result should not be generalized beyond these videos.

## Per-video comparison

### `videos/identical_balls_trick_000_018.mp4`

| label | n | fit mean px | fit median px | hand mean px | hand median px |
|---|---:|---:|---:|---:|---:|
| correct | 45 | 21.78 | 15.17 | 87.31 | 51.95 |
| wrong | 40 | 58.89 | 59.53 | 45.04 | 35.02 |

### `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4`

| label | n | fit mean px | fit median px | hand mean px | hand median px |
|---|---:|---:|---:|---:|---:|
| correct | 26 | 14.98 | 16.40 | 11.18 | 9.93 |
| wrong | 2 | 31.58 | 31.58 | 7.32 | 7.32 |

## Correct stitches with very good trajectory fit

- `videos/identical_balls_trick_000_018.mp4 source=28 candidate=29 gap=3 fit=0.535923 px hand=326.965433 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=43 candidate=45 gap=4 fit=1.197573 px hand=51.946974 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=45 candidate=46 gap=3 fit=1.216354 px hand=86.174562 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=40 candidate=41 gap=3 fit=1.487353 px hand=53.127425 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=41 candidate=43 gap=7 fit=1.508575 px hand=44.964311 px (right)`

## Wrong stitches with poor trajectory fit

- `videos/identical_balls_trick_000_018.mp4 source=16 candidate=19 gap=2 fit=129.345258 px hand=67.262235 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=14 candidate=18 gap=0 fit=121.888633 px hand=76.034189 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=4 candidate=8 gap=4 fit=109.033958 px hand=29.348380 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=68 candidate=70 gap=8 fit=108.439702 px hand=43.715882 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=57 candidate=63 gap=4 fit=99.078060 px hand=40.092633 px (right)`

## Correct stitches with poor fit and an available wrist

- `videos/identical_balls_trick_000_018.mp4 source=73 candidate=75 gap=4 fit=71.106459 px hand=72.873221 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=7 candidate=10 gap=2 fit=64.331998 px hand=72.539399 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=4 candidate=7 gap=0 fit=57.982154 px hand=68.236527 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=63 candidate=65 gap=5 fit=52.676112 px hand=39.895231 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=1 candidate=6 gap=4 fit=49.404224 px hand=42.937736 px (right)`

## Correct poor-fit stitches closest to a wrist

- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=9 candidate=13 gap=5 fit=21.350311 px hand=3.506962 px (left)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=22 candidate=26 gap=6 fit=17.145463 px hand=5.371684 px (right)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=31 candidate=35 gap=5 fit=18.409638 px hand=7.269105 px (right)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=19 candidate=22 gap=6 fit=17.846956 px hand=8.058926 px (right)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=2 candidate=8 gap=5 fit=19.367558 px hand=8.839860 px (right)`

## Wrong stitches with good trajectory fit

- `videos/identical_balls_trick_000_018.mp4 source=22 candidate=27 gap=5 fit=11.985217 px hand=18.763693 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=38 candidate=40 gap=10 fit=12.906510 px hand=28.976188 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=37 candidate=39 gap=6 fit=16.946509 px hand=36.783412 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=35 candidate=38 gap=5 fit=19.241389 px hand=6.985168 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=59 candidate=62 gap=10 fit=20.796188 px hand=12.523027 px (left)`

## Failure-mode question

The reviewed data is consistent with two overlapping regimes rather than a single hard rule: many wrong stitches have poor geometric fit, while some wrong stitches have good fit and some correct stitches have poor fit. The latter cases are candidates for hand-interaction or other occlusion-related review, but wrist proximity alone does not establish that explanation. No classifier or threshold was trained or selected.
