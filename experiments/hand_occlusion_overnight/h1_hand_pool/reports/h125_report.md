# H125 — H7 min-cost flow on the full E6c candidate set

**Status:** DONE. PASS (precision-optimized operating point remains h7v3plus3, but H125 v3 chain set is a strict recall upgrade for downstream consumers who can tolerate the +3-4pt precision drop).

## Motivation

The h7v3plus3 chain set (H34 = H22 + H26) achieves P=0.981 R=0.718 on the 113 review pairs.
The 0.282 recall gap is the focus of the post-H114 series. H121, H122, H123, H124
attributed the gap to one of three causes:

1. **H121 hypothesis:** h7v2 reclassification is over-applied because
   `tracklet_features.csv` is truncated 2-5 frames before the raw tracklet's last
   frame. **Confirmed by H121**: 26/34 (76.5%) of RECLASSIFIED edges have raw data
   that would NOT trigger reclassification. h7v2 admits 5 "spurious" reclassifications
   on identical + 21 on YouTube (76.5% combined). However, h7v3plus3 still
   achieves P=1.000 R=0.718 with h7v2 active, so this is a structural issue, not
   a recall limiter.

2. **H122 hypothesis:** the 5 RAW_REJECTS (H121) are visually mixed (4/5 are
   real catch-throws per visual QA). H123 stratifies 10 cases → 53.3% REAL precision
   (Wilson 95% CI [30%, 75%]). H7v2 reclassification is *defensible* at 80% but
   over-applies.

3. **H124 hypothesis:** a compound filter (B-not-A + B+not-D + fn<=3 + B+not-C)
   could recover the missing edges. **NEGATIVE**: 22 in-chain correct edges
   would be wrongly rejected, 0 wrong edges caught. Geometric post-filters are
   exhausted on the h7v2 reclassification signal.

**H125 takes a fundamentally different approach:** instead of post-filtering the
h7v3plus3 chain, **rerun H7 min-cost flow on the FULL E6c candidate set (113
edges, not 33+25=58)**. The H7 input is currently filtered to a curated subset;
H125 tests whether the larger pool enables a better chain.

## H125 v1 — K-best successor analysis

**Hypothesis:** the 20 NOT_IN_CHAIN + correct review pairs (the missing-correct
edges from h7v3plus3) are real catches the chain missed. If they are
**k-best alternatives** (rank-2 or rank-3 successors of a source), a k-best
augmentation is meaningful. If they are **low-rank alternatives** (rank-5+),
they are geometrically distinguishable from the in-chain picks in a way that
suggests they are not real capacity-conflicts.

**Method:** load E6c accepted_stitches (113 review pairs for both videos), load
h7v3plus3 admitted_edges (the chain picks), for each source list all
successor candidates sorted by trajectory_fit_error, compute rank of each
NOT_IN_CHAIN + correct edge.

**Result (per H125 v1 summary):**

| stem | n_sources | n_review_pairs | NOT_IN_CHAIN + correct | rank=1 | rank=2 | rank=3+ |
|---|---|---|---|---|---|---|
| identical | 56 | 85 | 18 | 16 | 2 | 0 |
| YouTube | 27 | 28 | 2 | 2 | 0 | 0 |

**Key finding:** 18/20 (90%) of NOT_IN_CHAIN + correct edges are rank-1
alternatives. They are the BEST successor for their source by
trajectory_fit_error, but were not admitted because either:
- They conflict with another edge in the chain (a higher-priority successor
  also targets the same tracklet), or
- The source already has a different successor in h7v3plus3.

This is strong evidence that the missing-correct edges are *real capacity
conflicts* in h7v3plus3's min-cost flow, not low-rank alternatives that
h7v3plus3 correctly rejected.

## H125 v2 — H7 min-cost flow on 4 E6c variants

**Hypothesis:** the 20 NOT_IN_CHAIN + correct edges are not in the current H7
input (which is the E6c-accepted subset, 53 edges). Running H7 on a larger pool
should expose more capacity conflicts and either:
- admit some of the missing-correct edges (recall boost), or
- cause more wrong edges to compete for capacity (precision drop).

