#!/usr/bin/env python3
"""H8 — Per-tracklet parabolic fit as a chain quality signal.

Question: a real airborne ball follows a parabolic trajectory
(constant gravity in image y). If a tracklet's points fit a parabola
with low residual, it's likely a real airborne ball. If the residual
is high, the tracklet may be:
  - held (zero velocity, but a parabola can fit)
  - mid-catch or mid-throw (transitions between held and airborne)
  - noisy tracking

Approach (declared before reading outcomes):
1. For each tracklet, fit y(t) = a*t^2 + b*t + c to its points.
2. Compute the mean residual and the curvature a (gravity proxy).
3. Classify each tracklet:
  - "BALLISTIC" if residual < 5px AND |a| > 0.1 (real arc)
  - "HELD" if residual < 5px AND |a| < 0.1 (no acceleration)
  - "NOISY" otherwise
4. For each H7 chain, compute the fraction of BALLISTIC tracklets.
   A chain with high BALLISTIC fraction is likely a real chain.
   A chain with low BALLISTIC fraction may be a tracker artifact.

This is a per-tracklet classification, not a per-edge classification.
The classification can be used as a downstream quality signal on H7
chains.

Note: gravity in image y is ~0.5 * g_real * (1/pixel_per_meter)^2 *
(1/fps)^2. For a juggling ball at ~1m distance with a 30fps camera
and 1280x720 image, a reasonable a is around 0.5-2.0 px/frame^2.
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
H8 = {
    "RESIDUAL_THRESHOLD_PX": 5.0,  # >5px = noisy
    "MIN_A_ABS": 0.1,              # |a| < 0.1 = held (no acceleration)
    "MIN_POINTS": 5,               # need at least 5 points to fit
}


def solve_3x3(A, b):
    """Solve a 3x3 linear system A x = b via Gaussian elimination."""
    n = 3
    M = [A[i] + [b[i]] for i in range(n)]
    for i in range(n):
        max_val = abs(M[i][i])
        max_row = i
        for k in range(i + 1, n):
            if abs(M[k][i]) > max_val:
                max_val = abs(M[k][i])
                max_row = k
        M[i], M[max_row] = M[max_row], M[i]
        for k in range(i + 1, n):
            factor = M[k][i] / M[i][i]
            for j in range(i, n + 1):
                M[k][j] -= factor * M[i][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def fit_parabola(pts):
    """Fit y = a*t^2 + b*t + c. Returns (a, b, c, mean_residual)."""
    if len(pts) < 3:
        return 0.0, 0.0, 0.0, float("inf")
    t0 = pts[0][0]
    ts = [(p[0] - t0) for p in pts]
    ys = [p[2] for p in pts]
    n = len(pts)
    sum_t4 = sum(t**4 for t in ts)
    sum_t3 = sum(t**3 for t in ts)
    sum_t2 = sum(t**2 for t in ts)
    sum_t = sum(ts)
    sum_ty = sum(t * y for t, y in zip(ts, ys))
    sum_y = sum(ys)
    sum_t2y = sum(t**2 * y for t, y in zip(ts, ys))
    A = [[sum_t4, sum_t3, sum_t2],
         [sum_t3, sum_t2, sum_t],
         [sum_t2, sum_t, n]]
    b = [sum_t2y, sum_ty, sum_y]
    a, b_, c = solve_3x3(A, b)
    residuals = [abs(a * t**2 + b_ * t + c - y) for t, y in zip(ts, ys)]
    mean_res = sum(residuals) / n
    return a, b_, c, mean_res


def load_tracklet_points(stem: str) -> dict[int, list[tuple[int, float, float]]]:
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


def classify_tracklet(pts) -> dict:
    """Classify a tracklet as BALLISTIC, HELD, or NOISY."""
    if len(pts) < H8["MIN_POINTS"]:
        return {"classification": "TOO_FEW_POINTS", "n_pts": len(pts)}
    a, b, c, mean_res = fit_parabola(pts)
    is_low_res = mean_res < H8["RESIDUAL_THRESHOLD_PX"]
    is_held = abs(a) < H8["MIN_A_ABS"]
    if is_low_res and is_held:
        cls = "HELD"
    elif is_low_res and not is_held:
        cls = "BALLISTIC"
    else:
        cls = "NOISY"
    return {
        "classification": cls,
        "n_pts": len(pts),
        "a": a,
        "b": b,
        "c": c,
        "mean_residual_px": mean_res,
    }


def main():
    summary = {"h8_thresholds": H8, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklet_points = load_tracklet_points(stem)
        chains = load_h237_chains(stem)
        print(f"  tracklets: {len(tracklet_points)}")
        print(f"  chains: {len(chains)}")

        # Per-tracklet classification
        classifications = {}
        for tid, pts in tracklet_points.items():
            classifications[tid] = classify_tracklet(pts)
        cls_counts = defaultdict(int)
        for tid, c in classifications.items():
            cls_counts[c["classification"]] += 1
        print(f"  per-tracklet classification:")
        for k, v in cls_counts.items():
            print(f"    {k}: {v}")

        # Per-chain: fraction of BALLISTIC tracklets
        chain_results = []
        for c in chains:
            tids = c["tids"]
            cls_list = [classifications.get(t, {}).get("classification", "MISSING")
                        for t in tids]
            n_ballistic = sum(1 for x in cls_list if x == "BALLISTIC")
            n_held = sum(1 for x in cls_list if x == "HELD")
            n_noisy = sum(1 for x in cls_list if x == "NOISY")
            n_total = len(cls_list)
            ballistic_frac = n_ballistic / n_total if n_total > 0 else 0
            chain_results.append({
                "chain_id": c["chain_id"],
                "n_tracklets": n_total,
                "n_ballistic": n_ballistic,
                "n_held": n_held,
                "n_noisy": n_noisy,
                "ballistic_frac": ballistic_frac,
                "classifications": cls_list,
            })
        # Show distribution
        n_pure_ballistic = sum(1 for c in chain_results if c["n_noisy"] == 0
                               and c["n_held"] == 0 and c["n_ballistic"] > 0)
        n_with_noisy = sum(1 for c in chain_results if c["n_noisy"] > 0)
        print(f"  chains with all-BALLISTIC tracklets: {n_pure_ballistic}")
        print(f"  chains with NOISY tracklets: {n_with_noisy}")
        if n_with_noisy > 0:
            print(f"  chains with NOISY tracklets (likely tracker artifacts):")
            for c in chain_results:
                if c["n_noisy"] > 0:
                    print(f"    chain {c['chain_id']}: n={c['n_tracklets']}, "
                          f"ballistic={c['n_ballistic']}, held={c['n_held']}, "
                          f"noisy={c['n_noisy']}, frac={c['ballistic_frac']:.2f}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "n_tracklets": len(tracklet_points),
            "class_counts": dict(cls_counts),
            "n_chains": len(chains),
            "n_pure_ballistic_chains": n_pure_ballistic,
            "n_noisy_chains": n_with_noisy,
            "chain_results": chain_results,
            "per_tracklet": {tid: c for tid, c in classifications.items()},
        }

    out_path = H1_DATA / "h8_v2_per_tracklet_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
