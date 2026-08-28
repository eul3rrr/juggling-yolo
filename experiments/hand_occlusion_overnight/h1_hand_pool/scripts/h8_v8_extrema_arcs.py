#!/usr/bin/env python3
"""H8 v8 - per-bounce segmentation via local extrema (peaks/valleys).

H8 v7's vy-sign-change segmentation was too coarse: with smoothing
K=2, vy never showed multiple sign changes within a long YouTube
tracklet, so 38/40 YouTube tracklets were detected as 1-arc.

v8 uses local extrema (peaks/valleys) in y with a min-distance
filter to detect bounces. A parabola is fit to each arc; physics
checks the velocity at adjacent arc boundaries (within tracklet)
AND across H7 air edges (between tracklets).

Hypothesis: proper extrema detection with min-distance=5 will
identify 3-5 arcs per long YouTube tracklet, giving v8 a
per-arc physics signal that v7 lacked. v8 should produce
non-trivial gravity estimates per arc and per-tracklet.
"""
from __future__ import annotations

import csv
import json
import statistics
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

# Thresholds (declared from physical geometry)
EXTREMA_MIN_DIST = 5  # frames between extrema (a single parabolic arc takes ~30 frames)
MIN_ARC_N = 4  # minimum points per arc to fit a parabola
MIN_TRACKLET_PTS = 8  # skip very short tracklets
GRAVITY_PX_PER_FRAME2 = 0.5
DISCONTINUITY_TOLERANCE = 8.0
PARABOLA_N_FOR_V5 = 8  # for cross-edge prediction, use last 8 frames of source


def load_tracklet_points(stem: str) -> dict:
    out = defaultdict(list)
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tid = int(r["track_id"])
            out[tid].append((int(r["frame"]), float(r["center_x"]),
                             float(r["center_y"])))
    for tid in out:
        out[tid].sort()
    return out


def find_extrema(points: list, min_dist: int) -> list:
    """Find local extrema (peaks AND valleys) in y with min-distance filter.

    Returns list of (idx, type) where type is "peak" or "valley".
    Both peaks and valleys are local extrema; we want both to delineate
    the parabolic-arc boundaries.
    """
    if len(points) < 2 * min_dist + 1:
        return []
    ys = [p[2] for p in points]
    extrema = []  # (idx, type)
    for i in range(min_dist, len(ys) - min_dist):
        # Check if local max
        is_max = all(ys[j] <= ys[i] for j in range(i - min_dist, i + min_dist + 1) if j != i)
        is_min = all(ys[j] >= ys[i] for j in range(i - min_dist, i + min_dist + 1) if j != i)
        if is_max:
            extrema.append((i, "peak"))
        elif is_min:
            extrema.append((i, "valley"))
    # Filter: keep only "true" peaks (where y is at local max) and "true" valleys
    # but also keep only extrema with min_dist between them
    # Alternative: enforce that extrema alternate peak-valley-peak...
    # For our purpose, just keep all of them; min_dist filter handles the
    # spurious ones.
    return extrema


def arcs_from_extrema(points: list, extrema: list) -> list:
    """Split tracklet into arcs using extrema as boundaries.

    Each arc is a list of (frame, x, y) points. Arcs span:
      - First arc: [0, first_extrema_idx)
      - Middle arcs: [extrema[i], extrema[i+1])
      - Last arc: [last_extrema_idx, len(points))
    """
    if not extrema:
        return [points] if len(points) >= MIN_ARC_N else []
    arcs = []
    # First arc
    if extrema[0][0] >= MIN_ARC_N:
        arcs.append(points[:extrema[0][0]])
    # Middle arcs
    for i in range(len(extrema) - 1):
        s = extrema[i][0]
        e = extrema[i + 1][0] + 1
        if e - s >= MIN_ARC_N:
            arcs.append(points[s:e])
    # Last arc
    if len(points) - 1 - extrema[-1][0] >= MIN_ARC_N:
        arcs.append(points[extrema[-1][0]:])
    return arcs


