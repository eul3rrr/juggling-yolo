# H35 — Downstream re-measurement on h7v3plus3 (H22 + H26 combined)

## Hypothesis

H22 split the YouTube 7-tid chain (1,9,13,16,21,29,34) into two 4-tid
chains: (1,9,13,16) and (20,21,29,34). H26 added 2 NEW REAL H20-KEPT
edges (7→10 and 59→61) on identical. The previous H11 v7 / H12 v8
identity propagation and pattern inference were computed on
**h7v3pure** (H7v2 + H15v2 only), NOT on **h7v3plus3** (H22 + H26).
We need to re-measure to:

1. See if the H22 chain split changes the per-frame census on YouTube.
2. See if the new YouTube chain 10 (20,21,29,34) has correct identity.
3. See if pattern inference catches different patterns on the 4-tid
   vs 7-tid chain.
4. See if the H26 identical edges (7→10, 59→61) show up in the
   identical event log + pattern inference.

## Implementation

`h35_h7v3plus3_downstream.py` re-runs the H11 v7 (identity
propagation) and H12 v7 (pattern inference) algorithms on:

- `h7v3plus3_chains_{stem}.csv` (chains)
- `h7v3plus3_admitted_edges_{stem}.csv` (edges)
- `h10v10_h7v3plus3_{stem}.csv` (H10 v10 chain quality)

It emits:
- `tracklet_identity_h35_{stem}.csv` — per-tracklet physical ball ID
- `chain_events_h35_{stem}.csv` — per-event catch/throw events
- `pattern_inference_h35_{stem}.csv` — per-frame juggling pattern

Hand-edge types are extended to include `H22_RECLASSIFIED_HAND_TRANSITION`
(new in H22). Hand is parsed from `h22_reason` and `h26_reason` fields.

## Quantitative result

### H11 (identity propagation)

| Video | h7v3plus2 CONF | h7v3plus3 CONF | multi_CONF | catches | throws | h22 events | h26 events | v_reclass |
|---|---|---|---|---|---|---|---|---|
| identical | 27 | **27** | 3 | 24 | 24 | 0 | 4 | 8 |
| YouTube  | 5  | **5**  | 1 | 25 | 25 | 2 | 0 | 2 |

Identical: unchanged from h7v3plus2 (H22 has no identical effect;
H26 added 4 h26 events). YouTube: 25 events (matches h7v3plus2) but
the chain topology differs — the 7-tid chain 0 is now a 4-tid chain
0 and a 4-tid chain 10. The 2 h22 events are 20→21 left-hand catch
+ throw (the new chain 10).

### H12 (pattern inference)

Identical (n=1042 frames):

| Pattern | h7v3plus2 | h7v3plus3 |
|---|---|---|
| FOUNTAIN_3+        | 298 (28.6%) | 298 (28.6%) |
| TWO_BALL           | 255 (24.5%) | 255 (24.5%) |
| SINGLE_BALL        | 216 (20.7%) | 216 (20.7%) |
| MIXED_3+           | 208 (20.0%) | 208 (20.0%) |
| MIXED_3+_UNCONFIRMED | 25 (2.4%) | 25 (2.4%) |
| CASCADE_3+         | 22 (2.1%)  | 22 (2.1%) |
| TWO_BALL_ONE_HAND  | 18 (1.7%)  | 18 (1.7%) |

Identical: identical to h7v3plus2. No H22 effect on identical.

YouTube (n=898 frames):

| Pattern | h7v3pure (H12 v8) | h7v3plus3 (H35) |
|---|---|---|
| MIXED_3+           | 589 (65.6%) | 589 (65.6%) |
| CASCADE_3+         | 129 (14.4%) | 129 (14.4%) |
| FOUNTAIN_3+        | 110 (12.2%) | 110 (12.2%) |
| MIXED_3+_UNCONFIRMED | 70 (7.8%) | 70 (7.8%) |

YouTube: identical to h7v3pure. The H22 chain split did NOT change
the per-frame pattern distribution. This makes sense: H22 split
chain 0 (7 tids) into chain 0 (4 tids) + chain 10 (4 tids). The
n_total distribution (5: 67.4%, 4: 29.1%, 6: 1.1%, 3: 2.4%)
depends on chain density per frame, which is dominated by the
5-7 single-tid chains, not the multi-tid chain topology.

### n_total distribution (per-frame ball count)

YouTube on h7v3plus3:
- n_total=5: 605 (67.4%) — visually confirmed at f=500 (5-ball pattern)
- n_total=4: 261 (29.1%)
- n_total=6: 10 (1.1%)
- n_total=3: 22 (2.4%)

