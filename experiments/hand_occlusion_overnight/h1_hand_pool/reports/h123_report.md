# H123 — Enlarged Visual QA of H121 RAW_REJECTS

**Date:** 2026-08-29 (this episode)
**Status:** **NEGATIVE REFINEMENT** of H122. The H122 80% REAL precision
estimate is REVISED DOWN to 53.3% on a stratified 15-case sample
(Wilson 95% CI: [30.1%, 75.2%]). H7v2 reclassification is **over-applied
at roughly 50% rate** in the YouTube-heavy RAW_REJECTS pool, and the
H112/H114 v1 strict geometric post-filters only catch 1/6 of the false
positives (the 22→27 case).

## Motivation

H122's 5-case visual QA found 4/5 (80%) REAL catch-throws and concluded
H7v2 reclassification is "defensible at 80%". However, the H122 sample
was selected for *diverse structural signatures* (very large feat/raw
disagreements), which may have biased toward the most informative cases.
H121 had 26 RAW_REJECTS total (5 H122-sampled, 21 un-sampled).

H122's "Future research" section explicitly recommended:
> "Larger visual QA sample. 5/26 RAW_REJECTS is a small sample. Visual
> QA on 10-15 more would tighten the 80% real-catch-throw bound."

H123 implements this recommendation with a stratified sample covering
diverse signatures.

## Hypothesis (declared before reading outcomes)

The H122 80% precision is real OR a biased estimate. A stratified sample
of 10 more RAW_REJECTS should resolve this:
- If H122 is correct: 10/10 stratified cases give ~80% REAL precision
- If H122 is biased: the stratified sample gives a substantially lower
  REAL precision (e.g., 40-50%)

## Method (declared)

Stratified sample of 10 RAW_REJECTS (2 identical + 8 YouTube) covering
diverse structural signatures:

- 40→41 identical (n_pts=33, raw_end_slope=-0.31 stationary): the only
  longer identical RAW_REJECTS
- 43→45 identical (n_pts=2, very short): the shortest RAW_REJECTS
- 2→8 YouTube: high raw_end_dist (54.8) and high sj_raw (121.2)
- 3→6 YouTube: small sj_raw (49.0), medium raw_end_dist (31.6)
- 9→13 YouTube: high raw_end_dist (66.9) and high sj_raw (119.8)
- 14→17 YouTube: only RAW_REJECTS with raw_end_slope negative (-0.21)
- 22→26 YouTube: medium sj_raw (112.3), large feat→raw dist jump
- 26→31 YouTube: largest sj_raw (152.1)
- 30→37 YouTube: small sj_raw (81.3), high feat_n_pts (119)
- 33→36 YouTube: small sj_raw (62.5), high feat_end_dist (24.95, at threshold)

Render 10 contact sheets using the H122 approach (raw trajectory +
feat-end vs raw-end markers + gray/magenta jump lines). Visual QA via
`vision_analyze` (1 question per case, 3 sub-questions).

## Per-case verdicts

| Edge | Stem | feat_jump | raw_jump | feat_slope | raw_slope | Selection rationale | Verdict |
|---|---|---|---|---|---|---|---|
| 40→41 | identical | 2.3 | 3.3 | -1.39 | -0.31 | longer identical, stationary at end | **REAL** |
| 43→45 | identical | 10.2 | 8.5 | n/a | -0.36 | shortest RAW_REJECTS, signature is noise | **TRACKER_ARTIFACT** |
| 2→8 | YouTube | 88.8 | 121.2 | 0.92 | 6.89 | high raw_d 54.8, high sj_raw 121.2 | **TRACKER_ARTIFACT** |
| 3→6 | YouTube | 47.8 | 49.0 | 0.95 | 10.04 | small sj_raw 49.0 | **REAL** |
| 9→13 | YouTube | 78.1 | 119.8 | 1.75 | 8.65 | high raw_d 66.9, high sj_raw 119.8 | **TRACKER_ARTIFACT** |
| 14→17 | YouTube | 85.0 | 83.8 | 2.15 | -0.21 | only negative raw_end_slope | **REAL** |
| 22→26 | YouTube | 80.8 | 112.3 | -0.29 | 7.32 | medium sj_raw 112.3 | **TRACKER_ARTIFACT** |
| 26→31 | YouTube | 119.9 | 152.1 | 0.94 | 6.49 | largest sj_raw 152.1 | **UNCERTAIN** |
| 30→37 | YouTube | 57.0 | 81.3 | 1.09 | 6.74 | small sj_raw 81.3, long source (119 pts) | **REAL** |
| 33→36 | YouTube | 50.1 | 62.5 | 2.94 | 7.83 | small sj_raw 62.5, high feat_end_dist 24.95 | **TRACKER_ARTIFACT** |

