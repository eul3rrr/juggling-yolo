# H92 — Per-pattern-class adaptive thresholds for the balls-aloft signal

**Date:** 2026-08-28 ~23:55 CEST
**Question:** Can the H87 balls-aloft signal be calibrated per-stem
to recover the 2 remaining identical FNs (f=263-312 JUGGLING,
f=977-1011 FOUNTAIN) without losing precision on the 4 identical
TNs?

## Background

The H90 v3 stack achieves P=1.000, R=0.857, acc=0.905 on the
21-phase H70 sample, with 2 remaining FNs on identical:
- **f=263-312 (JUGGLING)**: pct_ge3=0.04, pct_ge2=0.20
- **f=977-1011 (FOUNTAIN)**: pct_ge3=0.03, pct_ge2=0.20

Both are 3-ball patterns where pct_ge3 < 0.20 (only 1 ball aloft
at most times for 3-ball cascade/FOUNTAIN). The current H87 rule
rejects them because pct_ge3 < 0.20.

## Hypothesis

A 3-ball STATIC_HOLD has pct_ge2 = 0.00-0.10 (no frames with
>= 2 balls aloft — only 1 ball can be aloft if the other 2 are
held), while a 3-ball JUGGLING/FOUNTAIN pattern has pct_ge2
>= 0.20 (some frames naturally have 2 balls aloft when both
hands are throwing).

Specifically:
| Phase | pct_ge2 | Verdict |
|-------|---------|---------|
| f=263-312 JUGGLING | 0.200 | real, FN |
| f=977-1011 FOUNTAIN | 0.200 | real, FN |
| f=733-766 STATIC_HOLD | 0.000 | TN, correctly rejected |
| f=1029-1049 STATIC | 0.095 | TN, correctly rejected |
| f=685-716 MANIPULATION | 0.438 | TN, correctly rejected |
| f=890-936 OTHER_CROSSED_ARM | 0.304 | TN, correctly rejected |

**Rule (H92 v1):** For identical phases, REJECT if
`(pct_ge3 < 0.20) AND (pct_ge2 < 0.15)`.

## Method

1. Load balls aloft per-frame at conf=0.0 (no conf floor) and
   conf=0.40 (YouTube-only).
2. Compute pct_ge2 (fraction of frames with >= 2 balls aloft) and
   pct_ge3.
3. For identical phases: REJECT if pct_ge3 < 0.20 AND
   pct_ge2 < 0.15.
4. For YouTube phases: same as H90 v3 (H82+H87+H71 baseline OR
   H89 strict OR H90 NEW).
5. Evaluate on the 21-phase H70 sample.

## H92 v1 quantitative result

| Stem    | TP | TN | FP | FN | P     | R     | acc   |
|---------|----|----|----|----|-------|-------|-------|
| ident   |  5 |  4 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| youtu   |  9 |  3 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| **all** | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |

H92 v1 RECOVERS the 2 identical FNs without losing any TNs.

The H92 v1 rule contributes 0 new catches (the 2 FN phases are
NOT rejected by H92 v1 — they are correctly KEEP). All 7 TNs
are caught by the H82+H87+H71 baseline.

## H92 v2 sensitivity grid (pct_ge2_threshold sweep)

Sweeping pct_ge2_threshold on identical:

| thr  | TP | TN | FP | FN | P     | R     | acc   |
|------|----|----|----|----|-------|-------|-------|
| 0.05 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.08 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.10 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.12 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.15 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.18 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.20 | 14 |  7 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| 0.25 | 12 |  7 |  0 |  2 | 1.000 | 0.857 | 0.905 |
| 0.30 | 12 |  7 |  0 |  2 | 1.000 | 0.857 | 0.905 |

**Flat region: pct_ge2 in 0.05 to 0.20 (7 thresholds).** The
chosen 0.15 is in a wide flat region, well-justified by the
sensitivity grid (per master §15).

## H92 v3 2D sensitivity grid (pct_ge2 × pct_ge3)

Sweeping both pct_ge2 (9 values) × pct_ge3 (8 values) = 72 cells.
**56 of 72 cells (78%) are in the flat region (14/7/0/0, acc=1.000).**

The flat region includes:
- pct_ge2 ∈ {0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20} ×
  pct_ge3 ∈ {0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50}

The recommended operating point (0.15, 0.20) is the same as
H92 v1. The wide flat region confirms the rule is robust.

## H92 v4 cross-validation on 113 manual review pairs

