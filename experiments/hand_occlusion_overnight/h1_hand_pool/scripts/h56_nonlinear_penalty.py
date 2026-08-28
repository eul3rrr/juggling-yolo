#!/usr/bin/env python3
"""
H56 v1 - Non-linear g_cv penalty for H10 v11.

H55 v2 (linear penalty) over-penalizes chain 30 (visually confirmed
single-ball, g_cv=0.417) because the linear formula is too aggressive
on chains with mid-range q10 (0.4-0.6).

H56 v1 hypothesis: a non-linear penalty that only kicks in for
g_cv > 0.5 (linear ramp from 0 to 1.0) preserves low-CV chains.

Formulation:
  if g_cv < 0.5: penalty = 0
  elif g_cv < 1.0: penalty = w54 * (g_cv - 0.5) / 0.5  (linear ramp)
  else: penalty = w54  (max penalty)

Or simpler: g_penalty = max(0, g_cv - 0.5) * w54 * 2

q_v11 = max(0, min(1, q_v10 - g_penalty))
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# v3 settings
MIN_ARCS_FOR_PENALTY = 3
W54 = 0.30
G_CV_DEADZONE = 0.5  # no penalty below this
G_CV_RAMP_END = 1.0  # full penalty at this g_cv
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


def non_linear_penalty(g_cv, w54, deadzone=0.5, ramp_end=1.0):
    """Non-linear penalty with deadzone and ramp."""
    if g_cv is None or g_cv <= deadzone:
        return 0.0
    if g_cv >= ramp_end:
        return w54
    # Linear ramp from 0 at deadzone to w54 at ramp_end
    return w54 * (g_cv - deadzone) / (ramp_end - deadzone)


def main():
    summary = {"videos": {}, "config": {
        "MIN_ARCS_FOR_PENALTY": MIN_ARCS_FOR_PENALTY, "W54": W54,
        "G_CV_DEADZONE": G_CV_DEADZONE, "G_CV_RAMP_END": G_CV_RAMP_END,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H56 v1 non-linear penalty, "
              f"deadzone={G_CV_DEADZONE}, ramp_end={G_CV_RAMP_END}, w54={W54}) ===")
        h10 = load_h10v10(stem)
        h54 = load_h54_gcv(stem)
        chains = []
        for cid, info in h10.items():
            q10 = info["q"]
            if q10 is None:
                continue
            h54_info = h54.get(cid, {"g_cv": None, "n_arcs_clean": 0})
            n_arcs = h54_info["n_arcs_clean"]
            g_cv = h54_info["g_cv"]
            if n_arcs >= MIN_ARCS_FOR_PENALTY and g_cv is not None:
                g_pen = non_linear_penalty(g_cv, W54, G_CV_DEADZONE, G_CV_RAMP_END)
                penalized = g_pen > 0
            else:
                g_pen = 0.0
                penalized = False
            q11 = max(0.0, min(1.0, q10 - g_pen))
            chains.append({
                "chain_id": cid, "q10": q10, "q11": round(q11, 4),
                "g_cv": g_cv, "n_arcs_clean": n_arcs, "penalized": penalized,
                "g_penalty": round(g_pen, 4),
                "n_tracklets": info["n_tracklets"],
            })
        chains.sort(key=lambda c: -c["q11"])
        n_conf = sum(1 for c in chains if c["q11"] >= QUALITY_CONFIDENT)
        n_trust = sum(1 for c in chains if QUALITY_TRUSTABLE <= c["q11"] < QUALITY_CONFIDENT)
        n_low = sum(1 for c in chains if c["q11"] < QUALITY_TRUSTABLE)
        mean_q = statistics.mean(c["q11"] for c in chains)
        n_pen = sum(1 for c in chains if c["penalized"])
        print(f"  n_chains={len(chains)}, n_penalized={n_pen}, "
              f"n_conf={n_conf}, n_trust={n_trust}, n_low={n_low}, mean_q={mean_q:.4f}")
        # Top 10
        print("  Top-10 chains by q11:")
        for c in chains[:10]:
            tag = f" (g_pen={c['g_penalty']})" if c["penalized"] else ""
            print(f"    chain {c['chain_id']:>2}: q10={c['q10']:.3f}, "
                  f"q11={c['q11']:.3f}, n_tids={c['n_tracklets']}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}{tag}")
        # Bottom 5
        print("  Bottom-5 chains by q11:")
        for c in chains[-5:]:
            tag = f" (g_pen={c['g_penalty']})" if c["penalized"] else ""
            print(f"    chain {c['chain_id']:>2}: q10={c['q10']:.3f}, "
                  f"q11={c['q11']:.3f}, n_tids={c['n_tracklets']}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}{tag}")
        # Multi-tid CONFIDENT
        multi_conf = [c for c in chains
                      if c["n_tracklets"] >= 2 and c["q11"] >= QUALITY_CONFIDENT]
        multi_all = [c for c in chains if c["n_tracklets"] >= 2]
        print(f"  Multi-tid CONFIDENT: {len(multi_conf)}/{len(multi_all)}")
        for c in multi_conf:
            print(f"    chain {c['chain_id']:>2}: q11={c['q11']:.3f}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}")

        # Write per-chain CSV
        out_csv = H1_DATA / f"h10v11v3_nonlinear_w{W54}_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "q10", "g_cv", "n_arcs_clean",
                        "g_penalty", "q11", "label"])
            for c in chains:
                if c["q11"] >= QUALITY_CONFIDENT:
                    label = "CONFIDENT"
                elif c["q11"] >= QUALITY_TRUSTABLE:
                    label = "UNCERTAIN"
                else:
                    label = "LOW"
                w.writerow([c["chain_id"], c["n_tracklets"], c["q10"],
                            c["g_cv"] if c["g_cv"] is not None else "",
                            c["n_arcs_clean"], c["g_penalty"], c["q11"], label])

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_penalized": n_pen,
            "n_conf": n_conf, "n_trust": n_trust, "n_low": n_low,
            "mean_q": round(mean_q, 4),
            "multi_n_conf": len(multi_conf),
            "multi_n_total": len(multi_all),
        }

    out_path = H1_DATA / "h10v11v3_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
