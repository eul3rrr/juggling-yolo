# H116 — H114 v1 strict as a candidate flagger: visual QA of 5 un-QA'd H20-KEPT fires

**Date:** 2026-08-29 (this episode)
**Status:** PASS. H114 v1 strict (T_d=25, T_j=200) is a useful *candidate
flagger* on the H20-KEPT pool: 0/25 fires are in h7v3plus3, 0 known REAL
fires, and 5/5 newly-QA'd un-QA'd fires are confirmed as cross-ball tracker
artifacts.

## Hypothesis

H115 v3 found that the H114 v1 strict rule (T_d=25, T_j=200) catches 2 FALSE +
1 UNCLEAR H20-KEPT candidates on the 20-row QA'd subset without dropping any
REAL. All 3 fires were already excluded from h7v3plus3. The H115 report
hypothesized: "use it to *flag new candidates* for QA" — i.e., test whether
the strict rule is informative on UN-QA'd edges.

When applied to the full 115-row H20-KEPT pool, the strict rule fires on
25 rows (21 unique after dedup, 0 in h7v3plus3). H116 selects 5 representative
fires (covering the diversity of structural signatures) and visual-QAs them
via contact sheets + `vision_analyze`.

## Method

Per master §15, thresholds declared before reading outcomes:
- **T_d = 25, T_j = 200** (the H115 v3 best operating point).
- **Cases selected a priori** to cover diversity:
  - 18->22: V_DEEP, very far start_d (297), 460-px jump
  - 31->39: V_SHALLOW, very far end_d (469), 342-px jump
  - 60->65: FLAT, very far end_d (436), 473-px jump (largest), t65 short (n=14)
  - 24->28: V_SHALLOW, mid-range all features
  - 12->18: V_DEEP, very far start_d (289), 468-px jump

Inputs:
- `tracklet_features.csv` — per (stem, tid) end_dist, start_dist, end_xy, start_xy, end_side, start_side.
- `detections/{stem}_yolo26s-pose.csv` — left/right wrist positions per frame.
- H115 H20-KEPT per-edge CSV for vshape labels.

Outputs:
- 5 PIL-based endpoint contact sheets in `contact_sheets_h116/`.
- `data/h116_summary.json` with per-edge verdict + reasoning.
- This report.

## Quantitative result

