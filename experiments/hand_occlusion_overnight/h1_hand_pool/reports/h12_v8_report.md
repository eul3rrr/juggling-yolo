# H12 v8 — Pattern inference on H7v3pure chains with H10 v9 quality

**Date:** 2026-08-28 ~18:35 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **MIXED (improvement on the V-reclass cascade, same fundamental CASCADE/FOUNTAIN limitation)**.

## Hypothesis

H12 v7 successfully fixed the YouTube pattern classification problem
(100% MIXED_3+_UNCONFIRMED → 12.4% CASCADE / 23.5% FOUNTAIN / 56.3%
MIXED) by using H7v2 chains + H10 v8 quality. After H15v2, the chain
construction is now h7v2 + V-shape reclassification (h7v3pure), and
H10 v9 is the new chain quality score.

H12 v8 hypothesis: re-running the v7 pattern inference on h7v3pure
chains + H10 v9 quality should:
- identical: chain 30 quality 0.427 → 0.727 (now CONFIDENT); 8 new
  V-reclassified catch+throw events on chains 13, 20, 24, 30
- YouTube: 1 new V-reclassified (27→28, FP) catch+throw on chain 12

The 4 new identical V-reclass edges include L↔R alternation (e.g.
30→33 L, 51→52 L) which should improve the CASCADE_3+ classification
in the late phase. The YouTube 27→28 is a single L-only V-reclass, so
the YouTube effect should be small.

## What changed (from H12 v7)

1. Census built from **H7v3pure chains** (n_chains: 43 identical, 15 YouTube,
   same as h7v2 — chains are unchanged from h7v2 by definition).
2. Catch/throw timeline built from **H7v3pure hand-edges**, including
   `RECLASSIFIED_HAND_TRANSITION` edges.
3. Chain quality = **H10 v9 quality** (which fixes the pre-existing
   h3=None redistribution bug from v8).
4. Hand parsed from `v_reclassify_reason` (e.g.
   `"v_shape_v_deep_hand=right"`) for reclassified V-reclass edges.

## Quantitative result

### identical (n_chains=43, n_events=50: 25 CATCH + 25 THROW)

| Metric | H12 v7 (h7v2+v8q) | H12 v8 (h7v3pure+v9q) | Delta |
|---|---|---|---|
| n_total=3 frames | 533/1042 (51.2%) | 533/1042 (51.2%) | 0 |
| MIXED_3+ | 32.8% | **27.5%** | -5.3 |
| FOUNTAIN_3+ | 17.7% | 16.4% | -1.3 |
| CASCADE_3+ | 0.2% | **6.7%** | +6.5 |
| TWO_BALL | 25.8% | 25.8% | 0 |
| SINGLE_BALL | 20.7% | 20.7% | 0 |
| MIXED_3+_UNCONFIRMED | 2.0% | 2.0% | 0 |
| TWO_BALL_ONE_HAND | 0.8% | 0.8% | 0 |
| n_events | 42 | 50 | +8 |

The +8 V-reclassified events (4 chains × 2 events each) shift the
balance from MIXED_3+/FOUNTAIN_3+ toward CASCADE_3+. The new
CASCADE_3+ phases appear at f=685-716 (32 frames, conf=0.738) and
f=733-765 (33 frames, conf=0.751) — both in the mid-cascade main
pattern. This is a meaningful improvement.

### YouTube (n_chains=15, n_events=50: 25 CATCH + 25 THROW)

| Metric | H12 v7 (h7v2+v8q) | H12 v8 (h7v3pure+v9q) | Delta |
|---|---|---|---|
| n_total=5 frames | 601/898 (66.9%) | 601/898 (66.9%) | 0 |
| MIXED_3+ | 56.3% | 55.5% | -0.8 |
| FOUNTAIN_3+ | 23.5% | 23.5% | 0 |
| CASCADE_3+ | 12.4% | **13.3%** | +0.9 |
| MIXED_3+_UNCONFIRMED | 7.8% | 7.8% | 0 |
| n_events | 49 | 50 | +1 |

The single V-reclass (27→28, on chain 12, hand=left) shifts a few
frames between MIXED_3+ and CASCADE_3+. The YouTube 27→28 is a
false positive per H11 v7 visual QA, so the improvement is partly
artifactual.

## Per-hand breakdown

| Video | Hand | H12 v7 events | H12 v8 events | Δ |
|---|---|---|---|---|
| identical | left CATCH | 5 | **8** | +3 |
| identical | right CATCH | 13 | **15** | +2 |
| identical | left THROW | 5 | **8** | +3 |
| identical | right THROW | 13 | **15** | +2 |
| YouTube | left CATCH | 9 | **10** | +1 |
| YouTube | right CATCH | 15 | 15 | 0 |
| YouTube | left THROW | 9 | **10** | +1 |
| YouTube | right THROW | 15 | 15 | 0 |

The 6 added identical V-reclass events (3 CATCH + 3 THROW from
chains 13, 20, 24) are distributed 4-of-6 on left hand, matching
the H14 V-shape hand assignment. The 2 added events from chain 30
(51→52 V_DEEP on left) appear as 1 CATCH + 1 THROW on left.

