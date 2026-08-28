#!/usr/bin/env python3
"""H8 v5 - parabolic-fit long-tracklet physics check.

Hypothesis: H8 v3's 3-frame mean velocity is noisy on long
tracklets because it averages over the local parabolic arc.
A parabolic fit to the last 8-12 frames of source and first
8-12 frames of target should give a better local velocity
estimate. Then, with constant-gravity extrapolation across
the gap, predict the expected y-velocity at the gap edges
and compare to the actual.

Thresholds (declared from physical geometry, not from manual labels):
  - PARABOLA_N = 8 (frames to use for parabolic fit)
  - MIN_TRACKLET_PTS = 5
  - GRAVITY_PX_PER_FRAME2 = 0.5 (image-space gravity, see below)
  - DISCONTINUITY_TOLERANCE = 8.0 px/frame

The image-space gravity depends on the camera's pixel-to-meter
ratio. For a juggling ball at ~1m distance, a 100 px/m ratio,
and dt=1/30s, image-space gravity is:
  g_image = g_real * dt^2 * pixel_ratio = 9.81 * (1/30)^2 * 100
         = 9.81 / 900 * 100 = 1.09 px/frame^2
With 2x safety margin (we don't know exact camera distance),
GRAVITY_PX_PER_FRAME2 = 0.5 is conservative. A real ball's
y-velocity changes by ~0.5 px/frame per frame due to gravity.

Algorithm:
  1. For each BALLISTIC edge:
     a. Get last N frames of source tracklet.
     b. Fit y = a * t^2 + b * t + c (parabola in time).
     c. Local vy at end: 2*a*t_end + b.
     d. Get first N frames of target tracklet.
     e. Fit parabola to those.
     f. Local vy at start: 2*a*t_start + b.
     g. Gap frames: gap = t_target_start - t_source_end.
     h. Predicted target_vy = source_vy + g_image * gap.
     i. Discontinuity = |actual_target_vy - predicted_target_vy|.
     j. Status = VIOLATING if disc > tol else OK.
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

H8V5 = {
    "PARABOLA_N": 8,
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


def fit_parabola(frames: list[int], ys: list[float]):
    """Fit y = a*(t-t0)^2 + b*(t-t0) + c by least squares.
    Returns (a, b, c, t0) where t0 is the centering offset.
    The derivative dy/dt at time t is 2*a*(t-t0) + b.
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


def parabolic_vy_at(a: float, b: float, t0: float, t: int) -> float:
    """dy/dt at time t for y = a*(t-t0)^2 + b*(t-t0) + c is 2*a*(t-t0) + b."""
    return 2 * a * (t - t0) + b


def check_edge(edge: dict, tracklet_points: dict) -> dict:
    src = edge["from_tid"]
    tgt = edge["to_tid"]
    src_pts = tracklet_points.get(src, [])
    tgt_pts = tracklet_points.get(tgt, [])

    if edge["edge_type"] != "BALLISTIC":
        return {**edge, "physics_status": "N/A_HAND",
                "src_vy_parabolic": 0.0, "tgt_vy_parabolic": 0.0,
                "predicted_tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_used": 0, "tgt_n_used": 0}

    src_n = len(src_pts)
    tgt_n = len(tgt_pts)
    if src_n < H8V5["MIN_TRACKLET_PTS"] or tgt_n < H8V5["MIN_TRACKLET_PTS"]:
        return {**edge, "physics_status": "INSUFFICIENT_DATA",
                "src_vy_parabolic": 0.0, "tgt_vy_parabolic": 0.0,
                "predicted_tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_used": 0, "tgt_n_used": 0}

    n = H8V5["PARABOLA_N"]
    src_tail = src_pts[-n:] if src_n >= n else src_pts
    tgt_head = tgt_pts[:n] if tgt_n >= n else tgt_pts

    src_frames = [p[0] for p in src_tail]
    src_ys = [p[2] for p in src_tail]
    a_s, b_s, _, t0_s = fit_parabola(src_frames, src_ys)
    src_vy = parabolic_vy_at(a_s, b_s, t0_s, src_frames[-1])

    tgt_frames = [p[0] for p in tgt_head]
    tgt_ys = [p[2] for p in tgt_head]
    a_t, b_t, _, t0_t = fit_parabola(tgt_frames, tgt_ys)
    tgt_vy = parabolic_vy_at(a_t, b_t, t0_t, tgt_frames[0])

    gap = tgt_frames[0] - src_frames[-1]
    # If gap < 0 (overlapping), use gap = 1 frame for prediction
    gap_for_pred = max(gap, 1)
    predicted_tgt_vy = src_vy + H8V5["GRAVITY_PX_PER_FRAME2"] * gap_for_pred

    v_disc = abs(tgt_vy - predicted_tgt_vy)
    is_violating = v_disc > H8V5["DISCONTINUITY_TOLERANCE"]
    return {**edge, "physics_status": "VIOLATING" if is_violating else "OK",
            "src_vy_parabolic": src_vy,
            "tgt_vy_parabolic": tgt_vy,
            "predicted_tgt_vy": predicted_tgt_vy,
            "velocity_discontinuity": v_disc,
            "src_n_used": len(src_tail), "tgt_n_used": len(tgt_head),
            "gap_frames": gap,
            "src_a": a_s, "src_b": b_s,
            "tgt_a": a_t, "tgt_b": b_t,
            "src_n_pts": src_n, "tgt_n_pts": tgt_n}


def main():
    summary = {"h8v5_thresholds": H8V5, "videos": {}}
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
        if n_air_violating > 0:
            print(f"  VIOLATING air edges (parabolic fit + gravity):")
            for r in results:
                if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "VIOLATING":
                    print(f"    {r['from_tid']} -> {r['to_tid']}  "
                          f"src_n={r['src_n_pts']}, tgt_n={r['tgt_n_pts']}, "
                          f"src_vy={r['src_vy_parabolic']:.1f}, "
                          f"tgt_vy={r['tgt_vy_parabolic']:.1f}, "
                          f"pred={r['predicted_tgt_vy']:.1f}, "
                          f"gap={r['gap_frames']}, "
                          f"disc={r['velocity_discontinuity']:.1f}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_air": n_air,
            "n_air_ok": n_air_ok,
            "n_air_violating": n_air_violating,
            "n_air_insufficient": n_air_insuff,
            "results": results,
        }

    out_path = H1_DATA / "h8_v5_parabolic_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
