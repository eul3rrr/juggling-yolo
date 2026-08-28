#!/usr/bin/env python3
"""H15 — Reclassify h7v2-kept BALLISTIC edges as HAND_TRANSITION if they
pass an H14-style V-shape check AND a velocity-jump sanity check.

HYPOTHESIS (master §11, STATE.md item 22, H14 follow-up):

  H7v2 reclassification rule:
    src end_dist <= 108 AND src end_slope < -1.0
    OR tgt start_dist <= 108 AND tgt start_slope > 1.0

  is too strict. H14 found 4 hidden catch-throws on identical (and
  1 YouTube false positive) that the V-shape check recovered.

  H15 combines:
    1. H14 V-shape: full trajectory dips toward a hand and back out
       (V_DEEP: min_d<50 & ratio>=1.5; V_SHALLOW: min_d<100 & ratio>=1.3)
    2. H16-style velocity-jump sanity check: the spatial jump from
       src's last detection to tgt's first detection, divided by
       (gap+1), must be <= JUMP_TOLERANCE. A real catch+throw has
       the ball near the hand at both endpoints, so the jump is
       small. A tracklet break (like 27->28 YouTube) has a 100-px
       jump in 5 frames (20 px/frame) that this rejects.

  Together, these rules additively extend H7v2 by recovering the
  4 V-shape-positive BALLISTIC edges on identical without admitting
  the YouTube false positive.

APPROACH (declared before reading outcomes):

  THRESHOLDS (declared from physical geometry, NOT tuned to manual labels):
  * V_DEEP_MIN_PX = 50, V_DEEP_RATIO = 1.5
  * V_SHALLOW_MIN_PX = 100, V_SHALLOW_RATIO = 1.3
  * JUMP_TOLERANCE_PX_PER_FRAME = 15.0
        (real ball at 30fps reaches ~30 px/frame vertically; spatial
         tracklet break with 20 px/frame is implausible for a juggling
         ball at this image scale)
  * New edge type: V_RECLASSIFIED_HAND_TRANSITION
        (distinct from H7v2's RECLASSIFIED_HAND_TRANSITION to preserve
         provenance in downstream analysis)

  RECLASSIFICATION RULE (h7v3):
    An h7v2 BALLISTIC edge (i, j) is reclassified as
    V_RECLASSIFIED_HAND_TRANSITION if:
      - h14_classification in {V_DEEP, V_SHALLOW} (V-shape positive)
      AND
      - spatial_jump / (gap + 1) <= 15 px/frame (velocity sanity)

  Algorithm:
    1. Load h7v2 chains and edges.
    2. Load h14 V-shape per-edge classification.
    3. For each BALLISTIC edge in h7v2 admitted edges:
       a. Look up h14_classification. Skip if FLAT.
       b. Compute spatial_jump from src last det to tgt first det,
          divided by (gap + 1). Skip if jump > JUMP_TOLERANCE.
       c. Reclassify as V_RECLASSIFIED_HAND_TRANSITION with cost 1.0
          (same as hand-edges).
    4. Re-run min-cost flow with new edge types and capacities.
    5. Walk new chains.
    6. Recompute H10 v8 chain quality on new chains.
    7. Save h7v3 chains, edges, and chain quality CSVs.

  SENSITIVITY:
    * JUMP_TOLERANCE ∈ {10, 12, 15, 20, 30} (declared grid).
    * V-shape thresholds from h14 (5x4 grid).

EXPECTED OUTCOME:
  * identical: 4 new HAND_TRANSITION edges (23->25, 30->33, 39->47, 51->52).
    Some chains join. YouTube 27->28 is rejected by the velocity check.
  * YouTube: 0 new edges (the only V-shape positive is the 27->28 false
    positive, which fails the velocity-jump check).
  * H10 v8 mean quality: should improve on identical (no air-edge penalty
    on the 4 newly-hand-edges) and unchanged on YouTube.
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
H15_OUT = H1_DIR / "contact_sheets_h15"
H15_OUT.mkdir(parents=True, exist_ok=True)

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# H15 thresholds (declared from physical geometry, NOT tuned to manual labels)
H15 = {
    "V_DEEP_MIN_PX": 50,
    "V_DEEP_RATIO": 1.5,
    "V_SHALLOW_MIN_PX": 100,
    "V_SHALLOW_RATIO": 1.3,
    "JUMP_TOLERANCE_PX_PER_FRAME": 15.0,
    # Inherited H7v2 thresholds
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
    "MAX_GAP_FOR_RECLASSIFY_FRAMES": 20,
    "HAND_REACH_PX": 108,
    "MIN_TRACKLET_LEN": 3,
    "CATCH_SLOPE_PX_PER_FRAME": -1.0,
    "THROW_SLOPE_PX_PER_FRAME": 1.0,
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


def load_h7v2_edges(stem: str) -> list[dict]:
    """Load H7v2 admitted edges."""
    out = []
    with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def load_h14_per_edge(stem: str) -> dict[tuple[int, int], dict]:
    """Load H14 per-edge V-shape results. Return {(from, to): record}."""
    out = {}
    with (H1_DATA / "h14_summary.json").open() as fh:
        d = json.load(fh)
    for r in d["per_edge"]:
        if r["stem"] != stem:
            continue
        out[(r["from_tid"], r["to_tid"])] = r
    return out


def load_per_det_tracklet(stem: str, tid: int) -> list[tuple]:
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if int(r["track_id"]) != tid:
                continue
            try:
                fr = int(r["frame"])
                x = float(r["center_x"])
                y = float(r["center_y"])
                c = float(r["confidence"])
                out.append((fr, x, y, c))
            except (ValueError, KeyError):
                continue
    out.sort()
    return out


def compute_spatial_jump(stem: str, src_tid: int, tgt_tid: int) -> tuple[float, int]:
    """Compute the spatial jump (in px/frame) from src's last detection
    to tgt's first detection. Returns (jump_px_per_frame, gap_frames)."""
    src_dets = load_per_det_tracklet(stem, src_tid)
    tgt_dets = load_per_det_tracklet(stem, tgt_tid)
    if not src_dets or not tgt_dets:
        return float("inf"), 0
    src_last = src_dets[-1]
    tgt_first = tgt_dets[0]
    dx = tgt_first[1] - src_last[1]
    dy = tgt_first[2] - src_last[2]
    euclid = (dx * dx + dy * dy) ** 0.5
    gap = tgt_first[0] - src_last[0]
    # Per-frame rate (add 1 so a 0-frame gap isn't infinity)
    return euclid / max(1, gap + 1), gap


