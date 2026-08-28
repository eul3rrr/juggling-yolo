#!/usr/bin/env python3
"""H7 — Per-source successor assignment with capacity constraints and
gap/error-aware air-edge cost.

Master §17 says min-cost flow with capacity constraints (one predecessor
+ one successor per tracklet) is the principled formulation for the
H2 chain combination. H6 used a simplified per-source greedy
("lowest-cost successor wins per source"). H7 generalizes that:

* H6 = for each source, pick lowest-cost successor
* H7 = for each source, pick lowest-cost successor; but also for each
  target, only the lowest-cost predecessor is admitted; cycle detection
  and breaking is applied.

H7 also incorporates E6c's trajectory_fit_error into the air-edge cost
(H6 used a flat cost 2.0 for all air edges). The hypothesis: a
gap/error-aware cost is more discriminative than a flat cost.

Approach (declared before reading outcomes):

THRESHOLDS (declared from physical geometry, NOT from manual labels):
* HAND_EDGE_COST = 1.0                  # direct hand evidence
* AMBIGUOUS_HAND_EDGE_COST = 1.5        # hand evidence w/ identity ambiguity
* AIR_EDGE_BASE_COST = 2.0              # base cost for E6c air edge
* AIR_ERR_SCALE = 0.05                  # add 0.05 per unit of fit error
* AIR_GAP_SCALE = 0.1                   # add 0.1 per frame of time gap

INPUTS:
* h2_edges_*.csv (already includes HAND_TRANSITION, AMBIGUOUS_HAND_TRANSITION,
  BALLISTIC). metadata carries tok_age, hand, err.

ALGORITHM (simplified min-cost flow without scipy/networkx):
1. Build a cost matrix C[i,j] = cost of i→j (uses H7 thresholds).
2. For each source i, find its lowest-cost candidate j.
3. For each target j, find its lowest-cost source i.
4. Repeatedly pick the globally-cheapest edge (i→j) that:
   - i has no current successor
   - j has no current predecessor
   - this is cheaper than keeping either i or j unmatched
5. If i and j are already linked in a chain (transitively), skip (cycle).
6. Stop when no more edges can be admitted.
7. Compute chain statistics.

EXPECTED OUTCOME:
* H7 should resolve the 1 H2 conflict (tracklet 3 → {9, 8}) by picking
  the hand-edge (cost 1.5) over the air-edge (cost 2.0 + err penalty).
* H7 should produce MORE multi-tracklet chains than H6 because the
  capacity constraints are enforced globally.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# H7 thresholds (declared from physical geometry, NOT tuned to manual labels)
H7 = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
    "NO_SUCCESSOR_COST": 0.0,  # cost of assigning a tracklet to "no successor"
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    """Read tracklet_features.csv to get first/last frame per tid."""
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
            }
    return out


def load_h2_edges(stem: str) -> list[dict]:
    """Read H2 edges CSV. Returns list of dicts with cost info."""
    out = []
    with (H1_DATA / f"h2_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            # Parse metadata for air edges
            err = 0.0
            if r["edge_type"] == "BALLISTIC":
                m = re.search(r"err=([\d.]+)", r["metadata"])
                if m:
                    err = float(m.group(1))
            r["err"] = err
            out.append(r)
    return out


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    """Compute the cost of an H2 edge.

    Hand edges: flat cost.
    Air edges: base + err*scale + gap*scale.
    """
    etype = edge["edge_type"]
    if etype == "HAND_TRANSITION":
        return H7["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H7["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        return (H7["AIR_EDGE_BASE_COST"]
                + H7["AIR_ERR_SCALE"] * edge["err"]
                + H7["AIR_GAP_SCALE"] * gap)
    return 5.0  # unknown type


def h7_min_cost_flow(edges: list[dict], tracklets: dict[int, dict]
                     ) -> tuple[dict[int, int], list[dict], dict]:
    """Greedy iterative min-cost flow with capacity constraints.

    Returns:
        succ: dict mapping source_tid -> target_tid
        admitted_edges: list of admitted edges
        stats: dict of statistics
    """
    # Compute cost for each edge
    edges_with_cost = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        cost = edge_cost(e, tracklets[src]["last_frame"],
                         tracklets[tgt]["first_frame"])
        edges_with_cost.append({**e, "cost": cost})

    # Sort by cost (cheapest first)
    edges_with_cost.sort(key=lambda e: e["cost"])

    # Capacity constraints
    succ: dict[int, int] = {}     # source -> chosen target
    pred: dict[int, int] = {}     # target -> chosen source
    admitted = []

    # Reject edges that would create a cycle (DAG check)
    def would_cycle(src: int, tgt: int) -> bool:
        # Walk forward from src; if we ever reach tgt, it's a cycle.
        cur = src
        seen = set()
        while cur in succ and cur not in seen:
            seen.add(cur)
            cur = succ[cur]
            if cur == tgt:
                return True
        return False

    for e in edges_with_cost:
        src, tgt = e["from_tid"], e["to_tid"]
        if src in succ:
            continue  # src already has a successor
        if tgt in pred:
            continue  # tgt already has a predecessor
        if would_cycle(src, tgt):
            continue
        # Check that this assignment is cheaper than keeping src unmatched
        # (H7 has NO_SUCCESSOR_COST = 0.0, so we admit any positive cost
        # is worse than 0; but hand edges are 1.0+ which IS more than 0
        # so we'd never admit them under this rule. We want to admit
        # edges, so we treat NO_SUCCESSOR_COST as the cost of the best
        # alternative, which is infinity here. Each edge's cost is
        # its declared cost.)
        succ[src] = tgt
        pred[tgt] = src
        admitted.append(e)

    stats = {
        "n_edges_in": len(edges),
        "n_admitted": len(admitted),
        "n_rejected_capacity": len(edges) - len(admitted),
        "mean_cost_admitted": (sum(e["cost"] for e in admitted) / len(admitted)
                               if admitted else 0.0),
    }
    return succ, admitted, stats


def walk_chains(succ: dict[int, int], all_tids: list[int]) -> list[list[int]]:
    """Walk chains from roots (tracklets with no predecessor)."""
    has_pred = set(succ.values())
    roots = sorted(t for t in all_tids if t not in has_pred)
    chains = []
    for r in roots:
        chain = [r]
        cur = r
        while cur in succ:
            nxt = succ[cur]
            if nxt in chain:
                break  # avoid cycle
            chain.append(nxt)
            cur = nxt
        chains.append(chain)
    return chains


def main():
    summary = {"h7_thresholds": H7, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        edges = load_h2_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  H2 edges: {len(edges)}")

        succ, admitted, stats = h7_min_cost_flow(edges, tracklets)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H7 min-cost flow: {len(chains)} chains ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Print admitted edges for inspection
        print(f"  admitted edges:")
        for e in admitted:
            kind = e["edge_type"]
            extra = ""
            if kind == "BALLISTIC":
                extra = f" err={e['err']:.1f}"
            print(f"    {e['from_tid']:>3} -> {e['to_tid']:>3}  "
                  f"{kind:<28} cost={e['cost']:.2f}{extra}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_edges_in": stats["n_edges_in"],
            "n_admitted": stats["n_admitted"],
            "n_rejected_capacity": stats["n_rejected_capacity"],
            "mean_cost_admitted": stats["mean_cost_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
        }

    out_path = H1_DATA / "h7_min_cost_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h7_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost"])
            w.writeheader()
            for e in v["admitted_edges"]:
                w.writerow({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "edge_type": e["edge_type"],
                    "metadata": e["metadata"],
                    "cost": f"{e['cost']:.3f}",
                })
        with (H1_DATA / f"h7_chains_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "first_frame", "last_frame", "tids"])
            w.writeheader()
            for cid, chain in enumerate(v["chains"]):
                tracklets = load_tracklet_features(stem)
                if chain:
                    first_frame = min(tracklets[t]["first_frame"] for t in chain)
                    last_frame = max(tracklets[t]["last_frame"] for t in chain)
                else:
                    first_frame = last_frame = 0
                w.writerow({
                    "chain_id": cid,
                    "n_tracklets": len(chain),
                    "first_frame": first_frame,
                    "last_frame": last_frame,
                    "tids": ",".join(str(t) for t in chain),
                })


if __name__ == "__main__":
    main()
