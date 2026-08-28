#!/usr/bin/env python3
"""H7 sensitivity grid: vary AIR_ERR_SCALE, AIR_GAP_SCALE, AIR_EDGE_BASE_COST.

Question: is H7's cost function robust to small parameter perturbations?
The hypothesis is that the relative ordering of hand edges (cost 1.0/1.5)
and air edges (cost >= 2.0) is what matters; the exact penalty for
error/gap is less important as long as hand edges stay cheaper than
all air edges.

Sweep:
* AIR_ERR_SCALE in {0.0, 0.05, 0.10, 0.20}
* AIR_GAP_SCALE in {0.0, 0.05, 0.10, 0.20}
* AIR_EDGE_BASE_COST in {1.5, 2.0, 2.5}  # keep hand edges cheaper

For each (err_scale, gap_scale, base_cost), run H7 on both videos.
Count: n_chains, n_multi, longest, n_admitted, conflict resolution.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = ["identical_balls_trick_000_018",
         "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
            }
    return out


def load_h2_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h2_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            err = 0.0
            if r["edge_type"] == "BALLISTIC":
                m = re.search(r"err=([\d.]+)", r["metadata"])
                if m:
                    err = float(m.group(1))
            r["err"] = err
            out.append(r)
    return out


def edge_cost(e, src_last, tgt_first, H7):
    et = e["edge_type"]
    if et == "HAND_TRANSITION":
        return H7["HAND_EDGE_COST"]
    if et == "AMBIGUOUS_HAND_TRANSITION":
        return H7["AMBIGUOUS_HAND_EDGE_COST"]
    if et == "BALLISTIC":
        gap = max(0, tgt_first - src_last)
        return (H7["AIR_EDGE_BASE_COST"]
                + H7["AIR_ERR_SCALE"] * e["err"]
                + H7["AIR_GAP_SCALE"] * gap)
    return 5.0


def h7_run(edges, tracklets, H7):
    ec = []
    for e in edges:
        c = edge_cost(e, tracklets[e["from_tid"]]["last_frame"],
                      tracklets[e["to_tid"]]["first_frame"], H7)
        ec.append({**e, "cost": c})
    ec.sort(key=lambda e: e["cost"])
    succ, pred = {}, {}
    admitted = []
    def would_cycle(s, t):
        cur = s
        seen = set()
        while cur in succ and cur not in seen:
            seen.add(cur)
            cur = succ[cur]
            if cur == t:
                return True
        return False
    for e in ec:
        s, t = e["from_tid"], e["to_tid"]
        if s in succ or t in pred or would_cycle(s, t):
            continue
        succ[s] = t
        pred[t] = s
        admitted.append(e)
    all_tids = set(tracklets.keys())
    has_pred = set(succ.values())
    roots = sorted(t for t in all_tids if t not in has_pred)
    chains = []
    for r in roots:
        chain = [r]
        cur = r
        while cur in succ:
            nxt = succ[cur]
            if nxt in chain:
                break
            chain.append(nxt)
            cur = nxt
        chains.append(chain)
    return {
        "n_admitted": len(admitted),
        "n_chains": len(chains),
        "n_multi": sum(1 for c in chains if len(c) > 1),
        "longest": max((len(c) for c in chains), default=0),
        "succ": succ,
        "admitted": admitted,
    }


def main():
    # Baseline H7
    base = {
        "HAND_EDGE_COST": 1.0,
        "AMBIGUOUS_HAND_EDGE_COST": 1.5,
        "AIR_EDGE_BASE_COST": 2.0,
        "AIR_ERR_SCALE": 0.05,
        "AIR_GAP_SCALE": 0.1,
    }
    err_scales = [0.0, 0.05, 0.10, 0.20]
    gap_scales = [0.0, 0.05, 0.10, 0.20]
    base_costs = [1.5, 2.0, 2.5]

    grid = []
    for bc in base_costs:
        for es in err_scales:
            for gs in gap_scales:
                H7 = {**base, "AIR_EDGE_BASE_COST": bc,
                      "AIR_ERR_SCALE": es, "AIR_GAP_SCALE": gs}
                row = {"AIR_EDGE_BASE_COST": bc, "AIR_ERR_SCALE": es,
                       "AIR_GAP_SCALE": gs}
                for stem in STEMS:
                    tids = load_tracklet_features(stem)
                    edges = load_h2_edges(stem)
                    r = h7_run(edges, tids, H7)
                    # Verify conflict resolution: tracklet 3 -> 9 (not 8)
                    if 3 in r["succ"]:
                        conflict_3 = r["succ"][3]
                    else:
                        conflict_3 = None
                    row[stem] = {
                        "n_admitted": r["n_admitted"],
                        "n_chains": r["n_chains"],
                        "n_multi": r["n_multi"],
                        "longest": r["longest"],
                        "tracklet3_succ": conflict_3,
                    }
                grid.append(row)

    out = {"base": base, "grid": grid}
    out_path = H1_DATA / "h7_sens_grid.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"Saved: {out_path}")

    # Print the grid in compact form
    print(f"\n{'BC':>4} {'ES':>5} {'GS':>5} | "
          f"{'ident_n_admit':>12} {'ident_chains':>12} {'ident_multi':>12} "
          f"{'ident_long':>10} {'3->':>3} | "
          f"{'yt_n_admit':>10} {'yt_chains':>10} {'yt_multi':>10} "
          f"{'yt_long':>8}")
    print("-"*120)
    for row in grid:
        i = row["identical_balls_trick_000_018"]
        y = row["youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]
        print(f"{row['AIR_EDGE_BASE_COST']:>4.1f} {row['AIR_ERR_SCALE']:>5.2f} "
              f"{row['AIR_GAP_SCALE']:>5.2f} | "
              f"{i['n_admitted']:>12} {i['n_chains']:>12} {i['n_multi']:>12} "
              f"{i['longest']:>10} {str(i['tracklet3_succ']):>3} | "
              f"{y['n_admitted']:>10} {y['n_chains']:>10} {y['n_multi']:>10} "
              f"{y['longest']:>8}")


if __name__ == "__main__":
    main()