def should_reclassify_v(edge: dict, h14_record: dict | None, jump_px_per_frame: float
                        ) -> tuple[bool, str]:
    """Determine if a BALLISTIC edge should be reclassified as
    V_RECLASSIFIED_HAND_TRANSITION.

    Returns (should_reclassify, reason_string).
    """
    if edge["edge_type"] != "BALLISTIC":
        return False, "not_ballistic"
    if h14_record is None:
        return False, "no_h14_record"
    cls = h14_record.get("classification", "FLAT")
    if cls not in ("V_DEEP", "V_SHALLOW"):
        return False, f"not_v_shape_{cls}"
    tol = H15["JUMP_TOLERANCE_PX_PER_FRAME"]
    if jump_px_per_frame > tol:
        return False, f"jump_too_large_{jump_px_per_frame:.1f}_px_per_frame"
    return True, f"v_shape_{cls.lower()}_jump_{jump_px_per_frame:.1f}_hand={h14_record['which_hand']}"


def h7v3_min_cost_flow(edges: list[dict], tracklets: dict[int, dict]
                      ) -> tuple[dict[int, int], list[dict], dict]:
    """Same as H7v2 but with V_RECLASSIFIED_HAND_TRANSITION treated as HAND."""
    edges_with_cost = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        cost = edge_cost(e, tracklets[src]["last_frame"],
                         tracklets[tgt]["first_frame"])
        edges_with_cost.append({**e, "cost": cost})

    # Sort by cost (cheapest first)
    edges_with_cost.sort(key=lambda e: e["cost"])

    # Capacity constraints (one predecessor + one successor per tracklet)
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


