#!/usr/bin/env python3
"""H7 v2 — Re-classify BALLISTIC edges as HAND_TRANSITION if they pass through
a hand region at the connection point.

HYPOTHESIS (master §11, STATE.md item 21):
  H8 v8 analysis showed that most YouTube H7 BALLISTIC edges are actually
  catch+throw events in disguise — the source ends at the hand and the target
  starts at the hand, but H7 only sees the time gap and ballistic error, not
  the hand proximity at the connection point. The H7 chain algorithm
  classifies them as BALLISTIC, but they're really hand transitions with
  large velocity discontinuity (catch + throw in <10 frames).

  H7 v2 hypothesizes that adding a hand-region check at chain construction
  time will:
  1. Reclassify catch+throw BALLISTIC edges as HAND_TRANSITION (cost 1.0
     instead of 2.0+).
  2. Fix the YouTube H10 v5 over-counting at its source (reclassified edges
     are not BALLISTIC, so they're not penalized by h8).
  3. Not affect identical-video chains (the BALLISTIC edges there are mostly
     true identity switches, not catch+throws).

APPROACH (declared before reading outcomes):

  THRESHOLDS (declared from physical geometry, NOT tuned to manual labels):
  * HAND_REACH_PX = 108 (from H1 v1, = 0.15 * image_height)
  * MAX_GAP_FOR_RECLASSIFY_FRAMES = 20 (catch+throw takes ~5-15 frames;
    a real catch+throw has a small gap; larger gaps are not catch+throws)
  * MIN_HAND_PROXIMITY_FRAMES = 1 (either endpoint at the hand is enough)
  * HAND_EDGE_COST = 1.0 (same as H7)
  * AIR_EDGE_BASE_COST = 2.0 (same as H7)

  RECLASSIFICATION RULE:
  An edge (i, j) of type BALLISTIC is reclassified as HAND_TRANSITION if:
    - source's end_dist <= 108 (i.e., source ends within hand reach)
    OR
    - target's start_dist <= 108 (i.e., target starts within hand reach)
  AND
    - (target.first_frame - source.last_frame) <= 20 (small time gap)

  This rule is physical: a real catch happens at the hand, a real throw
  starts at the hand. A ballistic edge that connects to the hand at
  EITHER endpoint is likely a catch+throw pair. A small gap is required
  because a long gap means the ball was in the air, not at the hand.

  SENSITIVITY: MAX_GAP_FOR_RECLASSIFY_FRAMES ∈ {10, 15, 20, 30, 60}
  (declared BEFORE reading outcomes)

  INPUTS:
  * h2_edges_*.csv (HAND_TRANSITION, AMBIGUOUS_HAND_TRANSITION, BALLISTIC)
  * tracklet_features.csv (end_dist, start_dist per tracklet)

  OUTPUTS:
  * h7v2_admitted_edges_*.csv (with reclassified edge types)
  * h7v2_chains_*.csv
  * h7v2_summary.json

EXPECTED OUTCOME:
  * identical: minimal change (most BALLISTIC edges are real identity
    switches, not catch+throws)
  * YouTube: substantial change. Many BALLISTIC edges reclassified as
    HAND_TRANSITION, which removes them from h8's air-edge penalty
    in H10. The YouTube H10 v6b over-counting should be reduced.
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

# H7 v2 thresholds (declared from physical geometry, NOT tuned to manual labels)
H7V2 = {
    "HAND_REACH_PX": 108,                # 0.15 * 720 (from H1 v1)
    "MAX_GAP_FOR_RECLASSIFY_FRAMES": 20,  # catch+throw takes ~5-15 frames
    "HAND_EDGE_COST": 1.0,               # same as H7
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
    # H1 v4 catch/throw criteria (inherited from h1_hand_pool.py)
    "MIN_TRACKLET_LEN": 3,               # need >=3 obs to fit a slope
    "CATCH_SLOPE_PX_PER_FRAME": -1.0,    # distance decreasing at the end
    "THROW_SLOPE_PX_PER_FRAME": 1.0,     # distance increasing at the start
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    """Read tracklet_features.csv to get first/last frame and end_dist/start_dist per tid."""
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


def should_reclassify(edge: dict, src: dict, tgt: dict,
                      max_gap: int = H7V2["MAX_GAP_FOR_RECLASSIFY_FRAMES"],
                      reach: int = H7V2["HAND_REACH_PX"],
                      min_n_pts: int = H7V2["MIN_TRACKLET_LEN"],
                      catch_slope: float = H7V2["CATCH_SLOPE_PX_PER_FRAME"],
                      throw_slope: float = H7V2["THROW_SLOPE_PX_PER_FRAME"],
                      ) -> tuple[bool, str]:
    """Determine if a BALLISTIC edge should be reclassified as HAND_TRANSITION.

    STRICTER rule using H1 v4's catch/throw criteria:
    - Source is a catch if end_dist <= reach AND end_slope < catch_slope
      (i.e., the source's distance to the hand is decreasing).
    - Target is a throw if start_dist <= reach AND start_slope > throw_slope
      (i.e., the target's distance to the hand is increasing).
    - Either endpoint being a real catch/throw is sufficient to reclassify.
    - Plus a max-gap constraint: catch+throw takes ~5-15 frames.
    - Plus a min-n_pts constraint: need enough data to estimate slope.

    Returns: (should_reclassify, reason)
    """
    if edge["edge_type"] != "BALLISTIC":
        return False, "not_ballistic"
    gap = tgt["first_frame"] - src["last_frame"]
    if gap > max_gap:
        return False, f"gap_too_large_{gap}"
    # Source ends with catch signature
    src_is_catch = (src["n_pts"] >= min_n_pts
                    and src["end_dist"] is not None
                    and src["end_dist"] <= reach
                    and src["end_slope"] is not None
                    and src["end_slope"] < catch_slope)
    if src_is_catch:
        return True, (f"src_catch_dist={src['end_dist']:.1f}_"
                      f"slope={src['end_slope']:.2f}_"
                      f"side={src['end_side']}")
    # Target starts with throw signature
    tgt_is_throw = (tgt["n_pts"] >= min_n_pts
                    and tgt["start_dist"] is not None
                    and tgt["start_dist"] <= reach
                    and tgt["start_slope"] is not None
                    and tgt["start_slope"] > throw_slope)
    if tgt_is_throw:
        return True, (f"tgt_throw_dist={tgt['start_dist']:.1f}_"
                      f"slope={tgt['start_slope']:.2f}_"
                      f"side={tgt['start_side']}")
    return False, "no_catch_throw_signature"


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    """Compute the cost of an H2 edge. HAND edges (incl. reclassified) get
    flat cost; air edges get base + err*scale + gap*scale."""
    etype = edge["edge_type"]
    if etype in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION"):
        return H7V2["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H7V2["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        return (H7V2["AIR_EDGE_BASE_COST"]
                + H7V2["AIR_ERR_SCALE"] * edge["err"]
                + H7V2["AIR_GAP_SCALE"] * gap)
    return 5.0  # unknown type


def h7v2_min_cost_flow(edges: list[dict], tracklets: dict[int, dict]
                      ) -> tuple[dict[int, int], list[dict], dict]:
    """Greedy iterative min-cost flow with capacity constraints.

    Same as H7 but with reclassified edges.
    """
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
                break
            chain.append(nxt)
            cur = nxt
        chains.append(chain)
    return chains


def main():
    summary = {"h7v2_thresholds": H7V2, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        edges = load_h2_edges(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  H2 edges: {len(edges)}")

        # Step 1: reclassify BALLISTIC edges that pass through a hand region
        reclassified = []
        for e in edges:
            src = tracklets[e["from_tid"]]
            tgt = tracklets[e["to_tid"]]
            should, reason = should_reclassify(e, src, tgt)
            if should:
                e["edge_type"] = "RECLASSIFIED_HAND_TRANSITION"
                e["reclassify_reason"] = reason
                reclassified.append({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "reason": reason,
                    "gap": tgt["first_frame"] - src["last_frame"],
                })
        print(f"  reclassified: {len(reclassified)} of {len(edges)} edges")
        for r in reclassified[:5]:
            print(f"    {r['from_tid']:>3} -> {r['to_tid']:>3}  "
                  f"gap={r['gap']:>2}  {r['reason']}")
        if len(reclassified) > 5:
            print(f"    ... and {len(reclassified) - 5} more")

        # Step 2: run min-cost flow
        succ, admitted, stats = h7v2_min_cost_flow(edges, tracklets)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  H7 v2 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Edge type breakdown in admitted
        type_counts = defaultdict(int)
        for e in admitted:
            type_counts[e["edge_type"]] += 1
        print(f"  admitted edge types: {dict(type_counts)}")

        # Print reclassified edges in admitted
        rec_admitted = [e for e in admitted
                        if e["edge_type"] == "RECLASSIFIED_HAND_TRANSITION"]
        print(f"  reclassified in admitted: {len(rec_admitted)}")
        for e in rec_admitted:
            print(f"    {e['from_tid']:>3} -> {e['to_tid']:>3}  "
                  f"cost={e['cost']:.2f}  ({e['reclassify_reason']})")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_edges_in": stats["n_edges_in"],
            "n_reclassified": len(reclassified),
            "n_reclassified_admitted": len(rec_admitted),
            "n_admitted": stats["n_admitted"],
            "n_rejected_capacity": stats["n_rejected_capacity"],
            "mean_cost_admitted": stats["mean_cost_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
            "reclassified_edges": reclassified,
            "edge_type_counts": dict(type_counts),
        }

    out_path = H1_DATA / "h7v2_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost",
                "reclassify_reason"])
            w.writeheader()
            for e in v["admitted_edges"]:
                w.writerow({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "edge_type": e["edge_type"],
                    "metadata": e["metadata"],
                    "cost": f"{e['cost']:.3f}",
                    "reclassify_reason": e.get("reclassify_reason", ""),
                })
        with (H1_DATA / f"h7v2_chains_{stem}.csv").open("w", newline="") as fh:
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
        # Also write the reclassified edges log
        with (H1_DATA / f"h7v2_reclassified_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "gap", "reason"])
            w.writeheader()
            for r in v["reclassified_edges"]:
                w.writerow({
                    "from_tid": r["from_tid"],
                    "to_tid": r["to_tid"],
                    "gap": r["gap"],
                    "reason": r["reason"],
                })

    print("\n=== Per-video CSVs saved ===")


if __name__ == "__main__":
    main()
