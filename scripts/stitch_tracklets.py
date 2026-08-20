#!/usr/bin/env python3
"""Rank simple constant-velocity matches between Norfair tracklets."""

from __future__ import annotations

import argparse
import csv
import colorsys
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2

INPUT_FIELDS = ("frame", "time_seconds", "track_id", "confidence", "center_x", "center_y")
OUTPUT_FIELDS = [
    "source_tracklet",
    "candidate_tracklet",
    "gap_frames",
    "predicted_x",
    "predicted_y",
    "candidate_start_x",
    "candidate_start_y",
    "prediction_error",
    "source_end_frame",
    "candidate_start_frame",
    "end_velocity_x",
    "end_velocity_y",
    "candidate_rank",
]
TRAIL_LENGTH = 30
TRACKLET_EXPIRY_FRAMES = 15
BRIDGE_DISPLAY_AFTER_FRAMES = 15
TITLE_BAR_HEIGHT = 34


@dataclass(frozen=True)
class TrackletPoint:
    frame: int
    center_x: float
    center_y: float


@dataclass(frozen=True)
class StitchCandidate:
    source_tracklet: int
    candidate_tracklet: int
    gap_frames: int
    predicted_x: float
    predicted_y: float
    candidate_start_x: float
    candidate_start_y: float
    prediction_error: float
    source_end_frame: int
    candidate_start_frame: int
    end_velocity_x: float
    end_velocity_y: float
    candidate_rank: int

    def as_row(self) -> dict[str, object]:
        return {
            "source_tracklet": self.source_tracklet,
            "candidate_tracklet": self.candidate_tracklet,
            "gap_frames": self.gap_frames,
            "predicted_x": f"{self.predicted_x:.6f}",
            "predicted_y": f"{self.predicted_y:.6f}",
            "candidate_start_x": f"{self.candidate_start_x:.6f}",
            "candidate_start_y": f"{self.candidate_start_y:.6f}",
            "prediction_error": f"{self.prediction_error:.6f}",
            "source_end_frame": self.source_end_frame,
            "candidate_start_frame": self.candidate_start_frame,
            "end_velocity_x": f"{self.end_velocity_x:.6f}",
            "end_velocity_y": f"{self.end_velocity_y:.6f}",
            "candidate_rank": self.candidate_rank,
        }


def _nonnegative_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a nonnegative integer") from error
    if result < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return result


def _finite(value: str, field: str, line_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"CSV line {line_number}: {field} must be a number") from error
    if not math.isfinite(result):
        raise ValueError(f"CSV line {line_number}: {field} must be finite")
    return result


