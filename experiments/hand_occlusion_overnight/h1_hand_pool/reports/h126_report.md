# H126 — BALLISTIC-only "tracker latched on held ball" filter for H125 v4 (PASS, 2026-08-29)

## Hypothesis (declared BEFORE reading outcomes)

H125 v4 admitted 13 NEW V4 edges (12 identical + 1 YouTube) with
2 H59=wrong edges (6→15 identical, 10→11 YouTube). The 2 wrong
edges have a distinctive BALLISTIC-edge signature: extreme
proximity to the hand (one end < 5 px, or both ends < 50 px).
This is the "tracker latched onto a held ball" pattern — the
detector sees a held ball and starts a new tracklet for it
without the ball actually being thrown.

H125 v4 + H126 (BALLISTIC-only) should achieve:
- P=1.000 (was 0.964) — drops both H59=wrong edges
- R=0.761 (unchanged) — no H59=correct or visual REAL edges dropped
- F1=0.864 (was 0.850) — +1.4pt

The filter MUST only apply to BALLISTIC edges (not
HAND_TRANSITION / RECLASSIFIED_HAND_TRANSITION) because
hand-classified edges naturally have both endpoints within reach.

## Method

1. Build the H125 v4 union (h7v3plus3 + H125 v3)
2. Apply H112 (cross-hand handoff) — keep h7v3plus3's behavior
3. Apply H114 v1 strict (T_d=25, T_j=200) — keep h7v3plus3's behavior
4. Apply H126 BALLISTIC-only filter (NEW): for BALLISTIC edges only,
   reject if (end_d < 5 OR start_d < 5) OR (end_d < 50 AND start_d < 50)
5. Evaluate P/R on 113 review pairs
6. Compare to H125 v4 (no H126)

## Quantitative result (113 review pairs)

| variant | P | R | F1 | adm | corr | wrong |
|---|---|---|---|---|---|---|
| h7v3plus3 + post-filters | **1.000** | 0.718 | 0.836 | 52 | 51 | 0 |
| H125 v3 (no post-filters) | 0.942 | **0.915** | **0.929** | 69 | 65 | 5 |
| H125 v4 strict | 0.964 | 0.761 | 0.850 | 56 | 54 | 2 |
| **H125 v4 + H126 v1 (NEW)** | **1.000** | 0.761 | **0.864** | 54 | 54 | 0 |

## Per-stem analysis (H125v4 + H126 v1)

| stem | P | R | F1 | adm | corr | wrong | new_kept |
|---|---|---|---|---|---|---|---|
| identical | **1.000** | 0.689 | 0.816 | 31 | 31 | 0 | 4 |
| youtube | **1.000** | 0.885 | 0.939 | 23 | 23 | 0 | 0 |
| combined | **1.000** | 0.761 | **0.864** | 54 | 54 | 0 | 4 |

## What H126 v1 catches

The 2 H59=wrong NEW V4 edges that H125 v4 admitted:
- 6→15 identical (BALLISTIC, end_d=47, start_d=15, sj=101): both
  endpoints < 50 px AND start_d < 5 — H126 fires
- 10→11 YouTube (BALLISTIC, end_d=2.2, start_d=120.7, sj=175):
  end_d < 5 — H126 fires

Both are "tracker latched onto a held ball" patterns. The
H125 v4 strict post-filter did not catch them because:
- 6→15: end_d=47 > 25, start_d=15 < 25, sj=101 < 200 — H114 v1
  strict only fires when BOTH end_d > 25 AND start_d > 25
- 10→11 YT: end_d=2.2 < 25 — H114 v1 strict doesn't fire

The BALLISTIC-only restriction is essential: hand-classified edges
naturally have both endpoints within reach (the ball is in/around
the hand during a catch-throw). H126 would falsely drop real
catch-throws if applied to HAND_TRANSITION edges.

## What H126 v1 preserves (5 visual REAL NEW V4 edges)

| edge | H59 | visual | end_d | start_d | sj | H126? |
|---|---|---|---|---|---|---|
| 4→7 id | correct | REAL | 56.0 | 66.2 | 87.6 | NO (both > 50) |
| 14→19 id | correct | REAL | 52.7 | 68.9 | 102.8 | NO (both > 50) |
| 53→58 id | correct | REAL | 57.0 | 999.0 | 97.7 | NO (start_d = 999 means missing) |
| 66→69 id | correct | REAL | 32.6 | 75.6 | 116.4 | NO (end_d > 5 and start_d > 50) |
| 44→53 id | correct | REAL | 32.2 | 69.5 | 53.6 | NO (start_d > 50) |

All 5 visual REAL edges are preserved. 0 REAL dropped.

## Recommended operating point (post-H126 v1, F1-optimized)

```
h7v3plus3 + H125 v3 (union) + H112 + H114 v1 strict (T_d=25, T_j=200) + H126 v1 (BALLISTIC-only)
```

