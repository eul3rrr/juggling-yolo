#!/usr/bin/env python3
"""H14 sensitivity grid: sweep V_DEEP/V_SHALLOW thresholds and report counts.

Output: number of BALLISTIC edges classified as V_DEEP, V_SHALLOW, FLAT
        for each (min_d, ratio) combination.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/scripts")))
from h14_v_shape import (
    v_shape_check, get_h7v2_ballistic, get_h7v2_reclassified, get_v4d_links,
    load_wrist_frames,
)

H14_DATA = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data")


def main():
    print("H14 sensitivity grid: sweep V_DEEP/V_SHALLOW thresholds")

    # Thresholds to sweep
    deep_mins = [30, 40, 50, 60, 80]
    deep_ratios = [1.3, 1.5, 1.8, 2.0]
    shallow_mins = [80, 100, 120, 150]
    shallow_ratios = [1.1, 1.2, 1.3, 1.5]

    ballistic = get_h7v2_ballistic()
    reclassified = get_h7v2_reclassified()
    v4d = get_v4d_links()
    by_stem = defaultdict(lambda: {"ballistic": [], "reclassified": [], "v4d": []})
    for e in ballistic:
        by_stem[e["stem"]]["ballistic"].append(e)
    for e in reclassified:
        by_stem[e["stem"]]["reclassified"].append(e)
    for e in v4d:
        by_stem[e["stem"]]["v4d"].append(e)

    # Pre-compute v_shape for each edge per stem
    all_v = defaultdict(dict)  # (stem, kind, from_tid, to_tid) -> v_result
    for stem, groups in by_stem.items():
        wrist_frames = load_wrist_frames(stem)
        for kind, edges in groups.items():
            for e in edges:
                v = v_shape_check(e, wrist_frames)
                if v is not None:
                    all_v[(stem, kind, e["from_tid"], e["to_tid"])] = v

    # Sweep (using only V_DEEP_MIN, V_DEEP_RATIO; V_SHALLOW is the "mild" class)
    print(f"\n{'deep_min':>9} {'deep_r':>7}  "
          f"{'BALL V_DEEP':>13} {'BALL V_SHALLOW':>16} {'BALL FLAT':>11}  "
          f"{'RECL V_DEEP':>13} {'v4d V_DEEP':>11}")

    grid = []
    for dmin in deep_mins:
        for dratio in deep_ratios:
            ball_deep = ball_shallow = ball_flat = 0
            recl_deep = v4d_deep = 0
            for (stem, kind, ftid, ttid), v in all_v.items():
                cls = "FLAT"
                if v["min_hand_dist"] < dmin and v["ratio"] >= dratio:
                    cls = "V_DEEP"
                elif v["min_hand_dist"] < 100 and v["ratio"] >= 1.3:
                    cls = "V_SHALLOW"
                if kind == "ballistic":
                    if cls == "V_DEEP": ball_deep += 1
                    elif cls == "V_SHALLOW": ball_shallow += 1
                    else: ball_flat += 1
                elif kind == "reclassified":
                    if cls == "V_DEEP": recl_deep += 1
                elif kind == "v4d":
                    if cls == "V_DEEP": v4d_deep += 1
            print(f"{dmin:>9} {dratio:>7.1f}  "
                  f"{ball_deep:>13} {ball_shallow:>16} {ball_flat:>11}  "
                  f"{recl_deep:>13} {v4d_deep:>11}")
            grid.append({
                "deep_min": dmin, "deep_ratio": dratio,
                "ball_v_deep": ball_deep, "ball_v_shallow": ball_shallow, "ball_flat": ball_flat,
                "recl_v_deep": recl_deep, "v4d_v_deep": v4d_deep,
            })

    # Save
    out = {"grid": grid, "n_ballistic": len(ballistic), "n_reclassified": len(reclassified), "n_v4d": len(v4d)}
    out_path = H14_DATA / "h14_sensitivity.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {out_path}")

    # Also print per-edge classification for inspection
    print("\nPer-edge classification at default (50, 1.5):")
    for (stem, kind, ftid, ttid), v in sorted(all_v.items()):
        cls = "FLAT"
        if v["min_hand_dist"] < 50 and v["ratio"] >= 1.5:
            cls = "V_DEEP"
        elif v["min_hand_dist"] < 100 and v["ratio"] >= 1.3:
            cls = "V_SHALLOW"
        print(f"  {kind:<14} {stem[:25]:<25} {ftid:>3}->{ttid:<3}  "
              f"min_d={v['min_hand_dist']:>5.1f} ratio={v['ratio']:>4.2f}  cls={cls}")


if __name__ == "__main__":
    main()
