# Independent code audit

Audit basis: frozen research commit `ea17fb541a6998d0c4f0e63bd9cb4e38e40c19b5` plus the pre-overnight E6c artifacts. This audit reads implementation and CSVs, not report prose.

## Findings

1. **H7 is not global min-cost flow.** `h34_min_cost_flow.py:105-170` computes scalar costs, sorts ascending, and accepts an edge iff the source has no successor and target has no predecessor. The accurate description is **greedy cost-ordered one-predecessor/one-successor selector**. H125 v3 repeats the same algorithm in `h125_v3_grid.py:78-119`, despite the function name `h7_min_cost_flow`.
2. **Cycle check.** H7 follows existing `pred` links from `src` (`h34_min_cost_flow.py:132-143`); H125 v3 follows `succ` links from `src` (`h125_v3_grid.py:97-105`). Both are defensive checks. Since candidate edges are intended to be temporally forward, real cycles should already be impossible; the check is not evidence of global optimization.
3. **H125 v4 is not a tracker.** `h125_v4_union_strict.py:233-249` unions h7v3plus3 and H125-v3 pairs, deduplicates exact pairs, filters them, and evaluates membership. It does not re-run capacity-constrained selection after union. Its P=.964/R=.761 is therefore a **reviewed candidate-edge-set** result, not tracker precision/recall.
4. **H7v2 is primarily semantic.** The h7v2/h7v3pure edge CSVs retain the same source/target pair while changing `BALLISTIC` to `RECLASSIFIED_HAND_TRANSITION`; this is provenance/interpretation improvement unless the pair itself changes.
5. **H34/h7v3plus3 contains development-video interventions.** H34 explicitly removes `16->21` and adds `20->21` for YouTube (`h34_min_cost_flow.py:35-47`), and adds the H26-derived edges in h7v3plus2. These are not unseen-data validation.
6. **H1 v4 slope is dev-tuned.** `STATE.md` records that `MIN_FROM_SLOPE=2.5` was selected after known v3 false positives/successes were visually inspected. It is an automatic rule with development-video-tuned threshold, not independent validation.
7. **Pose confidence fields are mislabeled.** `h1_hand_pool.py:302-310` assigns `end_pose_conf` from `tr.confidences`, i.e. detector/tracklet confidence, not wrist/MediaPipe pose confidence. `start_pose_conf` is then copied from `end_pose_conf` at line 351. The demo omits these fields.
8. **113-pair labels are not one-to-one ground truth.** `h59_per_pair_eval.csv` contains multiple `correct` alternatives for one source (for example identical `12->17` and `12->16` are both labeled correct; `50->55` and `50->56` are both correct). A capacity-constrained tracker cannot recover every labeled alternative. The metric is candidate-pair recovery.
9. **H125 errors are not physical uncertainty.** H125 uses internal fit error and a cost formula (`2 + 0.05*err + 0.1*gap`); the H125 v4 material also discusses pseudo-pixel scaling. These are algorithmic scores, not calibrated physical uncertainty; the UI labels them internal/descriptive and does not present pseudo-pixels.
10. **Graph identity is not permanent ball identity.** H32/H11 analysis in `STATE.md` documents multi-ball chain merges. A chain ID (`T<number>` in the UI) means graph reconstruction continuity only. Hand occupancy can make physical identity unknowable.
11. **AIR paths.** The repository stores endpoint/fit evidence, not a uniquely saved full parabolic path for every E6c edge. The demo therefore uses a minimal dashed model connector labeled AIR rather than fabricating a parabola.

## Meaning of the demo levels

- **BASELINE / E6c:** accepted stitch CSVs from `detections/*_accepted_stitches.csv`.
- **AUTO:** `h7v3pure_admitted_edges_*.csv`, built from H1 v4d/H7v2 and H15v2, selected with the greedy one-to-one H7 selector. No H22/H26 example corrections.
- **RESEARCH-TUNED:** `h7v3plus3_admitted_edges_*.csv`, the H34 combination that includes H22/H26 development-video-informed decisions. It remains a coherent one-to-one edge set.
- **H125:** `h125_v3_default_admitted_*.csv` proposals, displayed only as an overlay. H125 v4 is not treated as a chain.

## Component table

| Component | Changes topology? | Automatic? | Dev-tuned? | Manual/example-specific? | Safe to show as tracker? | Notes |
|---|---:|---:|---:|---:|---:|---|
| E6c | Yes | Yes | No known claim | No | Yes, baseline | Accepted pre-overnight stitches |
| H1 v4d | Yes | Yes | Yes | No | Yes, as input | Slope threshold selected after dev QA |
| H7 | Yes | Yes | No | No | Yes, with accurate label | Greedy cost-ordered capacity selector |
| H7v2 | Usually no | Yes | Yes | No | Yes, as semantic layer | Reclassifies existing pairs near hand regions |
| H15 | Yes | Yes | Yes | No | Yes, in AUTO | V-shape reclassification; threshold/QA history is dev-scoped |
| H22 | Yes | Yes | Yes | Yes | Only in research-tuned | Explicit YouTube 16→21 veto / 20→21 replacement |
| H26 | Yes | Yes | Yes | Yes | Only in research-tuned | Adds two visually reviewed identical-video links |
| h7v3plus3 | Yes | Yes | Yes | Yes | Yes, as research-tuned | Coherent topology, but development-video informed |
| H10 quality | No | Yes | Yes | No | No | Downstream quality annotation, not association |
| H11 identity | No / annotation | Yes | Yes | No | No | Physical identity evidence is limited and merge-prone |
| H125 v3 | Yes when independently selected | Yes | Claimed geometry defaults | No | Experimental only | Greedy assignment on full E6c; not default AUTO |
| H125 v4 | **No** | Filters only | Yes | Yes | **No** | Union/proposal set; no post-union capacity enforcement |

## Audit conclusion

The honest comparison is topology plus provenance: AUTO is the defensible coherent automatic level, RESEARCH-TUNED shows the extra development-informed operating point, and H125 is a candidate-proposal diagnostic. Neither graph connectivity nor reviewed-pair recovery proves permanent physical-ball identity.