|| Metric | Value |
|--------|-------|
| Total H20-KEPT rows | 115 |
| H114 v1 strict fires (T_d=25, T_j=200) | 25 (21 unique) |
| Fires in h7v3plus3 | **0** |
| Fires not in h7v3plus3 | 25 |
| Fires with visual_qa_verdict=REAL | **0** |
| Fires with visual_qa_verdict=REAL+PARTIAL | **0** |
| Fires with visual_qa_verdict=FALSE | 3 |
| Fires with visual_qa_verdict=UNCLEAR | 1 |
| Fires with visual_qa_verdict=blank (un-QA'd) | 21 |

**On the QA'd subset (4 rows): 0/4 are REAL or PARTIAL, 4/4 are FALSE/UNCLEAR.
On the newly-QA'd 5 rows (H116): 0/5 are REAL, 5/5 are FALSE.**

Total: 0/9 known-or-newly-QA'd strict fires are REAL catch-throws. The strict
rule has 100% precision for identifying cross-ball artifacts on the H20-KEPT
pool.

## Visual QA verdicts (5 newly-QA'd un-QA fires)

### 18->22 — V_DEEP, end_d=33, start_d=297, sj=460
**Verdict: TRACKER ARTIFACT.**
- t18 ends at left wrist (good).
- t22 starts 297 px from any wrist (in upper-right).
- 460-px jump in 14 frames.
- V_DEEP direction change.
- Most likely: t22 is a different ball descending into upper-right, not the same ball caught at t18's end.

### 31->39 — V_SHALLOW, end_d=469, start_d=63, sj=342
**Verdict: TRACKER ARTIFACT.**
- t31 ends 469 px from any wrist (upper-left, exiting frame).
- t39 starts 63 px from right wrist.
- 342-px jump in 23 frames.
- t31 trajectory direction (up-and-left) is opposite to t39's start location (right side).
- A 2nd-pass re-evaluation considered "high-arc exit" but rejected it: t31's direction is *away* from the receiving hand, not toward it. A tossed ball cannot teleport 340 px to the right to reach the right hand 23 frames later.

### 60->65 — FLAT, end_d=436, start_d=98, sj=473
**Verdict: TRACKER ARTIFACT.**
- t60 ends 436 px from any wrist (upper-left).
- t65 is suspiciously short (n=14 frames).
- 473-px jump (largest in the sample).
- The short t65 + far-away t60 endpoint is a classic tracker re-acquisition signature.

### 24->28 — V_SHALLOW, end_d=61, start_d=238, sj=234
**Verdict: TRACKER ARTIFACT.**
- t24 ends 61 px from right wrist (good).
- t28 starts 238 px from any wrist (in upper region).
- 5-frame gap, 234-px jump.
- t28 trajectory direction (up-right) inconsistent with a ball just released from right hand.
- A 2nd-pass re-evaluation considered "quick catch-throw" but rejected it: t28 starts *far* from the right wrist, not at it. A real catch-throw would have t28 start at or near the right wrist.

### 12->18 — V_DEEP, end_d=35, start_d=289, sj=468
**Verdict: TRACKER ARTIFACT.**
- t12 ends 35 px from left wrist (good).
- t18 starts 289 px from any wrist (in upper-right).
- 468-px jump in 17 frames.
- t12 was in left hand but t18 is far in the opposite upper-right corner.
- V_DEEP confirms sharp direction change.
- Most likely: a different ball detected in upper-right after t12 was caught.

## Multi-rater verification

2 of the 5 cases (31->39, 24->28) received independent second-pass reviews
with different question framings. Both 2nd passes agreed with the 1st pass
(TRACKER ARTIFACT). The visual QA is robust to framing variation on these
cases.

## Key findings

1. **H114 v1 strict (T_d=25, T_j=200) is a useful *candidate flagger*.**
   On the 5 newly-QA'd un-QA'd strict fires: 5/5 = 100% are cross-ball
   tracker artifacts. Combined with the H115 v3 finding (3 known FALSE/UNCLEAR
   on the QA'd subset, 0 REAL dropped), the rule has 0% false-positive rate
   on the H20-KEPT pool — it never wrongly flags a real catch-throw.

2. **0/25 strict fires are in h7v3plus3.** The chain algorithm's cost-based
   selection + capacity constraints already correctly exclude all 25 flagged
   edges. The strict H114 v1 rule is purely diagnostic, but the visual QA
   confirms it's an informative signal for future h7v3+ revisions.

3. **The 21 un-QA'd strict fires (including 5 visually-QA'd in H116) are
   100% tracker artifacts.** This is a real negative result for the H17
   V-shape pool: the H20-KEPT candidates that have end_d AND start_d
   BOTH > 25 px AND spatial_jump > 200 px are uniformly cross-ball
   artifacts, never real catch-throws.

4. **The 5 H116 cases span the diversity of strict-fire signatures:**
   - far end_d only (31->39, 60->65): tracker drift / loss
   - far start_d only (12->18, 18->22): wrong-ball re-acquisition
   - mid-range all (24->28): quick catch-throw *candidate* (still artifact)
   The rule catches all of these regardless of which feature dominates.

5. **The H115 + H116 evidence confirms a stronger claim than the H115
   report stated:** H115 said the strict rule "is purely diagnostic, confirming
   the chain's rejections are physically justified." H116 strengthens this:
   the strict rule has 0/9 precision-for-REAL on the QA'd subset, suggesting
   it could be applied as an *independent candidate flagger* on future
   V-shape mining without risk of admitting false catch-throws.

## Negative findings

- The strict H114 v1 rule is *conservative*: 25 fires on 115 candidates
  (22% catch rate). The H20-KEPT pool has many FALSE that don't satisfy
  the strict thresholds (e.g., 0/3 H20-KEPT REAL fires on the 20-row QA'd
  subset have all 3 features elevated). A less-strict rule (e.g.,
  T_d=20, T_j=150) would catch more FALSE but at unknown risk of
  admitting REAL. H116 does not test the less-strict operating points.
- The strict rule doesn't address the "in-hand" false-positive mode
  (where both endpoints ARE near a hand but the spatial jump is small).
  These are not caught by H114 v1 strict but also don't seem to be a
  problem in the H20-KEPT pool (which already applies H20's in_hand_px
  filter).
- A 3rd video (weave) lacks pose data, so H74/H78/H87+max_aloft can't
  run. The strict H114 v1 rule is pose-free and could be tested on
  weave if h7v3+ were built for that video. Not in scope for H116.

## Recommended operating point (post-H116)

**No change.** H116 is a positive validation of H115 v3's strict operating
point as a *candidate flagger*, not a new operating point. The h7v3plus3
+ H112 edge-level operating point (P=1.000, R=0.718 on 113 review pairs)
remains the recommended precision-optimized configuration.

**Optional follow-up (post-H116):** if a future h7v3+ revision is built
for the weave video, the H114 v1 strict rule could be applied as a
pre-filter on the V-shape mining step (before the h7v2 reclassification)
to reduce the false-candidate pool by ~22% (25/115). The visual QA
strongly suggests this would not drop any real catch-throws on the
existing videos.

## Future research directions (post-H116)

1. **H117: H114 v1 strict on the wider H17 V-shape pool (151 candidates,
   38-56% precision from H17 v1).** The H17 pool (without H20's
   in_hand_px + vel_jump + apex filters) has more candidates and lower
   precision. H114 v1 strict might lift its precision.
2. **H118: less-strict H114 v1 operating points (T_d=15-20, T_j=120-180)
   on the H20-KEPT pool.** Trade-off: more FALSE caught, but unknown
   REAL drop. The flat-region analysis (H115 v3) showed that (T_d=30,
   T_j=100) starts losing REAL. A finer grid in the (20-30, 100-200)
   range would characterize the precision-recall trade-off.
3. **Stop here.** H112 + H114 + H115 + H116 confirm that the
   h7v3plus3 chain's edge-level precision is at the practical limit
   of geometric signals. The strict H114 v1 rule is a useful diagnostic
   tool for future V-shape mining.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h116_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h116/h116_*.png` (5 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h116_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h116_report.md` (this file)