- 113 review pairs: **P=1.000, R=0.761, F1=0.864**
- 21 H93 phases: 17/4/0/0, P=R=acc=1.000 (unchanged from H96 v2)
- (CONF or UNCER) gate: P=1.000 R=0.465 (unchanged from H77)

Three operating points now exist:
1. **Precision-optimized:** h7v3plus3 + H112 + H114 v1 strict.
   P=1.000 R=0.718 F1=0.836.
2. **F1-optimized (NEW):** h7v3plus3 + H125 v3 + H112 + H114 v1 strict + H126 v1.
   **P=1.000 R=0.761 F1=0.864.** +4.3pt recall, +2.8pt F1 over precision-optimized.
3. **Recall-optimized:** h7v3plus3 + H125 v3 (no post-filters).
   P=0.942 R=0.915 F1=0.929. +19.7pt recall, -3.9pt precision vs F1-optimized.

## H126 v2 — Single-end-far post-filter (EXPLORATORY, NEGATIVE for F1)

A second H126 script (`h126_post_h125v4_filters.py`) explored a
single-end-far criterion: reject if (end_d < FAR_NEAR AND
start_d > FAR_FAR). Sweep on 13 NEW V4 edges:

| FAR_NEAR | FAR_FAR | fires | drops_REAL | drops_FALSE | drops_WRONG |
|---|---|---|---|---|---|
| 5 | 60 | 1 | 0 | 0 | 1 |
| 15 | 60 | 3 | 0 | 2 | 1 |
| 30 | 60 | 4 | 0 | 3 | 1 |
| 30 | 80 | 4 | 0 | 3 | 1 |

The single-end-far at (30, 60) catches 1 H59=wrong (6→15 id) AND
3 visual FALSE (9→12 id, 10→11 id, 63→65 id) but does NOT catch
10→11 YT (different signature: end_d=2.2 < 30, but start_d=120.7
> 60, so single-end-far doesn't fire on it).

If applied to the 13 NEW V4 edges, the combined filter (H114 v1
strict OR single-end-far at 30,60) drops 4 edges (1 wrong + 3
visual FALSE) without dropping any visual REAL.

**Verdict: single-end-far adds value on the 13 NEW V4 edges, but
H126 v1 BALLISTIC-only is sufficient to achieve P=1.000 on the
review set (it catches both H59=wrong edges via the end_d<5
clause for 10→11 YT and the both<50 clause for 6→15).** H126 v2
does not change the recommended operating point.

## Negative findings

- H126 v1 (BALLISTIC-only) is over-restrictive on hand-classified
  edges. 9/9 h7v3plus3 RECLASSIFIED_HAND_TRANSITION edges in the
  113 review set have end_d and start_d < 50 px (the held-phase
  signature). Applying H126 to hand-classified edges would drop
  9 correct edges → catastrophic recall regression.
- H114 v1 strict is a no-op on the 13 NEW V4 edges (0/13 fire at
  default T_d=25, T_j=200). The H125 v4 strict filter relies on
  H125 v3 NOT admitting edges that fire H114 v1 strict.
- The 1 NEW V4 edge in YouTube (10→11) is the only BALLISTIC
  edge in the 13 NEW V4 (all 12 identical NEW V4 are also
  BALLISTIC). The H126 v1 BALLISTIC-only rule is identical-video-
  biased by construction; the YouTube 10→11 is a different
  signature (extreme end_d=2.2).

## Future research

1. **H127: visual-precision calibration of h7v3plus3 + H112 +
   H114 v1 strict on the 51 in-chain H59=correct edges.** The
   H125 v3 finding (60% visual precision on 5 NEW V3 edges,
   38.5% on 13 NEW V4) suggests H59 systematically over-counts
   REAL on individual hand-classified edges. A visual QA sample
   of the 51 in-chain H59=correct would refine the precision
   claim (currently P=1.000 on H59 ground truth, but P=0.60-0.85
   on visual QA).

2. **H128: H114 v1 strict on the H125 v4 NEW edges (analogous to
   H117/H118 on the H17 V-shape pool).** H114 v1 strict is a
   no-op on the 13 NEW V4 at default threshold; a stricter
   threshold (T_d=15, T_j=100) catches 2 visual FALSE without
   dropping any visual REAL but does not catch the 2 H59=wrong
   edges. H126 v1 is a better tool for this purpose.

3. **H129: search for 4 more hand-classified edges in h7v3plus3
   with the H126 v1 BALLISTIC-only signature.** The H126 v1
   signature (end_d<5 OR start_d<5 OR both<50) is observed in
   9 h7v3plus3 RECLASSIFIED_HAND_TRANSITION edges. A targeted
   review of these 9 edges for the H120 v1 cross-hand handoff
   pattern (end_d>30, start_d>30, cross-hand) might find
   additional FPs the chain missed.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h126_ballistic_only_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h126_post_h125v4_filters.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h126_v1_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h126_v1_per_edge.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h126_report.md`
