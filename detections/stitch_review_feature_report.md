# Reviewed stitch feature analysis

This is descriptive analysis only. It does not modify Norfair, candidate generation, tracklet IDs, or acceptance thresholds.

## Features

- `trajectory_fit_error`: pixel RMSE from fitting `x=a+b*t` and `y=c+d*t+e*t^2` to the last ten observed source points and first ten observed candidate points. Norfair-only predicted rows are retained in the track CSV but excluded from this fit.
- Source endpoints, candidate starts, and source endpoint velocity estimates use actual observed points; `prediction_error` remains the original stitch-candidate feature.
- Wrist distances: minimum Euclidean distance from the source endpoint, candidate start, and linearly interpolated gap positions to confident COCO wrists. Wrist confidence threshold was 0.30.
- The pretrained `yolo26s-pose.pt` model was used on both reviewed videos; no training or fine-tuning was performed.

## Overall correct versus wrong

| label | n | fit mean px | fit median px | hand mean px | hand median px | hand available |
|---|---:|---:|---:|---:|---:|---:|
| correct | 71 | 16.89 | 11.20 | 50.31 | 22.18 | 71/71 |
| wrong | 42 | 49.30 | 47.27 | 34.87 | 23.22 | 42/42 |

### Interpretation

- Correct stitches generally have lower trajectory-fit error in this reviewed sample (median 11.20 px versus 47.27 px for wrong). This supports using the fit as an analysis feature, but not as an automatic decision rule yet.
- Wrist proximity is not a clean global separator. Wrong stitches have mean/median nearest-wrist distance 34.87/23.22 px versus 50.31/22.18 px for correct, but the per-video breakdown is strongly affected by the label balance and scene composition.
- 113 reviewed rows were enriched; 113 had enough observed points for a trajectory fit. This result should not be generalized beyond these videos.

## Rank-stratified comparison

Rank-1 candidates are the top-ranked stitch hypotheses from the unchanged candidate generator; rank-2/3 rows are alternate candidates reviewed under the same labels.

| candidate ranks | label | n | fit median px |
|---|---:|---:|---:|

| rank-1 | correct | 68 | 10.87 |
| rank-1 | wrong | 15 | 46.14 |
| rank-2/3 | correct | 3 | 41.29 |
| rank-2/3 | wrong | 27 | 51.66 |

## Rank-1 candidate ambiguity

Margins are best-alternative error minus rank-1 error. Ratios are rank-1 error divided by best-alternative error; ratios closer to 1 indicate less relative separation, while lower ratios indicate a stronger relative preference. The best alternative is selected separately for prediction and trajectory fit when computing each metric.

| label | n | prediction margin median | trajectory-fit margin median | prediction ratio median | trajectory-fit ratio median |
|---|---:|---:|---:|---:|---:|
| correct | 23 | 146.13 px | 25.52 px | 0.42 | 0.27 |
| wrong | 3 | 74.87 px | 2.11 px | 0.65 | 0.95 |

- 26 of 83 reviewed rank-1 rows had both margins available; prediction margins are higher for correct rank-1 stitches in this sample.
- Trajectory-fit margins are higher for correct rank-1 stitches in this sample.
These are descriptive comparisons only; no threshold or classifier was selected.

### Confidently correct examples

- `videos/identical_balls_trick_000_018.mp4 source=39 candidate=47 prediction_alternative=48 trajectory_alternative=48 prediction_margin=609.766593 trajectory_margin=79.553154 prediction_ratio=0.023555 trajectory_ratio=0.016808`
- `videos/identical_balls_trick_000_018.mp4 source=4 candidate=7 prediction_alternative=8 trajectory_alternative=8 prediction_margin=470.682934 trajectory_margin=34.740729 prediction_ratio=0.185774 trajectory_ratio=0.642537`
- `videos/identical_balls_trick_000_018.mp4 source=31 candidate=36 prediction_alternative=38 trajectory_alternative=38 prediction_margin=410.726358 trajectory_margin=30.376437 prediction_ratio=0.031155 trajectory_ratio=0.040673`
- `videos/identical_balls_trick_000_018.mp4 source=41 candidate=43 prediction_alternative=44 trajectory_alternative=44 prediction_margin=270.232089 trajectory_margin=45.142732 prediction_ratio=0.032263 trajectory_ratio=0.026989`
- `videos/identical_balls_trick_000_018.mp4 source=64 candidate=68 prediction_alternative=69 trajectory_alternative=69 prediction_margin=264.823302 trajectory_margin=51.370532 prediction_ratio=0.353342 trajectory_ratio=0.297249`

### Ambiguous wrong examples

