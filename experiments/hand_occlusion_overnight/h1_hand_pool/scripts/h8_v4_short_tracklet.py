#!/usr/bin/env python3
"""H8 v4 — short-tracklet-only H8 physics check.

Hypothesis: H8 v3 is unreliable on long tracklets because
the constant-velocity tail/head windows are contaminated by
the tracklet's multiple parabolic arcs. A real juggling ball's
ballistic segment is short (typically 10-30 frames between
apexes). Restricting H8 to tracklets with n_pts <= SHORT_N
should recover the physics signal on YouTube.

Thresholds (declared from physical geometry, not from manual labels):
  - SHORT_N = 30 frames
  - VELOCITY_DISCONTINUITY_PX_PER_FRAME = 8.0
  - TAIL_FRAMES = 3
  - MIN_TRACKLET_PTS = 3

Algorithm:
  - For each BALLISTIC edge, check if BOTH source and target
    tracklets have n_pts <= SHORT_N.
  - If yes: apply v3 y-velocity discontinuity check.
  - If no: SKIP (mark as "LONG_TRACKLET" status, not violating).
  - The v3 result is preserved for the H10 quality score
    (so long-tracklet edges still get a meaningful h8 score).

Compare v4 to v3:
  - n_air_evaluated (was n_air in v3)
  - n_air_OK, n_air_VIOLATING
  - chains that change status (v3 said VIOLATING, v4 says OK or LONG_TRACKLET)
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

H8V4 = {
    "VELOCITY_DISCONTINUITY_PX_PER_FRAME": 8.0,
    "TAIL_FRAMES": 3,
    "MIN_TRACKLET_PTS": 3,
    "SHORT_N": 30,  # only apply v3 check if both tracklets are short
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


def check_edge(edge: dict, tracklet_points: dict, short_n: int) -> dict:
    src = edge["from_tid"]
    tgt = edge["to_tid"]
    src_pts = tracklet_points.get(src, [])
    tgt_pts = tracklet_points.get(tgt, [])
    src_n = len(src_pts)
    tgt_n = len(tgt_pts)
    src_short = src_n <= short_n
    tgt_short = tgt_n <= short_n

    if edge["edge_type"] != "BALLISTIC":
        # Hand edges: not checked
        return {**edge, "physics_status": "N/A_HAND",
                "src_vy": 0.0, "tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_pts": src_n, "tgt_n_pts": tgt_n,
                "src_short": src_short, "tgt_short": tgt_short}

    if not (src_short and tgt_short):
        return {**edge, "physics_status": "LONG_TRACKLET",
                "src_vy": 0.0, "tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_pts": src_n, "tgt_n_pts": tgt_n,
                "src_short": src_short, "tgt_short": tgt_short}

    if src_n < H8V4["MIN_TRACKLET_PTS"] or tgt_n < H8V4["MIN_TRACKLET_PTS"]:
        return {**edge, "physics_status": "INSUFFICIENT_DATA",
                "src_vy": 0.0, "tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_pts": src_n, "tgt_n_pts": tgt_n,
                "src_short": src_short, "tgt_short": tgt_short}

    src_vy = vy_tail(src_pts, H8V4["TAIL_FRAMES"])
    tgt_vy = vy_head(tgt_pts, H8V4["TAIL_FRAMES"])
    v_disc = abs(src_vy - tgt_vy)
    is_violating = v_disc > H8V4["VELOCITY_DISCONTINUITY_PX_PER_FRAME"]
    return {**edge, "physics_status": "VIOLATING" if is_violating else "OK",
            "src_vy": src_vy, "tgt_vy": tgt_vy,
            "velocity_discontinuity": v_disc,
            "src_n_pts": src_n, "tgt_n_pts": tgt_n,
            "src_short": src_short, "tgt_short": tgt_short}


def main():
    # Load v3 results for comparison
    v3_summary_path = H1_DATA / "h8_v3_edge_physics_summary.json"
    v3_summary = json.loads(v3_summary_path.read_text()) if v3_summary_path.exists() else None

    summary = {"h8v4_thresholds": H8V4, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklet_points = load_tracklet_points(stem)
        edges = load_h237_edges(stem)
        print(f"  tracklets: {len(tracklet_points)}")
        print(f"  H7 edges: {len(edges)}")

        results = []
        for e in edges:
            r = check_edge(e, tracklet_points, H8V4["SHORT_N"])
            results.append(r)

        n_air = sum(1 for r in results if r["edge_type"] == "BALLISTIC")
        n_hand = sum(1 for r in results if "HAND_TRANSITION" in r["edge_type"])
        n_air_ok = sum(1 for r in results
                       if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "OK")
        n_air_violating = sum(1 for r in results
                              if r["edge_type"] == "BALLISTIC"
                              and r["physics_status"] == "VIOLATING")
        n_air_long = sum(1 for r in results
                         if r["edge_type"] == "BALLISTIC"
                         and r["physics_status"] == "LONG_TRACKLET")
        n_air_insuff = sum(1 for r in results
                           if r["edge_type"] == "BALLISTIC"
                           and r["physics_status"] == "INSUFFICIENT_DATA")
        print(f"  hand edges: {n_hand}")
        print(f"  air edges: {n_air} (OK={n_air_ok}, VIOLATING={n_air_violating}, "
              f"LONG_TRACKLET={n_air_long}, INSUFFICIENT={n_air_insuff})")
        if n_air_violating > 0:
            print(f"  VIOLATING air edges (short tracklets only):")
            for r in results:
                if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "VIOLATING":
                    print(f"    {r['from_tid']} -> {r['to_tid']}  "
                          f"src_n={r['src_n_pts']}, tgt_n={r['tgt_n_pts']}, "
                          f"src_vy={r['src_vy']:.1f}, tgt_vy={r['tgt_vy']:.1f}, "
                          f"disc={r['velocity_discontinuity']:.1f}")
        if n_air_long > 0:
            print(f"  LONG_TRACKLET air edges (skipped, n_pts > {H8V4['SHORT_N']}):")
            for r in results:
                if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "LONG_TRACKLET":
                    print(f"    {r['from_tid']} -> {r['to_tid']}  "
                          f"src_n={r['src_n_pts']}, tgt_n={r['tgt_n_pts']}")

        # Compare to v3
        if v3_summary is not None and stem in v3_summary.get("videos", {}):
            v3_results = v3_summary["videos"][stem]["results"]
            v3_status = {f"{r['from_tid']}->{r['to_tid']}": r["physics_status"]
                         for r in v3_results if r["edge_type"] == "BALLISTIC"}
            v4_status = {f"{r['from_tid']}->{r['to_tid']}": r["physics_status"]
                         for r in results if r["edge_type"] == "BALLISTIC"}
            n_changed = sum(1 for k in v4_status if v3_status.get(k) != v4_status.get(k))
            print(f"  v3 -> v4 status changes: {n_changed}/{len(v4_status)} air edges")
            for k in v4_status:
                v3s = v3_status.get(k, "MISSING")
                v4s = v4_status[k]
                if v3s != v4s:
                    print(f"    {k}: {v3s} -> {v4s}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_hand": n_hand,
            "n_air": n_air,
            "n_air_ok": n_air_ok,
            "n_air_violating": n_air_violating,
            "n_air_long": n_air_long,
            "n_air_insufficient": n_air_insuff,
            "results": results,
        }

    out_path = H1_DATA / "h8_v4_short_tracklet_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
