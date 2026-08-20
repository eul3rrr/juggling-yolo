#!/usr/bin/env python3
"""Track existing YOLO center-point detections with Norfair."""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import numpy as np
from norfair import Detection, Tracker

CSV_FIELDS = ["frame", "time_seconds", "track_id", "confidence", "center_x", "center_y", "observed"]
REQUIRED_DETECTION_FIELDS = ("frame", "confidence", "center_x", "center_y")
TRAIL_LENGTH = 30


@dataclass(frozen=True)
class DetectionRow:
    frame: int
    confidence: float
    center_x: float
    center_y: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track existing YOLO center-point detections with Norfair."
    )
    parser.add_argument("input_video", type=Path)
    parser.add_argument("detections_csv", type=Path)
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=50.0,
        help="Maximum center-point matching distance in pixels (default: 50).",
    )
    parser.add_argument(
        "--hit-counter-max",
        type=_positive_int,
        default=15,
        help="Maximum number of consecutive misses before a track is deleted (default: 15).",
    )
    parser.add_argument("--output-video", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    return parser.parse_args()


def _positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def _finite_float(value: str, field: str, line_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Malformed detections CSV line {line_number}: {field} must be a number, got {value!r}"
        ) from error
    if not math.isfinite(result):
        raise ValueError(
            f"Malformed detections CSV line {line_number}: {field} must be finite"
        )
    return result


def load_detections(
    path: Path, expected_video_name: str | None = None
) -> dict[int, list[DetectionRow]]:
    """Read and group zero-based YOLO rows by frame."""
    if not path.is_file():
        raise FileNotFoundError(f"Detections CSV does not exist: {path}")
    grouped: dict[int, list[DetectionRow]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"Detections CSV has no header: {path}")
        missing = [field for field in REQUIRED_DETECTION_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Detections CSV is missing required columns: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed detections CSV line {line_number}: missing value")
            if expected_video_name is not None and "video" in row:
                if row["video"] != expected_video_name:
                    raise ValueError(
                        f"Detections CSV line {line_number} belongs to {row['video']!r}, "
                        f"not input video {expected_video_name!r}"
                    )
            if "time_seconds" in row:
                time_seconds = _finite_float(row["time_seconds"], "time_seconds", line_number)
                if time_seconds < 0:
                    raise ValueError(
                        f"Malformed detections CSV line {line_number}: time_seconds must be non-negative"
                    )
            try:
                frame = int(row["frame"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Malformed detections CSV line {line_number}: frame must be a non-negative integer"
                ) from error
            if frame < 0:
                raise ValueError(
                    f"Malformed detections CSV line {line_number}: frame must be non-negative"
                )
            confidence = _finite_float(row["confidence"], "confidence", line_number)
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    f"Malformed detections CSV line {line_number}: confidence must be between 0 and 1"
                )
            center_x = _finite_float(row["center_x"], "center_x", line_number)
            center_y = _finite_float(row["center_y"], "center_y", line_number)
            grouped[frame].append(DetectionRow(frame, confidence, center_x, center_y))
    return dict(grouped)


def to_norfair_detections(rows: list[DetectionRow]) -> list[Detection]:
    """Convert YOLO rows to one-point Norfair detections with YOLO scores."""
    return [
        Detection(
            points=np.array([[row.center_x, row.center_y]], dtype=np.float32),
            scores=np.array([row.confidence], dtype=np.float32),
        )
        for row in rows
    ]


def video_metadata(path: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
        raise RuntimeError(
            f"Invalid video metadata: fps={fps}, width={width}, height={height}, "
            f"frame_count={frame_count}"
        )
    return fps, width, height, frame_count


def _track_rows(tracks, frame_index: int, fps: float, current_detections=None):
    current_detections = current_detections or []
    for track in tracks:
        if track.is_initializing or track.id is None or track.last_detection is None:
            continue
        points = np.asarray(track.estimate)
        if points.shape != (1, 2) or not np.isfinite(points).all():
            continue
        score = np.asarray(track.last_detection.scores).reshape(-1)
        if len(score) != 1 or not np.isfinite(score[0]):
            continue
        center_x, center_y = (float(value) for value in points[0])
        yield {
            "frame": frame_index,
            "time_seconds": f"{frame_index / fps:.6f}",
            "track_id": int(track.id),
            "confidence": f"{float(score[0]):.6f}",
            "center_x": f"{center_x:.3f}",
            "center_y": f"{center_y:.3f}",
            "observed": int(any(track.last_detection is detection for detection in current_detections)),
        }, (round(center_x), round(center_y))


def main() -> None:
    args = parse_args()
    input_video = args.input_video.resolve()
    detections_csv = args.detections_csv.resolve()
    if not input_video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    if args.distance_threshold <= 0 or not math.isfinite(args.distance_threshold):
        raise ValueError("--distance-threshold must be a finite positive number")

    fps, width, height, video_frame_count = video_metadata(input_video)
    detections = load_detections(detections_csv, expected_video_name=input_video.name)
    out_video = (args.output_video or PROJECT_ROOT / "outputs" / f"{input_video.stem}_norfair.mp4").resolve()
    out_csv = (args.output_csv or PROJECT_ROOT / "detections" / f"{input_video.stem}_norfair.csv").resolve()
    out_video.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    invalid_frames = [frame for frame in detections if frame >= video_frame_count]
    if invalid_frames:
        raise ValueError(
            f"Detections CSV references frame {min(invalid_frames)}, but video has "
            f"{video_frame_count} frames (zero-based)"
        )

    tracker = Tracker(
        distance_function="euclidean",
        distance_threshold=args.distance_threshold,
        hit_counter_max=args.hit_counter_max,
    )
    trails: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=TRAIL_LENGTH))
    capture = cv2.VideoCapture(str(input_video))
    writer = cv2.VideoWriter(str(out_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {input_video}")
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create annotated video: {out_video}")

    frame_count = 0
    row_count = 0
    try:
        with out_csv.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS, lineterminator="\n")
            csv_writer.writeheader()
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                current = to_norfair_detections(detections.get(frame_count, []))
                tracks = tracker.update(current)
                for output_row, center in _track_rows(tracks, frame_count, fps, current):
                    track_id = output_row["track_id"]
                    trail = trails[track_id]
                    trail.append(center)
                    for previous, point in zip(trail, list(trail)[1:]):
                        cv2.line(frame, previous, point, (0, 220, 0), 2, cv2.LINE_AA)
                    cv2.circle(frame, center, 4, (0, 220, 0), -1, cv2.LINE_AA)
                    cv2.putText(
                        frame,
                        f"id {track_id} {output_row['confidence']}",
                        (center[0] + 6, max(18, center[1] - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 220, 0),
                        2,
                        cv2.LINE_AA,
                    )
                    csv_writer.writerow(output_row)
                    row_count += 1
                writer.write(frame)
                frame_count += 1
    finally:
        capture.release()
        writer.release()
    if frame_count != video_frame_count:
        raise RuntimeError(
            f"Video ended after {frame_count} frames, but metadata reported {video_frame_count}"
        )
    print(f"Frames processed: {frame_count}")
    print(f"Track rows written: {row_count}")
    print(f"Annotated video: {out_video}")
    print(f"Track CSV: {out_csv}")
    print("CSV points are current Norfair estimates; observed=1 marks a track matched to a YOLO detection on that frame.")


if __name__ == "__main__":
    main()
