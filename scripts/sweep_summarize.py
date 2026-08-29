#!/usr/bin/env python3
"""Summarize the yolo26l vs yolo26x confidence-threshold sweep.

For every (model, video, threshold) combination, read the detection CSV,
the Norfair tracklet CSV and the stitch candidate CSV and emit a single
row of summary metrics. Also computes the per-step "newly admitted"
detection count for 0.15->0.10, 0.10->0.075 and 0.075->0.05.

Output JSON and CSV are written next to the CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DETECTION_FIELDS = (
    "video", "frame", "time_seconds", "class_id", "class_name",
    "confidence", "x1", "y1", "x2", "y2", "center_x", "center_y",
    "width", "height",
)
NORFAIR_FIELDS = (
    "frame", "time_seconds", "track_id", "confidence",
    "center_x", "center_y", "observed",
)
STITCH_FIELDS = (
    "source_tracklet", "candidate_tracklet", "gap_frames",
    "predicted_x", "predicted_y", "candidate_start_x", "candidate_start_y",
    "prediction_error", "source_end_frame", "candidate_start_frame",
    "end_velocity_x", "end_velocity_y", "candidate_rank",
)


def _f(value: str) -> float:
    return float(value)


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing required fields: {sorted(missing)}")
        return rows


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[int(pos)]
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def detection_summary(rows: list[dict[str, str]], frame_count: int) -> dict:
    """Detect-count, frame distribution, confidence quantiles."""
    per_frame: Counter[int] = Counter()
    confidences: list[float] = []
    for row in rows:
        per_frame[int(row["frame"])] += 1
        confidences.append(_f(row["confidence"]))
    distribution = Counter()
    for n in per_frame.values():
        if n == 0:
            distribution[0] += 1
        elif n == 1:
            distribution[1] += 1
        elif n == 2:
            distribution[2] += 1
        elif n == 3:
            distribution[3] += 1
        else:
            distribution["4+"] += 1
    # Fill in zeros for bins that did not appear so the output is complete
    bin_filled = {**{k: 0 for k in (0, 1, 2, 3, "4+")}, **distribution}
    frames_with_any = len(per_frame)
    frames_with_zero = (frame_count - frames_with_any) if frame_count else 0
    bin_filled[0] = bin_filled.get(0, 0) + frames_with_zero
    bin_filled_str: dict[str, int] = {str(k): int(v) for k, v in bin_filled.items()}
    return {
        "total_detections": len(rows),
        "mean_per_frame": len(rows) / frame_count if frame_count else 0.0,
        "median_per_frame": statistics.median(per_frame.values()) if per_frame else 0.0,
        "frame_count_distribution": bin_filled_str,
        "confidence": {
            "mean": statistics.fmean(confidences) if confidences else 0.0,
            "median": statistics.median(confidences) if confidences else 0.0,
            "p25": _quantile(confidences, 0.25),
            "p75": _quantile(confidences, 0.75),
            "min": min(confidences) if confidences else 0.0,
            "max": max(confidences) if confidences else 0.0,
        },
    }


def norfair_summary(rows: list[dict[str, str]]) -> dict:
    """Per-track counts, observed frames, lifespans."""
    per_track_observed: Counter[int] = Counter()
    per_track_total: Counter[int] = Counter()
    total_obs = 0
    for row in rows:
        tid = int(row["track_id"])
        per_track_total[tid] += 1
        if int(row["observed"]) == 1:
            per_track_observed[tid] += 1
            total_obs += 1
    lifespans = list(per_track_total.values())
    observed_counts = list(per_track_observed.values())
    short_le_5 = sum(1 for o in observed_counts if o <= 5)
    short_le_10 = sum(1 for o in observed_counts if o <= 10)
    return {
        "n_unique_track_ids": len(per_track_total),
        "n_track_rows": len(rows),
        "observed_fraction": total_obs / len(rows) if rows else 0.0,
        "observed_per_track": {
            "median": statistics.median(observed_counts) if observed_counts else 0.0,
            "mean": statistics.fmean(observed_counts) if observed_counts else 0.0,
        },
        "lifespan": {
            "median": statistics.median(lifespans) if lifespans else 0.0,
            "max": max(lifespans) if lifespans else 0.0,
            "mean": statistics.fmean(lifespans) if lifespans else 0.0,
        },
        "short_tracks_le_5": short_le_5,
        "short_tracks_le_10": short_le_10,
    }


def stitch_summary(rows: list[dict[str, str]]) -> dict:
    """Stitch candidate / gap / rank-1 prediction-error distribution."""
    gap_values: list[int] = []
    rank1_errors: list[float] = []
    source_ids: set[str] = set()
    for row in rows:
        gap_values.append(int(row["gap_frames"]))
        source_ids.add(row["source_tracklet"])
        if int(row["candidate_rank"]) == 1:
            rank1_errors.append(_f(row["prediction_error"]))
    return {
        "n_candidates": len(rows),
        "n_source_tracklets_with_candidates": len(source_ids),
        "gap_distribution": {
            "median": statistics.median(gap_values) if gap_values else 0.0,
            "max": max(gap_values) if gap_values else 0,
            "mean": statistics.fmean(gap_values) if gap_values else 0.0,
        },
        "rank1_prediction_error": {
            "median": statistics.median(rank1_errors) if rank1_errors else 0.0,
            "p75": _quantile(rank1_errors, 0.75),
            "n": len(rank1_errors),
        },
    }


def step_new_detections(
    lower_rows: list[dict[str, str]],
    higher_rows: list[dict[str, str]],
) -> dict:
    """How many detections are admitted when dropping from higher to lower threshold.

    Identifies the new rows by (frame, center_x, center_y, confidence) so
    we can count them and describe where they fall in the video.
    """
    higher_keys = {
        (int(r["frame"]),
         round(_f(r["center_x"]), 2),
         round(_f(r["center_y"]), 2),
         round(_f(r["confidence"]), 4)): r
        for r in higher_rows
    }
    new_rows: list[dict[str, str]] = []
    for row in lower_rows:
        key = (int(row["frame"]),
               round(_f(row["center_x"]), 2),
               round(_f(row["center_y"]), 2),
               round(_f(row["confidence"]), 4))
        if key not in higher_keys:
            new_rows.append(row)
    confs = [_f(r["confidence"]) for r in new_rows]
    frame_buckets: Counter[str] = Counter()
    for r in new_rows:
        f = int(r["frame"])
        if f < 200:
            frame_buckets["0-199"] += 1
        elif f < 400:
            frame_buckets["200-399"] += 1
        elif f < 600:
            frame_buckets["400-599"] += 1
        elif f < 800:
            frame_buckets["600-799"] += 1
        else:
            frame_buckets["800+"] += 1
    return {
        "n_new": len(new_rows),
        "conf_mean": statistics.fmean(confs) if confs else 0.0,
        "conf_max": max(confs) if confs else 0.0,
        "frame_bucket_distribution": dict(frame_buckets),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-dir", type=Path,
                        default=PROJECT_ROOT / "detections" / "detector_seg_comparison" / "threshold_sweep")
    parser.add_argument("--videos", nargs="+", required=True,
                        help="Video stems (no .mp4).")
    parser.add_argument("--models", nargs="+", default=["yolo26l", "yolo26x"])
    parser.add_argument("--thresholds", nargs="+", default=["015", "010", "0075", "005"])
    parser.add_argument("--video-frame-counts", nargs="+", type=int, required=True)
    args = parser.parse_args()

    if len(args.videos) != len(args.video_frame_counts):
        raise ValueError("--videos and --video-frame-counts length must match")

    summary: dict[str, dict] = {}
    flat_rows: list[dict] = []
    for video, frame_count in zip(args.videos, args.video_frame_counts):
        for model in args.models:
            det_rows_by_thr: dict[str, list[dict[str, str]]] = {}
            for thr in args.thresholds:
                det_path = args.sweep_dir / f"{video}_{model}_classes-32_conf{thr}.csv"
                det_rows_by_thr[thr] = _read_csv(det_path, DETECTION_FIELDS)

            # New-detection deltas
            deltas: dict[str, dict] = {}
            deltas["015_to_010"] = step_new_detections(
                det_rows_by_thr["010"], det_rows_by_thr["015"])
            deltas["010_to_0075"] = step_new_detections(
                det_rows_by_thr["0075"], det_rows_by_thr["010"])
            deltas["0075_to_005"] = step_new_detections(
                det_rows_by_thr["005"], det_rows_by_thr["0075"])

            for thr in args.thresholds:
                key = f"{video}__{model}__conf{thr}"
                det_rows = det_rows_by_thr[thr]
                nf_path = args.sweep_dir / f"{video}_{model}_classes-32_conf{thr}_norfair_dt50_hc5.csv"
                st_path = args.sweep_dir / f"{video}_{model}_classes-32_conf{thr}_norfair_dt50_hc5_stitches.csv"
                summary[key] = {
                    "video": video,
                    "model": model,
                    "threshold_str": f"0.{thr[0:1]}{'0' if len(thr) == 3 else thr[1:]}",
                    "detection": detection_summary(det_rows, frame_count),
                    "norfair": norfair_summary(_read_csv(nf_path, NORFAIR_FIELDS)),
                    "stitch": stitch_summary(_read_csv(st_path, STITCH_FIELDS)),
                }
                det = summary[key]["detection"]
                norf = summary[key]["norfair"]
                stch = summary[key]["stitch"]
                flat_rows.append({
                    "video": video,
                    "model": model,
                    "threshold": f"conf{thr}",
                    "total_detections": det["total_detections"],
                    "mean_per_frame": round(det["mean_per_frame"], 3),
                    "median_per_frame": det["median_per_frame"],
                    "frames_0": det["frame_count_distribution"]["0"],
                    "frames_1": det["frame_count_distribution"]["1"],
                    "frames_2": det["frame_count_distribution"]["2"],
                    "frames_3": det["frame_count_distribution"]["3"],
                    "frames_4+": det["frame_count_distribution"]["4+"],
                    "conf_mean": round(det["confidence"]["mean"], 3),
                    "conf_p25": round(det["confidence"]["p25"], 3),
                    "conf_p75": round(det["confidence"]["p75"], 3),
                    "n_unique_track_ids": norf["n_unique_track_ids"],
                    "track_rows": norf["n_track_rows"],
                    "observed_fraction": round(norf["observed_fraction"], 3),
                    "observed_median": norf["observed_per_track"]["median"],
                    "observed_mean": round(norf["observed_per_track"]["mean"], 1),
                    "lifespan_median": norf["lifespan"]["median"],
                    "lifespan_max": norf["lifespan"]["max"],
                    "short_tracks_le_5": norf["short_tracks_le_5"],
                    "short_tracks_le_10": norf["short_tracks_le_10"],
                    "n_stitch_candidates": stch["n_candidates"],
                    "n_stitch_sources": stch["n_source_tracklets_with_candidates"],
                    "stitch_gap_median": stch["gap_distribution"]["median"],
                    "stitch_gap_max": stch["gap_distribution"]["max"],
                    "rank1_error_median": round(stch["rank1_prediction_error"]["median"], 1),
                    "rank1_error_p75": round(stch["rank1_prediction_error"]["p75"], 1),
                })
            summary[f"{video}__{model}__new_detection_deltas"] = deltas

    out_json = args.sweep_dir / "sweep_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote sweep summary JSON: {out_json}")

    if flat_rows:
        out_csv = args.sweep_dir / "sweep_summary.csv"
        with out_csv.open("w", newline="", encoding="utf-8") as fout:
            writer = csv.DictWriter(fout, fieldnames=list(flat_rows[0].keys()))
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"Wrote sweep summary CSV: {out_csv}")


if __name__ == "__main__":
    main()