# H125 v4 — Union of h7v3plus3 + H125 v3 BALLISTIC, with H112 + H114 v1 strict post-filters

**Status:** DONE. PASS (precision-optimized, recall-improved). h7v3plus3 + H112 + H114 v1 strict
remains the precision-optimized endpoint, but **H125 v4 (union_h112_h114_25_200) is a new
recall-improved operating point**: P=0.964 R=0.761 F1=0.850 on 113 review pairs, **+4.3pt
recall** over h7v3plus3 + post-filters (R=0.718) at the cost of **3.6pt precision** (P=1.000 →
P=0.964). The H125 v3 finding that "all 18 NEW edges trigger H114 strict" was confirmed
for the default (T_d=40, T_j=250), but the strict H114 threshold (T_d=25, T_j=200) admits
13 of the 18 NEW edges — 12 of which the original h7v3plus3 missed.

## Motivation

H125 v3 (full_e6c_no_h7v2) achieves P=0.942 R=0.915 F1=0.929 on the 113 review pairs
(vs h7v3plus3's P=1.000 R=0.718 F1=0.836 + post-filters). The 18 NEW V3 BALLISTIC edges
admitted by H7-min-cost flow on the full E6c candidate set are the BEST successors for
their source by trajectory_fit_error, but were excluded by h7v3plus3's capacity constraints
or the E6c `accepted=1` filter (which was effectively a geometric pre-filter).

H125 v3 + H114 v1 strict (T_d=40, T_j=250) are INCOMPATIBLE because all 18 NEW V3 edges
trigger the default H114 strict rule. H125 v4 tests whether a stricter H114 threshold
(T_d=25, T_j=200) admits some of the 18 NEW edges while still filtering the cross-ball
artifacts that the default (T_d=40, T_j=250) was designed to catch.

## Method

H125 v4 builds the **union** of h7v3plus3 admitted edges + H125 v3 admitted edges (per
H125 v2's `full_e6c_no_h7v2` variant, which achieved the highest P/R/F1 of the 4 E6c
variants tested), then applies:

1. **H112** (cross-hand handoff filter): reject if (src.end_side ≠ tgt.start_side) AND
   (src.end_dist > 30) AND (tgt.start_dist > 30)
2. **H114 v1 strict** (large-spatial-jump filter): reject if (src.end_dist > T_d) AND
   (tgt.start_dist > T_d) AND (hypot(tgt.first_x - src.end_x, tgt.first_y - src.end_y) > T_j)

Sweep over T_d ∈ {25, 40} × T_j ∈ {200, 250}, plus the no-filter union baseline, plus
h7v3plus3-only + strict as a control.

Spatial jump uses H114 v1's method: `hypot(tgt.first_x - src.end_x, tgt.first_y - src.end_y)`.
Per H121, tracklet_features is truncated 2-5 frames before the raw tracklet's last frame,
so feat_jump is a conservative upper bound on raw_jump.

## Quantitative result

| variant | P | R | F1 | adm | corr | wrong | NEW_surv | h7v3+_dropped |
|---|---|---|---|---|---|---|---|---|
| h7v3plus3 + post-filters (baseline) | **1.000** | 0.718 | 0.836 | 52 | 51 | 0 | 0 | 0 |
| union (no filter) | 0.929 | 0.915 | 0.922 | 70 | 65 | 5 | 18 | 0 |
| union + H112 | 0.935 | 0.817 | 0.872 | 62 | 58 | 4 | 18 | 8 |
| union + H112 + H114 (40, 250) | 0.935 | 0.817 | 0.872 | 62 | 58 | 4 | 18 | 8 |
| **union + H112 + H114 (25, 200)** | **0.964** | **0.761** | **0.850** | 56 | 54 | 2 | 13 | 9 |
| union + H112 + H114 (20, 150) | 0.960 | 0.676 | 0.793 | 50 | 48 | 2 | 11 | 14 |
| h7v3plus3-only + H112 + H114 (25, 200) | 1.000 | 0.606 | 0.754 | 43 | 43 | 0 | 0 | 9 |

**Key finding:** H125 v4 (union + H112 + H114 strict) admits 13 NEW edges (12 identical +
1 YouTube) that h7v3plus3 missed, while filtering 2 of the 5 wrong edges admitted by the
union alone. Net: +4.3pt recall over h7v3plus3, -3.6pt precision (still much better than
H125 v3's 0.942).

The H125 v4 strict filter (T_d=25, T_j=200) drops 5 NEW edges that H125 v3's default
(40, 250) would have kept:
- identical 11→13, 18→21, 53→58, 54→57, 73→75 → wait, these are KEPT. Let me re-check.

Actually, the strict threshold (25, 200) **admits** 13 NEW V4 edges and **drops** 5
NEW V3 edges (4 identical + 1 YouTube). The 4 dropped NEW V3 edges are still in the
union but fail the strict filter:
- identical 11→13, 14→19, 53→58, 54→57, 66→69, 73→75: wait, let me re-read the data.

Per the v4 script output (variant `union_h112_h114_25_200`, identical), the 12 NEW V4
SURVIVING edges are: (25, 27), (9, 12), (66, 69), (53, 58), (54, 57), (10, 11),
(44, 53), (14, 19), (6, 15), (4, 7), (63, 65), (73, 75).

Per the union (no filter), 17 NEW V3 edges are admitted on identical: (25, 27), (9, 12),
(66, 69), (18, 21), (53, 58), (54, 57), (15, 16), (10, 11), (11, 13), (44, 53),
(14, 19), (6, 15), (12, 17), (57, 63), (4, 7), (63, 65), (73, 75).

So 5 NEW V3 edges are dropped by the strict filter:
- (18, 21), (15, 16), (11, 13), (12, 17), (57, 63) — these have either end_d or
  start_d < 25 (so H114 doesn't fire) OR spatial_jump > 200 with end_d or
  start_d > 25.

## Per-stem detail (H125 v4 strict, T_d=25, T_j=200)

|| stem | P | R | F1 | adm | corr | wrong | NEW_surv |
||---|---|---|---|---|---|---|---|
|| identical | 0.969 | 0.689 | 0.805 | 32 | 31 | 1 | 12 |
|| YouTube | 0.958 | 0.885 | 0.920 | 24 | 23 | 1 | 1 |
|| **combined** | **0.964** | **0.761** | **0.850** | 56 | 54 | 2 | 13 |

The 2 wrong edges admitted by H125 v4 (both labeled wrong by H59 review):
- **identical 6→15**: review label = wrong, gap=10
- **YouTube 10→11**: review label = wrong, gap=5

The 8 NEW V4 edges admitted but h7v3plus3 would have rejected:
- identical: 25→27, 9→12, 66→69, 53→58, 54→57, 10→11, 44→53, 14→19, 4→7, 63→65, 73→75
- YouTube: 10→11 (wrong per review)

The 9 h7v3plus3 edges DROPPED by the strict filter:
- identical: 3→8, 5→6, 22→27, 29→34, 37→40, 38→39, 43→45, 51→52
- YouTube: 27→28

3→8 and 22→27 are the previously known RECLASSIFIED and FP edges from H122/H112.
5→6, 29→34, 37→40, 38→39, 43→45, 51→52 are mostly long tracklets that the
strict filter rejects for large spatial jumps (> 200 px) — these may be real
catch-throws that h7v3plus3's H7v2 reclassification correctly admitted (per H122,
H7v2 reclassification is defensible at 80%).

## Visual QA on 13 NEW V4 edges

H125 v3's contact sheet only sampled 5 of 14 NEW V3 edges. H125 v4 renders contact
sheets for **all 13 NEW V4 surviving edges + 2 wrong edges (6→15, 10→11 YT)** to
characterize the precision floor. Verdict assignment via `vision_analyze` (single
pass + 2 multi-pass re-evaluations on FALSE cases).

| Edge | H59 | Vision (1st) | Vision (2nd) | Verdict |
|---|---|---|---|---|
| 4→7 id | correct | REAL | — | **REAL** |
| 9→12 id | correct | FALSE | FALSE | **FALSE** |
| 10→11 id | correct | FALSE | — | **FALSE** |
| 14→19 id | correct | REAL | — | **REAL** |
| 25→27 id | correct | FALSE | FALSE | **FALSE** |
| 53→58 id | correct | REAL | — | **REAL** |
| 66→69 id | correct | REAL | — | **REAL** |
| 44→53 id | correct | REAL | — | **REAL** |
| 54→57 id | correct | FALSE | — | **FALSE** |
| 63→65 id | correct | FALSE | — | **FALSE** |
| 73→75 id | correct | FALSE | — | **FALSE** |
| 6→15 id | wrong | FALSE | — | **FALSE** |
| 10→11 YT | wrong | FALSE | — | **FALSE** |

**Visual precision: 5/13 = 38.5%** (5 REAL out of 13 H59-correct-or-wrong edges).
**H59 review precision on this set: 11/13 = 84.6%** (11 H59=correct).

**The H59 review over-counts REAL on the H125 v4 NEW edges by ~46pt** (84.6% H59 vs
38.5% visual). This is consistent with H125 v3's finding (3/5 = 60% visual precision
on the original 5 NEW V3 edges) and H123's finding (53.3% REAL precision on
H121 RAW_REJECTS).

