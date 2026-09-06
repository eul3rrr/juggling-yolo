#!/usr/bin/env python3
"""Render the three recruiter-facing static demo videos from existing CSVs.

This renderer deliberately consumes detector, Norfair, pose, and accepted hand
outputs only. It never loads a model or performs inference.
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import math
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Sequence

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = PROJECT_ROOT / "videos/identical_balls_trick_000_018.mp4"
DEFAULT_DETECTIONS = PROJECT_ROOT / "detections/demo/identical_balls_trick_000_018_yolo26l_classes-32.csv"
DEFAULT_TRACKLETS = PROJECT_ROOT / "detections/demo/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv"
DEFAULT_POSE = PROJECT_ROOT / "detections/identical_balls_trick_000_018_yolo26s-pose.csv"
DEFAULT_ASSOCIATIONS = PROJECT_ROOT / "detections/demo/identical_balls_trick_000_018_hand_associations.csv"
DEFAULT_EVENTS = PROJECT_ROOT / "detections/demo/identical_balls_trick_000_018_hand_events.csv"
DEFAULT_STATE_TRACE = PROJECT_ROOT / "detections/demo/identical_balls_trick_000_018_hand_state_trace.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs/assets"

TRAIL_LENGTH = 30
BRIDGE_WINDOW = 30
TITLE_HEIGHT = 62
FONT = cv2.FONT_HERSHEY_SIMPLEX


@dataclass(frozen=True)
class TrackPoint:
    frame: int
    x: float
    y: float
    confidence: float
    observed: bool


@dataclass(frozen=True)
class Detection:
    frame: int
    x: float
    y: float
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


@dataclass(frozen=True)
class Wrist:
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class Pose:
    left: Wrist
    right: Wrist


@dataclass(frozen=True)
class Bridge:
    source_track: int
    target_track: int
    source_frame: int
    target_frame: int
    source: tuple[float, float]
    target: tuple[float, float]
    hand: str


def _required(reader: csv.DictReader, fields: Iterable[str], path: Path) -> None:
    missing = sorted(set(fields) - set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def load_tracklets(path: Path) -> dict[int, list[TrackPoint]]:
    """Load Norfair rows, retaining predicted rows for local track display."""
    grouped: dict[int, list[TrackPoint]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(reader, ("frame", "track_id", "center_x", "center_y", "confidence", "observed"), path)
        for line, row in enumerate(reader, start=2):
            try:
                point = TrackPoint(
                    int(row["frame"]), float(row["center_x"]), float(row["center_y"]),
                    float(row["confidence"]), bool(int(row["observed"])),
                )
                track_id = int(row["track_id"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path} line {line}: invalid tracklet row") from error
            if point.frame < 0:
                raise ValueError(f"{path} line {line}: frame must be nonnegative")
            grouped[track_id].append(point)
    return {track: sorted(points, key=lambda point: point.frame) for track, points in grouped.items()}


def load_detections(path: Path) -> dict[int, list[Detection]]:
    grouped: dict[int, list[Detection]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(reader, ("frame", "center_x", "center_y", "x1", "y1", "x2", "y2", "confidence"), path)
        for row in reader:
            detection = Detection(
                int(row["frame"]), float(row["center_x"]), float(row["center_y"]),
                float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"]),
                float(row["confidence"]),
            )
            grouped[detection.frame].append(detection)
    return dict(grouped)


def load_pose(path: Path) -> dict[int, Pose]:
    grouped: dict[int, Pose] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(
            reader,
            ("frame", "left_wrist_x", "left_wrist_y", "left_wrist_confidence", "right_wrist_x", "right_wrist_y", "right_wrist_confidence"),
            path,
        )
        for row in reader:
            grouped[int(row["frame"])] = Pose(
                Wrist(float(row["left_wrist_x"]), float(row["left_wrist_y"]), float(row["left_wrist_confidence"])),
                Wrist(float(row["right_wrist_x"]), float(row["right_wrist_y"]), float(row["right_wrist_confidence"])),
            )
    return grouped


def observed_points(points: Sequence[TrackPoint]) -> list[TrackPoint]:
    """Return only detector-observed points; predicted Norfair states are excluded."""
    return [point for point in points if point.observed]


def track_continuity(tracklets: dict[int, list[TrackPoint]], frame: int, trail_length: int = TRAIL_LENGTH) -> dict[int, list[TrackPoint]]:
    """Build short observed-only histories available at a frame."""
    start = frame - trail_length
    return {
        track: [point for point in observed_points(points) if start <= point.frame <= frame]
        for track, points in tracklets.items()
        if any(point.observed and start <= point.frame <= frame for point in points)
    }


def _find(parent: dict[int, int], item: int) -> int:
    if item not in parent:
        raise ValueError(f"Unknown tracklet {item}")
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


def build_hid_mapping(track_ids: Iterable[int], accepted_pairs: Iterable[tuple[int, int]]) -> dict[int, int]:
    """Union accepted hand links and assign deterministic component HIDs."""
    parent = {track_id: track_id for track_id in sorted(set(track_ids))}
    for source, target in accepted_pairs:
        source_root = _find(parent, source)
        target_root = _find(parent, target)
        if source_root != target_root:
            parent[target_root] = source_root
    roots = sorted({_find(parent, track_id) for track_id in parent})
    hid_by_root = {root: hid for hid, root in enumerate(roots, start=1)}
    return {track_id: hid_by_root[_find(parent, track_id)] for track_id in sorted(parent)}


def load_associations(path: Path) -> list[tuple[int, int, int, int, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(reader, ("source_track_id", "target_track_id", "source_end_frame", "target_start_frame", "resolved_hand", "association_type"), path)
        rows = []
        for row in reader:
            if row["association_type"].strip().upper() != "HAND":
                continue
            hand = row["resolved_hand"].strip().upper()
            rows.append((int(row["source_track_id"]), int(row["target_track_id"]), int(row["source_end_frame"]), int(row["target_start_frame"]), hand or "AMBIGUOUS"))
    return rows


def load_events(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(reader, ("track_id", "boundary_type", "boundary_frame", "event_type", "preferred_hand"), path)
        return list(reader)


def load_state_trace(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _required(reader, ("frame", "event_type", "track_id", "pending_after"), path)
        return list(reader)


_PENDING_RE = re.compile(r"T(\d+):\{([^}]*)\}")


def parse_pending(value: str | None) -> dict[int, tuple[str, ...]]:
    """Parse only the state trace's pending_after representation."""
    if not value:
        return {}
    pending: dict[int, tuple[str, ...]] = {}
    for track, hands in _PENDING_RE.findall(value):
        pending[int(track)] = tuple(hand.strip().upper() for hand in hands.split(",") if hand.strip())
    return pending


