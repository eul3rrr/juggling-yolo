# H10 v7 — Length-dependent weight for h8v8

## Hypothesis

H10 v6b uses per-video adaptive weights. This requires knowing
which video is being analyzed. A length-dependent weight would
generalize: w8v8 = min(0.30, mean(n_tracklet_pts) / 200).

Rationale: long tracklets have more arcs and the parabolic
fit is more reliable, so h8v8 should be weighted more.
Short tracklets have fewer arcs and the parabolic fit is
unreliable, so h8v8 should be weighted less.

## Quantitative result

| Video | mean tracklet length | mean w8v8 applied | v5 mean q | v7 mean q | delta |
|---|---|---|---|---|---|
| identical | 36.5 | ~0.18 | 0.529 | 0.509 | -0.020 |
| youtube | 108.5 | ~0.30 | 0.537 | 0.557 | +0.021 |

### Identical top 5 (v7)
- chain 2: v5 #4 → v7 #0 (promoted, w8v8=0.22 from len=44)
- chain 36: v5 #1 → v7 #1 (preserved)
- chain 8: v5 #5 → v7 #2 (promoted)
- chain 20: v5 #3 → v7 #3 (preserved)
- chain 19: v5 #2 → v7 #4 (demoted)

### YouTube top 5 (v7)
- chain 6: v5 #0 → v7 #0 (preserved, w8v8=0.30 from len=92)
- chain 12: v5 #1 → v7 #1 (preserved)
- chain 3: v5 #2 → v7 #2 (preserved, w8v8=0.30 from len=223)
- chain 8: v5 #4 → v7 #3 (promoted)
- chain 0: v5 #7 → v7 #4 (promoted)

## Comparison to v6b

| Video | v5 | v6b | v7 |
|---|---|---|---|
| identical | 0.529 | 0.529 (matches v5) | 0.509 |
| youtube | 0.537 | 0.569 | 0.557 |

H10 v7 is WORSE than v6b on both videos:
- identical: v7 is -0.020 worse than v5 (v6b is 0.000 worse)
- youtube: v7 is +0.021 better than v5 (v6b is +0.032 better)

The reason: v7's w8v8 = min(0.30, n/200) gives w8v8 > 0 even
for short tracklets (e.g., n=20 gives w8v8=0.10). This still
introduces the per-arc gravity noise on identical, just less
than the v6 default. v6b's hard cutoff (w8v8=0 for identical)
avoids the noise entirely.

## Negative findings

1. **Length-dependent weight is worse than per-video fixed
   weight.** v7's w8v8 ranges from 0.10 to 0.30 on identical
   (still has h8v8 noise for short tracklets) and is
   uniformly 0.30 on YouTube (same as v6b). The v7 result
   is a weighted average of v5 and v6 behaviors, not an
   improvement on either.

2. **The LENGTH_DIVISOR=200 choice is somewhat arbitrary.**
   Smaller divisor (e.g., 100) would give higher w8v8 for
   shorter tracklets, increasing the noise. Larger
   divisor (e.g., 400) would decrease w8v8 for YouTube,
   reducing the benefit. Not investigated.

3. **The v7 formula is more complex than v6b without
   being better.** v6b's per-video fixed weights are
   simpler and more accurate. v7 is a generalization
   attempt that didn't work.

## Verdict

**H10 v7: NEGATIVE.** Length-dependent weight is a
natural generalization of v6b's per-video weights, but
it doesn't outperform v6b. The v7 formula has
intermediate behavior between v5 (no h8v8) and v6
(full h8v8), which is worse than either extreme.

**H10 v6b remains the recommended operating point** for
mixed-video analyses.

## Lessons

1. **Per-video fixed weights are hard to beat with
   length-dependent formulas.** The "right" w8v8 is a
   step function of video (0 for identical, 0.25 for
   YouTube), not a smooth function of tracklet length.

2. **Smoothing a step function doesn't help.** v7
   smooths the v6b step function but loses the
   sharpness of the step.

3. **The h8v8 signal is binary at the tracklet level.**
   Either a tracklet is long enough for the parabolic
   fit to be reliable (length > 50-100 frames), or
   it isn't. There's no meaningful "in between".

## Artifacts

- `scripts/h10v7_length_dependent.py`
- `data/h10v7_chain_quality_*.csv` (2 files)
- `data/h10v7_summary.json`
- `reports/h10v7_report.md`