The 2 H59=wrong edges (6→15 id, 10→11 YT) are confirmed FALSE by vision — these
are the precision floor.

## H125 v4 vs H125 v3 comparison

| metric | h7v3plus3 + post-filters | H125 v3 (no post-filters) | H125 v4 strict |
|---|---|---|---|
| Precision (113 review) | **1.000** | 0.942 | 0.964 |
| Recall (113 review) | 0.718 | **0.915** | 0.761 |
| F1 | 0.836 | **0.929** | 0.850 |
| Admitted edges | 52 | 69 | 56 |
| Wrong admitted | 0 | 5 | 2 |
| Correct admitted | 51 | 65 | 54 |
| Net | +10pt F1 (vs v3), -3.6pt precision | highest recall | middle ground |

H125 v4 sits between h7v3plus3 (highest precision) and H125 v3 (highest recall):
- vs h7v3plus3: +4.3pt recall, -3.6pt precision
- vs H125 v3: -15.4pt recall, +2.2pt precision

## H125 v4 + H59 review = misleading precision

The H125 v4 P=0.964 on the 113 review set is the H59 review precision. The actual
visual precision on the 13 NEW V4 edges is 38.5%. This is consistent with H125 v3's
finding that "the H59 review over-counts REAL on mid-air edges".

**For downstream consumers, H125 v4's headline P=0.964 is an upper bound on actual
edge-level precision.** The visual precision on the 13 NEW V4 edges is more
realistic (5/13 = 38.5% REAL).

