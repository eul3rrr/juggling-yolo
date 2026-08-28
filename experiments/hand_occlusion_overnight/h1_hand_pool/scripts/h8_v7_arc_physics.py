#!/usr/bin/env python3
"""H8 v7 - per-bounce segmentation of long tracklets via y-velocity sign changes.

H8 v6's apex detection (APEX_HALFWIN=6) was too coarse: it only finds
major apexes via local y-max, but within each parabolic arc the ball
can have multiple y oscillations (especially during catch-throw motion).

A more robust segmentation: detect y-velocity sign changes. At each
apex, vy goes from + to - (or vice versa). A zero-crossing of vy
demarks a parabola boundary.

Algorithm:
  1. Compute vy at each point (smoothed dy/dt over ±K frames).
  2. Find zero-crossings (sign changes) in vy.
  3. Each segment between zero-crossings is one parabolic arc.
  4. For each edge between two arcs (A→B), check physics:
     - Predict vy at end of arc A using constant-gravity extrapolation.
     - Predict vy at start of arc B using parabolic fit.
     - Compare; large discontinuity => identity switch.
  5. For H7 chains, we need to map arc boundaries to chain edges:
     - If the air edge in H7 connects tracklet X (source) to tracklet Y
       (target), we look at:
       - Source's LAST arc: tail's vy_predicted at end of arc.
       - Target's FIRST arc: head's vy_predicted at start of arc.
     - If both arcs are present, the physics check uses the arc-pair.

Hypothesis: per-bounce segmentation via sign changes will give better
arc-isolated physics signals than v6's apex detection. The result
should be more identity-switch catches on the long-tracklet-heavy
YouTube video (where v5 fails).
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

# Thresholds (declared from physical geometry, not from manual labels)
K = 2  # smoothing half-window for vy
GRAVITY_PX_PER_FRAME2 = 0.5
DISCONTINUITY_TOLERANCE = 8.0  # px/frame
MIN_ARC_N = 4  # minimum points per arc to fit a parabola
MIN_TRACKLET_PTS = 5  # skip very short tracklets


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


def compute_vy(points: list, K: int) -> list:
    """Return per-point smoothed vy (px/frame).

    For each point, vy is the mean of (dy/dt) over the K frames before
    and K frames after (if available).
    """
    n = len(points)
    vy = [0.0] * n
    for i in range(n):
        f_i, _, y_i = points[i]
        sum_dy = 0.0
        sum_dt = 0
        for j in range(max(0, i - K), min(n, i + K + 1)):
            if j == i:
                continue
            f_j, _, y_j = points[j]
            sum_dy += y_j - y_i
            sum_dt += f_j - f_i
        if sum_dt != 0:
            vy[i] = sum_dy / sum_dt
    return vy


def find_arc_boundaries(vy: list, points: list) -> list:
    """Find arc boundary indices where vy sign changes.

    Returns list of (start_idx, end_idx) for each arc, where indices
    are into points/vy arrays.
    """
    if not vy:
        return []
    arcs = []
    cur_start = 0
    prev_sign = 1 if vy[0] > 0 else (-1 if vy[0] < 0 else 0)
    for i in range(1, len(vy)):
        cur_sign = 1 if vy[i] > 0 else (-1 if vy[i] < 0 else 0)
        if prev_sign != 0 and cur_sign != 0 and cur_sign != prev_sign:
            # Sign change - boundary
            if i - cur_start >= MIN_ARC_N:
                arcs.append((cur_start, i - 1))
            cur_start = i
        if cur_sign != 0:
            prev_sign = cur_sign
    if len(vy) - cur_start >= MIN_ARC_N:
        arcs.append((cur_start, len(vy) - 1))
    # Also handle leading/trailing zero-sign portions
    return arcs


def fit_parabola_arc(points: list, arc: tuple) -> dict:
    """Fit y = 0.5*g*t^2 + v0*t + y0 to arc; return fit parameters.

    Returns dict with keys: g, v0, y0, n_pts.
    """
    s, e = arc
    arc_pts = points[s:e + 1]
    if len(arc_pts) < 3:
        return {"g": 0.0, "v0": 0.0, "y0": 0.0, "n_pts": len(arc_pts),
                "fit_residual": 1e9}
    # Use f0 as time origin
    f0 = arc_pts[0][0]
    ts = [p[0] - f0 for p in arc_pts]
    ys = [p[2] for p in arc_pts]
    n = len(ts)
    # Least squares: y = a + b*t + c*t^2
    # (a = y0, b = v0, c = 0.5*g)
    sum_t = sum(ts)
    sum_t2 = sum(t * t for t in ts)
    sum_t3 = sum(t * t * t for t in ts)
    sum_t4 = sum(t ** 4 for t in ts)
    sum_y = sum(ys)
    sum_ty = sum(t * y for t, y in zip(ts, ys))
    sum_t2y = sum(t * t * y for t, y in zip(ts, ys))
    # 3x3 normal equations
    M = [
        [n, sum_t, sum_t2],
        [sum_t, sum_t2, sum_t3],
        [sum_t2, sum_t3, sum_t4],
    ]
    rhs = [sum_y, sum_ty, sum_t2y]
    # Solve by Cramer's rule
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
    # Residual
    res = 0.0
    for t, y in zip(ts, ys):
        y_pred = a + b * t + c * t * t
        res += (y - y_pred) ** 2
    return {"y0": a, "v0": b, "g": 2 * c, "n_pts": n,
            "fit_residual": res / n}


def predict_vy_at(arc: dict, f_target: int, f0: int) -> float:
    """Predict vy at frame f_target using arc's parabolic fit."""
    return arc["v0"] + arc["g"] * (f_target - f0)


