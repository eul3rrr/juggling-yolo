# H61 — YouTube 16→21 vs 20→21 catch+throw conflict: visual adjudication

**Date:** 2026-08-28 ~16:50 CEST
**Status:** COMPLETE (H22 verdict visually confirmed: 20→21 is the real catch-throw)
**Author:** autonomous hand-occlusion overnight research lab

---

## The conflict

- **2024 manual stitch review** (stitch_review_labels.csv): YouTube
  16→21 is "correct" (gap=8, prediction_error=194.41)
- **H22 visual analysis (2026-08-28)**: YouTube 16→21 is WRONG.
  Tracklet 16 ends at f=468 (2 frames BEFORE t20's contact at
  f=471-473). The real catch is t20→t21 (V-shape min_d=5.3 vs
  t21's start_dist=35.3).
- **H22 resolution**: VETO 16→21 and admit 20→21 in the chain set.
  The h7v3plus3 chain set has 20→21 (as H22_RECLASSIFIED_HAND_TRANSITION)
  and excludes 16→21.

**The conflict between the 2024 manual labels and the 2026 lab
visual analysis was unresolved in H22 — only the H22 visual analysis
was reported. H61 renders a side-by-side contact sheet and asks the
vision tool to adjudicate the conflict.**

## Method

Render two panels:
- **TOP**: tracklet 16 (gray, f=343-468) followed by tracklet 21
  (yellow, f=482-512). The 16→21 alternative.
- **BOTTOM**: tracklet 20 (green, f=466-473) followed by tracklet 21
  (yellow, f=482-512). The 20→21 alternative.

Both panels show the right wrist (blue circle) at the relevant
frames. The catch physically happens at the right hand at f=482
(where t21 starts).

Vision tool is asked: which source tracklet's endpoint is closer
to the right wrist and is the more plausible catch predecessor?

## Vision tool verdict (multi-evidence)

The vision tool gave a 3-evidence verdict for 20→21:

1. **Proximity**: Tracklet 20's endpoint (f=473) is essentially AT
   the right-hand catch zone. Tracklet 16's endpoint (f=468) is
   high and offset from the wrist, visibly FAR from the right
   hand.

2. **Temporal gap**: 20→21 has only a 9-frame gap (473→482);
   16→21 has a 14-frame gap (468→482). The 9-frame gap is more
   physically plausible for a continuous catch event.

3. **Trajectory continuity**: Tracklet 20's path leads naturally
   to where the right hand is at f=473, making it the credible
   predecessor of t21. Tracklet 16's trajectory ends in a region
   inconsistent with handing the ball to the right hand.

**The vision tool's verdict: 20→21 is the real catch-throw;
16→21 is not.**

## Verdict

**H22 confirmed: 20→21 is the real catch-throw.**

The h7v3plus3 chain set (which includes 20→21 and excludes 16→21)
is correct. The 2024 manual review's "correct" label on 16→21 is
**wrong** by 2026 visual standards.

## Implications

1. **The H22 visual analysis is a stronger signal than the 2024
   manual labels** for this specific case. The 2024 reviewer did
   not have access to the V-shape hand-proximity evidence that H22
   developed. The 2026 lab analysis is more rigorous.

2. **The h7v3plus3 chain set's chain quality improves by +0.0034
   on YouTube** thanks to this correction. The H10 v11 v3 quality
   score correctly identified chain 10 (containing 20→21) as
   higher-quality than the original 7-tid chain (containing 16→21).

3. **The 1 FP from H59 (identical 22→27) is the only remaining
   ground-truth conflict.** All other 51 TP match the manual
   review. The H22 conflict is the only "FN that's actually a TN"
   case — the manual review's "correct" label is wrong, not the
   h7v3plus3 operating point.

4. **H61 is a useful research artifact for the human reviewer.**
   The side-by-side contact sheet makes the conflict visually
   obvious. The human can inspect the actual frames and confirm
   the vision tool's verdict.

## Limitations

- The vision tool's verdict is consistent with H22's V-shape
  analysis (min_d=5.3 for 20→21 vs target_start_dist=35.3 for
  16→21). Both methods independently conclude 20→21 is correct.
- The 2024 manual review was done with a different methodology
  (purely visual without V-shape or hand-proximity evidence).
  The 2024 reviewer may have seen the same visual cue but
  interpreted it differently (perhaps considering 16→21 a
  "ballistic pass-through" rather than a "catch+throw").
- The 9-frame gap (20→21) is still quite short for a 5-ball
  shower hold. The H60 finding was that YouTube's median held
  phase is 9 frames, so 20→21 is exactly the typical YouTube
  hold.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h61_youtube_16_21_conflict.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_16to21_*.png` (LEFT panel)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_20to21_*.png` (RIGHT panel)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h61/youtube_16to21_vs_20to21_*.png` (combined)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h61_pair_metadata.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h61_report.md`
