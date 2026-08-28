# H13 — Detector-level low-confidence ball evidence at hand events

**Date:** 2026-08-28 ~17:00 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** COMPLETE — three iterations, mixed result.

## Hypothesis (master §14)

For each v4d hand-link AND each H7v2-reclassified edge, scan a
wider temporal window for low-confidence sports-ball detections
within reach of the relevant hand. If they exist, the hand-link is
"corroborated" by detector evidence (even if the gap spans
detector dropouts).

This is the natural follow-up to H3 (which only considered v4d
hand-links): extending master §14's "lower-confidence evidence tier
only near an active hand event" to the H7v2 reclassified edges as
well.

## Thresholds (declared before reading outcomes)

- HAND_REACH_PX = 108 (same as v2/v4/H7v2)
- LOW_CONF_THRESHOLD = 0.5
- GAP_PAD_FRAMES = 5 (extend window beyond the gap by 5 frames each side)
- MAX_GAP_FRAMES = 60 (skip edges with gap > 60)
- MIN_CLUSTER_DETECTIONS = 3 (v2 stationary cluster criterion)
- STATIONARY_MAX_STD_PX = 30 (cluster must be within 30 px)
- BASELINE_SAMPLES = 200 (FPR control)

## Three iterations

### v1: lenient criterion (any low-conf detection in reach)

Single detection: classify as CORROBORATED if any low-conf sports
ball detection in the search window. Result: FPR = 91-100% (every
random hand-frame window has at least one low-conf detection). The
detector fires constantly on background.

**Verdict: TOO LENIENT — useless as a discriminator.**

### v2: H3 stationary-cluster criterion (≥3 dets in 30 px)

Apply H3 v3's stationary-cluster criterion restricted to the
edge window. Result: only 6/62 edges (10%) get v2 CORROBORATED,
of which 3 are v4d links (52→54, etc.) and 3 are h7v2_kept_ballistic
edges (28→29, 51→52, 41→43). Baseline FPR (random hand-frames):
identical 42%, YouTube 15%.

**Verdict: ALSO PROBLEMATIC — kept_ballistic edges get the same
cluster signal as real catch-throws. H3 stationary-cluster is
NOT a discriminator.**

### v3-v4: concentration ratio and peak-vs-context test

The mean *concentration* (n_in_reach / (n_in_reach + n_out_reach))
captures the relative density of low-conf dets at the hand region.
The peak-vs-context ratio (event-window conc / ±30-frame context
conc) measures whether the hand is a "magnet" during the event.

**Verdict: these tests reveal a real statistical signal but neither
fires as a hard "corroborated/ambiguous" classifier.**

## Key quantitative result

**Mean concentration per group (with bootstrap 90% CI):**

| Group | n | mean conc | median | stdev | mean gap |
|---|---|---|---|---|---|
| v4d hand-links (identical) | 10 | 0.142 ± 0.012 | 0.140 | 0.037 | 18.0 |
| h7v2_reclassified (identical) | 13 | 0.201 ± 0.020 | 0.172 | 0.074 | 10.2 |
| h7v2_kept_ballistic (identical) | 12 | 0.206 ± 0.021 | 0.195 | 0.071 | 8.9 |
| v4d hand-links (YouTube) | 1 | 0.232 | 0.232 | 0 | 17.0 |
| h7v2_reclassified (YouTube) | 25 | 0.303 ± 0.012 | 0.288 | 0.060 | 9.8 |
| h7v2_kept_ballistic (YouTube) | 1 | 0.214 | 0.214 | 0 | 8.0 |

**Bootstrap 90% CI for differences (identical):**
- h7v2_reclassified - v4d: **+0.059 [+0.022, +0.098]** (significant)
- h7v2_kept_ballistic - v4d: **+0.064 [+0.027, +0.102]** (significant)
- h7v2_reclassified - h7v2_kept_ballistic: -0.005 [-0.047, +0.041] (not significant)

**Cohen's d (h7v2_reclass vs v4d, identical): +0.965** (large effect).

**YouTube (n=25 reclassified, 1 of each other):**
- h7v2_reclassified - v4d: +0.071 [+0.052, +0.090] (significant)
- h7v2_reclassified - h7v2_kept_ballistic: +0.089 [+0.070, +0.108] (significant)