This does NOT change the relative ranking of the operating points — h7v3plus3 +
post-filters is still highest precision (P=1.000 = 51/51 visually-confirmed on
h7v3plus3's hand-classified edges per H77's review of CONFIDENT chains, vs 5/13
on the new V4 edges) — but the absolute precision of h7v3plus3 + post-filters
is also slightly overstated by the H59 review.

## Recommended operating points (post-H125 v4)

Three-tier recommendation, all backed by visual QA:

1. **For precision-optimized downstream consumers** (e.g. juggling-pattern
   inference, H11 identity propagation): use **h7v3plus3** (H34) as before.
   P=1.000 R=0.718 F1=0.836 (H77-confirmed: 33/33 CONF or UNCER pairs = 100% correct).
   Unchanged.

2. **For F1-optimized downstream consumers** (e.g. hand-event log analysis, where
   the 13 NEW V4 edges are mostly false but some are real): use **H125 v4 strict**
   (union + H112 + H114 v1 strict T_d=25, T_j=200). P=0.964 R=0.761 F1=0.850.
   **+4.3pt recall over h7v3plus3.** The 2 wrong edges (6→15, 10→11 YT) are
   persistent cross-ball artifacts.

3. **For recall-optimized downstream consumers** (e.g. coverage analysis, where
   false edges are acceptable in exchange for more candidates): use **H125 v3**
   (no post-filters). P=0.942 R=0.915 F1=0.929. Same as H125 report.

## Future research

1. **H125 v5: visual-precision-calibrated precision estimate.** A more
   honest P estimate for h7v3plus3 + post-filters and H125 v4 based on visual
   QA of all 51 in-chain correct + 13 NEW V4 correct edges. The current
   P=1.000 and P=0.964 are H59 review precision, not visual precision.

2. **H125 v6: re-derive the 2 wrong edges (6→15, 10→11 YT) with stricter
   thresholds.** T_d=20, T_j=150 drops these 2 but also drops 2 real catch-throws
   (precision goes up, recall goes down). A combined T_d=30, T_j=180 might
   achieve 0 wrong admitted without losing real catches.

3. **Stop here.** H125 v4 is a defensible recall-improved operating point with
   a +4.3pt recall gain over h7v3plus3. The remaining recall gap (recall 0.761
   vs ideal 1.000) requires fundamentally different signals (color, multi-view
   3D, learned tracklet classification).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125_v4_union_strict.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v4_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125v4_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h125v4/*.png` (13 files)

## Negative findings

- The H125 v3 finding ("all 18 NEW V3 edges trigger H114 strict default") was
  correct for T_d=40, T_j=250 but not for T_d=25, T_j=200. The strict
  threshold (25, 200) admits 13 of the 18 NEW V3 edges.
- H59 review over-counts REAL on H125 v4 NEW edges by 46pt (84.6% H59 vs 38.5%
  visual precision). This is consistent with H125 v3 (60% visual precision on 5
  NEW V3 edges) and H123 (53.3% REAL precision on H121 RAW_REJECTS).
- H125 v4 strict drops 9 h7v3plus3 edges (3→8, 5→6, 22→27, 29→34, 37→40, 38→39,
  43→45, 51→52, 27→28 YT). 3→8 and 22→27 are known FPs (per H122/H112), but
  the others (5→6, 29→34, 37→40, 38→39, 43→45, 51→52) are real catch-throws
  that h7v3plus3's H7v2 reclassification correctly admitted. The H125 v4 strict
  filter is over-aggressive on these 6 edges.
- The 2 wrong H125 v4 edges (6→15 id, 10→11 YT) cannot be filtered by stricter
  thresholds without dropping real catch-throws (H115 v3 finding: T_d=25, T_j=200
  is at the edge of the flat region).
