#!/usr/bin/env python3
"""
H57 - H10 v11 v4: extend H56 v1 with conditional penalty for high-CV
chains with few arcs.

H56 v1's n_arcs_clean >= 3 gate is too strict for chains with very
high g_cv (e.g., chain 14 with g_cv=1.089 and only 2 clean arcs).
When a chain has g_cv > 1.0, even 2 arcs are sufficient to detect
the inconsistency.

H57 v1 formulation:
  if n_arcs_clean >= 3:
    apply full H56 v1 non-linear penalty
  elif n_arcs_clean == 2 and g_cv >= HIGH_CV_FLOOR:
    apply partial penalty (e.g., 0.5 * w54 if g_cv > HIGH_CV_FLOOR)
  else:
    no penalty

HIGH_CV_FLOOR = 1.0 (only chains with extreme g_cv get the
reduced-n_arcs penalty)
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# H57 v1 settings
DEADZONE = 0.5
RAMP_END = 1.0
W54 = 0.30
HIGH_CV_FLOOR = 1.0  # trigger partial penalty for low-arc + high-g_cv
PARTIAL_W54 = 0.15   # half of full penalty for low-arc + high-g_cv
MIN_ARCS_PARTIAL = 2  # min arcs for partial penalty (vs 3 for full)

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


def non_linear_penalty(g_cv, w54, deadzone, ramp_end):
    if g_cv is None or g_cv <= deadzone:
        return 0.0
    if g_cv >= ramp_end:
        return w54
    return w54 * (g_cv - deadzone) / (ramp_end - deadzone)


def compute_h57_penalty(g_cv, n_arcs, w54_full, w54_partial, deadzone, ramp_end,
                        high_cv_floor, min_arcs_full, min_arcs_partial):
    """Compute H57 v1 penalty: full if n_arcs >= full_min, partial if
    n_arcs == partial_min AND g_cv >= high_cv_floor, else 0."""
    if g_cv is None:
        return 0.0
    if n_arcs >= min_arcs_full:
        return non_linear_penalty(g_cv, w54_full, deadzone, ramp_end)
    if n_arcs >= min_arcs_partial and g_cv >= high_cv_floor:
        # Linear ramp from 0 at floor to partial_w54 at g_cv=1.5
        # (full penalty for g_cv >= 1.5)
        if g_cv >= 1.5:
            return w54_partial
        return w54_partial * (g_cv - high_cv_floor) / (1.5 - high_cv_floor)
    return 0.0


def main():
    summary = {"videos": {}, "config": {
        "DEADZONE": DEADZONE, "RAMP_END": RAMP_END, "W54": W54,
        "HIGH_CV_FLOOR": HIGH_CV_FLOOR, "PARTIAL_W54": PARTIAL_W54,
        "MIN_ARCS_FULL": 3, "MIN_ARCS_PARTIAL": 2,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H57 v1 conditional penalty) ===")
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
            g_pen = compute_h57_penalty(
                g_cv, n_arcs, W54, PARTIAL_W54, DEADZONE, RAMP_END,
                HIGH_CV_FLOOR, 3, MIN_ARCS_PARTIAL)
            q11 = max(0.0, min(1.0, q10 - g_pen))
            chains.append({
                "chain_id": cid, "q10": q10, "q11": round(q11, 4),
                "g_cv": g_cv, "n_arcs_clean": n_arcs,
                "g_penalty": round(g_pen, 4),
                "n_tracklets": info["n_tracklets"],
            })
        chains.sort(key=lambda c: -c["q11"])
        n_conf = sum(1 for c in chains if c["q11"] >= QUALITY_CONFIDENT)
        n_trust = sum(1 for c in chains if QUALITY_TRUSTABLE <= c["q11"] < QUALITY_CONFIDENT)
        n_low = sum(1 for c in chains if c["q11"] < QUALITY_TRUSTABLE)
        mean_q = statistics.mean(c["q11"] for c in chains)
        n_pen = sum(1 for c in chains if c["g_penalty"] > 0)
        print(f"  n_chains={len(chains)}, n_penalized={n_pen}, "
              f"n_conf={n_conf}, n_trust={n_trust}, n_low={n_low}, mean_q={mean_q:.4f}")
        # Show chains that were penalized
        print("  Penalized chains:")
        for c in chains:
            if c["g_penalty"] > 0:
                print(f"    chain {c['chain_id']:>2}: q10={c['q10']:.3f}, "
                      f"q11={c['q11']:.3f}, g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}, "
                      f"g_pen={c['g_penalty']}")
        # Multi-tid CONFIDENT
        multi_conf = [c for c in chains
                      if c["n_tracklets"] >= 2 and c["q11"] >= QUALITY_CONFIDENT]
        multi_all = [c for c in chains if c["n_tracklets"] >= 2]
        print(f"  Multi-tid CONFIDENT: {len(multi_conf)}/{len(multi_all)}")
        for c in multi_conf:
            print(f"    chain {c['chain_id']:>2}: q11={c['q11']:.3f}, "
                  f"g_cv={c['g_cv']}, n_arcs={c['n_arcs_clean']}")

        out_csv = H1_DATA / f"h10v11v4_conditional_w{W54}_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "q10", "g_cv", "n_arcs_clean",
                        "g_penalty", "q11"])
            for c in chains:
                w.writerow([c["chain_id"], c["n_tracklets"], c["q10"],
                            c["g_cv"] if c["g_cv"] is not None else "",
                            c["n_arcs_clean"], c["g_penalty"], c["q11"]])

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_penalized": n_pen,
            "n_conf": n_conf, "n_trust": n_trust, "n_low": n_low,
            "mean_q": round(mean_q, 4),
            "multi_n_conf": len(multi_conf),
            "multi_n_total": len(multi_all),
        }

    out_path = H1_DATA / "h10v11v4_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
