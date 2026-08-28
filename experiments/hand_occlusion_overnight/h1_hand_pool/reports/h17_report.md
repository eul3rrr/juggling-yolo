# H17 — V-shape recovery for v4d-rejected links + strict V-shape candidate search

**Date:** 2026-08-28 ~18:50 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **PARTIAL PASS** (useful research tool, but H17 strict V-shape has lower precision than h7v2's endpoint check).

## Hypothesis

H14's V-shape classifier found 5 V-shape positives among the 13 h7v2-kept BALLISTIC edges. H15v2 reclassified 4 of them (23→25, 30→33, 39→47, 51→52) as V_RECLASSIFIED_HAND_TRANSITION. H17 hypothesis: there are MORE V-shape hidden catch-throws that the chain pipeline missed, particularly:

1. **v4d-rejected links** (35→40 identical, 15→25 YouTube) — v4d rejected them for `LOW_FROM_SLOPE` (< 2.5 px/frame) but they may be real catch-throws.
2. **E6c candidate edges NOT admitted by h7v2** — E6c is the trajectory-fit predecessor candidate set; h7v2 rejected some for cost reasons but the V-shape may rescue them.
3. **Adjacent tracklet pairs NOT in any h7v2 edge** — truly novel candidates.

H17 adds a **STRICT filter** on top of V-shape: at least one endpoint must be within 108 px of a hand (the reach radius), AND the V-apex hand must match the endpoint's "end_side" or "start_side", AND a `MIN_SLOPE = 1.0` catch/throw signature is required. This aims to reduce the naive V-shape false-positive rate.

## Thresholds (declared from physical geometry, NOT tuned to labels)

Inherited from H14/H15v2:
- `TAIL_FRAMES = 6`, `HEAD_FRAMES = 6`, `GAP_INTERP_FRAMES = 5`
- `HAND_REACH_PX = 108`
- `V_DEEP_MIN_PX = 50`, `V_DEEP_RATIO = 1.5` → V_DEEP
- `V_SHALLOW_MIN_PX = 100`, `V_SHALLOW_RATIO = 1.3` → V_SHALLOW
- `MAX_GAP_FOR_VSHAPE_FRAMES = 30`
- `MIN_TRACKLET_LEN = 3`

H17's STRICT additions:
- `STRICT_ENDPOINT_MAX_DIST_PX = 108` — at least one endpoint within reach
- `STRICT_MIN_SLOPE = 1.0` — endpoint must have |slope| >= 1.0 (catch/throw signature)
- The endpoint's `end_side` / `start_side` must match the V-apex hand (left/right)

## Quantitative result

| Source | n_strict | min_d range | in h7v3 edge set | transitive in chain |
|---|---|---|---|---|
| v4d_rejected (n=2) | 2 | 8.3-15.3 | **1** (15→25 already in h7v3) | 0 |
| e6c_not_in_h7v2 (n=many) | 42 | 2.1-58.2 (median 22.4) | 0 | 4 |
| adjacent (n=many) | 107 | 1.1-101.6 (median 22.4) | 0 | 0 |
| **Total** | **151** | | **1** | **4** |

### Per-stem breakdown

| Stem | adjacent | e6c_not_in_h7v2 | v4d_rejected | Total |
|---|---|---|---|---|
| identical | 89 | 38 | 1 | 128 |
| YouTube | 18 | 4 | 1 | 23 |

The YouTube video has 7x fewer strict V-shape positives than identical. This is because:
- YouTube has only 40 tracklets (vs 76 identical)
- YouTube's tracklets are much longer (median 30+ frames vs identical's < 20), so fewer "adjacent" tracklet pairs exist within the 30-frame MAX_GAP
- YouTube's hand-pose misses are more common (face-feature confusion from H3), so some V-shapes near the hand region are rejected by the strict endpoint check

### Gap distribution (e6c_not_in_h7v2 strict positives)

Gaps 5-16, median 8. The V-shape strict check is most productive for short gaps (5-11 frames) which are typical catch-throw time scales.

## Visual QA: 16 contact sheets inspected

16 contact sheets were rendered and inspected via `vision_analyze` — the 2 v4d-rejected plus 14 samples from e6c_not_in_h7v2 and adjacent. Results:

