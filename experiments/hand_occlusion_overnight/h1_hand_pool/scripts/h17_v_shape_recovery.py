#!/usr/bin/env python3
"""H17: V-shape recovery for v4d-rejected links + V-shape search with strict filter.

HYPOTHESIS:
  H14 found 4 hidden catch-throws on identical by checking V-shape on
  h7v2 BALLISTIC edges. H15v2 reclassified them.

  H17 hypothesis: there are MORE V-shape catch-throws that the chain
  pipeline missed, particularly:
  1. v4d-rejected links (35->40 identical, 15->25 youtube) - low slope
     but possibly real catch-throws
  2. E6c-candidate edges NOT admitted by H7 (h7 discarded for cost reasons)
  3. Adjacent tracklet pairs that are NOT in any h7v2 edge (truly novel)

  Naive V-shape (240 positives) is too permissive. A STRICT V-shape that
  combines position + endpoint signature should be more discriminating.

  The strict filter:
  - V-shape positive (existing H14 rule)
  - AND: the source's end or target's start is within 108px of a hand
    (at least one endpoint must be at the hand)
  - AND: the V-apex is at a real catch moment (min_d < 50)
  - AND: the source's end_slope or target's start_slope is consistent
    with a catch/throw (using tracklet_features.csv)

  Expected: 35->40 should pass all strict filters (H12 v3 confirmed).
  Other candidates that pass should be inspected.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H17_OUT = H1_DIR / "contact_sheets_h17"
H17_OUT.mkdir(parents=True, exist_ok=True)

H17_THRESHOLDS = {
    "TAIL_FRAMES": 6,
    "HEAD_FRAMES": 6,
    "GAP_INTERP_FRAMES": 5,
    "HAND_REACH_PX": 108,
    "V_DEEP_MIN_PX": 50,
    "V_DEEP_RATIO": 1.5,
    "V_SHALLOW_MIN_PX": 100,
    "V_SHALLOW_RATIO": 1.3,
    "MAX_GAP_FOR_VSHAPE_FRAMES": 30,
    "MIN_TRACKLET_LEN": 3,
    # Strict filter additions:
    "STRICT_ENDPOINT_MAX_DIST_PX": 108,  # at least one endpoint must be at hand
    "STRICT_MIN_SLOPE": 1.0,              # the catching/throw slope must be at least 1.0 px/frame
}

# Data sources
V4D_LINKS_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"
V4D_REJECTED_PATH = H1_DATA / "rejected_links_v4_v4d_throw7_full.csv"
E6C_STITCH_PATHS = {
    "identical_balls_trick_000_018":
        WORKTREE / "detections" / "identical_balls_trick_000_018_norfair_dt50_hc5_accepted_stitches.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        WORKTREE / "detections" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_norfair_dt50_hc5_accepted_stitches.csv",
}
H7V2_EDGES_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v2_admitted_edges_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v2_admitted_edges_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
TRACKLET_FEATURES_PATH = H1_DATA / "tracklet_features.csv"


def load_tracklet_features() -> dict:
    """Read tracklet_features.csv into a dict by (stem, tid)."""
    out = {}
    with TRACKLET_FEATURES_PATH.open() as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["tid"]))
            def _f(v):
                try:
                    return float(v) if v != "" else None
                except (ValueError, TypeError):
                    return None
            out[key] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "end_dist": _f(r["end_dist"]),
                "end_side": r["end_side"] or None,
                "start_dist": _f(r["start_dist"]),
                "start_side": r["start_side"] or None,
                "end_slope": _f(r["end_slope"]),
                "start_slope": _f(r["start_slope"]),
            }
    return out


def load_per_det_tracklet(stem: str, tid: int) -> list[tuple]:
    """Return list of (frame, x, y, conf) for a tracklet from Norfair CSV."""
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


def load_wrist_frames(stem: str) -> dict:
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                lx = float(r["left_wrist_x"]); ly = float(r["left_wrist_y"])
                rx = float(r["right_wrist_x"]); ry = float(r["right_wrist_y"])
                out[fr] = {"left": (lx, ly), "right": (rx, ry)}
            except (ValueError, KeyError):
                continue
    return out


def find_closest_wrist(wrist_frames: dict, frame: int, max_diff: int = 5):
    if not wrist_frames:
        return None
    if frame in wrist_frames:
        return wrist_frames[frame]
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def interpolate_gap(src_tail, tgt_head, gap):
    """Interpolate N points between src_tail[-1] and tgt_head[0]."""
    if not src_tail or not tgt_head:
        return []
    src_x, src_y = src_tail[-1][1], src_tail[-1][2]
    tgt_x, tgt_y = tgt_head[0][1], tgt_head[0][2]
    n = H17_THRESHOLDS["GAP_INTERP_FRAMES"]
    pts = []
    for i in range(1, n + 1):
        t = i / (n + 1)
        x = src_x + t * (tgt_x - src_x)
        y = src_y + t * (tgt_y - src_y)
        pts.append((x, y))
    return pts


def v_shape_check(edge, wrist_frames):
    """Compute V-shape signature. Returns None if no wrist data."""
    stem = edge["stem"]
    src_dets = load_per_det_tracklet(stem, edge["from_tid"])
    tgt_dets = load_per_det_tracklet(stem, edge["to_tid"])
    if not src_dets or not tgt_dets:
        return None
    if len(src_dets) < H17_THRESHOLDS["MIN_TRACKLET_LEN"]:
        return None
    if len(tgt_dets) < H17_THRESHOLDS["MIN_TRACKLET_LEN"]:
        return None

    tail_n = H17_THRESHOLDS["TAIL_FRAMES"]
    head_n = H17_THRESHOLDS["HEAD_FRAMES"]
    src_tail = src_dets[-tail_n:]
    tgt_head = tgt_dets[:head_n]

    gap_pts = interpolate_gap(src_tail, tgt_head, edge.get("gap", 0))

    trajectory = []
    for (fr, x, y, c) in src_tail:
        trajectory.append((fr, x, y))
    for (i, (x, y)) in enumerate(gap_pts):
        approx_fr = src_tail[-1][0] + (i + 1) * max(1, edge.get("gap", 1) // (len(gap_pts) + 1))
        trajectory.append((approx_fr, x, y))
    for (fr, x, y, c) in tgt_head:
        trajectory.append((fr, x, y))

    min_dist_l = min_dist_r = float("inf")
    max_dist_l = max_dist_r = 0.0
    apex_l = apex_r = None
    for (fr, x, y) in trajectory:
        w = find_closest_wrist(wrist_frames, fr, max_diff=5)
        if w is None:
            continue
        if "left" in w:
            lx, ly = w["left"]
            d = ((x - lx) ** 2 + (y - ly) ** 2) ** 0.5
            if d < min_dist_l:
                min_dist_l = d
                apex_l = (x, y, fr)
            if d > max_dist_l:
                max_dist_l = d
        if "right" in w:
            rx, ry = w["right"]
            d = ((x - rx) ** 2 + (y - ry) ** 2) ** 0.5
            if d < min_dist_r:
                min_dist_r = d
                apex_r = (x, y, fr)
            if d > max_dist_r:
                max_dist_r = d

    if min_dist_l == float("inf") and min_dist_r == float("inf"):
        return None
    if min_dist_l <= min_dist_r:
        which = "left"
        min_d = min_dist_l
        max_d = max_dist_l
        apex = apex_l
    else:
        which = "right"
        min_d = min_dist_r
        max_d = max_dist_r
        apex = apex_r

    if max_d == 0:
        ratio = 0
    else:
        ratio = max_d / min_d if min_d > 0 else 0

    if min_d < H17_THRESHOLDS["V_DEEP_MIN_PX"] and ratio >= H17_THRESHOLDS["V_DEEP_RATIO"]:
        cls = "V_DEEP"
    elif min_d < H17_THRESHOLDS["V_SHALLOW_MIN_PX"] and ratio >= H17_THRESHOLDS["V_SHALLOW_RATIO"]:
        cls = "V_SHALLOW"
    else:
        cls = "FLAT"

    return {
        "min_hand_dist": min_d,
        "max_hand_dist": max_d,
        "ratio": ratio,
        "which_hand": which,
        "apex": apex,
        "classification": cls,
        "trajectory": trajectory,
    }


def strict_filter(edge, v_result, features):
    """Apply strict endpoint filter: at least one endpoint at hand,
    AND the V-apex hand matches the endpoint hand (so it's the
    SAME hand involved in the catch+throw).

    Returns True if all strict filters pass.
    """
    stem = edge["stem"]
    src_key = (stem, edge["from_tid"])
    tgt_key = (stem, edge["to_tid"])
    src_feat = features.get(src_key, {})
    tgt_feat = features.get(tgt_key, {})

    # Check 1: at least one endpoint within STRICT_ENDPOINT_MAX_DIST_PX
    end_dist = src_feat.get("end_dist")
    start_dist = tgt_feat.get("start_dist")
    end_side = src_feat.get("end_side")
    start_side = tgt_feat.get("start_side")
    end_at_hand = (end_dist is not None
                   and end_dist <= H17_THRESHOLDS["STRICT_ENDPOINT_MAX_DIST_PX"]
                   and end_side == v_result["which_hand"])
    start_at_hand = (start_dist is not None
                     and start_dist <= H17_THRESHOLDS["STRICT_ENDPOINT_MAX_DIST_PX"]
                     and start_side == v_result["which_hand"])
    if not (end_at_hand or start_at_hand):
        return False, "NO_ENDPOINT_AT_HAND"

    # Check 2: the relevant endpoint's slope has a catch/throw signature
    # catch: end_slope < -STRICT_MIN_SLOPE (distance decreasing)
    # throw: start_slope > STRICT_MIN_SLOPE (distance increasing)
    end_slope = src_feat.get("end_slope")
    start_slope = tgt_feat.get("start_slope")
    catch_ok = (end_at_hand and end_slope is not None and end_slope < -H17_THRESHOLDS["STRICT_MIN_SLOPE"])
    throw_ok = (start_at_hand and start_slope is not None and start_slope > H17_THRESHOLDS["STRICT_MIN_SLOPE"])
    if not (catch_ok or throw_ok):
        return False, "NO_CATCH_THROW_SLOPE"

    return True, "STRICT_PASS"


def get_v4d_rejected() -> list[dict]:
    """Read v4d-rejected links (the 2 candidates: 35->40, 15->25)."""
    out = []
    with V4D_REJECTED_PATH.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "stem": r["stem"],
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "from_frame": int(r["from_frame"]),
                "to_frame": int(r["to_frame"]),
                "gap": int(r["to_frame"]) - int(r["from_frame"]),
                "source": "v4d_rejected",
            })
    return out


def get_e6c_candidates() -> list[dict]:
    out = []
    seen = set()
    for stem, path in E6C_STITCH_PATHS.items():
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                src = int(r["source_tracklet"])
                tgt = int(r["candidate_tracklet"])
                if (stem, src, tgt) in seen:
                    continue
                seen.add((stem, src, tgt))
                err = float(r["trajectory_fit_error"])
                out.append({
                    "stem": stem,
                    "from_tid": src,
                    "to_tid": tgt,
                    "err": err,
                    "accepted": int(r["accepted"]),
                    "source": "e6c_stitch",
                })
    return out


def get_h7v2_admitted_pairs() -> set:
    out = set()
    for stem, path in H7V2_EDGES_PATHS.items():
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                out.add((stem, int(r["from_tid"]), int(r["to_tid"])))
    return out


def evaluate_candidate_set(name, candidates, features, h7v2_admitted):
    """Run V-shape + strict filter on a set of candidates."""
    results = []
    by_stem = defaultdict(list)
    for e in candidates:
        by_stem[e["stem"]].append(e)

    for stem in sorted(by_stem.keys()):
        wrist_frames = load_wrist_frames(stem)
        for edge in by_stem[stem]:
            # Get gap from features if not set
            if "gap" not in edge or edge["gap"] is None:
                src_key = (stem, edge["from_tid"])
                tgt_key = (stem, edge["to_tid"])
                if src_key not in features or tgt_key not in features:
                    continue
                edge["gap"] = features[tgt_key]["first_frame"] - features[src_key]["last_frame"]
            if edge["gap"] <= 0 or edge["gap"] > H17_THRESHOLDS["MAX_GAP_FOR_VSHAPE_FRAMES"]:
                continue
            v = v_shape_check(edge, wrist_frames)
            if v is None:
                continue
            strict_pass, strict_reason = strict_filter(edge, v, features)
            in_h7v2 = (stem, edge["from_tid"], edge["to_tid"]) in h7v2_admitted
            results.append({
                "edge": edge,
                "kind": name,
                "vshape": v["classification"],
                "min_hand_dist": v["min_hand_dist"],
                "ratio": v["ratio"],
                "which_hand": v["which_hand"],
                "apex": v["apex"],
                "strict_pass": strict_pass,
                "strict_reason": strict_reason,
                "in_h7v2": in_h7v2,
            })
    return results


def main():
    print("H17: V-shape recovery with STRICT filter")
    print(f"  thresholds: {H17_THRESHOLDS}")
    print()

    features = load_tracklet_features()
    h7v2_admitted = get_h7v2_admitted_pairs()

    # ---- Part 1: v4d-rejected links ----
    print("=== Part 1: v4d-rejected links ===")
    v4d_rejected = get_v4d_rejected()
    p1 = evaluate_candidate_set("v4d_rejected", v4d_rejected, features, h7v2_admitted)
    for r in p1:
        e = r["edge"]
        print(f"  {e['from_tid']:>3}->{e['to_tid']:<3} gap={e['gap']:>2}  "
              f"v={r['vshape']:<8} min_d={r['min_hand_dist']:>5.1f} ratio={r['ratio']:.2f} "
              f"hand={r['which_hand']:<5} strict={r['strict_pass']} ({r['strict_reason']})  "
              f"in_h7v2={r['in_h7v2']}")

    # ---- Part 2: E6c candidates NOT in h7v2 ----
    print()
    print("=== Part 2: E6c candidates NOT in h7v2 ===")
    e6c_candidates = get_e6c_candidates()
    e6c_not_in_h7v2 = [e for e in e6c_candidates
                       if (e["stem"], e["from_tid"], e["to_tid"]) not in h7v2_admitted]
    p2 = evaluate_candidate_set("e6c_not_in_h7v2", e6c_not_in_h7v2, features, h7v2_admitted)
    strict_p2 = [r for r in p2 if r["strict_pass"]]
    print(f"  Total E6c-not-in-h7v2 V-shape positives: {sum(1 for r in p2 if r['vshape'] != 'FLAT')}")
    print(f"  STRICT V-shape positives: {len(strict_p2)}")
    for r in strict_p2:
        e = r["edge"]
        print(f"  STRICT  {e['from_tid']:>3}->{e['to_tid']:<3} gap={e['gap']:>2}  "
              f"v={r['vshape']:<8} min_d={r['min_hand_dist']:>5.1f} ratio={r['ratio']:.2f} "
              f"hand={r['which_hand']:<5} err={e.get('err', 0):.1f}")

    # ---- Part 3: Adjacent tracklet pairs NOT in h7v2 (truly novel) ----
    print()
    print("=== Part 3: Adjacent tracklet pairs (NOT in h7v2) ===")
    by_stem_features = defaultdict(list)
    for (stem, tid), feat in features.items():
        by_stem_features[stem].append((tid, feat))

    p3_candidates = []
    for stem in sorted(by_stem_features.keys()):
        tids_sorted = sorted(by_stem_features[stem], key=lambda x: x[1]["first_frame"])
        for i, (src_tid, src_feat) in enumerate(tids_sorted):
            for j, (tgt_tid, tgt_feat) in enumerate(tids_sorted):
                if j <= i:
                    continue
                if (stem, src_tid, tgt_tid) in h7v2_admitted:
                    continue
                gap = tgt_feat["first_frame"] - src_feat["last_frame"]
                if gap <= 0 or gap > H17_THRESHOLDS["MAX_GAP_FOR_VSHAPE_FRAMES"]:
                    continue
                if tgt_feat["first_frame"] < src_feat["first_frame"]:
                    continue
                p3_candidates.append({
                    "stem": stem,
                    "from_tid": src_tid,
                    "to_tid": tgt_tid,
                    "gap": gap,
                    "source": "adjacent_search",
                })

    p3 = evaluate_candidate_set("adjacent", p3_candidates, features, h7v2_admitted)
    strict_p3 = [r for r in p3 if r["strict_pass"]]
    print(f"  Total adjacent V-shape positives: {sum(1 for r in p3 if r['vshape'] != 'FLAT')}")
    print(f"  STRICT V-shape positives: {len(strict_p3)}")
    for r in strict_p3:
        e = r["edge"]
        print(f"  STRICT  {e['from_tid']:>3}->{e['to_tid']:<3} gap={e['gap']:>2}  "
              f"v={r['vshape']:<8} min_d={r['min_hand_dist']:>5.1f} ratio={r['ratio']:.2f} "
              f"hand={r['which_hand']:<5}")

    # ---- Part 4: Sanity check on h7v2 BALLISTIC edges (control) ----
    print()
    print("=== Part 4: Sanity check - h7v2 BALLISTIC edges (control) ===")
    p4_candidates = []
    for stem, path in H7V2_EDGES_PATHS.items():
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                if r["edge_type"] != "BALLISTIC":
                    continue
                p4_candidates.append({
                    "stem": stem,
                    "from_tid": int(r["from_tid"]),
                    "to_tid": int(r["to_tid"]),
                    "gap": int(r["to_frame"]) - int(r["from_frame"]) if "to_frame" in r else 0,
                    "source": "h7v2_ballistic_control",
                })
    p4 = evaluate_candidate_set("h7v2_ballistic_control", p4_candidates, features, h7v2_admitted)
    strict_p4 = [r for r in p4 if r["strict_pass"]]
    print(f"  h7v2 BALLISTIC strict positives: {len(strict_p4)}")
    for r in strict_p4:
        e = r["edge"]
        print(f"  BALL  {e['from_tid']:>3}->{e['to_tid']:<3} gap={e['gap']:>2}  "
              f"v={r['vshape']:<8} min_d={r['min_hand_dist']:>5.1f} ratio={r['ratio']:.2f} "
              f"hand={r['which_hand']:<5}")

    # ---- Summary ----
    all_results = p1 + p2 + p3 + p4
    print()
    print("=== Summary ===")
    by_kind_strict = defaultdict(int)
    by_kind_vshape = defaultdict(lambda: defaultdict(int))
    for r in all_results:
        by_kind_strict[(r["kind"], r["strict_pass"])] += 1
        by_kind_vshape[r["kind"]][r["vshape"]] += 1
    print("  by kind, V-shape distribution:")
    for kind, vshape in by_kind_vshape.items():
        print(f"    {kind}: {dict(vshape)}")
    print(f"  STRICT positives by kind:")
    for kind in sorted(set(r["kind"] for r in all_results)):
        n_strict = sum(1 for r in all_results if r["kind"] == kind and r["strict_pass"])
        print(f"    {kind}: {n_strict}")

    # Save
    out = {
        "thresholds": H17_THRESHOLDS,
        "per_edge": [
            {
                "kind": r["kind"],
                "stem": r["edge"]["stem"],
                "from_tid": r["edge"]["from_tid"],
                "to_tid": r["edge"]["to_tid"],
                "gap": r["edge"].get("gap", 0),
                "vshape": r["vshape"],
                "min_hand_dist": round(r["min_hand_dist"], 2),
                "ratio": round(r["ratio"], 3),
                "which_hand": r["which_hand"],
                "apex_frame": r["apex"][2] if r["apex"] else None,
                "apex_x": round(r["apex"][0], 1) if r["apex"] else None,
                "apex_y": round(r["apex"][1], 1) if r["apex"] else None,
                "strict_pass": r["strict_pass"],
                "strict_reason": r["strict_reason"],
                "in_h7v2": r["in_h7v2"],
            }
            for r in all_results
        ],
    }
    out_path = H1_DATA / "h17_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved: {out_path}")
    print(f"  total edges analyzed: {len(all_results)}")

    # Save strict positives
    strict_all = [r for r in all_results if r["strict_pass"]]
    pos_path = H1_DATA / "h17_strict_v_shape_positives.csv"
    with pos_path.open("w", newline="") as fh:
        fields = [
            "kind", "stem", "from_tid", "to_tid", "gap",
            "vshape", "min_hand_dist", "ratio",
            "which_hand", "in_h7v2", "apex_frame", "apex_x", "apex_y",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in strict_all:
            e = r["edge"]
            w.writerow({
                "kind": r["kind"],
                "stem": e["stem"],
                "from_tid": e["from_tid"],
                "to_tid": e["to_tid"],
                "gap": e.get("gap", 0),
                "vshape": r["vshape"],
                "min_hand_dist": round(r["min_hand_dist"], 2),
                "ratio": round(r["ratio"], 3),
                "which_hand": r["which_hand"],
                "in_h7v2": r["in_h7v2"],
                "apex_frame": r["apex"][2] if r["apex"] else None,
                "apex_x": round(r["apex"][0], 1) if r["apex"] else None,
                "apex_y": round(r["apex"][1], 1) if r["apex"] else None,
            })
    print(f"  STRICT V-shape positives: {len(strict_all)} -> {pos_path}")


if __name__ == "__main__":
    main()