def fit_parabola(arc: list) -> dict:
    """Fit y = 0.5*g*t^2 + v0*t + y0 to arc; return fit parameters.

    Uses least-squares. Returns dict with keys: g, v0, y0, n_pts, fit_residual.
    """
    if len(arc) < 3:
        return {"g": 0.0, "v0": 0.0, "y0": 0.0, "n_pts": len(arc),
                "fit_residual": 1e9}
    f0 = arc[0][0]
    ts = [p[0] - f0 for p in arc]
    ys = [p[2] for p in arc]
    n = len(ts)
    sum_t = sum(ts)
    sum_t2 = sum(t * t for t in ts)
    sum_t3 = sum(t * t * t for t in ts)
    sum_t4 = sum(t ** 4 for t in ts)
    sum_y = sum(ys)
    sum_ty = sum(t * y for t, y in zip(ts, ys))
    sum_t2y = sum(t * t * y for t, y in zip(ts, ys))
    M = [
        [n, sum_t, sum_t2],
        [sum_t, sum_t2, sum_t3],
        [sum_t2, sum_t3, sum_t4],
    ]
    rhs = [sum_y, sum_ty, sum_t2y]
    def det3(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    D = det3(M)
    if abs(D) < 1e-9:
        return {"g": 0.0, "v0": 0.0, "y0": ys[0], "n_pts": n,
                "fit_residual": 1e9}
    def replace_col(m, col, v):
        out = [row[:] for row in m]
        for i in range(3):
            out[i][col] = v[i]
        return out
    a = det3(replace_col(M, 0, rhs)) / D
    b = det3(replace_col(M, 1, rhs)) / D
    c = det3(replace_col(M, 2, rhs)) / D
    res = 0.0
    for t, y in zip(ts, ys):
        y_pred = a + b * t + c * t * t
        res += (y - y_pred) ** 2
    return {"y0": a, "v0": b, "g": 2 * c, "n_pts": n,
            "fit_residual": res / n}


def predict_vy_at(arc: list, fit: dict, f_target: int) -> float:
    """Predict vy at frame f_target using arc's parabolic fit."""
    f0 = arc[0][0]
    return fit["v0"] + fit["g"] * (f_target - f0)


def load_h7_air_edges(stem: str) -> list:
    """Return list of (from_tid, to_tid) for BALLISTIC edges in H7 chains."""
    path = H1_DATA / f"h7_admitted_edges_{stem}.csv"
    edges = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["edge_type"] == "BALLISTIC":
                edges.append((int(r["from_tid"]), int(r["to_tid"])))
    return edges


def physics_check_v8(src_arcs: list, src_fits: list,
                      tgt_arcs: list, tgt_fits: list,
                      src_last_frame: int, tgt_first_frame: int) -> dict:
    """Physics check using the arc containing the connection point.

    For source: find the arc containing src_last_frame, predict vy
    at src_last_frame.
    For target: find the arc containing tgt_first_frame, predict vy
    at tgt_first_frame.

    The previous version always used the last arc of source and the
    first arc of target, which gave wrong results when the source
    tracklet has many extrema (long target tracklets) — the actual
    end-of-source is in the middle of the last arc, not at its end.
    """
    if not src_arcs or not tgt_arcs:
        return {"verdict": "INSUFFICIENT", "reason": "no arcs"}

    # Find the source arc that contains src_last_frame
    src_idx = None
    for i, arc in enumerate(src_arcs):
        if arc[0][0] <= src_last_frame <= arc[-1][0]:
            src_idx = i
            break
    if src_idx is None:
        # Fallback: use last arc
        src_idx = len(src_arcs) - 1

    # Find the target arc that contains tgt_first_frame
    tgt_idx = None
    for i, arc in enumerate(tgt_arcs):
        if arc[0][0] <= tgt_first_frame <= arc[-1][0]:
            tgt_idx = i
            break
    if tgt_idx is None:
        tgt_idx = 0

    src_arc = src_arcs[src_idx]
    tgt_arc = tgt_arcs[tgt_idx]
    src_fit = src_fits[src_idx]
    tgt_fit = tgt_fits[tgt_idx]
    if len(src_arc) < MIN_ARC_N or len(tgt_arc) < MIN_ARC_N:
        return {"verdict": "INSUFFICIENT", "reason": "short arcs"}
    if src_fit["n_pts"] < MIN_ARC_N or tgt_fit["n_pts"] < MIN_ARC_N:
        return {"verdict": "INSUFFICIENT", "reason": "short fit"}
    src_vy_at_src_end = predict_vy_at(src_arc, src_fit, src_last_frame)
    tgt_vy_at_tgt_start = predict_vy_at(tgt_arc, tgt_fit, tgt_first_frame)
    gap = tgt_first_frame - src_last_frame
    if gap > 0:
        src_vy_at_tgt = src_vy_at_src_end + GRAVITY_PX_PER_FRAME2 * gap
    else:
        src_vy_at_tgt = src_vy_at_src_end
    diff = abs(src_vy_at_tgt - tgt_vy_at_tgt_start)
    verdict = "VIOLATING" if diff > DISCONTINUITY_TOLERANCE else "OK"
    return {
        "verdict": verdict,
        "src_vy_pred": round(src_vy_at_src_end, 2),
        "tgt_vy_pred": round(tgt_vy_at_tgt_start, 2),
        "src_vy_at_tgt": round(src_vy_at_tgt, 2),
        "discontinuity": round(diff, 2),
        "src_arc_n_pts": src_fit["n_pts"],
        "tgt_arc_n_pts": tgt_fit["n_pts"],
        "src_g": round(src_fit["g"], 3),
        "tgt_g": round(tgt_fit["g"], 3),
        "gap_frames": gap,
        "fit_residual_src": round(src_fit["fit_residual"], 2),
        "fit_residual_tgt": round(tgt_fit["fit_residual"], 2),
    }


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H8 v8 extrema-arc physics) ===")
        tracklets = load_tracklet_points(stem)
        # Per-tracklet arcs and fits
        per_track = {}
        for tid, pts in tracklets.items():
            if len(pts) < MIN_TRACKLET_PTS:
                per_track[tid] = {"arcs": [], "fits": [], "n_pts": len(pts),
                                  "n_arcs": 0}
                continue
            extrema = find_extrema(pts, EXTREMA_MIN_DIST)
            arcs = arcs_from_extrema(pts, extrema)
            fits = [fit_parabola(a) for a in arcs]
            per_track[tid] = {"arcs": arcs, "fits": fits, "n_pts": len(pts),
                              "n_arcs": len(arcs)}
        # Statistics: n_arcs distribution
        n_arcs_dist = defaultdict(int)
        for tid, info in per_track.items():
            n_arcs_dist[info["n_arcs"]] += 1
        print(f"  Tracklet arc-count distribution (n_arcs: n_tracklets):")
        for n_arcs in sorted(n_arcs_dist):
            print(f"    {n_arcs} arcs: {n_arcs_dist[n_arcs]} tracklets")
        # Per-arc gravity distribution
        gs = []
        gs_clean = []  # 0.05 < g < 5.0
        for tid, info in per_track.items():
            for fit in info["fits"]:
                gs.append(fit["g"])
                if 0.05 < fit["g"] < 5.0:
                    gs_clean.append(fit["g"])
        if gs:
            print(f"  Gravity distribution (per-arc, all): mean={statistics.mean(gs):.3f}, "
                  f"median={statistics.median(gs):.3f}, std={statistics.stdev(gs):.3f}, n={len(gs)}")
            print(f"  Gravity distribution (per-arc, clean 0.05<g<5.0): mean={statistics.mean(gs_clean):.3f}, "
                  f"median={statistics.median(gs_clean):.3f}, std={statistics.stdev(gs_clean):.3f}, n={len(gs_clean)}")
            print(f"  Quoted gravity: {GRAVITY_PX_PER_FRAME2}")
        # Also: per-arc fit_residual distribution
        residuals = [fit["fit_residual"] for tid, info in per_track.items() for fit in info["fits"]]
        if residuals:
            print(f"  Fit residual distribution: mean={statistics.mean(residuals):.1f}, "
                  f"median={statistics.median(residuals):.1f}, n={len(residuals)}")
        # H7 chain evaluation
        air_edges = load_h7_air_edges(stem)
        edge_results = []
        n_ok = 0
        n_viol = 0
        n_insuff = 0
        for src_tid, tgt_tid in air_edges:
            if src_tid not in per_track or tgt_tid not in per_track:
                continue
            src_info = per_track[src_tid]
            tgt_info = per_track[tgt_tid]
            src_pts = tracklets[src_tid]
            tgt_pts = tracklets[tgt_tid]
            res = physics_check_v8(
                src_info["arcs"], src_info["fits"],
                tgt_info["arcs"], tgt_info["fits"],
                src_pts[-1][0], tgt_pts[0][0])
            res["src_tid"] = src_tid
            res["tgt_tid"] = tgt_tid
            edge_results.append(res)
            if res["verdict"] == "OK":
                n_ok += 1
            elif res["verdict"] == "VIOLATING":
                n_viol += 1
            else:
                n_insuff += 1
        print(f"  Air-edge physics check ({len(air_edges)} edges):")
        print(f"    OK: {n_ok}, VIOLATING: {n_viol}, INSUFFICIENT: {n_insuff}")
        # Persist
        out_path = H1_DATA / f"h8_v8_extrema_arcs_{stem}.csv"
        with out_path.open("w", newline="") as fh:
            if edge_results:
                fieldnames = ["src_tid", "tgt_tid", "verdict", "reason",
                              "src_vy_pred", "tgt_vy_pred", "src_vy_at_tgt",
                              "discontinuity", "src_arc_n_pts",
                              "tgt_arc_n_pts", "src_g", "tgt_g",
                              "gap_frames", "fit_residual_src",
                              "fit_residual_tgt"]
                w = csv.DictWriter(fh, fieldnames=fieldnames,
                                    extrasaction="ignore")
                w.writeheader()
                w.writerows(edge_results)
        print(f"  wrote: {out_path.name}")
        summary["videos"][stem] = {
            "n_tracklets": len(tracklets),
            "arc_count_distribution": dict(n_arcs_dist),
            "n_air_edges": len(air_edges),
            "n_ok": n_ok,
            "n_violating": n_viol,
            "n_insufficient": n_insuff,
            "gravity_mean_all": float(statistics.mean(gs)) if gs else None,
            "gravity_median_all": float(statistics.median(gs)) if gs else None,
            "gravity_mean_clean": float(statistics.mean(gs_clean)) if gs_clean else None,
            "gravity_median_clean": float(statistics.median(gs_clean)) if gs_clean else None,
            "gravity_quoted": GRAVITY_PX_PER_FRAME2,
            "residual_mean": float(statistics.mean(residuals)) if residuals else None,
            "residual_median": float(statistics.median(residuals)) if residuals else None,
        }
    out = H1_DATA / "h8_v8_extrema_arcs_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