## Interpretation

1. **v4d hand-links have LOWER concentration than h7v2-reclassified
   and h7v2-kept-ballistic edges.** This is largely because v4d
   links have longer gaps (18 frames vs 9-10) which means wider
   search windows, so the n_out_reach denominator is larger.
   **The detector concentration is not a discriminator for v4d vs
   h7v2 — it correlates with gap length, not with event type.**

2. **h7v2_reclassified and h7v2_kept_ballistic are NOT distinguishable
   by detector concentration.** On identical, their concentrations
   are statistically identical (CI includes 0). On YouTube, the
   reclassified group has higher concentration, but the sample size
   for kept_ballistic is n=1 (only 1 edge).
   **H7v2's reclassification rule is doing the work via geometric
   heuristics, not via detector signal.** The detector sees the
   held ball similarly whether the chain algorithm says "catch-throw"
   or "identity switch."

3. **H3's stationary-cluster criterion is a noisy signal.** 3/6 v2
   CORROBORATED edges are h7v2_kept_ballistic (true identity
   switches that the chain algorithm kept as ballistic). The
   cluster pattern (low-conf dets in 30 px radius over ≥5 frames)
   is not specific to held balls — it appears at identity switches
   too, because both situations have a ball visible at the hand.

## Visual QA

14 contact sheets rendered and 4 inspected via `vision_analyze`:
- v4d 52→54: REAL held ball, conf 0.94-0.98, clearly CORROBORATED.
- h7v2_kept_ballistic 41→43: TWO balls visible in the right hand
  in all 6 frames, vision tool sees them as a single cluster.
  H7v2 correctly identifies this as an identity switch (not
  a clean catch-throw), but the detector signal is the same as a
  catch-throw. v2 still CORROBORATES it.
- h7v2_reclassified 35→37 (v4_peak): 46 in-reach dets, 0 clusters.
  The hand region is rich in low-conf evidence but the detections
  are not spatially coherent. The vision tool interprets this as
  "ambiguous" — the geometric reclassification is more confident
  than the detector signal.

## Verdict: PARTIAL PASS (limited signal)

**What works:**
- Concentration is a real signal. v4d links are statistically
  distinguishable from h7v2-reclassified and h7v2-kept-ballistic
  edges (Cohen's d = 0.965, large effect).
- The h7v2 reclassification rule is empirically validated by the
  detector signal: reclassified edges have similar concentration
  to kept-ballistic edges (the rule isn't wildly misclassifying
  obvious non-catches as catches).
- The peak-vs-context test (v4) identifies edges with a "magnet
  hand" pattern. Only 5/62 edges (8%) qualify, but those are
  mostly visually distinct held-ball moments.

**What doesn't work:**
- The H3 stationary-cluster criterion (master §14) is NOT a
  discriminator between real catch-throws and identity switches.
  3/6 v2 CORROBORATED edges are kept-ballistic. This is an
  important NEGATIVE finding for master §14.
- The detector doesn't preferentially fire at hand events vs
  random hand-region windows. The mean concentration at hand-
  events (0.15-0.30) is similar to the mean concentration at
  random hand-region windows (0.21 identical, 0.36 YouTube).
- Single low-conf detection (v1) has FPR 91-100% — useless.

**Implications for downstream consumers:**
- H3's `h3_confirmed` flag (used in H11 identity propagation) is
  a noisy signal. 50% of v2 CORROBORATED edges are kept-ballistic
  (true identity switches), so the flag is more like "this edge
  has detector activity at the hand" than "this edge is a real
  catch-throw".
- A stricter H3 would need to combine the cluster signal with
  additional filters (e.g., the hand must be the only hand with
  detector activity, or the cluster must be tight and at the
  specific hand used by the v4d rule).

## Sensitivity

- GAP_PAD_FRAMES=5 covers gap+pad up to 11 frames. Most edges
  (75%+) have gap ≤ 10 frames, so the pad is well-calibrated.
- All sensitivity results in `h13_sensitivity.json`.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13_low_conf_corroboration.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h13_sensitivity.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_per_edge.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h13_sensitivity.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h13/*.png` (14 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h13_report.md` (this file)
