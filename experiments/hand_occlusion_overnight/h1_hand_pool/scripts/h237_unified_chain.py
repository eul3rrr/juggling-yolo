#!/usr/bin/env python3
"""H2+H3+H7 unified chain representation.

Integrate:
- v4d hand-links (HAND_TRANSITION / AMBIGUOUS_HAND_TRANSITION)
- E6c mid-air edges (BALLISTIC)
- H3 stationary-cluster confirmation flag (h3_confirmed)
- H7 conflict resolution (one successor per source, one predecessor per target)

This is the most informative possible chain representation. Each edge has:
- edge_type (HAND_TRANSITION / AMBIGUOUS_HAND_TRANSITION / BALLISTIC)
- from_tid, to_tid
- H7 cost
- h3_confirmed (only for hand transitions)
- chain provenance

The H7 successor map is the conflict-resolved backbone. Edges not in
H7's admitted set are NOT in the final chain (H2 union-find admitted
all, H6/H7 resolve conflicts).

Output:
- data/h237_unified_chains_<stem>.csv: per-chain summary
- data/h237_unified_edges_<stem>.csv: per-edge list with H7 + H3 metadata
- data/h237_unified_summary.json: full summary
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

H7 = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
}


def load_tracklet_features(stem):
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


def load_v4d_with_h3(stem):
    """Returns dict (from_tid, to_tid) -> hand link dict with h3_confirmed."""
    out = {}
    with (H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["h3_confirmed"] = (r["h3_confirmed"] == "True")
            out[(r["from_tid"], r["to_tid"])] = r
    return out


def load_h2_edges(stem):
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


def edge_cost(e, src_last, tgt_first):
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


def h7_resolve(edges, tracklets):
    """Run H7 (greedy iterative min-cost with capacity constraints)."""
    ec = []
    for e in edges:
        c = edge_cost(e, tracklets[e["from_tid"]]["last_frame"],
                      tracklets[e["to_tid"]]["first_frame"])
        ec.append({**e, "cost": c})
    ec.sort(key=lambda e: e["cost"])
    succ, pred = {}, {}
    admitted = []
    def cycle(s, t):
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
        if s in succ or t in pred or cycle(s, t):
            continue
        succ[s] = t
        pred[t] = s
        admitted.append(e)
    return succ, admitted


def walk_chains(succ, all_tids):
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
    summary = {"h7_thresholds": H7, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        h2_edges = load_h2_edges(stem)
        v4d_h3 = load_v4d_with_h3(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  H2 edges: {len(h2_edges)}")
        print(f"  v4d with H3: {len(v4d_h3)}")

        # H7 resolve
        succ, admitted = h7_resolve(h2_edges, tracklets)
        # Augment admitted edges with H3 confirmation if applicable
        for e in admitted:
            e["h3_confirmed"] = v4d_h3.get((e["from_tid"], e["to_tid"]),
                                            {}).get("h3_confirmed", None)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H2+H7 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        n_conflicts = len([e for e in h2_edges
                           if e["edge_type"].endswith("HAND_TRANSITION")])
        n_air = sum(1 for e in admitted if e["edge_type"] == "BALLISTIC")
        n_hand = sum(1 for e in admitted if "HAND_TRANSITION" in e["edge_type"])
        n_h3_confirmed = sum(1 for e in admitted if e.get("h3_confirmed"))
        print(f"  admitted: {len(admitted)} ({n_hand} hand, {n_air} air, "
              f"{n_h3_confirmed} h3_confirmed)")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_h2_edges": len(h2_edges),
            "n_admitted": len(admitted),
            "n_hand_admitted": n_hand,
            "n_air_admitted": n_air,
            "n_h3_confirmed": n_h3_confirmed,
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
        }

    out_path = H1_DATA / "h237_unified_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h237_unified_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "cost", "h3_confirmed",
                "metadata"])
            w.writeheader()
            for e in v["admitted_edges"]:
                w.writerow({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "edge_type": e["edge_type"],
                    "cost": f"{e['cost']:.3f}",
                    "h3_confirmed": "" if e.get("h3_confirmed") is None else e["h3_confirmed"],
                    "metadata": e["metadata"],
                })
        with (H1_DATA / f"h237_unified_chains_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "first_frame", "last_frame",
                "n_hand_edges", "n_air_edges", "n_h3_confirmed", "tids"])
            w.writeheader()
            tracklets = load_tracklet_features(stem)
            for cid, chain in enumerate(v["chains"]):
                if chain:
                    first_frame = min(tracklets[t]["first_frame"] for t in chain)
                    last_frame = max(tracklets[t]["last_frame"] for t in chain)
                else:
                    first_frame = last_frame = 0
                tids_set = set(chain)
                n_h = sum(1 for e in v["admitted_edges"]
                           if e["from_tid"] in tids_set and e["to_tid"] in tids_set
                           and "HAND_TRANSITION" in e["edge_type"])
                n_a = sum(1 for e in v["admitted_edges"]
                           if e["from_tid"] in tids_set and e["to_tid"] in tids_set
                           and e["edge_type"] == "BALLISTIC")
                n_h3 = sum(1 for e in v["admitted_edges"]
                           if e["from_tid"] in tids_set and e["to_tid"] in tids_set
                           and e.get("h3_confirmed"))
                w.writerow({
                    "chain_id": cid,
                    "n_tracklets": len(chain),
                    "first_frame": first_frame,
                    "last_frame": last_frame,
                    "n_hand_edges": n_h,
                    "n_air_edges": n_a,
                    "n_h3_confirmed": n_h3,
                    "tids": ",".join(str(t) for t in chain),
                })


if __name__ == "__main__":
    main()
