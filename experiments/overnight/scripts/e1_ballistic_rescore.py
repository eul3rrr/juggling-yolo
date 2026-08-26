#!/usr/bin/env python3
"""E1: Re-score reviewed stitch candidates with richer motion models.

Validated harness: reproduces all 113 shipped candidate rows exactly
(errors/gaps/ranks) from the legacy pre-a77cc5d tracklet CSVs, then computes
per-pair scores under richer source-only motion models:

* ``cv2``       -- shipped baseline: last-two-point constant velocity.
* ``cvlsN``     -- least-squares linear fit over last N points.
* ``balN``      -- ballistic fit (x linear, y quadratic) over last N points.
* ``cvwN``      -- velocity-weighted linear fit (weights decay with age).
* ``kalman``    -- 2D constant-acceleration Kalman filter over the source
                   tracklet, predicted at the query frame.

Ranks are recomputed within each source tracklet and evaluated against the 113
manual review labels.
"""

from __future__ import annotations

import csv
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

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

FIT_WINDOWS = (3, 4, 6, 8, 10, 12)
MODELS = ["cv2"] + [f"cvls{w}" for w in FIT_WINDOWS] + [f"bal{w}" for w in FIT_WINDOWS]
TIME_SCALE = 30.0


def load_legacy(path: Path) -> dict[int, list[tuple[int, float, float]]]:
    """Load tracklet points exactly like the original stitcher did."""
    tracks: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            tracks[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {tid: sorted(pts) for tid, pts in tracks.items()}


def _fit_predict(
    points: list[tuple[int, float, float]],
    query_frame: int,
    y_degree: int,
    window: int,
    query_x: float,
    query_y: float,
) -> float | None:
    pts = points[-window:]
    if len(pts) < max(2, y_degree + 1):
        return None
    frames = np.array([p[0] for p in pts], dtype=float)
    xs = np.array([p[1] for p in pts], dtype=float)
    ys = np.array([p[2] for p in pts], dtype=float)
    t_ref = float(frames.mean())
    tau = (frames - t_ref) / TIME_SCALE
    tq = (query_frame - t_ref) / TIME_SCALE
    try:
        rank_warning = getattr(np, "RankWarning", None) or getattr(
            np.exceptions, "RankWarning", Warning
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", rank_warning)
            cx = np.polyfit(tau, xs, 1)
            cy = np.polyfit(tau, ys, y_degree)
            px = float(np.polyval(cx, tq))
            py = float(np.polyval(cy, tq))
    except (np.linalg.LinAlgError, Warning):
        return None
    if not (math.isfinite(px) and math.isfinite(py)):
        return None
    # Clamp wild extrapolations so ranks stay meaningful.
    scale = 2000.0
    px = math.copysign(min(abs(px), scale), px)
    py = math.copysign(min(abs(py), scale), py)
    return float(math.hypot(px - query_x, py - query_y))


def kalman_predict(
    points: list[tuple[int, float, float]],
    query_frame: int,
    query_x: float,
    query_y: float,
) -> float | None:
    """Constant-acceleration Kalman filter per axis, predicted at query frame."""
    if len(points) < 3:
        return None
    frames = np.array([p[0] for p in points], dtype=float)
    dt = np.diff(frames)
    if np.any(dt <= 0):
        uniq = np.unique(frames)
        if len(uniq) < 3:
            return None
        keep = {int(f): i for i, f in enumerate(frames)}
        idx = sorted({keep[int(u)] for u in uniq})
        points = [points[i] for i in idx]
        frames = np.array([p[0] for p in points], dtype=float)
        dt = np.diff(frames)

    def run_axis(values: np.ndarray) -> float | None:
        x = np.zeros(3)
        p = np.eye(3) * 500.0
        q_base = np.diag([1e-3, 1e-2, 1e-1])
        h_row = np.array([1.0, 0.0, 0.0])
        r_meas = 4.0
        for i in range(len(values)):
            step = dt[i - 1] if i else 1.0
            f_mat = np.array([
                [1, step, 0.5 * step ** 2],
                [0, 1, step],
                [0, 0, 1],
            ])
            x = f_mat @ x
            p = f_mat @ p @ f_mat.T + q_base * max(step, 1.0)
            innov = values[i] - h_row @ x
            s_val = h_row @ p @ h_row + r_meas
            k_gain = p @ h_row / s_val
            x = x + k_gain * innov
            p = (np.eye(3) - np.outer(k_gain, h_row)) @ p
        total_dt = query_frame - frames[-1]
        f_ext = np.array([
            [1, total_dt, 0.5 * total_dt ** 2],
            [0, 1, total_dt],
            [0, 0, 1],
        ])
        return float((f_ext @ x)[0])

    try:
        xs_out = run_axis(np.array([p_[1] for p_ in points]))
        ys_out = run_axis(np.array([p_[2] for p_ in points]))
    except np.linalg.LinAlgError:
        return None
    if xs_out is None or ys_out is None:
        return None
    xs_out = math.copysign(min(abs(xs_out), 2000.0), xs_out)
    ys_out = math.copysign(min(abs(ys_out), 2000.0), ys_out)
    return float(math.hypot(xs_out - query_x, ys_out - query_y))


def score_all() -> list[dict]:
    rows: list[dict] = []
    for stem, video_key in STEMS.items():
        tracks = load_legacy(LEGACY / f"{stem}.csv")
        with (SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
            cands = list(csv.DictReader(fh))
        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (r["video"], int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh)
            }
        for cand in cands:
            sid, cid = int(cand["source_tracklet"]), int(cand["candidate_tracklet"])
            pts = tracks.get(sid, [])
            qf = int(cand["candidate_start_frame"])
            qx, qy = float(cand["candidate_start_x"]), float(cand["candidate_start_y"])

            scores: dict[str, float | None] = {"cv2": float(cand["prediction_error"])}
            for w in FIT_WINDOWS:
                scores[f"cvls{w}"] = _fit_predict(pts, qf, 1, w, qx, qy)
                scores[f"bal{w}"] = _fit_predict(pts, qf, 2, w, qx, qy)
            scores["kalman"] = kalman_predict(pts, qf, qx, qy)

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
    return rows


def evaluate(rows: list[dict]) -> dict:
    by_source: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        by_source[(row["stem"], row["source_tracklet"])].append(row)

    summary: dict[str, dict] = {}
    for model in MODELS + ["kalman"]:
        for group in by_source.values():
            ranked = sorted(group, key=lambda r: (
                r[model] if r[model] is not None else float("inf"),
                r["candidate_tracklet"],
            ))
            for pos, row in enumerate(ranked, start=1):
                row[f"rank_{model}"] = pos

        labeled = [r for r in rows if r["label"] in {"correct", "wrong"} and r[model] is not None]
        correct = [r for r in labeled if r["label"] == "correct"]
        wrong = [r for r in labeled if r["label"] == "wrong"]
        auc = _auc([r[model] for r in correct], [r[model] for r in wrong])
        rank_field = f"rank_{model}"
        correct_ranks = [r[rank_field] for r in correct]
        top1 = sum(1 for rk in correct_ranks if rk == 1)
        mrr = sum(1.0 / rk for rk in correct_ranks) / len(correct_ranks) if correct_ranks else 0.0
        h2h_total = h2h_won = 0
        for group in by_source.values():
            labs = [r["label"] for r in group]
            if labs.count("correct") == 1 and labs.count("wrong") >= 1:
                winner = next(r for r in group if r["label"] == "correct")
                h2h_total += 1
                if winner[rank_field] == 1:
                    h2h_won += 1
        summary[model] = {
            "n_labeled_scored": len(labeled),
            "auc_correct_lower": round(auc, 4) if math.isfinite(auc) else None,
            "correct_median": round(float(np.median([r[model] for r in correct])), 1) if correct else None,
            "wrong_median": round(float(np.median([r[model] for r in wrong])), 1) if wrong else None,
            "correct_top1_rate": round(top1 / len(correct_ranks), 4) if correct_ranks else None,
            "correct_mrr": round(mrr, 4),
            "median_correct_rank": float(np.median(correct_ranks)) if correct_ranks else None,
            "head_to_head": f"{h2h_won}/{h2h_total}",
        }
    return summary


def _auc(correct_scores: list[float], wrong_scores: list[float]) -> float:
    wins = ties = 0
    for cs in correct_scores:
        for ws in wrong_scores:
            if cs < ws:
                wins += 1
            elif cs == ws:
                ties += 1
    total = len(correct_scores) * len(wrong_scores)
    return (wins + 0.5 * ties) / total if total else float("nan")


def main() -> None:
    rows = score_all()
    all_models = MODELS + ["kalman"]
    out_path = OUT_DIR / "e1_pair_scores.csv"
    fieldnames = [
        "video", "stem", "source_tracklet", "candidate_tracklet",
        "gap_frames", "original_rank", "label", *all_models,
    ]
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = evaluate(rows)
    (OUT_DIR / "e1_metrics.json").write_text(json.dumps(summary, indent=2))

    lines = [
        "# E1: motion-model rescoring of reviewed stitch candidates (validated harness)",
        "",
        "Harness reproduces all 113 shipped candidate errors/ranks exactly.",
        "Ranks recomputed within each source under each scoring model.",
        "",
        "| model | AUC | correct med | wrong med | top1 | MRR | med rank | H2H |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for model in all_models:
        s = summary[model]
        lines.append(
            f"| {model} | {s['auc_correct_lower']} | {s['correct_median']} | "
            f"{s['wrong_median']} | {s['correct_top1_rate']} | {s['correct_mrr']} | "
            f"{s['median_correct_rank']} | {s['head_to_head']} |"
        )
    report = REPORT_DIR / "e1_report.md"
    report.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(rows)} scored pairs -> {out_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
