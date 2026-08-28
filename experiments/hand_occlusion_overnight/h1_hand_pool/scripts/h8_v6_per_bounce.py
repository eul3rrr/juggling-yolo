#!/usr/bin/env python3
"""H8 v6 - per-bounce parabolic fit on long tracklets.

Hypothesis: H8 v5's problem on YouTube long tracklets is
that the parabolic fit on the last 8 frames of source and
first 8 frames of target may be at different points in
the juggling cycle (rising vs falling). If we can identify
the parabolic arc boundaries within a long tracklet, the
tail/head fit would be more accurate.

Algorithm (per long tracklet):
1. Find local y-maxima (apexes) in the tracklet using a
   sliding window. An apex is a frame where y is locally
   maximal in a window of size 2*APEX_HALFWIN+1.
2. Identify parabolic arc boundaries: each arc is from one
   apex to the next (or to the start/end of the tracklet).
3. The "tail" of the tracklet is the last 8 frames of the
   last arc.
4. The "head" of the tracklet is the first 8 frames of the
   first arc.

For the physics check on an edge (src -> tgt):
- If src is long: use tail = last 8 frames of src's last arc.
- If tgt is long: use head = first 8 frames of tgt's first arc.
- Otherwise: use the v5 method (last/first 8 frames).

Thresholds (declared from physical geometry):
- APEX_HALFWIN = 6 frames
- ARC_N = 8 frames
- MIN_ARC_LEN = 5 frames
- MIN_TRACKLET_PTS = 5
- GRAVITY_PX_PER_FRAME2 = 0.5
- DISCONTINUITY_TOLERANCE = 8.0
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

H8V6 = {
    "APEX_HALFWIN": 6,
    "ARC_N": 8,
    "MIN_ARC_LEN": 5,
    "MIN_TRACKLET_PTS": 5,
    "GRAVITY_PX_PER_FRAME2": 0.5,
    "DISCONTINUITY_TOLERANCE": 8.0,
}


def load_tracklet_points(stem: str) -> dict[int, list[tuple[int, float, float]]]:
    out = {}
    candidates = [
        WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv",
        WORKTREE / "detections" / f"{stem}_yolo26s_botsort.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with path.open() as fh:
            by_tid = {}
            for r in csv.DictReader(fh):
                if "track_id" not in r:
                    continue
                tid = int(r["track_id"])
                by_tid.setdefault(tid, []).append((int(r["frame"]),
                                                   float(r["center_x"]),
                                                   float(r["center_y"])))
        if by_tid:
            for tid, pts in by_tid.items():
                pts.sort()
                out[tid] = pts
            break
    return out


def load_h237_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def find_apexes(pts, halfwin: int) -> list[int]:
    """Find frames where y is locally maximal in a window of
    2*halfwin+1 frames. Returns list of frame numbers at the apexes.

    A local maximum is a frame f such that y[f] >= y[f-k] and
    y[f] >= y[f+k] for all 1 <= k <= halfwin.
    """
    if len(pts) < 2 * halfwin + 1:
        return []
    apexes = []
    ys = [p[2] for p in pts]
    frames = [p[0] for p in pts]
    for i in range(halfwin, len(pts) - halfwin):
        is_apex = True
        for k in range(1, halfwin + 1):
            if ys[i - k] > ys[i] or ys[i + k] > ys[i]:
                is_apex = False
                break
        if is_apex:
            apexes.append(frames[i])
    return apexes


def split_into_arcs(pts, apex_frames: list[int]) -> list[list[tuple]]:
    """Split the tracklet into parabolic arcs. Each arc is the
    frames between consecutive apexes (or between the start/end
    of the tracklet and the nearest apex).
    """
    if not apex_frames:
        return [pts]
    arcs = []
    # First arc: from start to first apex
    first_apex_idx = next((i for i, p in enumerate(pts) if p[0] == apex_frames[0]), 0)
    if first_apex_idx > 0:
        arcs.append(pts[:first_apex_idx + 1])
    # Middle arcs: between consecutive apexes
    for i in range(len(apex_frames) - 1):
        a_frame = apex_frames[i]
        b_frame = apex_frames[i + 1]
        a_idx = next((j for j, p in enumerate(pts) if p[0] == a_frame), None)
        b_idx = next((j for j, p in enumerate(pts) if p[0] == b_frame), None)
        if a_idx is not None and b_idx is not None and b_idx > a_idx:
            arcs.append(pts[a_idx:b_idx + 1])
    # Last arc: from last apex to end
    last_apex_idx = next((i for i, p in enumerate(pts) if p[0] == apex_frames[-1]), len(pts) - 1)
    if last_apex_idx < len(pts) - 1:
        arcs.append(pts[last_apex_idx:])
    return arcs


def get_arc_tail(arc_pts: list, n: int) -> list:
    """Get the last n points of an arc (excluding the apex)."""
    # Skip the first point if it's the apex (it has zero velocity)
    if len(arc_pts) > 1:
        tail = arc_pts[1:]  # skip apex
    else:
        tail = arc_pts
    return tail[-n:] if len(tail) >= n else tail


def get_arc_head(arc_pts: list, n: int) -> list:
    """Get the first n points of an arc (excluding the apex)."""
    if len(arc_pts) > 1:
        head = arc_pts[:-1]  # skip apex
    else:
        head = arc_pts
    return head[:n] if len(head) >= n else head


def fit_parabola(frames, ys):
    """Fit y = a*(t-t0)^2 + b*(t-t0) + c by least squares.
    Returns (a, b, c, t0).
    """
    import numpy as np
    t = np.array(frames, dtype=float)
    y = np.array(ys, dtype=float)
    t0 = float(t.mean())
    tc = t - t0
    X = np.column_stack([tc * tc, tc, np.ones_like(tc)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, b, c = [float(x) for x in coef]
    return a, b, c, t0


def parabolic_vy_at(a, b, t0, t):
    return 2 * a * (t - t0) + b


def check_edge(edge, tracklet_points):
    src = edge["from_tid"]
    tgt = edge["to_tid"]
    src_pts = tracklet_points.get(src, [])
    tgt_pts = tracklet_points.get(tgt, [])

    if edge["edge_type"] != "BALLISTIC":
        return {**edge, "physics_status": "N/A_HAND",
                "src_vy_parabolic": 0.0, "tgt_vy_parabolic": 0.0,
                "predicted_tgt_vy": 0.0, "velocity_discontinuity": 0.0}

    src_n = len(src_pts)
    tgt_n = len(tgt_pts)
    if src_n < H8V6["MIN_TRACKLET_PTS"] or tgt_n < H8V6["MIN_TRACKLET_PTS"]:
        return {**edge, "physics_status": "INSUFFICIENT_DATA",
                "src_vy_parabolic": 0.0, "tgt_vy_parabolic": 0.0,
                "predicted_tgt_vy": 0.0, "velocity_discontinuity": 0.0}

    n = H8V6["ARC_N"]

    # Detect apexes and split into arcs (for long tracklets)
    src_apexes = find_apexes(src_pts, H8V6["APEX_HALFWIN"])
    tgt_apexes = find_apexes(tgt_pts, H8V6["APEX_HALFWIN"])
    src_arcs = split_into_arcs(src_pts, src_apexes)
    tgt_arcs = split_into_arcs(tgt_pts, tgt_apexes)

    # Use last arc's tail for source, first arc's head for target
    src_use = get_arc_tail(src_arcs[-1], n) if src_arcs else src_pts[-n:]
    tgt_use = get_arc_head(tgt_arcs[0], n) if tgt_arcs else tgt_pts[:n]

    if len(src_use) < 3 or len(tgt_use) < 3:
        return {**edge, "physics_status": "INSUFFICIENT_DATA",
                "src_vy_parabolic": 0.0, "tgt_vy_parabolic": 0.0,
                "predicted_tgt_vy": 0.0, "velocity_discontinuity": 0.0}

    src_frames = [p[0] for p in src_use]
    src_ys = [p[2] for p in src_use]
    a_s, b_s, _, t0_s = fit_parabola(src_frames, src_ys)
    src_vy = parabolic_vy_at(a_s, b_s, t0_s, src_frames[-1])

    tgt_frames = [p[0] for p in tgt_use]
    tgt_ys = [p[2] for p in tgt_use]
    a_t, b_t, _, t0_t = fit_parabola(tgt_frames, tgt_ys)
    tgt_vy = parabolic_vy_at(a_t, b_t, t0_t, tgt_frames[0])

    gap = tgt_frames[0] - src_frames[-1]
    gap_for_pred = max(gap, 1)
    predicted_tgt_vy = src_vy + H8V6["GRAVITY_PX_PER_FRAME2"] * gap_for_pred
    v_disc = abs(tgt_vy - predicted_tgt_vy)
    is_violating = v_disc > H8V6["DISCONTINUITY_TOLERANCE"]
    return {**edge, "physics_status": "VIOLATING" if is_violating else "OK",
            "src_vy_parabolic": src_vy, "tgt_vy_parabolic": tgt_vy,
            "predicted_tgt_vy": predicted_tgt_vy,
            "velocity_discontinuity": v_disc,
            "src_n_apexes": len(src_apexes), "tgt_n_apexes": len(tgt_apexes),
            "src_n_arcs": len(src_arcs), "tgt_n_arcs": len(tgt_arcs),
            "src_n_used": len(src_use), "tgt_n_used": len(tgt_use),
            "gap_frames": gap,
            "src_n_pts": src_n, "tgt_n_pts": tgt_n}


def main():
    summary = {"h8v6_thresholds": H8V6, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklet_points = load_tracklet_points(stem)
        edges = load_h237_edges(stem)
        print(f"  tracklets: {len(tracklet_points)}")
        print(f"  H7 edges: {len(edges)}")

        results = []
        for e in edges:
            r = check_edge(e, tracklet_points)
            results.append(r)

        n_air = sum(1 for r in results if r["edge_type"] == "BALLISTIC")
        n_air_ok = sum(1 for r in results
                       if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "OK")
        n_air_violating = sum(1 for r in results
                              if r["edge_type"] == "BALLISTIC"
                              and r["physics_status"] == "VIOLATING")
        n_air_insuff = sum(1 for r in results
                           if r["edge_type"] == "BALLISTIC"
                           and r["physics_status"] == "INSUFFICIENT_DATA")
        print(f"  air edges: {n_air} (OK={n_air_ok}, VIOLATING={n_air_violating}, "
              f"INSUFFICIENT={n_air_insuff})")
        if n_air_violating > 0 and n_air_violating <= 30:
            print(f"  VIOLATING air edges (per-bounce parabolic):")
            for r in results:
                if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "VIOLATING":
                    print(f"    {r['from_tid']} -> {r['to_tid']}  "
                          f"src_n={r['src_n_pts']} ({r.get('src_n_arcs',1)} arcs, "
                          f"{r.get('src_n_apexes',0)} apexes), "
                          f"tgt_n={r['tgt_n_pts']} ({r.get('tgt_n_arcs',1)} arcs, "
                          f"{r.get('tgt_n_apexes',0)} apexes), "
                          f"src_vy={r['src_vy_parabolic']:.1f}, "
                          f"tgt_vy={r['tgt_vy_parabolic']:.1f}, "
                          f"disc={r['velocity_discontinuity']:.1f}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_air": n_air,
            "n_air_ok": n_air_ok,
            "n_air_violating": n_air_violating,
            "n_air_insufficient": n_air_insuff,
            "results": results,
        }

    out_path = H1_DATA / "h8_v6_per_bounce_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
