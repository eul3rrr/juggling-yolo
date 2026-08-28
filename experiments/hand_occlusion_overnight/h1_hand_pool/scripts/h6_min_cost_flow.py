#!/usr/bin/env python3
"""H6 — Min-cost flow for the H2 AIR+HAND graph combination.

Master §17 lists min-cost flow as a candidate approach for combining
AIR and HAND edges. H2 uses a simple union-find which records but
does not resolve conflicts. A min-cost flow formulation could find
an optimal assignment that resolves conflicts.

Hypothesis: formulating the H2 chain-combination as a min-cost flow
problem will resolve the 1 H2 conflict (tracklet 3 → {hand=9, air=8})
in a principled way.

Approach (declared before reading outcomes):
- Nodes: tracklet IDs.
- Edges: candidate links (from H2's edge list), each with a cost.
- Capacity: each tracklet can have at most one predecessor and one
  successor.
- Find a min-cost flow that respects these capacities.

For the simplest case, the optimal flow will either include
(3 → 9, hand) OR (3 → 8, air), but not both. The lower-cost
edge wins.

Cost definitions (declared first):
- HAND_EDGE_COST = 1.0 (we trust hand edges most)
- AIR_EDGE_COST = 2.0 (air edges are less reliable)
- IDENTITY_AMBIGUOUS_HAND_COST = 1.5 (hand edge with ambiguous identity)

Note: this is a simplified model. A full min-cost flow would
incorporate the from/to frames, gap times, and ballistics.
This experiment tests whether the basic formulation already
resolves the conflict.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Thresholds (declared first)
H6 = {
    "HAND_EDGE_COST": 1.0,
    "AIR_EDGE_COST": 2.0,
    "IDENTITY_AMBIGUOUS_HAND_COST": 1.5,
}


def load_h2_edges(stem: str) -> list[dict]:
    path = H1_DATA / f"h2_edges_{stem}.csv"
    with path.open() as fh:
        return list(csv.DictReader(fh))


def load_h2_conflicts(stem: str) -> list[dict]:
    path = H1_DATA / f"h2_conflicts_{stem}.csv"
    with path.open() as fh:
        return list(csv.DictReader(fh))


def edge_cost(edge: dict) -> float:
    """Compute the cost of an H2 edge."""
    etype = edge["edge_type"]
    if etype == "HAND_TRANSITION":
        return H6["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H6["IDENTITY_AMBIGUOUS_HAND_COST"]
    if etype == "BALLISTIC":
        return H6["AIR_EDGE_COST"]
    return 5.0  # unknown type


def resolve_conflict_with_min_cost(edges_from_src: list[dict]) -> dict | None:
    """Given a set of edges from the SAME source, pick the lowest-cost one.
    If only one edge, return it. If multiple, return the min-cost one.
    This is a per-source greedy choice, which is a simplified min-cost flow.
    """
    if not edges_from_src:
        return None
    return min(edges_from_src, key=lambda e: edge_cost(e))


def main():
    STEMS = ["identical_balls_trick_000_018",
             "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]
    summary = {}
    for stem in STEMS:
        edges = load_h2_edges(stem)
        conflicts = load_h2_conflicts(stem)
        print(f"\n=== {stem} ===")
        print(f"  edges: {len(edges)}, conflicts: {len(conflicts)}")

        # Group edges by source tracklet
        by_src = {}
        for e in edges:
            src = int(e["from_tid"])
            by_src.setdefault(src, []).append(e)
            e["cost"] = edge_cost(e)

        # For each conflict source, pick the lowest-cost successor
        resolutions = {}
        for c in conflicts:
            src = int(c["from_tid"])
            edges_from_src = by_src.get(src, [])
            chosen = resolve_conflict_with_min_cost(edges_from_src)
            if chosen is not None:
                resolutions[src] = (chosen["to_tid"], chosen["edge_type"], chosen["cost"])
                choices_str = ", ".join(
                    f"{e['to_tid']}({e['edge_type']}, cost={e['cost']:.1f})"
                    for e in edges_from_src
                )
                print(f"  conflict: tracklet {src} -> [{choices_str}]")
                print(f"    resolved: -> {chosen['to_tid']} ({chosen['edge_type']}, cost={chosen['cost']:.1f})")

        # Build a min-cost successor map (one successor per tracklet, lowest cost)
        succ = {}
        for src, es in by_src.items():
            best = resolve_conflict_with_min_cost(es)
            if best is not None:
                succ[src] = int(best["to_tid"])

        # Compute chain statistics
        # Tracklet IDs
        all_tids = set()
        for e in edges:
            all_tids.add(int(e["from_tid"]))
            all_tids.add(int(e["to_tid"]))
        # Find roots: tracklets with no incoming edge (from the resolved succ map)
        has_incoming = set(succ.values())
        roots = sorted(t for t in all_tids if t not in has_incoming)
        # Walk chains
        chains = []
        for r in roots:
            chain = [r]
            cur = r
            visited = {cur}
            while cur in succ:
                nxt = succ[cur]
                if nxt in visited:
                    break  # avoid cycles
                chain.append(nxt)
                visited.add(nxt)
                cur = nxt
            chains.append(chain)
        # Add cycle chains (tracklets not reached from roots)
        for t in sorted(all_tids):
            if t not in has_incoming and t not in [c[0] for c in chains]:
                # This is a tracklet with no incoming and no chain yet
                # (Shouldn't happen given roots computation but just in case)
                chains.append([t])

        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H2 min-cost flow: {len(chains)} chains ({n_multi} multi-tracklet, "
              f"longest {len(longest)} tracklets: {longest})")
        summary[stem] = {
            "n_edges": len(edges),
            "n_conflicts": len(conflicts),
            "n_chains": len(chains),
            "n_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "resolutions": {str(k): v for k, v in resolutions.items()},
        }

    out = {"h6_thresholds": H6, "summary": summary}
    with (H1_DATA / "h6_min_cost_summary.json").open("w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\nSaved: {H1_DATA / 'h6_min_cost_summary.json'}")


if __name__ == "__main__":
    main()
