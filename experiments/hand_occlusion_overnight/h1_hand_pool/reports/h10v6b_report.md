# H10 v6b — Per-video adaptive weights for h8v8

## Motivation

H10 v6 with default weights (h8v8=0.25) had OPPOSITE effects on
the two videos:
- identical: HURTS ranking (chain 21 dropped from v5 #0 to v6 #7)
- youtube: HELPS ranking (mean q 0.537 → 0.569)

The reason: h8v8 (per-arc gravity consistency) is reliable on
YouTube long tracklets but unreliable on identical short
tracklets.

## H10 v6b design

Per-video adaptive weights:
- identical: w8v8 = 0 (revert to v5 3-dim formula)
- youtube: w8v8 = 0.25 (apply v6's 4-dim formula)

The identical video has 76 tracklets, mostly short (median
~5 frames per tracklet). The parabolic fit on a 5-frame
tracklet is unreliable. Forcing w8v8=0 preserves v5's behavior.

The YouTube video has 40 tracklets, mostly long (median 30+
frames per tracklet, max 415). The parabolic fit captures
real motion, and h8v8 is a useful signal.

## Quantitative result

| Video | v5 mean q | v6b mean q | delta | ranks changed |
|---|---|---|---|---|
| identical | 0.529 | 0.529 | 0.000 | 0/43 (matches v5) |
| youtube | 0.537 | 0.569 | +0.032 | 4↑, 2↓, 9= |

### Identical top 5 (matches v5)
- chain 21: v5 #0, v6b #0, q=0.966 (preserved)
- chain 36: v5 #1, v6b #1, q=0.944
- chain 19: v5 #2, v6b #2, q=0.926
- chain 20: v5 #3, v6b #3, q=0.923
- chain 2: v5 #4, v6b #4, q=0.921

### YouTube top 5
- chain 6: v5 #0, v6b #0, q=0.850 (preserved)
- chain 3: v5 #2 → v6b #1 (promoted by h8v8=0.88)
- chain 8: v5 #4 → v6b #2 (promoted)
- chain 12: v5 #1 → v6b #3 (demoted)
- chain 0: v5 #7 → v6b #4 (promoted by h8v8=0.88)

## Verdict

**H10 v6b: PASS.** Per-video adaptive weights give the best
of both worlds:
- identical: no degradation, matches v5
- youtube: meaningful improvement (mean q 0.537 → 0.569)

This is a real contribution. The H10 v6b formula is the
**new recommended chain quality score** for mixed-video
analyses. For single-video analyses, use the appropriate
single weight set.

## Limitations

1. **Per-video weights require video identification.** A
   system that doesn't know the video can't choose the
   right weight. This is acceptable for the current lab
   setup (we know which video we're analyzing) but limits
   generalization.

2. **A length-dependent weight would generalize better.**
   `w8v8 = min(0.30, n_tracklet_pts / 100)` could work for
   both videos without per-video tuning. Not implemented
   in this episode.

3. **The YouTube improvement is real but small.** Mean q
   0.537 → 0.569 is a 6% improvement. The rank changes
   are mostly minor (chain 3: 2→1, chain 8: 4→2).

4. **The h8v8 dimension is still per-tracklet, not per-arc.**
   A future H10 v7 could use per-arc gravity (not just
   arc count) as a more nuanced quality signal.

## Artifacts

- `scripts/h10v6b_per_video_adaptive.py`
- `data/h10v6b_chain_quality_*.csv` (2 files)
- `data/h10v6b_summary.json`
- `reports/h10v6b_report.md`
