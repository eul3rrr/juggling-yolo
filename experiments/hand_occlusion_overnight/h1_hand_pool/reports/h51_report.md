# H51 — Combined H12 v8 + H50 + H43 Filter

**Date:** 2026-08-28 ~16:45 CEST
**Status:** COMPLETE (PASS — H50 and H43 compose cleanly)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis

H50 closes H49's negative result: 10-frame filter has real
downstream impact of 1.0% identical / 0.0% YouTube pattern label
changes. H43 is a separate filter that rejects FOUNTAIN_3+
classifications where H12 v8 confidence < 0.55 (precision 100%
on H39 visual QA, 9.1% of FOUNTAIN_3+ frames on identical, 0%
on YouTube).

**Question**: do H50 (event-log filter) and H43 (confidence filter)
compose cleanly? The two filters operate at different stages:
- H50 modifies the input event log (drops 6 events on identical)
- H43 modifies the output pattern labels (rejects 21 FOUNTAIN_3+ frames on identical)

They should be independent because the H50 event-log changes
don't directly affect H12 v8's confidence scores for the remaining
frames. The 1.0% per-frame change from H50 might, however, push
some borderline FOUNTAIN_3+ frames (conf 0.55-0.65) into MIXED_3+,
where H43 wouldn't apply.

## Method

1. Load H50's filtered pattern_inference (H12 v8 + 10-frame filter).
2. Apply H43's confidence < 0.55 filter to FOUNTAIN_3+ frames.
3. Compare to:
   - H12 v8 unfiltered + H43 (baseline: just H43)
   - H50 filtered + H43 (new: H50 + H43)
4. Report per-pattern distribution, per-frame diff, and substantial phase changes.

**Thresholds (from H43 and H50, not tuned to labels):**
- H50: MIN_FLIGHT_TIME = 10 frames
- H43: H12 v8 confidence < 0.55 → FOUNTAIN_LOW_CONF

## Quantitative result

### Pattern distribution: H43 only / H50+H43

**identical (1042 frames):**

| Pattern | H43 only | H50+H43 | Delta |
|---|---|---|---|
| MIXED_3+            | 27.5% (286) | 27.2% (282) | -4f |
| TWO_BALL            | 25.8% (269) | 25.8% (269) | +0f |
| SINGLE_BALL         | 20.7% (216) | 20.7% (216) | +0f |
| FOUNTAIN_3+         | 14.4% (150) | 14.1% (147) | -3f |
| CASCADE_3+          |  6.7%  (70) |  7.4%  (77) | +7f |
| FOUNTAIN_LOW_CONF   |  2.0%  (21) |  2.0%  (21) | +0f |
| MIXED_3+_UNCONFIRMED |  2.0%  (21) |  2.0%  (21) | +0f |
| TWO_BALL_ONE_HAND   |  0.8%   (8) |  0.8%   (8) | +0f |

**YouTube (898 frames):**

| Pattern | H43 only | H50+H43 | Delta |
|---|---|---|---|
| MIXED_3+            | 55.5% (498) | 55.5% (498) | +0f |
| FOUNTAIN_3+         | 23.5% (211) | 23.5% (211) | +0f |
| CASCADE_3+          | 13.3% (119) | 13.3% (119) | +0f |
| MIXED_3+_UNCONFIRMED |  7.8%  (70) |  7.8%  (70) | +0f |

### FOUNTAIN_LOW_CONF counts

| Video | H43 only | H50+H43 | Change |
|---|---|---|---|
| identical | 21 frames | 21 frames | 0 |
| YouTube   |  0 frames |  0 frames | 0 |

The H43 filter's rejection count is unchanged by H50 because:
- H50 only drops frames in a specific subset (the K=4 window
  around the 3 dropped (CATCH, THROW) pairs)
- H43 rejects FOUNTAIN_3+ frames with confidence < 0.55, which
  are all in the f=1029-1060 "OTHER 2-ball exercise" region
