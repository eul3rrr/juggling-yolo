# H120 — Multi-rule strict flagger (H114 v1 + cross-hand + single-end-far)

## Background

H119 found that the 10 visually-QA'd un-QA'd H17 full pool strict fires
cluster into 3 distinct geometric failure modes:
- cross-hand handoff (5/10): src near hand A, tgt near hand B
- single-end-far (4/10): one endpoint at hand, other far
- both-end-far (1/10): both endpoints far from any hand

H114 v1 strict (T_d=25, T_j=200) catches all 10 because BOTH endpoints
must be > 25 px (cross-hand) and the jump must be > 200.

H120 hypothesis: a multi-rule flagger with 3 distinct geometric rules
might catch more cross-ball artifacts than H114 v1 strict alone, with
similar precision.

## Method (v1 — Rule A + B + C)

Three rules with declared thresholds (per master §15):
- Rule A (H114 v1 strict): end_d > T_D_A AND start_d > T_D_A AND spatial_jump > T_J_A
  Defaults: T_D_A=25, T_J_A=200
- Rule B (cross-hand handoff): end_side != start_side AND min(end_d, start_d) > T_D_B AND sj > T_J_B
  Defaults: T_D_B=30, T_J_B=100
- Rule C (single-end-far): (end_d > T_D_C AND start_d < T_D_C) OR (start_d > T_D_C AND end_d < T_D_C)
  AND spatial_jump > T_J_C
  Defaults: T_D_C=50, T_J_C=80

v1 = Rule A OR Rule B OR Rule C (3-rule OR).
v2 = Rule A OR Rule B (drop Rule C, which has high FP rate on chain-accepted edges).

## Quantitative result (H17 full pool, 177 unique edges)

| Stack | n_fires | n_new vs H114 strict | n_in_h7v3plus3 | n_chain_FPs |
|-------|--------:|---------------------:|---------------:|------------:|
| H114 v1 strict | 47 | — | 0 | 2 (3→8, 22→27) |
| H120 v1 (A+B+C) | 93 | 46 | 0 | **9** |
| H120 v2 (A+B) | 54 | 7 | 0 | 2 (3→8, 22→27) |

The 9 chain FPs for v1 (A+B+C) include 7 false-positive REJECTIONS of
real catch-throws in h7v3plus3 (e.g., 17→23, 53→60, 70→74 HAND_TRANSITION
edges, 11→14 AMBIGUOUS_HAND_TRANSITION, etc.). Rule C fires on the very
pattern it's trying to identify (HAND_TRANSITION with one end far from
the hand). v1 is REJECTED.

## H120 v2 (A+B only): breakdown of 54 fires

- 18 fires = Rule A only (H114 v1 strict subset, sj > 200)
- 29 fires = Rule A + Rule B (both fire)
- 7 fires = Rule B only (NEW, sj < 200 but cross-hand with both > 30 px)

All 54 fires have 0 in h7v3plus3 (chain correctly excludes them all).
The 2 H17 v1 visual QA FALSE (4→8, 66→68) are still caught by A.
The 7 NEW Rule-B-only fires are un-QA'd.

## Threshold sensitivity (H17 full pool, 25-cell v2 sweep)

All 25 cells in (T_D_B, T_J_B) ∈ {20, 25, 30, 40, 50} × {60, 80, 100, 150, 200}
are SAFE (0 REAL on the H17 v1 visual QA subset). Best safe cell:
T_D_B=20, T_J_B=60 → 62 fires, 3 QA'd, 0 REAL, 3 FALSE.

## H20-KEPT pool (115 edges, 29 deduped QA'd)

| Stack | n_fires | n_new vs H114 default |
|-------|--------:|----------------------:|
| H114 v1 default (T_D=40, T_J=250) | 4 | — |
| H120 v2 (A+B) | 29 | 25 |
| H120 v1 (A+B+C) | 67 | 63 |

0/29 H120 v2 fires are in h7v3plus3. The 25 NEW fires are all un-QA'd
on the H20-KEPT side. Per H115 v3, the H20-KEPT has 15% REAL precision
on the 20-row QA'd subset (3 REAL out of 20). The 25 NEW H120 v2 fires
are un-QA'd, so we cannot validate their precision.

## Visual QA of 7 NEW H120 v2 Rule-B-only fires

All 7 fires are on identical_balls_trick_000_018 (5 are in the
"adjacent_vshape" pool, 2 are in the "e6c_not_in_h7v2" pool). Visual QA
via vision_analyze on all 7:

| Edge | Kind | V-shape | Spatial jump | Verdict |
|------|------|---------|-------------:|---------|
| 14→19 | e6c_not_in_h7v2 | V_SHALLOW | 102.8 | TRACKER ARTIFACT (temporal overlap: target starts at f=174, source ends at f=180) |
| 25→26 | e6c_not_in_h7v2 | V_DEEP | 132.8 | TRACKER ARTIFACT (both tracklets on right side, not a cross-hand handoff) |
| 1→8 | adjacent_vshape | V_SHALLOW | 172.6 | TRACKER ARTIFACT (26-frame gap, neither endpoint near a wrist) |
| 10→12 | adjacent_vshape | V_SHALLOW | 166.2 | TRACKER ARTIFACT (both tracklets on same side) |
| 15→19 | adjacent_vshape | V_DEEP | 124.9 | TRACKER ARTIFACT (target goes upward away from any hand) |
| 63→68 | adjacent_vshape | V_DEEP | 181.9 | TRACKER ARTIFACT (depth mismatch: end_d=63 vs start_d=36) |
| 70→73 | adjacent_vshape | V_DEEP | 199.1 | UNCERTAIN/REAL (L→R signature plausible, but vision tool ambiguous) |