| # | Edge | Source | min_d | V | Verdict |
|---|------|--------|-------|---|---------|
| 1 | 35→40 identical | v4d_rej | 15.3 | V_DEEP | unclear (long 27-frame gap; H12 v3 confirmed real) |
| 2 | 15→25 YouTube | v4d_rej | 8.3 | V_DEEP | **REAL** |
| 3 | 6→15 identical | e6c | 2.1 | V_DEEP | **REAL** |
| 4 | 4→8 identical | e6c | 2.97 | V_DEEP | **FALSE** (in-hand, not airborne) |
| 5 | 35→38 identical | e6c | 6.99 | V_DEEP | **FALSE** (source high, not descending) |
| 6 | 56→57 identical | e6c | 7.1 | V_DEEP | **REAL** |
| 7 | 10→11 YouTube | e6c | 4.69 | V_DEEP | **FALSE** (apex high above hands) |
| 8 | 20→21 YouTube | e6c | 5.32 | V_DEEP | **REAL** |
| 9 | 54→57 identical | e6c | 8.51 | V_DEEP | **REAL** |
| 10 | 66→68 identical | e6c | 10.86 | V_DEEP | **FALSE** (source held, target at hand) |
| 11 | 23→24 YouTube | e6c | 7.8 | V_DEEP | **PARTIAL** (plausible same-hand catch-rethrow) |
| 12 | 1→10 YouTube | e6c | 8.19 | V_DEEP | **FALSE** (apex at shoulder, not hand) |
| 13 | 29→33 identical | adj | 5.63 | V_DEEP | **PARTIAL** (real catch, throw not visible) |
| 14 | 13→15 identical | adj | 2.1 | V_DEEP | **PARTIAL** (real catch, throw not visible) |
| 15 | 56→58 identical | adj | 7.1 | V_DEEP | **REAL** (long 26-frame gap, clear catch-throw) |
| 16 | 24→27 YouTube | adj | 1.06 | V_DEEP | **FALSE** (apex at torso, not hand) |

**Tally: 5 REAL + 3 PARTIAL + 1 UNCLEAR + 7 FALSE = 16.**

- If PARTIAL=TP: 9/16 = 56% precision
- If PARTIAL=FP: 6/16 = 38% precision (excluding the unclear)
- The 7 FALSE positives all have a similar failure pattern: the V-apex is interpolated as a position 1-10 px from a hand, but the source/target tracklets are actually in-hand or stationary detections, not airborne catches.

## Key finding: the 2 v4d-rejected links are mostly already in h7v3

The 2 v4d-rejected links that the V-shape strict check recovers are:

