#!/usr/bin/env python3
"""H14: V-shape trajectory check on h7v2 BALLISTIC edges.

Hypothesis: BALLISTIC edges that h7v2 KEPT (didn't reclassify) might
actually be hidden catch-throws that the strict h7v2 rule missed.

H7v2 reclassification requires:
  end_dist <= 108 AND end_slope < -1.0   (catch signature)
  OR start_dist <= 108 AND start_slope > 1.0   (throw signature)

A V-shape check is more permissive: it looks at the FULL source-tail
+ gap-interpolation + target-head trajectory and asks whether it
dips toward a hand and comes back out. A real catch-throw has this
V-shape signature; a true mid-air identity switch has a smoother
monotonic trajectory (the ball just keeps flying).

Algorithm:
1. For each h7v2 BALLISTIC edge (src, tgt), load the per-detection
   positions of src (last 6 frames) and tgt (first 6 frames).
2. Interpolate positions in the gap (linear time, mean y-velocity).
3. For each hand (left, right), compute the minimum hand-distance
   across the V-shaped trajectory.
4. Classify:
   - "V_DEEP" if min_hand_dist < 50 (close to hand) AND max-to-min
     ratio > 1.5 (came in from far away).
   - "V_SHALLOW" if min_hand_dist < 100 AND ratio > 1.3.
   - "FLAT" if neither.

Compare with h7v2_reclassified and v4d links as controls. If
BALLISTIC edges with V_DEEP / V_SHALLOW signature are visually real
catch-throws, then h7v2's strict rule is too narrow and H14 is a
recovery mechanism (replaces h7v2_kept_ballistic for some edges).

Contact sheets and visual QA for V_DEEP edges.
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
H14_OUT = H1_DIR / "contact_sheets_h14"
H14_OUT.mkdir(parents=True, exist_ok=True)

H14_THRESHOLDS = {
    "TAIL_FRAMES": 6,           # source tracklet's last N frames
    "HEAD_FRAMES": 6,           # target tracklet's first N frames
    "GAP_INTERP_FRAMES": 5,     # interpolated points in the gap
    "HAND_REACH_PX": 108,       # canonical hand reach (H1 v1)
    "V_DEEP_MIN_PX": 50,        # min hand-distance to classify as V_DEEP
    "V_DEEP_RATIO": 1.5,        # max_hand_dist / min_hand_dist ratio
    "V_SHALLOW_MIN_PX": 100,    # min hand-distance to classify as V_SHALLOW
    "V_SHALLOW_RATIO": 1.3,
    "NEAR_END_DIST_TOLERANCE": 5,  # accept end_dist up to 108+5 (h7v2 borderline)
}

# Data sources (reuse from h13)
V4D_LINKS_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"
H7V2_RECLASS_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v2_reclassified_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v2_reclassified_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
H7V2_EDGES_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v2_admitted_edges_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v2_admitted_edges_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
TRACKLET_FEATURES_PATH = H1_DATA / "tracklet_features.csv"


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


def get_h7v2_ballistic() -> list[dict]:
    """Get the BALLISTIC edges that h7v2 did NOT reclassify (kept_ballistic)."""
    out = []
    for stem, reclass_path in H7V2_RECLASS_PATHS.items():
        edges_path = H7V2_EDGES_PATHS.get(stem)
        if edges_path is None or not reclass_path.exists() or not edges_path.exists():
            continue
        reclass_pairs = set()
        with reclass_path.open() as fh:
            for r in csv.DictReader(fh):
                reclass_pairs.add((int(r["from_tid"]), int(r["to_tid"])))
        with edges_path.open() as fh:
            for r in csv.DictReader(fh):
                ftid = int(r["from_tid"])
                ttid = int(r["to_tid"])
                if (ftid, ttid) in reclass_pairs:
                    continue
                # The "kept" edges are HAND_TRANSITION (already classified
                # by v4d), AMBIGUOUS_HAND_TRANSITION, or BALLISTIC. We're
                # interested in the BALLISTIC ones (the genuine mid-air
                # edges that h7v2 didn't catch as catch-throws).
                if r["edge_type"] != "BALLISTIC":
                    continue
                out.append({
                    "stem": stem,
                    "from_tid": ftid,
                    "to_tid": ttid,
                    "edge_type": r["edge_type"],
                    "cost": float(r["cost"]),
                })
    return out


def get_h7v2_reclassified() -> list[dict]:
    out = []
    for stem, path in H7V2_RECLASS_PATHS.items():
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                m = re.search(r"side=(\w+)", r.get("reason", ""))
                hand = m.group(1) if m else "unknown"
                out.append({
                    "stem": stem,
                    "from_tid": int(r["from_tid"]),
                    "to_tid": int(r["to_tid"]),
                    "gap": int(r["gap"]),
                    "hand": hand,
                })
    return out


def get_v4d_links() -> list[dict]:
    out = []
    with V4D_LINKS_PATH.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "stem": r["stem"],
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "hand": r["hand"],
                "from_frame": int(r["from_frame"]),
                "to_frame": int(r["to_frame"]),
                "gap": int(r["to_frame"]) - int(r["from_frame"]),
            })
    return out


def interpolate_gap(src_tail, tgt_head, gap):
    """Return a list of (x, y) positions interpolated in the gap.
    src_tail: list of (frame, x, y) for source tracklet's last 6 frames
    tgt_head: list of (frame, x, y) for target tracklet's first 6 frames
    gap: number of frames between source.last_frame and target.first_frame
    """
    if not src_tail or not tgt_head:
        return []
    src_x, src_y = src_tail[-1][1], src_tail[-1][2]
    tgt_x, tgt_y = tgt_head[0][1], tgt_head[0][2]
    n = H14_THRESHOLDS["GAP_INTERP_FRAMES"]
    pts = []
    for i in range(1, n + 1):
        t = i / (n + 1)
        x = src_x + t * (tgt_x - src_x)
        y = src_y + t * (tgt_y - src_y)
        pts.append((x, y))
    return pts


def v_shape_check(edge, wrist_frames):
    """Compute the V-shape signature of an edge's trajectory.

    Returns a dict with:
    - min_hand_dist_left: min dist to left wrist across trajectory
    - min_hand_dist_right: min dist to right wrist
    - max_hand_dist_left: max dist
    - max_hand_dist_right: max dist
    - which_hand: which hand has the smaller min
    - classification: V_DEEP / V_SHALLOW / FLAT
    - apex: (x, y) of the V apex (closest point to a hand)
    - trajectory: list of (frame, x, y) for plotting
    """
    stem = edge["stem"]
    src_dets = load_per_det_tracklet(stem, edge["from_tid"])
    tgt_dets = load_per_det_tracklet(stem, edge["to_tid"])
    if not src_dets or not tgt_dets:
        return None

    tail_n = H14_THRESHOLDS["TAIL_FRAMES"]
    head_n = H14_THRESHOLDS["HEAD_FRAMES"]
    src_tail = src_dets[-tail_n:]   # (frame, x, y, conf)
    tgt_head = tgt_dets[:head_n]

    # Interpolation in the gap
    gap_pts = interpolate_gap(src_tail, tgt_head, edge.get("gap", 0))

    # Build full trajectory with frame stamps
    trajectory = []
    for (fr, x, y, c) in src_tail:
        trajectory.append((fr, x, y))
    for (i, (x, y)) in enumerate(gap_pts):
        # Approximate frame in the gap
        approx_fr = src_tail[-1][0] + (i + 1) * max(1, edge.get("gap", 1) // (len(gap_pts) + 1))
        trajectory.append((approx_fr, x, y))
    for (fr, x, y, c) in tgt_head:
        trajectory.append((fr, x, y))

    # For each hand, compute min/max hand distance across the trajectory
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

    # Choose hand with smaller min_dist
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

    if min_d < H14_THRESHOLDS["V_DEEP_MIN_PX"] and ratio >= H14_THRESHOLDS["V_DEEP_RATIO"]:
        cls = "V_DEEP"
    elif min_d < H14_THRESHOLDS["V_SHALLOW_MIN_PX"] and ratio >= H14_THRESHOLDS["V_SHALLOW_RATIO"]:
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


def main():
    print("H14: V-shape trajectory check on h7v2 BALLISTIC edges")
    print(f"  thresholds: {H14_THRESHOLDS}")
    print()

    ballistic = get_h7v2_ballistic()
    reclassified = get_h7v2_reclassified()
    v4d = get_v4d_links()
    print(f"  BALLISTIC kept: {len(ballistic)}")
    print(f"  h7v2_reclassified: {len(reclassified)}")
    print(f"  v4d: {len(v4d)}")
    print()

    # Group by stem
    by_stem_ballistic = defaultdict(list)
    for e in ballistic:
        by_stem_ballistic[e["stem"]].append(e)
    by_stem_reclass = defaultdict(list)
    for e in reclassified:
        by_stem_reclass[e["stem"]].append(e)
    by_stem_v4d = defaultdict(list)
    for e in v4d:
        by_stem_v4d[e["stem"]].append(e)

    all_results = []

    for stem in sorted(set(list(by_stem_ballistic) + list(by_stem_reclass) + list(by_stem_v4d))):
        print(f"\n=== {stem} ===")
        wrist_frames = load_wrist_frames(stem)

        # BALLISTIC (kept)
        n_ball = {"V_DEEP": 0, "V_SHALLOW": 0, "FLAT": 0, "skip": 0}
        for e in by_stem_ballistic.get(stem, []):
            v = v_shape_check(e, wrist_frames)
            if v is None:
                n_ball["skip"] += 1
                continue
            n_ball[v["classification"]] += 1
            result = {"edge": e, "kind": "ballistic", **v}
            all_results.append(result)
            print(f"  BALL  {e['from_tid']:>3}->{e['to_tid']:<3} gap={e.get('gap', 0):>2}  "
                  f"min_d={v['min_hand_dist']:>5.1f} max_d={v['max_hand_dist']:>5.1f} ratio={v['ratio']:.2f} "
                  f"hand={v['which_hand']:<5} class={v['classification']}")
        print(f"  BALL summary: {n_ball}")

        # RECLASSIFIED (control - should mostly be V_DEEP / V_SHALLOW)
        n_rec = {"V_DEEP": 0, "V_SHALLOW": 0, "FLAT": 0, "skip": 0}
        for e in by_stem_reclass.get(stem, []):
            v = v_shape_check(e, wrist_frames)
            if v is None:
                n_rec["skip"] += 1
                continue
            n_rec[v["classification"]] += 1
            result = {"edge": e, "kind": "reclassified", **v}
            all_results.append(result)
        print(f"  RECL summary: {n_rec}")

        # v4d (control - should mostly be V_DEEP / V_SHALLOW)
        n_v4d = {"V_DEEP": 0, "V_SHALLOW": 0, "FLAT": 0, "skip": 0}
        for e in by_stem_v4d.get(stem, []):
            v = v_shape_check(e, wrist_frames)
            if v is None:
                n_v4d["skip"] += 1
                continue
            n_v4d[v["classification"]] += 1
            result = {"edge": e, "kind": "v4d", **v}
            all_results.append(result)
        print(f"  v4d  summary: {n_v4d}")

    # Aggregate by group
    print("\n=== per-group V-shape summary ===")
    for kind in ["v4d", "reclassified", "ballistic"]:
        rs = [r for r in all_results if r["kind"] == kind]
        n_vd = sum(1 for r in rs if r["classification"] == "V_DEEP")
        n_vs = sum(1 for r in rs if r["classification"] == "V_SHALLOW")
        n_fl = sum(1 for r in rs if r["classification"] == "FLAT")
        n_sk = sum(1 for r in rs if r["classification"] not in ("V_DEEP", "V_SHALLOW", "FLAT"))
        if rs:
            mean_min = statistics.mean(r["min_hand_dist"] for r in rs)
            mean_max = statistics.mean(r["max_hand_dist"] for r in rs)
            mean_ratio = statistics.mean(r["ratio"] for r in rs)
        else:
            mean_min = mean_max = mean_ratio = 0
        print(f"  {kind:<14}: V_DEEP={n_vd:>3} V_SHALLOW={n_vs:>3} FLAT={n_fl:>3} skip={n_sk:>3}  "
              f"mean_min_d={mean_min:.1f} mean_max_d={mean_max:.1f} mean_ratio={mean_ratio:.2f}")

    # Save per-edge
    out = {
        "thresholds": H14_THRESHOLDS,
        "per_edge": [
            {
                "kind": r["kind"],
                "stem": r["edge"]["stem"],
                "from_tid": r["edge"]["from_tid"],
                "to_tid": r["edge"]["to_tid"],
                "gap": r["edge"].get("gap", 0),
                "min_hand_dist": round(r["min_hand_dist"], 2),
                "max_hand_dist": round(r["max_hand_dist"], 2),
                "ratio": round(r["ratio"], 3),
                "which_hand": r["which_hand"],
                "classification": r["classification"],
                "apex_frame": r["apex"][2] if r["apex"] else None,
                "apex_x": round(r["apex"][0], 1) if r["apex"] else None,
                "apex_y": round(r["apex"][1], 1) if r["apex"] else None,
            }
            for r in all_results
        ],
    }
    out_path = H1_DATA / "h14_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved: {out_path}")
    print(f"  total edges analyzed: {len(all_results)}")


if __name__ == "__main__":
    main()
