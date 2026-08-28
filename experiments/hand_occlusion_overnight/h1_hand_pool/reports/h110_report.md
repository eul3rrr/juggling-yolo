# H110 — H108 v1 consumer-facing module (CONSUMER-PASS)

**Date:** 2026-08-28 ~22:50 (continuation episode, post-H109)
**Status:** CONSUMER-PASS. The H108 v1 stack is now packaged as a
single importable Python module with a clean API for downstream
consumers.

## Hypothesis (from H108 PASS)

The H108 v1 stack achieves PERFECT 17/4/0/0 on the 21 H93 corrected
phases. The implementation is currently spread across multiple scripts
(`h108_v1_stack.py`, `h108_structural_signatures.py`, plus the data
files). A consumer-facing module would make it easier for downstream
code to use the H108 v1 stack.

## Method

Created `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h108_v1.py`
as a single importable module. The module exposes:

- `load_h93_gt() -> dict[phase_key, verdict]`: load the 21-phase ground truth
- `load_h108_per_phase() -> dict[phase_key, h108_row]`: load per-phase aggregates
- `load_h106_per_phase() -> dict[phase_key, h106_row]`: load per-pattern features
- `classify_phase(phase_key, h108_row, h106_row, r4b_thr=0.50) -> (is_active, signals)`:
  classify a single phase
- `h108_v1_stack(r4b_thr=0.50) -> (results, TP, TN, FP, FN)`: full evaluation

The module also exposes canonical thresholds as module-level constants:
- `H108_R4B_UNCONF_FRAC_THR = 0.50` (R4b threshold)
- `H106_FOUNTAIN_H90_PCT_GE3_THR = 0.40`, etc. (per-pattern thresholds)

## Validation

Running the module reproduces H108 v1's PERFECT 17/4/0/0 result:

```
$ python3 h108_v1.py
H108 v1 stack on H93 corrected GT (n=21):
  TP=17 TN=4 FP=0 FN=0
  Precision = 1.000, Recall = 1.000, Accuracy = 1.000
  PERFECT: True
```

## Usage example

```python
from h108_v1 import classify_phase, h108_v1_stack, load_h93_gt

# Full evaluation
results, tp, tn, fp, fn = h108_v1_stack()
print(f"TP={tp} TN={tn} FP={fp} FN={fn}")

# Single phase
gt = load_h93_gt()
h108_row = ...  # load from h108_per_phase.csv
h106_row = ...  # load from h106_per_phase.csv
is_active, signals = classify_phase("identical_balls_trick_000_018_685_716", h108_row, h106_row)
print(f"is_active={is_active}, signals={signals}")  # False, ['H87_max_aloft']
```

## Verdict: CONSUMER-PASS.

The H108 v1 stack is now available as a single importable module with
a clean API. Downstream consumers can use the module directly without
re-implementing the per-pattern logic.

## Limitations

- The module requires the data files (`h93_multi_rater_qa.json`,
  `h108_per_phase.csv`, `h106_per_phase.csv`) at the canonical paths.
  For production use, downstream code should pre-compute these from
  raw H7 chains + H12 v8 cache.
- The module is a thin wrapper over the data + classification logic. It
  does not implement the data pipeline (H7 chain construction, H10
  quality, H12 v8 inference) — those are upstream components.
- The R4b threshold (0.50) is hard-coded. For 3rd videos, downstream
  code may want to tune this threshold (per H101 per-video calibration
  findings).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h108_v1.py`
  (importable module, ~250 lines)