## Visual QA details

### 40→41 identical — REAL_CATCH_THROW

Vision verdict: "VERDICT: REAL_CATCH_THROW". The source tracklet is a
monotonic rising arc that ends stationary at the hand (raw_end_slope=-0.31,
"stationary at end"). The feat_end_slope=-1.39 is the legitimate H7v2
catch signal; the source trajectory shape (rising then terminating at
hand) is consistent with a real catch.

This is the H122 pattern: source tracklet contains a complete catch
event, the "edge" to tracklet 41 is a secondary continuation.

### 43→45 identical — TRACKER_ARTIFACT

Vision verdict: "VERDICT: TRACKER_ARTIFACT". The source tracklet has
only 2 raw points (frames 621, 622) and a raw slope of -0.36 — well
below the H7v2 catch threshold of -1.0. The V-shape visible in the
plot is formed by the *target* tracklet (45) ascending and curving
back, not the source (43). The catch/throw signature in the
2-point source is noise.

The 22→27 case has a similar profile: very short source tracklet
makes the catch/throw signature noisy. H7v2's reclassification
catches a real catch in some 2-pt sources (e.g., 5→6, 38→39) but
fails in others (e.g., 43→45, 22→27).

### 2→8 YouTube — TRACKER_ARTIFACT

Vision verdict: "VERDICT: TRACKER_ARTIFACT". The source's raw last
frame is well below the feat-end, and the raw slope (+6.89) is
strongly ascending away from the hand. The 121.2-px raw jump
indicates the source ball is moving upward away from one hand while
the target ball starts near a different position — inconsistent with
a single ball's catch-throw.

### 3→6 YouTube — REAL_CATCH_THROW

Vision verdict: "VERDICT: REAL_CATCH_THROW". The source is a clean
monotonic descent ending near the hand, the target is a clean upward
arc from the hand, and the 49-px spatial jump across 12 frames is
physically plausible for a hand-position change between consecutive
juggling throws. This is a genuine catch-throw that H7v2
reclassification correctly identifies.

### 9→13 YouTube — TRACKER_ARTIFACT

Vision verdict: "VERDICT: TRACKER_ARTIFACT". The raw endpoint is at the
bottom of the plot, well below the source start, and the raw slope
(+8.65) indicates post-throw ascending. The 119.8-px raw jump and the
ascent direction indicate the raw tracker drifted away from the true
ball position near the hand.

### 14→17 YouTube — REAL_CATCH_THROW

Vision verdict: "VERDICT: REAL_CATCH_THROW". The source trajectory
forms a complete V-shape (descending from f=308, reaching minimum
near f=375, beginning ascent at f=379). The V is contained within
frames 308-379, indicating the ball was caught and immediately
re-thrown within a single tracker identity. The 6-frame gap and
~84-px jump are consistent with a continuous catch-throw.

This case is unique: it's the only H121 RAW_REJECTS with negative
raw_end_slope (-0.21). The raw tracker captured a stationary ball at
the V-apex, and the feat_end_slope (+2.15) reflects the post-V
ascent, not a catch. H7v2's "catch signature" must have triggered
on a different feature (probably start_dist or side).

### 22→26 YouTube — TRACKER_ARTIFACT

Vision verdict: "VERDICT: TRACKER_ARTIFACT". The feat-based slope is
mildly descending (-0.29) but the raw slope is steeply descending
(+7.32). The raw endpoint is geometrically below and offset from
the parabola's actual catch zone, and the target tracklet begins in
a different region. The 51.5-px feat→raw dist jump indicates the
raw tracker lost the object and jumped to a different location.

### 26→31 YouTube — UNCERTAIN