**6/7 = 86% are confirmed FALSE (cross-ball tracker artifacts).**
**1/7 = 14% is genuinely UNCERTAIN (70→73).**

This is a high false-positive rate for a candidate flagger. Combined with
H115 v3's finding that the H20-KEPT pool has 15% REAL precision, Rule B
alone does NOT have discriminating power. The cross-hand geometric
criterion is too permissive (any cross-hand transition with both endpoints
> 30 px and sj < 200 fires Rule B).

## Chain FP check (2/59 chain-accepted edges fire H120 v2)

The 2 chain FPs are:
- **3→8 identical** (RECLASSIFIED_HAND_TRANSITION, fires Rule A): H114
  visual QA said "Likely a False Positive" but H7v2 reclassification
  admitted it. H112 does not catch 3→8 because the spatial jump (227)
  exceeds the 30 px reach check.
- **22→27 identical** (RECLASSIFIED_HAND_TRANSITION, fires Rule B): the
  H112-discovered FP, which H112 + H114 v1 strict already correctly
  catch.

Both are previously-known issues. H120 v2 does not discover new FPs
in the chain. The 2 chain FPs are not actionable (3→8 was already
flagged suspect by H114 QA; 22→27 is already excluded by H112).

## Verdict

**NEGATIVE / FAIL for v1 (A+B+C).** Rule C fires on 7 in-chain
RECLASSIFIED_HAND_TRANSITION edges (real catch-throws wrongly flagged
as artifacts). The "single-end-far" geometry is the natural signature
of HAND_TRANSITION (ball at hand → ball at apex → back in hand), so
Rule C is a fundamental misfit for the task.

**MIXED for v2 (A+B).** The 2 chain FPs are already known. The 7 NEW
Rule-B-only fires are 6/7 = 86% FALSE, 1/7 = 14% UNCERTAIN. Rule B
adds value only as a strict post-hoc validator (per the H115 v3 logic),
not as a candidate flagger.

## Recommended operating point (unchanged from H112 + H114 v1 strict)

H120 v1 is REJECTED. H120 v2 is equivalent to H114 v1 strict for the
operational purpose of catching cross-ball artifacts, with 7 additional
fires that are not informative. H120 is a useful *methodological*
exploration of the 3 distinct failure modes identified by H119, but the
operational point is unchanged:

- **For chain-edge precision**: h7v3plus3 + H112 (cross_hand + end>30 +
  start>30) — already P=1.000 R=0.718 on 113 review pairs.
- **For V-shape candidate flagger**: H114 v1 strict (T_d=25, T_j=200) —
  0/15 visually-QA'd strict fires are REAL across 5 pools (95% Wilson
  upper bound = 12.87%).

## Negative findings

- Rule C (single-end-far) is fundamentally a misfit: it fires on the
  very geometric pattern it tries to identify (HAND_TRANSITION with
  one end far).
- Rule B (cross-hand handoff, sj 100-200) has 6/7 = 86% false-positive
  rate on the H120 v2 NEW visual QA subset. The cross-hand geometric
  criterion is too permissive.
- The 2 chain FPs (3→8, 22→27) are not new. 3→8 was already flagged
  as suspect in H114 visual QA; 22→27 is the H112-discovered FP.
- H120 v2 (A+B) has 25/25 safe cells in the 2D sweep (per H17 v1 visual
  QA), but the 7 NEW Rule-B-only fires are mostly FALSE — the safety
  on the QA'd subset does not generalize to the un-QA'd pool.

## Future research

1. **H121: Re-evaluate the H7v3plus3 chain on the 6 H120 v2 FALSE cases
   + 1 UNCERTAIN.** The H120 visual QA found that 6 of the 7 NEW Rule-B
   fires are clearly cross-ball artifacts. Some of these are in chains
   that include real catch-throws — the chain might benefit from a
   stricter cross-hand rejection at the chain construction level.
2. **H122: Investigate the 3→8 (RECLASSIFIED_HAND_TRANSITION) edge
   more carefully.** H114 visual QA flagged 3→8 as "Likely a False
   Positive" but it remains in h7v3plus3 because H7v2 reclassification
   downgraded the air-edge to HAND_TRANSITION. A targeted investigation
   of the H7v2 reclassification criteria for cross-hand edges with
   large spatial jumps could identify other latent chain FPs.
3. **Stop here.** H112 + H114 v1 strict is the precision-optimized
   endpoint for cross-ball artifact rejection. H120 confirmed that
   no additional geometric rules add value beyond H114 v1 strict.
   The 0.282 recall gap requires fundamentally different signals
   (color, multi-view 3D, learned tracklet classification).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h120_multi_rule_flagger.py` (with math import fix)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h120_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h120_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h120_v{1,2}_*.csv` (8 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h120/*.png` (7 files)
