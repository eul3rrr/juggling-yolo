#!/usr/bin/env python3
"""
H92 v2 — Sensitivity grid for H92 v1 thresholds.

Sweep PCT_GE2_THRESHOLD in {0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30}
on the 21-phase H70 sample.

Confirm the 0.15 operating point is in a flat region (per master §15).
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

# Reuse H92 v1 functions
sys.path.insert(0, str(Path(__file__).parent))
from h92_v1_pct_ge2 import (
    BALLS_CSV, POSE_CSV, ALOFT_RADIUS, GT, REAL_VERDICTS, MISCLASS_VERDICTS, STEMS,
    load_balls_with_conf, load_wrists, dist, compute_aloft_per_frame, h82_h87_h71_catches
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
DETECTIONS = WORKTREE / "detections"
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"


def h92_reject_with_thr(key, phase_signals, pct_ge2_thr, pct_ge3_thr=0.20):
    stem, start, end = key
    if h82_h87_h71_catches(key):
        return True, "baseline"
    sig = phase_signals.get(key, {})
    if stem.startswith("ident"):
        pct_ge3_0 = sig.get("pct_ge3_0", 1.0)
        pct_ge2_0 = sig.get("pct_ge2_0", 1.0)
        if pct_ge3_0 < pct_ge3_thr and pct_ge2_0 < pct_ge2_thr:
            return True, "h92"
        return False, ""
    else:
        pct_ge3_4 = sig.get("pct_ge3_4", 1.0)
        if pct_ge3_4 < 0.30:
            return True, "h89_strict"
        if pct_ge3_4 < 0.40:
            max_4 = sig.get("max_4", 0)
            drop = sig.get("drop", 0)
            if max_4 >= 4 or drop > 0.38:
                return True, "h90_new"
        return False, ""


def main():
    print("=" * 80)
    print("H92 v2 — Sensitivity grid for pct_ge2 threshold")
    print("=" * 80)

    balls_c0 = {stem: load_balls_with_conf(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls_with_conf(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    phase_signals = {}
    for key, gt in GT.items():
        stem, start, end = key
        n_aloft_0, n_total_0 = compute_aloft_per_frame(balls_c0[stem], wrists_data[stem], start, end)
        n_aloft_4, n_total_4 = compute_aloft_per_frame(balls_c4[stem], wrists_data[stem], start, end)
        if not n_aloft_0 or not n_aloft_4:
            continue
        pct_ge1_0 = sum(1 for n in n_aloft_0 if n >= 1) / len(n_aloft_0)
        pct_ge2_0 = sum(1 for n in n_aloft_0 if n >= 2) / len(n_aloft_0)
        pct_ge3_0 = sum(1 for n in n_aloft_0 if n >= 3) / len(n_aloft_0)
        pct_ge3_4 = sum(1 for n in n_aloft_4 if n >= 3) / len(n_aloft_4)
        max_4 = max(n_aloft_4)
        drop = pct_ge3_0 - pct_ge3_4
        phase_signals[key] = {
            "verdict": gt[1], "pct_ge1_0": pct_ge1_0, "pct_ge2_0": pct_ge2_0,
            "pct_ge3_0": pct_ge3_0, "pct_ge3_4": pct_ge3_4, "max_4": max_4, "drop": drop,
        }

    # Sweep
    print("\nSweeping pct_ge2_threshold in {0.05, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30}:")
    print(f"{'thr':>6} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6} {'iFN':>3} {'iFP':>3}")
    grid = {}
    for pct_ge2_thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]:
        TP = TN = FP = FN = 0
        iTP = iTN = iFP = iFN = 0
        for key, gt in GT.items():
            stem, start, end = key
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            rejected, via = h92_reject_with_thr(key, phase_signals, pct_ge2_thr)
            keep = not rejected
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and rejected: FN += 1
            if stem.startswith("ident"):
                if is_real and keep: iTP += 1
                elif is_real and not keep: iFN += 1
                elif is_misclass and keep: iFP += 1
                elif is_misclass and not keep: iTN += 1
        p = TP / max(1, TP+FP)
        r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        print(f"{pct_ge2_thr:>6.2f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p:>6.3f} {r:>6.3f} {acc:>6.3f} {iFN:>3} {iFP:>3}")
        grid[pct_ge2_thr] = {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "P": round(p, 3), "R": round(r, 3), "acc": round(acc, 3), "iFN": iFN, "iFP": iFP}

    # Flat region analysis
    print("\nFlat region analysis:")
    flat_thrs = [thr for thr, m in grid.items() if m["TP"] == 14 and m["TN"] == 7 and m["FP"] == 0 and m["FN"] == 0]
    if flat_thrs:
        print(f"  Flat region: pct_ge2 in {min(flat_thrs):.2f} to {max(flat_thrs):.2f} ({len(flat_thrs)} thresholds)")
    else:
        print(f"  No flat region with 14/7/0/0.")

    # Save grid
    with open(f"{H1_DATA}/h92_v2_sens_grid.json", "w") as f:
        json.dump({
            "pct_ge3_threshold": 0.20,
            "pct_ge2_thresholds": grid,
            "flat_region_thresholds": flat_thrs,
            "recommended": 0.15,
        }, f, indent=2)
    print(f"\nWrote {H1_DATA}/h92_v2_sens_grid.json")


if __name__ == "__main__":
    main()
