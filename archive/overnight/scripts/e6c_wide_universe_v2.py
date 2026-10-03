#!/usr/bin/env python3
"""E6c: widened universe v2 -- phantom-free data, per-video calibration,
gap-normalized assignment costs.

Fixes over E6b:
1. Tracklet points restricted to the observed-only join (no Norfair phantom
   estimates), same join as e3_shared_gravity.observed_masked_legacy.
2. Calibration gates computed PER VIDEO by running the E4 synthetic-cut
   protocol on that video's observed data.
3. Assignment cost = err / q90(gap): measured surprise in noise units, so
   long-gap edges can compete fairly with short-gap edges.
"""

from __future__ import annotations

import csv
import json
import math
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
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
CAL_GAPS = (2, 4, 6, 10, 15, 20, 30)


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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cx = np.polyfit(tau, xs, 1)
            cy = np.polyfit(tau, ys, 2)
            return float(np.polyval(cx, tq)), float(np.polyval(cy, tq))
    except np.linalg.LinAlgError:
        return None


def calibrate_per_video(tracks: dict) -> dict[int, float]:
    """E4-style synthetic cuts on THIS video; return q90(bal8 err) by gap."""
    by_frame: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    for tid, pts in tracks.items():
        for f, x, y in pts:
            by_frame[f].append((tid, x, y))
    errs_by_gap: dict[int, list[float]] = defaultdict(list)
    MIN_RUN = 12
    for tid, pts in tracks.items():
        runs = []
        cur = [pts[0]]
        for prev, pt in zip(pts[:-1], pts[1:]):
            if pt[0] - prev[0] == 1:
                cur.append(pt)
            else:
                if len(cur) >= MIN_RUN:
                    runs.append(cur)
                cur = [pt]
        if len(cur) >= MIN_RUN:
            runs.append(cur)
        run_frames = {p[0] for p in pts}
        for run in runs:
            n = len(run)
            for off in range(4, n - 2, 4):
                left = run[:off][-12:]
                if len(left) < 3:
                    continue
                cut_a = run[off - 1][0]
                pred = None
                last_ctx_len = len(left)
                for k in CAL_GAPS:
                    cut_b = cut_a + k
                    if cut_b not in run_frames:
                        continue
                    true_pt = next((p for p in run[off:] if p[0] == cut_b), None)
                    if true_pt is None:
                        continue
                    comps = by_frame.get(cut_b, [])
                    if len(comps) < 2:
                        continue
                    # context must end k frames before re-entry
                    if left[-1][0] != cut_b - k:
                        continue
                    pred = bal8_predict(left, cut_b)
                    if pred is None:
                        continue
                    d_true = math.hypot(pred[0] - true_pt[1], pred[1] - true_pt[2])
                    errs_by_gap[k].append(d_true)
                _ = last_ctx_len
    return {
        k: round(float(np.percentile(v, 90)), 1) if v else float("inf")
        for k, v in sorted(errs_by_gap.items())
    }


def gate_for(cal: dict[int, float], gap: int) -> float:
    ks = sorted(cal)
    for k in ks:
        if gap <= k and math.isfinite(cal[k]):
            return cal[k]
    best = max((v for v in cal.values() if math.isfinite(v)), default=float("nan"))
    return best


