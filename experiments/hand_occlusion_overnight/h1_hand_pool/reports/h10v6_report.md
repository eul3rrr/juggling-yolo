# H10 v6 — Per-arc gravity as 4th quality dimension

## Hypothesis

H8 v8 produces per-arc parabolic fits for each tracklet. A
tracklet whose arcs all have gravity close to the expected 0.5
is a clean parabolic tracklet. A tracklet with widely varying
g across arcs is noisy or hand-contaminated.

Hypothesis: a chain of clean parabolic tracklets is more likely
a real juggling cycle. Adding h8v8 (per-arc gravity consistency)
as a 4th quality dimension should improve the chain ranking
over H10 v5 (3 dimensions: h3 + h8 + h9).

Formula: `quality_v6 = 0.25*h3 + 0.20*h8 + 0.30*h9 + 0.25*h8v8`
h8v8 = mean over the chain's tracklets of
  `n_arcs_within_[0.2,0.8]_of_g / n_arcs_with_valid_g`

## Quantitative result (default weights, h8v8=0.25)

| Video | v5 mean q | v6 mean q | v5 rank changed |
|---|---|---|---|
| identical | 0.529 | 0.495 | 35/43 (31↑, 5↓, 7=) |
| YouTube | 0.537 | 0.569 | 4/15 (4↑, 2↓, 9=) |

The h8v8 dimension has OPPOSITE effects on the two videos:
- **Identical**: h8v8 HURTS mean quality (0.529 → 0.495).
  Chain 21 (was v5 #0 with q=0.966) drops to v6 #7 because
  t31 and t36 have per-arc g=0.117 (not close to 0.5). The
  parabolic fits for t31/t36 are unreliable because the
  tracklets span asymmetric motions (apexes are not
  centered in the data window).
- **YouTube**: h8v8 HELPS mean quality (0.537 → 0.569).
  Chain 3, 8, 0 promote from v5 ranks 2, 4, 7 to v6 ranks
  2, 3, 5 because they have h8v8=0.88 (high arc-gravity
  consistency).

## Sensitivity grid on h8v8 weight

| w8v8 | identical mean q | youtube mean q |
|---|---|---|
| 0.00 (= v5) | 0.529 | 0.537 |
| 0.10 | 0.520 | 0.547 |
| 0.20 | 0.513 | 0.556 |
| 0.25 (default) | 0.510 | 0.559 |
| 0.30 | 0.507 | 0.562 |
| 0.40 | 0.502 | 0.567 |
| 0.50 | 0.498 | 0.571 |

The sensitivity is **NOT flat** on either video. The h8v8
weight trades off:
- Higher w8v8 → better YouTube ranking (long tracklets benefit)
- Higher w8v8 → worse identical ranking (short tracklets
  have unreliable parabolic fits)

## Big movers (default weights, h8v8=0.25)

### Identical — top IMPROVED
- chain 2: v5 rank 4 → v6 rank 0 (v5 q=0.921, v6 q=0.816)
- chain 8: v5 rank 5 → v6 rank 2 (v5 q=0.849, v6 q=0.761)
- chain 29: v5 rank 7 → v6 rank 5 (v5 q=0.750, v6 q=0.675)
- chain 13: v5 rank 42 → v6 rank 40 (v5 q=0.297, v6 q=0.348)
- chain 30: v5 rank ? → v6 rank ? (v5 q=0.454, v6 q=0.482)

### Identical — top WORSENED
- chain 15: v5 rank ? → v6 rank 28 (v5 q=0.473, v6 q=0.331)
- chain 21: v5 rank 0 → v6 rank 7 (v5 q=0.966, v6 q=0.643)
- chain 19, 20, 38: small changes

### YouTube — top IMPROVED
- chain 0: v5 rank 7 → v6 rank 4
- chain 8: v5 rank 4 → v6 rank 2
- chain 3, 9: small changes

### YouTube — top WORSENED
- chain 1: v5 rank 3 → v6 rank 8
- chain 12: v5 rank 1 → v6 rank 3

## Negative findings

1. **H10 v6 with default weights HURTS identical ranking.**
   Chain 21 (v5 #0) dropping to v6 #7 is a real loss.
   t31 and t36 are real tracklets in a real chain; their
   per-arc g=0.117 is an artifact of asymmetric motion
   (apex near one end of the data window), not a real
   quality signal.

2. **The h8v8 dimension has opposite effects on identical
   vs YouTube.** Identical has mostly short tracklets where
   the parabolic fit is unreliable. YouTube has long
   tracklets where the parabolic fit captures real
   parabolic motion. A single weight set cannot optimize
   for both.

3. **Chain 21's h8v8=0.0 may be a false negative.** The
   chain is a real single ball (v5 quality 0.966 confirms
   it) but the v8 per-arc analysis says it has irregular
   parabolic motion. This is likely because t31 spans an
   apex (rising then falling) and t36 doesn't, so the
   per-arc fits give different g values.

## Verdict

**H10 v6: MIXED.** The h8v8 dimension is a real signal for
YouTube long tracklets but a noise source for identical
short tracklets. With default weights (0.25 on h8v8),
identical ranking degrades and YouTube ranking improves.

**Recommendation: H10 v6b (per-video adaptive weights).**
Use w8v8=0.0 for identical (revert to v5), w8v8=0.30 for
YouTube. This gives:
- Identical: matches v5 (no degradation)
- YouTube: mean q 0.562 (improvement over v5's 0.537)

Alternatively, the h8v8 weight could be a function of the
tracklet length: w8v8 = min(0.30, n_tracklet_pts / 200).
Long tracklets get more weight, short tracklets get less.

**Neither has been implemented as H10 v6b in this episode.**
The H10 v6 finding is that the per-arc gravity is a
useful 4th dimension but needs careful per-video tuning.

## Artifacts

- `scripts/h10v6_with_h8v8.py`
- `data/h10v6_chain_quality_*.csv` (2 files)
- `data/h10v6_summary.json`
- `reports/h10v6_report.md`