def index_pending_states(rows: Sequence[dict[str, str]]) -> dict[int, dict[int, tuple[str, ...]]]:
    states: dict[int, dict[int, tuple[str, ...]]] = {}
    current: dict[int, tuple[str, ...]] = {}
    for row in sorted(rows, key=lambda item: int(item["frame"])):
        current = parse_pending(row.get("pending_after"))
        states[int(row["frame"])] = dict(current)
    return states


def _endpoint(tracklets: dict[int, list[TrackPoint]], track_id: int, first: bool) -> TrackPoint:
    points = observed_points(tracklets[track_id])
    if not points:
        raise ValueError(f"Tracklet {track_id} has no observed points")
    return points[0] if first else points[-1]


def build_bridges(
    tracklets: dict[int, list[TrackPoint]],
    associations: Sequence[tuple[int, int, int, int, str]],
    events: Sequence[dict[str, str]],
) -> list[Bridge]:
    event_points = {
        (int(row["track_id"]), row["boundary_type"].upper(), int(row["boundary_frame"])):
        (float(row["boundary_x"]), float(row["boundary_y"]))
        for row in events
        if row.get("boundary_x") not in (None, "") and row.get("boundary_y") not in (None, "")
    }
    bridges = []
    for source_id, target_id, source_frame, target_frame, hand in associations:
        if source_id not in tracklets or target_id not in tracklets:
            raise ValueError(f"Association {source_id}->{target_id} references a missing tracklet")
        source_endpoint = _endpoint(tracklets, source_id, first=False)
        target_endpoint = _endpoint(tracklets, target_id, first=True)
        if source_endpoint.frame != source_frame or target_endpoint.frame != target_frame:
            raise ValueError(
                f"Association {source_id}->{target_id} expects observed endpoints "
                f"{source_frame}->{target_frame}, but the selected tracklets provide "
                f"{source_endpoint.frame}->{target_endpoint.frame}"
            )
        source = event_points.get((source_id, "END", source_frame))
        target = event_points.get((target_id, "START", target_frame))
        if source is None or target is None:
            raise ValueError(f"Association {source_id}->{target_id} has no matching event boundary coordinates")
        if target_frame <= source_frame:
            raise ValueError(f"Association {source_id}->{target_id} does not move forward in time")
        bridges.append(Bridge(source_id, target_id, source_frame, target_frame, source, target, hand))
    return bridges


