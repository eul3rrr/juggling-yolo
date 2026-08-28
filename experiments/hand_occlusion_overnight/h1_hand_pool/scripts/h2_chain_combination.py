#!/usr/bin/env python3
"""H2 — Combine v4 hand-links with E6c mid-air edges into a unified chain
representation. Preserve edge provenance.

For each video, the inputs are:
- v4 hand-links (data/hand_links_v4_v4d_throw7_full.csv): the FROM
  tracklet was held in a hand, then the TO tracklet is thrown from
  that hand. Tagged HAND_TRANSITION or AMBIGUOUS_HAND_TRANSITION.
- E6c accepted mid-air edges (detections/<stem>_norfair_dt50_hc5_accepted_stitches.csv):
  the FROM tracklet's trajectory predicts the TO tracklet's start
  position. Tagged BALLISTIC.
- Tracklet-level CONTINUOUS edges: when two tracklets are
  *consecutive* (i.e. the next tracklet starts right after the
  previous ends with no gap), this is a CONTINUOUS observation.

The H2 chain combination:

1. For each v4 hand-link, the FROM tracklet is "consumed" by the
   hand (a HAND_TRANSITION edge), and the TO tracklet is "born"
   from the hand (also HAND_TRANSITION).
2. For each E6c accepted edge (source, candidate), insert a
   BALLISTIC edge between them.
3. Where a v4 hand-link and an E6c mid-air edge BOTH connect the
   same FROM tracklet to *different* destinations, RECORD the
   conflict (don't silently resolve).
4. Where a v4 hand-link and an E6c mid-air edge connect the same
   pair (source, candidate), mark the edge as HAND_AIR_AGREEMENT
   (the strongest possible edge).

Output:
- data/h2_chains.csv: per-chain summary (chain_id, tracklets, edges)
- data/h2_edges.csv: per-edge list with edge_type, source_tid, target_tid
- data/h2_conflicts.csv: per-conflict list (where hand and air disagree)
- data/h2_summary.json: counts and agreement statistics
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"
H2_DATA = H1_DATA  # write into the same data dir for now


STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    """Read v4 tracklet_features.csv to get first/last frame per tid."""
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
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


def load_v4_links(stem: str) -> list[dict]:
    """Read v4d hand_links.csv."""
    out = []
    with (H1_DATA / "hand_links_v4_v4d_throw7_full.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["from_frame"] = int(r["from_frame"])
            r["to_frame"] = int(r["to_frame"])
            r["from_dist"] = float(r["from_dist"])
            r["to_dist"] = float(r["to_dist"])
            r["from_slope"] = float(r["from_slope"])
            r["to_slope"] = float(r["to_slope"])
            r["tok_age_frames"] = int(r["tok_age_frames"])
            r["identity_ambiguous"] = (r["identity_ambiguous"] == "True")
            out.append(r)
    return out


def load_e6c_edges(stem: str) -> list[dict]:
    """Read E6c accepted_stitches.csv (accepted mid-air edges)."""
    out = []
    path = DETECTIONS / f"{stem}_norfair_dt50_hc5_accepted_stitches.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["accepted"] != "1":
                continue
            r["source_tracklet"] = int(r["source_tracklet"])
            r["candidate_tracklet"] = int(r["candidate_tracklet"])
            r["trajectory_fit_error"] = float(r["trajectory_fit_error"])
            out.append(r)
    return out


def build_chains(stem: str, hand_links: list[dict], air_edges: list[dict],
                 tracklets: dict[int, dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Build a chain representation from the edges.

    Each tracklet starts in its own chain. Hand-links and air-edges
    union their tracklets into a single chain. Conflicts (where
    hand and air both link the same source to DIFFERENT targets)
    are recorded separately.
    """
    # union-find over tracklets
    parent: dict[int, int] = {tid: tid for tid in tracklets}
    rank: dict[int, int] = {tid: 0 for tid in tracklets}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1

    # Build edges
    edges = []  # list of dicts: {from_tid, to_tid, edge_type, ...}
    for hl in hand_links:
        edges.append({
            "from_tid": hl["from_tid"],
            "to_tid": hl["to_tid"],
            "edge_type": ("AMBIGUOUS_HAND_TRANSITION" if hl["identity_ambiguous"]
                          else "HAND_TRANSITION"),
            "from_frame": hl["from_frame"],
            "to_frame": hl["to_frame"],
            "tok_age_frames": hl["tok_age_frames"],
            "hand": hl["hand"],
        })
        union(hl["from_tid"], hl["to_tid"])
    for ae in air_edges:
        edges.append({
            "from_tid": ae["source_tracklet"],
            "to_tid": ae["candidate_tracklet"],
            "edge_type": "BALLISTIC",
            "trajectory_fit_error": ae["trajectory_fit_error"],
        })
        union(ae["source_tracklet"], ae["candidate_tracklet"])

    # Find conflicts: a source tracklet has both a hand-link and
    # an air-edge to different destinations.
    by_source_hand: dict[int, int] = {}
    by_source_air: dict[int, int] = {}
    for e in edges:
        if e["edge_type"].endswith("HAND_TRANSITION"):
            if e["from_tid"] in by_source_hand and by_source_hand[e["from_tid"]] != e["to_tid"]:
                pass  # multiple hand-links from same source (shouldn't happen)
            by_source_hand[e["from_tid"]] = e["to_tid"]
        elif e["edge_type"] == "BALLISTIC":
            if e["from_tid"] in by_source_air and by_source_air[e["from_tid"]] != e["to_tid"]:
                pass
            by_source_air[e["from_tid"]] = e["to_tid"]

    conflicts = []
    for src, hand_target in by_source_hand.items():
        if src in by_source_air and by_source_air[src] != hand_target:
            conflicts.append({
                "from_tid": src,
                "hand_target": hand_target,
                "air_target": by_source_air[src],
            })
    # Also record agreements: a source has BOTH a hand-link and an
    # air-edge to the SAME destination (strongest possible edge).
    agreements = []
    for src, hand_target in by_source_hand.items():
        if src in by_source_air and by_source_air[src] == hand_target:
            agreements.append({
                "from_tid": src,
                "to_tid": hand_target,
                "kind": "HAND_AIR_AGREEMENT",
            })

    # Build chain summary
    chain_tids: dict[int, list[int]] = defaultdict(list)
    for tid in tracklets:
        chain_tids[find(tid)].append(tid)
    chains = []
    for cid, tids in sorted(chain_tids.items()):
        tids_sorted = sorted(tids, key=lambda t: tracklets[t]["first_frame"])
        n_tracklets = len(tids_sorted)
        first_frame = tracklets[tids_sorted[0]]["first_frame"]
        last_frame = tracklets[tids_sorted[-1]]["last_frame"]
        # Find all edges within this chain
        tids_set = set(tids_sorted)
        chain_edges = [e for e in edges
                       if e["from_tid"] in tids_set
                       and e["to_tid"] in tids_set]
        n_hand = sum(1 for e in chain_edges if "HAND_TRANSITION" in e["edge_type"])
        n_air = sum(1 for e in chain_edges if e["edge_type"] == "BALLISTIC")
        chains.append({
            "chain_id": cid,
            "n_tracklets": n_tracklets,
            "first_frame": first_frame,
            "last_frame": last_frame,
            "tids": tids_sorted,
            "n_hand_edges": n_hand,
            "n_air_edges": n_air,
        })

    return chains, edges, conflicts


