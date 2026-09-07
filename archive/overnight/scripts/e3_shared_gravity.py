#!/usr/bin/env python3
"""E3: shared-gravity constrained stitch rescoring.

Step 1 -- estimate one image-space vertical acceleration per video by fitting
quadratics to fully-observed (dt==1) 8-point windows inside every tracklet,
then taking the median acceleration across windows.

Step 2 -- score every reviewed stitch candidate with a y-model whose quadratic
coefficient is FIXED to the shared gravity (only intercept+slope fitted),
against the candidate start point. Compare against the unconstrained ballistic
baseline from E1 on the same labels.
"""

from __future__ import annotations

import csv
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

from e1_ballistic_rescore import (
    BASE,
    FIT_WINDOWS,
    LEGACY,
    SHIPPED,
    STEMS,
    TIME_SCALE,
    _fit_predict,
    evaluate,
    load_legacy,
)

OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"
G_WINDOWS = (6, 8, 12)


def observed_masked_legacy(stem: str) -> dict[int, list[tuple[int, float, float]]]:
    """Legacy points restricted to rows that survive into the regenerated
    observed-only CSV (join on frame+track_id+rounded center)."""
    tracks = load_legacy(LEGACY / f"{stem}.csv")
    current_observed = set()
    path = SHIPPED / f"{stem}_norfair_dt50_hc5.csv"
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed") == "1":
                key = (
                    int(row["frame"]),
                    int(row["track_id"]),
                    round(float(row["center_x"]), 3),
                    round(float(row["center_y"]), 3),
                )
                current_observed.add(key)
    masked: dict[int, list[tuple[int, float, float]]] = {}
    hit = miss = 0
    for tid, pts in tracks.items():
        kept = []
        for f, x, y in pts:
            if (f, tid, round(x, 3), round(y, 3)) in current_observed:
                kept.append((f, x, y))
                hit += 1
            else:
                miss += 1
        if kept:
            masked[tid] = kept
    print(f"[{stem}] observed join: kept={hit} dropped={miss}")
    return masked


def estimate_gravity(
    tracks: dict[int, list[tuple[int, float, float]]], window: int
) -> tuple[float, np.ndarray]:
    """Median image-space y-acceleration from dt==1 windows of ``window`` pts."""
    accels = []
    for pts in tracks.values():
        if len(pts) < window:
            continue
        frames = np.array([p[0] for p in pts])
        ys = np.array([p[2] for p in pts])
        for i in range(len(pts) - window + 1):
            f_win = frames[i : i + window]
            if np.any(np.diff(f_win) != 1):
                continue
            tau = f_win - f_win.mean()
            try:
                coef = np.polyfit(tau, ys[i : i + window], 2)
            except np.linalg.LinAlgError:
                continue
            accels.append(2.0 * coef[0])
    arr = np.array(accels)
    return float(np.median(arr)) if len(arr) else float("nan"), arr


def gravity_constrained_score(
    pts: list[tuple[int, float, float]],
    qframe: int,
    qx: float,
    qy: float,
    g_tau: float,
    window: int,
) -> float | None:
    """Predict with x~linear, y~c0+c1*t+(g/2)t^2 (g fixed); return px distance."""
    wpts = pts[-window:]
    if len(wpts) < 4:
        return None
    frames = np.array([p[0] for p in wpts], dtype=float)
    xs = np.array([p[1] for p in wpts], dtype=float)
    ys = np.array([p[2] for p in wpts], dtype=float)
    t_ref = float(frames.mean())
    tau = (frames - t_ref) / TIME_SCALE
    tq = (qframe - t_ref) / TIME_SCALE
    try:
        cx = np.polyfit(tau, xs, 1)
        resid = ys - 0.5 * g_tau * tau ** 2
        cy = np.polyfit(tau, resid, 1)
        px = float(np.polyval(cx, tq))
        py = float(np.polyval(cy, tq) + 0.5 * g_tau * tq ** 2)
    except (np.linalg.LinAlgError, Warning):
        return None
    if not (math.isfinite(px) and math.isfinite(py)):
        return None
    scale = 2000.0
    px = math.copysign(min(abs(px), scale), px)
    py = math.copysign(min(abs(py), scale), py)
    return float(math.hypot(px - qx, py - qy))