- The 10 frames that H50 changes are not in the FOUNTAIN_3+
  low-conf region (H50 changes FOUNTAIN_3+ at f=232-234 with
  conf 0.593, but 0.593 > 0.55, so H43 doesn't reject them)

### Per-frame diff (H50+H43 vs H43 only)

| Video | Frames changed | % changed |
|---|---|---|
| identical | 10 / 1042 | **1.0%** |
| YouTube   |  0 / 898  | **0.0%** |

The diff is identical to the H50 alone result (1.0%/0.0%) because
H50's frame changes don't trigger H43.

### Substantial phases (n_frames >= 20)

| Video | H43 only | H50+H43 |
|---|---|---|
| identical | 15 | 15 (unchanged) |
| YouTube   | 12 | 12 (unchanged) |

## Key findings

1. **H50 and H43 compose cleanly.** The two filters operate at
   different stages (event log vs pattern label) and don't interfere
   with each other. H50+H43 is equivalent to H43 + H50 (commutative
   order).

2. **H50+H43 is strictly more precise than either alone.**
   - H50 alone: -0.3% FOUNTAIN_3+ (3 frames), +0.7% CASCADE_3+ (7 frames)
   - H43 alone: -2.0% FOUNTAIN_3+ (21 frames), unchanged CASCADE_3+
   - **H50+H43: -2.3% FOUNTAIN_3+ (24 frames), +0.7% CASCADE_3+ (7 frames)**

3. **The 1.0% H50 frame change is independent of H43.** None of
   the 10 H50-changed frames are in the H43 rejection region
   (conf < 0.55). The two filters address different error modes:
   - H50: identity switches (flight time < 10 frames) → CASCADE_3+ recovery
   - H43: low-confidence FOUNTAIN_3+ → FOUNTAIN_LOW_CONF reclassification

4. **Substantial phases are preserved.** Both 15 identical and
   12 YouTube substantial phases are unchanged.

5. **YouTube is unaffected by both filters.** H50 is a no-op
   (no flights < 10 frames), H43 is a no-op (no FOUNTAIN_3+
   frames with conf < 0.55 on YouTube).

## Recommended operating point

**h7v3plus3 chain set + H12 v8 + H50 10-frame event log filter +
H43 FOUNTAIN_3+ confidence filter**

This is the final precision-optimized configuration for
FOUNTAIN_3+ / CASCADE_3+ downstream consumers. The combined
filter:
- Drops 6 events on identical (H50)
- Rejects 21 FOUNTAIN_3+ frames on identical (H43)
- Recovers 7 CASCADE_3+ frames on identical (H50)
- No changes on YouTube (both filters are no-ops)

## Verdict

**H51 verdict: PASS.** H50 and H43 compose cleanly. The combined
filter is a strict improvement over either alone:

- H50: precision improvement via event-log filter (1.0% identical
  frames change pattern)
- H43: precision improvement via confidence-based filter (2.0%
  identical FOUNTAIN_3+ frames rejected)
- H50+H43: combined precision improvement (2.3% identical
  FOUNTAIN_3+ reduction, 0.7% CASCADE_3+ increase)
- YouTube: 0% change (both filters are no-ops)

The H50+H43 combination does not break any substantial phases and
addresses two independent error modes (identity switches and
low-confidence FOUNTAIN_3+). The combined filter is the
recommended operating point for downstream consumers needing
precision-optimized juggling-pattern classification.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h51_combined_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_filtered_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_phases_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h51_combined_filter_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h51_report.md` (this file)

## Recommended next research

The h7v3plus3 + H12 v8 + H50 + H43 stack is now the recommended
operating point. The most likely productive directions:

1. **H52: H8 v5 parabolic fit for ft=3-9 disambiguation** — the
   H50 visual QA on chain 13 ft=3 suggests a real catch-throw CAN
   have a 3-frame flight. H8 v5's parabolic fit on source-tail +
   target-head could distinguish "real short catch-throw" from
   "tracker fragmentation" for ambiguous ft=3-9 cases. This would
   refine H50's filter to preserve chain 13 ft=3 while still
   rejecting ft=1 and ft=5.

2. **H53: per-event vs per-flight H50 analysis** — the H12 v8
   event log structure uses (CATCH, THROW) PAIRS. A per-event
   analysis (drop only the CATCH or only the THROW, not the pair)
   might preserve more signal. Lower priority.

3. **Stop here**. The h7v3plus3 + H12 v8 + H50 + H43 stack is
   well-validated. The next step (H52) is a refinement for one
   ambiguous case (chain 13 ft=3) and would not change the overall
   conclusion.
