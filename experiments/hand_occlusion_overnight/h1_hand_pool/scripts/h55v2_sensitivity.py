#!/usr/bin/env python3
"""
H55 v2 sensitivity grid: w54 ∈ {0.0, 0.10, 0.20, 0.30, 0.40, 0.50},
gated by n_arcs_clean >= MIN_ARCS_FOR_PENALTY ∈ {2, 3, 4}.

For each (w54, min_arcs) cell, report:
- n_chains penalized
- n_CONFIDENT, n_TRUSTABLE, n_LOW
- mean q
- multi-tid CONFIDENT count (the key metric)
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

W54_VALUES = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
MIN_ARCS_VALUES = [2, 3, 4]
STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4


def load_h10v10(stem):
    path = H1_DATA / f"h10v10_h7v3plus3_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            q = r["quality_v10"]
            out[r["chain_id"]] = {
                "q": float(q) if q else None,
                "n_tracklets": int(r["n_tracklets"]),
            }
    return out


def load_h54_gcv(stem):
    path = H1_DATA / f"h54_per_chain_arc_gravity_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            gcv = r["g_cv_clean"]
            out[r["chain_id"]] = {
                "g_cv": float(gcv) if gcv else None,
                "n_arcs_clean": int(r["n_arcs_clean"]),
            }
    return out


def main():
    summary = {"videos": {}, "config": {
        "W54_VALUES": W54_VALUES, "MIN_ARCS_VALUES": MIN_ARCS_VALUES,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H55 v2 sensitivity) ===")
        h10 = load_h10v10(stem)
        h54 = load_h54_gcv(stem)
        for min_arcs in MIN_ARCS_VALUES:
            print(f"  min_arcs={min_arcs}:")
            for w54 in W54_VALUES:
                chains = []
                for cid, info in h10.items():
                    q10 = info["q"]
                    if q10 is None:
                        continue
                    h54_info = h54.get(cid, {"g_cv": None, "n_arcs_clean": 0})
                    n_arcs = h54_info["n_arcs_clean"]
                    g_cv = h54_info["g_cv"]
                    if n_arcs >= min_arcs and g_cv is not None:
                        g_penalty = g_cv
                    else:
                        g_penalty = 0.0
                    q11 = max(0.0, min(1.0, q10 - w54 * g_penalty))
                    chains.append({"q11": q11, "q10": q10, "n_tracklets": info["n_tracklets"]})
                n_conf = sum(1 for c in chains if c["q11"] >= QUALITY_CONFIDENT)
                n_trust = sum(1 for c in chains if QUALITY_TRUSTABLE <= c["q11"] < QUALITY_CONFIDENT)
                n_low = sum(1 for c in chains if c["q11"] < QUALITY_TRUSTABLE)
                mean_q = statistics.mean(c["q11"] for c in chains)
                multi = [c for c in chains if c["n_tracklets"] >= 2]
                multi_conf = sum(1 for c in multi if c["q11"] >= QUALITY_CONFIDENT)
                n_pen = sum(1 for c in chains if c["q11"] < c["q10"] - 0.01)
                print(f"    w54={w54:.2f}: n_pen={n_pen}, n_conf={n_conf}, "
                      f"n_trust={n_trust}, n_low={n_low}, mean_q={mean_q:.4f}, "
                      f"multi_conf={multi_conf}/{len(multi)}")
                summary["videos"].setdefault(stem, {})[f"min_arcs_{min_arcs}_w54_{w54:.2f}"] = {
                    "n_pen": n_pen, "n_conf": n_conf, "n_trust": n_trust,
                    "n_low": n_low, "mean_q": round(mean_q, 4),
                    "multi_conf": multi_conf, "multi_total": len(multi),
                }

    out_path = H1_DATA / "h55v2_sensitivity_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