def cubic_bezier_points(
    start: tuple[float, float],
    end: tuple[float, float],
    offset: float = 86.0,
    samples: int = 24,
    bend_sign: int = 1,
) -> list[tuple[float, float]]:
    """Return a visibly curved cubic connector, not an interpolated trajectory."""
    if samples < 2:
        raise ValueError("samples must be at least 2")
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(1.0, math.hypot(dx, dy))
    normal = (-dy / length * offset * bend_sign, dx / length * offset * bend_sign)
    control_a = (start[0] + dx * 0.34 + normal[0], start[1] + dy * 0.34 + normal[1])
    control_b = (end[0] - dx * 0.34 + normal[0], end[1] - dy * 0.34 + normal[1])
    points = []
    for index in range(samples):
        t = index / (samples - 1)
        u = 1.0 - t
        points.append((
            u**3 * start[0] + 3 * u**2 * t * control_a[0] + 3 * u * t**2 * control_b[0] + t**3 * end[0],
            u**3 * start[1] + 3 * u**2 * t * control_a[1] + 3 * u * t**2 * control_b[1] + t**3 * end[1],
        ))
    return points


def dashed_polyline(points: Sequence[tuple[float, float]], dash: int = 12, gap: int = 8) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Convert a polyline into dash segments for thick graphical bridges."""
    if len(points) < 2:
        return []
    segments = []
    for first, second in zip(points, points[1:]):
        x1, y1 = first
        x2, y2 = second
        distance = math.hypot(x2 - x1, y2 - y1)
        if distance == 0:
            continue
        ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
        cursor = 0.0
        while cursor < distance:
            end = min(distance, cursor + dash)
            segments.append(((round(x1 + ux * cursor), round(y1 + uy * cursor)), (round(x1 + ux * end), round(y1 + uy * end))))
            cursor += dash + gap
    return segments


def event_windows(bridges: Sequence[Bridge], frame_count: int, window: int = BRIDGE_WINDOW) -> dict[int, list[Bridge]]:
    indexed: dict[int, list[Bridge]] = defaultdict(list)
    for bridge in bridges:
        for frame in range(max(0, bridge.target_frame - window), min(frame_count, bridge.target_frame + window + 1)):
            indexed[frame].append(bridge)
    return dict(indexed)


def ffmpeg_command(output: Path, width: int, height: int, fps: float, crf: int = 23, ffmpeg: str = "ffmpeg") -> list[str]:
    """Build the shared raw-BGR H.264 output command."""
    if not 0 <= crf <= 51:
        raise ValueError("CRF must be between 0 and 51")
    rate = Fraction(fps).limit_denominator(100_000)
    rate_text = f"{rate.numerator}/{rate.denominator}"
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", rate_text, "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-bf", "0", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]


def _color(index: int, total: int, saturation: float = 0.72, value: float = 0.94) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((index * 0.61803398875) % 1.0, saturation, value)
    return round(blue * 255), round(green * 255), round(red * 255)


def _text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int] = (240, 244, 246), scale: float = 0.52, thickness: int = 1) -> None:
    cv2.putText(frame, text, origin, FONT, scale, (8, 12, 14), thickness + 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, FONT, scale, color, thickness, cv2.LINE_AA)


def _panel(frame, title: str, subtitle: str, width: int, height: int, accent: tuple[int, int, int] = (208, 231, 239)) -> None:
    cv2.rectangle(frame, (0, 0), (width, TITLE_HEIGHT), (14, 20, 24), -1)
    cv2.rectangle(frame, (0, TITLE_HEIGHT - 2), (width, TITLE_HEIGHT), accent, -1)
    _text(frame, title, (22, 28), (242, 246, 247), 0.68, 2)
    _text(frame, subtitle, (22, 51), (174, 194, 201), 0.40)


def _draw_trails(frame, histories: dict[int, list[TrackPoint]], colors: dict[int, tuple[int, int, int]], labels: dict[int, str] | None = None) -> None:
    for track_id, points in histories.items():
        if not points:
            continue
        color = colors[track_id]
        for first, second in zip(points, points[1:]):
            if second.frame == first.frame + 1:
                cv2.line(frame, (round(first.x), round(first.y)), (round(second.x), round(second.y)), color, 2, cv2.LINE_AA)
        current = points[-1]
        center = (round(current.x), round(current.y))
        cv2.circle(frame, center, 7, color, -1, cv2.LINE_AA)
        cv2.circle(frame, center, 10, (245, 248, 249), 1, cv2.LINE_AA)
        if labels is not None:
            _text(frame, labels[track_id], (center[0] + 12, max(TITLE_HEIGHT + 20, center[1] - 9)), color, 0.46, 1)


def _draw_boxes(frame, detections: Sequence[Detection], color: tuple[int, int, int] = (213, 232, 238)) -> None:
    for detection in detections:
        p1 = (round(detection.x1), round(detection.y1))
        p2 = (round(detection.x2), round(detection.y2))
        cv2.rectangle(frame, p1, p2, color, 2, cv2.LINE_AA)
        _text(frame, f"sports ball {detection.confidence:.2f}", (p1[0], max(TITLE_HEIGHT + 16, p1[1] - 7)), color, 0.38)


def _draw_pose(frame, pose: Pose | None) -> None:
    if pose is None:
        return
    for label, wrist, color in (("L", pose.left, (221, 179, 82)), ("R", pose.right, (87, 202, 220))):
        if wrist.confidence < 0.35:
            continue
        center = (round(wrist.x), round(wrist.y))
        cv2.circle(frame, center, 14, color, 2, cv2.LINE_AA)
        cv2.circle(frame, center, 4, color, -1, cv2.LINE_AA)
        _text(frame, f"{label} wrist", (center[0] + 17, center[1] + 5), color, 0.40)


def _draw_bridge(frame, bridge: Bridge, frame_index: int, sequence: int) -> None:
    bend_sign = 1 if sequence % 2 else -1
    points = cubic_bezier_points(bridge.source, bridge.target, bend_sign=bend_sign)
    for first, second in dashed_polyline(points, dash=18, gap=11):
        cv2.line(frame, first, second, (64, 220, 237), 8, cv2.LINE_AA)
        cv2.line(frame, first, second, (225, 249, 251), 3, cv2.LINE_AA)
    source = (round(bridge.source[0]), round(bridge.source[1]))
    target = (round(bridge.target[0]), round(bridge.target[1]))
    cv2.circle(frame, source, 13, (64, 220, 237), 3, cv2.LINE_AA)
    cv2.circle(frame, target, 13, (64, 220, 237), 3, cv2.LINE_AA)
    cv2.circle(frame, source, 5, (225, 249, 251), -1, cv2.LINE_AA)
    cv2.circle(frame, target, 5, (225, 249, 251), -1, cv2.LINE_AA)
    # OpenCV's Hershey fonts are ASCII-only; avoid replacement glyphs in baked labels.
    label = f"HAND / {bridge.hand}   T{bridge.source_track} -> T{bridge.target_track}"
    (text_width, text_height), baseline = cv2.getTextSize(label, FONT, 0.48, 1)
    x = frame.shape[1] - text_width - 24
    y = TITLE_HEIGHT + text_height + 12 + (sequence - 1) * (text_height + baseline + 14)
    cv2.rectangle(frame, (x - 6, y - text_height - 6), (x + text_width + 6, y + baseline + 5), (12, 24, 28), -1)
    cv2.rectangle(frame, (x - 6, y - text_height - 6), (x + text_width + 6, y + baseline + 5), (64, 220, 237), 1)
    _text(frame, label, (x, y), (225, 249, 251), 0.48, 1)


def _pending_wrist(frame, pending: dict[int, tuple[str, ...]], pose: Pose | None) -> None:
    if pose is None:
        return
    y = TITLE_HEIGHT + 28
    for track_id, hands in sorted(pending.items()):
        if len(hands) != 1:
            _text(frame, f"PENDING T{track_id} · hand unresolved", (22, y), (187, 204, 209), 0.45)
            y += 22
            continue
        hand = hands[0]
        wrist = pose.left if hand == "LEFT" else pose.right
        center = (round(wrist.x), round(wrist.y))
        label = f"{hand} / T{track_id} PENDING"
        (text_width, text_height), baseline = cv2.getTextSize(label, FONT, 0.43, 1)
        x = max(8, min(center[0] + 38, frame.shape[1] - text_width - 18))
        label_y = max(TITLE_HEIGHT + text_height + 8, min(center[1] - 22, frame.shape[0] - baseline - 8))
        cv2.circle(frame, center, 19, (64, 220, 237), 2, cv2.LINE_AA)
        cv2.line(frame, center, (x - 6, label_y - text_height // 2), (64, 220, 237), 2, cv2.LINE_AA)
        cv2.rectangle(frame, (x - 6, label_y - text_height - 6), (x + text_width + 6, label_y + baseline + 5), (12, 24, 28), -1)
        cv2.rectangle(frame, (x - 6, label_y - text_height - 6), (x + text_width + 6, label_y + baseline + 5), (64, 220, 237), 1)
        _text(frame, label, (x, label_y), (225, 249, 251), 0.43, 1)


def _latest_pending(states: dict[int, dict[int, tuple[str, ...]]], frame: int, current: dict[int, tuple[str, ...]]) -> dict[int, tuple[str, ...]]:
    if frame in states:
        return states[frame]
    return current


def render_frame(
    source_frame,
    frame_index: int,
    mode: str,
    width: int,
    height: int,
    tracklets: dict[int, list[TrackPoint]],
    detections: dict[int, list[Detection]],
    poses: dict[int, Pose],
    hid_mapping: dict[int, int],
    bridge_index: dict[int, list[Bridge]],
    pending: dict[int, tuple[str, ...]],
) -> object:
    frame = source_frame.copy()
    histories = track_continuity(tracklets, frame_index)
    if mode == "local":
        local_colors = {track: _color(track, max(tracklets) + 1) for track in tracklets}
        _draw_trails(frame, histories, local_colors, {track: f"T{track}" for track in histories})
        _draw_boxes(frame, detections.get(frame_index, []))
        _panel(frame, "01  DETECTION + LOCAL TRACKING", "YOLO sports-ball boxes  /  Norfair observed tracklets  /  local T# only", width, height)
    elif mode == "hand":
        local_colors = {track: _color(track, max(tracklets) + 1) for track in tracklets}
        _draw_trails(frame, histories, local_colors, {track: f"T{track}" for track in histories})
        _draw_pose(frame, poses.get(frame_index))
        for sequence, bridge in enumerate(bridge_index.get(frame_index, []), start=1):
            _draw_bridge(frame, bridge, frame_index, sequence)
        _pending_wrist(frame, pending, poses.get(frame_index))
        _panel(frame, "02  HAND-AWARE STITCHING", "local T# colors  /  anatomical wrists  /  accepted hand associations", width, height, (64, 220, 237))
    else:
        hid_colors = {hid: _color(hid, max(hid_mapping.values()) + 1, 0.62, 0.96) for hid in set(hid_mapping.values())}
        identity_colors = {track: hid_colors[hid_mapping[track]] for track in histories}
        identity_labels = {track: f"HID {hid_mapping[track]}" for track in histories}
        _draw_trails(frame, histories, identity_colors, identity_labels)
        _panel(frame, "03  RECONSTRUCTED IDENTITY", "stable HID components  /  observed-only short trails  /  no predicted positions", width, height, (124, 209, 221))
    return frame


def _metadata(video: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open source video: {video}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if fps <= 0 or width <= 0 or height <= 0 or count <= 0:
        raise ValueError(f"Source video has invalid metadata: {video}")
    return fps, width, height, count


def render(args: argparse.Namespace) -> None:
    paths = [args.video, args.detections, args.tracklets, args.pose, args.associations, args.events, args.state_trace]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required demo input does not exist: " + ", ".join(missing))
    if shutil.which(args.ffmpeg) is None:
        raise RuntimeError(f"ffmpeg executable not found: {args.ffmpeg}")
    fps, width, height, frame_count = _metadata(args.video)
    tracklets = load_tracklets(args.tracklets)
    detections = load_detections(args.detections)
    poses = load_pose(args.pose)
    associations = load_associations(args.associations)
    events = load_events(args.events)
    bridges = build_bridges(tracklets, associations, events)
    hid_mapping = build_hid_mapping(tracklets, [(source, target) for source, target, _, _, _ in associations])
    pending_states = index_pending_states(load_state_trace(args.state_trace))
    bridge_index = event_windows(bridges, frame_count)
    poster_frame = min(120, frame_count - 1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "local": args.output_dir / "demo-local-tracking.mp4",
        "hand": args.output_dir / "demo-hand-stitching.mp4",
        "identity": args.output_dir / "demo-reconstructed-identity.mp4",
    }
    posters = {mode: path.with_suffix(".jpg") for mode, path in outputs.items()}
    processes = [subprocess.Popen(ffmpeg_command(path, width, height, fps, args.crf, args.ffmpeg), stdin=subprocess.PIPE) for path in outputs.values()]
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        for process in processes:
            process.kill()
        raise RuntimeError(f"Could not open source video: {args.video}")
    current_pending: dict[int, tuple[str, ...]] = {}
    rendered = 0
    try:
        for frame_index in range(frame_count):
            ok, source_frame = capture.read()
            if not ok:
                raise RuntimeError(f"Source video ended before frame {frame_index} of {frame_count}")
            current_pending = _latest_pending(pending_states, frame_index, current_pending)
            for process, mode in zip(processes, outputs):
                output_frame = render_frame(source_frame, frame_index, mode, width, height, tracklets, detections, poses, hid_mapping, bridge_index, current_pending)
                if frame_index == poster_frame:
                    cv2.imwrite(str(posters[mode]), output_frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                assert process.stdin is not None
                process.stdin.write(output_frame.tobytes())
            rendered += 1
    finally:
        capture.release()
        for process in processes:
            if process.stdin is not None:
                process.stdin.close()
        return_codes = [process.wait() for process in processes]
    if rendered != frame_count:
        raise RuntimeError(f"Rendered {rendered} frames, expected {frame_count}")
    if any(code != 0 for code in return_codes):
        raise RuntimeError(f"ffmpeg failed with return codes: {return_codes}")
    print(f"Source: {args.video} ({width}x{height}, {fps:.6f} fps, {frame_count} frames)")
    print(f"Output metadata: H.264 libx264, yuv420p, {width}x{height}, {fps:.6f} fps, {rendered} frames, no audio")
    print(f"Accepted hand associations: {len(associations)}; reconstructed HIDs: {len(set(hid_mapping.values()))}")
    for path in (*outputs.values(), *posters.values()):
        print(f"{path}: {path.stat().st_size / 1024 / 1024:.2f} MiB")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--detections", type=Path, default=DEFAULT_DETECTIONS)
    parser.add_argument("--tracklets", type=Path, default=DEFAULT_TRACKLETS)
    parser.add_argument("--pose", type=Path, default=DEFAULT_POSE)
    parser.add_argument("--associations", type=Path, default=DEFAULT_ASSOCIATIONS)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="Authoritative event CSV (validated for CLI swaps)")
    parser.add_argument("--state-trace", type=Path, default=DEFAULT_STATE_TRACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--crf", type=int, default=23)
    args = parser.parse_args(argv)
    if args.crf < 0 or args.crf > 51:
        parser.error("--crf must be between 0 and 51")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    try:
        render(parse_args(argv))
    except (FileNotFoundError, RuntimeError, ValueError, OSError) as error:
        print(f"render_demo_videos.py: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