Vision verdict: "VERDICT: UNCERTAIN". The feat endpoint (slope=0.94)
sits near the hand consistent with a catch, but the raw endpoint
(slope=6.49) ascends sharply upward away from the hand over only 5
frames. The 152.1-px raw jump to a descending target parabola is
more consistent with the raw tracker capturing the post-catch
re-throw motion (tracker bleeding into the next throw) than a clean
catch-throw handoff. This is the most ambiguous case in the
sample — could be a real catch-throw that the raw tracker
overshot, or a tracker artifact.

### 30→37 YouTube — REAL_CATCH_THROW

Vision verdict: "VERDICT: REAL_CATCH_THROW". The long source
tracklet (119 raw points) cleanly arcs down to the L-hand position
(consistent with a catch), the 9-frame gap is small, the spatial
jump (57-81 px) is short and consistent with a re-throw from the
same hand, and the reclassifier correctly flagged it as a hand
transition.

### 33→36 YouTube — TRACKER_ARTIFACT

Vision verdict: "VERDICT: TRACKER_ARTIFACT". The source tracklet
ends with a single descent into the hand (no V-shape, no throw
within the source), and the target tracklet starts at the same
hand position to begin a new throw. The small sj_raw (62.5 px) and
feat_end_dist right at threshold (24.95), combined with the missing
V-shape in the source, indicate the tracker is breaking the
trajectory at the hand rather than capturing a true catch-throw
cycle within a single continuous tracklet.

## Aggregate verdict (H122 + H123 combined)

| Verdict | H122 (5) | H123 (10) | Combined (15) |
|---|---|---|---|
| REAL catch-throw | 4 (80%) | 4 (40%) | **8 (53.3%)** |
| TRACKER_ARTIFACT | 1 (20%) | 5 (50%) | **6 (40.0%)** |
| UNCERTAIN | 0 (0%) | 1 (10%) | **1 (6.7%)** |

**REAL precision: 8/15 = 53.3%** (Wilson 95% CI: [30.1%, 75.2%]).
Excluding the 1 UNCERTAIN: 8/14 = 57.1% (Wilson 95% CI: [32.6%, 78.6%]).

### Per-stem breakdown

| Stem | n | REAL | ARTIFACT | UNCERTAIN | REAL % | Wilson 95% CI |
|---|---|---|---|---|---|---|
| identical | 5 | 3 | 2 | 0 | 60.0% | [23.1%, 88.2%] |
| YouTube | 10 | 5 | 4 | 1 | 50.0% | [23.7%, 76.3%] |

The YouTube RAW_REJECTS pool has slightly lower REAL precision than
identical (50% vs 60%), but the difference is not statistically
significant (overlapping CIs).

## Implication for H7v2 reclassification

**H7v2 reclassification is over-applied at ~50% rate** when the input
tracklet_features is used. The H122 "80% defensible" conclusion is
**REVISED** to "~50% defensible" on a larger sample.

This is consistent with the H121 finding: 26/34 (76.5%) of
RECLASSIFIED_HAND_TRANSITION edges would NOT be reclassified if raw
data were used. Of those 26 RAW_REJECTS, the H122+H123 visual QA
finds 8/15 = 53.3% are real catch-throws (and 6/15 = 40% are tracker
artifacts that H7v2 incorrectly flagged as hand transitions).

## Implication for H112 / H114 v1 strict

H112 cross-hand handoff filter (fires on 22→27) catches **1/6 (17%)**
of the H122+H123 artifacts. The remaining 5 artifacts survive H112.

H114 v1 strict (T_d=25, T_j=200) would fire on **0/6** of the H123
artifacts (max sj_raw=152.1, below 200). The 22→27 case is the only
RAW_REJECTS with feat_jump > 200 (190.4); H114 fires on the orig metric
in H117, but at the raw metric the 22→27 raw_jump is 37.5 (well below
200) and H114 would NOT fire on the raw metric.

**The geometric post-filters compensate for only ~1/6 of the H7v2
artifacts.** The remaining artifacts survive the precision-optimized
h7v3plus3 + H112 + H114 v1 strict stack.

## Aggregate precision at the chain level

The h7v3plus3 chain set contains 26 RAW_REJECTS edges (per H121). At
~50% REAL precision, ~13 of those 26 edges are false positives in
the chain. Combined with the 8 STILL_RECLASSIFIED edges (H7v2_orig =
H7v2_raw both reclassify), the chain contains ~13-15 FPs from H7v2
reclassification alone.

