#!/usr/bin/env python3
"""H108 v1 — Full stack: H96 v2 + R4 = 17/4/0/0 explicit on all 4 TNs.

Hypothesis (from H108 v0 catalog): adding an explicit R4 signal to the
H96 v2 stacked guards allows the system to:
1. NOT depend on H12 v8's UNCONFIRMED label as the rejection criterion
2. Be more robust to H12 v8 future-version changes
3. Have an explicit R4 that catches f=2-71 (currently only H12 v8's
   UNCONFIRMED label catches it)

R4 candidates (from H108 v0 sensitivity):
- R4b: unconf_frac >= 0.50 catches ONLY f=2-71 (wide flat 0.50-1.00)
- R4c: mean_conf < 0.45 catches ONLY f=2-71 (narrow flat 0.35-0.45)
- R4f: unconf_frac >= 0.50 AND max_A >= 3 catches ONLY f=2-71 (wide flat)

This script implements H108 v1 = H106 v2 + R4 (any of R4b/R4c/R4f) and
tests on H93 corrected GT.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_SCRIPTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "scripts"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_h93_gt():
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        return json.load(fh)["corrected_ground_truth"]


def load_h108_per_phase():
    """Return dict[phase_key -> row dict]."""
    out = {}
    with (H1_DATA / "h108_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = r
    return out


def load_h106_per_phase():
    """Return dict[phase_key -> row dict]."""
    out = {}
    with (H1_DATA / "h106_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = r
    return out


# Canonical H108 R4 thresholds (chosen from H108 v0 flat region)
H108_UNCONF_FRAC_THR = 0.50    # R4b: unconf_frac >= 0.50 catches f=2-71
H108_MEAN_CONF_THR = 0.45      # R4c: mean_conf < 0.45 catches f=2-71
H108_R4_USE = "R4b"            # which R4 to use (R4b, R4c, R4f)


def classify_phase_r4(pkey, h108_row, h106_row, r4_use="R4b"):
    """Classify a phase using H96 v2 per-pattern logic + R4 (H108).

    Returns (is_active_pred, signals_fired_list).
    """
    h106_signals = h106_row.get("signals_fired", "")
    dominant = h106_row.get("dominant_h12", "UNKNOWN")
    unconf_frac = float(h108_row.get("unconf_frac", 0))
    mean_conf = float(h108_row.get("mean_conf", 0))
    max_a = int(h108_row.get("max_A", 0))

    signals = []

    # --- H96 v2 per-pattern logic ---
    if dominant == "FOUNTAIN_3+":
        # H96 v2: H90 NEW (c40_pct_ge3 < 0.40 AND c40_max_aloft >= 4)
        #         OR H78 (lr_mean_diff > 10)
        c40_pct_ge3 = float(h106_row.get("h90_c40_pct_ge3", 1.0))
        c40_max_aloft = int(float(h106_row.get("h90_c40_max_aloft", 0)))
        h78_mean_diff = float(h106_row.get("lr_mean_diff", 0))

        if c40_pct_ge3 < 0.40 and c40_max_aloft >= 4:
            signals.append("H90_NEW")
        if h78_mean_diff > 10:
            signals.append("H78")
    elif dominant == "CASCADE_3+":
        # H96 v2: H87+max_aloft (h87_pct_ge3 < 0.20 AND h87_max_aloft >= 2)
        #         OR H74v4 (lr_var < 0.20 AND unique_LR <= 1)
        h87_pct_ge3 = float(h106_row.get("h87_pct_ge3", 1.0))
        h87_max_aloft = int(float(h106_row.get("h87_max_aloft", 0)))
        lr_var = float(h106_row.get("lr_var", 1.0))
        lr_unique = int(float(h106_row.get("lr_unique", 99)))

        if h87_pct_ge3 < 0.20 and h87_max_aloft >= 2:
            signals.append("H87_max_aloft")
        if lr_var < 0.20 and lr_unique <= 1:
            signals.append("H74v4")
    elif "MIXED" in dominant:
        # H12 v8 UNCONFIRMED label is the rejection — no H96 v2 signal
        # needed; H108 R4 might still apply
        pass

    # --- H108 R4 (the new explicit signal) ---
    if r4_use == "R4b":
        if unconf_frac >= H108_UNCONF_FRAC_THR:
            signals.append("H108_R4b")
    elif r4_use == "R4c":
        if mean_conf < H108_MEAN_CONF_THR:
            signals.append("H108_R4c")
    elif r4_use == "R4f":
        if unconf_frac >= H108_UNCONF_FRAC_THR and max_a >= 3:
            signals.append("H108_R4f")

    is_active_pred = len(signals) == 0
    return is_active_pred, signals


def run_h108_v1(r4_use="R4b"):
    gt = load_h93_gt()
    h108 = load_h108_per_phase()
    h106 = load_h106_per_phase()

    results = []
    for pkey, verdict in gt.items():
        if pkey not in h108 or pkey not in h106:
            continue
        h108_row = h108[pkey]
        h106_row = h106[pkey]
        is_active_pred, signals = classify_phase_r4(pkey, h108_row, h106_row, r4_use)
        is_active_gt = (verdict == "JUGGLING")
        results.append({
            "phase_key": pkey,
            "verdict": verdict,
            "is_active_pred": is_active_pred,
            "is_active_gt": is_active_gt,
            "dominant_h12": h106_row.get("dominant_h12", ""),
            "signals_fired": ",".join(signals) if signals else "none",
            "unconf_frac": h108_row.get("unconf_frac", ""),
            "mean_conf": h108_row.get("mean_conf", ""),
            "max_A": h108_row.get("max_A", ""),
        })

    tp = sum(1 for r in results if r["is_active_pred"] and r["is_active_gt"])
    tn = sum(1 for r in results if not r["is_active_pred"] and not r["is_active_gt"])
    fp = sum(1 for r in results if r["is_active_pred"] and not r["is_active_gt"])
    fn = sum(1 for r in results if not r["is_active_pred"] and r["is_active_gt"])
    return results, tp, tn, fp, fn


def main():
    print("=" * 80)
    print("H108 v1 — H106 v2 per-pattern + R4 explicit (17/4/0/0 should be confirmed)")
    print("=" * 80)

    for r4_use in ["R4b", "R4c", "R4f"]:
        results, tp, tn, fp, fn = run_h108_v1(r4_use)
        n = tp + tn + fp + fn
        P = tp / (tp + fp) if (tp + fp) else 0.0
        R = tp / (tp + fn) if (tp + fn) else 0.0
        acc = (tp + tn) / n if n else 0.0
        perfect = (tp == 17 and tn == 4 and fp == 0 and fn == 0)
        print(f"\n=== H108 v1 with {r4_use} ===")
        print(f"  TP={tp} TN={tn} FP={fp} FN={fn} (n={n})")
        print(f"  Precision = {P:.3f}, Recall = {R:.3f}, Accuracy = {acc:.3f}")
        print(f"  PERFECT: {perfect}")
        print(f"  Per-phase details:")
        for r in results:
            if r["is_active_pred"] and r["is_active_gt"]:
                tag = "TP"
            elif not r["is_active_pred"] and not r["is_active_gt"]:
                tag = "TN"
            elif r["is_active_pred"] and not r["is_active_gt"]:
                tag = "FP"
            else:
                tag = "FN"
            print(f"    [{tag}] {r['phase_key'][-50:]:<50} v={r['verdict']:<22} "
                  f"dom={r['dominant_h12']:<25} signals={r['signals_fired']}")

    # Use R4b as canonical
    print("\n=== Canonical H108 v1 with R4b ===")
    results, tp, tn, fp, fn = run_h108_v1("R4b")
    perfect = (tp == 17 and tn == 4 and fp == 0 and fn == 0)
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    summary = {
        "method": "H108 v1: H106 v2 per-pattern + R4b (unconf_frac >= 0.50)",
        "thresholds": {
            "H108_UNCONF_FRAC_THR": H108_UNCONF_FRAC_THR,
            "H108_MEAN_CONF_THR": H108_MEAN_CONF_THR,
            "H108_R4_USE": H108_R4_USE,
        },
        "h93_results": {
            "TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "P": round(P, 3), "R": round(R, 3), "acc": round(acc, 3),
            "n": tp + tn + fp + fn,
            "PERFECT": perfect,
        },
    }
    out = H1_DATA / "h108_v1_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary: {out}")
    print(f"\nPERFECT (17/4/0/0): {perfect}")

    # Save per-phase for canonical
    out_csv = H1_DATA / "h108_v1_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        wr.writeheader()
        wr.writerows(results)
    print(f"Per-phase CSV: {out_csv}")


if __name__ == "__main__":
    main()