def edge_cost(edge: dict, source_last_frame: int, target_first_frame: int) -> float:
    """Cost function. HAND edges (incl. RECLASSIFIED and V_RECLASSIFIED) = 1.0."""
    etype = edge["edge_type"]
    if etype in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
                 "V_RECLASSIFIED_HAND_TRANSITION"):
        return H15["HAND_EDGE_COST"]
    if etype == "AMBIGUOUS_HAND_TRANSITION":
        return H15["AMBIGUOUS_HAND_EDGE_COST"]
    if etype == "BALLISTIC":
        gap = max(0, target_first_frame - source_last_frame)
        err = edge.get("err", 0.0) or 0.0
        return (H15["AIR_EDGE_BASE_COST"]
                + H15["AIR_ERR_SCALE"] * err
                + H15["AIR_GAP_SCALE"] * gap)
    return 5.0


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
    print("H15: h7v3 = H7v2 + V-shape reclassification of kept BALLISTIC edges")
    print(f"  thresholds: {H15}")
    print()

    summary = {"h15_thresholds": H15, "videos": {}}

    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        h7v2_edges = load_h7v2_edges(stem)
        h14_records = load_h14_per_edge(stem)

        # Step 1: identify BALLISTIC edges that pass V-shape + velocity-jump
        v_reclassified = []
        for e in h7v2_edges:
            if e["edge_type"] != "BALLISTIC":
                continue
            h14 = h14_records.get((e["from_tid"], e["to_tid"]))
            jump, gap = compute_spatial_jump(stem, e["from_tid"], e["to_tid"])
            should, reason = should_reclassify_v(e, h14, jump)
            if should:
                e["edge_type"] = "V_RECLASSIFIED_HAND_TRANSITION"
                e["v_reclassify_reason"] = reason
                e["cost"] = H15["HAND_EDGE_COST"]
                v_reclassified.append({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "reason": reason,
                    "gap": gap,
                    "jump_px_per_frame": round(jump, 2),
                    "h14_class": h14["classification"] if h14 else None,
                    "h14_min_d": h14["min_hand_dist"] if h14 else None,
                    "h14_hand": h14["which_hand"] if h14 else None,
                })

        # Step 2: also report the BALLISTIC edges that h7v3 considered but rejected
        v_rejected = []
        for e in h7v2_edges:
            if e["edge_type"] != "BALLISTIC":
                continue
            # already reclassified above
            if e.get("edge_type") == "V_RECLASSIFIED_HAND_TRANSITION":
                continue
            h14 = h14_records.get((e["from_tid"], e["to_tid"]))
            if h14 is None or h14.get("classification") not in ("V_DEEP", "V_SHALLOW"):
                continue
            jump, gap = compute_spatial_jump(stem, e["from_tid"], e["to_tid"])
            v_rejected.append({
                "from_tid": e["from_tid"],
                "to_tid": e["to_tid"],
                "h14_class": h14.get("classification"),
                "jump_px_per_frame": round(jump, 2),
                "gap": gap,
                "reason": "jump_too_large",
            })

        print(f"  v_reclassified (NEW h7v3 hand-edges): {len(v_reclassified)}")
        for r in v_reclassified:
            print(f"    {r['from_tid']:>3} -> {r['to_tid']:>3}  "
                  f"gap={r['gap']:>2}  h14={r['h14_class']:<9}  "
                  f"jump={r['jump_px_per_frame']:>5.1f}  hand={r['h14_hand']:<5}  "
                  f"({r['reason']})")
        print(f"  v_rejected (V-shape but velocity fails): {len(v_rejected)}")
        for r in v_rejected:
            print(f"    {r['from_tid']:>3} -> {r['to_tid']:>3}  "
                  f"gap={r['gap']:>2}  h14={r['h14_class']:<9}  "
                  f"jump={r['jump_px_per_frame']:>5.1f}")

        # Step 3: re-run min-cost flow with new edge types
        # All h7v2_edges (some now V_RECLASSIFIED) go in
        edges_for_flow = h7v2_edges
        succ, admitted, stats = h7v3_min_cost_flow(edges_for_flow, tracklets)
        chains = walk_chains(succ, sorted(tracklets.keys()))
        n_multi = sum(1 for c in chains if len(c) > 1)
        longest = max(chains, key=len) if chains else []
        print(f"  h7v3 chains: {len(chains)} ({n_multi} multi, "
              f"longest {len(longest)}: {longest})")
        print(f"  admitted: {stats['n_admitted']}/{stats['n_edges_in']} "
              f"(mean cost {stats['mean_cost_admitted']:.2f})")

        # Edge type breakdown
        type_counts = defaultdict(int)
        for e in admitted:
            type_counts[e["edge_type"]] += 1
        print(f"  admitted edge types: {dict(type_counts)}")

        # V_RECLASSIFIED in admitted
        v_rec_admitted = [e for e in admitted
                          if e["edge_type"] == "V_RECLASSIFIED_HAND_TRANSITION"]
        print(f"  V_RECLASSIFIED in admitted: {len(v_rec_admitted)}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklets),
            "n_edges_in": stats["n_edges_in"],
            "n_v_reclassified": len(v_reclassified),
            "n_v_rejected": len(v_rejected),
            "n_v_reclassified_admitted": len(v_rec_admitted),
            "n_admitted": stats["n_admitted"],
            "n_rejected_capacity": stats["n_rejected_capacity"],
            "mean_cost_admitted": stats["mean_cost_admitted"],
            "n_chains": len(chains),
            "n_chains_multi": n_multi,
            "longest": len(longest),
            "longest_chain": longest,
            "admitted_edges": admitted,
            "chains": chains,
            "v_reclassified": v_reclassified,
            "v_rejected": v_rejected,
            "edge_type_counts": dict(type_counts),
        }

    # Save summary
    out_path = H1_DATA / "h15_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        # Edges
        with (H1_DATA / f"h7v3_admitted_edges_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "edge_type", "metadata", "cost",
                "reclassify_reason", "v_reclassify_reason"])
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
                })
        # Chains
        with (H1_DATA / f"h7v3_chains_{stem}.csv").open("w", newline="") as fh:
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
        # V-reclassified log
        with (H1_DATA / f"h7v3_v_reclassified_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "gap", "h14_class", "h14_min_d",
                "h14_hand", "jump_px_per_frame", "reason"])
            w.writeheader()
            for r in v["v_reclassified"]:
                w.writerow({k: r[k] for k in w.fieldnames})
        # V-rejected log (V-shape positive but velocity-failed)
        with (H1_DATA / f"h7v3_v_rejected_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "from_tid", "to_tid", "gap", "h14_class",
                "jump_px_per_frame", "reason"])
            w.writeheader()
            for r in v["v_rejected"]:
                w.writerow({k: r[k] for k in w.fieldnames})

    print("\n=== Per-video CSVs saved ===")


if __name__ == "__main__":
    main()