These FPs are bounded by:
- 0/26 are in the 113 manual review pair set (so H59 precision/recall
  metrics are unchanged)
- The h7v3plus3 chain set has 40 identical + 13 YouTube chains;
  ~13-15 FPs in ~53 chains is a 24-28% FP rate at the chain level

The H59 P=0.981 metric measures precision at the *chain-edge* level
(71 correct + 42 wrong = 113 pairs), not at the chain level. The 42
"wrong" pairs in H59 are mostly NOT in h7v3plus3, so they don't
contaminate the chain precision directly. But chains that contain
H7v2-reclassified FPs may propagate those FPs to downstream consumers
(H11 identity propagation, H12 pattern inference, H36 hand-occupancy).

## Negative findings

- H122's 80% precision was a biased estimate from a small sample
  selected for diverse structural signatures. The H123 stratified
  sample shows 53.3% precision on 15 cases total.
- H112 only catches 1/6 (17%) of H123 artifacts. The geometric
  post-filters are insufficient.
- H114 v1 strict catches 0/6 of H123 artifacts (max sj_raw=152.1).
- The 1 UNCERTAIN case (26→31) is the largest raw_jump (152.1) and
  is the only one with a strong ambiguity signal.
- 43→45 (2-pt source) and 33→36 (feat_end_dist at threshold) are the
  most obvious geometric artifacts — short source tracklets and
  endpoints at H7v2's distance threshold (108 px) produce unstable
  catch signatures.
- H7v2's "edge J= 0.94" (43→45) and "edge J=2.94" (33→36) cases
  are FP-prone because the source tracklet is too short or the
  endpoint is right at the threshold.

## Recommended operating point (UPDATED)

The h7v3plus3 + H112 + H114 v1 strict stack is **still the
precision-optimized operating point** at the chain-edge level
(P=1.000, R=0.718 on 113 review pairs). But the H123 finding
clarifies that:

1. **H7v2 reclassification is over-applied at ~50% rate.** A
   downstream consumer of h7v3plus3 chains should treat
   RECLASSIFIED_HAND_TRANSITION edges with skepticism.
2. **H112 + H114 catch only ~1/6 of the H7v2 artifacts.** A
   consumer that needs high precision on hand transitions should
   consider only STILL_RECLASSIFIED + H22_RECLASSIFIED + H26_RECLASSIFIED
   edges (the 8+1+3 = 12 edges where H7v2_orig agrees with the
   raw-data reclassification, plus the 1 H22 YouTube veto and the
   3 H24-KEPT identical edges).
3. **H7v2 reclassification's 53% precision is consistent with
   the H59 finding (P=0.981 at edge level on 113 pairs)** because
   the 113 pairs are sampled from the still-reclassified edges
   and the hand transitions from the original v4d pipeline, not
   the H7v2-reclassified edges. The 26 H7v2 reclassifications are
   mostly not in the manual review.

## Future research

1. **H124: precision-optimized edge filter** — use the H122+H123
   visual QA to define a stricter post-filter for H7v2-reclassified
   edges. The 8/15 REAL cases have a specific signature: source
   tracklet contains a V-shape OR the target tracklet has small
   sj_raw. A geometric filter on these signatures might catch
   5/8 REAL while rejecting 5/6 ARTIFACT.
2. **H125: re-evaluate the H7v2-reclassified edges that ARE in the
   113 manual review set** — the H59 finding was 0/26 RAW_REJECTS
   in the review set, but the chain set has H7v2-reclassified
   edges that ARE in chains. A targeted check on chain-internal
   RECLASSIFIED edges (i.e., edges in h7v3plus3 that are also
   RECLASSIFIED_HAND_TRANSITION) would give a more precise
   precision estimate.
3. **Stop here.** The h7v3plus3 chain set is precision-optimized
   at the 113 review pair level. The H123 finding is a real
   negative that documents the H7v2 over-application, but the
   chain's edge-level P=1.000 is preserved because the 113 pairs
   are sampled from non-H7v2 sources.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h123_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h123/*.png` (10 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h123_report.md` (this file)
