#!/usr/bin/env python3
"""
H55 sensitivity grid: sweep w54 over {0.0, 0.10, 0.20, 0.30, 0.40, 0.50}
and report the impact on multi-tid CONFIDENT vs UNCERTAIN/LOW classification.
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

W54_VALUES = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
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
            out[r["chain_id"]] = float(gcv) if gcv else None
    return out


def main():
    summary = {"videos": {}, "config": {"W54_VALUES": W54_VALUES}}
    for stem in STEMS:
        print(f"\n=== {stem} (H55 sensitivity grid) ===")
        h10 = load_h10v10(stem)
        gcv = load_h54_gcv(stem)
        # Get v11 quality per w54
        results_per_w = {}
        for w54 in W54_VALUES:
            chains = []
            for cid, info in h10.items():
                q10 = info["q"]
                if q10 is None:
                    continue
                g = gcv.get(cid)
                g_penalty = g if g is not None else 0.0
                q11 = max(0.0, min(1.0, q10 - w54 * g_penalty))
                chains.append({"chain_id": cid, "q10": q10, "g_cv": g,
                               "q11": q11, "n_tracklets": info["n_tracklets"]})
            results_per_w[w54] = chains
        # Per-w54 stats
        for w54 in W54_VALUES:
            chains = results_per_w[w54]
            n_conf = sum(1 for c in chains if c["q11"] >= QUALITY_CONFIDENT)
            n_trust = sum(1 for c in chains if QUALITY_TRUSTABLE <= c["q11"] < QUALITY_CONFIDENT)
            n_low = sum(1 for c in chains if c["q11"] < QUALITY_TRUSTABLE)
            mean_q = statistics.mean(c["q11"] for c in chains)
            # Multi-tid stats
            multi = [c for c in chains if c["n_tracklets"] >= 2]
            multi_conf = sum(1 for c in multi if c["q11"] >= QUALITY_CONFIDENT)
            multi_mean = statistics.mean(c["q11"] for c in multi) if multi else None
            print(f"  w54={w54:.2f}: n_conf={n_conf}, n_trust={n_trust}, n_low={n_low}, "
                  f"mean_q={mean_q:.4f}, multi_n={len(multi)}, "
                  f"multi_n_conf={multi_conf}, multi_mean_q={multi_mean:.4f}")
            summary["videos"].setdefault(stem, {})[f"w54_{w54:.2f}"] = {
                "n_conf": n_conf, "n_trust": n_trust, "n_low": n_low,
                "mean_q": round(mean_q, 4),
                "multi_n": len(multi),
                "multi_n_conf": multi_conf,
                "multi_mean_q": round(multi_mean, 4) if multi_mean else None,
            }

    out_path = H1_DATA / "h55_sensitivity_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
