# H13 v2 — Stricter H13 cluster criterion with hand-specificity filter

**Date:** 2026-08-28 ~17:30 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **NEGATIVE result**, confirms H13 v1's finding.

## Hypothesis

H13 v1's main weakness: the stationary-cluster criterion (≥3 low-conf dets
in 30px radius over ≥5 frames) fires on 3/6 v2 CORROBORATED edges that
are h7v2_kept_ballistic — true identity switches. The cluster pattern is
NOT specific to held balls because the detector can fire on two balls
in the same hand (e.g. 41→43 case with 2 balls in the right hand).

H13 v2 hypothesis: a stricter criterion that requires the cluster to be
at the EXACT hand used by the edge AND with a clean other-hand will
discriminate real catch-throws from identity switches.

## Thresholds (declared from physical geometry, NOT from manual labels)

- `STATIONARY_MAX_STD_PX = 25` (slightly tighter than H3 v3's 30)
- `OTHER_HAND_MAX_LOW_CONF = 2` (allow a few dets at the other hand)
- `HAND_REACH_PX = 108` (same as H1 v1)
- `LOW_CONF_THRESHOLD = 0.5`
- `GAP_PAD_FRAMES = 5`
- `MAX_GAP_FRAMES = 60`

The "hand" field is taken from each edge's metadata; for h7v2 edges
where hand is `left_inferred` / `right_inferred` (inferred from ball
position at gap midpoint), the other-hand check is skipped
(`other_hand_low_conf = -1`, `other_hand_clear = True`).

## Quantitative result

|| Source | n_total | STRICT_CORROBORATED | AMBIGUOUS_OTHER_HAND | NOT_CORROBORATED |
||---|---|---|---|---|
|| v4d | 11 | **0** | 0 | 11 |
|| h7v2_reclassified | 38 | 1 | 1 | 36 |
|| h7v2_kept_ballistic | 13 | **3** | 0 | 10 |

**The strict criterion FAILED to discriminate.**
- 0/11 v4d links get STRICT_CORROBORATED (v4d has more "other_hand
  low_conf" because of longer gaps → wider windows).
- 3/13 h7v2_kept_ballistic edges get STRICT_CORROBORATED:
  - 28→29 identical f=382-391 (gap=9) — confirmed identity switch
    (h8 v3 caught this)
  - 51→52 identical f=766-775 (gap=9) — confirmed identity switch
  - 41→43 identical f=608-621 (gap=13) — confirmed identity switch
    (this is the "2 balls in one hand" case)
- 1/38 h7v2_reclassified edge (45→46 identical) gets
  STRICT_CORROBORATED — this is the only true-positive corroboration
  in the entire 62-edge sample.

The h7v2_kept_ballistic STRICT_CORROBORATED rate (3/13 = 23%) is
higher than the h7v2_reclassified rate (1/38 = 2.6%). The criterion
is actively MIS-calibrated: it correlates with "identity switch" not
"real catch-throw".

## Why the strict criterion failed

The "other_hand_clear" check requires the OTHER hand to have
≤2 low-conf dets in the search window. The window is gap+10 frames
wide; for an identical-video frame range, the detector fires on
background features at 0.3-0.5 Hz on each hand. So the other-hand
window almost always has ≥2 dets. The filter has very low specificity.

For the h7v2_kept_ballistic edges (inferred hand), the other-hand
check is skipped, so they default to "other_hand_clear=True". This
explains why they get STRICT_CORROBORATED more often: the filter
that would have caught them is disabled.

For the v4d edges (known hand), the other-hand check is enabled,
and the criterion is too strict. 11/11 v4d links are NOT_CORROBORATED
even though all 11 are visually-confirmed real catch-throws.

## Verdict: **NEGATIVE**

**The detector's low-confidence signal is fundamentally NOT a
discriminator for catch-throws vs identity switches.** This is
the same conclusion as H13 v1 but reached via a more aggressive
filter.

Three separate approaches (v1 single-detection, v2 stationary-cluster,
v3+v4 concentration, v2 strict cluster) all fail to discriminate.
The reason is structural: the detector's low-confidence tier is a
noisy signal at the hand region for *any* event (real catch, identity
switch, multi-ball merge, ball passing through), and the event-level
context (which hand, which ball, in/out of hand) is required to
interpret it correctly. The detector alone cannot provide this
context.

**Implication for master §14**: the "lower-confidence evidence tier
only near an active hand event" idea is *not implementable* with
detector signal alone. A future implementation would need to combine
the detector signal with the v4d / h7v2 hand-event logic — but that
is circular, since the hand-event logic is what we're trying to
corroborate.

## Sensitivity

The strict criterion's `STATIONARY_MAX_STD_PX = 25` is slightly
tighter than H3 v3's 30. A looser setting would admit more v4d
links as STRICT_CORROBORATED but also more kept_ballistic edges
(worse). The (25, 2) operating point is at a near-flat boundary.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13v2_strict_corroboration.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13v2_summary.json`

## See also

- `h13_report.md` — v1 (looser stationary cluster criterion, also NEGATIVE)
- `RESEARCH_NOTES.md` §28-32 — H10/H11/H12 insights
