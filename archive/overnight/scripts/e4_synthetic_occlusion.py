#!/usr/bin/env python3
"""E4: synthetic occlusion benchmark for wide-gap stitch feasibility.

Takes clean fully-observed runs (dt==1, observed=1, length>=MIN_RUN) from the
regenerated tracklet CSVs, deletes k-frame windows to synthesize occlusions,
and asks: ranking the true continuation against ALL competing observations
near the re-entry frame, how often does each motion model put it first?

Outputs:
* top1/top3 accuracy vs gap k per scoring model;
* empirical error distributions vs k (calibration for sigma(gap) gates);
* JSON + markdown report.

No manual labels involved; the cut location IS the ground truth.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"

STEMS = {
    "identical_balls_trick_000_018": 59.94,
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 59.94,
}
MIN_RUN = 12
CUT_STRIDE = 4
GAPS = (2, 4, 6, 10, 15, 20, 30)
MODELS = ("cv2", "bal8", "kalman")
TIME_SCALE = 30.0
COMPETITOR_FRAME_TOL = 1


def load_observed(stem: str) -> dict[int, list[tuple[int, float, float]]]:
    tracks: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    path = SHIPPED / f"{stem}_norfair_dt50_hc5.csv"
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed") != "1":
                continue
            tracks[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {t: sorted(pts) for t, pts in tracks.items()}


def clean_runs(pts: list[tuple[int, float, float]]) -> list[list[tuple[int, float, float]]]:
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
    return runs


def fit_predict(
    pts: list[tuple[int, float, float]], qframe: int
) -> tuple[float, float] | None:
    """Return (px, py) prediction at qframe from x-lin/y-quad fit, else None."""
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


def cv_predict(pts: list[tuple[int, float, float]], qframe: int) -> tuple[float, float] | None:
    if len(pts) < 2:
        return None
    (f1, x1, y1), (f2, x2, y2) = pts[-2], pts[-1]
    dt = f2 - f1
    if dt <= 0:
        return None
    h = qframe - f2
    return x2 + (x2 - x1) / dt * h, y2 + (y2 - y1) / dt * h


def kalman_pred(pts: list[tuple[int, float, float]], qframe: int) -> tuple[float, float] | None:
    if len(pts) < 4:
        return None
    frames = np.array([p[0] for p in pts[-14:]], dtype=float)

    def axis(vals: np.ndarray) -> float:
        x = np.zeros(3)
        p = np.eye(3) * 500.0
        q_b = np.diag([1e-3, 1e-2, 1e-1])
        h_row = np.array([1.0, 0.0, 0.0])
        r_m = 4.0
        for i in range(len(vals)):
            step = frames[i] - frames[i - 1] if i else 1.0
            f_mat = np.array([[1, step, 0.5 * step**2], [0, 1, step], [0, 0, 1]])
            x = f_mat @ x
            p = f_mat @ p @ f_mat.T + q_b * max(step, 1.0)
            innov = vals[i] - h_row @ x
            s_val = h_row @ p @ h_row + r_m
            k_g = p @ h_row / s_val
            x = x + k_g * innov
            p = (np.eye(3) - np.outer(k_g, h_row)) @ p
        total = qframe - frames[-1]
        f_ext = np.array([[1, total, 0.5 * total**2], [0, 1, total], [0, 0, 1]])
        return float((f_ext @ x)[0])

    try:
        return (
            axis(np.array([q[1] for q in pts[-14:]])),
            axis(np.array([q[2] for q in pts[-14:]])),
        )
    except np.linalg.LinAlgError:
        return None


PREDICTORS = {"cv2": cv_predict, "bal8": fit_predict, "kalman": kalman_pred}


def main() -> None:
    rng = np.random.default_rng(20260826)
    per_model = {m: defaultdict(lambda: {"top1": 0, "top3": 0, "n": 0, "errs": []})
                 for m in MODELS}
    n_cuts_total = 0

    for stem, fps in STEMS.items():
        tracks = load_observed(stem)
        # competitor index: frame -> list of (track_id, x, y)
        by_frame: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
        for tid, pts in tracks.items():
            for f, x, y in pts:
                by_frame[f].append((tid, x, y))

        for tid, pts in tracks.items():
            for run in clean_runs(pts):
                run_len = len(run)
                for start_off in range(4, run_len - 2, CUT_STRIDE):
                    left_ctx = [p for p in run[:start_off]][-12:]
                    if len(left_ctx) < 3:
                        continue
                    cut_a_frame = run[start_off - 1][0] if start_off else left_ctx[-1][0]
                    for k in GAPS:
                        cut_b = cut_a_frame + k
                        true_pt = next((p for p in run[start_off:] if p[0] == cut_b), None)
                        if true_pt is None:
                            continue
                        competitors = sorted(set(by_frame.get(cut_b, [])))
                        if len(competitors) < 2:
                            continue
                        n_cuts_total += 1
                        for model, fn in PREDICTORS.items():
                            pred = fn(left_ctx, cut_b)
                            if pred is None:
                                continue
                            px, py = pred
                            scored = []
                            true_err = None
                            for j, (t2, x2, y2) in enumerate(competitors):
                                d = math.hypot(px - x2, py - y2)
                                scored.append((d, t2, j))
                                if t2 == tid:
                                    true_err = d
                            if true_err is None:
                                continue
                            scored.sort()
                            rank = next(
                                i + 1 for i, (d, t2, j) in enumerate(scored) if t2 == tid
                            )
                            bucket = per_model[model][k]
                            bucket["n"] += 1
                            bucket["errs"].append(true_err)
                            bucket["top1"] += rank == 1
                            bucket["top3"] += rank <= 3

    summary = {}
    for model, buckets in per_model.items():
        summary[model] = {}
        for k in sorted(buckets):
            b = buckets[k]
            errs = np.array(b["errs"]) if b["errs"] else np.array([np.nan])
            summary[model][k] = {
                "n": b["n"],
                "top1": round(b["top1"] / b["n"], 4) if b["n"] else None,
                "top3": round(b["top3"] / b["n"], 4) if b["n"] else None,
                "err_median": round(float(np.nanmedian(errs)), 1),
                "err_q90": round(float(np.nanpercentile(errs, 90)), 1),
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e4_synthetic_occlusion.json").write_text(
        json.dumps({"n_cuts": n_cuts_total, "summary": summary}, indent=2)
    )

    lines = [
        "# E4: synthetic occlusion benchmark",
        "",
        f"Cuts evaluated: {n_cuts_total} (clean observed runs >= {MIN_RUN} frames).",
        "",
        "| model | gap | n | top1 | top3 | err med | err q90 |",
        "|---|---|---|---|---|---|---|",
    ]
    for model in MODELS:
        for k in sorted(summary[model], key=int):
            s = summary[model][k]
            lines.append(
                f"| {model} | {k} | {s['n']} | {s['top1']} | {s['top3']} | "
                f"{s['err_median']} | {s['err_q90']} |"
            )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "e4_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
