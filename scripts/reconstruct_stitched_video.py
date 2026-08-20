#!/usr/bin/env python3
"""Render a descriptive high-confidence chain reconstruction from existing outputs."""

from __future__ import annotations

import argparse
import colorsys
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIT_THRESHOLD = 22.0
TRAIL_LENGTH = 30
TRACKLET_EXPIRY_FRAMES = 15
TITLE_BAR_HEIGHT = 54


@dataclass(frozen=True)
class TrackPoint:
    frame: int
    center_x: float
    center_y: float
    observed: int


@dataclass(frozen=True)
class DetectionBox:
    center_x: float
    center_y: float
    x1: float
    y1: float
    x2: float
    y2: float


def _point(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def _text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int], scale: float = 0.52) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def load_tracklets(path: Path) -> dict[int, list[TrackPoint]]:
    grouped: dict[int, list[TrackPoint]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"frame", "track_id", "center_x", "center_y"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Tracklet CSV is missing columns: {', '.join(missing)}")
        for row in reader:
            grouped[int(row["track_id"])].append(
                TrackPoint(
                    int(row["frame"]), float(row["center_x"]), float(row["center_y"]),
                    int(row.get("observed", "1")),
                )
            )
    return {track_id: sorted(points, key=lambda point: point.frame) for track_id, points in grouped.items()}


def load_detection_boxes(path: Path) -> dict[int, list[DetectionBox]]:
    grouped: dict[int, list[DetectionBox]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"frame", "center_x", "center_y", "x1", "y1", "x2", "y2"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Detection CSV is missing columns: {', '.join(missing)}")
        for row in reader:
            grouped[int(row["frame"])].append(
                DetectionBox(
                    float(row["center_x"]), float(row["center_y"]), float(row["x1"]),
                    float(row["y1"]), float(row["x2"]), float(row["y2"]),
                )
            )
    return dict(grouped)


def load_feature_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select_accepted_stitches(rows: list[dict[str, str]], fit_threshold: float) -> list[dict[str, str]]:
    if not math.isfinite(fit_threshold) or fit_threshold < 0:
        raise ValueError("fit_threshold must be a finite nonnegative number")
    accepted = []
    for row in rows:
        if row.get("rank") != "1":
            continue
        try:
            fit = float(row["trajectory_fit_error"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(fit) and fit <= fit_threshold:
            accepted.append(row)
    return accepted


def build_chain_mapping(track_ids: set[int], accepted_pairs: list[tuple[int, int]]) -> dict[int, int]:
    parent = {track_id: track_id for track_id in track_ids}

    def find(track_id: int) -> int:
        while parent[track_id] != track_id:
            parent[track_id] = parent[parent[track_id]]
            track_id = parent[track_id]
        return track_id

    for source, candidate in accepted_pairs:
        if source not in parent or candidate not in parent:
            raise ValueError(f"Accepted stitch references missing tracklet: {source}->{candidate}")
        source_root, candidate_root = find(source), find(candidate)
        if source_root != candidate_root:
            parent[candidate_root] = source_root

    roots = sorted({find(track_id) for track_id in track_ids})
    chain_by_root = {root: chain_id for chain_id, root in enumerate(roots, start=1)}
    return {track_id: chain_by_root[find(track_id)] for track_id in sorted(track_ids)}


def _colors(chain_mapping: dict[int, int]) -> dict[int, tuple[int, int, int]]:
    chain_ids = sorted(set(chain_mapping.values()))
    result = {}
    for index, chain_id in enumerate(chain_ids):
        red, green, blue = colorsys.hsv_to_rgb(index / max(1, len(chain_ids)), 0.82, 0.95)
        result[chain_id] = (round(blue * 255), round(green * 255), round(red * 255))
    return result


def _observed_endpoint(tracklets: dict[int, list[TrackPoint]], track_id: int, first: bool) -> TrackPoint | None:
    points = [point for point in tracklets.get(track_id, []) if point.observed == 1]
    if not points:
        return None
    return points[0] if first else points[-1]


def _bridge_point(source: TrackPoint, candidate: TrackPoint, frame: int) -> tuple[float, float]:
    elapsed = candidate.frame - source.frame
    if elapsed <= 0:
        return candidate.center_x, candidate.center_y
    alpha = max(0.0, min(1.0, (frame - source.frame) / elapsed))
    return (
        source.center_x + alpha * (candidate.center_x - source.center_x),
        source.center_y + alpha * (candidate.center_y - source.center_y),
    )


def _nearest_box(point: TrackPoint, boxes: list[DetectionBox]) -> DetectionBox | None:
    if point.observed != 1 or not boxes:
        return None
    return min(boxes, key=lambda box: math.hypot(point.center_x - box.center_x, point.center_y - box.center_y))


def _draw_dashed_line(frame, first: tuple[int, int], second: tuple[int, int], color: tuple[int, int, int], width: int = 3) -> None:
    distance = max(1, int(math.hypot(second[0] - first[0], second[1] - first[1])))
    for start in range(0, distance, 12):
        alpha_start = start / distance
        alpha_end = min(1.0, (start + 6) / distance)
        a = (round(first[0] + alpha_start * (second[0] - first[0])), round(first[1] + alpha_start * (second[1] - first[1])))
        b = (round(first[0] + alpha_end * (second[0] - first[0])), round(first[1] + alpha_end * (second[1] - first[1])))
        cv2.line(frame, a, b, color, width, cv2.LINE_AA)


def _bridge_records(tracklets: dict[int, list[TrackPoint]], accepted: list[dict[str, str]]) -> list[dict[str, object]]:
    bridges = []
    for row in accepted:
        source = _observed_endpoint(tracklets, int(row["source_tracklet"]), first=False)
        candidate = _observed_endpoint(tracklets, int(row["candidate_tracklet"]), first=True)
        if source is None or candidate is None or candidate.frame <= source.frame:
            continue
        bridges.append({"row": row, "source": source, "candidate": candidate})
    return bridges


def write_mapping(path: Path, chain_mapping: dict[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["track_id", "chain_id"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({"track_id": track_id, "chain_id": chain_id} for track_id, chain_id in sorted(chain_mapping.items()))


def write_stitch_table(path: Path, rows: list[dict[str, str]], accepted: list[dict[str, str]], chain_mapping: dict[int, int]) -> None:
    accepted_keys = {(row["source_tracklet"], row["candidate_tracklet"]) for row in accepted}
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source_tracklet", "candidate_tracklet", "trajectory_fit_error", "accepted", "chain_id"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            key = (row.get("source_tracklet", ""), row.get("candidate_tracklet", ""))
            is_accepted = key in accepted_keys
            writer.writerow({
                "source_tracklet": key[0], "candidate_tracklet": key[1],
                "trajectory_fit_error": row.get("trajectory_fit_error", ""),
                "accepted": int(is_accepted),
                "chain_id": chain_mapping.get(int(key[0]), "") if is_accepted else "",
            })


def render_video(
    video: Path,
    tracklets: dict[int, list[TrackPoint]],
    boxes: dict[int, list[DetectionBox]],
    chain_mapping: dict[int, int],
    bridges: list[dict[str, object]],
    output: Path,
    fit_threshold: float,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create output video: {output}")
    by_frame: dict[int, list[tuple[int, TrackPoint]]] = defaultdict(list)
    for track_id, points in tracklets.items():
        for point in points:
            by_frame[point.frame].append((track_id, point))
    colors = _colors(chain_mapping)
    rendered = 0
    try:
        for frame_index in range(frame_count):
            ok, frame = capture.read()
            if not ok:
                break
            for track_id, point in by_frame.get(frame_index, []):
                chain_id = chain_mapping[track_id]
                color = colors[chain_id]
                visible = [candidate for candidate in tracklets[track_id] if candidate.frame <= frame_index][-TRAIL_LENGTH:]
                observed_visible = [candidate for candidate in visible if candidate.observed == 1]
                predicted_visible = [candidate for candidate in visible if candidate.observed == 0]
                for first, second in zip(observed_visible, observed_visible[1:]):
                    cv2.line(frame, _point(first.center_x, first.center_y), _point(second.center_x, second.center_y), color, 2, cv2.LINE_AA)
                for first, second in zip(predicted_visible, predicted_visible[1:]):
                    _draw_dashed_line(frame, _point(first.center_x, first.center_y), _point(second.center_x, second.center_y), (0, 180, 255), 2)
                center = _point(point.center_x, point.center_y)
                detection_box = _nearest_box(point, boxes.get(frame_index, []))
                if detection_box is not None:
                    cv2.rectangle(frame, _point(detection_box.x1, detection_box.y1), _point(detection_box.x2, detection_box.y2), color, 2, cv2.LINE_AA)
                    cv2.circle(frame, center, 5, color, -1, cv2.LINE_AA)
                else:
                    cv2.circle(frame, center, 6, (0, 180, 255), 2, cv2.LINE_AA)
                state = "OBS" if point.observed == 1 else "PRED"
                _text(frame, f"Chain {chain_id} {state}", (center[0] + 8, max(20, center[1] - 8)), color if point.observed else (0, 180, 255), 0.48)
            for bridge in bridges:
                source = bridge["source"]
                candidate = bridge["candidate"]
                if not (source.frame < frame_index < candidate.frame):
                    continue
                inferred = _point(*_bridge_point(source, candidate, frame_index))
                next_point = _point(*_bridge_point(source, candidate, min(candidate.frame, frame_index + 1)))
                color = colors[chain_mapping[int(bridge["row"]["source_tracklet"])] ]
                _draw_dashed_line(frame, inferred, next_point, (255, 255, 0), 4)
                cv2.circle(frame, inferred, 5, (255, 255, 0), -1, cv2.LINE_AA)
                if frame_index == source.frame + 1:
                    _text(frame, f"INFERRED stitch fit {float(bridge['row']['trajectory_fit_error']):.2f}px", (10, TITLE_BAR_HEIGHT + 22), (255, 220, 0), 0.5)
            cv2.rectangle(frame, (0, 0), (width, TITLE_BAR_HEIGHT), (18, 18, 18), -1)
            _text(frame, f"Current best Norfair reconstruction | fit <= {fit_threshold:.1f}px | frame {frame_index}", (10, 22), (255, 255, 255), 0.52)
            _text(frame, "filled box/circle=observed YOLO   orange hollow/dash=Norfair prediction   cyan dash=inferred stitch", (10, 45), (220, 220, 220), 0.4)
            writer.write(frame)
            rendered += 1
    finally:
        capture.release()
        writer.release()
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("tracklets_csv", type=Path)
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("detections_csv", type=Path)
    parser.add_argument("--fit-threshold", type=float, default=FIT_THRESHOLD)
    parser.add_argument("--output-video", type=Path, required=True)
    parser.add_argument("--mapping-csv", type=Path, required=True)
    parser.add_argument("--stitches-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tracklets = load_tracklets(args.tracklets_csv)
    feature_rows = [row for row in load_feature_rows(args.features_csv) if Path(row.get("video", "")).name == args.video.name]
    if not feature_rows:
        raise ValueError(f"Feature CSV has no rows for video {args.video.name}")
    accepted = select_accepted_stitches(feature_rows, args.fit_threshold)
    accepted_pairs = [(int(row["source_tracklet"]), int(row["candidate_tracklet"])) for row in accepted]
    chain_mapping = build_chain_mapping(set(tracklets), accepted_pairs)
    bridges = _bridge_records(tracklets, accepted)
    boxes = load_detection_boxes(args.detections_csv)
    write_mapping(args.mapping_csv, chain_mapping)
    write_stitch_table(args.stitches_csv, feature_rows, accepted, chain_mapping)
    rendered = render_video(args.video, tracklets, boxes, chain_mapping, bridges, args.output_video, args.fit_threshold)
    print(f"Tracklets: {len(tracklets)}")
    print(f"Accepted rank-1 stitches: {len(accepted)}")
    print(f"Renderable inferred bridges: {len(bridges)}")
    print(f"Chains: {len(set(chain_mapping.values()))}")
    print(f"Frames rendered: {rendered}")
    print(f"Reconstruction video: {args.output_video}")
    print(f"Chain mapping CSV: {args.mapping_csv}")
    print(f"Stitch table CSV: {args.stitches_csv}")


if __name__ == "__main__":
    main()
