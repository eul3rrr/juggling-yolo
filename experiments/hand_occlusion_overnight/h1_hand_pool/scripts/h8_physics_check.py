#!/usr/bin/env python3
"""H8 — Physics consistency check on H7 chains.

Hypothesis: each H7 chain represents a single physical ball. The ball's
motion in mid-air is governed by gravity (constant downward acceleration
in image space, where the camera is fixed). A chain is "physics-consistent"
if the mid-air segments can be explained by a single projectile motion.

Specifically: for each chain, fit a parabolic trajectory
  y(t) = y0 + v0y * t + 0.5 * a * t^2
to the mid-air points (skip the held phase) and check the residual.
Chains with large residuals are flagged as "physics-violating" — they
may contain wrong tracklet associations.

Question: do the physics-violating chains correspond to the H2/H7
conflict cases? If so, physics consistency is a useful post-hoc
validation of chain quality.

Approach (declared before reading outcomes):
1. For each H7 chain, identify mid-air tracklets (those that are
   connected by BALLISTIC air-edges). Skip the held phases
   (immediately after HAND_TRANSITION or before AMBIGUOUS_HAND_TRANSITION).
2. Fit a 2nd-order polynomial y(t) to the mid-air points.
3. Compute residuals: actual y - predicted y.
4. Flag chains with residual > THRESHOLD.

This is a *validation* experiment, not a *recovery* experiment —
it doesn't generate new chains, it scores the existing ones.
"""
from __future__ import annotations

import csv
import json
import math
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

# H8 thresholds (declared from physical geometry)
# Gravity in image y: ~30 px/s^2 for a ball at 30 fps (real g=9.8 m/s^2,
# pixel-to-meter ratio depends on distance but in juggling the ball stays
# at roughly constant distance so the y acceleration is ~constant).
# A fit residual > 5 px is suspicious (more than half a ball radius).
H8 = {
    "RESIDUAL_THRESHOLD_PX": 5.0,
    "MIN_MID_AIR_POINTS": 5,
}


