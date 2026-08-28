#!/usr/bin/env python3
"""H22: H20-KEPT edge veto mode for H7v3pure chain construction.

HYPOTHESIS:
  H21 v1 integrated 3/4 visually-confirmed REAL H20-KEPT edges on
  identical, but the YouTube 20->21 edge was REJECTED by capacity
  conflict with the existing 16->21 edge. Visual analysis suggests
  the existing 16->21 edge is WRONG: tracklet 20 is the canonical
  contact (3 detections at right wrist with min_d ≈ 5 px), while
  tracklet 16 is a spurious earlier-detection (n=126 frames, ending
  2 frames before t20's contact at f=471-473).

  H22 implements a VETO mode: when an H20-KEPT edge is rejected by
  capacity because of an existing edge, check if the H20-KEPT edge
  has STRONGER hand-proximity evidence (lower min_d from V-shape)
  than the existing edge. If so, VETO the existing edge and admit
  the H20-KEPT edge.

  VETO criteria:
  - The H20-KEPT edge has min_d < MIN_D_VETO (default 30 px) — the
    H20-KEPT edge is a tight V-shape, not a marginal one.
  - The existing edge has start_dist (target's first frame distance
    to wrist) > VETO_DIST_THRESHOLD (default 30 px) — the existing
    edge is a marginal BALLISTIC reclassification, not a tight one.
  - If both criteria are met, the H20-KEPT edge wins.

EXPECTED OUTCOME:
  - identical: no change (no capacity conflicts on identical)
  - YouTube: 20->21 admitted, 16->21 vetoed. The h7v3plus YouTube
    chain 0 (1,9,13,16,21,29,34) extends to (1,9,13,16,20,21,29,34).
    H10 v9 chain quality should improve (one more hand-edge, fewer
    BALLISTIC edges per chain).
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

# H22 thresholds (declared from physical geometry, NOT tuned to labels)
H22 = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
    # Veto thresholds: an H20-KEPT edge can veto an existing edge if
    # the H20-KEPT has min_d < MIN_D_VETO AND the existing edge's
    # target has start_dist > VETO_DIST_THRESHOLD
    "MIN_D_VETO": 30.0,             # px (H20-KEPT min_d)
    "VETO_DIST_THRESHOLD": 30.0,    # px (existing target start_dist)
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            def _f(s):
                if s is None or s == "":
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "end_dist": _f(r["end_dist"]),
                "start_dist": _f(r["start_dist"]),
                "end_slope": _f(r["end_slope"]),
                "start_slope": _f(r["start_slope"]),
                "end_side": r["end_side"] or None,
                "start_side": r["start_side"] or None,
            }
    return out


def load_h7v3pure_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def load_h17_strict_positives() -> dict[tuple, dict]:
    """Load H17 strict V-shape positives, keyed by (stem, from_tid, to_tid)."""
    out = {}
    with (H1_DATA / "h17_strict_v_shape_positives.csv").open() as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["from_tid"]), int(r["to_tid"]))
            out[key] = {
                "kind": r["kind"],
                "vshape": r["vshape"],
                "min_hand_dist": float(r["min_hand_dist"]),
                "ratio": float(r["ratio"]),
                "which_hand": r["which_hand"],
                "in_h7v2": r["in_h7v2"] == "True",
            }
    return out


def load_h20_kept_e6c() -> set:
    """Load H20-KEPT e6c_not_in_h7v2 strict positives (the 23 on identical + 3 on youtube)."""
    out = set()
    with (H1_DATA / "h20_strict_v_shape_positives_inhand.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "e6c_not_in_h7v2" and r["h20_keep"] == "True":
                out.add((r["stem"], int(r["from_tid"]), int(r["to_tid"])))
    return out


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    etype = edge["edge_type"]
    if etype in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
                 "V_RECLASSIFIED_HAND_TRANSITION", "H22_RECLASSIFIED_HAND_TRANSITION"):
        return H22["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H22["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        err = edge.get("err", 0.0) or 0.0
        return (H22["AIR_EDGE_BASE_COST"]
                + H22["AIR_ERR_SCALE"] * err
                + H22["AIR_GAP_SCALE"] * gap)
    return 5.0


def h22_min_cost_flow_with_veto(edges: list[dict], tracklets: dict[int, dict],
                                veto_decisions: list[dict] = []
                                ) -> tuple[dict[int, int], list[dict], dict, list[dict]]:
    """Min-cost flow with H22 VETO.

    Veto logic:
    1. Run a first pass of min-cost flow (no veto).
    2. For each veto candidate (H20-KEPT edge that was rejected):
       - If the blocking existing edge has higher cost (or weaker
         start_dist) than the H20-KEPT edge, VETO the existing edge
         and re-run.
    3. For simplicity, we pre-compute veto decisions based on the
       input data and then apply them in the flow.
    """
    # First pass: greedy min-cost flow
    edges_with_cost = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        cost = edge_cost(e, tracklets[src]["last_frame"],
                         tracklets[tgt]["first_frame"])
        edges_with_cost.append({**e, "cost": cost})

    edges_with_cost.sort(key=lambda e: e["cost"])

    succ: dict[int, int] = {}
    pred: dict[int, int] = {}
    admitted = []
    vetoed = []  # list of (h20_kept_edge, blocking_edge)

    def would_cycle(src: int, tgt: int) -> bool:
        cur = src
        seen = set()
        while cur in succ and cur not in seen:
            seen.add(cur)
            cur = succ[cur]
            if cur == tgt:
                return True
        return False

    # Build a set of (vetoing_edge, blocking_edge) pairs
    # where the vetoing edge is an H22-KEPT (H20-KEPT visually-confirmed)
    # and the blocking edge is the existing edge that occupies the same
    # successor slot.
    veto_map: dict[int, dict] = {}  # to_tid -> {h22_edge, blocking_edge}
    if veto_decisions:
        for v in veto_decisions:
            veto_map[v["blocking_to_tid"]] = v

    # First pass: build a record of which existing edges would be vetoed
    # (we need to identify them to skip when admitted in cost order)
    vetoed_blocking_keys: set = set()
    if veto_decisions:
        for v in veto_decisions:
            vetoed_blocking_keys.add((v["blocking_from_tid"], v["blocking_to_tid"]))

    # First pass: greedy min-cost flow, but skip edges that will be vetoed
    for e in edges_with_cost:
        src, tgt = e["from_tid"], e["to_tid"]
        # Skip the existing edge that is being vetoed
        if (src, tgt) in vetoed_blocking_keys:
            # Track this as a vetoed edge
            v = veto_map.get(tgt)
            if v is not None and v["blocking_from_tid"] == src:
                vetoed.append(v)
            continue
        if src in succ:
            continue
        if tgt in pred:
            continue
        if would_cycle(src, tgt):
            continue
        succ[src] = tgt
        pred[tgt] = src
        admitted.append(e)

    # Now admit the H22-KEPT edges that veto'd existing ones
    if veto_decisions:
        for v in veto_decisions:
            h22_edge = v["h22_edge"]
            ft, tt = h22_edge["from_tid"], h22_edge["to_tid"]
            if ft in succ:
                continue
            if tt in pred:
                continue
            if would_cycle(ft, tt):
                continue
            succ[ft] = tt
            pred[tt] = ft
            admitted.append(h22_edge)

    stats = {
        "n_edges_in": len(edges),
        "n_admitted": len(admitted),
        "n_rejected_capacity": len(edges) - len(admitted),
        "n_vetoed_existing": len(vetoed),
        "mean_cost_admitted": (sum(e["cost"] for e in admitted) / len(admitted)
                               if admitted else 0.0),
    }
    return succ, admitted, stats, vetoed


def walk_chains(succ: dict[int, int], all_tids: list[int]) -> list[list[int]]:
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
    return chains


def compute_veto_decisions(stem: str, h7v3pure_edges: list[dict],
                            tracklets: dict, h17_pos: dict,
                            h20_kept: set) -> list[dict]:
    """For each H20-KEPT edge in this stem, check if it would be vetoed
    by an existing edge. Return a list of veto decisions to apply.

    A veto decision is created if:
    - The H20-KEPT edge is not already in the h7v3pure admitted edges
    - The H20-KEPT edge has min_d < MIN_D_VETO (strong V-shape)
    - The H20-KEPT edge's target is also a target of an existing edge
      (i.e., they compete for the same successor slot)
    - The existing edge's TARGET has start_dist > VETO_DIST_THRESHOLD
      (i.e., the existing edge is a marginal BALLISTIC reclassification)
    - The H20-KEPT edge's SOURCE does NOT already have a successor in
      the chain set (i.e., we can admit the H22-KEPT edge without
      breaking a chain topology)
    """
    decisions = []
    existing_targets = {e["to_tid"]: e for e in h7v3pure_edges}
    existing_sources = {e["from_tid"]: e for e in h7v3pure_edges}
    for (s, ft, tt) in h20_kept:
        if s != stem:
            continue
        if ft not in tracklets or tt not in tracklets:
            continue
        h17 = h17_pos.get((s, ft, tt))
        if h17 is None:
            continue
        if h17["min_hand_dist"] >= H22["MIN_D_VETO"]:
            continue
        # Check if this edge is already in h7v3pure (then no veto needed)
        if any(e["from_tid"] == ft and e["to_tid"] == tt for e in h7v3pure_edges):
            continue
        # Check if the H20-KEPT edge's source already has a successor
        # (if so, vetoing would break the chain topology)
        if ft in existing_sources and existing_sources[ft]["to_tid"] != tt:
            continue
        # Check if there's a competing existing edge for the same target
        blocking = existing_targets.get(tt)
        if blocking is None:
            continue
        # Get the existing edge's target's start_dist
        tgt_tt = tracklets[tt]
        if tgt_tt["start_dist"] is None or tgt_tt["start_dist"] <= H22["VETO_DIST_THRESHOLD"]:
            continue
        # Both conditions met: H20-KEPT has strong V-shape, existing has weak target
        h22_edge = {
            "from_tid": ft,
            "to_tid": tt,
            "edge_type": "H22_RECLASSIFIED_HAND_TRANSITION",
            "metadata": f"h22_vshape={h17['vshape']}_min_d={h17['min_hand_dist']:.1f}",
            "reclassify_reason": "",
            "v_reclassify_reason": "",
            "h22_reason": (f"veto: H20-KEPT min_d={h17['min_hand_dist']:.1f} "
                           f"overrides existing {blocking['from_tid']}->{tt} "
                           f"(target start_dist={tgt_tt['start_dist']:.1f})"),
            "which_hand": h17["which_hand"],
            "cost": H22["HAND_EDGE_COST"],
        }
        decisions.append({
            "h22_edge": h22_edge,
            "blocking_from_tid": blocking["from_tid"],
            "blocking_to_tid": tt,
            "blocking_edge_type": blocking["edge_type"],
            "blocking_metadata": blocking.get("metadata", ""),
            "blocking_target_start_dist": tgt_tt["start_dist"],
            "h20_min_d": h17["min_hand_dist"],
        })
    return decisions


def main():
    print("H22: H20-KEPT edge veto mode for H7v3pure chain construction")
    print(f"  thresholds: {H22}")
    print()

    h17_pos = load_h17_strict_positives()
    h20_kept = load_h20_kept_e6c()
    print(f"  H17 strict positives: {len(h17_pos)}")
    print(f"  H20-KEPT e6c_not_in_h7v2: {len(h20_kept)}")

    summary = {"h22_thresholds": H22, "videos": {}}

    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        h7v3pure_edges = load_h7v3pure_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  h7v3pure edges: {len(h7v3pure_edges)}")

        # Compute veto decisions
        veto_decisions = compute_veto_decisions(
            stem, h7v3pure_edges, tracklets, h17_pos, h20_kept)
        print(f"  H22 VETO decisions: {len(veto_decisions)}")
        for v in veto_decisions:
            h22 = v["h22_edge"]
            bl = v["blocking_from_tid"]
            tt = v["blocking_to_tid"]
            et = v["blocking_edge_type"]
            sd = v["blocking_target_start_dist"]
            md = v["h20_min_d"]
            print(f"    {h22['from_tid']:>3d}->{h22['to_tid']:<3d} vetoes {bl:>3d}->{tt:<3d} "
                  f"({et}); H20 min_d={md:.1f} < existing start_dist={sd:.1f}")

        # Run min-cost flow with veto
        succ, admitted, stats, vetoed = h22_min_cost_flow_with_veto(
            h7v3pure_edges, tracklets, veto_decisions)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H22 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Edge type breakdown
        type_counts = defaultdict(int)
        for e in admitted:
            type_counts[e["edge_type"]] += 1
        print(f"  admitted edge types: {dict(type_counts)}")

        h22_admitted = [e for e in admitted
                        if e["edge_type"] == "H22_RECLASSIFIED_HAND_TRANSITION"]
        print(f"  H22_RECLASSIFIED in admitted: {len(h22_admitted)}")
        for e in h22_admitted:
            print(f"    {e['from_tid']:>3d} -> {e['to_tid']:<3d}  cost={e['cost']:.2f}  "
                  f"({e.get('h22_reason', '')})")

        # Compare to h7v3pure
        try:
            h7v3_chains = list(csv.DictReader(open(H1_DATA / f"h7v3pure_chains_{stem}.csv")))
            print(f"  h7v3pure chain count: {len(h7v3_chains)}")
            print(f"  h22 chain count: {len(chains)}  (delta {len(chains) - len(h7v3_chains):+d})")
        except FileNotFoundError:
            pass

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_h7v3pure_edges": len(h7v3pure_edges),
            "n_veto_decisions": len(veto_decisions),
            "n_vetoed_existing": stats["n_vetoed_existing"],
            "n_h22_admitted": len(h22_admitted),
            "n_admitted": stats["n_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
            "veto_decisions": veto_decisions,
            "edge_type_counts": dict(type_counts),
        }

    out_path = H1_DATA / "h22_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h7v3veto_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost",
                "reclassify_reason", "v_reclassify_reason", "h22_reason"])
            w.writeheader()
            for e in v["admitted_edges"]:
                w.writerow({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "edge_type": e["edge_type"],
                    "metadata": e.get("metadata", ""),
                    "cost": f"{e['cost']:.3f}",
                    "reclassify_reason": e.get("reclassify_reason", ""),
                    "v_reclassify_reason": e.get("v_reclassify_reason", ""),
                    "h22_reason": e.get("h22_reason", ""),
                })
        with (H1_DATA / f"h7v3veto_chains_{stem}.csv").open("w", newline="") as fh:
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
        # H22 VETO decisions log
        with (H1_DATA / f"h7v3veto_veto_decisions_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "h22_from_tid", "h22_to_tid", "blocking_from_tid", "blocking_to_tid",
                "blocking_edge_type", "blocking_target_start_dist", "h20_min_d",
                "h22_reason"])
            w.writeheader()
            for v_d in v["veto_decisions"]:
                w.writerow({
                    "h22_from_tid": v_d["h22_edge"]["from_tid"],
                    "h22_to_tid": v_d["h22_edge"]["to_tid"],
                    "blocking_from_tid": v_d["blocking_from_tid"],
                    "blocking_to_tid": v_d["blocking_to_tid"],
                    "blocking_edge_type": v_d["blocking_edge_type"],
                    "blocking_target_start_dist": v_d["blocking_target_start_dist"],
                    "h20_min_d": v_d["h20_min_d"],
                    "h22_reason": v_d["h22_edge"].get("h22_reason", ""),
                })

    print("\n=== Per-video CSVs saved ===")


if __name__ == "__main__":
    main()
