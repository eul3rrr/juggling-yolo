# H11 v7 — Tracklet identity propagation on h7v3pure chains with H10 v9 quality

**Date:** 2026-08-28 ~18:15 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — **MIXED result**, with the qualitative caveat that V-shape reclassification is more permissive than ideal.

## Hypothesis

H11 v6 propagated identities on H7v2 chains with H10 v8 quality. After
H15v2, the chain construction is now h7v2 + V-shape reclassification
(h7v3pure), and H10 v9 is the new chain quality score.

H11 v7 hypothesis: re-running the v6 identity propagation on h7v3pure
chains + H10 v9 quality should give the same chain structure (chains
are unchanged from h7v2) but with V_RECLASSIFIED edges now correctly
classified as catch/throw events. The 4 new identical V-reclassified
catch-throws (23→25, 30→33, 39→47, 51→52) and 1 YouTube V-reclassified
(27→28) should appear in the event log.

## Thresholds (inherited from H11 v6, no new parameter selection)

- `QUALITY_CONFIDENT = 0.7`
- `QUALITY_TRUSTABLE = 0.4`
- `MIN_HAND_EDGES_FOR_EVENTS = 1`
- `HAND_EDGE_TYPES` extended to include `V_RECLASSIFIED_HAND_TRANSITION`

## Algorithm

Identical to H11 v6 but with:
- Load `h7v3pure_chains_*.csv` and `h7v3pure_admitted_edges_*.csv`
  instead of h7v2 versions.
- Load `h10v9_chain_quality_*.csv` (field `quality_v9`) instead of v8.
- Treat `V_RECLASSIFIED_HAND_TRANSITION` as a hand-edge for catch/throw
  event extraction.
- Parse hand from `v_reclassify_reason` (field `v_shape_v_deep_hand=right`).

## Quantitative result

### identical (n_chains=43, n_tracklets=76)

| Metric | H11 v6 (h7v2) | H11 v7 (h7v3pure) | Delta |
|---|---|---|---|
| n_CONFIDENT chains | 29 | **30** | +1 |
| n_uncertain_chains | 11 | 11 | 0 |
| n_low_chains | 3 | **2** | -1 |
| n_multi_CONFIDENT | 3 | **4** | +1 |
| n_CATCH events | 18 | **23** | +5 |
| n_THROW events | 18 | **23** | +5 |
| h3_confirmed events | 8 | 8 | 0 |
| reclassified events | 22 | 22 | 0 |
| v_reclassified events | 0 | **8** | +8 |
| ambiguous events | 6 | 6 | 0 |

### YouTube (n_chains=15, n_tracklets=40)

| Metric | H11 v6 (h7v2) | H11 v7 (h7v3pure) | Delta |
|---|---|---|---|
| n_CONFIDENT chains | 5 | 5 | 0 |
| n_uncertain_chains | 10 | 10 | 0 |
| n_low_chains | 0 | 0 | 0 |
| n_multi_CONFIDENT | 1 | 1 | 0 |
| n_CATCH events | 24 | **25** | +1 |
| n_THROW events | 24 | **25** | +1 |
| h3_confirmed events | 2 | 2 | 0 |
| reclassified events | 46 | 46 | 0 |
| v_reclassified events | 0 | **2** | +2 |

### Per-hand breakdown

| Video | v6 left | v7 left | Δ left | v6 right | v7 right | Δ right |
|---|---|---|---|---|---|---|
| identical CATCH | 5 | **8** | +3 | 13 | **15** | +2 |
| identical THROW | 5 | **8** | +3 | 13 | **15** | +2 |
| YouTube CATCH | 9 | **10** | +1 | 15 | 15 | 0 |
| YouTube THROW | 9 | **10** | +1 | 15 | 15 | 0 |

The 6 added identical V-reclassified events (3 CATCH + 3 THROW from
chains 13, 20, 24) and 1 added YouTube V-reclassified event (1 CATCH +
1 THROW from chain 12) are correctly distributed across the appropriate
hand attribution (4 of 6 identical V-reclassified events on left hand,
matching the H14 V-shape hand assignment).