def load_tracklet_points(stem: str) -> dict[int, list[tuple[int, float, float]]]:
    """Load all tracklet points for a given stem.

    Returns {tid: [(frame, x, y), ...]}."""
    out = defaultdict(list)
    candidates = [
        WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv",
        WORKTREE / "detections" / f"{stem}_yolo26s_botsort.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                if "track_id" not in r:
                    continue
                tid = int(r["track_id"])
                out[tid].append((int(r["frame"]), float(r["center_x"]),
                                 float(r["center_y"])))
        if out:
            break
    for tid in out:
        out[tid].sort()
    return dict(out)


def load_h237_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            r["n_tracklets"] = int(r["n_tracklets"])
            r["n_hand_edges"] = int(r["n_hand_edges"])
            r["n_air_edges"] = int(r["n_air_edges"])
            r["n_h3_confirmed"] = int(r["n_h3_confirmed"])
            out.append(r)
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


def fit_parabola(points: list[tuple[int, float, float]]) -> tuple[float, float, float, float]:
    """Fit y = a*t^2 + b*t + c to the (t, y) data using least squares.

    Returns (a, b, c, mean_residual).
    """
    if len(points) < 3:
        return 0.0, 0.0, 0.0, float("inf")
    # Normalize t to start at 0 for numerical stability
    t0 = points[0][0]
    ts = [(p[0] - t0) for p in points]
    ys = [p[2] for p in points]
    # Solve least-squares
    # Build A matrix: [t^2, t, 1] for each row
    n = len(points)
    sum_t4 = sum(t**4 for t in ts)
    sum_t3 = sum(t**3 for t in ts)
    sum_t2 = sum(t**2 for t in ts)
    sum_t = sum(ts)
    sum_ty = sum(t * y for t, y in zip(ts, ys))
    sum_y = sum(ys)
    sum_t2y = sum(t**2 * y for t, y in zip(ts, ys))
    # 3x3 system
    # [sum_t4  sum_t3  sum_t2] [a]   [sum_t2y]
    # [sum_t3  sum_t2  sum_t ] [b] = [sum_ty ]
    # [sum_t2  sum_t   n     ] [c]   [sum_y  ]
    A = [[sum_t4, sum_t3, sum_t2],
         [sum_t3, sum_t2, sum_t],
         [sum_t2, sum_t, n]]
    b_vec = [sum_t2y, sum_ty, sum_y]
    # Solve via Gaussian elimination
    coeffs = solve_3x3(A, b_vec)
    a, b, c = coeffs
    # Compute residuals
    residuals = [abs(a * t**2 + b * t + c - y) for t, y in zip(ts, ys)]
    mean_res = sum(residuals) / len(residuals)
    return a, b, c, mean_res


def solve_3x3(A: list[list[float]], b: list[float]) -> list[float]:
    """Solve a 3x3 linear system A x = b via Gaussian elimination."""
    n = 3
    # Augment
    M = [A[i] + [b[i]] for i in range(n)]
    # Forward elimination with partial pivoting
    for i in range(n):
        # Find pivot
        max_val = abs(M[i][i])
        max_row = i
        for k in range(i + 1, n):
            if abs(M[k][i]) > max_val:
                max_val = abs(M[k][i])
                max_row = k
        M[i], M[max_row] = M[max_row], M[i]
        # Eliminate
        for k in range(i + 1, n):
            factor = M[k][i] / M[i][i]
            for j in range(i, n + 1):
                M[k][j] -= factor * M[i][j]
    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def physics_check_chain(chain: dict, edges: list[dict],
                        tracklet_points: dict[int, list]) -> dict:
    """Check physics consistency of a chain.

    For each chain, fit a parabola to each consecutive pair of
    mid-air tracklets connected by a BALLISTIC edge. Each parabolic
    arc represents one throw cycle. Chains with consistent per-edge
    parabolas (residual < threshold) are flagged as physics-consistent.
    """
    tids = chain["tids"]
    if len(tids) < 2:
        return {"chain_id": chain["chain_id"], "n_tracklets": len(tids),
                "physics_consistent": True, "note": "single tracklet"}

    # Identify mid-air EDGES (consecutive pairs connected by BALLISTIC)
    mid_air_pairs = []
    for i in range(len(tids) - 1):
        edge = next((e for e in edges
                     if e["from_tid"] == tids[i] and e["to_tid"] == tids[i + 1]),
                    None)
        if edge and edge["edge_type"] == "BALLISTIC":
            mid_air_pairs.append((tids[i], tids[i + 1]))

    if not mid_air_pairs:
        return {"chain_id": chain["chain_id"], "n_tracklets": len(tids),
                "physics_consistent": True, "note": "no mid-air edges"}

    # For each mid-air pair, gather points from both tracklets and fit
    # a parabola. Compute residual.
    per_edge_residuals = []
    per_edge_details = []
    for src, tgt in mid_air_pairs:
        src_pts = tracklet_points.get(src, [])
        tgt_pts = tracklet_points.get(tgt, [])
        if len(src_pts) < 2 or len(tgt_pts) < 2:
            continue
        # Use only the last few points of src and first few of tgt
        # (the ones near the edge).
        # Take last 3 of src, first 3 of tgt.
        n_tail = 3
        edge_pts = src_pts[-n_tail:] + tgt_pts[:n_tail]
        edge_pts.sort()
        if len(edge_pts) < H8["MIN_MID_AIR_POINTS"]:
            continue
        a, b, c, mean_res = fit_parabola(edge_pts)
        per_edge_residuals.append(mean_res)
        per_edge_details.append({
            "from_tid": src, "to_tid": tgt, "n_points": len(edge_pts),
            "a": a, "b": b, "c": c, "mean_residual_px": mean_res,
        })

    if not per_edge_residuals:
        return {"chain_id": chain["chain_id"], "n_tracklets": len(tids),
                "physics_consistent": True, "note": "no per-edge points"}

    mean_res = sum(per_edge_residuals) / len(per_edge_residuals)
    max_res = max(per_edge_residuals)
    is_consistent = max_res < H8["RESIDUAL_THRESHOLD_PX"]
    return {
        "chain_id": chain["chain_id"],
        "n_tracklets": len(tids),
        "tids": tids,
        "n_mid_air_edges": len(mid_air_pairs),
        "n_edges_fit": len(per_edge_residuals),
        "mean_residual_px": mean_res,
        "max_residual_px": max_res,
        "physics_consistent": is_consistent,
        "per_edge": per_edge_details,
    }


def main():
    summary = {"h8_thresholds": H8, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklet_points = load_tracklet_points(stem)
        chains = load_h237_chains(stem)
        edges = load_h237_edges(stem)
        print(f"  chains: {len(chains)}")
        print(f"  edges: {len(edges)}")

        # Physics check each chain
        results = []
        for c in chains:
            r = physics_check_chain(c, edges, tracklet_points)
            results.append(r)
        # Distribution
        n_consistent = sum(1 for r in results if r["physics_consistent"])
        n_inconsistent = sum(1 for r in results if not r["physics_consistent"])
        print(f"  physics-consistent chains: {n_consistent}")
        print(f"  physics-violating chains: {n_inconsistent}")
        if n_inconsistent > 0:
            print(f"  violating chains:")
            for r in results:
                if not r["physics_consistent"]:
                    print(f"    chain {r['chain_id']}: tids={r.get('tids',[])}, "
                          f"mean_residual={r.get('mean_residual_px', 'NA'):.2f}")

        # Summary stats
        consistent_res = [r["mean_residual_px"] for r in results
                          if r["physics_consistent"] and "mean_residual_px" in r]
        all_res = [r["mean_residual_px"] for r in results
                   if "mean_residual_px" in r]
        if all_res:
            print(f"  mean residual: {sum(all_res)/len(all_res):.2f} px")
            print(f"  max residual: {max(all_res):.2f} px")
        summary["videos"][stem] = {
            "video_key": video_key,
            "n_chains": len(chains),
            "n_consistent": n_consistent,
            "n_inconsistent": n_inconsistent,
            "results": results,
        }

    out_path = H1_DATA / "h8_physics_check_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
