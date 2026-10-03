#!/usr/bin/env python3
"""E6b: widened candidate universe (gap<=30) with ballistic scoring.

Generates all eligible source->candidate pairs up to MAX_GAP frames using the
validated legacy tracklet data, scores them with bal8 (and cv2 as reference),
then evaluates:

1. Coverage: how many rank-1 links per gap bucket under a calibrated
   k-dependent acceptance gate (bal8 error <= q90(k) from E4).
2. Regression risk: for the 113 labeled pairs, does their rank WORSEN when
   longer-gap competitors join the pool? (new competitors can steal rank-1)
3. Global assignment over the widened pool (successor formulation), conflicts,
   and chain stats.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

BASE = Path(__file__).resolve().parents[1]
LEGACY = BASE / "data" / "legacy_csv"
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}
MAX_GAP = 30
TIME_SCALE = 30.0
# bal8 error q90 by gap from E4 synthetic benchmark (calibration curve):
GATE_Q90 = {2: 6.9, 4: 16.5, 6: 31.0, 10: 65.6, 15: 108.6, 20: 210.1, 30: 453.1}


def load_legacy(path: Path) -> dict[int, list[tuple[int, float, float]]]:
    tracks: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            tracks[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {tid: sorted(pts) for tid, pts in tracks.items()}


def bal8_predict(pts, qframe):
    wpts = pts[-8:]
    if len(wpts) < 3:
        return None
    frames = np.array([p[0] for p in wpts], dtype=float)
    xs = np.array([p[1] for p in wpts], dtype=float)
    ys = np.array([p[2] for p in wpts], dtype=float)
    t_ref = float(frames.mean())
    tau = (frames - t_ref) / TIME_SCALE
    tq = (qframe - t_ref) / TIME_SCALE
    try:
        cx = np.polyfit(tau, xs, 1)
        cy = np.polyfit(tau, ys, 2)
        return float(np.polyval(cx, tq)), float(np.polyval(cy, tq))
    except (np.linalg.LinAlgError, Warning):
        return None


def cv2_predict(pts, qframe):
    if len(pts) < 2:
        return None
    (f1, x1, y1), (f2, x2, y2) = pts[-2], pts[-1]
    dt = f2 - f1
    if dt <= 0:
        return None
    h = qframe - f2
    return x2 + (x2 - x1) / dt * h, y2 + (y2 - y1) / dt * h


def gate_for(gap: int) -> float:
    ks = sorted(GATE_Q90)
    for k in ks:
        if gap <= k:
            return GATE_Q90[k]
    return GATE_Q90[ks[-1]]


def main() -> None:
    report_lines = [
        "# E6b: widened candidate universe (gap<=30), ballistic scoring",
        "",
    ]
    totals = defaultdict(int)
    for stem, video_key in STEMS.items():
        tracks = load_legacy(LEGACY / f"{stem}.csv")
        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh) if r["video"] == video_key
            }
        # shipped narrow-universe ranks for regression comparison
        shipped_rank = {}
        with (SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
            for row in csv.DictReader(fh):
                shipped_rank[
                    (int(row["source_tracklet"]), int(row["candidate_tracklet"]))
                ] = int(row["candidate_rank"])

        # generate wide universe
        cand_rows = []
        for sid in sorted(tracks):
            sp = tracks[sid]
            if len(sp) < 3:
                continue
            end_f = sp[-1][0]
            for cid in sorted(tracks):
                if cid == sid:
                    continue
                cp = tracks[cid]
                if not cp or cp[0][0] <= end_f:
                    continue
                gap = cp[0][0] - end_f - 1
                if gap > MAX_GAP:
                    continue
                qb = bal8_predict(sp, cp[0][0])
                qc = cv2_predict(sp, cp[0][0])
                err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
                err_c = math.hypot(qc[0] - cp[0][1], qc[1] - cp[0][2]) if qc else None
                cand_rows.append({
                    "sid": sid, "cid": cid, "gap": gap,
                    "bal8": err_b, "cv2": err_c,
                    "label": labels.get((sid, cid), ""),
                    "shipped_rank": shipped_rank.get((sid, cid)),
                })

        # rank within source under bal8
        by_source = defaultdict(list)
        for r in cand_rows:
            by_source[r["sid"]].append(r)
        for group in by_source.values():
            group.sort(key=lambda r: (
                r["bal8"] if r["bal8"] is not None else float("inf"),
                r["cid"],
            ))
            for pos, r in enumerate(group, start=1):
                r["rank"] = pos

        # coverage by gap bucket among rank-1 accepted under calibrated gate
        bucket_stats = defaultdict(lambda: {"rank1": 0, "accepted": 0})
        for group in by_source.values():
            if not group:
                continue
            top = group[0]
            b = min((k for k in sorted(GATE_Q90) if top["gap"] <= k), default=30)
            bucket_stats[b]["rank1"] += 1
            if top["bal8"] is not None and top["bal8"] <= gate_for(top["gap"]):
                bucket_stats[b]["accepted"] += 1
        report_lines.append(f"## {stem}")
        report_lines.append("")
        report_lines.append("| gap bucket | rank-1 sources | accepted under calib gate |")
        report_lines.append("|---|---|---|")
        for b in sorted(bucket_stats):
            s = bucket_stats[b]
            totals[f"rank1_{b}"] += s["rank1"]
            totals[f"acc_{b}"] += s["accepted"]
            report_lines.append(f"| <= {b} | {s['rank1']} | {s['accepted']} |")

        # regression analysis on labeled pairs
        worse = same = better = 0
        stolen_examples = []
        for r in cand_rows:
            if not r["label"]:
                continue
            old_rank = r["shipped_rank"]
            new_rank = r["rank"]
            if old_rank is None:
                continue
            if new_rank > old_rank:
                worse += 1
                if old_rank == 1 and new_rank > 1:
                    thief = next(
                        (g for g in by_source[r["sid"]] if g["cid"] != r["cid"] and g["gap"] > 10),
                        None,
                    )
                    stolen_examples.append({
                        "pair": (r["sid"], r["cid"]), "label": r["label"],
                        "old": old_rank, "new": new_rank,
                        "thief_gap": thief["gap"] if thief else None,
                        "thief_err": round(thief["bal8"], 1) if thief else None,
                        "own_err": round(r["bal8"], 1) if r["bal8"] is not None else None,
                    })
            elif new_rank < old_rank:
                better += 1
            else:
                same += 1
        report_lines.append("")
        report_lines.append(
            f"labeled-pair rank changes vs shipped universe: worse={worse} "
            f"same={same} better={better}"
        )
        report_lines.append(f"stolen rank-1 examples: {json.dumps(stolen_examples[:12], default=list)}")

        # global successor assignment over widened pool with calibrated gates
        all_ids = sorted(tracks)
        n = len(all_ids)
        idx = {t: i for i, t in enumerate(all_ids)}
        cost = np.full((n, 2 * n), 1e9)
        cost[:, n:] = [gate_for(30)] * n
        for r in cand_rows:
            v = r["bal8"]
            if v is None or v >= gate_for(r["gap"]):
                continue
            si, ci = idx[r["sid"]], idx[r["cid"]]
            if cost[si, ci] > v:
                cost[si, ci] = v
        ri, ci = linear_sum_assignment(cost)
        links = {(all_ids[a], all_ids[b]) for a, b in zip(ri, ci)
                 if b < n and cost[a, b] < 1e9}
        conf = len(links) - len({c for _, c in links})
        tp = sum(1 for r in cand_rows if (r["sid"], r["cid"]) in links and r["label"] == "correct")
        fp = sum(1 for r in cand_rows if (r["sid"], r["cid"]) in links and r["label"] == "wrong")
        new_links = [l for l in links if l not in shipped_rank]
        report_lines.append("")
        report_lines.append(
            f"global assignment over wide pool: links={len(links)} conflicts={conf} "
            f"labeled-tp={tp} labeled-fp={fp} new-beyond-shipped={len(new_links)}"
        )
        totals["links"] += len(links)
        totals["conflicts"] += conf
        totals["new_links"] += len(new_links)
        report_lines.append("")

    header = [
        "TOTALS across videos:",
        f"  rank1/accepted per bucket: "
        + ", ".join(f"{k}={v}" for k, v in sorted(totals.items())),
    ]
    print("\n".join(header))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "e6b_report.md").write_text("\n".join(report_lines + header) + "\n")
    print(f"wrote reports/e6b_report.md")


if __name__ == "__main__":
    main()
