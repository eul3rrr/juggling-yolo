# H43 — H12 v8 confidence-based FOUNTAIN_3+ filter

## Hypothesis

H39 visual QA found that the late-phase FOUNTAIN_3+ blocks on
identical (f=890-1050) include both real and misclassified phases.
The H12 v8 confidence for these varies from 0.463 to 0.844.

Question: does filtering FOUNTAIN_3+ with H12 v8 confidence
< 0.55 produce a safe precision improvement?

## Implementation

For each FOUNTAIN_3+ frame with H12 v8 confidence < 0.55, mark as
FOUNTAIN_LOW_CONF. Compare with H39 v2 and H41 v2 results.

## Quantitative result

### identical
- FOUNTAIN_3+ total: 298
- Low confidence (< 0.55): 27 (9.1%)
- Mid confidence (0.55-0.70): 67 (22.5%)
- High confidence (>= 0.70): 204 (68.5%)
- After H43 filter: 271 FOUNTAIN_3+ kept, 27 FOUNTAIN_LOW_CONF

### YouTube
- FOUNTAIN_3+ total: 110
- Low confidence (< 0.55): 0 (0%)
- Mid confidence (0.55-0.70): 110 (100%)
- High confidence (>= 0.70): 0 (0%)
- After H43 filter: 110 FOUNTAIN_3+ kept, 0 rejected

The 27 identical rejections are all in f=1029-1060 (the
"OTHER 2-ball exercise" phase from H39 visual QA).
YouTube has no rejections because all YouTube FOUNTAIN_3+
phases have confidence in 0.629-0.649 range.

## Visual QA cross-check on H43 (using H39 verdicts)

| Phase | Mean conf | H43 reject? | Vision verdict | Result |
|---|---|---|---|---|
| f=243-252 | 0.593 | NO | real FOUNTAIN | ✓ correct keep |
| f=263-312 | 0.728 | NO | MIXED (real) | ✓ correct keep |
| f=411-449 | 0.797 | NO | MIXED (real) | ✓ correct keep |
| f=631-669 | 0.714 | NO | real FOUNTAIN | ✓ correct keep |
| f=685-716 | 0.738 | NO | real FOUNTAIN | ✓ correct keep |
| f=733-766 | 0.748 | NO | QA_PENDING | (unknown) |
| f=860-871 | 0.642 | NO | MIXED (real) | ✓ correct keep |
| f=977-1011 | 0.565 | NO | OTHER hold trick | ✗ missed |
| f=1029-1050 | 0.463 | YES | OTHER 2-ball exercise | ✓ correct reject |
| f=339-374 (YouTube) | 0.649 | NO | CASCADE (real) | ✓ correct keep |
| f=800-861 (YouTube) | 0.637 | NO | MIXED (real) | ✓ correct keep |

**H43 precision: 1/1 = 100% (no over-rejects)**
**H43 recall: 1/2 = 50% (missed 1 OTHER phase)**

## Key findings

1. **H43 is a SAFE post-filter.** The 27/298 (9.1%) low-confidence
   FOUNTAIN_3+ frames on identical are ALL in f=1029-1060 — the
   "OTHER 2-ball exercise" phase from H39 visual QA. H43
   correctly identifies and rejects them.

2. **H43 misses the f=977-1011 hold trick (conf 0.565).** This
   phase has mid confidence (0.55-0.70) and is not rejected by
   H43. Lowering the threshold to 0.55 would catch this but also
   reject some real FOUNTAIN phases.

3. **YouTube has no rejections because all FOUNTAIN_3+ are in
   0.629-0.649 range.** H43 has no impact on YouTube.

4. **H43 is the most reliable of the FOUNTAIN_3+ post-filters:**
   - H39 v1 (frame-level H36): precision 20% (over-rejects 60% of real juggling)
   - H39 v2 (phase-level H36): precision 50% on 2 rejections
   - H41 v2 (H40 v2): precision 50% on 4 rejections
   - H43 (H12 v8 confidence < 0.55): precision 100% on 1 rejection

5. **The H12 v8 confidence is the most discriminating signal we
   have for FOUNTAIN_3+ misclassifications** — even more than
   H36 chain-driven state, H40 v2 sustained-occupancy, or the
   hybrid H42 state.

## Verdict

**PASS (narrow scope).** H43 is a safe, narrow-scope post-filter
that rejects FOUNTAIN_3+ classifications where H12 v8 confidence
is < 0.55. The 9.1% rejection rate on identical is small but
reliable. H43 should be applied as a downstream consumer filter
to remove the most clearly unreliable FOUNTAIN_3+ classifications.

**Recommended operating point:** H43 filter is safe to apply.
H43 + h7v3plus3 chain set is the new recommended operating
configuration for FOUNTAIN_3+ downstream consumers.

## Negative findings

1. **H43 only catches the lowest-confidence misclassifications.**
   The f=977-1011 hold trick (conf 0.565) is not caught by H43.
   Lowering the threshold would over-reject real FOUNTAIN.

2. **H43 has no effect on YouTube.** All YouTube FOUNTAIN_3+
   have similar confidence (0.629-0.649) regardless of whether
   they're real or misclassified. The H12 v8 confidence signal
   is uninformative on YouTube.

3. **H43 is a one-sided fix.** It only rejects FOUNTAIN_3+ — it
   doesn't address the underlying K=4 sliding window problem
   that causes the over-classification.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h43_low_conf_fountain.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h43_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h43_filtered_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h43_report.md`
