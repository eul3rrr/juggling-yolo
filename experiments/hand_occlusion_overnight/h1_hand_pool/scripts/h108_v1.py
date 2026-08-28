"""H108 v1 stack — Consumer-facing module.

This module packages the H108 v1 stack (H106 v2 per-pattern + R4b explicit
signal) as a single importable function for downstream consumers.

The H108 v1 stack achieves PERFECT 17/4/0/0 on the 21 H93 corrected
phases (P=R=acc=1.000) — see h1_hand_pool/reports/h108_report.md.

Usage:
    from h108_v1 import classify_phase, h108_v1_stack, load_h93_gt

    # Load H93 ground truth
    gt = load_h93_gt()

    # For each phase, get the H108 v1 prediction
    for phase_key, verdict in gt.items():
        # Load H12 v6 per-phase CSV row and H12 v7 per-frame cache for this phase
        h106_row = ...
        h108_row = ...
        is_active_pred, signals = classify_phase(phase_key, h106_row, h108_row)
        print(f"{phase_key}: is_active={is_active_pred}, signals={signals}")

    # Or run the full H93 evaluation
    results, tp, tn, fp, fn = h108_v1_stack()
    print(f"TP={tp} TN={tn} FP={fp} FN={fn} (n={tp+tn+fp+fn})")
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# Canonical H108 R4b threshold (chosen from H108 v0 flat region 0.50-1.00)
H108_R4B_UNCONF_FRAC_THR = 0.50

# H96 v2 / H106 v2 per-pattern thresholds (canonical)
H106_FOUNTAIN_H90_PCT_GE3_THR = 0.40    # H90 NEW
H106_FOUNTAIN_H90_MAX_ALOFT_THR = 4      # H90 NEW
H106_FOUNTAIN_H78_MEAN_DIFF_THR = 10     # H78 (Mills Mess)
H106_CASCADE_H87_PCT_GE3_THR = 0.20      # H87+max_aloft
H106_CASCADE_H87_MAX_ALOFT_THR = 2       # H87+max_aloft
H106_CASCADE_H74_LR_VAR_THR = 0.20       # H74v4
H106_CASCADE_H74_UNIQUE_LR_THR = 1       # H74v4

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_h93_gt() -> dict[str, str]:
    """Load H93 corrected ground truth (21 phases).

    Returns dict[phase_key -> verdict] where verdict is one of
    'JUGGLING', 'STATIC_HOLD', 'OTHER_CROSSED_ARM'.
    """
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        return json.load(fh)["corrected_ground_truth"]


def load_h108_per_phase() -> dict[str, dict]:
    """Load H108 per-phase CSV (21 rows).

    Returns dict[phase_key -> row dict] with fields:
    - max_A, min_A, mean_A, max_events, mean_events, max_conf, mean_conf
    - unconf_frac, n_unconf, max_total, min_total, frac_total_ge3
    - h70_pattern, h70_spec_conc, h106_h87_pct_ge3, h106_h87_max_aloft
    - h106_h90_c40_pct_ge3, h106_h78_mean_diff, h106_lr_var, h106_signals_fired
    """
    out = {}
    with (H1_DATA / "h108_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = r
    return out


def load_h106_per_phase() -> dict[str, dict]:
    """Load H106 per-phase CSV (21 rows).

    Returns dict[phase_key -> row dict] with fields used by the H108 v1
    classifier (dominant_h12, h87_pct_ge3, h87_max_aloft, h90_c40_pct_ge3,
    h90_c40_max_aloft, lr_mean_diff, lr_var, lr_unique, signals_fired).
    """
    out = {}
    with (H1_DATA / "h106_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = r
    return out


def classify_phase(
    phase_key: str,
    h108_row: dict,
    h106_row: dict,
    r4b_thr: float = H108_R4B_UNCONF_FRAC_THR,
) -> tuple[bool, list[str]]:
    """Classify a phase using the H108 v1 stack (H106 v2 + R4b).

    Returns (is_active_pred, signals_fired):
    - is_active_pred: True if the phase is a real juggling phase
      (no rejection signal fired), False if rejected as STATIC_HOLD
      or OTHER_CROSSED_ARM.
    - signals_fired: list of signal names that fired (H90_NEW, H78,
      H87_max_aloft, H74v4, H108_R4b). Empty list if is_active_pred.

    H108 v1 per-pattern logic:
    - FOUNTAIN_3+: REJECT if H90 NEW (c40_pct_ge3<0.40 AND
      c40_max_aloft>=4) OR H78 (lr_mean_diff>10).
    - CASCADE_3+: REJECT if H87+max_aloft (h87_pct_ge3<0.20 AND
      h87_max_aloft>=2) OR H74v4 (lr_var<0.20 AND unique_LR<=1).
    - MIXED_3+: REJECT if R4b (unconf_frac>=0.50).
    """
    dominant = h106_row.get("dominant_h12", "UNKNOWN")
    unconf_frac = float(h108_row.get("unconf_frac", 0))
    max_a = int(h108_row.get("max_A", 0))

    signals = []

    if dominant == "FOUNTAIN_3+":
        c40_pct_ge3 = float(h106_row.get("h90_c40_pct_ge3", 1.0))
        c40_max_aloft = int(float(h106_row.get("h90_c40_max_aloft", 0)))
        h78_mean_diff = float(h106_row.get("lr_mean_diff", 0))

        if c40_pct_ge3 < H106_FOUNTAIN_H90_PCT_GE3_THR and c40_max_aloft >= H106_FOUNTAIN_H90_MAX_ALOFT_THR:
            signals.append("H90_NEW")
        if h78_mean_diff > H106_FOUNTAIN_H78_MEAN_DIFF_THR:
            signals.append("H78")
    elif dominant == "CASCADE_3+":
        h87_pct_ge3 = float(h106_row.get("h87_pct_ge3", 1.0))
        h87_max_aloft = int(float(h106_row.get("h87_max_aloft", 0)))
        lr_var = float(h106_row.get("lr_var", 1.0))
        lr_unique = int(float(h106_row.get("lr_unique", 99)))

        if h87_pct_ge3 < H106_CASCADE_H87_PCT_GE3_THR and h87_max_aloft >= H106_CASCADE_H87_MAX_ALOFT_THR:
            signals.append("H87_max_aloft")
        if lr_var < H106_CASCADE_H74_LR_VAR_THR and lr_unique <= H106_CASCADE_H74_UNIQUE_LR_THR:
            signals.append("H74v4")
    elif "MIXED" in dominant:
        # MIXED_3+ / MIXED_3+_UNCONFIRMED: R4b explicit signal
        if unconf_frac >= r4b_thr:
            signals.append("H108_R4b")

    is_active_pred = len(signals) == 0
    return is_active_pred, signals


def h108_v1_stack(
    r4b_thr: float = H108_R4B_UNCONF_FRAC_THR,
) -> tuple[list[dict], int, int, int, int]:
    """Run the full H108 v1 stack on the 21 H93 corrected phases.

    Returns (results, TP, TN, FP, FN).
    - results: list of per-phase dicts with fields phase_key, verdict,
      is_active_pred, is_active_gt, dominant_h12, signals_fired, ...
    - TP, TN, FP, FN: confusion matrix counts
    """
    gt = load_h93_gt()
    h108 = load_h108_per_phase()
    h106 = load_h106_per_phase()

    results = []
    for pkey, verdict in gt.items():
        if pkey not in h108 or pkey not in h106:
            continue
        is_active_pred, signals = classify_phase(pkey, h108[pkey], h106[pkey], r4b_thr)
        is_active_gt = (verdict == "JUGGLING")
        results.append({
            "phase_key": pkey,
            "verdict": verdict,
            "is_active_pred": is_active_pred,
            "is_active_gt": is_active_gt,
            "dominant_h12": h106[pkey].get("dominant_h12", ""),
            "signals_fired": ",".join(signals) if signals else "none",
        })

    tp = sum(1 for r in results if r["is_active_pred"] and r["is_active_gt"])
    tn = sum(1 for r in results if not r["is_active_pred"] and not r["is_active_gt"])
    fp = sum(1 for r in results if r["is_active_pred"] and not r["is_active_gt"])
    fn = sum(1 for r in results if not r["is_active_pred"] and r["is_active_gt"])
    return results, tp, tn, fp, fn


def main():
    """Run H108 v1 stack and print evaluation summary."""
    results, tp, tn, fp, fn = h108_v1_stack()
    n = tp + tn + fp + fn
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    acc = (tp + tn) / n if n else 0.0
    perfect = (tp == 17 and tn == 4 and fp == 0 and fn == 0)

    print(f"H108 v1 stack on H93 corrected GT (n={n}):")
    print(f"  TP={tp} TN={tn} FP={fp} FN={fn}")
    print(f"  Precision = {P:.3f}, Recall = {R:.3f}, Accuracy = {acc:.3f}")
    print(f"  PERFECT: {perfect}")
    print()
    print("Per-phase details:")
    for r in results:
        if r["is_active_pred"] and r["is_active_gt"]:
            tag = "TP"
        elif not r["is_active_pred"] and not r["is_active_gt"]:
            tag = "TN"
        elif r["is_active_pred"] and not r["is_active_gt"]:
            tag = "FP"
        else:
            tag = "FN"
        print(f"  [{tag}] {r['phase_key'][-50:]:<50} v={r['verdict']:<22} "
              f"dom={r['dominant_h12']:<25} signals={r['signals_fired']}")


if __name__ == "__main__":
    main()