def main() -> None:
    rows = []
    gravity_info = {}
    fps_map = {"identical_balls_trick_000_018": 59.94,
               "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 59.94}
    for stem, video_key in STEMS.items():
        tracks_all = load_legacy(LEGACY / f"{stem}.csv")
        tracks_obs = observed_masked_legacy(stem)
        for gw in G_WINDOWS:
            g_all, arr_all = estimate_gravity(tracks_all, gw)
            g_obs, _ = estimate_gravity(tracks_obs, gw)
            fps = fps_map[stem]
            print(
                f"[{stem}] gw={gw}: n_windows={len(arr_all)} "
                f"g_median(all)={g_all:.3f} px/f^2 ({g_all * fps ** 2:.0f} px/s^2)  "
                f"g_median(obs-only)={g_obs:.3f}"
            )
            if gw == 8:
                gravity_info[stem] = {
                    "window": gw,
                    "n_windows": int(len(arr_all)),
                    "g_px_per_f2": round(g_all, 4),
                    "g_px_per_s2": round(g_all * fps ** 2, 1),
                    "g_obs_only_px_per_f2": round(g_obs, 4),
                    "g_q25": round(float(np.percentile(arr_all, 25)), 4),
                    "g_q75": round(float(np.percentile(arr_all, 75)), 4),
                }

        g_hat = gravity_info[stem]["g_px_per_f2"] / TIME_SCALE ** 2  # to tau units

        with (SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
            cands = list(csv.DictReader(fh))
        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (r["video"], int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh)
            }
        for cand in cands:
            sid, cid = int(cand["source_tracklet"]), int(cand["candidate_tracklet"])
            pts = tracks_all.get(sid, [])
            qf = int(cand["candidate_start_frame"])
            qx, qy = float(cand["candidate_start_x"]), float(cand["candidate_start_y"])
            scores: dict[str, float | None] = {}
            for w in FIT_WINDOWS:
                scores[f"gfix{w}"] = gravity_constrained_score(pts, qf, qx, qy, g_hat, w)
                scores[f"bal{w}"] = _fit_predict(pts, qf, 2, w, qx, qy)
            rows.append({
                "video": video_key,
                "stem": stem,
                "source_tracklet": sid,
                "candidate_tracklet": cid,
                "gap_frames": int(cand["gap_frames"]),
                "original_rank": int(cand["candidate_rank"]),
                "label": labels.get((video_key, sid, cid), ""),
                **scores,
            })

    models = (
        [f"gfix{w}" for w in FIT_WINDOWS] + [f"bal{w}" for w in FIT_WINDOWS]
    )
    summary = evaluate(rows, models)
    sub = {m: summary[m] for m in models}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "video", "stem", "source_tracklet", "candidate_tracklet",
        "gap_frames", "original_rank", "label", *models,
    ]
    with (OUT_DIR / "e3_pair_scores.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# E3: shared-gravity constrained stitching",
        "",
        f"Gravity estimates: ```json```",
        "",
        "| model | AUC | correct med | wrong med | top1 | MRR | med rank | H2H |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in models:
        s = sub[m]
        lines.append(
            f"| {m} | {s['auc_correct_lower']} | {s['correct_median']} | "
            f"{s['wrong_median']} | {s['correct_top1_rate']} | {s['correct_mrr']} | "
            f"{s['median_correct_rank']} | {s['head_to_head']} |"
        )
    report_text = "\n".join(lines) + "\n"
    report_text += "\n```json\n" + json.dumps(gravity_info, indent=2) + "\n```\n"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "e3_report.md").write_text(report_text)
    (OUT_DIR / "e3_gravity.json").write_text(json.dumps(gravity_info, indent=2))
    (OUT_DIR / "e3_metrics.json").write_text(json.dumps(sub, indent=2))
    print()
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
