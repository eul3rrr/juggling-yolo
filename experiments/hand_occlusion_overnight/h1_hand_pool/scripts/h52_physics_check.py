#!/usr/bin/env python3
"""H52: H8 v5 parabolic fit on H50-dropped (CATCH, THROW) pairs.

HYPOTHESIS:
  H50 visual QA found 2/3 dropped pairs are clearly tracker artifacts
  (chain 23 ft=1, chain 30 ft=5), but 1/3 (chain 13 ft=3) is
  visually a real catch-throw. The 10-frame filter may be
  over-aggressive for this 1 case.

  H8 v5 parabolic fit computes the source-tracklet tail's y-velocity
  and the target-tracklet head's y-velocity, and checks the
  velocity discontinuity (accounting for gravity over the gap).
  For a REAL catch-throw with a short held phase, the velocities
  should be physically consistent (small discontinuity).
  For a TRACKER FRAGMENTATION, the source and target are
  unrelated balls with large velocity discontinuity.

  Question: can H8 v5's physics check distinguish the chain 13
  ft=3 case (visual says REAL) from the chain 23/30 cases
  (visual says FRAGMENTATION)?

  This is a NARROW-SCOPE test on the 3 H50-dropped pairs, not
  a new event-log filter. If H8 v5 successfully disambiguates
  ft=3-9 cases, the H50 10-frame filter could be refined
  to a per-flight H8 v5-based filter (keep short flights with
  consistent physics, drop short flights with discontinuous physics).

METHOD:
  1. Load H50's dropped (CATCH, THROW) pairs.
  2. For each pair, find the source and target tracklets in
     the h7v3pure chain.
  3. Apply H8 v5 parabolic fit to the source tail and target head.
  4. Compute velocity_discontinuity = |tgt_vy - predicted_tgt_vy|.
  5. Classify: low discontinuity -> PHYSICS_OK (real catch-throw);
     high discontinuity -> PHYSICS_VIOLATION (tracker fragmentation).
  6. Compare H8 v5 classification to H50 visual QA.
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

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H8 v5 thresholds (from h8_v5_parabolic.py)
H8V5 = {
    "PARABOLA_N": 8,  # last 8 / first 8 frames
    "MIN_TRACKLET_PTS": 6,  # H8 v5 default
    "GRAVITY_PX_PER_FRAME2": 0.46,  # empirical YouTube median from H8 v8
    "DISCONTINUITY_TOLERANCE": 5.0,  # px/frame
}


def load_tracklet_points(stem: str) -> dict[int, list]:
    out = defaultdict(list)
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r.get("observed") not in ("True", "1", "true"):
                continue
            try:
                tid = int(r["track_id"])
                f = int(r["frame"])
                x = float(r["center_x"])
                y = float(r["center_y"])
            except (ValueError, KeyError):
                continue
            out[tid].append((f, x, y))
    for tid in out:
        out[tid].sort(key=lambda p: p[0])
    return dict(out)


def fit_parabola(frames: list[int], ys: list[float]) -> tuple:
    """Fit y = a*(t-t0)^2 + b*(t-t0) + c by least squares.
    Returns (a, b, c, t0).
    """
    t = list(frames)
    n = len(t)
    if n < 3:
        return 0.0, 0.0, ys[0] if ys else 0.0, t[0] if t else 0
    t0 = sum(t) / n
    tc = [ti - t0 for ti in t]
    # Normal equations for y = a*tc^2 + b*tc + c
    S_tc2 = sum(x * x for x in tc)
    S_tc = sum(tc)
    S_tc3 = sum(x * x * x for x in tc)
    S_tc4 = sum(x * x * x * x for x in tc)
    S_y = sum(ys)
    S_tc_y = sum(tc[i] * ys[i] for i in range(n))
    S_tc2_y = sum(tc[i] * tc[i] * ys[i] for i in range(n))
    # Solve 3x3: [S_tc4, S_tc3, S_tc2] [a]   [S_tc2_y]
    #           [S_tc3, S_tc2, S_tc ] [b] = [S_tc_y ]
    #           [S_tc2, S_tc,  n    ] [c]   [S_y    ]
    # Use Gaussian elimination (simple, no numpy needed)
    M = [
        [S_tc4, S_tc3, S_tc2, S_tc2_y],
        [S_tc3, S_tc2, S_tc,  S_tc_y],
        [S_tc2, S_tc,  n,     S_y],
    ]
    # Forward elimination
    for i in range(3):
        # Find pivot
        max_row = i
        for k in range(i + 1, 3):
            if abs(M[k][i]) > abs(M[max_row][i]):
                max_row = k
        M[i], M[max_row] = M[max_row], M[i]
        if abs(M[i][i]) < 1e-12:
            continue
        for k in range(i + 1, 3):
            factor = M[k][i] / M[i][i]
            for j in range(i, 4):
                M[k][j] -= factor * M[i][j]
    # Back substitution
    coef = [0.0] * 3
    for i in range(2, -1, -1):
        if abs(M[i][i]) < 1e-12:
            coef[i] = 0.0
        else:
            coef[i] = (M[i][3] - sum(M[i][j] * coef[j] for j in range(i + 1, 3))) / M[i][i]
    a, b, c = coef
    return a, b, c, t0


def parabolic_vy_at(a: float, b: float, t0: float, t: int) -> float:
    return 2 * a * (t - t0) + b


def check_pair(src_pts: list, tgt_pts: list, gap: int) -> dict:
    """Apply H8 v5 parabolic check to a (source, target) tracklet pair."""
    if len(src_pts) < H8V5["MIN_TRACKLET_PTS"] or len(tgt_pts) < H8V5["MIN_TRACKLET_PTS"]:
        return {"physics_status": "INSUFFICIENT_DATA",
                "src_vy": 0.0, "tgt_vy": 0.0, "predicted_tgt_vy": 0.0,
                "velocity_discontinuity": 0.0,
                "src_n_used": len(src_pts), "tgt_n_used": len(tgt_pts)}

    n = H8V5["PARABOLA_N"]
    src_tail = src_pts[-n:]
    tgt_head = tgt_pts[:n]

    src_frames = [p[0] for p in src_tail]
    src_ys = [p[2] for p in src_tail]
    a_s, b_s, _, t0_s = fit_parabola(src_frames, src_ys)
    src_vy = parabolic_vy_at(a_s, b_s, t0_s, src_frames[-1])

    tgt_frames = [p[0] for p in tgt_head]
    tgt_ys = [p[2] for p in tgt_head]
    a_t, b_t, _, t0_t = fit_parabola(tgt_frames, tgt_ys)
    tgt_vy = parabolic_vy_at(a_t, b_t, t0_t, tgt_frames[0])

    # Predict the target's expected y-velocity at the start of the target tracklet
    # assuming constant gravity over the gap.
    gap_for_pred = max(gap, 1)
    predicted_tgt_vy = src_vy + H8V5["GRAVITY_PX_PER_FRAME2"] * gap_for_pred

    v_disc = abs(tgt_vy - predicted_tgt_vy)
    is_violating = v_disc > H8V5["DISCONTINUITY_TOLERANCE"]
    return {
        "physics_status": "VIOLATING" if is_violating else "OK",
        "src_vy": round(src_vy, 3),
        "tgt_vy": round(tgt_vy, 3),
        "predicted_tgt_vy": round(predicted_tgt_vy, 3),
        "velocity_discontinuity": round(v_disc, 3),
        "src_n_used": len(src_tail),
        "tgt_n_used": len(tgt_head),
        "src_a_parabolic": round(a_s, 3),
        "tgt_a_parabolic": round(a_t, 3),
    }


def main():
    summary = {
        "config": H8V5,
        "videos": {},
    }
    for stem in STEMS:
        print(f"\n=== {stem} (H52: H8 v5 physics on H50-dropped pairs) ===")
        tracklet_points = load_tracklet_points(stem)
        print(f"  loaded {len(tracklet_points)} tracklets")

        # Load H50's dropped pairs
        dropped_path = H1_DATA / f"h50_dropped_events_{stem}.csv"
        if not dropped_path.exists():
            print(f"  No dropped events file: {dropped_path}")
            continue
        # Group by chain_id and pair
        chain_drops = defaultdict(list)
        with dropped_path.open() as fh:
            for r in csv.DictReader(fh):
                chain_drops[int(r["chain_id"])].append(r)
        # Load h7v3pure chains to get prev_tid
        chains_by_id = {}
        with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                chains_by_id[int(r["chain_id"])] = r
        # Pair up CATCH+THROW for each chain
        for cid, events in chain_drops.items():
            # Sort by event_frame
            events.sort(key=lambda e: int(e["event_frame"]))
            catch = next((e for e in events if e["event"] == "CATCH"), None)
            throw = next((e for e in events if e["event"] == "THROW"), None)
            if not catch or not throw:
                continue
            to_tid = int(throw["tid"])
            # Find prev_tid from the chain's tids list
            tids = [int(t) for t in chains_by_id[cid]["tids"].split(",") if t]
            tids.sort()
            # The prev_tid is the largest tid in tids that is < to_tid
            prev_tids = [t for t in tids if t < to_tid]
            from_tid = max(prev_tids) if prev_tids else to_tid
            f_throw = int(throw["event_frame"])
            f_catch = int(catch["event_frame"])
            ft = int(throw["flight_time"])
            print(f"\n  Chain {cid}: CATCH@ f={f_catch} (tid={catch['tid']}) -> "
                  f"THROW@ f={f_throw} (tid={to_tid}), flight_time={ft}")
            src_pts = tracklet_points.get(from_tid, [])
            tgt_pts = tracklet_points.get(to_tid, [])
            print(f"    source (tid {from_tid}): {len(src_pts)} pts "
                  f"f={src_pts[0][0] if src_pts else 'N/A'}-{src_pts[-1][0] if src_pts else 'N/A'}")
            print(f"    target (tid {to_tid}): {len(tgt_pts)} pts "
                  f"f={tgt_pts[0][0] if tgt_pts else 'N/A'}-{tgt_pts[-1][0] if tgt_pts else 'N/A'}")
            gap = f_throw - f_catch
            if gap == 0:
                gap = 1
            result = check_pair(src_pts, tgt_pts, gap)
            print(f"    H8 v5 physics: {result['physics_status']}")
            if result['physics_status'] != 'INSUFFICIENT_DATA':
                print(f"      src_vy = {result['src_vy']}, tgt_vy = {result['tgt_vy']}, "
                      f"predicted = {result['predicted_tgt_vy']}")
                print(f"      velocity_discontinuity = {result['velocity_discontinuity']} "
                      f"(tol = {H8V5['DISCONTINUITY_TOLERANCE']})")
                print(f"      src_a = {result['src_a_parabolic']}, tgt_a = {result['tgt_a_parabolic']}")
            else:
                print(f"      src_n_used = {result['src_n_used']}, tgt_n_used = {result['tgt_n_used']} "
                      f"(need {H8V5['MIN_TRACKLET_PTS']})")
            verdict = ("REAL_CATCH_THROW" if result["physics_status"] == "OK"
                       else "TRACKER_FRAGMENTATION" if result["physics_status"] == "VIOLATING"
                       else "INSUFFICIENT_DATA")
            print(f"    H8 v5 verdict: {verdict}")
            # Sensitivity grid on MIN_TRACKLET_PTS
            print(f"    Sensitivity grid on MIN_TRACKLET_PTS:")
            for min_pts in [2, 3, 4, 5, 6, 8, 10]:
                H8V5_grid = dict(H8V5, MIN_TRACKLET_PTS=min_pts)
                # Re-check with this min_pts
                if (len(src_pts) < min_pts) or (len(tgt_pts) < min_pts):
                    grid_verdict = "INSUFFICIENT_DATA"
                else:
                    # Inline the check
                    n = H8V5_grid["PARABOLA_N"]
                    src_tail = src_pts[-n:]
                    tgt_head = tgt_pts[:n]
                    src_frames = [p[0] for p in src_tail]
                    src_ys = [p[2] for p in src_tail]
                    a_s, b_s, _, t0_s = fit_parabola(src_frames, src_ys)
                    src_vy = parabolic_vy_at(a_s, b_s, t0_s, src_frames[-1])
                    tgt_frames = [p[0] for p in tgt_head]
                    tgt_ys = [p[2] for p in tgt_head]
                    a_t, b_t, _, t0_t = fit_parabola(tgt_frames, tgt_ys)
                    tgt_vy = parabolic_vy_at(a_t, b_t, t0_t, tgt_frames[0])
                    gap_for_pred = max(gap, 1)
                    predicted_tgt_vy = src_vy + H8V5_grid["GRAVITY_PX_PER_FRAME2"] * gap_for_pred
                    v_disc = abs(tgt_vy - predicted_tgt_vy)
                    grid_verdict = "OK" if v_disc <= H8V5_grid["DISCONTINUITY_TOLERANCE"] else "VIOLATING"
                print(f"      MIN_TRACKLET_PTS={min_pts}: {grid_verdict}")
            summary["videos"].setdefault(stem, []).append({
                "chain_id": cid,
                "from_tid": from_tid,
                "to_tid": to_tid,
                "f_catch": f_catch,
                "f_throw": f_throw,
                "flight_time": ft,
                "gap": gap,
                "src_n_pts": len(src_pts),
                "tgt_n_pts": len(tgt_pts),
                "h8v5_result": result,
                "h8v5_verdict": verdict,
            })

    out_summary = H1_DATA / "h52_physics_check_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_summary}")


if __name__ == "__main__":
    main()
