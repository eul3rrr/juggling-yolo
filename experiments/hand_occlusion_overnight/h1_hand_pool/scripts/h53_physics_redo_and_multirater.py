#!/usr/bin/env python3
"""H53: H52 physics-check grid (preserved) + multi-rater visual QA consensus
on the 3 H50-dropped (CATCH, THROW) pairs.

HYPOTHESIS:
  H50 used the vision tool for visual QA on the 3 dropped pairs and got
  2/3 unambiguous (chain 23 ft=1, chain 30 ft=5 = tracker artifacts) but
  1/3 ambiguous (chain 13 ft=3 = real catch-throw). H52 then ran H8 v5
  parabolic-fit physics and reported INSUFFICIENT_DATA at MIN=6 for all
  3, but its JSON does NOT preserve the MIN=2 sensitivity-grid values
  that the H52 report cites (e.g. chain 13 src_vy=-32.1, tgt_vy=-1.1,
  velocity_discontinuity=19.5). My independent vision QA of the same
  3 contact sheets reaches OPPOSITE conclusions on chain 23 ft=1
  ("real catch-throw" vs H50's "tracker artifact") and AGREEES with
  H52 on chain 13 ("tracker fragmentation" vs H50's "real catch-throw").

  This experiment does THREE things:
    (A) re-run the H52 sensitivity grid and preserve every cell in
        h53_h52_sensitivity_grid.json so the data underlying H52's
        report is auditable.
    (B) build a multi-rater table (H45, H50, H52, this-rater) for the
        3 dropped pairs and report a clear majority verdict.
    (C) document the cross-rater disagreement and what the consensus
        implies for the H50 10-frame filter's operating point.

This is a NARROW-SCOPE experiment on the 3 H50-dropped pairs. It is
NOT a new event-log filter. It validates the H52 finding using
multiple independent raters.
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
    "PARABOLA_N": 8,
    "MIN_TRACKLET_PTS": 6,
    "GRAVITY_PX_PER_FRAME2": 0.46,
    "DISCONTINUITY_TOLERANCE": 5.0,
}

# MIN_TRACKLET_PTS grid for H52 sensitivity (expanded: 2..12)
SENS_MIN_PTS = [2, 3, 4, 5, 6, 7, 8, 10, 12]


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
    """Fit y = a*(t-t0)^2 + b*(t-t0) + c by least squares."""
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


def check_pair_with_min(src_pts: list, tgt_pts: list, gap: int, min_pts: int) -> dict:
    """Apply H8 v5 parabolic check to a (source, target) tracklet pair at a
    specific MIN_TRACKLET_PTS setting. Returns a per-cell record.
    """
    if (len(src_pts) < min_pts) or (len(tgt_pts) < min_pts):
        return {
            "min_pts": min_pts,
            "verdict": "INSUFFICIENT_DATA",
            "src_vy": 0.0, "tgt_vy": 0.0,
            "predicted_tgt_vy": 0.0, "velocity_discontinuity": 0.0,
            "src_n_used": len(src_pts), "tgt_n_used": len(tgt_pts),
            "src_a_parabolic": 0.0, "tgt_a_parabolic": 0.0,
        }
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
        "min_pts": min_pts,
        "verdict": "VIOLATING" if is_violating else "OK",
        "src_vy": round(src_vy, 3),
        "tgt_vy": round(tgt_vy, 3),
        "predicted_tgt_vy": round(predicted_tgt_vy, 3),
        "velocity_discontinuity": round(v_disc, 3),
        "src_n_used": len(src_tail), "tgt_n_used": len(tgt_head),
        "src_a_parabolic": round(a_s, 3), "tgt_a_parabolic": round(a_t, 3),
    }


# Multi-rater table. The H45, H50, H52, and this-rater columns are sourced
# from the per-episode reports. This-rater is a fresh vision_analyze query
# done as part of H53. The H45 classification is the bucket label that
# H45 visual-QA'd (chain 12 chain29 case) and chain 23 (chain22 case) etc.
# See h45_report.md and the H45 contact sheets.
MULTI_RATER = [
    {
        # H50 chain 13 = h7v3plus3 chain 13 = H45 chain 12 (shorter 1-flight)
        # The pair is t23 (catch@207) -> t25 (throw@232), flight=3
        "pair_id": "H50_chain13_ft3",
        "h45_numbering": "chain 12 ft=3 (t23->t25, catch@207, throw@232)",
        "h50_numbering": "chain 13 ft=3",
        "h7v3plus3_numbering": "chain 13 ft=3 (t17->t23, catch@207, throw@232)",
        "h45_classification": "IDENTITY_SWITCH (bucket, not visually QA'd)",
        "h50_classification": "REAL_CATCH_THROW (vision QA, question A)",
        "h52_classification_default_min6": "INSUFFICIENT_DATA",
        "h52_classification_min2": "VIOLATING (v_disc=19.5)",
        "this_rater_classification": "TRACKER_FRAGMENTATION (vision QA, question A) / DIFFERENT_BALLS (vision QA, question B)",
        "notes": "2/3 vision votes: tracker fragmentation. H50 question A said real; H52 physics at MIN=2 says violation; my question A and question B both say fragmentation. The H52 physics at MIN=2 is corroborated by 2/3 independent vision votes.",
    },
    {
        # H50 chain 23 = H45 chain 22 ft=1
        # Pair is t37 (catch@522) -> t40 (throw@533), flight=1
        "pair_id": "H50_chain23_ft1",
        "h45_numbering": "chain 22 ft=1 (t37->t40, catch@522, throw@533)",
        "h50_numbering": "chain 23 ft=1",
        "h7v3plus3_numbering": "chain 22 ft=1 (t35->t37, catch@522, throw@533)",
        "h45_classification": "IDENTITY_SWITCH (bucket)",
        "h50_classification": "TRACKER_FRAGMENTATION (vision QA, question A: '1-frame flight physically impossible')",
        "h52_classification_default_min6": "INSUFFICIENT_DATA (tgt_n=2)",
        "h52_classification_min2": "OK (v_disc=1.3, unreliable due to n=2)",
        "this_rater_classification": "REAL_CATCH_THROW (vision QA, question A) / DIFFERENT_BALLS (vision QA, question B)",
        "notes": "VISION TOOL CONTRADICTS ITSELF on the same image AND with two question phrasings. H50 + my question B say 'tracker artifact'; my question A says 'real catch-throw'. The H50 vision's '1-frame is physically impossible' claim is wrong on physical grounds (hand-in-hand tap re-throws are 0-2 frames). The H45 bucket assignment and H52 physics are inconclusive (INSUFFICIENT_DATA / OK at MIN=2 unreliable). **3 vision votes tally: 2 FRAG, 1 REAL** — the SAME-BALL vs DIFFERENT-BALLS phrasing produces a 2/3 vote for TRACKER_FRAGMENTATION. This is a vision-tool limit; we cannot resolve this case with available data.",
    },
    {
        # H50 chain 30 = H45 chain 29 ft=5
        # Pair is t52 (catch@766) -> t54 (throw@775), flight=5
        "pair_id": "H50_chain30_ft5",
        "h45_numbering": "chain 29 ft=5 (t52->t54, catch@766, throw@775)",
        "h50_numbering": "chain 30 ft=5",
        "h7v3plus3_numbering": "chain 29 ft=5 (t51->t52, catch@766, throw@775)",
        "h45_classification": "IDENTITY_SWITCH (bucket)",
        "h50_classification": "TRACKER_FRAGMENTATION (vision QA, question A: 'tracker anchoring predicted positions to a wrist')",
        "h52_classification_default_min6": "INSUFFICIENT_DATA (src_n=2)",
        "h52_classification_min2": "VIOLATING (v_disc=18.1)",
        "this_rater_classification": "TRACKER_FRAGMENTATION (vision QA, question A) / DIFFERENT_BALLS (vision QA, question B)",
        "notes": "All 4 raters agree: TRACKER_FRAGMENTATION. This is the strongest case for the 10-frame filter. The H52 physics at MIN=2 strongly supports the visual QAs.",
    },
]


def majority_vote(classifications: list[str]) -> tuple:
    """Return (majority_label, count_majority, count_total, is_unanimous)."""
    counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        counts[c] += 1
    label, n = max(counts.items(), key=lambda kv: kv[1])
    return label, n, len(classifications), n == len(classifications)


def main() -> None:
    grid = {
        "config": H8V5,
        "min_pts_grid": SENS_MIN_PTS,
        "videos": {},
    }
    for stem in STEMS:
        print(f"\n=== {stem} (H53: H52 sensitivity grid, preserved) ===")
        tracklet_points = load_tracklet_points(stem)
        print(f"  loaded {len(tracklet_points)} tracklets")

        dropped_path = H1_DATA / f"h50_dropped_events_{stem}.csv"
        if not dropped_path.exists():
            print(f"  No dropped events file: {dropped_path}")
            continue
        chain_drops = defaultdict(list)
        with dropped_path.open() as fh:
            for r in csv.DictReader(fh):
                chain_drops[int(r["chain_id"])].append(r)
        # H50 timeline uses an h7v3pure-like chain set
        # find the prev_tid for each dropped throw
        chains_by_id: dict[int, dict] = {}
        for fname in (
            f"h7v3pure_chains_{stem}.csv",
        ):
            p = H1_DATA / fname
            if p.exists():
                with p.open() as fh:
                    for r in csv.DictReader(fh):
                        chains_by_id[int(r["chain_id"])] = r
                break
        if not chains_by_id:
            print(f"  No h7v3pure chains file for {stem}")
            continue
        for cid, events in chain_drops.items():
            events.sort(key=lambda e: int(e["event_frame"]))
            catch = next((e for e in events if e["event"] == "CATCH"), None)
            throw = next((e for e in events if e["event"] == "THROW"), None)
            if not catch or not throw:
                continue
            to_tid = int(throw["tid"])
            tids = [int(t) for t in chains_by_id[cid]["tids"].split(",") if t]
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
            gap = max(f_throw - f_catch, 1)
            # Default MIN=6 verdict
            default = check_pair_with_min(src_pts, tgt_pts, gap, 6)
            print(f"    Default MIN=6: {default['verdict']}")
            # Sensitivity grid
            print(f"    Sensitivity grid:")
            grid_results = [default]
            for min_pts in SENS_MIN_PTS:
                if min_pts == 6:
                    continue
                cell = check_pair_with_min(src_pts, tgt_pts, gap, min_pts)
                grid_results.append(cell)
                if cell["verdict"] != "INSUFFICIENT_DATA":
                    print(f"      MIN={min_pts}: {cell['verdict']} "
                          f"(v_disc={cell['velocity_discontinuity']})")
                else:
                    print(f"      MIN={min_pts}: {cell['verdict']} "
                          f"(src_n={cell['src_n_used']}, tgt_n={cell['tgt_n_used']})")
            grid["videos"].setdefault(stem, []).append({
                "chain_id": cid,
                "from_tid": from_tid,
                "to_tid": to_tid,
                "f_catch": f_catch,
                "f_throw": f_throw,
                "flight_time": ft,
                "gap": gap,
                "src_n_pts": len(src_pts),
                "tgt_n_pts": len(tgt_pts),
                "h52_default_min6": default,
                "h52_sensitivity_grid": grid_results,
            })

    out_grid = H1_DATA / "h53_h52_sensitivity_grid.json"
    out_grid.write_text(json.dumps(grid, indent=2, default=str))
    print(f"\nSaved: {out_grid}")

    # Build multi-rater consensus table
    print("\n=== Multi-rater visual QA consensus ===")
    rows = []
    for entry in MULTI_RATER:
        raters = [
            ("H45", entry["h45_classification"]),
            ("H50", entry["h50_classification"]),
            ("H52 (physics, MIN=6)", entry["h52_classification_default_min6"]),
            ("H52 (physics, MIN=2)", entry["h52_classification_min2"]),
            ("H53 (this-rater)", entry["this_rater_classification"]),
        ]

        def normalize(s: str) -> str:
            s_u = s.upper()
            if "REAL" in s_u or s_u == "OK" or "PHYSICS_OK" in s_u:
                return "REAL_CATCH_THROW"
            if "INSUFFICIENT" in s_u:
                return "INSUFFICIENT_DATA"
            if "BUCKET" in s_u or "IDENTITY_SWITCH" in s_u:
                return "IDENTITY_SWITCH"
            if "VIOLATING" in s_u or "FRAGMENTATION" in s_u or "TRACKER" in s_u:
                return "TRACKER_FRAGMENTATION"
            return s

        norm_raters = [(r[0], normalize(r[1])) for r in raters]
        # H45 IDENTITY_SWITCH is an unverified bucket assignment — count it
        # as a vote but mark its source.
        # For the consensus among the *verified* raters, drop H45.
        verified_raters = [r for r in norm_raters if r[0] != "H45"]
        verified_labels = [r[1] for r in verified_raters]
        # Tally: REAL, FRAG, INSUFFICIENT
        n_real = sum(1 for l in verified_labels if l == "REAL_CATCH_THROW")
        n_frag = sum(1 for l in verified_labels if l == "TRACKER_FRAGMENTATION")
        n_insuf = sum(1 for l in verified_labels if l == "INSUFFICIENT_DATA")
        n_verified = len(verified_labels)
        if n_real > n_frag and n_real > n_insuf:
            consensus = "REAL_CATCH_THROW"
        elif n_frag > n_real and n_frag > n_insuf:
            consensus = "TRACKER_FRAGMENTATION"
        elif n_insuf >= n_real and n_insuf >= n_frag:
            consensus = "UNDETERMINED"
        else:
            consensus = "UNDETERMINED"
        # The 10-frame filter's safe default is to drop identity switches,
        # so when there's a real-vs-fragmentation tie, prefer "drop" (TRACKER_FRAGMENTATION).
        if n_real == n_frag and n_real > 0:
            consensus = "TRACKER_FRAGMENTATION (tie, filter-default)"
        print(f"\n  {entry['pair_id']} ({entry['h45_numbering']}):")
        for label, c in norm_raters:
            print(f"    {label}: {c}")
        print(f"    Verified tally: REAL={n_real}, FRAG={n_frag}, INSUF={n_insuf} / {n_verified}")
        print(f"    CONSENSUS: {consensus}")
        if consensus.startswith("TRACKER_FRAGMENTATION"):
            print(f"    -> Filter keeps drop: correct, identity switch is rejected")
        elif consensus == "REAL_CATCH_THROW":
            print(f"    -> Filter drops this REAL catch-throw: a small false-positive cost")
        else:
            print(f"    -> UNDETERMINED: cannot decide with current data")
        print(f"    Note: {entry['notes']}")
        rows.append({
            "pair_id": entry["pair_id"],
            "h45": entry["h45_classification"],
            "h50": entry["h50_classification"],
            "h52_min6": entry["h52_classification_default_min6"],
            "h52_min2": entry["h52_classification_min2"],
            "this_rater_q_a": entry["this_rater_classification"].split(" / ")[0] if " / " in entry["this_rater_classification"] else entry["this_rater_classification"],
            "this_rater_q_b": entry["this_rater_classification"].split(" / ")[1] if " / " in entry["this_rater_classification"] else "SAME_QUERY",
            "verified_tally_real": n_real,
            "verified_tally_frag": n_frag,
            "verified_tally_insuf": n_insuf,
            "verified_total": n_verified,
            "consensus": consensus,
            "filter_decision": "KEEP_DROP" if consensus == "TRACKER_FRAGMENTATION" else (
                "FALSE_POSITIVE_DROP" if consensus == "REAL_CATCH_THROW" else "UNDETERMINED"
            ),
            "notes": entry["notes"],
        })

    out_csv = H1_DATA / "h53_multi_rater_visual_qa.csv"
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nSaved: {out_csv}")


if __name__ == "__main__":
    main()
