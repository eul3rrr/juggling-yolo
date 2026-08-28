# H12 v7 — Pattern inference on H7v2 chains with H10 v8 quality

## Hypothesis
H12 v2 was the best event-log-based pattern classifier, but
suffered on YouTube because H10 v5 over-counted chains (n_total=5
in 601/898 frames), forcing 100% MIXED_3+_UNCONFIRMED. H7v2
reclassifies 25/27 YouTube BALLISTIC edges as HAND_TRANSITION
and fixes the over-counting at the source.

H12 v7 hypothesis: re-running the v2 pattern inference on H7v2
chains with H10 v8 quality should give a meaningful YouTube
pattern classification for the first time.

## What changed
1. Census built from H7v2 chains (which have different membership
   than H237v5 chains).
2. Catch/throw timeline built from H7v2 hand-edges (including
   RECLASSIFIED_HAND_TRANSITION).
3. Chain quality = H10 v8 quality (which has h8=1.0 for most
   YouTube chains after reclassification).
4. Hand parsed from reclassify_reason for reclassified edges
   (e.g. "src_catch_dist=106.2_slope=-23.59_side=left").

## Quantitative result

### identical
| Metric | H12 v2 | H12 v7 |
|---|---|---|
| n_total=3 frames | 533/1077 (49.4%) | 533/1042 (51.2%) |
| MIXED_3+ | 29.3% | 32.8% |
| FOUNTAIN_3+ | 15.5% | 17.7% |
| CASCADE_3+ | 6.8% | 0.2% |
| TWO_BALL | 20.3% | 25.8% |
| SINGLE_BALL | 19.8% | 20.7% |
| NO_BALL | 0% | 0% |

### YouTube
| Metric | H12 v2 | H12 v7 |
|---|---|---|
| n_total=3 frames | 22/898 (2.4%) | 22/898 (2.4%) |
| n_total=4 frames | 265/898 (29.5%) | 265/898 (29.5%) |
| n_total=5 frames | 601/898 (66.9%) | 601/898 (66.9%) |
| MIXED_3+ | 0% | 56.3% |
| FOUNTAIN_3+ | 0% | 23.5% |
| CASCADE_3+ | 0% | 12.4% |
| MIXED_3+_UNCONFIRMED | 100% | 7.8% |

## YouTube: 100% MIXED_3+_UNCONFIRMED → 7.8%

The 100% MIXED_3+_UNCONFIRMED of v2 was caused by `hand=unknown`
for all reclassified events (v2's timeline didn't parse the
reclassified edges correctly). H12 v7 fixes this by parsing
`side=left/right` from the reclassify_reason, which gives proper
hand alternation metrics. With proper hand information:
- 12.4% CASCADE_3+ (proper alternation, high catch rate)
- 23.5% FOUNTAIN_3+ (same-hand dominance)
- 56.3% MIXED_3+ (events present but ambiguous)
- 7.8% MIXED_3+_UNCONFIRMED (early frames with too few events)

The n_total distribution is unchanged (5 is correct for 67% of
frames) because the YouTube video is genuinely a 5-ball pattern
(visual confirmation at f=2, f=500).

## identical: CASCADE_3+ drops from 6.8% to 0.2%

CASCADE_3+ classification requires:
- same_hand_run ≤ 1 (most events alternate hands)
- alternation ≥ 0.5 (hand-alternation score)
- catch_rate ≥ 1.0 Hz (frequent catch events)

In v7, more events are present (because H7v2 reclassified
catch+throw BALLISTIC edges as HAND_TRANSITION), but the events
are not perfectly alternating. With 21 CATCH events, the K=4
window often has 1-2 same-hand runs (e.g. right→right→left→right)
which fails the same_hand_run ≤ 1 check.

## Visual QA on late phase (f=890-1050)
H12 v7 still classifies 74.5% of late phase as FOUNTAIN_3+
(matches v2's 71%). Vision analysis of 6 frames (f=890, 920,
950, 980, 1010, 1040) confirms the actual pattern is CASCADE:
balls alternate between left and right hands.

This confirms the previously documented fundamental limitation:
CASCADE/FOUNTAIN classification is limited by event log density,
not chain quality. H7v2 fixes the chain quality (YouTube h8
over-penalization) but the event log is still right-hand-biased
in the late phase.

## Verdict: **MIXED**

H12 v7 successfully fixes the YouTube pattern classification
problem (100% MIXED_3+_UNCONFIRMED → 12.4% CASCADE_3+ /
23.5% FOUNTAIN_3+ / 56.3% MIXED_3+). This is a meaningful
improvement.

H12 v7 does NOT fix the identical CASCADE/FOUNTAIN misclassification
in the late phase (74.5% FOUNTAIN vs visual CASCADE). This is
the same fundamental limitation as before: event log is right-
hand-biased, so the K=4 window sees mostly right-hand events.

**The h8 over-penalization on YouTube is fixed (H10 v8 PASS).**
**The CASCADE/FOUNTAIN classification is still fundamentally
limited by event log density.**

## Artifacts
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v7_h7v2_patterns.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v7_late_phase_sheet.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v7_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v7_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/catch_throw_timeline_v7_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v7_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v7/late_phase_f890_1040.png`