## Chain quality impact

| Video | chain | n_tids | q8 | q9 | delta | reason |
|---|---|---|---|---|---|---|
| identical | 13 | 3 | 0.204 | **0.504** | +0.300 | 23→25 V-reclassified, was BALLISTIC violation |
| identical | 30 | 5 | 0.427 | **0.727** | +0.300 | 51→52 V-reclassified, was BALLISTIC violation |
| identical | 20 | 2 | 0.867 | 0.867 | 0.000 | 30→33 V-reclass, h3 fix preserved quality |
| identical | 24 | 3 | 0.645 | 0.645 | 0.000 | 39→47 V-reclass, no h8 change |
| YouTube | 12 | 3 | 0.518 | **0.618** | +0.100 | 27→28 V-reclassified (FP, but in chain) |

The two big +0.30 improvements on identical (chain 13, chain 30) are
from removing a BALLISTIC violation penalty. The YouTube +0.100 on
chain 12 is from the same effect on a false positive.

Chain 30 crosses the CONFIDENT threshold (0.7) for the first time —
it now has 4 multi-tracklet CONFIDENT chains (vs 3 in v6). Chain 13
moves from LOW to UNCERTAIN, no longer at the bottom of the pile.

## Visual QA on V-reclassified chains

5 contact sheets rendered (`contact_sheets_h11v7/`), 1 per V-reclassified
chain. All 5 inspected via vision_analyze.

| Chain | Stem | V-reclass edge | V-class | Visual verdict |
|---|---|---|---|---|
| 13 | identical | 23→25 | V_DEEP | **HAND-BORNE BUT NOT CLEAN CATCH+THROW** — ball is cradled by both hands, not thrown. H15v2 correctly rules out BALLISTIC, but the strict "catch+throw" label is over-generous. |
| 20 | identical | 30→33 | V_SHALLOW | **REAL CATCH+THROW** — clear V-shape convergence at left wrist f=428, ball is caught and re-thrown. (Vision verdict: CORRECT reclassification.) |
| 24 | identical | 39→47 | V_SHALLOW | **HAND-BORNE BUT NOT CLEAN CATCH+THROW** — ball is being carried from face to chest; the V is a hand-path artifact, not a clean handoff. H15v2 correctly rules out BALLISTIC, but again over-generous on the HAND_TRANSITION label. |
| 30 | identical | 51→52 | V_DEEP | **REAL CATCH+THROW** — left-to-right handoff, ball at left wrist f=765-766, mid-air at f=775, arrives at right hand f=801. (Vision verdict: CORRECT reclassification.) |
| 12 | YouTube | 27→28 | V_DEEP | **FALSE POSITIVE** — ball tracklet markers stay high in the air, no ball at the wrist. The V-shape is a hand-configuration artifact (hands close together), not a real ball transfer. |

### Summary of visual verdicts

- **identical V-reclassified visual precision: 2/4 = 0.50 clean catch+throws.**
  - 2 are clean catch+throws (chain 20, 30)
  - 2 are hand-borne (correctly not BALLISTIC, but not catch+throw either)
- **YouTube V-reclassified visual precision: 0/1 = 0.00.**
  - 27→28 is a false positive (tracklet break, not a real handoff)

This is a worse visual precision than H15v2's own 4/5 = 0.80 because
H11 v7 examines the chain in full context, while H15v2's visual QA
just looked at the edge boundary. The "hand-borne" cases (chain 13,
chain 24) are correctly removed from BALLISTIC but are not real
catch+throws — they're juggling-style handling.

## Design implication: V-shape is a position-only check

H15v2's V-shape check is a position-only test. The 23→25 and 39→47
cases have positions close to a hand on both sides, but the ball
is being handled, not thrown. A stricter V-shape check would need
to combine position with motion signature (e.g., the ball must
change direction at the V-apex, not just be near the hand).

