#!/usr/bin/env python3
"""H26: integrate H24's 2 NEW REAL H20-KEPT edges as HAND_TRANSITION edges.

HYPOTHESIS:
  H24 found 2 NEW REAL H20-KEPT-not-in-h7v2 candidates:
    - identical 7->10 (V_SHALLOW, R->L hand-off, min_d=57.35)
    - identical 59->61 (V_DEEP, R->L hand-off, min_d=18.94)

  Both are visually-confirmed real catch+throws that h7v2 missed.
  H21 v1 already integrated 5 other H20-KEPT REAL edges (H20's
  8-candidate sample). H26 adds H24's 2 NEW REAL edges on top of
  H21's 5 edges, producing a richer chain set.

  H26 question: do these 2 additional REAL edges improve chain
  quality, or do they introduce BALLISTIC edges that h8 v5
  penalizes (the H21 v2 quality drop pattern)?

APPROACH (declared before reading outcomes):
  - Inherit H21 v1's edge set + H21_RECLASSIFIED + H24_RECLASSIFIED
  - HAND_EDGE_COST = 1.0, AMBIGUOUS = 1.5, BALLISTIC base = 2.0
  - Re-run min-cost flow with the augmented edge set
  - Walk new chains
  - Compare to h7v3pure (H22 reference) and h7v3plus (H21 reference)
  - Run H10 v9 chain quality (v6b per-video weights) on h7v3plus2
  - The 2 H24-KEPT edges use the same HAND_TRANSITION cost (1.0)
    and inherit H24's vshape/hand info
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

# H26 visually-confirmed REAL H20-KEPT edges (from H24)
# Format: (stem, from_tid, to_tid) -> {h24_verdict, vshape, hand, min_d, ratio, gap}
H26_RECLASSIFIED = {
    ("identical_balls_trick_000_018", 7, 10): {
        "h24_verdict": "REAL", "vshape": "V_SHALLOW", "which_hand": "left",
        "min_d": 57.35, "ratio": 2.239, "gap": 8,
        "h26_reason": "H24 visually-confirmed REAL H20-KEPT-not-in-h7v2 (R->L hand-off)",
    },
    ("identical_balls_trick_000_018", 59, 61): {
        "h24_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "right",
        "min_d": 18.94, "ratio": 5.303, "gap": 11,
        "h26_reason": "H24 visually-confirmed REAL H20-KEPT-not-in-h7v2 (R->L hand-off, V_DEEP)",
    },
}

H26_THRESHOLDS = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
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


def load_h21_reclassified() -> dict:
    """Load the H21 v1 5 visually-confirmed REAL H20-KEPT edges."""
    # Re-import H21's reclassified dict via JSON summary if available
    out = {}
    h21_summary = H1_DATA / "h21_summary.json"
    if h21_summary.exists():
        s = json.loads(h21_summary.read_text())
        for stem, v in s["videos"].items():
            for ft, tt, meta in v["h21_added"]:
                out[(stem, ft, tt)] = meta
    return out


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    etype = edge["edge_type"]
    if etype in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
                 "V_RECLASSIFIED_HAND_TRANSITION", "H21_RECLASSIFIED_HAND_TRANSITION",
                 "H26_RECLASSIFIED_HAND_TRANSITION"):
        return H26_THRESHOLDS["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H26_THRESHOLDS["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        err = edge.get("err", 0.0) or 0.0
        return (H26_THRESHOLDS["AIR_EDGE_BASE_COST"]
                + H26_THRESHOLDS["AIR_ERR_SCALE"] * err
                + H26_THRESHOLDS["AIR_GAP_SCALE"] * gap)
    return 5.0


def h26_min_cost_flow(edges: list[dict], tracklets: dict[int, dict]
                      ) -> tuple[dict[int, int], list[dict], dict]:
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

    def would_cycle(src: int, tgt: int) -> bool:
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
            continue
        if tgt in pred:
            continue
        if would_cycle(src, tgt):
            continue
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


def main():
    print("H26: integrate 2 H24 visually-confirmed REAL H20-KEPT edges as HAND_TRANSITION")
    print(f"  thresholds: {H26_THRESHOLDS}")
    print(f"  H24 NEW REAL edges: {list(H26_RECLASSIFIED.keys())}")
    print()

    summary = {"h26_thresholds": H26_THRESHOLDS, "videos": {}}

    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        h7v3pure_edges = load_h7v3pure_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  h7v3pure edges: {len(h7v3pure_edges)}")

        # Add H24 NEW REAL edges that target this stem
        h26_kept_for_stem = [k for k in H26_RECLASSIFIED.keys() if k[0] == stem]
        added = []
        for (s, ft, tt) in h26_kept_for_stem:
            meta = H26_RECLASSIFIED[(s, ft, tt)]
            new_edge = {
                "from_tid": ft,
                "to_tid": tt,
                "edge_type": "H26_RECLASSIFIED_HAND_TRANSITION",
                "metadata": f"h26_vshape={meta['vshape']}_h24={meta['h24_verdict']}_min_d={meta['min_d']}",
                "reclassify_reason": "",
                "v_reclassify_reason": "",
                "h26_reason": meta["h26_reason"],
                "which_hand": meta["which_hand"],
            }
            h7v3pure_edges.append(new_edge)
            added.append((ft, tt, meta))
        print(f"  H26-KEPT edges added: {len(added)}")
        for ft, tt, meta in added:
            print(f"    {ft:>3d} -> {tt:<3d}  h24={meta['h24_verdict']:<5} vshape={meta['vshape']:<9} "
                  f"hand={meta['which_hand']:<5}  ({meta['h26_reason']})")

        # Re-run min-cost flow
        succ, admitted, stats = h26_min_cost_flow(h7v3pure_edges, tracklets)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H26 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Edge type breakdown
        type_counts = defaultdict(int)
        for e in admitted:
            type_counts[e["edge_type"]] += 1
        print(f"  admitted edge types: {dict(type_counts)}")

        h26_admitted = [e for e in admitted
                        if e["edge_type"] == "H26_RECLASSIFIED_HAND_TRANSITION"]
        print(f"  H26_RECLASSIFIED in admitted: {len(h26_admitted)}")
        for e in h26_admitted:
            print(f"    {e['from_tid']:>3d} -> {e['to_tid']:<3d}  cost={e['cost']:.2f}")

        # Load h7v3pure chains for comparison
        try:
            h7v3_chains = list(csv.DictReader(open(H1_DATA / f"h7v3pure_chains_{stem}.csv")))
            h7v3_by_tid = {}
            for c in h7v3_chains:
                tids = set(int(t) for t in c["tids"].split(","))
                for t in tids:
                    h7v3_by_tid[t] = int(c["chain_id"])
            print(f"  H7v3pure chain count: {len(h7v3_chains)}")
        except FileNotFoundError:
            h7v3_chains = []
            h7v3_by_tid = {}
            print("  no h7v3pure chains file")

        # For each H26-KEPT edge, where do its endpoints live now?
        print(f"  H26-KEPT edge integration:")
        for ft, tt, meta in added:
            src_chain = None
            tgt_chain = None
            for cid, c in enumerate(chains):
                tids = set(c)
                if ft in tids:
                    src_chain = (cid, c)
                if tt in tids:
                    tgt_chain = (cid, c)
            h7v3_src = h7v3_by_tid.get(ft, "?")
            h7v3_tgt = h7v3_by_tid.get(tt, "?")
            print(f"    {ft:>3d}->{tt:<3d}  h7v3: src=chain {h7v3_src} tgt=chain {h7v3_tgt}")
            if src_chain and tgt_chain and src_chain[0] == tgt_chain[0]:
                print(f"      H26 INTEGRATION: merged into chain {src_chain[0]} = {src_chain[1]}")
            elif src_chain and tgt_chain:
                print(f"      H26 INTEGRATION: chain {src_chain[0]} (length {len(src_chain[1])}) "
                      f"-> chain {tgt_chain[0]} (length {len(tgt_chain[1])}) "
                      f"via {ft}->{tt}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_h7v3pure_edges": len(h7v3pure_edges) - len(added),
            "n_h26_added": len(added),
            "n_admitted": stats["n_admitted"],
            "n_rejected_capacity": stats["n_rejected_capacity"],
            "mean_cost_admitted": stats["mean_cost_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
            "h26_added": added,
            "edge_type_counts": dict(type_counts),
        }

    out_path = H1_DATA / "h26_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h7v3plus2_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost",
                "reclassify_reason", "v_reclassify_reason", "h26_reason"])
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
                    "h26_reason": e.get("h26_reason", ""),
                })
        with (H1_DATA / f"h7v3plus2_chains_{stem}.csv").open("w", newline="") as fh:
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
        # H26-Kept edges log
        with (H1_DATA / f"h7v3plus2_h26_kept_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "h24_verdict", "vshape", "which_hand",
                "min_d", "ratio", "gap", "h26_reason", "admitted"])
            w.writeheader()
            for ft, tt, meta in v["h26_added"]:
                admitted_keys = {(e["from_tid"], e["to_tid"]) for e in v["admitted_edges"]}
                admitted = (ft, tt) in admitted_keys
                w.writerow({
                    "from_tid": ft,
                    "to_tid": tt,
                    "h24_verdict": meta["h24_verdict"],
                    "vshape": meta["vshape"],
                    "which_hand": meta["which_hand"],
                    "min_d": meta["min_d"],
                    "ratio": meta["ratio"],
                    "gap": meta["gap"],
                    "h26_reason": meta["h26_reason"],
                    "admitted": admitted,
                })

    print("\n=== Per-video CSVs saved ===")


if __name__ == "__main__":
    main()
