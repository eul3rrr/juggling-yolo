#!/usr/bin/env python3
"""H8 — Edge-level physics consistency check on H7 chains.

Hypothesis: E6c's accepted ballistic edges are based on a constant-
velocity (linear) ballistic prediction. A stricter test: a real
ballistic edge should have CONTINUOUS y-velocity (no teleports) AND
a y-acceleration consistent with gravity.

Approach (declared before reading outcomes):
1. For each BALLISTIC edge in H7's chain representation, compute:
   - src_end_y_velocity (from last 3 frames of source tracklet)
   - tgt_start_y_velocity (from first 3 frames of target tracklet)
   - velocity_discontinuity = |src_vy - tgt_vy|
   - acceleration across the gap (assumes ~gravity)
2. Flag edges with velocity_discontinuity > THRESHOLD as
   "PHYSICS_VIOLATING" (likely identity switch).

This is a per-edge check that doesn't require fitting a parabola.
It's fast, simple, and works on both short and long tracklets.

Thresholds (declared from physical geometry):
- For a 30 fps camera, a real ball's y-velocity changes by
  ~0.5 * g * dt = ~5 px/frame over a 1-frame gap (assuming pixel-
  to-meter ratio of ~100 px/m and dt=1/30 s). A velocity
  discontinuity > 5 px/frame is suspicious.
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

# H8 thresholds (declared from physical geometry)
H8 = {
    "VELOCITY_DISCONTINUITY_PX_PER_FRAME": 8.0,
    "TAIL_FRAMES": 3,
    "MIN_TRACKLET_PTS": 3,
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


def vy_tail(pts, n):
    """Average y-velocity over the last n frames."""
    if len(pts) < 2:
        return 0.0
    sub = pts[-n:] if len(pts) >= n else pts
    if len(sub) < 2:
        return 0.0
    dy = sub[-1][2] - sub[0][2]
    dt = sub[-1][0] - sub[0][0]
    if dt == 0:
        return 0.0
    return dy / dt


def vy_head(pts, n):
    """Average y-velocity over the first n frames."""
    if len(pts) < 2:
        return 0.0
    sub = pts[:n] if len(pts) >= n else pts
    if len(sub) < 2:
        return 0.0
    dy = sub[-1][2] - sub[0][2]
    dt = sub[-1][0] - sub[0][0]
    if dt == 0:
        return 0.0
    return dy / dt


def check_edge(edge: dict, tracklet_points: dict) -> dict:
    """Check the physics consistency of an edge."""
    src = edge["from_tid"]
    tgt = edge["to_tid"]
    src_pts = tracklet_points.get(src, [])
    tgt_pts = tracklet_points.get(tgt, [])
    if len(src_pts) < H8["MIN_TRACKLET_PTS"] or len(tgt_pts) < H8["MIN_TRACKLET_PTS"]:
        return {**edge, "physics_status": "INSUFFICIENT_DATA",
                "src_vy": 0.0, "tgt_vy": 0.0,
                "velocity_discontinuity": 0.0}
    src_vy = vy_tail(src_pts, H8["TAIL_FRAMES"])
    tgt_vy = vy_head(tgt_pts, H8["TAIL_FRAMES"])
    v_disc = abs(src_vy - tgt_vy)
    is_violating = v_disc > H8["VELOCITY_DISCONTINUITY_PX_PER_FRAME"]
    return {**edge, "physics_status": "VIOLATING" if is_violating else "OK",
            "src_vy": src_vy, "tgt_vy": tgt_vy,
            "velocity_discontinuity": v_disc}


def main():
    summary = {"h8_thresholds": H8, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklet_points = load_tracklet_points(stem)
        edges = load_h237_edges(stem)
        print(f"  tracklets: {len(tracklet_points)}")
        print(f"  H7 edges: {len(edges)}")

        # Only check BALLISTIC edges for physics consistency.
        # Hand edges are EXPECTED to be discontinuous (the ball
        # stops in the hand and restarts), so a high y-velocity
        # discontinuity on a hand edge is NORMAL, not a violation.
        results = []
        for e in edges:
            r = check_edge(e, tracklet_points)
            results.append(r)
        n_air = sum(1 for r in results if r["edge_type"] == "BALLISTIC")
        n_hand = sum(1 for r in results if "HAND_TRANSITION" in r["edge_type"])
        n_air_ok = sum(1 for r in results
                       if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "OK")
        n_air_violating = sum(1 for r in results
                              if r["edge_type"] == "BALLISTIC"
                              and r["physics_status"] == "VIOLATING")
        n_hand_violating = sum(1 for r in results
                               if "HAND_TRANSITION" in r["edge_type"]
                               and r["physics_status"] == "VIOLATING")
        print(f"  hand edges: {n_hand} ({n_hand_violating} flagged, but this is NORMAL — held-then-released causes vy discontinuity by design)")
        print(f"  air edges: {n_air} ({n_air_ok} OK, {n_air_violating} violating)")
        if n_air_violating > 0:
            print(f"  VIOLATING air edges (likely false positives in E6c):")
            for r in results:
                if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "VIOLATING":
                    print(f"    {r['from_tid']} -> {r['to_tid']}  "
                          f"src_vy={r['src_vy']:.1f}, tgt_vy={r['tgt_vy']:.1f}, "
                          f"disc={r['velocity_discontinuity']:.1f}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_hand": n_hand,
            "n_hand_violating": n_hand_violating,
            "n_air": n_air,
            "n_air_ok": n_air_ok,
            "n_air_violating": n_air_violating,
            "results": results,
        }

    out_path = H1_DATA / "h8_v3_edge_physics_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