def physics_check_v7(tid_src: int, points_src: list, arcs_src: list,
                      tid_tgt: int, points_tgt: list, arcs_tgt: list,
                      edge: dict) -> dict:
    """Physics check for an H7 air edge using arc-based segmentation.

    Uses:
      - Source tracklet's LAST arc: predict vy at source's last frame.
      - Target tracklet's FIRST arc: predict vy at target's first frame.
      - These are the values AT the air gap; physical continuity means
        they should be close (within DISCONTINUITY_TOLERANCE).
    """
    if not arcs_src or not arcs_tgt:
        return {"verdict": "INSUFFICIENT", "reason": "no arcs",
                "src_vy_pred": None, "tgt_vy_pred": None}
    last_arc_src = arcs_src[-1]
    first_arc_tgt = arcs_tgt[0]
    fit_src = fit_parabola_arc(points_src, last_arc_src)
    fit_tgt = fit_parabola_arc(points_tgt, first_arc_tgt)
    if fit_src["n_pts"] < MIN_ARC_N or fit_tgt["n_pts"] < MIN_ARC_N:
        return {"verdict": "INSUFFICIENT", "reason": "short arcs",
                "src_vy_pred": None, "tgt_vy_pred": None}
    f_src_end = points_src[last_arc_src[1]][0]
    f0_src = points_src[last_arc_src[0]][0]
    f_tgt_start = points_tgt[first_arc_tgt[0]][0]
    f0_tgt = points_tgt[first_arc_tgt[0]][0]
    src_vy_pred = predict_vy_at(fit_src, f_src_end, f0_src)
    tgt_vy_pred = predict_vy_at(fit_tgt, f_tgt_start, f0_tgt)
    # Constant-gravity extrapolation across the gap
    gap = f_tgt_start - f_src_end
    if gap > 0:
        src_vy_at_tgt = src_vy_pred + GRAVITY_PX_PER_FRAME2 * gap
    else:
        src_vy_at_tgt = src_vy_pred
    diff = abs(src_vy_at_tgt - tgt_vy_pred)
    verdict = "VIOLATING" if diff > DISCONTINUITY_TOLERANCE else "OK"
    return {
        "verdict": verdict,
        "src_vy_pred": round(src_vy_pred, 2),
        "tgt_vy_pred": round(tgt_vy_pred, 2),
        "src_vy_at_tgt": round(src_vy_at_tgt, 2),
        "discontinuity": round(diff, 2),
        "src_arc_n_pts": fit_src["n_pts"],
        "tgt_arc_n_pts": fit_tgt["n_pts"],
        "src_g": round(fit_src["g"], 3),
        "tgt_g": round(fit_tgt["g"], 3),
        "gap_frames": gap,
        "fit_residual_src": round(fit_src["fit_residual"], 2),
        "fit_residual_tgt": round(fit_tgt["fit_residual"], 2),
    }