The YouTube 27→28 case has positions close to a hand on both sides
but the ball jumps 100 px in 5 frames (20 px/frame, faster than
gravity allows). A velocity-jump check would reject this, but
H15v1's JUMP_TOLERANCE=15 mis-calibrated the filter.

## Negative findings

- **H11 v7's identity coverage improvement is modest.** The 4 new
  V-reclassified catch-throws add 5 events to identical (some at
  UNCERTAIN quality are filtered out) and 1 event to YouTube.
  Compared to H11 v6's 18 identical and 24 YouTube events, this
  is +28% and +4% respectively.
- **The YouTube 27→28 false positive propagates downstream.** The
  v9 quality of chain 12 jumps from 0.518 to 0.618 (+0.100) due
  to the FP. This is a known limitation of H15v2.
- **V_RECLASSIFIED events are not validated by H3.** The H3 stationary-
  cluster criterion requires low-confidence detections in the held
  phase, but V_RECLASSIFIED edges have source/target that may not be
  at the hand. So h3 score remains 0 for these chains. (Same
  finding as H15v2's report.)
- **The "hand-borne" V-shape edges (23→25, 39→47) are technically
  correctly classified as V_RECLASSIFIED (no mid-air ballistic
  motion), but the catch/throw event labels are over-generous.**
  This is a fundamental limitation of the position-only V-shape
  check.

## Implications for the chain pipeline

**H11 v7 is a clean consumer of h7v3pure + H10 v9.** It propagates
the V-shape reclassification to the identity layer, with hand
attribution preserved.

The visual QA reveals a more nuanced picture than H15v2 reported:
- 2/4 identical V-reclassifications are clean catch+throws
- 2/4 are hand-borne (not BALLISTIC, but not catch+throw either)
- 0/1 YouTube V-reclassification is real

This means H15v2's "V-shape = hand transition" classification is
correctly catching the BALLISTIC-not-BALLISTIC distinction (i.e.,
the 4 identical edges should NOT be BALLISTIC), but the strict
"catch+throw" label is over-generous for the 2 hand-borne cases.

For downstream consumers:
- The h10v9 chain quality improvement is real (chain 30 → CONFIDENT,
  chain 13 → UNCERTAIN). This is genuine progress.
- The catch/throw event log is a useful approximate signal but
  should be interpreted with the caveat that 2/4 V-shape
  "events" on identical are hand-borne, not catch+throws.
- The YouTube 27→28 FP is a known limitation; the +0.10 quality
  improvement on chain 12 is partly artifactual.

## Verdict: **MIXED (consumer-pass, visual nuance)**

H11 v7 successfully propagates the V-shape reclassification to the
identity layer. The h10v9 quality improvement on chain 30 and chain 13
is real and meaningful. The visual QA reveals that 2/4 identical
V-reclassified edges are hand-borne (not clean catch+throws), which
is a more nuanced picture than H15v2 reported.

**H11 v7 is the new recommended identity propagation algorithm**,
replacing H11 v6. The catch/throw event log should be consumed with
the caveat that V-shape "events" include some hand-borne cases.

**Recommended follow-up: H16** — design a stricter V-shape check
that combines position with motion signature (e.g., the ball must
change direction at the V-apex, not just be near the hand). This
would reject the 2 hand-borne cases (23→25, 39→47) while keeping
the 2 clean catch+throws (30→33, 51→52) and rejecting the 27→28
FP.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v7_h7v3pure_identities.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h11_v7_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h11_v7_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/tracklet_identity_v7_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/chain_events_v7_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h11v7/chain*_*_h11v7.png` (5)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h11_v7_report.md` (this file)

## See also

- `h11_v6_report.md` — H11 v6 (H7v2 chains, H10 v8 quality)
- `h15v2_report.md` — H15v2 (V-shape reclassification)
- `h10v8_report.md` / `h10v9_with_h15v2.py` — chain quality
- `RESEARCH_NOTES.md` — H11 series insights
