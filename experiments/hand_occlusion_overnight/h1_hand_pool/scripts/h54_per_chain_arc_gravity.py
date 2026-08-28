#!/usr/bin/env python3
"""
H54 - Per-chain arc-gravity distribution as a single-ball signal.

Hypothesis: the h7v3plus3 chain set's per-chain coefficient of variation
(CV) of clean per-arc gravity values is a discriminative signal for
"is this a single physical ball?".

Predictions:
- Real single-ball chains have LOW gravity CV (every arc has the same g)
- Multi-ball merge chains have HIGH gravity CV (different physical balls
  have different apparent gravity due to perspective, hand motion, etc.)

A per-chain gravity CV is complementary to the H10 v10 quality score
(0.30*h3 + 0.30*h8 + 0.40*h9 + h8v8) because it uses a fundamentally
different signal: the within-chain consistency of the physics model,
not the cross-edge or coverage signals.

Algorithm:
1. Re-run the H8 v8 extrema-arc fit for every tracklet in h7v3plus3.
2. Collect per-arc gravity values (g) per chain.
3. Filter to clean arcs (0.05 < g < 5.0).
4. Compute per-chain: n_arcs_clean, g_mean, g_std, g_cv = std/mean.
5. Compare to H10 v10 chain quality and H11 v7 confidence labels.

Outputs:
- data/h54_per_chain_arc_gravity_<stem>.csv: per-chain g statistics
- data/h54_per_tracklet_arcs_<stem>.csv: per-tracklet per-arc gravity
- data/h54_summary.json: aggregate statistics
- reports/h54_report.md: analysis
"""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Re-use H8 v8's thresholds (declared from physical geometry)
EXTREMA_MIN_DIST = 5
MIN_ARC_N = 4
MIN_TRACKLET_PTS = 8
GRAVITY_CLEAN_LO = 0.05
GRAVITY_CLEAN_HI = 5.0

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_tracklet_points(stem: str) -> dict:
    """Return tid -> list of (frame, x, y) sorted by frame."""
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


def find_extrema(points, min_dist):
    """Local extrema in y with min-distance filter."""
    if len(points) < 2 * min_dist + 1:
        return []
    ys = [p[2] for p in points]
    extrema = []
    for i in range(min_dist, len(ys) - min_dist):
        is_max = all(ys[j] <= ys[i] for j in range(i - min_dist, i + min_dist + 1) if j != i)
        is_min = all(ys[j] >= ys[i] for j in range(i - min_dist, i + min_dist + 1) if j != i)
        if is_max:
            extrema.append((i, "peak"))
        elif is_min:
            extrema.append((i, "valley"))
    return extrema


def arcs_from_extrema(points, extrema):
    if not extrema:
        return [points] if len(points) >= MIN_ARC_N else []
    arcs = []
    if extrema[0][0] >= MIN_ARC_N:
        arcs.append(points[:extrema[0][0]])
    for i in range(len(extrema) - 1):
        s = extrema[i][0]
        e = extrema[i + 1][0] + 1
        if e - s >= MIN_ARC_N:
            arcs.append(points[s:e])
    if len(points) - 1 - extrema[-1][0] >= MIN_ARC_N:
        arcs.append(points[extrema[-1][0]:])
    return arcs


def fit_parabola(arc):
    """Fit y = 0.5*g*t^2 + v0*t + y0 to arc; return fit parameters."""
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


def compute_arcs_per_tracklet(stem):
    """Per-tracklet per-arc gravity fits. Returns tid -> list of {g, n_pts, residual}."""
    tracklets = load_tracklet_points(stem)
    out = {}
    for tid, pts in tracklets.items():
        if len(pts) < MIN_TRACKLET_PTS:
            out[tid] = []
            continue
        extrema = find_extrema(pts, EXTREMA_MIN_DIST)
        arcs = arcs_from_extrema(pts, extrema)
        fits = [fit_parabola(a) for a in arcs]
        out[tid] = [{"g": fit["g"], "n_pts": fit["n_pts"],
                     "residual": fit["fit_residual"],
                     "f_start": arc[0][0], "f_end": arc[-1][0]}
                    for arc, fit in zip(arcs, fits)]
    return out


def load_h7v3plus3_chains(stem):
    """Return list of dicts: {chain_id, tids: [int]}."""
    path = H1_DATA / f"h7v3plus3_chains_{stem}.csv"
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tids_str = r["tids"].strip()
            if tids_str:
                tids = [int(t) for t in tids_str.split(",") if t.strip()]
            else:
                tids = []
            out.append({"chain_id": r["chain_id"],
                        "n_tracklets": int(r["n_tracklets"]),
                        "first_frame": int(r["first_frame"]),
                        "last_frame": int(r["last_frame"]),
                        "tids": tids})
    return out


def load_h10v10_quality(stem):
    """Return chain_id -> quality_v10 (float or None)."""
    path = H1_DATA / f"h10v10_h7v3plus3_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            q = r["quality_v10"]
            out[r["chain_id"]] = float(q) if q else None
    return out


