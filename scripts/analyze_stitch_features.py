#!/usr/bin/env python3
"""Analyze reviewed stitch hypotheses without changing candidate generation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import numpy as np
import torch
from ultralytics import YOLO

TRACKLET_FIELDS = ("frame", "time_seconds", "track_id", "confidence", "center_x", "center_y")
STITCH_FIELDS = (
    "source_tracklet", "candidate_tracklet", "gap_frames", "predicted_x", "predicted_y",
    "candidate_start_x", "candidate_start_y", "prediction_error", "source_end_frame",
    "candidate_start_frame", "end_velocity_x", "end_velocity_y", "candidate_rank",
)
POSE_FIELDS = (
    "video", "frame", "time_seconds", "person_index", "person_confidence",
    "left_wrist_x", "left_wrist_y", "left_wrist_confidence",
    "right_wrist_x", "right_wrist_y", "right_wrist_confidence",
)
OUTPUT_FIELDS = (
    "video", "source_tracklet", "candidate_tracklet", "rank", "gap_frames",
    "prediction_error", "trajectory_fit_error", "source_end_hand_distance",
    "candidate_start_hand_distance", "gap_hand_distance", "nearest_hand_distance",
    "nearest_hand", "nearest_hand_frame", "source_observed_points", "candidate_observed_points",
    "source_observed_velocity_x", "source_observed_velocity_y", "trajectory_fit_status", "label",
)


def resolve_device(requested: str) -> str:
    return ("0" if torch.cuda.is_available() else "cpu") if requested == "auto" else requested


def stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def model_reference(model: str) -> str:
    candidate = Path(model)
    if not candidate.is_absolute() and (PROJECT_ROOT / candidate).is_file():
        return str(PROJECT_ROOT / candidate)
    return model


def pose_csv_default(video: Path, detections_dir: Path) -> Path:
    return detections_dir / f"{video.stem}_yolo26s-pose.csv"


def pose_overlay_default(video: Path, outputs_dir: Path) -> Path:
    return outputs_dir / "pose_overlay" / f"{video.stem}_yolo26s-pose_overlay.mp4"


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def load_tracklets(path: Path) -> dict[int, list[tuple[int, float, float, int]]]:
    tracklets: dict[int, list[tuple[int, float, float, int]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            tracklets[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]), int(row.get("observed", "1")))
            )
    for points in tracklets.values():
        points.sort(key=lambda point: point[0])
    return dict(tracklets)


def load_stitches(path: Path) -> dict[tuple[int, int], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (int(row["source_tracklet"]), int(row["candidate_tracklet"])): row
            for row in csv.DictReader(handle)
        }


def load_labels(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fit_trajectory_error(
    source: list[tuple],
    candidate: list[tuple],
    points_per_side: int,
) -> float:
    observed_source = [point for point in source if len(point) < 4 or point[3] == 1]
    observed_candidate = [point for point in candidate if len(point) < 4 or point[3] == 1]
    points = observed_source[-points_per_side:] + observed_candidate[:points_per_side]
    if len(points) < 3:
        return math.nan
    time = np.asarray([point[0] for point in points], dtype=float)
    time -= time[0]
    x = np.asarray([point[1] for point in points], dtype=float)
    y = np.asarray([point[2] for point in points], dtype=float)
    x_design = np.column_stack((np.ones_like(time), time))
    y_design = np.column_stack((np.ones_like(time), time, time * time))
    x_coefficients, *_ = np.linalg.lstsq(x_design, x, rcond=None)
    y_coefficients, *_ = np.linalg.lstsq(y_design, y, rcond=None)
    x_residual = x_design @ x_coefficients - x
    y_residual = y_design @ y_coefficients - y
    return float(np.sqrt(np.mean(x_residual * x_residual + y_residual * y_residual)))


def observed_velocity(points: list[tuple]) -> tuple[float, float] | None:
    """Estimate endpoint velocity from the last two actual observations."""
    observed = [point for point in points if len(point) < 4 or point[3] == 1]
    if len(observed) < 2:
        return None
    previous, current = observed[-2], observed[-1]
    delta_frame = current[0] - previous[0]
    if delta_frame <= 0:
        return None
    return ((current[1] - previous[1]) / delta_frame, (current[2] - previous[2]) / delta_frame)


def observed_points(points: list[tuple]) -> list[tuple]:
    return [point for point in points if len(point) < 4 or point[3] == 1]


def load_pose(path: Path) -> dict[int, list[dict[str, float | str | None]]]:
    by_frame: dict[int, list[dict[str, float | str | None]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_frame[int(row["frame"])].append({
                "left_x": parse_float(row.get("left_wrist_x")),
                "left_y": parse_float(row.get("left_wrist_y")),
                "left_conf": parse_float(row.get("left_wrist_confidence")),
                "right_x": parse_float(row.get("right_wrist_x")),
                "right_y": parse_float(row.get("right_wrist_y")),
                "right_conf": parse_float(row.get("right_wrist_confidence")),
            })
    return dict(by_frame)


def wrist_candidates(
    pose_by_frame: dict[int, list[dict[str, float | str | None]]],
    frame: int,
    confidence_threshold: float,
) -> list[tuple[str, float, float]]:
    wrists: list[tuple[str, float, float]] = []
    for person in pose_by_frame.get(frame, []):
        for side in ("left", "right"):
            x = person[f"{side}_x"]
            y = person[f"{side}_y"]
            confidence = person[f"{side}_conf"]
            if x is not None and y is not None and confidence is not None and confidence >= confidence_threshold:
                wrists.append((side, float(x), float(y)))
    return wrists


def nearest_at(
    pose_by_frame: dict[int, list[dict[str, float | str | None]]],
    frame: int,
    point: tuple[float, float],
    confidence_threshold: float,
) -> tuple[float, str] | None:
    wrists = wrist_candidates(pose_by_frame, frame, confidence_threshold)
    if not wrists:
        return None
    ranked = sorted((math.hypot(point[0] - x, point[1] - y), side) for side, x, y in wrists)
    return ranked[0]


def bridge_point(
    source_point: tuple[float, float],
    candidate_point: tuple[float, float],
    frame: int,
    source_frame: int,
    candidate_frame: int,
) -> tuple[float, float]:
    if candidate_frame <= source_frame:
        return candidate_point
    alpha = (frame - source_frame) / (candidate_frame - source_frame)
    alpha = max(0.0, min(1.0, alpha))
    return (
        source_point[0] + alpha * (candidate_point[0] - source_point[0]),
        source_point[1] + alpha * (candidate_point[1] - source_point[1]),
    )


def hand_features(
    candidate: dict[str, str],
    source_point: tuple[float, float],
    pose_by_frame: dict[int, list[dict[str, float | str | None]]],
    confidence_threshold: float,
) -> dict[str, str]:
    source_frame = int(candidate["source_end_frame"])
    candidate_frame = int(candidate["candidate_start_frame"])
    candidate_point = (float(candidate["candidate_start_x"]), float(candidate["candidate_start_y"]))
    observations: list[tuple[str, int, tuple[float, float]]] = [
        ("source_end", source_frame, source_point),
        ("candidate_start", candidate_frame, candidate_point),
    ]
    for frame in range(source_frame + 1, candidate_frame):
        observations.append(("gap", frame, bridge_point(source_point, candidate_point, frame, source_frame, candidate_frame)))

    best_by_region: dict[str, tuple[float, str, int]] = {}
    for region, frame, point in observations:
        nearest = nearest_at(pose_by_frame, frame, point, confidence_threshold)
        if nearest is not None and (region not in best_by_region or nearest[0] < best_by_region[region][0]):
            best_by_region[region] = (nearest[0], nearest[1], frame)
    all_values = list(best_by_region.values())
    overall = min(all_values, default=None, key=lambda value: value[0])
    return {
        "source_end_hand_distance": f"{best_by_region['source_end'][0]:.6f}" if "source_end" in best_by_region else "",
        "candidate_start_hand_distance": f"{best_by_region['candidate_start'][0]:.6f}" if "candidate_start" in best_by_region else "",
        "gap_hand_distance": f"{best_by_region['gap'][0]:.6f}" if "gap" in best_by_region else "",
        "nearest_hand_distance": f"{overall[0]:.6f}" if overall else "",
        "nearest_hand": overall[1] if overall else "unavailable",
        "nearest_hand_frame": str(overall[2]) if overall else "",
    }


def run_pose(video: Path, output_csv: Path, output_video: Path, model: str, imgsz: int, device: str, conf: float) -> None:
    video = video.resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid video metadata: fps={fps}, width={width}, height={height}")
    resolved_device = resolve_device(device)
    model_ref = model_reference(model)
    pose_model = YOLO(model_ref)
    if pose_model.task != "pose":
        raise ValueError(f"Expected a pose checkpoint, but {model!r} has task {pose_model.task!r}")
    print(f"Pose input: {video}")
    print(f"Pose model: {model_ref} (task={pose_model.task})")
    print(f"Requested device: {device}; resolved device: {resolved_device}")
    rows = 0
    output_video.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create pose overlay video: {output_video}")
    rendered_frames = 0
    try:
        with output_csv.open("w", newline="", encoding="utf-8") as handle:
            csv_writer = csv.DictWriter(handle, fieldnames=POSE_FIELDS, lineterminator="\n")
            csv_writer.writeheader()
            results = pose_model.predict(
                source=str(video), stream=True, conf=conf, imgsz=imgsz,
                device=resolved_device, vid_stride=1, save=False, verbose=False,
            )
            for frame, result in enumerate(results):
                plotted = result.plot(boxes=True, labels=True, conf=True, kpt_radius=4, kpt_line=True)
                if plotted.shape[1] != width or plotted.shape[0] != height:
                    plotted = cv2.resize(plotted, (width, height))
                writer.write(plotted)
                rendered_frames += 1
                keypoints = result.keypoints
                if keypoints is None or keypoints.data is None:
                    continue
                data = keypoints.data.detach().cpu().numpy()
                person_conf = result.boxes.conf.detach().cpu().numpy() if result.boxes is not None else np.full(len(data), np.nan)
                for person_index, person in enumerate(data):
                    def value(index: int, coordinate: int) -> str:
                        return f"{float(person[index, coordinate]):.6f}" if person.shape[0] > index else ""
                    def confidence(index: int) -> str:
                        return f"{float(person[index, 2]):.6f}" if person.shape[0] > index and person.shape[1] > 2 else ""
                    csv_writer.writerow({
                        "video": stored_path(video), "frame": frame,
                        "time_seconds": f"{frame / fps:.6f}" if fps > 0 else "",
                        "person_index": person_index,
                        "person_confidence": f"{float(person_conf[person_index]):.6f}" if person_index < len(person_conf) and math.isfinite(float(person_conf[person_index])) else "",
                        "left_wrist_x": value(9, 0), "left_wrist_y": value(9, 1), "left_wrist_confidence": confidence(9),
                        "right_wrist_x": value(10, 0), "right_wrist_y": value(10, 1), "right_wrist_confidence": confidence(10),
                    })
                    rows += 1
    finally:
        writer.release()
    print(f"Pose rows: {rows}")
    print(f"Pose CSV: {output_csv}")
    print(f"Pose overlay frames: {rendered_frames}")
    print(f"Pose overlay video: {output_video}")


def enrich(
    labels_csv: Path,
    output_csv: Path,
    summary_json: Path,
    report_md: Path,
    detections_dir: Path,
    points_per_side: int,
    wrist_confidence: float,
) -> None:
    labels = load_labels(labels_csv)
    output_rows: list[dict[str, str]] = []
    for label in labels:
        video = PROJECT_ROOT / label["video"] if not Path(label["video"]).is_absolute() else Path(label["video"])
        video = video.resolve()
        stem = video.stem
        tracklets_path = detections_dir / f"{stem}_norfair_dt50_hc5.csv"
        stitches_path = detections_dir / f"{stem}_norfair_dt50_hc5_stitches.csv"
        pose_path = pose_csv_default(video, detections_dir)
        tracklets = load_tracklets(tracklets_path)
        stitches = load_stitches(stitches_path)
        pose_by_frame = load_pose(pose_path)
        source_id = int(label["source_tracklet"])
        candidate_id = int(label["candidate_tracklet"])
        stitch = stitches[(source_id, candidate_id)]
        source_observed = observed_points(tracklets[source_id])
        candidate_observed = observed_points(tracklets[candidate_id])
        trajectory_error = fit_trajectory_error(tracklets[source_id], tracklets[candidate_id], points_per_side)
        source_velocity = observed_velocity(tracklets[source_id])
        analysis_stitch = dict(stitch)
        if source_observed:
            analysis_stitch["source_end_frame"] = str(source_observed[-1][0])
        if candidate_observed:
            analysis_stitch.update({
                "candidate_start_frame": str(candidate_observed[0][0]),
                "candidate_start_x": str(candidate_observed[0][1]),
                "candidate_start_y": str(candidate_observed[0][2]),
            })
        row = {
            "video": label["video"], "source_tracklet": str(source_id), "candidate_tracklet": str(candidate_id),
            "rank": stitch["candidate_rank"], "gap_frames": stitch["gap_frames"],
            "prediction_error": stitch["prediction_error"],
            "trajectory_fit_error": f"{trajectory_error:.6f}" if math.isfinite(trajectory_error) else "",
            "source_observed_points": str(len(source_observed)),
            "candidate_observed_points": str(len(candidate_observed)),
            "source_observed_velocity_x": f"{source_velocity[0]:.6f}" if source_velocity else "",
            "source_observed_velocity_y": f"{source_velocity[1]:.6f}" if source_velocity else "",
            "trajectory_fit_status": "ok" if len(source_observed) + len(candidate_observed) >= 3 else "too_few_observed_points",
            "label": label.get("label", ""),
        }
        source_point = (source_observed[-1][1], source_observed[-1][2]) if source_observed else (float(stitch["predicted_x"]), float(stitch["predicted_y"]))
        row.update(hand_features(analysis_stitch, source_point, pose_by_frame, wrist_confidence))
        output_rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    summary = summarize(output_rows)
    summary["parameters"] = {
        "points_per_side": points_per_side,
        "wrist_confidence": wrist_confidence,
        "trajectory_model": "x=a+b*t; y=c+d*t+e*t^2",
        "trajectory_rmse_units": "pixels",
        "hand_distance_units": "pixels",
        "hand_gap_position": "linear interpolation between source endpoint and candidate start",
    }
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(output_rows, report_md)
    print(f"Enriched rows: {len(output_rows)}")
    print(f"Enriched CSV: {output_csv}")
    print(f"Summary JSON: {summary_json}")
    print(f"Report Markdown: {report_md}")


def numeric(rows: Iterable[dict[str, str]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = parse_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def stats(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    values = numeric(rows, "trajectory_fit_error")
    hand = numeric(rows, "nearest_hand_distance")
    def median(values: list[float]) -> float | None:
        return float(np.median(values)) if values else None
    return {
        "n": len(rows), "trajectory_fit_error_mean": float(np.mean(values)) if values else None,
        "trajectory_fit_error_median": median(values), "trajectory_fit_error_min": min(values) if values else None,
        "trajectory_fit_error_max": max(values) if values else None,
        "nearest_hand_distance_mean": float(np.mean(hand)) if hand else None,
        "nearest_hand_distance_median": median(hand),
        "nearest_hand_available_n": len(hand),
        "nearest_hand_available_fraction": len(hand) / len(rows) if rows else None,
    }


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    labels = sorted({row.get("label", "") for row in rows})
    result: dict[str, object] = {"total_rows": len(rows), "by_label": {}}
    for label in labels:
        subset = [row for row in rows if row.get("label", "") == label]
        result["by_label"][label or "blank"] = stats(subset)
    for video in sorted({row["video"] for row in rows}):
        subset = [row for row in rows if row["video"] == video]
        result.setdefault("by_video", {})[video] = {
            "all": stats(subset),
            "by_label": {label or "blank": stats([row for row in subset if row.get("label", "") == label]) for label in labels},
        }
    return result


def _fmt(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.2f}"


def _row_ref(row: dict[str, str]) -> str:
    return (f"{row['video']} source={row['source_tracklet']} "
            f"candidate={row['candidate_tracklet']} gap={row['gap_frames']} "
            f"fit={row['trajectory_fit_error']} px hand={row['nearest_hand_distance'] or 'unavailable'} px "
            f"({row['nearest_hand']})")


def write_report(rows: list[dict[str, str]], output: Path) -> None:
    correct = [row for row in rows if row.get("label") == "correct"]
    wrong = [row for row in rows if row.get("label") == "wrong"]
    report = [
        "# Reviewed stitch feature analysis",
        "",
        "This is descriptive analysis only. It does not modify Norfair, candidate generation, "
        "tracklet IDs, or acceptance thresholds.",
        "",
        "## Features",
        "",
        "- `trajectory_fit_error`: pixel RMSE from fitting `x=a+b*t` and `y=c+d*t+e*t^2` "
        "to the last ten observed source points and first ten observed candidate points. "
        "Norfair-only predicted rows are retained in the track CSV but excluded from this fit.",
        "- Source endpoints, candidate starts, and source endpoint velocity estimates use actual "
        "observed points; `prediction_error` remains the original stitch-candidate feature.",
        "- Wrist distances: minimum Euclidean distance from the source endpoint, candidate "
        "start, and linearly interpolated gap positions to confident COCO wrists. Wrist "
        "confidence threshold was 0.30.",
        "- The pretrained `yolo26s-pose.pt` model was used on both reviewed videos; no training "
        "or fine-tuning was performed.",
        "",
        "## Overall correct versus wrong",
        "",
        "| label | n | fit mean px | fit median px | hand mean px | hand median px | hand available |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, subset in (("correct", correct), ("wrong", wrong)):
        current = stats(subset)
        report.append(
            f"| {label} | {len(subset)} | {_fmt(current['trajectory_fit_error_mean'])} | "
            f"{_fmt(current['trajectory_fit_error_median'])} | {_fmt(current['nearest_hand_distance_mean'])} | "
            f"{_fmt(current['nearest_hand_distance_median'])} | "
            f"{current['nearest_hand_available_n']}/{len(subset)} |"
        )
    report.extend([
        "",
        "### Interpretation",
        "",
        f"- Correct stitches generally have lower trajectory-fit error in this reviewed sample "
        f"(median {_fmt(stats(correct)['trajectory_fit_error_median'])} px versus "
        f"{_fmt(stats(wrong)['trajectory_fit_error_median'])} px for wrong). This supports "
        "using the fit as an analysis feature, but not as an automatic decision rule yet.",
        f"- Wrist proximity is not a clean global separator. Wrong stitches have mean/median "
        f"nearest-wrist distance {_fmt(stats(wrong)['nearest_hand_distance_mean'])}/"
        f"{_fmt(stats(wrong)['nearest_hand_distance_median'])} px versus "
        f"{_fmt(stats(correct)['nearest_hand_distance_mean'])}/"
        f"{_fmt(stats(correct)['nearest_hand_distance_median'])} px for correct, but the "
        "per-video breakdown is strongly affected by the label balance and scene composition.",
        f"- {len(rows)} reviewed rows were enriched; "
        f"{sum(bool(row.get('trajectory_fit_error')) for row in rows)} had enough observed points "
        "for a trajectory fit. This result should not be generalized beyond these videos.",
        "",
        "## Rank-stratified comparison",
        "",
        "Rank-1 candidates are the top-ranked stitch hypotheses from the unchanged candidate generator; "
        "rank-2/3 rows are alternate candidates reviewed under the same labels.",
        "",
        "| candidate ranks | label | n | fit median px |",
        "|---|---:|---:|---:|",
        "",
    ])
    for rank_name, rank_values in (("rank-1", {1}), ("rank-2/3", {2, 3})):
        for label in ("correct", "wrong"):
            subset = [row for row in rows if row.get("label") == label and int(row["rank"]) in rank_values]
            report.append(f"| {rank_name} | {label} | {len(subset)} | {_fmt(stats(subset)['trajectory_fit_error_median'])} |")
    report.extend([
        "## Per-video comparison",
        "",
    ])
    for video in sorted({row["video"] for row in rows}):
        report.append(f"### `{video}`")
        report.append("")
        report.append("| label | n | fit mean px | fit median px | hand mean px | hand median px |")
        report.append("|---|---:|---:|---:|---:|---:|")
        for label in ("correct", "wrong"):
            subset = [row for row in rows if row["video"] == video and row.get("label") == label]
            current = stats(subset)
            report.append(
                f"| {label} | {len(subset)} | {_fmt(current['trajectory_fit_error_mean'])} | "
                f"{_fmt(current['trajectory_fit_error_median'])} | {_fmt(current['nearest_hand_distance_mean'])} | "
                f"{_fmt(current['nearest_hand_distance_median'])} |"
            )
        report.append("")

    def examples(title: str, subset: list[dict[str, str]], reverse: bool) -> None:
        report.append(f"## {title}")
        report.append("")
        for row in sorted(subset, key=lambda item: float(item["trajectory_fit_error"]), reverse=reverse)[:5]:
            report.append(f"- `{_row_ref(row)}`")
        report.append("")

    examples("Correct stitches with very good trajectory fit", correct, False)
    examples("Wrong stitches with poor trajectory fit", wrong, True)
    correct_with_hand = [row for row in correct if row["nearest_hand_distance"]]
    wrong_with_hand = [row for row in wrong if row["nearest_hand_distance"]]
    examples("Correct stitches with poor fit and an available wrist", correct_with_hand, True)
    correct_fit_median = stats(correct)["trajectory_fit_error_median"]
    correct_poor_fit_near_hand = [
        row for row in correct_with_hand
        if correct_fit_median is not None and float(row["trajectory_fit_error"]) > correct_fit_median
    ]
    report.append("## Correct poor-fit stitches closest to a wrist")
    report.append("")
    for row in sorted(correct_poor_fit_near_hand, key=lambda item: float(item["nearest_hand_distance"]))[:5]:
        report.append(f"- `{_row_ref(row)}`")
    report.append("")
    examples("Wrong stitches with good trajectory fit", wrong_with_hand, False)
    report.extend([
        "## Failure-mode question",
        "",
        "The reviewed data is consistent with two overlapping regimes rather than a single "
        "hard rule: many wrong stitches have poor geometric fit, while some wrong stitches "
        "have good fit and some correct stitches have poor fit. The latter cases are candidates "
        "for hand-interaction or other occlusion-related review, but wrist proximity alone does "
        "not establish that explanation. No classifier or threshold was trained or selected.",
        "",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pose = subparsers.add_parser("pose")
    pose.add_argument("video", type=Path)
    pose.add_argument("--model", default="yolo26s-pose.pt")
    pose.add_argument("--output-csv", type=Path, default=None)
    pose.add_argument("--output-video", type=Path, default=None)
    pose.add_argument("--imgsz", type=int, default=960)
    pose.add_argument("--conf", type=float, default=0.15)
    pose.add_argument("--device", default="auto")
    enrich_parser = subparsers.add_parser("enrich")
    enrich_parser.add_argument("labels_csv", type=Path, default=PROJECT_ROOT / "detections" / "stitch_review_labels.csv", nargs="?")
    enrich_parser.add_argument("--output-csv", type=Path, default=PROJECT_ROOT / "detections" / "stitch_review_features.csv")
    enrich_parser.add_argument("--summary-json", type=Path, default=PROJECT_ROOT / "detections" / "stitch_review_feature_summary.json")
    enrich_parser.add_argument("--report-md", type=Path, default=PROJECT_ROOT / "detections" / "stitch_review_feature_report.md")
    enrich_parser.add_argument("--detections-dir", type=Path, default=PROJECT_ROOT / "detections")
    enrich_parser.add_argument("--points-per-side", type=int, default=10)
    enrich_parser.add_argument("--wrist-confidence", type=float, default=0.30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "pose":
        video = args.video.resolve()
        output = (args.output_csv or pose_csv_default(video, PROJECT_ROOT / "detections")).resolve()
        output_video = (args.output_video or pose_overlay_default(video, PROJECT_ROOT / "outputs")).resolve()
        run_pose(video, output, output_video, args.model, args.imgsz, args.device, args.conf)
    else:
        if args.points_per_side < 1:
            raise ValueError("--points-per-side must be positive")
        enrich(args.labels_csv.resolve(), args.output_csv.resolve(), args.summary_json.resolve(), args.report_md.resolve(), args.detections_dir.resolve(), args.points_per_side, args.wrist_confidence)


if __name__ == "__main__":
    main()