def load_h7_chains(stem: str) -> list:
    """Return list of {chain_id, tids, edges: [{from, to, type}]}."""
    path = H1_DATA / f"h7_admitted_edges_{stem}.csv"
    edges = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["edge_type"] == "BALLISTIC":
                edges.append({
                    "from": int(r["from_tid"]),
                    "to": int(r["to_tid"]),
                    "type": "BALLISTIC",
                })
    # Group by chain
    from collections import defaultdict as dd
    adj = dd(list)
    for e in edges:
        adj[e["from"]].append(e["to"])
    # Find connected components
    visited = set()
    chains = []
    for start in list(adj.keys()):
        if start in visited:
            continue
        comp = []
        stack = [start]
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            comp.append(n)
            for nx in adj[n]:
                if nx not in visited:
                    stack.append(nx)
        comp.sort()
        chains.append({"tids": comp, "edges": edges})
    return chains


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H8 v7 arc-based physics) ===")
        tracklets = load_tracklet_points(stem)
        # Per-tracklet vy and arcs
        per_track = {}
        for tid, pts in tracklets.items():
            if len(pts) < MIN_TRACKLET_PTS:
                per_track[tid] = {"vy": [], "arcs": [], "n_pts": len(pts),
                                  "points": pts}
                continue
            vy = compute_vy(pts, K)
            arcs = find_arc_boundaries(vy, pts)
            per_track[tid] = {"vy": vy, "arcs": arcs, "n_pts": len(pts),
                              "points": pts}
        # Statistics
        n_arcs_dist = defaultdict(int)
        for tid, info in per_track.items():
            n_arcs_dist[len(info["arcs"])] += 1
        print(f"  Tracklet arc-count distribution (n_arcs: n_tracklets):")
        for n_arcs in sorted(n_arcs_dist):
            print(f"    {n_arcs} arcs: {n_arcs_dist[n_arcs]} tracklets")
        # Per-tracklet g fit (mean over arcs)
        gs = []
        for tid, info in per_track.items():
            for arc in info["arcs"]:
                fit = fit_parabola_arc(info["points"], arc)
                if 0.1 < fit["g"] < 5.0:  # plausible gravity
                    gs.append(fit["g"])
        if gs:
            print(f"  Gravity distribution (per-arc): mean={statistics.mean(gs):.2f}, "
                  f"median={statistics.median(gs):.2f}, "
                  f"std={statistics.stdev(gs):.2f}, n={len(gs)}")
            print(f"  Quoted gravity: {GRAVITY_PX_PER_FRAME2}")
        # H7 chain evaluation
        chains = load_h7_chains(stem)
        # Build air-edge set
        air_edges = set()
        for c in chains:
            for e in c["edges"]:
                if e["type"] == "BALLISTIC":
                    air_edges.add((e["from"], e["to"]))
        # Run physics check on each air edge
        edge_results = []
        n_ok = 0
        n_viol = 0
        n_insuff = 0
        for src, tgt in air_edges:
            if src not in per_track or tgt not in per_track:
                continue
            res = physics_check_v7(
                src, per_track[src]["points"], per_track[src]["arcs"],
                tgt, per_track[tgt]["points"], per_track[tgt]["arcs"],
                {"from": src, "to": tgt})
            res["src_tid"] = src
            res["tgt_tid"] = tgt
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
        out_path = H1_DATA / f"h8_v7_arc_physics_{stem}.csv"
        with out_path.open("w", newline="") as fh:
            if edge_results:
                # Build union of all keys
                all_keys = set()
                for r in edge_results:
                    all_keys.update(r.keys())
                fieldnames = ["src_tid", "tgt_tid", "verdict", "reason",
                              "src_vy_pred", "tgt_vy_pred", "src_vy_at_tgt",
                              "discontinuity", "src_arc_n_pts",
                              "tgt_arc_n_pts", "src_g", "tgt_g",
                              "gap_frames", "fit_residual_src",
                              "fit_residual_tgt"]
                # Append any unexpected keys at end
                for k in sorted(all_keys):
                    if k not in fieldnames:
                        fieldnames.append(k)
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
            "gravity_mean": float(statistics.mean(gs)) if gs else None,
            "gravity_median": float(statistics.median(gs)) if gs else None,
            "gravity_quoted": GRAVITY_PX_PER_FRAME2,
        }
    out = H1_DATA / "h8_v7_arc_physics_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
