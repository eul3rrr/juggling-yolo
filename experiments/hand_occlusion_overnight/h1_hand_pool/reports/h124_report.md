# H124 — Compound precision-optimized edge filter (NEGATIVE for chain precision)

**Date:** 2026-08-29 (this episode)
**Status:** **NEGATIVE** for the original goal of improving h7v3plus3 edge-level
precision. The H124 v1 rule was derived from the 14 H122+H123 visual-QA'd
RAW_REJECTS cases (achieving 0% false-reject on REALS) but **fails catastrophically
on the broader 113 review pair set**: fires on 51 pairs but only 21 are
wrong pairs (P=0.412) and 22 are in the chain (would be wrongly rejected).

## Motivation

H123's stratified 10-case visual QA refined the H122 80% REAL precision
estimate to 53.3% on a 15-case combined sample. The H112 cross-hand handoff
filter and H114 v1 strict large-jump filter together only catch 1/6 of
the H7v2 reclassification artifacts. The H123 "Future research" section
explicitly proposed:

> H124: precision-optimized edge filter — use the H122+H123 visual QA
> to define a stricter post-filter for H7v2-reclassified edges. The 8/15
> REAL cases have a specific signature: source tracklet contains a V-shape
> OR the target tracklet has small sj_raw.

## Hypothesis (declared before reading outcomes)

A compound geometric rule derived from the H122+H123 visual QA verdicts
should:
- Reject the 4/6 H122+H123 TRACKER_ARTIFACT cases (3→8-style V-shape
  in source, 64→68-style multi-ball handoff, 22→27-style cross-hand, etc.)
- Preserve all 8/8 H122+H123 REAL cases (0% false-reject on REALS)
- Generalize to the broader 113 review pair set with similar precision

## Method (declared)

Tested compound rules on the 14 H122+H123 visual-QA'd RAW_REJECTS
(8 REAL, 6 TRACKER_ARTIFACT, 1 UNCERTAIN excluded). Searched over a 5D
parameter grid (sj_raw threshold × raw_end_dist threshold × raw_end_slope
threshold × feat_n_pts threshold × rule structure). Final chosen rule:

```
FIRE (suggest REJECT) if
    (sj_raw > 90 AND NOT (raw_end_dist > 100 OR raw_end_slope > 10))
OR  (feat_n_pts <= 3)
```

The rule is intended to apply ONLY to RECLASSIFIED_HAND_TRANSITION edges
(H7v2 downgraded BALLISTIC to HAND_TRANSITION based on tracklet_features).

## H124 v1 result (RAW_REJECTS subset, 14 cases)

```
TP=8 (REAL kept), FP=0 (REAL wrongly rejected),
FN=2 (ARTIFACT missed), TN=4 (ARTIFACT caught),  acc=0.857
P_when_fire=1.000 (every fire is a real artifact)
R_artifacts=0.667 (catches 4/6 artifacts)
```

The rule has perfect precision (0% false-reject) on the H122+H123 sample.
The 2 missed artifacts (22→27, 33→36) have small sj_raw (37.5, 62.5) and
are correctly classified as REAL by visual QA only because the chain
already correctly excluded them via the H112 cross-hand handoff filter.

## H124 v2 cross-validation (113 review pair set)

The rule fires on **51/113** review pairs:
- 22 in h7v3plus3 chain: 22/22 are "correct" per reviewer
- 29 NOT in h7v3plus3 chain: 21/29 are "wrong" per reviewer, 8/29 are "correct"

| Subset | n_fires | n_correct | n_wrong | P_when_fire |
|--------|---------|-----------|---------|-------------|
| All fires | 51 | 30 | 21 | 0.412 |
| In h7v3plus3 (would be rejected) | 22 | 22 | **0** | **0.000** |
| NOT in h7v3plus3 | 29 | 8 | 21 | 0.724 |
| RECLASSIFIED in chain | 20 | 20 | 0 | 0.000 |
| OTHER edges in chain | 2 | 2 | 0 | 0.000 |

## H124 v2 finding: CATASTROPHIC REGRESSION

**If H124 v1 is applied as a chain post-filter:**
- 22 in-chain correct edges would be WRONGLY REJECTED (FN)
- 0 in-chain wrong edges would be correctly caught (TP-reduction)
- Net effect: precision drops, recall drops

**If H124 v1 is applied as a candidate flagger for the H7v2 reclassification
pool (where it was derived):**
- 20/20 RECLASSIFIED review pairs that fire are "correct" per reviewer
- 0/20 are "wrong" per reviewer
- 0% catch rate on actual wrongs (consistent with H122/H123)

## Why H124 v1 overfits to the H122+H123 sample