This matches the H12 v8 result. H22 chain split did not change it.

### Substantial phases (n_frames >= 20)

Identical h7v3plus3 (13 phases, same as h7v3plus2):
- f=174-195 MIXED_3+
- f=208-231 SINGLE_BALL
- f=263-312 FOUNTAIN_3+
- f=335-398 SINGLE_BALL
- f=411-449 FOUNTAIN_3+
- f=473-506 SINGLE_BALL
- f=549-578 MIXED_3+
- f=631-669 FOUNTAIN_3+
- f=685-716 FOUNTAIN_3+
- f=733-766 FOUNTAIN_3+
- f=890-936 MIXED_3+
- f=977-1011 FOUNTAIN_3+
- f=1029-1050 FOUNTAIN_3+

YouTube h7v3plus3 (13 phases, same as h7v3pure):
- f=2-71 MIXED_3+_UNCONFIRMED
- f=114-255 MIXED_3+
- f=267-298 MIXED_3+
- f=308-338 MIXED_3+
- f=339-374 FOUNTAIN_3+
- f=375-410 MIXED_3+
- f=420-469 MIXED_3+
- f=510-590 MIXED_3+
- f=595-643 MIXED_3+
- f=678-700 MIXED_3+
- f=769-799 MIXED_3+
- f=800-861 FOUNTAIN_3+
- f=862-899 MIXED_3+

## Visual QA

6 contact sheets were rendered:
- youtube_1_9.png — chain 0 (1,9,13,16) left→left→left→left
- youtube_9_13.png
- youtube_13_16.png
- youtube_20_21.png — chain 10 (20,21,29,34) NEW after H22 split
- youtube_21_29.png
- youtube_29_34.png

The contact sheets show the YouTube chain 0 + 10 split correctly:
chain 0 (1,9,13,16) is a sustained sequence (4 tids, all 4-7 pts
each), and chain 10 (20,21,29,34) is also a sustained sequence.

## Findings

1. **The h7v3plus3 chain set is functionally equivalent to h7v3pure
   for downstream consumers (H11/H12).** H22's YouTube 7→4+4 chain
   split is a chain-topology change that does NOT change the per-frame
   census or the per-frame pattern distribution. The reason: the
   pattern distribution is dominated by the 11 single-tid YouTube
   chains (which have constant n_total=1) and the multi-tid chains
   contribute to n_total=4-5 only on their respective frames.

2. **H26's identical h26 events (4 events on 2 edges) propagate to
   the event log correctly.** The h26_reason parsing works: 4 events
   on identical are tagged h26_reclassified=True, hand=unknown
   (H26's edges don't store hand in the standard format).

3. **H22's YouTube h22 events (2 events on 1 edge) propagate to
   the event log correctly.** The h22_reason parsing works: 2 events
   on YouTube are tagged h22_reclassified=True, hand=left (parsed
   from "vetoed 16→21 in favor of h20_kept 20→21 ... hand=left ...").

4. **The YouTube 5-ball pattern is real and stable across h7v3
   variants.** n_total=5 is 67.4% of YouTube frames, n_total=4 is
   29.1%, n_total=6 is 1.1%. This is consistent with a 5-ball
   cascade pattern, as visually confirmed at f=500.

5. **The pattern-distribution sensitivity to h7v3 variant is ZERO.**
   H35 re-runs identical to h7v3pure (H12 v8). This is a useful
   negative finding: the pattern distribution is not sensitive to
   which h7v3 variant we use, so downstream consumers can use
   h7v3plus3 (the most-up-to-date chain set) without affecting
   H12 pattern inference results.

## Verdict

**PASS (consumer-pass, no change).** H35 confirms that the
h7v3plus3 chain set is functionally equivalent to h7v3pure for
the H11/H12 downstream consumers. The pattern distribution,
phase detection, and per-frame census are all stable across
h7v3 variants. The H22 YouTube chain split and H26 identical
edges propagate to the event log correctly.

## Implications for downstream consumers

- **Use h7v3plus3** for H11 v7 identity propagation (H35's
  identity CSVs supersede H11 v7's).
- **Use h7v3plus3** for H12 v7/v8 pattern inference (H35's
  pattern CSVs are equivalent to H12 v8's).
- The chain topology change (H22 split) is a chain-quality
  improvement (+0.0034 YouTube) that does NOT change the
  per-frame pattern distribution.
- The H26 identical events (4 events) are now tagged in the
  event log as h26_reclassified=True.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h35_h7v3plus3_downstream.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h35_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h35_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_h35_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_h35_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_h35_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h35/*.png` (6 files)