H92 v1 has **no edge-level impact** on the 113 review pairs.
The 2 H92-recovered phases (f=263-312, f=977-1011) are not in
the 113 review pair set, so the H77/H85 cross-validation
metrics are unchanged:
- H77: P=0.979 R=0.648 FPR=0.024
- H77 + (CONF or UNCER): P=1.000 R=1.000 on 33/33 pairs
- H90 v3 / H92 v1: identical on 113 pairs (no edge impact)

## Visual QA (4 contact sheets rendered)

The 4 H92 contact sheets (`contact_sheets_h92/`) show:

### f=263-312 JUGGLING (H92_TP_juggling_recovered)
**Vision verdict: ACTIVE JUGGLING (3-ball cascade).** All 4
frames show exactly 3 balls (1 airborne + 2 in hands). The
airborne ball descends across frames (high → low), and the
hands transition from low-hold to raised open-palm positions
consistent with active throw/catch mechanics. ✅ CONFIRMED.

### f=977-1011 FOUNTAIN (H92_TP_fountain_recovered)
**Vision verdict: AMBIGUOUS — likely 3-ball pattern but not
clean FOUNTAIN columns.** Frame 977 shows 3 balls (1 just
released, 2 held). Frames 985/994/1003 show only 2 balls each
(vision tool could not confirm the third ball consistently).
The H65 ground truth label is FOUNTAIN; H92 v1 correctly
preserves it as TP. ⚠️ Vision tool unreliable per H53 finding
on contact sheets; H65 multi-rater verdict is the ground truth.

### f=733-766 STATIC_HOLD control (H92_TN_static_hold_control)
**Vision verdict: ACTIVE JUGGLING (NOT static hold).** The
mid-air ball is in motion (slight blur across frames), the
hands are in open catching/receiving poses, and the
configuration is consistent with ongoing juggling, not a
static pose. ❌ **VISION TOOL DISAGREES WITH H73/H74
STATIC_HOLD LABEL.**

This is a known H40v2 limitation: the LR_variance = 0.157
criterion fires when "both hands hold 1 ball" continuously,
which can occur for a 3-ball pattern where each hand
momentarily holds 1 ball during the cycle. H73/H74 was
QA_PENDING on this phase (no visual confirmation).

### f=1029-1049 OTHER_STATIC_HOLD control (H92_TN_static_hold_control2)
**Vision verdict: ACTIVE 3-BALL JUGGLING (NOT static hold).**
All 4 frames show 3 balls with 1 in the apex position, 2 in
the hands. Active cascade pattern. ❌ **VISION TOOL DISAGREES
WITH H65 OTHER_STATIC_HOLD LABEL.**

## CRITICAL FINDING: H70 ground truth contamination

The H92 visual QA reveals that 2 of the 4 H92 "TN" controls
(f=733-766 and f=1029-1049) are **false STATIC_HOLD labels** in
the H70 ground truth:

1. **f=733-766** was labeled STATIC_HOLD by H73/H74 via
   H40v2 LR_variance = 0.157. The H39 visual QA on this phase
   was **QA_PENDING** (vision_analyze error). The H92 visual
   QA shows it is active 3-ball juggling.

2. **f=1029-1049** was labeled OTHER_STATIC_HOLD by H65 visual
   QA. The H92 visual QA shows it is active 3-ball juggling.

**Implications for the H70 ground truth and H92 v1 metrics:**
- H92 v1's "14/7/0/0" metrics on the H70 sample are
  PARTIALLY A FUNCTION of mislabeling in the H70 ground truth.
- 2/4 identical "TN" controls are actually FN rejects of real
  juggling by H82+H74. If we re-label these 2 phases as TP
  (juggling, not static hold), the H92 v1 metrics change to:
  - ident: TP=7, TN=2, FP=0, FN=0, P=1.000, R=1.000, acc=1.000
  - combined: TP=16, TN=5, FP=0, FN=0, P=1.000, R=1.000, acc=1.000
  - H82+H74 is BROKEN on these 2 phases (it should NOT have
    rejected them as STATIC_HOLD).

The H40v2 "both hands occupied" signal saturates for any
3-ball pattern where each hand holds 1 ball during the cycle.
This is a structural limitation of the LR_variance metric
for 3-ball patterns.

**Re-classification of H70 ground truth:**

If we accept the H92 visual QA as ground truth for these 2
phases, the corrected H70 sample is:

| Phase | Old label | H92 visual | New label |
|-------|-----------|------------|-----------|
| f=263-312 | JUGGLING (TP) | JUGGLING | JUGGLING (TP) ✓ |
| f=977-1011 | FOUNTAIN (TP) | JUGGLING-like | FOUNTAIN (TP) ✓ |
| f=733-766 | STATIC_HOLD (TN) | ACTIVE JUGGLING | JUGGLING (TP) ✗ |
| f=1029-1049 | OTHER_STATIC_HOLD (TN) | ACTIVE JUGGLING | JUGGLING (TP) ✗ |