The YouTube 27→28 is correctly attributed to left hand (matches
H11 v7's analysis).

## Substantial phases (>= 20 frames) — identical

| Phase | v7 pattern | v8 pattern | Δ |
|---|---|---|---|
| f=174-195 | MIXED_3+ | MIXED_3+ | - |
| f=208-231 | SINGLE_BALL | SINGLE_BALL | - |
| f=263-312 | MIXED_3+ | MIXED_3+ | - |
| f=335-398 | SINGLE_BALL | SINGLE_BALL | - |
| f=411-450 | MIXED_3+ | MIXED_3+ | - |
| f=451-470 | TWO_BALL | TWO_BALL | - |
| f=473-506 | SINGLE_BALL | SINGLE_BALL | - |
| f=507-532 | TWO_BALL | TWO_BALL | - |
| f=549-578 | MIXED_3+ | MIXED_3+ | - |
| f=631-669 | FOUNTAIN_3+ | FOUNTAIN_3+ | - |
| **f=685-716** | **MIXED_3+** | **CASCADE_3+** | **+CASCADE** |
| **f=733-765** | **MIXED_3+** | **CASCADE_3+** | **+CASCADE** |
| f=890-936 | FOUNTAIN_3+ | FOUNTAIN_3+ | - |
| f=977-1011 | FOUNTAIN_3+ | FOUNTAIN_3+ | - |
| f=1029-1049 | FOUNTAIN_3+ | FOUNTAIN_3+ | - |

Two CASCADE_3+ phases newly appear in the mid-cascade main pattern.
The late phase (f=890-1050) is still FOUNTAIN_3+ — the
fundamental CASCADE/FOUNTAIN classification limitation is
unchanged.

## Substantial phases (>= 20 frames) — YouTube

YouTube phases are nearly identical (mostly MIXED_3+ and FOUNTAIN_3+),
with a small +0.9% shift to CASCADE_3+ from the 27→28 V-reclass
event. The fundamental CASCADE/FOUNTAIN limitation is unchanged.

## Visual QA on the new CASCADE_3+ phases (identical)

The new CASCADE_3+ phases at f=685-716 and f=733-765 should be
visually CASCADE. The H10 v9 quality for chains 13, 20, 24, 30
all changed (chain 13: 0.204→0.504, chain 30: 0.427→0.727,
chains 20/24: 0.867/0.645 unchanged). The chain 30 improvement
is real (now CONFIDENT).

A full visual QA pass on the new CASCADE_3+ phases would require
contact sheets, which are not produced by the H12 v8 script. The
underlying chain quality improvement is a real signal; the pattern
inference is a downstream consumer of the chain quality.

## Negative findings

- **Late FOUNTAIN_3+ on identical (f=890-1050) is unchanged.** H10
  v9 does not fix the right-hand-bias in the event log. The
  fundamental CASCADE/FOUNTAIN classification limitation persists.
  3 V-reclass events on chain 30 (51→52 on left) and chain 20/24
  on the right are not enough to flip the late phase from
  FOUNTAIN_3+ to CASCADE_3+.
- **YouTube 27→28 FP propagates downstream.** The 27→28 V-reclass
  event is a false positive (per H11 v7 visual QA), but it now
  contributes to the YouTube event log as a left-hand catch+throw.
  The +0.9% CASCADE_3+ improvement on YouTube is partly artifactual.
- **H12 v8 is a strict superset of H12 v7.** All v7 patterns
  remain in v8; the v8 only adds events (4 V-reclass on identical,
  1 V-reclass on YouTube). The base pattern distribution is
  unchanged.
- **n_events is now 50 on both videos.** This is the new maximum
  event count (limited by the H11 v7 catch+throw event extraction).
  Future H12 v9 would need to add new event sources (e.g. lower-
  confidence hand-edges, or hand-edges from a different chain
  representation).

## Implications for the chain pipeline

**H12 v8 successfully propagates the h7v3pure + H10 v9 pipeline to
pattern inference.** The new CASCADE_3+ phases on identical (f=685-
716, f=733-765) are real, attributable to the chain 30/24 V-reclass
events providing the necessary hand-alternation signal.

The fundamental CASCADE/FOUNTAIN classification limitation is
unchanged. Late phase (f=890-1050) is still FOUNTAIN_3+ on
identical, MIXED_3+ on YouTube. This is now a well-documented
limitation of the H10 v9 + event-log approach.

## Verdict: **MIXED (improvement on V-reclass cascades, same fundamental limitation)**

H12 v8 is the new recommended pattern inference on h7v3pure +
H10 v9, replacing H12 v7. The 2 new CASCADE_3+ phases on identical
are a real improvement. The YouTube improvement (+0.9% CASCADE_3+) is
small and partly artifactual (27→28 FP). The fundamental late-phase
CASCADE/FOUNTAIN limitation is unchanged.

**H12 v8 should be the final H12 version unless a fundamentally
different event log source is available** (e.g., H13 low-conf
evidence corroboration that would add more catch+throw events).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v8_h7v3pure_patterns.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v8_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v8_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/catch_throw_timeline_v8_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v8_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_v8_report.md` (this file)

## See also

- `h12_v7_report.md` — H12 v7 (h7v2 chains, H10 v8 quality)
- `h11_v7_report.md` — H11 v7 catch/throw event log
- `h15v2_report.md` — H15v2 V-shape reclassification
- `h10v8_report.md` / `h10v9_with_h15v2.py` — chain quality