The H122+H123 sample was 14 RAW_REJECTS cases (H7v2_orig reclassified but
H7v2_raw wouldn't). The "sjr>90 AND NOT(red>100 OR res>10)" signature
happens to discriminate well in this specific subset because:

1. The H7v2 reclassification edge type is BIASED toward cross-ball
   handoffs that have moderate sj_raw (60-150) and are NOT multi-ball
   handoffs (so res isn't high post-throw).
2. The fn<=3 branch is biased toward 2-pt sources that are noisy.

But the broader E6c review set has many correct catches with the same
geometric signature (e.g., 11→13, 12→17, 70→74 with high sjr and
moderate red, all in chain, all "correct" per reviewer). The rule
fails because the geometry of real catches and cross-ball handoffs
overlap heavily in the 2D feature space.

## What H124 v1 IS useful for (post-hoc validation)

The 21 NOT_IN_CHAIN + wrong fires are correct review pairs that the
chain algorithm (correctly) excluded. H124 v1's P=0.724 on this subset
(21/29 correct rejects) is a useful post-hoc validation signal: "the
chain's exclusion of these edges is consistent with a geometric
artifact signature".

The 8 NOT_IN_CHAIN + correct fires are real catches the chain couldn't
admit (capacity constraint). H124 v1 incorrectly flags them as artifacts,
confirming that geometric post-filters cannot recover capacity-rejected
edges. This is consistent with the H59 finding (20 FN, 0.282 recall gap).

## Comparison with H112, H114 v1 strict, H7v2 reclassification

| Filter | Subset | n_fires | P_when_fire | R_when_fire |
|--------|--------|---------|-------------|-------------|
| H112 (cross-hand + end>30 + start>30) | 113 review | 1 | 1.000 | 0.024 |
| H114 v1 default (T_d=40, T_j=250) | h7v3+ in chain | 0 | N/A | N/A |
| H114 v1 strict (T_d=25, T_j=200) | H20-KEPT (deduped QA) | 4 | 0.000 | 0.000 |
| H114 v1 strict (T_d=25, T_j=200) | H17 strict pool | 30 | 0.000 | 0.000 |
| **H124 v1** | 113 review (all) | **51** | **0.412** | **0.500** |
| **H124 v1** | 113 review in chain | **22** | **0.000** | **0.000** |
| H124 v1 | 113 review NOT in chain | 29 | 0.724 | N/A |

H124 v1 is the LEAST PRECISE of all the geometric post-filters on the
113 review set. The 0.412 overall P is dominated by the 22 in-chain
correct edges that the rule wrongly flags.

## Verdict

**H124 v1 REJECTED.** The rule is overfit to the H122+H123 sample and
fails catastrophically on the broader 113 review pair set:
- 22 in-chain correct edges would be wrongly rejected (FN=22)
- 0 in-chain wrong edges would be correctly caught
- Net effect: chain precision and recall both DROP

**H124 v1 is useful as post-hoc validation** of the chain's NOT_IN_CHAIN
exclusions (P=0.724 on the 29 NOT_IN_CHAIN fires), but this is
redundant with the chain's own min-cost flow logic.

## Negative findings

1. **The H122+H123 sample is too biased to derive a general rule.** It
   is 14 H7v2 reclassifications, which is a specific edge type with
   different geometry than the broader E6c candidate set.

2. **The fn<=3 branch is broken for real catches.** Many real catches
   in the review set have 1-3 point source tracklets (e.g., 5→6, 20→21,
   21→22, 23→24, 27→28, 43→45) — short sources are common when the
   detector catches a ball near the hand. The fn<=3 branch flags these
   as artifacts but they're correct.

3. **The sjr>90 + red/res guard has limited discriminative power.** Real
   catches (11→13, 12→17, 17→22, 54→57, 66→69, 16→21) and cross-ball
   handoffs (6→15, 9→13, 11→12, 12→16, 15→17) overlap heavily in the
   2D (sjr, red, res) feature space.

4. **Geometric post-filters cannot recover capacity-rejected edges.** The
   8 NOT_IN_CHAIN + correct review pairs are real catches that the chain
   couldn't admit due to its one-successor-per-source constraint. No
   geometric filter can recover them; only a different chain construction
   (multi-hypothesis tracking) could.

5. **H7v2 reclassification is hard to filter geometrically.** The
   20/20 RECLASSIFIED review pairs that fire the rule are all "correct"
   per reviewer. The H7v2 reclassification rules (catch_dist<=108 AND
   catch_slope<=-1.0) actually work well on the broader E6c set, even
   though they over-apply at the RAW_REJECTS level.

## Recommended operating point (unchanged)

The h7v3plus3 + H112 + H114 v1 strict stack remains the precision-
optimized operating point. H124 v1 is a **negative validation** of
the difficulty of geometric post-filtering for H7v2 reclassifications:

- h7v3plus3 chain set: P=1.000 R=0.718 on 113 review pairs (no edge impact)
- (CONF or UNCER) gate: P=1.000 R=0.465 on 33/33 review pairs
- H112 lift: P 0.981 -> 1.000 (caught 1 FP, 22->27)

The 0.282 recall gap requires fundamentally different signals:
multi-hypothesis tracking, learned color tracking, or 3D ball
estimation.

## Future research

1. **Stop here on geometric post-filters.** The 0.282 recall gap is
   fundamental — no geometric rule can recover capacity-rejected
   edges.

2. **Multi-hypothesis tracking** (MHT) is the only known approach that
   could systematically address the capacity constraint. The H7 min-cost
   flow has a strict one-successor-per-source DAG structure; MHT would
   maintain multiple plausible successor hypotheses per source.

3. **Learned color tracking** would require re-running the detector
   with color features, which is a major project. Out of scope for
   overnight.

4. **3D ball estimation** (Ponglertnapakorn 2025) requires multi-view
   or learned depth estimation. Out of scope for monocular 2D setup.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h124_v1_compound_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h124_v2_review_pair_check.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h124_v1_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h124_v1_per_edge.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h124_v2_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h124_v2_per_pair.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h124_report.md` (this file)