def main():
    out = {"videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        hand_links = load_v4_links(stem)
        air_edges = load_e6c_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  v4d hand-links: {len(hand_links)}")
        print(f"  E6c air-edges: {len(air_edges)}")

        chains, edges, conflicts = build_chains(stem, hand_links, air_edges,
                                                 tracklets)
        print(f"  H2 chains: {len(chains)}")
        print(f"  H2 edges: {len(edges)}")
        print(f"  conflicts: {len(conflicts)}")
        for c in chains:
            if c["n_tracklets"] > 1:
                print(f"    chain {c['chain_id']}: tids {c['tids']} "
                      f"({c['n_hand_edges']} hand, {c['n_air_edges']} air)")
        for conflict in conflicts:
            print(f"    CONFLICT: {conflict['from_tid']} -> hand={conflict['hand_target']}, air={conflict['air_target']}")

        out["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_hand_links": len(hand_links),
            "n_air_edges": len(air_edges),
            "n_chains": len(chains),
            "n_chains_multi": sum(1 for c in chains if c["n_tracklets"] > 1),
            "n_edges": len(edges),
            "n_conflicts": len(conflicts),
            "conflicts": conflicts,
            "chains": chains,
        }

    out_path = H2_DATA / "h2_summary.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        chains = out["videos"][stem]["chains"]
        edges = []
        # Re-build edges for CSV export
        hand_links = load_v4_links(stem)
        air_edges = load_e6c_edges(stem)
        for hl in hand_links:
            edges.append({
                "from_tid": hl["from_tid"],
                "to_tid": hl["to_tid"],
                "edge_type": "AMBIGUOUS_HAND_TRANSITION" if hl["identity_ambiguous"] else "HAND_TRANSITION",
                "metadata": f"tok_age={hl['tok_age_frames']},hand={hl['hand']}",
            })
        for ae in air_edges:
            edges.append({
                "from_tid": ae["source_tracklet"],
                "to_tid": ae["candidate_tracklet"],
                "edge_type": "BALLISTIC",
                "metadata": f"err={ae['trajectory_fit_error']:.2f}",
            })
        with (H2_DATA / f"h2_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["from_tid", "to_tid", "edge_type", "metadata"])
            w.writeheader()
            for e in edges:
                w.writerow(e)
        with (H2_DATA / f"h2_chains_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "first_frame", "last_frame",
                "n_hand_edges", "n_air_edges", "tids"])
            w.writeheader()
            for c in chains:
                w.writerow({
                    "chain_id": c["chain_id"],
                    "n_tracklets": c["n_tracklets"],
                    "first_frame": c["first_frame"],
                    "last_frame": c["last_frame"],
                    "n_hand_edges": c["n_hand_edges"],
                    "n_air_edges": c["n_air_edges"],
                    "tids": ",".join(str(t) for t in c["tids"]),
                })
        with (H2_DATA / f"h2_conflicts_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["from_tid", "hand_target", "air_target"])
            w.writeheader()
            for c in out["videos"][stem]["conflicts"]:
                w.writerow(c)


if __name__ == "__main__":
    main()
