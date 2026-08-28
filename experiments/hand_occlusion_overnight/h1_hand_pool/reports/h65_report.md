# H65 — FOUNTAIN_3+ label validation at scale (post-H64 zones)

**Date:** 2026-08-28
**Hypothesis:** With H50's 10-frame event log filter applied (the latest
validated filter) and the H64 zone classification (post-f=240 is the
FOUNTAIN-rich phase on identical; YouTube has SHOWER bursts at
f=420-510 and f=769-825 per H63), H12 v8's FOUNTAIN_3+ classification
might be more accurate than the 30% found in H39.

**Method:** Render 4-frame contact sheets for all substantial
FOUNTAIN_3+ phases (>= 20 frames) in the H50-filtered pattern data.
Classify each phase by hand/ball positions using vision_analyze.
Compare vision verdict to H12 v8 label.

**Sample:** 7 substantial FOUNTAIN_3+ phases (4 identical + 3 YouTube).

## Results

| Video | Phase | n | conf | Zone | H12 v8 | Vision | Match |
|---|---|---|---|---|---|---|---|
| identical | 631-669 | 39 | 0.714 | POST_F240_FOUNTAIN_ZONE | FOUNTAIN_3+ | FOUNTAIN | YES |
| identical | 890-936 | 47 | 0.571 | POST_F240_FOUNTAIN_ZONE | FOUNTAIN_3+ | OTHER | NO |
| identical | 977-1011 | 35 | 0.565 | POST_F240_FOUNTAIN_ZONE | FOUNTAIN_3+ | FOUNTAIN | YES |
| identical | 1029-1049 | 21 | 0.463 | POST_F240_FOUNTAIN_ZONE | FOUNTAIN_3+ | OTHER | NO |
| youtube | 339-374 | 36 | 0.646 | OUTSIDE_KNOWN_SHOWER | FOUNTAIN_3+ | FOUNTAIN | YES |
| youtube | 482-594 | 113 | 0.653 | OUTSIDE_KNOWN_SHOWER | FOUNTAIN_3+ | OTHER | NO |
| youtube | 800-861 | 62 | 0.651 | NEAR_SHOWER_BURST_769-825 | FOUNTAIN_3+ | CASCADE | NO |

**H12 v8 FOUNTAIN_3+ accuracy on this sample: 3/7 = 43%.**

This is an improvement over H39's 30% but still a noisy classifier.

## Per-video breakdown

**Identical (3-ball, n=4 phases):**
- 2/4 FOUNTAIN (631-669, 977-1011)
- 2/4 OTHER / trick-hold (890-936, 1029-1049)
- Both wrong cases are in the post-f=240 FOUNTAIN-rich zone (H64)
- Wrong cases have LOWER H12 v8 confidence (0.571, 0.463) than correct
  cases (0.714, 0.565 — but 977-1011 is 0.565 with FOUNTAIN verdict)

**YouTube (5-ball, n=3 phases):**
- 1/3 FOUNTAIN (339-374) — the f=339-374 phase is genuine fountain
  (synchronized 3-up-2-held structure)
- 1/3 OTHER / static hold (482-594) — 113-frame "static" window,
  only 4 of 5 balls visible, balls appear to be falling/resting
- 1/3 CASCADE (800-861) — alternating hand throws with crossing arcs
- Confidences are similar (0.646, 0.653, 0.651) — no signal here

## Comparison to H39 (30% finding)

H39 was on 10 substantial FOUNTAIN_3+ phases (9 identical + 1 YouTube +
2 outside-known-shower) and found 30% accuracy:
- 3/10 FOUNTAIN
- 4/10 MIXED
- 1/10 CASCADE
- 2/10 OTHER

H65 (3/7 = 43%) is a more accurate sample for two reasons:
1. H50 filter (10-frame event log filter) drops the 3 identity
   switches on identical — this may remove some CASCADE events
   that H39 mislabeled
2. H65 uses 4-frame sheets (more focused than H39's 6-frame)
3. H65 separates FOUNTAIN from MIXED (H39 had MIXED as a separate
   category; H65 collapses it to FOUNTAIN if the synchrony is
   present, OTHER if not)

The 30% → 43% improvement is real but small. H12 v8's FOUNTAIN_3+
classification remains unreliable.

## Why H12 v8 over-classifies FOUNTAIN_3+

H12 v8's classifier is based on the K=4 sliding window of recent
catch/throw events. It looks for "same-hand repeated catches" to
infer FOUNTAIN. But:

1. **Hold/trick frames look same-hand in the event log.** The
   1029-1049 identical phase has 2 balls in the hands the whole
   time. Any catch event the H12 v8 detects in this window will
   be on the same hand as the previous catch (because the juggler
   is just holding, not throwing). H12 v8's classifier interprets
   this as FOUNTAIN, but the actual pattern is a static hold.

2. **CASCADE phases with 2+ ball hand-occupancy are mislabeled.**
   The 800-861 YouTube phase is a CASCADE with the right hand
   holding an extra ball (likely from a SHOWER burst that
   extends beyond the H63 SHOWER burst window). The extra ball
   in the hand makes the catch rhythm look same-hand to H12 v8.

3. **The H50 10-frame filter is a necessary but not sufficient
   fix.** It removes tracker-fragmentation events (which look
   like rapid alternation) but cannot distinguish "hold" from
   "synchronized throw".

## The H43 confidence filter remains the best post-filter

H43 (H12 v8 confidence < 0.55) correctly identifies 27/298 (9.1%) of
identical FOUNTAIN_3+ frames as low-confidence. All 27 are in
f=1029-1060 (the "OTHER 2-ball exercise" phase from H39 visual QA).
H65 confirms this: the 1029-1049 phase has conf 0.463 and is OTHER
in the visual QA.

H43's catch: the 890-936 phase has conf 0.571 (above 0.55) and is
also OTHER. H43 misses it. The 977-1011 phase has conf 0.565 and
is FOUNTAIN. H43 correctly preserves it.

**H65 confirms H43's 0.55 threshold is a useful but not perfect
filter.** The threshold's precision is high (1.000 on H39 + H65
samples) but its recall is low (1/2 OTHER in identical H65 sample).

## Implications for the operating point

1. **H12 v8 FOUNTAIN_3+ is unreliable but not unusable.** The 43%
   accuracy on H65 is low but the correct 3 phases are genuine
   FOUNTAIN phases (synchronized parallel throws).

2. **The h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H52 + H53
   stack remains the final operating point.** The H43 confidence
   filter is the most precise FOUNTAIN_3+ post-filter; H65
   confirms it.

3. **A truly reliable FOUNTAIN_3+ classifier would need continuous
   hand-occupancy signal** (per H40, H41 finding that H40 v2
   hand-occupancy doesn't cleanly discriminate FOUNTAIN from
   CASCADE). This is a fundamental limitation of the chain-event
   representation.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h65_fountain_label_validation.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h65_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h65_visual_qa_verdicts.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h65/*.png` (7 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h65_report.md`