def main() -> None:
    master = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        cal = calibrate_per_video(tracks)
        print(f"[{stem}] per-video q90 calibration: {cal}")
        master[stem] = {"calibration": cal}

        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh) if r["video"] == video_key
            }
        shipped_rank = {}
        with (SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
            for row in csv.DictReader(fh):
                shipped_rank[(int(row["source_tracklet"]), int(row["candidate_tracklet"]))] = int(
                    row["candidate_rank"]
                )

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
                err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
                cand_rows.append({
                    "sid": sid, "cid": cid, "gap": gap, "bal8": err_b,
                    "label": labels.get((sid, cid), ""),
                    "shipped_rank": shipped_rank.get((sid, cid)),
                })

        by_source = defaultdict(list)
        for r in cand_rows:
            by_source[r["sid"]].append(r)
        for group in by_source.values():
            group.sort(key=lambda r: (
                r["bal8"] if r["bal8"] is not None else float("inf"), r["cid"]
            ))
            for pos, r in enumerate(group, 1):
                r["rank"] = pos

        # rank-1 acceptance under per-video calibrated gates
        accepted_rank1 = [
            g[0] for g in by_source.values()
            if g and g[0]["bal8"] is not None and g[0]["bal8"] <= gate_for(cal, g[0]["gap"])
        ]
        acc_correct = sum(1 for r in accepted_rank1 if r["label"] == "correct")
        acc_wrong = sum(1 for r in accepted_rank1 if r["label"] == "wrong")
        print(f"[{stem}] rank-1 accepted: n={len(accepted_rank1)} "
              f"correct={acc_correct} wrong={acc_wrong}")
        master[stem]["rank1_accepted"] = {
            "n": len(accepted_rank1), "correct": acc_correct, "wrong": acc_wrong}

        # theft analysis on labeled pairs
        thefts = []
        for group in by_source.values():
            for r in group:
                if not r["label"] or r["shipped_rank"] is None:
                    continue
                if r["rank"] > r["shipped_rank"]:
                    thieves = [g for g in group if g["cid"] != r["cid"]
                               and g["rank"] < r["rank"]]
                    nearest = min(thieves, key=lambda g: g["rank"]) if thieves else None
                    thefts.append({
                        "pair": [r["sid"], r["cid"]], "label": r["label"],
                        "old": r["shipped_rank"], "new": r["rank"],
                        "top_thief_gap": nearest["gap"] if nearest else None,
                        "top_thief_err": round(nearest["bal8"], 1) if nearest and nearest["bal8"] else None,
                    })
        n_worse = len(thefts)
        n_theft_wrong = sum(1 for t in thefts if t["label"] == "wrong")
        print(f"[{stem}] demotions: {n_worse} (of which wrong-labeled: {n_theft_wrong})")
        master[stem]["thefts"] = {"demoted": n_worse, "of_which_wrong": n_theft_wrong,
                                  "detail": thefts[:15]}

        # global assignment with gap-normalized costs
        all_ids = sorted(tracks)
        n_t = len(all_ids)
        idx = {t: i for i, t in enumerate(all_ids)}
        cost = np.full((n_t, 2 * n_t), 1e9)
        dummy_cost = 1.0
        cost[:, n_t:] = dummy_cost
        for r in cand_rows:
            v = r["bal8"]
            if v is None or v >= gate_for(cal, r["gap"]):
                continue
            rel = v / gate_for(cal, r["gap"])
            si, ci = idx[r["sid"]], idx[r["cid"]]
            if cost[si, ci] > rel:
                cost[si, ci] = rel
        ri, ci = linear_sum_assignment(cost)
        links = {(all_ids[a], all_ids[b]) for a, b in zip(ri, ci)
                 if b < n_t and cost[a, b] < 1e9}
        conf = len(links) - len({c for _, c in links})
        tp = sum(1 for r in cand_rows if (r["sid"], r["cid"]) in links and r["label"] == "correct")
        fp = sum(1 for r in cand_rows if (r["sid"], r["cid"]) in links and r["label"] == "wrong")
        beyond = sum(1 for l in links if l not in shipped_rank)
        print(f"[{stem}] global(normalized): links={len(links)} conflicts={conf} "
              f"tp={tp} fp={fp} new={beyond}")
        master[stem]["global"] = {
            "links": len(links), "conflicts": conf, "labeled_tp": tp,
            "labeled_fp": fp, "new_vs_shipped": beyond,
        }
        # chain stats
        succ = dict(links)
        preds = {c for _, c in links}
        chains = []
        visited = set()
        for s0 in sorted(succ):
            if s0 in preds or s0 in visited:
                continue
            ch = [s0]
            visited.add(s0)
            cur = succ.get(s0)
            while cur is not None and cur not in visited:
                ch.append(cur)
                visited.add(cur)
                cur = succ.get(cur)
            chains.append(ch)
        lens = [len(c) for c in chains]
        print(f"[{stem}] chains={len(chains)} max={max(lens) if lens else 0} "
              f"mean={round(float(np.mean(lens)), 2) if lens else 0}")
        master[stem]["chains"] = {"n": len(chains),
                                  "max": max(lens) if lens else 0,
                                  "mean": round(float(np.mean(lens)), 2) if lens else 0.0}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e6c_wide_v2.json").write_text(json.dumps(master, indent=2))

    lines = ["# E6c: widened universe v2 (observed-only, per-video calibration, normalized costs)", ""]
    for stem in STEMS:
        m = master[stem]
        lines.append(f"## {stem}")
        lines.append(f"- calibration q90: `{m['calibration']}`")
        ra = m["rank1_accepted"]
        lines.append(f"- rank-1 accepted under calibrated gates: {ra}")
        th = m["thefts"]
        lines.append(f"- demotions of labeled pairs: {th['demoted']} "
                     f"(wrong-labeled demoted: {th['of_which_wrong']})")
        g = m["global"]
        c = m["chains"]
        lines.append(f"- global assignment: {g}, chains: {c}")
        lines.append("")
    (REPORT_DIR / "e6c_report.md").write_text("\n".join(lines) + "\n")
    print("wrote reports/e6c_report.md")


if __name__ == "__main__":
    main()