def per_chain_arc_gravity(chain, arc_per_tid):
    """Aggregate per-arc gravity for a chain. Returns dict of stats."""
    gs_all = []
    gs_clean = []
    n_tracklets = len(chain["tids"])
    n_arcs_total = 0
    n_arcs_clean = 0
    for tid in chain["tids"]:
        arcs = arc_per_tid.get(tid, [])
        for arc in arcs:
            n_arcs_total += 1
            g = arc["g"]
            gs_all.append(g)
            if GRAVITY_CLEAN_LO < g < GRAVITY_CLEAN_HI:
                gs_clean.append(g)
                n_arcs_clean += 1
    g_mean_clean = statistics.mean(gs_clean) if gs_clean else None
    g_std_clean = statistics.stdev(gs_clean) if len(gs_clean) >= 2 else None
    g_cv_clean = (g_std_clean / g_mean_clean) if (g_std_clean is not None and g_mean_clean) else None
    g_mean_all = statistics.mean(gs_all) if gs_all else None
    return {
        "n_tracklets": n_tracklets,
        "n_arcs_total": n_arcs_total,
        "n_arcs_clean": n_arcs_clean,
        "g_mean_all": round(g_mean_all, 3) if g_mean_all is not None else None,
        "g_mean_clean": round(g_mean_clean, 3) if g_mean_clean is not None else None,
        "g_std_clean": round(g_std_clean, 3) if g_std_clean is not None else None,
        "g_cv_clean": round(g_cv_clean, 3) if g_cv_clean is not None else None,
    }


def main():
    summary = {"videos": {}, "config": {
        "EXTREMA_MIN_DIST": EXTREMA_MIN_DIST,
        "MIN_ARC_N": MIN_ARC_N,
        "MIN_TRACKLET_PTS": MIN_TRACKLET_PTS,
        "GRAVITY_CLEAN_LO": GRAVITY_CLEAN_LO,
        "GRAVITY_CLEAN_HI": GRAVITY_CLEAN_HI,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H54 per-chain arc-gravity) ===")
        arc_per_tid = compute_arcs_per_tracklet(stem)
        chains = load_h7v3plus3_chains(stem)
        h10_quality = load_h10v10_quality(stem)

        # Per-tracklet per-arc CSV
        per_track_csv = H1_DATA / f"h54_per_tracklet_arcs_{stem}.csv"
        with per_track_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["tid", "n_arcs", "arc_idx", "g", "n_pts",
                        "residual", "f_start", "f_end", "is_clean"])
            for tid in sorted(arc_per_tid):
                arcs = arc_per_tid[tid]
                for i, arc in enumerate(arcs):
                    g = arc["g"]
                    is_clean = (GRAVITY_CLEAN_LO < g < GRAVITY_CLEAN_HI)
                    w.writerow([tid, len(arcs), i, round(g, 3), arc["n_pts"],
                                round(arc["residual"], 2), arc["f_start"],
                                arc["f_end"], is_clean])

        # Per-chain CSV
        per_chain_csv = H1_DATA / f"h54_per_chain_arc_gravity_{stem}.csv"
        with per_chain_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "n_arcs_total",
                        "n_arcs_clean", "g_mean_all", "g_mean_clean",
                        "g_std_clean", "g_cv_clean", "h10_quality_v10"])
            for chain in chains:
                stats = per_chain_arc_gravity(chain, arc_per_tid)
                w.writerow([chain["chain_id"], stats["n_tracklets"],
                            stats["n_arcs_total"], stats["n_arcs_clean"],
                            stats["g_mean_all"], stats["g_mean_clean"],
                            stats["g_std_clean"], stats["g_cv_clean"],
                            h10_quality.get(chain["chain_id"])])

        # Aggregate statistics
        n_chains = len(chains)
        # Per-chain gravity CV distribution
        cvs = []
        g_means = []
        n_clean_3plus = 0
        for chain in chains:
            stats = per_chain_arc_gravity(chain, arc_per_tid)
            if stats["g_cv_clean"] is not None:
                cvs.append(stats["g_cv_clean"])
            if stats["g_mean_clean"] is not None:
                g_means.append(stats["g_mean_clean"])
            if stats["n_arcs_clean"] >= 3:
                n_clean_3plus += 1
        # Cross-reference with H10 v10 quality
        # Pearson correlation of g_cv_clean vs h10_quality_v10 (multi-tracklet chains only)
        pairs = []
        for chain in chains:
            stats = per_chain_arc_gravity(chain, arc_per_tid)
            q = h10_quality.get(chain["chain_id"])
            if stats["g_cv_clean"] is not None and q is not None:
                pairs.append((stats["g_cv_clean"], q))
        # Pearson correlation
        pearson = None
        if len(pairs) >= 2:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mx = statistics.mean(xs)
            my = statistics.mean(ys)
            num = sum((x - mx) * (y - my) for x, y in pairs)
            dx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
            dy = (sum((y - my) ** 2 for y in ys)) ** 0.5
            if dx > 0 and dy > 0:
                pearson = num / (dx * dy)

        # Spearman rank correlation
        def rank(xs):
            sorted_xs = sorted(enumerate(xs), key=lambda p: p[1])
            ranks = [0] * len(xs)
            for r, (i, _) in enumerate(sorted_xs):
                ranks[i] = r + 1
            return ranks
        spearman = None
        if len(pairs) >= 2:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            rx = rank(xs)
            ry = rank(ys)
            n = len(pairs)
            d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
            spearman = 1 - 6 * d2 / (n * (n * n - 1))

        video_summary = {
            "n_chains": n_chains,
            "n_chains_with_clean_arcs": len(cvs),
            "n_chains_with_3plus_clean_arcs": n_clean_3plus,
            "g_cv_mean": round(statistics.mean(cvs), 3) if cvs else None,
            "g_cv_median": round(statistics.median(cvs), 3) if cvs else None,
            "g_cv_min": round(min(cvs), 3) if cvs else None,
            "g_cv_max": round(max(cvs), 3) if cvs else None,
            "g_mean_overall": round(statistics.mean(g_means), 3) if g_means else None,
            "pearson_g_cv_vs_h10_quality": round(pearson, 3) if pearson is not None else None,
            "spearman_g_cv_vs_h10_quality": round(spearman, 3) if spearman is not None else None,
            "n_pairs_for_corr": len(pairs),
        }
        summary["videos"][stem] = video_summary
        print(f"  {video_summary}")

    out_path = H1_DATA / "h54_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
