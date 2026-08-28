#!/usr/bin/env python3
"""
H92 v3 — 2D sensitivity grid for (pct_ge2, pct_ge3) thresholds on identical.

The H92 v1 rule is: REJECT if (pct_ge3 < 0.20) AND (pct_ge2 < 0.15).
This script sweeps both thresholds and finds the flat region.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from h92_v1_pct_ge2 import (
    BALLS_CSV, POSE_CSV, ALOFT_RADIUS, GT, REAL_VERDICTS, MISCLASS_VERDICTS, STEMS,
    load_balls_with_conf, load_wrists, dist, compute_aloft_per_frame, h82_h87_h71_catches
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"


def h92_reject_2d(key, phase_signals, pct_ge2_thr, pct_ge3_thr):
    stem, start, end = key
    if h82_h87_h71_catches(key):
        return True
    sig = phase_signals.get(key, {})
    if stem.startswith("ident"):
        pct_ge3_0 = sig.get("pct_ge3_0", 1.0)
        pct_ge2_0 = sig.get("pct_ge2_0", 1.0)
        if pct_ge3_0 < pct_ge3_thr and pct_ge2_0 < pct_ge2_thr:
            return True
        return False
    else:
        # YouTube: same as H90 v3
        pct_ge3_4 = sig.get("pct_ge3_4", 1.0)
        if pct_ge3_4 < 0.30:
            return True
        if pct_ge3_4 < 0.40:
            max_4 = sig.get("max_4", 0)
            drop = sig.get("drop", 0)
            if max_4 >= 4 or drop > 0.38:
                return True
        return False


def main():
    print("=" * 80)
    print("H92 v3 — 2D sensitivity grid for (pct_ge2, pct_ge3) thresholds")
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
        pct_ge2_0 = sum(1 for n in n_aloft_0 if n >= 2) / len(n_aloft_0)
        pct_ge3_0 = sum(1 for n in n_aloft_0 if n >= 3) / len(n_aloft_0)
        pct_ge3_4 = sum(1 for n in n_aloft_4 if n >= 3) / len(n_aloft_4)
        max_4 = max(n_aloft_4)
        drop = pct_ge3_0 - pct_ge3_4
        phase_signals[key] = {
            "pct_ge2_0": pct_ge2_0, "pct_ge3_0": pct_ge3_0,
            "pct_ge3_4": pct_ge3_4, "max_4": max_4, "drop": drop,
        }

    # 2D grid
    print("\n2D grid sweep (rows: pct_ge2 threshold, cols: pct_ge3 threshold):")
    print(f"Cell format: 'TP/TN/FP/FN acc'  — looking for 14/7/0/0 acc=1.000")
    pct_ge2_thrs = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]
    pct_ge3_thrs = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

    grid = {}
    for pg2 in pct_ge2_thrs:
        row = {}
        for pg3 in pct_ge3_thrs:
            TP = TN = FP = FN = 0
            for key, gt in GT.items():
                stem, start, end = key
                verdict = gt[1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                rejected = h92_reject_2d(key, phase_signals, pg2, pg3)
                keep = not rejected
                if is_real and keep: TP += 1
                elif is_misclass and not keep: TN += 1
                elif is_misclass and keep: FP += 1
                elif is_real and rejected: FN += 1
            acc = (TP+TN) / 21
            row[pg3] = {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "acc": round(acc, 3)}
            grid[(pg2, pg3)] = row[pg3]
        # Print row
        cells = "  ".join(f"pg3={pg3}:{row[pg3]['TP']}/{row[pg3]['TN']}/{row[pg3]['FP']}/{row[pg3]['FN']}={row[pg3]['acc']:.3f}" for pg3 in pct_ge3_thrs)
        print(f"pg2={pg2:>5.2f} | {cells}")

    # Find flat region (14/7/0/0)
    print("\nFlat region (14/7/0/0, acc=1.000):")
    flat_cells = [(pg2, pg3) for (pg2, pg3), m in grid.items() if m["TP"] == 14 and m["TN"] == 7 and m["FP"] == 0 and m["FN"] == 0]
    if flat_cells:
        for pg2, pg3 in flat_cells:
            print(f"  ({pg2}, {pg3})")
    print(f"\nTotal flat cells: {len(flat_cells)}")

    with open(f"{H1_DATA}/h92_v3_2d_grid.json", "w") as f:
        json.dump({
            "flat_cells": [{"pct_ge2_thr": pg2, "pct_ge3_thr": pg3} for pg2, pg3 in flat_cells],
            "n_flat": len(flat_cells),
            "recommended": {"pct_ge2_thr": 0.15, "pct_ge3_thr": 0.20},
        }, f, indent=2)
    print(f"\nWrote {H1_DATA}/h92_v3_2d_grid.json")


if __name__ == "__main__":
    main()
