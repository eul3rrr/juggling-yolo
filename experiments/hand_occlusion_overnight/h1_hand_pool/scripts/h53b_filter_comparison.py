#!/usr/bin/env python3
"""H53: H52+MIN=2 filter applied to the full H12 v8 event log.

Tests whether H8 v5 parabolic physics check (with relaxed MIN=2) can
serve as an alternative or complement to H50's 10-frame flight-time filter
on the full H12 v8 catch+throw event log.

For each (CATCH, THROW) pair:
- If H8 v5 at MIN=2 returns VIOLATING (velocity_discontinuity > 5.0),
  the pair is flagged.
- Compare to H50's flagging (flight_time < 10).

Hypothesis: H8 v5 physics at MIN=2 will flag the same identity switches
that H50 flags, providing a physics-based corroboration.
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

H8V5 = {
    "PARABOLA_N": 8,
    "MIN_TRACKLET_PTS": 2,  # MIN=2 to match H52 sensitivity grid
    "GRAVITY_PX_PER_FRAME2": 0.46,
    "DISCONTINUITY_TOLERANCE": 5.0,
}

H50_MIN_FLIGHT = 10  # frames


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
    t = list(frames)
    n = len(t)
    if n < 3:
        return 0.0, 0.0, ys[0] if ys else 0.0, t[0] if t else 0
    t0 = sum(t) / n
    tc = [ti - t0 for ti in t]
    S_tc2 = sum(x * x for x in tc)
    S_tc = sum(tc)
    S_tc3 = sum(x * x * x for x in tc)
    S_tc4 = sum(x * x * x * x for x in tc)
    S_y = sum(ys)
    S_tc_y = sum(tc[i] * ys[i] for i in range(n))
    S_tc2_y = sum(tc[i] * tc[i] * ys[i] for i in range(n))
    M = [
        [S_tc4, S_tc3, S_tc2, S_tc2_y],
        [S_tc3, S_tc2, S_tc,  S_tc_y],
        [S_tc2, S_tc,  n,     S_y],
    ]
    for i in range(3):
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


def check_pair_min2(src_pts: list, tgt_pts: list, gap: int) -> dict:
    if (len(src_pts) < H8V5["MIN_TRACKLET_PTS"]) or (len(tgt_pts) < H8V5["MIN_TRACKLET_PTS"]):
        return {"verdict": "INSUFFICIENT_DATA", "velocity_discontinuity": 0.0,
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
    gap_for_pred = max(gap, 1)
    predicted_tgt_vy = src_vy + H8V5["GRAVITY_PX_PER_FRAME2"] * gap_for_pred
    v_disc = abs(tgt_vy - predicted_tgt_vy)
    is_violating = v_disc > H8V5["DISCONTINUITY_TOLERANCE"]
    return {
        "verdict": "VIOLATING" if is_violating else "OK",
        "src_vy": round(src_vy, 3), "tgt_vy": round(tgt_vy, 3),
        "predicted_tgt_vy": round(predicted_tgt_vy, 3),
        "velocity_discontinuity": round(v_disc, 3),
        "src_n_used": len(src_tail), "tgt_n_used": len(tgt_head),
    }


def main() -> None:
    summary = {"config": H8V5, "h50_min_flight": H50_MIN_FLIGHT, "videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H53b: H52+MIN=2 vs H50 on full event log) ===")
        tracklet_points = load_tracklet_points(stem)
        # Load the H12 v8 timeline (h7v3plus3 chain events)
        # Use catch_throw_timeline_v8 (H12 v8 unfiltered baseline)
        timeline_path = H1_DATA / f"catch_throw_timeline_v8_{stem}.csv"
        if not timeline_path.exists():
            # Fall back to h50 timeline
            timeline_path = H1_DATA / f"catch_throw_timeline_h50_{stem}.csv"
            if not timeline_path.exists():
                print(f"  No timeline file for {stem}")
                continue
        # Build per-chain CATCH -> next CATCH pairs (a CATCH is followed by a THROW
        # in the same chain, then the next CATCH in the same chain)
        chain_events: dict[int, list[dict]] = defaultdict(list)
        with timeline_path.open() as fh:
            for r in csv.DictReader(fh):
                chain_events[int(r["chain_id"])].append(r)
        # Group by chain, sort by event_frame, build (CATCH, THROW, NEXT_CATCH) tuples
        # The "flight" is from the THROW event_frame to the NEXT CATCH event_frame
        # in the same chain.
        # But for a H50-style filter we want CATCH->next CATCH (with the THROW in
        # between). H50 reports flight_time as the gap from the CATCH's event_frame
        # to the next CATCH's event_frame.
        pairs = []
        for cid in sorted(chain_events.keys()):
            events = chain_events[cid]
            events.sort(key=lambda e: int(e["event_frame"]))
            for i, ev in enumerate(events):
                if ev["event"] != "CATCH":
                    continue
                f_catch = int(ev["event_frame"])
                tid_catch = int(ev["tid"])
                # find the next CATCH in same chain
                next_catches = [e for e in events[i+1:] if e["event"] == "CATCH"]
                if not next_catches:
                    continue
                next_c = next_catches[0]
                f_next_catch = int(next_c["event_frame"])
                ft = f_next_catch - f_catch
                pairs.append({
                    "chain_id": cid,
                    "f_catch": f_catch,
                    "f_throw": f_catch,  # placeholder; we don't need throw frame
                    "tid_catch": tid_catch,
                    "tid_next_catch": int(next_c["tid"]),
                    "flight_time": ft,
                })
        # For each pair, find source/target tracklets in h7v3plus3 chain set
        chains_by_id: dict[int, dict] = {}
        for fname in (f"h7v3plus3_chains_{stem}.csv", f"h7v3pure_chains_{stem}.csv"):
            p = H1_DATA / fname
            if p.exists():
                with p.open() as fh:
                    for r in csv.DictReader(fh):
                        chains_by_id[int(r["chain_id"])] = r
                break
        if not chains_by_id:
            print(f"  No chain file for {stem}")
            continue
        # Process pairs
        h50_drops = 0
        h52min2_drops = 0
        h50_only_drops = 0  # H50 says drop, H52 says keep
        h52_only_drops = 0  # H52 says drop, H50 says keep
        both_drop = 0
        pair_records = []
        for pair in pairs:
            cid = pair["chain_id"]
            if cid not in chains_by_id:
                continue
            tids = [int(t) for t in chains_by_id[cid]["tids"].split(",") if t]
            tids.sort()
            from_tid = pair["tid_catch"]
            to_tid = pair["tid_next_catch"]
            src_pts = tracklet_points.get(from_tid, [])
            tgt_pts = tracklet_points.get(to_tid, [])
            gap = max(pair["flight_time"], 1)
            h52 = check_pair_min2(src_pts, tgt_pts, gap)
            # H50 filter is gap_frames (CATCH->THROW) < 10, not CATCH->next CATCH
            # For CATCH->next CATCH, the natural definition is "same-chain gap"
            h50_drop = pair["flight_time"] < H50_MIN_FLIGHT
            h52_drop = h52["verdict"] == "VIOLATING"
            if h50_drop:
                h50_drops += 1
            if h52_drop:
                h52min2_drops += 1
            if h50_drop and h52_drop:
                both_drop += 1
            elif h50_drop and not h52_drop:
                h50_only_drops += 1
            elif h52_drop and not h50_drop:
                h52_only_drops += 1
            pair_records.append({
                "chain_id": cid,
                "from_tid": from_tid,
                "to_tid": to_tid,
                "flight_time": pair["flight_time"],
                "h50_drop": h50_drop,
                "h52_min2_drop": h52_drop,
                "h52_verdict": h52["verdict"],
                "v_disc": h52.get("velocity_discontinuity", 0.0),
                "src_n": len(src_pts),
                "tgt_n": len(tgt_pts),
            })
        # Also process CATCH->THROW pairs from H50 timeline for H50-vs-H52 comparison
        # The H50 timeline has 'gap_frames' which is CATCH->THROW same-chain distance
        c2t_pairs = []
        for cid in sorted(chain_events.keys()):
            events = chain_events[cid]
            events.sort(key=lambda e: int(e["event_frame"]))
            catch = None
            for ev in events:
                if ev["event"] == "CATCH":
                    catch = ev
                elif ev["event"] == "THROW" and catch is not None:
                    f_catch = int(catch["event_frame"])
                    f_throw = int(ev["event_frame"])
                    gap = f_throw - f_catch
                    # The proper source/target for H8 v5 physics check
                    # is the prev_tid tracklet's END (at f_catch) and the
                    # current tid tracklet's START (at f_throw).
                    prev_tid_v = int(catch.get("prev_tid", 0))
                    cur_tid_v = int(ev["tid"])
                    c2t_pairs.append({
                        "chain_id": cid,
                        "from_tid": prev_tid_v,
                        "to_tid": cur_tid_v,
                        "gap_frames": gap,
                        "f_catch": f_catch,
                        "f_throw": f_throw,
                    })
                    catch = None
        c2t_records = []
        h50_drops_c2t = 0
        h52_drops_c2t = 0
        both_c2t = 0
        h50_only_c2t = 0
        h52_only_c2t = 0
        for pair in c2t_pairs:
            cid = pair["chain_id"]
            if cid not in chains_by_id:
                continue
            src_pts = tracklet_points.get(pair["from_tid"], [])
            tgt_pts = tracklet_points.get(pair["to_tid"], [])
            gap = max(pair["gap_frames"], 1)
            h52 = check_pair_min2(src_pts, tgt_pts, gap)
            h50_drop = pair["gap_frames"] < H50_MIN_FLIGHT
            h52_drop = h52["verdict"] == "VIOLATING"
            if h50_drop:
                h50_drops_c2t += 1
            if h52_drop:
                h52_drops_c2t += 1
            if h50_drop and h52_drop:
                both_c2t += 1
            elif h50_drop and not h52_drop:
                h50_only_c2t += 1
            elif h52_drop and not h50_drop:
                h52_only_c2t += 1
            c2t_records.append({
                "chain_id": cid,
                "from_tid": pair["from_tid"],
                "to_tid": pair["to_tid"],
                "gap_frames": pair["gap_frames"],
                "f_catch": pair["f_catch"],
                "f_throw": pair["f_throw"],
                "h50_drop": h50_drop,
                "h52_min2_drop": h52_drop,
                "h52_verdict": h52["verdict"],
                "v_disc": h52.get("velocity_discontinuity", 0.0),
                "src_n": len(src_pts),
                "tgt_n": len(tgt_pts),
            })
        # Summary
        print(f"  CATCH->next CATCH pairs: {len(pair_records)}")
        print(f"    H50 drops (flight<10): {h50_drops}")
        print(f"    H52+MIN=2 drops (VIOLATING): {h52min2_drops}")
        print(f"    Both drop: {both_drop}")
        print(f"    H50 only: {h50_only_drops}")
        print(f"    H52+MIN=2 only: {h52_only_drops}")
        print(f"  CATCH->THROW pairs (H50 timeline): {len(c2t_records)}")
        print(f"    H50 drops (gap<10): {h50_drops_c2t}")
        print(f"    H52+MIN=2 drops (VIOLATING): {h52_drops_c2t}")
        print(f"    Both drop: {both_c2t}")
        print(f"    H50 only: {h50_only_c2t}")
        print(f"    H52+MIN=2 only: {h52_only_c2t}")
        summary["videos"][stem] = {
            "c2c": {
                "n_pairs": len(pair_records),
                "h50_drops": h50_drops,
                "h52_min2_drops": h52min2_drops,
                "both_drop": both_drop,
                "h50_only_drops": h50_only_drops,
                "h52_only_drops": h52_only_drops,
            },
            "c2t": {
                "n_pairs": len(c2t_records),
                "h50_drops": h50_drops_c2t,
                "h52_min2_drops": h52_drops_c2t,
                "both_drop": both_c2t,
                "h50_only_drops": h50_only_c2t,
                "h52_only_drops": h52_only_c2t,
            },
        }
        # Save pair records
        out_csv = H1_DATA / f"h53_filter_comparison_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(pair_records[0].keys()) if pair_records else [
                "chain_id", "from_tid", "to_tid", "flight_time",
                "h50_drop", "h52_min2_drop", "h52_verdict", "v_disc",
                "src_n", "tgt_n"])
            w.writeheader()
            for r in pair_records:
                w.writerow(r)
        print(f"  Saved C2C: {out_csv}")
        out_c2t = H1_DATA / f"h53_c2t_filter_comparison_{stem}.csv"
        with out_c2t.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(c2t_records[0].keys()) if c2t_records else [
                "chain_id", "from_tid", "to_tid", "gap_frames", "f_catch", "f_throw",
                "h50_drop", "h52_min2_drop", "h52_verdict", "v_disc",
                "src_n", "tgt_n"])
            w.writeheader()
            for r in c2t_records:
                w.writerow(r)
        print(f"  Saved C2T: {out_c2t}")
    out_summary = H1_DATA / "h53_filter_comparison_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_summary}")


if __name__ == "__main__":
    main()