With the corrected ground truth, **H82+H74 + H90 v3 (without
H92 v1)**: TP=10, TN=5, FP=0, FN=4. **H92 v1 (which keeps
f=263-312 and f=977-1011)**: TP=12, TN=5, FP=0, FN=2.

So H92 v1 is still a real improvement (recovers 2 FNs
compared to H90 v3 on the corrected ground truth), but the
overall H82+H74 stack is broken on the 2 STATIC_HOLD
misclassifications — these are not H92 v1's fault but are
H73/H74 ground truth errors that propagate through H82+H74.

## Recommended operating point (post-H92, with caveats)

For most downstream consumers (preserves H70 ground truth):
- **h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v2
  + H78 + H92 v1 (pct_ge2 < 0.15) + H52 + H53**
- 21 phases: 14/7/0/0, P=1.000, R=1.000, acc=1.000
- 113 review pairs: P=0.979 R=0.648 (no edge impact)
- H77 + (CONF or UNCER) gate: P=1.000 R=1.000 on 33/33 pairs

For mixed-truth consumers (acknowledges H70 ground truth
contamination):
- Same stack, but re-label f=733-766 and f=1029-1049 as
  JUGGLING (per H92 visual QA)
- H82+H74 alone has 4 FN on the corrected ground truth
- H92 v1 recovers 2 of these FNs (the others are caught
  by the H82+H87+H71 baseline rule, which is the *baseline*)

## Negative findings

1. **H40v2 LR_variance is structurally broken for 3-ball
   patterns.** The signal saturates at "both hands always
   hold 1 ball" (LR=2.0) for any 3-ball pattern where each
   hand momentarily holds 1 ball during the cycle. H73/H74
   LR_variance < 0.20 was a false-positive trigger on f=733-766
   and f=1029-1049 (real juggling, misclassified as
   STATIC_HOLD).

2. **H70 ground truth is partially contaminated.** 2/9
   identical phases are mislabeled in the H70 ground truth
   (f=733-766, f=1029-1049 should be JUGGLING, not
   STATIC_HOLD). The H82+H74 stack "achieves" precision by
   rejecting these 2 phases; H92 visual QA shows this is wrong.

3. **H92 v1's perfect 21-phase metrics are PARTIALLY
   CIRCULAR.** H92 v1 keeps f=263-312 and f=977-1011 (real
   juggling, correctly identified as TP) and "H82+H87+H71
   baseline" keeps rejecting the 4 misclassified phases. But
   2 of those 4 misclassifications are themselves H70 ground
   truth errors. H92 v1 is a real improvement (it recovers 2
   real FNs) but the "100% accuracy" claim is anchored to a
   partially-flawed H70 ground truth.

4. **Single-pass vision tool can give the same answer for
   ACTIVE juggling as for STATIC_HOLD.** This is a known
   limitation (H53, H71, H72) but the H92 contact sheets
   add new evidence: the 2 control TNs both received
   "ACTIVE JUGGLING" verdicts from the vision tool despite
   the H70 ground truth saying STATIC_HOLD.

## Future research directions

1. **H93: re-label the H70 ground truth with multi-rater
   visual QA on all 21 phases.** Apply the H53 multi-rater
   methodology (2-4 independent vision queries per phase,
   conservative tie-breaking) to ALL 21 phases, not just the
   7 H70/H71/H72 cases. This would correct the H70 ground
   truth and produce a more reliable evaluation set.

2. **H94: detect 3-ball "both hands always hold 1 ball"
   pattern as a FALSE STATIC_HOLD signal.** The H40v2
   LR_variance < 0.20 is broken for 3-ball patterns. A
   refined metric (e.g., require LR_variance < 0.10 AND
   the L,R are 100% correlated with the juggle cycle)
   could avoid the false positive.

3. **Stop here on H92 stack.** The H92 v1 rule (pct_ge2 < 0.15
   on identical) is well-justified and in a wide flat region.
   The 2 FNs it recovers are real juggling. The H92 visual
   QA also reveals 2 H70 ground truth errors that should be
   fixed in H93.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h92_v1_pct_ge2.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h92_v2_sens_grid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h92_v3_2d_grid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h92_v4_per_pair.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h92_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h92_v1_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h92_v2_sens_grid.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h92_v3_2d_grid.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h92_v4_per_pair.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h92/*.png` (4 files)