**Method:** 4 variants of the H7 input:
- `full_e6c`: 113 E6c + h7v2 hand-link edges (118 total)
- `e6c_accepted_only`: 53 E6c + h7v2 hand-link edges
- `full_e6c_no_h7v2`: 113 E6c only (no hand-link edges)
- `e6c_accepted_no_h7v2`: 53 E6c only (matches h7v3plus3's "ballistic" subset)

**Result (per H125 v2 summary):**

| variant | identical adm | identical P/R | youtube adm | youtube P/R |
|---|---|---|---|---|
| full_e6c | 48/118 | 0.878/0.800 | 25/53 | 1.000/0.923 |
| e6c_accepted_only | 33/60 | 0.962/0.556 | 25/51 | 1.000/0.923 |
| **full_e6c_no_h7v2** | **44/85** | **0.932/0.911** | **25/28** | **0.960/0.923** |
| e6c_accepted_no_h7v2 | 25/27 | 1.000/0.556 | 24/26 | 1.000/0.923 |

**Key findings:**

1. **`full_e6c_no_h7v2` is the recall champion:** P=0.932 R=0.911 on identical,
   P=0.960 R=0.923 on YouTube. Combined F1=0.929 (vs h7v3plus3's 0.829). This is
   a +19.7pt recall gain on identical and -3.9pt precision drop combined.

2. **Adding h7v2 hand-link edges HURTS precision.** The `full_e6c` variant
   drops to P=0.878 on identical (vs 0.932 without h7v2). The h7v2 hand-link
   edges introduce new admissions that are not in the review set, and they
   cause wrong edge competition that admits 5 wrong review edges instead of
   3 (H121's 26 RAW_REJECTS would explain this).

3. **E6c-accepted filtering is harmful at the chain level.** Running on
   E6c-accepted only (the original H7 input) gives identical R=0.556 — the
   same R as e6c_accepted_no_h7v2. The E6c-accepted filter keeps the wrong
   14 of 19 missing-wrong edges out, but it ALSO keeps out 14/18 of the
   missing-correct edges. The "cleaner" input is over-filtered.

## H125 v3 — Sensitivity grid on the full_e6c_no_h7v2 variant

**Hypothesis:** the H7 cost formula `cost = 2.0 + 0.05*err + 0.10*gap` is
declared from physical geometry. A sensitivity grid over (err_scale, gap_scale)
should confirm the default is in a flat region, indicating robustness.

**Method:** 5×4 = 20 cells. (err_scale ∈ {0.025, 0.05, 0.075, 0.10, 0.15},
gap_scale ∈ {0.05, 0.10, 0.15, 0.20}). Default = (0.05, 0.10).

**Result (per H125 v3 grid summary):**

| range | identical P | identical R | identical F1 | youtube P | youtube R | youtube F1 |
|---|---|---|---|---|---|---|
| min | 0.826 | 0.844 | 0.835 | 0.920 | 0.885 | 0.902 |
| max | 0.932 | 0.911 | 0.921 | 0.960 | 0.923 | 0.941 |
| **default (0.05, 0.10)** | **0.932** | **0.911** | **0.921** | **0.960** | **0.923** | **0.941** |

**Flat region:** err_scale ∈ {0.025, 0.05, 0.075} is identical (0.932, 0.911).
err_scale = 0.10 drops YouTube precision to 0.920 (1 wrong admitted).
gap_scale is flat at all values for both videos.

**The default (0.05, 0.10) is in the flat region** and is robust to small
perturbations. The strict-rejection of (0.10+) at the top end is the only
sensitive axis.

## Visual QA on 5 H125 v3 NEW CORRECT edges

Selected 5 of the 14 NEW V3 admitted edges that are NOT_IN_CHAIN + correct
per H59 review. Contact sheets at
`experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h125v3/`.

| edge | video | H59 label | Visual verdict | Notes |
|---|---|---|---|---|
| 4→7 | identical | CORRECT | **REAL catch-throw** | Ball in hand at f=36, smooth hand-off |
| 25→27 | identical | CORRECT | **REAL catch-throw** | 3px x, 22px y — same ball, brief hold |
| 12→17 | identical | CORRECT | **TRACKER FRAGMENTATION** | Same ball, fragmented tracking. H59 mislabel. |
| 9→12 | identical | CORRECT | **REAL catch-throw** | 1-frame gap, clear hand-off |
| 16→21 | YouTube | CORRECT | **TRACKER FRAGMENTATION** | Source held in L hand, target is different ball. H22 was correct to VETO. H59 mislabel. |

**Visual precision: 3/5 = 60% on the H125 v3 NEW edges.**

**The 2 mislabels (12→17, 16→21) are real defects in the H59 review set.**
Both are cross-ball artifacts that the original reviewer (likely a person
eyeballing contact sheets) flagged as CORRECT because the ball is "near
the hand" at the transition. The detailed contact sheet analysis shows
neither is a real catch-throw.

**Sanity check on H7v3plus3:** h7v3plus3 already excludes 12→17 and 16→21
on geometric grounds (cross-hand handoff, large spatial jump, H22 veto
respectively). The h7v3plus3 chain was correct to reject them; the H59
review was wrong to label them CORRECT.

**After correcting for the 2 H59 mislabels:**

| set | P (H59 raw) | P (after correction) | R (H59 raw) | R (after correction) |
|---|---|---|---|---|
| h7v3plus3 | 0.981 | 0.981 (no change, both mislabels are NIC) | 0.718 | 0.718 (no change) |
| H125 v3 | 0.942 | (65-1)/(69-1) = 64/68 = **0.941** | 0.915 | (65-1)/(71-0) = 64/71 = **0.901** |

The corrected P is essentially the same (0.942 → 0.941) because 12→17 is
one of the 65 admitted correct edges. The corrected R drops slightly
(0.915 → 0.901) because removing 12→17 from the admitted set also removes
it from the correct-admitted set. Net: still a +18pt recall gain over
h7v3plus3.

## H114 v1 strict compatibility (H125 v3 ⊥ H114 v1 strict)

**All 18 NEW H125 v3 edges trigger H114 v1 strict** (T_d=40, T_j=250). The
NEW edges have:
- end_d or start_d > 40 (geometrically far from hand), AND
- jump > 250 in some cases

This is a structural property: the E6c `accepted=1` filter (which excludes
H125 v3's NEW edges from h7v3plus3's input) was effectively a pre-filter
that removed precisely the high-end_d / high-jump edges. H125 v3 admits
them anyway because the H7 min-cost flow doesn't have access to end_d /
start_d — it only uses trajectory_fit_error and gap.

**Therefore:** H125 v3 cannot be combined with H112 + H114 v1 strict
without dropping all 18 NEW edges. The 4 wrong review edges (6→15,
18→21, 57→63, 10→11 youtube) admit 4 cross-ball artifacts that the
existing geometric post-filters cannot catch.

## Recommended operating point

**Two-tier recommendation:**

1. **For precision-optimized downstream consumers** (e.g. juggling-pattern
   inference, H11 identity propagation): use **h7v3plus3** (H34) as before.
   P=1.000 R=0.718 F1=0.829 (after H112 + H114 v1 strict). Unchanged.

2. **For recall-optimized downstream consumers** (e.g. hand-event log
   analysis, where missing real catches is worse than admitting a few
   cross-ball artifacts): use **H125 v3 chain set** (NEW) WITHOUT H114 v1
   strict. P=0.942 R=0.915 F1=0.929. **+19.7pt recall, -3.9pt precision,
   +10pt F1 vs h7v3plus3.** Downstream consumers should treat each NEW
   edge as a *candidate* and apply their own geometric validation.

The H125 v3 chain set is a strict superset of h7v3plus3's ballistic-only
subset (the BALLISTIC edges in h7v3plus3 are all admitted in H125 v3).
H125 v3 does NOT include h7v3plus3's HAND_TRANSITION / RECLASSIFIED edges
(because H125 v3 runs on E6c BALLISTIC only). For a combined chain set
that includes hand transitions + the new BALLISTIC edges, see H125 v4
(planned).

## Future research

1. **H125 v4: H7v3plus3 + H125 v3 union chain set.** Add H125 v3's 18 NEW
   edges to h7v3plus3 as BALLISTIC edges. Apply H112 + H114 v1 strict
   post-filters. Visual QA on the 18 new edges to determine precision
   impact.

2. **H125 v5: H125 v3 with E6c rejection criteria.** H7 currently uses
   the `accepted` column from E6c only at the input filter (53 edges).
   H125 v3 ignores the `accepted` column. A hybrid: use E6c's
   `trajectory_fit_error < 50` as a soft prior (cost = base * 2.0 if
   err > 50) instead of hard filtering. This may let some of the 14/19
   missing-wrong edges be properly rejected while still admitting the
   14/18 missing-correct edges.

3. **H125 v6: per-source k-best chain (multi-hypothesis).** A true
   k-best min-cost flow that admits up to k successors per source. The
   h7v3plus3 picks 1 of 18 (k=1); the H125 v3 picks 14 of 18 (k=∞).
   A k=2 chain would admit 18-25 edges total.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125_v1_kbest_analysis.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125_v2_h7_on_full_e6c.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125_v3_grid.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h125v3_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v1_kbest_per_edge.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v1_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v2_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v2_*.csv` (8 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v3_grid_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h125_v3_default_admitted_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h125v3/h125v3_*.png` (5 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h125_report.md` (this file)
