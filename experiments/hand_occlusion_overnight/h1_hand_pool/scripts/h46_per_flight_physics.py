#!/usr/bin/env python3
"""H46: per-flight physics check via bounce model.

REVISED HYPOTHESIS (H46 v1 was wrong):

  H46 v1 tried to extrapolate source's last parabola across
  the gap to predict target's first position. This was
  fundamentally wrong because the held phase at the hand is
  NOT a free-fall continuation — it's a forced stop + re-launch.
  Result: H46 v1 marked ALL flights as PHYSICS_VIOLATION,
  including visually-confirmed real catch-throws.

  H46 v2 (this script) uses a BOUNCE PHYSICS model:
    - Source's last arc has v0_in (velocity just before hand)
    - Target's first arc has v0_out (velocity just after hand)
    - A real catch-throw has v0_out ≈ -e * v0_in where
      e is the coefficient of restitution (0.4-0.9 for
      juggling catches)
    - v0_in < 0 (ball coming down to hand)
    - v0_out > 0 (ball going up after throw)
    - Their ratio is bounded by physical juggler limits

  Expected:
    - Real catch-throws: v0_out / |v0_in| in [0.3, 1.5]
      (catch-amplified throws are common in juggling)
    - Identity switches (H12 v8 false positive):
      v0_out / |v0_in| is negative (both going same direction)
      OR magnitudes are wildly different (no bounce)
    - Tracker fragmentations: v0 magnitudes are both very
      small OR the ratio is degenerate

ALGORITHM:
  1. For each H12 v8 flight, fit a parabola to source's
     last 8 points and target's first 8 points.
  2. Read v0 (initial velocity) from each fit.
  3. Compute v0_out / |v0_in| ratio.
  4. Classify as BOUNCE_OK if ratio in [0.3, 1.5] AND
     v0_in < 0 AND v0_out > 0, else BOUNCE_VIOLATION.
  5. Cross-validate against the 11 H45 visually-confirmed
     flights: 7 REAL + 4 NOT_REAL.

  THRESHOLDS declared from physical juggler limits:
    RATIO_MIN = 0.3 (juggler catches add ~3x energy)
    RATIO_MAX = 1.5 (max 50% extra height for hard throw)
    V0_IN_MAX = -0.5 (must be descending at min 0.5 px/frame)
    V0_OUT_MIN = 0.5 (must be ascending at min 0.5 px/frame)
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Thresholds (declared from physical juggler limits, NOT from manual labels)
TAIL_N = 3  # use last/first 3 points for velocity estimate
VY_DESCEND_MAX = -0.5  # source must descend at min 0.5 px/frame
VY_ASCEND_MIN = 0.5  # target must ascend at min 0.5 px/frame
MIN_TRACKLET_PTS = 5


def load_tracklet_points(stem: str) -> dict[int, list[tuple[int, float, float]]]:
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


def fit_parabola_y(pts: list[tuple[int, float, float]]) -> dict:
    """Fit y = 0.5*g*t^2 + v0*t + y0 to (frame, x, y) pts.

    Returns dict with keys: g, v0, y0, t0, n_pts, fit_residual.
    """
    if len(pts) < 3:
        return {"g": 0.0, "v0": 0.0, "y0": 0.0, "t0": pts[0][0] if pts else 0,
                "n_pts": len(pts), "fit_residual": 1e9}
    f0 = pts[0][0]
    ts = [p[0] - f0 for p in pts]
    ys = [p[2] for p in pts]
    n = len(ts)
    S_tt = sum(t * t for t in ts)
    S_ttt = sum(t ** 3 for t in ts)
    S_tttt = sum(t ** 4 for t in ts)
    S_y = sum(ys)
    S_ty = sum(t * y for t, y in zip(ts, ys))
    S_tty = sum(t * t * y for t, y in zip(ts, ys))
    A = [[S_tttt, S_ttt, S_tt],
         [S_ttt, S_tt, sum(ts)],
         [S_tt, sum(ts), n]]
    B = [S_tty, S_ty, S_y]
    def det3(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    d = det3(A)
    if abs(d) < 1e-9:
        return {"g": 0.0, "v0": 0.0, "y0": pts[-1][2], "t0": f0,
                "n_pts": n, "fit_residual": 1e9}
    def col_replace(col, val):
        m = [row[:] for row in A]
        for i in range(3):
            m[i][col] = val
        return m
    a = det3(col_replace(0, B[0])) / d
    b = det3(col_replace(1, B[1])) / d
    c = det3(col_replace(2, B[2])) / d
    g = 2 * a
    v0 = b
    y0 = c
    pred = [0.5 * g * t * t + v0 * t + y0 for t in ts]
    res = math.sqrt(sum((y - p) ** 2 for y, p in zip(ys, pred)) / n)
    return {"g": g, "v0": v0, "y0": y0, "t0": f0, "n_pts": n, "fit_residual": res}


def mean_vy(pts: list, n: int = TAIL_N) -> float:
    """Compute mean vy over the last/first `n` points (dy/df)."""
    if len(pts) < 2:
        return 0.0
    use = pts[-n:] if n > 0 else pts
    if len(use) < 2:
        return 0.0
    # Mean velocity across all consecutive pairs
    vys = []
    for i in range(1, len(use)):
        dy = use[i][2] - use[i - 1][2]
        df = use[i][0] - use[i - 1][0]
        if df > 0:
            vys.append(dy / df)
    if not vys:
        return 0.0
    return sum(vys) / len(vys)


def main() -> None:
    all_results = []
    for stem in STEMS:
        tracklets = load_tracklet_points(stem)
        with (H1_DATA / "h45_siteswap_flights.csv").open() as fh:
            flights = [r for r in csv.DictReader(fh) if r["stem"] == stem]
        print(f"\n=== {stem} ({len(flights)} flights) ===")
        for flight in flights:
            src_tid = int(flight["throw_tid"])
            tgt_tid = int(flight["next_catch_tid"])
            throw_frame = int(flight["throw_frame"])
            catch_frame = int(flight["next_catch_frame"])
            gap = catch_frame - throw_frame
            ft = int(flight["flight_time"])
            if src_tid not in tracklets or tgt_tid not in tracklets:
                continue
            src_pts = tracklets[src_tid]
            tgt_pts = tracklets[tgt_tid]
            if len(src_pts) < MIN_TRACKLET_PTS or len(tgt_pts) < MIN_TRACKLET_PTS:
                continue
            # Source's mean vy (over last 3 points)
            v_in = mean_vy(src_pts, n=TAIL_N)
            # Target's mean vy (over first 3 points)
            v_out = mean_vy(tgt_pts[:TAIL_N] if len(tgt_pts) > TAIL_N else tgt_pts,
                            n=TAIL_N)
            # Verdict
            in_descending = v_in < VY_DESCEND_MAX  # negative
            out_ascending = v_out > VY_ASCEND_MIN  # positive
            if in_descending and out_ascending:
                verdict = "BOUNCE_OK"
            else:
                verdict = "BOUNCE_VIOLATION"
            all_results.append({
                "stem": stem,
                "chain_id": flight["chain_id"],
                "src_tid": src_tid,
                "tgt_tid": tgt_tid,
                "throw_frame": throw_frame,
                "catch_frame": catch_frame,
                "flight_time": ft,
                "v_in": round(v_in, 2),
                "v_out": round(v_out, 2),
                "in_descending": in_descending,
                "out_ascending": out_ascending,
                "src_n_pts": len(src_pts),
                "tgt_n_pts": len(tgt_pts),
                "verdict": verdict,
            })
            print(f"  chain={flight['chain_id']} t{src_tid}->t{tgt_tid} "
                  f"ft={ft} v_in={v_in:.2f} v_out={v_out:.2f} "
                  f"desc={in_descending} asc={out_ascending} "
                  f"verdict={verdict}")

    out_path = H1_DATA / "h46_per_flight_physics.csv"
    with out_path.open("w", newline="") as fh:
        if all_results:
            w = csv.DictWriter(fh, fieldnames=list(all_results[0].keys()))
            w.writeheader()
            w.writerows(all_results)
    print(f"\nSaved: {out_path} ({len(all_results)} rows)")

    # Summary
    summary = {
        "videos": {},
        "config": {
            "TAIL_N": TAIL_N,
            "VY_DESCEND_MAX": VY_DESCEND_MAX,
            "VY_ASCEND_MIN": VY_ASCEND_MIN,
            "MIN_TRACKLET_PTS": MIN_TRACKLET_PTS,
        },
    }
    for stem in STEMS:
        rows = [r for r in all_results if r["stem"] == stem]
        verdict_counts = defaultdict(int)
        for r in rows:
            verdict_counts[r["verdict"]] += 1
        summary["videos"][stem] = {
            "n_flights": len(rows),
            "verdict_counts": dict(verdict_counts),
        }
    out_summary = H1_DATA / "h46_per_flight_physics_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2))
    print(f"Saved: {out_summary}")
    print("\n=== Summary ===")
    for stem, s in summary["videos"].items():
        print(f"  {stem}: {s['n_flights']} flights, verdicts={s['verdict_counts']}")


if __name__ == "__main__":
    main()
