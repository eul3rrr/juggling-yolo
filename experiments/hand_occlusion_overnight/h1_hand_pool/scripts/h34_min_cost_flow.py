#!/usr/bin/env python3
"""H34 — H22 + H26 combined chain set with full min-cost flow.

Combines h7v3plus2 (H26 = H7v3pure + 2 H24 NEW REAL H20-KEPT
edges) with H22's YouTube veto (replace 16->21 with 20->21).

Re-runs min-cost flow on the combined edge set and produces the
h7v3plus3 chains + H10 v10 quality scores.
"""
from __future__ import annotations

import csv
import json
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

H34_THRESHOLDS = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
}

# H22 veto: YouTube only — replace 16->21 with 20->21
H22_VETO = {
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        "remove": (16, 21),
        "add": {
            "from_tid": 20, "to_tid": 21,
            "edge_type": "H22_RECLASSIFIED_HAND_TRANSITION",
            "metadata": "h22_vshape=V_DEEP_min_d=5.3",
            "cost": 1.0, "reclassify_reason": "", "v_reclassify_reason": "",
            "h22_reason": "veto: H20-KEPT min_d=5.3 overrides existing 16->21 (target start_dist=35.3)",
        },
    },
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["tid"] = int(r["tid"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["n_pts"] = int(r["n_pts"])
            r["first_x"] = float(r["first_x"])
            r["first_y"] = float(r["first_y"])
            r["last_x"] = float(r["last_x"])
            r["last_y"] = float(r["last_y"])
            out[r["tid"]] = r
    return out


def load_h7v3plus2_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            try:
                r["cost"] = float(r["cost"])
            except (ValueError, KeyError):
                r["cost"] = None
            out.append(r)
    return out


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    """Compute edge cost with the same formula as H7."""
    t = H34_THRESHOLDS
    et = edge["edge_type"]
    if et == "HAND_TRANSITION":
        return t["HAND_EDGE_COST"]
    if et == "AMBIGUOUS_HAND_TRANSITION":
        return t["AMBIGUOUS_HAND_EDGE_COST"]
    if et == "BALLISTIC":
        base = t["AIR_EDGE_BASE_COST"]
        # Extract err from metadata
        meta = edge.get("metadata", "")
        err = 0.0
        try:
            err = float(meta.split("err=")[1].split(",")[0])
        except (IndexError, ValueError):
            err = 0.0
        gap = max(0, target_first_frame - source_last_frame - 1)
        return base + t["AIR_ERR_SCALE"] * err + t["AIR_GAP_SCALE"] * gap
    # All other hand-edge types
    return t["HAND_EDGE_COST"]


def min_cost_flow(edges: list[dict], tracklets: dict[int, dict]) -> list[list[int]]:
    """Greedy iterative min-cost flow with capacity constraints.

    Returns list of chains (each chain is a list of tids).
    """
    # Build all tids
    all_tids = sorted(tracklets.keys())

    # Compute edge costs
    costed_edges = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        src_meta = tracklets.get(src, {})
        tgt_meta = tracklets.get(tgt, {})
        src_last = src_meta.get("last_frame", 0)
        tgt_first = tgt_meta.get("first_frame", 0)
        c = edge_cost(e, src_last, tgt_first)
        costed_edges.append((c, src, tgt, e))

    # Sort by cost ascending
    costed_edges.sort(key=lambda x: x[0])

    # Greedy assignment with capacity constraints
    pred: dict[int, int] = {}  # tid -> predecessor tid
    succ: dict[int, int] = {}  # tid -> successor tid

    def would_cycle(src: int, tgt: int) -> bool:
        # Check if adding src->tgt creates a cycle
        cur = src
        seen = set()
        while cur in pred:
            if cur in seen:
                return True
            seen.add(cur)
            cur = pred[cur]
            if cur == tgt:
                return True
        return False

    for c, src, tgt, e in costed_edges:
        if tgt in pred or src in succ:
            continue  # capacity constraint violated
        if would_cycle(src, tgt):
            continue
        pred[tgt] = src
        succ[src] = tgt

    # Walk chains
    chains = []
    visited = set()
    # Find chain starts (no predecessor)
    starts = [t for t in all_tids if t not in pred]
    for start in starts:
        if start in visited:
            continue
        chain = [start]
        visited.add(start)
        cur = start
        while cur in succ:
            cur = succ[cur]
            chain.append(cur)
            visited.add(cur)
        chains.append(chain)

    return chains


def main() -> None:
    summary = {"videos": {}, "thresholds": H34_THRESHOLDS}
    for stem in STEMS:
        tracklets = load_tracklet_features(stem)
        edges = load_h7v3plus2_edges(stem)

        # Apply H22 veto if applicable: skip the blocking 16->21 edge
        # and add the H22 20->21 edge.
        if stem in H22_VETO:
            spec = H22_VETO[stem]
            rm_from, rm_to = spec["remove"]
            # Note: edge list is filtered to EXCLUDE the blocking edge
            # (H22 vetoes it). The H22 20->21 edge is added separately.
            edges = [e for e in edges
                     if not (e["from_tid"] == rm_from and e["to_tid"] == rm_to)]
            edges.append(spec["add"])

        # Min-cost flow
        chains = min_cost_flow(edges, tracklets)

        # Save chains
        out_csv = H1_DATA / f"h7v3plus3_chains_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "first_frame", "last_frame", "tids"])
            for cid, ch in enumerate(chains):
                # Compute first/last frame from tracklets
                ch_metas = [tracklets.get(t, {}) for t in ch]
                first_frame = min((m.get("first_frame", 0) for m in ch_metas), default=0)
                last_frame = max((m.get("last_frame", 0) for m in ch_metas), default=0)
                w.writerow([cid, len(ch), first_frame, last_frame, ",".join(str(t) for t in ch)])

        # Stats
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max((len(c) for c in chains), default=0)
        longest_chain = max(chains, key=len) if chains else []

        # Edge type counts
        from collections import Counter
        et_counts = Counter(e["edge_type"] for e in edges)

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_multi_tracklet": n_multi,
            "longest": longest,
            "longest_chain": longest_chain,
            "edge_type_counts": dict(et_counts),
        }
        print(f"  {stem}: n_chains={len(chains)} n_multi={n_multi} "
              f"longest={longest} ({longest_chain[:5]}{'...' if longest > 5 else ''})")

    out_json = H1_DATA / "h34_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