def load_tracklets(path: Path) -> dict[int, list[TrackletPoint]]:
    """Load and group Norfair rows by track ID, sorted by frame."""
    if not path.is_file():
        raise FileNotFoundError(f"Tracklets CSV does not exist: {path}")
    grouped: dict[int, list[TrackletPoint]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"Tracklets CSV has no header: {path}")
        missing = [field for field in INPUT_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Tracklets CSV is missing required columns: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            if any(row.get(field) in (None, "") for field in INPUT_FIELDS):
                raise ValueError(f"CSV line {line_number}: missing value")
            try:
                frame = int(row["frame"])
                track_id = int(row["track_id"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"CSV line {line_number}: frame and track_id must be integers") from error
            if frame < 0:
                raise ValueError(f"CSV line {line_number}: frame must be nonnegative")
            _finite(row["time_seconds"], "time_seconds", line_number)
            _finite(row["confidence"], "confidence", line_number)
            center_x = _finite(row["center_x"], "center_x", line_number)
            center_y = _finite(row["center_y"], "center_y", line_number)
            grouped[track_id].append(TrackletPoint(frame, center_x, center_y))
    return {track_id: sorted(points, key=lambda point: point.frame) for track_id, points in grouped.items()}


def stitch_tracklets(
    tracklets: dict[int, list[TrackletPoint]], max_gap_frames: int = 10
) -> list[StitchCandidate]:
    """Return every eligible candidate, ranked independently for each source."""
    if max_gap_frames < 0:
        raise ValueError("max_gap_frames must be nonnegative")
    results: list[StitchCandidate] = []
    for source_id in sorted(tracklets):
        source_points = sorted(tracklets[source_id], key=lambda point: point.frame)
        if len(source_points) < 2:
            continue
        previous, endpoint = source_points[-2:]
        frame_delta = endpoint.frame - previous.frame
        if frame_delta <= 0:
            continue
        velocity_x = (endpoint.center_x - previous.center_x) / frame_delta
        velocity_y = (endpoint.center_y - previous.center_y) / frame_delta
        source_candidates: list[StitchCandidate] = []
        for candidate_id in sorted(tracklets):
            if candidate_id == source_id or not tracklets[candidate_id]:
                continue
            candidate_points = sorted(tracklets[candidate_id], key=lambda point: point.frame)
            start = candidate_points[0]
            if start.frame <= endpoint.frame:
                continue
            gap = start.frame - endpoint.frame - 1
            if gap > max_gap_frames:
                continue
            elapsed = start.frame - endpoint.frame
            predicted_x = endpoint.center_x + velocity_x * elapsed
            predicted_y = endpoint.center_y + velocity_y * elapsed
            error = math.hypot(predicted_x - start.center_x, predicted_y - start.center_y)
            source_candidates.append(
                StitchCandidate(
                    source_id,
                    candidate_id,
                    gap,
                    predicted_x,
                    predicted_y,
                    start.center_x,
                    start.center_y,
                    error,
                    endpoint.frame,
                    start.frame,
                    velocity_x,
                    velocity_y,
                    0,
                )
            )
        source_candidates.sort(key=lambda candidate: (candidate.prediction_error, candidate.candidate_tracklet))
        results.extend(
            replace(candidate, candidate_rank=rank)
            for rank, candidate in enumerate(source_candidates, start=1)
        )
    return results


def write_candidates(path: Path, candidates: list[StitchCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(candidate.as_row() for candidate in candidates)


def _tracklet_colors(tracklets: dict[int, list[TrackletPoint]]) -> dict[int, tuple[int, int, int]]:
    """Assign stable, widely spaced BGR colors in track ID order."""
    colors: dict[int, tuple[int, int, int]] = {}
    track_ids = sorted(tracklets)
    for index, track_id in enumerate(track_ids):
        hue = index / max(1, len(track_ids))
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.8, 0.95)
        colors[track_id] = (round(blue * 255), round(green * 255), round(red * 255))
    return colors


def interpolate_bridge_point(candidate: StitchCandidate, frame_index: int) -> tuple[float, float]:
    """Return the hypothetical bridge position, clamped to its endpoints."""
    elapsed = candidate.candidate_start_frame - candidate.source_end_frame
    if elapsed <= 0:
        return candidate.candidate_start_x, candidate.candidate_start_y
    source_x = candidate.predicted_x - candidate.end_velocity_x * elapsed
    source_y = candidate.predicted_y - candidate.end_velocity_y * elapsed
    alpha = max(0.0, min(1.0, (frame_index - candidate.source_end_frame) / elapsed))
    return (
        source_x + alpha * (candidate.candidate_start_x - source_x),
        source_y + alpha * (candidate.candidate_start_y - source_y),
    )


def _draw_label(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    """Draw text with a dark outline so labels remain readable over video."""
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def _draw_tracklets(frame, frame_index: int, tracklets: dict[int, list[TrackletPoint]],
                    tracklet_colors: dict[int, tuple[int, int, int]]) -> None:
    """Draw recent Norfair trails, omitting tracklets long after their last point."""
    for track_id in sorted(tracklets):
        points = tracklets[track_id]
        if not points or frame_index > points[-1].frame + TRACKLET_EXPIRY_FRAMES:
            continue
        visible = [point for point in points if point.frame <= frame_index][-TRAIL_LENGTH:]
        if not visible:
            continue
        color = tracklet_colors[track_id]
        for previous, current in zip(visible, visible[1:]):
            cv2.line(
                frame,
                _point(previous.center_x, previous.center_y),
                _point(current.center_x, current.center_y),
                color,
                1,
                cv2.LINE_AA,
            )
        current = visible[-1]
        if current.frame == frame_index:
            center = _point(current.center_x, current.center_y)
            cv2.circle(frame, center, 4, color, -1, cv2.LINE_AA)
            _draw_label(frame, f"id {track_id}", (center[0] + 7, max(16, center[1] - 7)), color)


def _draw_title(frame, title: str) -> None:
    cv2.rectangle(frame, (0, 0), (frame.shape[1], TITLE_BAR_HEIGHT), (20, 20, 20), -1)
    cv2.putText(frame, title, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                (255, 255, 255), 2, cv2.LINE_AA)


def _draw_bridges(frame, frame_index: int, rank_one: list[StitchCandidate]) -> None:
    bridge_color = (0, 215, 255)
    source_marker_color = (0, 140, 255)
    target_marker_color = (0, 255, 255)
    for candidate in rank_one:
        if not candidate.source_end_frame <= frame_index <= candidate.candidate_start_frame + BRIDGE_DISPLAY_AFTER_FRAMES:
            continue
        source = interpolate_bridge_point(candidate, candidate.source_end_frame)
        target = (candidate.candidate_start_x, candidate.candidate_start_y)
        source_point = _point(*source)
        target_point = _point(*target)
        cv2.line(frame, source_point, target_point, bridge_color, 4, cv2.LINE_AA)
        cv2.drawMarker(frame, source_point, source_marker_color, cv2.MARKER_DIAMOND, 14, 3, cv2.LINE_AA)
        cv2.drawMarker(frame, target_point, target_marker_color, cv2.MARKER_CROSS, 16, 3, cv2.LINE_AA)
        interpolated = _point(*interpolate_bridge_point(candidate, frame_index))
        cv2.circle(frame, interpolated, 7, (0, 165, 255), -1, cv2.LINE_AA)
        label = (f"STITCH {candidate.source_tracklet} -> {candidate.candidate_tracklet}, "
                 f"gap {candidate.gap_frames}, error {candidate.prediction_error:.1f}")
        _draw_label(frame, label, (max(5, target_point[0] + 8), max(20, target_point[1] - 8)), bridge_color)


def annotate_video(
    input_video: Path,
    output_video: Path,
    candidates: list[StitchCandidate],
    tracklets: dict[int, list[TrackletPoint]] | None = None,
) -> None:
    capture = cv2.VideoCapture(str(input_video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {input_video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError("Input video has invalid metadata")
    output_video.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width * 2, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create annotated video: {output_video}")
    rank_one = [candidate for candidate in candidates if candidate.candidate_rank == 1]
    tracklets = tracklets or {}
    tracklet_colors = _tracklet_colors(tracklets)
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            original = frame.copy()
            stitch_view = frame.copy()
            _draw_tracklets(original, frame_index, tracklets, tracklet_colors)
            _draw_tracklets(stitch_view, frame_index, tracklets, tracklet_colors)
            _draw_bridges(stitch_view, frame_index, rank_one)
            _draw_title(original, "ORIGINAL NORFAIR TRACKLETS")
            _draw_title(stitch_view, "STITCH VIEW")
            writer.write(cv2.hconcat((original, stitch_view)))
            frame_index += 1
    finally:
        capture.release()
        writer.release()


def _point(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank constant-velocity matches between Norfair tracklets.")
    parser.add_argument("input_video", type=Path)
    parser.add_argument("tracklets_csv", type=Path)
    parser.add_argument("--max-gap-frames", type=_nonnegative_int, default=10)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-video", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_video = args.input_video.resolve()
    tracklets_csv = args.tracklets_csv.resolve()
    if not input_video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    tracklets = load_tracklets(tracklets_csv)
    candidates = stitch_tracklets(tracklets, args.max_gap_frames)
    output_csv = (args.output_csv or PROJECT_ROOT / "detections" / f"{input_video.stem}_stitches.csv").resolve()
    output_video = (args.output_video or PROJECT_ROOT / "outputs" / f"{input_video.stem}_stitches.mp4").resolve()
    write_candidates(output_csv, candidates)
    annotate_video(input_video, output_video, candidates, tracklets)
    print(f"Candidates written: {len(candidates)}")
    print(f"Stitch CSV: {output_csv}")
    print(f"Annotated video: {output_video}")


if __name__ == "__main__":
    main()