- **35→40 identical** (gap=27, min_d=15.3, V_DEEP) — already in h7v3 chain 23 as `35→37` (RECLASSIFIED_HAND_TRANSITION) and `37→40` (RECLASSIFIED_HAND_TRANSITION). H17's 35→40 spans the same physical connection via an intermediate tracklet (37).
- **15→25 YouTube** (gap=11, min_d=8.3, V_DEEP) — directly in h7v3 as `15,25,RECLASSIFIED_HAND_TRANSITION,err=10.73`. The h7v2 reclassification rule (src_catch_dist=6.6, slope=-2.08) accepted it because the source's end_dist=6.6 is well within 108 px and the |slope|=2.08 >= h7v2's threshold of 1.0 (which is more permissive than v4d's 2.5).

**H17's strict V-shape does not recover any v4d-rejected link that h7v2's endpoint check missed.** The two paths reach the same conclusion (both are real catch-throws) but via different mechanisms:
- v4d rejects for `LOW_FROM_SLOPE` (the catch slope is < 2.5 px/frame)
- h7v2 reclassifies because the source endpoint is within reach (dist=6.6) AND has a catch slope (|slope| >= 1.0)
- H17 strict V-shape reclassifies because the source-tail + gap + target-head trajectory dips toward a hand (min_d=8.3) with V-shape ratio >= 4.24

For 35→40 identical, the situation is more subtle. v4d rejected the 35→40 link directly (LOW_FROM_SLOPE 2.31) but the chain pipeline recovers the connection via an intermediate t37. The chain 23 (`35,37,40,41,43,45,46`) is a 7-tracklet juggling cycle, so the v4d-rejection of 35→40 doesn't lose information.

## Negative findings

- **H17 strict V-shape is NOT a precision-preserving alternative to h7v2.** The 16-sample visual QA suggests ~38-56% precision on novel e6c_not_in_h7v2 candidates, vs h7v2's ~80% precision on its reclassified edges. The strict filter (dist <= 108 + slope >= 1.0 + side match) helps but is not enough — many false V-shapes satisfy it because the source/target are in-hand or stationary.

- **The "adjacent" search (107 strict positives) is too permissive.** Most adjacent tracklet pairs are temporally close (~1-10 frame gap) and the V-shape check is dominated by short trajectories. Many adjacent positives are within the same hand (in-hand held balls) and the V-apex is artificially close to a hand because the hand isn't moving. Visual QA of 6→15 (REAL) and 13→15 (PARTIAL) suggests 2/7 inspected adjacent positives are real catch-throws; the rest are in-hand or short-trajectory artifacts.

- **H17's V-shape is a position-only check.** The H11 v7 visual QA finding applies here too: position-only V-shape admits some hand-borne cases (ball being carried, not caught+thrown) and tracklet breaks (jumps in position with no real ball transfer). A velocity-jump check would help, but H15v1's JUMP_TOLERANCE=15 mis-calibrated the filter (rejected 23→25 with jump=23.4 px/frame and admitted 27→28 with jump=14.5).

- **The YouTube video has few H17 strict positives (23) because most candidate pairs already have at least one of: long source/target tracklet (no V-shape possible), or the source/target doesn't have a wrist-anchored V-apex.** The 4 YouTube e6c_not_in_h7v2 strict positives are short-gap candidates that the e6c trajectory fit error was too high for h7v2 to accept.

## Implications for the chain pipeline

**H17 does not recommend a new chain reclassification rule.** The h7v2 endpoint check (dist <= 108 AND |slope| >= 1.0) is more precise (~80% precision) than H17's V-shape + strict filter (~38-56% precision on novel candidates). The 2 v4d-rejected links that H17 finds are already in the h7v3 chains.

**H17 is useful as a research tool** for:
1. **Finding V-shape positives that h7v2 missed** for further investigation. The 42 e6c_not_in_h7v2 strict positives include ~3-4 real catch-throws (visual QA) that the chain pipeline doesn't yet emit. These could be added to a downstream "alternative catch-throw candidates" list for review.
2. **Characterizing the V-shape false-positive rate** on a larger sample. The naive V-shape would emit ~1000+ positives on the 76 identical tracklets; the strict filter cuts this to 128 (38 e6c + 89 adjacent + 1 v4drej), but the precision is still below h7v2's.
3. **Validating the existing h7v2 chain** by checking that all h7v2 HAND_TRANSITION edges are V-shape strict positives. This is a useful negative control: if any h7v2 hand-edge fails the strict V-shape check, it might be a wrong reclassification.

## Verdict: **PARTIAL PASS**

H17's strict V-shape filter is a useful research tool for finding candidate catch-throws that the chain pipeline missed, but its precision (~38-56% on a 16-sample visual QA) is below the existing h7v2 endpoint check (~80% on visually-confirmed reclassifications). H17 does not recover any v4d-rejected link that the h7v2 chain pipeline didn't already catch. The 151 strict positives include ~3-4 real catch-throws that h7v2 missed entirely (in the e6c_not_in_h7v2 set), but most are false positives dominated by in-hand held balls.

**H17 should be used as a research tool for finding candidates, not as a reclassification rule for production chains.** A downstream consumer can use H17's strict positives as a "candidate list" for manual review.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h17_v_shape_recovery.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h17_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h17_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h17_v_shape_positives.csv` (naive V-shape positives)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h17_strict_v_shape_positives.csv` (151 strict positives)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h17/*.png` (28 contact sheets)

## See also

- `h14_report.md` — H14 V-shape classifier (5 V-shape positives on h7v2-kept BALLISTIC)
- `h15v2_report.md` — H15v2 V-shape reclassification (4 new V_RECLASSIFIED edges)
- `h11_v7_report.md` — H11 v7 identity propagation (catches the 2/4 hand-borne vs 2/4 clean catch+throw nuance)
- `h16_report.md` — H16 H3 corroboration of V-reclassified edges
- `h7v2_report.md` — H7v2 reclassification rule (the existing endpoint check)