- `videos/identical_balls_trick_000_018.mp4 source=63 candidate=66 prediction_alternative=65 trajectory_alternative=65 prediction_margin=8.279594 trajectory_margin=-6.340612 prediction_ratio=0.977660 trajectory_ratio=1.115545`
- `videos/identical_balls_trick_000_018.mp4 source=15 candidate=17 prediction_alternative=16 trajectory_alternative=16 prediction_margin=74.870756 trajectory_margin=2.111431 prediction_ratio=0.648899 trajectory_ratio=0.948858`
- `videos/identical_balls_trick_000_018.mp4 source=18 candidate=21 prediction_alternative=22 trajectory_alternative=22 prediction_margin=163.022415 trajectory_margin=10.948259 prediction_ratio=0.593570 trajectory_ratio=0.788065`

### Wrong rank-1 stitches that still look confident

- `videos/identical_balls_trick_000_018.mp4 source=18 candidate=21 prediction_alternative=22 trajectory_alternative=22 prediction_margin=163.022415 trajectory_margin=10.948259 prediction_ratio=0.593570 trajectory_ratio=0.788065`
- `videos/identical_balls_trick_000_018.mp4 source=15 candidate=17 prediction_alternative=16 trajectory_alternative=16 prediction_margin=74.870756 trajectory_margin=2.111431 prediction_ratio=0.648899 trajectory_ratio=0.948858`
- `videos/identical_balls_trick_000_018.mp4 source=63 candidate=66 prediction_alternative=65 trajectory_alternative=65 prediction_margin=8.279594 trajectory_margin=-6.340612 prediction_ratio=0.977660 trajectory_ratio=1.115545`

## Per-video comparison

### `videos/identical_balls_trick_000_018.mp4`

| label | n | fit mean px | fit median px | hand mean px | hand median px |
|---|---:|---:|---:|---:|---:|
| correct | 45 | 20.14 | 15.55 | 76.10 | 34.12 |
| wrong | 40 | 50.72 | 48.88 | 35.53 | 23.22 |

### `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4`

| label | n | fit mean px | fit median px | hand mean px | hand median px |
|---|---:|---:|---:|---:|---:|
| correct | 26 | 11.27 | 11.10 | 5.68 | 4.27 |
| wrong | 2 | 20.81 | 20.81 | 21.72 | 21.72 |

## Correct stitches with very good trajectory fit

- `videos/identical_balls_trick_000_018.mp4 source=43 candidate=45 gap=4 fit=0.483449 px hand=49.630991 px (right)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=27 candidate=28 gap=4 fit=0.583007 px hand=25.172746 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=28 candidate=29 gap=3 fit=0.591355 px hand=326.965433 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=37 candidate=40 gap=10 fit=0.846868 px hand=35.675104 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=45 candidate=46 gap=3 fit=1.031029 px hand=82.695399 px (left)`

## Wrong stitches with poor trajectory fit

- `videos/identical_balls_trick_000_018.mp4 source=16 candidate=19 gap=2 fit=112.329997 px hand=54.036804 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=4 candidate=8 gap=4 fit=97.187035 px hand=43.604425 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=68 candidate=70 gap=8 fit=90.506115 px hand=12.945669 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=2 candidate=6 gap=4 fit=86.346332 px hand=8.064484 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=39 candidate=48 gap=9 fit=80.913163 px hand=111.706284 px (left)`

## Correct stitches with poor fit and an available wrist

- `videos/identical_balls_trick_000_018.mp4 source=7 candidate=10 gap=2 fit=65.083367 px hand=29.383404 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=4 candidate=7 gap=0 fit=62.446306 px hand=52.732355 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=73 candidate=75 gap=4 fit=57.704643 px hand=19.384163 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=63 candidate=65 gap=5 fit=54.875807 px hand=23.873959 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=11 candidate=13 gap=1 fit=45.812772 px hand=34.117568 px (right)`

## Correct poor-fit stitches closest to a wrist

- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=9 candidate=13 gap=5 fit=14.914964 px hand=0.729726 px (left)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=2 candidate=8 gap=5 fit=11.564336 px hand=1.290472 px (right)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=35 candidate=38 gap=2 fit=12.855921 px hand=1.896378 px (left)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=25 candidate=33 gap=0 fit=12.815928 px hand=2.477373 px (left)`
- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=1 candidate=9 gap=6 fit=16.577872 px hand=3.281262 px (left)`

## Wrong stitches with good trajectory fit

- `videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4 source=1 candidate=10 gap=9 fit=12.630490 px hand=31.938719 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=22 candidate=27 gap=5 fit=12.853832 px hand=5.125457 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=38 candidate=40 gap=10 fit=13.099916 px hand=32.390025 px (right)`
- `videos/identical_balls_trick_000_018.mp4 source=37 candidate=39 gap=6 fit=14.632402 px hand=35.696252 px (left)`
- `videos/identical_balls_trick_000_018.mp4 source=35 candidate=38 gap=5 fit=16.222763 px hand=18.710291 px (left)`

## Failure-mode question

The reviewed data is consistent with two overlapping regimes rather than a single hard rule: many wrong stitches have poor geometric fit, while some wrong stitches have good fit and some correct stitches have poor fit. The latter cases are candidates for hand-interaction or other occlusion-related review, but wrist proximity alone does not establish that explanation. No classifier or threshold was trained or selected.
