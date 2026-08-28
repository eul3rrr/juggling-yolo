#!/usr/bin/env python3
"""H21: integrate H20-KEPT visually-confirmed REAL edges as new HAND_TRANSITION edges.

HYPOTHESIS:
  H20 found 26 e6c_not_in_h7v2 candidates that pass all 3 H20 filters. Of
  the 8 visually-QA'd, 5 are REAL or PARTIAL. These 5 represent real
  catch+throws that the production h7v2 chain set missed. The question
  is: do they improve chain quality and identity propagation if added
  to the h7v3pure chain pipeline?

  The 5 visually-confirmed REAL H20-KEPT edges:
  - identical 6->15  (chain 4 [5,6] -> chain 11 [15]: 3-tracklet chain)
  - identical 54->57 (chain 30 [51,52,54,59,63] -> chain 33 [57]: extends)
  - identical 56->57 (singleton 56 -> chain 33 [57]: extends)
  - identical 56->58 (singleton 56 -> chain 34 [58]: 2-tracklet chain)
  - youtube  20->21  (chain 10 [20] -> chain 0 [1,9,13,16,21,29,34]: extends)

  Important constraint: the 4 identical edges were NOT in the E6c accepted
  edges set (E6c didn't see them as mid-air edges). The 1 YouTube edge
  was in H2 as BALLISTIC but rejected by H7v2's strict endpoint check
  (target's first frame was 35.3 px from wrist, > the reach radius).

  This means H21 must:
  1. Add the 4 identical edges as NEW HAND_TRANSITION edges (not reclassify).
  2. Re-evaluate the YouTube 20->21 edge as HAND_TRANSITION (override
     the strict endpoint rejection).

APPROACH (declared before reading outcomes):

  H21 thresholds (inherited from H7v2 / H15v2):
  * HAND_EDGE_COST = 1.0
  * AMBIGUOUS_HAND_EDGE_COST = 1.5
  * AIR_EDGE_BASE_COST = 2.0
  * HAND_REACH_PX = 108 (not enforced for H21-Kept edges, which are
    added unconditionally based on H20 visual QA)

  H21 step:
    1. Load h7v3pure edges (from h7v3pure_admitted_edges_<stem>.csv)
    2. Add the 5 H20-KEPT-REAL edges as new HAND_TRANSITION edges with
       cost 1.0
    3. Re-run min-cost flow with the augmented edge set
    4. Walk new chains
    5. Compare to h7v3pure: which chains merged? which extended?
    6. Save h7v3plus chains, edges

EXPECTED OUTCOME:
  * identical: chain 4 (5,6) + chain 11 (15) -> chain (5,6,15) via 6->15
  * identical: chain 30 (51,52,54,59,63) + chain 33 (57) -> chain (51,52,54,59,63,57) via 54->57
  * identical: new chain 56,57 via 56->57
  * identical: new chain 56,58 via 56->58 (or merges with 56,57 if 57->58)
  * youtube: chain 0 (1,9,13,16,21,29,34) + chain 10 (20) -> chain (1,9,13,16,20,21,29,34) via 20->21
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

# H21 visually-confirmed REAL H20-KEPT edges
# Format: (stem, from_tid, to_tid) -> {h17_verdict, h20_vshape, which_hand, min_d, ratio, gap}
H21_RECLASSIFIED = {
    ("identical_balls_trick_000_018", 6, 15): {
        "h17_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "right",
        "min_d": 2.1, "ratio": 46.6, "gap": 16,
        "h21_reason": "H20-KEPT e6c_not_in_h7v2, vision-confirmed REAL",
    },
    ("identical_balls_trick_000_018", 54, 57): {
        "h17_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "right",
        "min_d": 8.5, "ratio": 38.1, "gap": 9,
        "h21_reason": "H20-KEPT e6c_not_in_h7v2, vision-confirmed REAL",
    },
    ("identical_balls_trick_000_018", 56, 57): {
        "h17_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "left",
        "min_d": 7.1, "ratio": 65.5, "gap": 10,
        "h21_reason": "H20-KEPT e6c_not_in_h7v2, vision-confirmed REAL",
    },
    ("identical_balls_trick_000_018", 56, 58): {
        "h17_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "left",
        "min_d": None, "ratio": None, "gap": None,
        "h21_reason": "H20-KEPT e6c_not_in_h7v2, vision-confirmed REAL",
    },
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 20, 21): {
        "h17_verdict": "REAL", "vshape": "V_DEEP", "which_hand": "right",
        "min_d": 5.3, "ratio": 17.3, "gap": 12,
        "h21_reason": "H20-KEPT e6c_not_in_h7v2, vision-confirmed REAL (was BALLISTIC in H2, rejected by H7v2 strict endpoint check)",
    },
}

H21_THRESHOLDS = {
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
    """Load H7v3pure admitted edges."""
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    """Cost function. HAND edges (incl. H21-KEPT) = 1.0."""
    etype = edge["edge_type"]
    if etype in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
                 "V_RECLASSIFIED_HAND_TRANSITION", "H21_RECLASSIFIED_HAND_TRANSITION"):
        return H21_THRESHOLDS["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H21_THRESHOLDS["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        err = edge.get("err", 0.0) or 0.0
        return (H21_THRESHOLDS["AIR_EDGE_BASE_COST"]
                + H21_THRESHOLDS["AIR_ERR_SCALE"] * err
                + H21_THRESHOLDS["AIR_GAP_SCALE"] * gap)
    return 5.0


def h21_min_cost_flow(edges: list[dict], tracklets: dict[int, dict]
                      ) -> tuple[dict[int, int], list[dict], dict]:
    """Same as H7v2 but with H21-KEPT edges included."""
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
    print("H21: integrate 5 H20-KEPT visually-confirmed REAL edges as HAND_TRANSITION")
    print(f"  thresholds: {H21_THRESHOLDS}")
    print()

    summary = {"h21_thresholds": H21_THRESHOLDS, "videos": {}}

    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        h7v3pure_edges = load_h7v3pure_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  h7v3pure edges: {len(h7v3pure_edges)}")

        # Add the H21-KEPT edges that target this stem
        h21_kept_for_stem = [k for k in H21_RECLASSIFIED.keys() if k[0] == stem]
        added = []
        for (s, ft, tt) in h21_kept_for_stem:
            meta = H21_RECLASSIFIED[(s, ft, tt)]
            new_edge = {
                "from_tid": ft,
                "to_tid": tt,
                "edge_type": "H21_RECLASSIFIED_HAND_TRANSITION",
                "metadata": f"h21_vshape={meta['vshape']}_h17={meta['h17_verdict']}_min_d={meta['min_d']}",
                "reclassify_reason": "",
                "v_reclassify_reason": "",
                "h21_reason": meta["h21_reason"],
                "which_hand": meta["which_hand"],
            }
            h7v3pure_edges.append(new_edge)
            added.append((ft, tt, meta))
        print(f"  H21-KEPT edges added: {len(added)}")
        for ft, tt, meta in added:
            print(f"    {ft:>3d} -> {tt:<3d}  h17={meta['h17_verdict']:<5} vshape={meta['vshape']} "
                  f"hand={meta['which_hand']:<5}  ({meta['h21_reason']})")

        # Re-run min-cost flow
        succ, admitted, stats = h21_min_cost_flow(h7v3pure_edges, tracklets)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H21 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Edge type breakdown
        type_counts = defaultdict(int)
        for e in admitted:
            type_counts[e["edge_type"]] += 1
        print(f"  admitted edge types: {dict(type_counts)}")

        h21_admitted = [e for e in admitted
                        if e["edge_type"] == "H21_RECLASSIFIED_HAND_TRANSITION"]
        print(f"  H21_RECLASSIFIED in admitted: {len(h21_admitted)}")
        for e in h21_admitted:
            print(f"    {e['from_tid']:>3d} -> {e['to_tid']:<3d}  cost={e['cost']:.2f}")

        # Compare to h7v3pure chains: which chains merged/extended?
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

        # For each H21-KEPT edge, where do its endpoints live now?
        print(f"  H21-KEPT edge integration:")
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
                print(f"      H21 INTEGRATION: merged into chain {src_chain[0]} = {src_chain[1]}")
            elif src_chain and tgt_chain:
                print(f"      H21 INTEGRATION: chain {src_chain[0]} (length {len(src_chain[1])}) "
                      f"-> chain {tgt_chain[0]} (length {len(tgt_chain[1])}) "
                      f"via {ft}->{tt}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_h7v3pure_edges": len(h7v3pure_edges) - len(added),
            "n_h21_added": len(added),
            "n_admitted": stats["n_admitted"],
            "n_rejected_capacity": stats["n_rejected_capacity"],
            "mean_cost_admitted": stats["mean_cost_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
            "h21_added": added,
            "edge_type_counts": dict(type_counts),
        }

    out_path = H1_DATA / "h21_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h7v3plus_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost",
                "reclassify_reason", "v_reclassify_reason", "h21_reason"])
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
                    "h21_reason": e.get("h21_reason", ""),
                })
        with (H1_DATA / f"h7v3plus_chains_{stem}.csv").open("w", newline="") as fh:
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
        # H21-Kept edges log
        with (H1_DATA / f"h7v3plus_h21_kept_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "h17_verdict", "vshape", "which_hand",
                "min_d", "ratio", "gap", "h21_reason", "admitted"])
            w.writeheader()
            for ft, tt, meta in v["h21_added"]:
                # Check if this edge was admitted
                admitted_keys = {(e["from_tid"], e["to_tid"]) for e in v["admitted_edges"]}
                admitted = (ft, tt) in admitted_keys
                w.writerow({
                    "from_tid": ft,
                    "to_tid": tt,
                    "h17_verdict": meta["h17_verdict"],
                    "vshape": meta["vshape"],
                    "which_hand": meta["which_hand"],
                    "min_d": meta["min_d"],
                    "ratio": meta["ratio"],
                    "gap": meta["gap"],
                    "h21_reason": meta["h21_reason"],
                    "admitted": admitted,
                })

    print("\n=== Per-video CSVs saved ===")


if __name__ == "__main__":
    main()
