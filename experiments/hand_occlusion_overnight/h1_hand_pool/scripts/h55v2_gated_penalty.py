#!/usr/bin/env python3
"""
H55 v2: H10 v10 + H54 gravity-CV with gated penalty.

v1's linear penalty was too aggressive — chains with n_arcs_clean=0 or 1
have meaningless g_cv (it's just the variance of a single value or empty).
v2 only applies the g_cv penalty to chains with n_arcs_clean >= 2.

For chains with n_arcs_clean < 2, g_cv_penalty = 0 (no change from v10).

Additional v2 refinements:
- Use g_cv only for multi-tid chains (n_tracklets >= 2) — single-tid
  g_cv measures within-tracklet arc consistency, which is a different
  signal
- Or: use max(g_cv, 0) as a soft penalty gated by n_arcs_clean >= 3
  (need 3+ arcs to robustly estimate CV)
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# v2 settings
MIN_ARCS_FOR_PENALTY = 3  # need at least 3 clean arcs to robustly estimate CV
W54 = 0.30  # v2b: smaller weight to preserve chain 6 YouTube
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
    """Return chain_id -> {g_cv, n_arcs_clean, n_arcs_total}."""
    path = H1_DATA / f"h54_per_chain_arc_gravity_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            gcv = r["g_cv_clean"]
            out[r["chain_id"]] = {
                "g_cv": float(gcv) if gcv else None,
                "n_arcs_clean": int(r["n_arcs_clean"]),
                "n_arcs_total": int(r["n_arcs_total"]),
            }
    return out


def main():
    summary = {"videos": {}, "config": {
        "MIN_ARCS_FOR_PENALTY": MIN_ARCS_FOR_PENALTY, "W54": W54,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H55 v2 w54={W54}, min_arcs={MIN_ARCS_FOR_PENALTY}) ===")
        h10 = load_h10v10(stem)
        h54 = load_h54_gcv(stem)
        chains = []
        for cid, info in h10.items():
            q10 = info["q"]
            if q10 is None:
                continue
            h54_info = h54.get(cid, {"g_cv": None, "n_arcs_clean": 0, "n_arcs_total": 0})
            n_arcs = h54_info["n_arcs_clean"]
            g_cv = h54_info["g_cv"]
            # v2: only apply penalty if n_arcs_clean >= MIN_ARCS_FOR_PENALTY
            if n_arcs >= MIN_ARCS_FOR_PENALTY and g_cv is not None:
                g_penalty = g_cv
                penalized = True
            else:
                g_penalty = 0.0
                penalized = False
            q11 = max(0.0, min(1.0, q10 - W54 * g_penalty))
            chains.append({
                "chain_id": cid, "q10": q10, "q11": round(q11, 4),
                "g_cv": g_cv, "n_arcs_clean": n_arcs, "penalized": penalized,
                "n_tracklets": info["n_tracklets"],
            })
        # Sort
        chains.sort(key=lambda c: -c["q11"])
        n_conf = sum(1 for c in chains if c["q11"] >= QUALITY_CONFIDENT)
        n_trust = sum(1 for c in chains if QUALITY_TRUSTABLE <= c["q11"] < QUALITY_CONFIDENT)
        n_low = sum(1 for c in chains if c["q11"] < QUALITY_TRUSTABLE)
        mean_q = statistics.mean(c["q11"] for c in chains)
        n_penalized = sum(1 for c in chains if c["penalized"])
        print(f"  n_chains={len(chains)}, n_penalized={n_penalized}, "
              f"n_conf={n_conf}, n_trust={n_trust}, n_low={n_low}, mean_q={mean_q:.4f}")
        # Top-10 chains
        print("  Top-10 chains by q11:")
        for c in chains[:10]:
            tag = " (PENALIZED)" if c["penalized"] else ""
            print(f"    chain {c['chain_id']:>2}: q10={c['q10']:.3f}, "
                  f"q11={c['q11']:.3f}, n_tids={c['n_tracklets']}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}{tag}")
        # Bottom-5
        print("  Bottom-5 chains by q11:")
        for c in chains[-5:]:
            tag = " (PENALIZED)" if c["penalized"] else ""
            print(f"    chain {c['chain_id']:>2}: q10={c['q10']:.3f}, "
                  f"q11={c['q11']:.3f}, n_tids={c['n_tracklets']}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}{tag}")
        # Multi-tid CONFIDENT
        multi_conf = [c for c in chains
                      if c["n_tracklets"] >= 2 and c["q11"] >= QUALITY_CONFIDENT]
        multi_all = [c for c in chains if c["n_tracklets"] >= 2]
        print(f"  Multi-tid CONFIDENT: {len(multi_conf)}/{len(multi_all)}")
        for c in multi_conf:
            tag = " (PENALIZED)" if c["penalized"] else ""
            print(f"    chain {c['chain_id']:>2}: q11={c['q11']:.3f}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}{tag}")

        # Write per-chain CSV
        out_csv = H1_DATA / f"h10v11v2_w{W54}_minarcs{MIN_ARCS_FOR_PENALTY}_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "q10", "g_cv", "n_arcs_clean",
                        "penalized", "q11"])
            for c in chains:
                w.writerow([c["chain_id"], c["n_tracklets"], c["q10"],
                            c["g_cv"] if c["g_cv"] is not None else "",
                            c["n_arcs_clean"], c["penalized"], c["q11"]])

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_penalized": n_penalized,
            "n_conf": n_conf, "n_trust": n_trust, "n_low": n_low,
            "mean_q": round(mean_q, 4),
            "multi_n_conf": len(multi_conf),
            "multi_n_total": len(multi_all),
        }

    out_path = H1_DATA / "h10v11v2_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
