#!/usr/bin/env python3
"""Prepare and manually review short videos for proposed tracklet stitches."""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2

TRACKLET_FIELDS = ("frame", "time_seconds", "track_id", "confidence", "center_x", "center_y")
CANDIDATE_FIELDS = (
    "source_tracklet", "candidate_tracklet", "gap_frames", "prediction_error",
    "source_end_frame", "candidate_start_frame", "predicted_x", "predicted_y",
    "candidate_start_x", "candidate_start_y", "end_velocity_x", "end_velocity_y",
    "candidate_rank",
)
LABEL_FIELDS = (
    "video", "source_tracklet", "candidate_tracklet", "gap_frames",
    "prediction_error", "label", "clip_path", "clip_index",
)
LABEL_BY_KEY = {
    ord("c"): "correct",
    ord("w"): "wrong",
    ord("u"): "unclear",
}
LABEL_ALIASES = {"c": "correct", "w": "wrong", "u": "unclear"}
MANIFEST_FIELDS = (
    "clip_index", "video", "clip_path", "source_tracklet", "candidate_tracklet",
    "gap_frames", "prediction_error", "source_end_frame", "candidate_start_frame",
    "candidate_rank",
)


def _stored_path(path: Path) -> str:
    """Use a repository-relative path when possible, avoiding local usernames."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_stored_path(value: str) -> Path:
    """Resolve repository-relative paths while accepting legacy absolute paths."""
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Candidate:
    source_tracklet: int
    candidate_tracklet: int
    gap_frames: int
    prediction_error: float
    source_end_frame: int
    candidate_start_frame: int
    predicted_x: float
    predicted_y: float
    candidate_start_x: float
    candidate_start_y: float
    end_velocity_x: float
    end_velocity_y: float
    candidate_rank: int


def _number(row: dict[str, str], field: str, line: int, integer: bool = False):
    try:
        value = int(row[field]) if integer else float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"CSV line {line}: {field} must be a {'integer' if integer else 'number'}") from error
    if not math.isfinite(value):
        raise ValueError(f"CSV line {line}: {field} must be finite")
    return value


def load_candidates(path: Path) -> list[Candidate]:
    """Parse the candidate CSV without applying or changing matching rules."""
    if not path.is_file():
        raise FileNotFoundError(f"Stitch candidate CSV does not exist: {path}")
    result = []
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"Candidate CSV has no header: {path}")
        missing = [field for field in CANDIDATE_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Candidate CSV is missing required columns: {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            values = {field: _number(row, field, line, field in {
                "source_tracklet", "candidate_tracklet", "gap_frames", "source_end_frame",
                "candidate_start_frame", "candidate_rank",
            }) for field in CANDIDATE_FIELDS}
            if any(values[field] < 0 for field in ("gap_frames", "source_end_frame", "candidate_start_frame")):
                raise ValueError(f"CSV line {line}: frame and gap values must be nonnegative")
            result.append(Candidate(**values))
    return result


def load_tracklets(path: Path) -> dict[int, list[tuple[int, float, float]]]:
    """Load only frame and position data needed for review overlays."""
    if not path.is_file():
        raise FileNotFoundError(f"Tracklets CSV does not exist: {path}")
    grouped: dict[int, list[tuple[int, float, float]]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"Tracklets CSV has no header: {path}")
        missing = [field for field in TRACKLET_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Tracklets CSV is missing required columns: {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            frame = _number(row, "frame", line, True)
            track_id = _number(row, "track_id", line, True)
            x = _number(row, "center_x", line)
            y = _number(row, "center_y", line)
            grouped.setdefault(track_id, []).append((frame, x, y))
    return {track_id: sorted(points) for track_id, points in grouped.items()}


def clip_bounds(source_end_frame: int, candidate_start_frame: int, fps: float,
                frame_count: int, pre_seconds: float = 1.0, post_seconds: float = 1.0) -> tuple[int, int]:
    if fps <= 0 or frame_count <= 0:
        raise ValueError("fps and frame_count must be positive")
    if pre_seconds < 0 or post_seconds < 0:
        raise ValueError("pre_seconds and post_seconds must be nonnegative")
    start = max(0, source_end_frame - round(pre_seconds * fps))
    end = min(frame_count - 1, candidate_start_frame + round(post_seconds * fps))
    return start, max(start, end)


def interpolate_bridge_point(candidate: Candidate, frame_index: int) -> tuple[float, float]:
    """Interpolate from the observed source endpoint to candidate start, with clamping."""
    elapsed = candidate.candidate_start_frame - candidate.source_end_frame
    source_x = candidate.predicted_x - candidate.end_velocity_x * elapsed
    source_y = candidate.predicted_y - candidate.end_velocity_y * elapsed
    if elapsed <= 0:
        return candidate.candidate_start_x, candidate.candidate_start_y
    alpha = max(0.0, min(1.0, (frame_index - candidate.source_end_frame) / elapsed))
    return (source_x + alpha * (candidate.candidate_start_x - source_x),
            source_y + alpha * (candidate.candidate_start_y - source_y))


def _key(video: str, candidate: Candidate) -> tuple[str, str, str]:
    return video, str(candidate.source_tracklet), str(candidate.candidate_tracklet)


def _key_parts(video: str, source_tracklet: object, candidate_tracklet: object) -> tuple[str, str, str]:
    return str(_resolve_stored_path(video)), str(source_tracklet), str(candidate_tracklet)


def _read_labels(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not {"video", "source_tracklet", "candidate_tracklet", "label"}.issubset(reader.fieldnames):
            raise ValueError(f"Labels CSV is missing required columns: {path}")
        rows = {}
        for row in reader:
            row["label"] = LABEL_ALIASES.get(row.get("label", ""), row.get("label", ""))
            rows[_key_parts(row["video"], row["source_tracklet"], row["candidate_tracklet"])] = row
        return rows


def write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in LABEL_FIELDS} for row in rows)


def _safe(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value))


def _point(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def _text(frame, text: str, origin: tuple[int, int], color: tuple[int, int, int], scale: float = .55) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def render_clip(video: Path, output: Path, tracklets: dict[int, list[tuple[int, float, float]]],
                candidate: Candidate, start: int, end: int, fps: float, width: int, height: int) -> None:
    capture = cv2.VideoCapture(str(video))
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not capture.isOpened() or not writer.isOpened():
        capture.release(); writer.release()
        raise RuntimeError(f"Could not open video or create clip: {video} / {output}")
    source = tracklets.get(candidate.source_tracklet, [])
    target = tracklets.get(candidate.candidate_tracklet, [])
    colors = ((255, 80, 40), (220, 60, 220))  # BGR: blue source, magenta candidate
    capture.set(cv2.CAP_PROP_POS_FRAMES, start)
    try:
        for frame_index in range(start, end + 1):
            ok, frame = capture.read()
            if not ok:
                break
            for points, color, label in ((source, colors[0], "SOURCE"), (target, colors[1], "CANDIDATE")):
                visible = [(x, y) for f, x, y in points if f <= frame_index][-30:]
                for first, second in zip(visible, visible[1:]):
                    cv2.line(frame, _point(*first), _point(*second), color, 4, cv2.LINE_AA)
                if visible:
                    cv2.circle(frame, _point(*visible[-1]), 7, color, -1, cv2.LINE_AA)
                if visible and points and visible[-1] == (points[-1][1], points[-1][2]) and frame_index == points[-1][0]:
                    _text(frame, f"{label} {candidate.source_tracklet if label == 'SOURCE' else candidate.candidate_tracklet}",
                          (_point(*visible[-1])[0] + 8, max(20, _point(*visible[-1])[1] - 8)), color)
            source_point = _point(*interpolate_bridge_point(candidate, candidate.source_end_frame))
            target_point = _point(candidate.candidate_start_x, candidate.candidate_start_y)
            cv2.line(frame, source_point, target_point, (0, 190, 255), 6, cv2.LINE_AA)
            cv2.drawMarker(frame, source_point, (0, 140, 255), cv2.MARKER_DIAMOND, 16, 3)
            cv2.drawMarker(frame, target_point, (0, 220, 255), cv2.MARKER_CROSS, 18, 3)
            cv2.circle(frame, _point(*interpolate_bridge_point(candidate, frame_index)), 8, (0, 120, 255), -1, cv2.LINE_AA)
            cv2.rectangle(frame, (0, 0), (width, 38), (20, 20, 20), -1)
            _text(frame, f"SOURCE {candidate.source_tracklet}  CANDIDATE {candidate.candidate_tracklet}  "
                  f"GAP {candidate.gap_frames}  ERROR {candidate.prediction_error:.2f}  FRAME {frame_index}",
                  (10, 26), (255, 255, 255), .52)
            writer.write(frame)
    finally:
        capture.release(); writer.release()


def prepare(video: Path, tracklets_csv: Path, stitches_csv: Path, output_dir: Path, labels_csv: Path,
            pre_seconds: float = 1.0, post_seconds: float = 1.0) -> None:
    candidates = load_candidates(stitches_csv)
    tracklets = load_tracklets(tracklets_csv)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS)); frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)); height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)); capture.release()
    start_rows = _read_labels(labels_csv)
    video_name = _stored_path(video)
    manifest_rows = []
    label_rows = []
    output_dir.mkdir(parents=True, exist_ok=True)
    current_keys = {_key(video_name, candidate) for candidate in candidates}
    # Keep labels belonging to other prepared videos in the combined file.
    for old in start_rows.values():
        if _key_parts(old["video"], old["source_tracklet"], old["candidate_tracklet"]) not in current_keys:
            label_rows.append({field: old.get(field, "") for field in LABEL_FIELDS})
    for index, candidate in enumerate(candidates):
        start, end = clip_bounds(candidate.source_end_frame, candidate.candidate_start_frame, fps, frame_count, pre_seconds, post_seconds)
        filename = (f"{index:05d}_source-{_safe(candidate.source_tracklet)}_candidate-{_safe(candidate.candidate_tracklet)}_"
                    f"gap-{_safe(candidate.gap_frames)}_rank-{_safe(candidate.candidate_rank)}_error-{_safe(f'{candidate.prediction_error:.2f}')}.mp4")
        clip_path = output_dir / filename
        render_clip(video, clip_path, tracklets, candidate, start, end, fps, width, height)
        manifest = {"clip_index": str(index), "video": video_name, "clip_path": _stored_path(clip_path),
                    "source_tracklet": str(candidate.source_tracklet), "candidate_tracklet": str(candidate.candidate_tracklet),
                    "gap_frames": str(candidate.gap_frames), "prediction_error": str(candidate.prediction_error),
                    "source_end_frame": str(candidate.source_end_frame), "candidate_start_frame": str(candidate.candidate_start_frame),
                    "candidate_rank": str(candidate.candidate_rank)}
        manifest_rows.append(manifest)
        old = start_rows.get(_key(video_name, candidate))
        label_rows.append({**manifest, "label": old.get("label", "") if old else ""})
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS); writer.writeheader(); writer.writerows(manifest_rows)
    write_labels(labels_csv, label_rows)


def review(labels_csv: Path, start_index: int, only_video: str | None, window_name: str,
           include_labeled: bool, manifest: Path | None = None) -> None:
    with labels_csv.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if manifest and not any(row.get("clip_path") for row in rows):
        with manifest.open(newline="", encoding="utf-8") as file:
            clips = {row["clip_index"]: row["clip_path"] for row in csv.DictReader(file)}
        for row in rows: row["clip_path"] = clips.get(row.get("clip_index", ""), "")
    items = [row for row in rows if (only_video is None or row.get("video") == only_video) and (include_labeled or not row.get("label"))]
    for position, row in enumerate(items[start_index:], start=start_index):
        stored_clip = row.get("clip_path", "")
        clip = _resolve_stored_path(stored_clip) if stored_clip else Path()
        if not stored_clip or not clip.is_file():
            raise FileNotFoundError(f"Clip path is missing or does not exist: {stored_clip}")
        key = None
        while True:
            video = cv2.VideoCapture(str(clip))
            if not video.isOpened():
                raise RuntimeError(f"Could not open review clip: {stored_clip}")
            decision = None
            while True:
                ok, frame = video.read()
                if not ok:
                    break
                _text(frame, f"ITEM {position + 1}/{len(items)}  LABEL: {row.get('label') or 'blank'}  c/w/u/s/q", (10, 25), (255, 255, 255))
                cv2.imshow(window_name, frame)
                raw_key = cv2.waitKey(30)
                key = raw_key & 0xFF if raw_key >= 0 else -1
                if key in (*LABEL_BY_KEY, ord("s"), ord("q")):
                    decision = key
                    break
            video.release()
            if decision is not None:
                key = decision
                break
        if key == ord("q"): break
        if key in LABEL_BY_KEY:
            row["label"] = LABEL_BY_KEY[key]
            write_labels(labels_csv, rows)
    cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prep = subparsers.add_parser("prepare")
    prep.add_argument("video", type=Path); prep.add_argument("tracklets_csv", type=Path); prep.add_argument("stitches_csv", type=Path)
    prep.add_argument("--output-dir", type=Path, default=None); prep.add_argument("--labels-csv", type=Path, default=PROJECT_ROOT / "detections" / "stitch_review_labels.csv")
    prep.add_argument("--pre-seconds", type=float, default=1.0); prep.add_argument("--post-seconds", type=float, default=1.0)
    rev = subparsers.add_parser("review")
    rev.add_argument("labels_csv", type=Path); rev.add_argument("--start-index", type=int, default=0); rev.add_argument("--only-video"); rev.add_argument("--window-name", default="Stitch review"); rev.add_argument("--include-labeled", action="store_true"); rev.add_argument("--manifest", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        video = args.video.resolve()
        output = (args.output_dir or PROJECT_ROOT / "outputs" / "stitch_review" / video.stem).resolve()
        prepare(video, args.tracklets_csv.resolve(), args.stitches_csv.resolve(), output, args.labels_csv.resolve(), args.pre_seconds, args.post_seconds)
        print(f"Prepared {len(load_candidates(args.stitches_csv.resolve()))} stitch clips in {output}")
    else:
        review(args.labels_csv.resolve(), args.start_index, args.only_video, args.window_name, args.include_labeled, args.manifest.resolve() if args.manifest else None)


if __name__ == "__main__":
    main()
