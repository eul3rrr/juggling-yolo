#!/usr/bin/env python3
"""Run generic Ultralytics tracking on every frame of one video."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import torch
from ultralytics import YOLO
from ultralytics.utils import YAML

CSV_FIELDS = [
    "video", "frame", "time_seconds", "tracker", "track_id", "class_id",
    "class_name", "confidence", "x1", "y1", "x2", "y2", "center_x",
    "center_y", "width", "height",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generic YOLO tracking on every video frame."
    )
    parser.add_argument("input_video", type=Path)
    parser.add_argument("--model", default="yolo26s.pt")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--classes", type=int, nargs="+", default=[32])
    parser.add_argument(
        "--tracker", default=str(PROJECT_ROOT / "configs" / "bytetrack.yaml")
    )
    parser.add_argument("--tracker-label", default=None)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument(
        "--detections-dir", type=Path, default=PROJECT_ROOT / "detections"
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--trail-length", type=int, default=30)
    return parser.parse_args()


def resolve_device(requested: str) -> str:
    return requested if requested != "auto" else ("0" if torch.cuda.is_available() else "cpu")


def safe_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "tracker"


def video_metadata(path: Path) -> tuple[float, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid video metadata: fps={fps}, width={width}, height={height}")
    return fps, width, height


def validate_tracker(path: Path) -> tuple[str, bool]:
    if not path.is_file():
        raise FileNotFoundError(f"Tracker config does not exist: {path}")
    config = YAML.load(str(path))
    tracker_type = config.get("tracker_type")
    if tracker_type not in {"bytetrack", "botsort"}:
        raise ValueError(f"Unsupported tracker_type in {path}: {tracker_type!r}")
    if tracker_type == "botsort":
        if "with_reid" not in config:
            raise ValueError(f"BoT-SORT config must define with_reid: {path}")
        reid_enabled = bool(config["with_reid"])
    else:
        reid_enabled = False
    return str(tracker_type), reid_enabled


def draw_tracks(frame, tracks, trails, names):
    for track_id, x1, y1, x2, y2, class_id, confidence, center in tracks:
        color = (0, 220, 0)
        if track_id is not None:
            trail = trails[track_id]
            trail.append(center)
            for previous, current in zip(trail, list(trail)[1:]):
                cv2.line(frame, previous, current, color, 2, cv2.LINE_AA)
        cv2.rectangle(frame, (round(x1), round(y1)), (round(x2), round(y2)), color, 2)
        label = f"id {track_id if track_id is not None else '-'} {names[int(class_id)]} {confidence:.2f}"
        cv2.putText(frame, label, (round(x1), max(18, round(y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def main() -> None:
    args = parse_args()
    input_video = args.input_video.resolve()
    if not input_video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf must be between 0 and 1")
    if args.imgsz <= 0 or args.trail_length <= 0:
        raise ValueError("--imgsz and --trail-length must be positive")

    tracker_path = Path(args.tracker)
    if not tracker_path.is_absolute():
        tracker_path = (PROJECT_ROOT / tracker_path).resolve()
    tracker_type, reid_enabled = validate_tracker(tracker_path)
    tracker_label = safe_tag(args.tracker_label or tracker_path.stem)
    device = resolve_device(args.device)
    model_reference = args.model
    project_model = PROJECT_ROOT / args.model
    if not Path(args.model).is_absolute() and project_model.is_file():
        model_reference = str(project_model)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.detections_dir.mkdir(parents=True, exist_ok=True)
    fps, width, height = video_metadata(input_video)
    run_tag = f"{input_video.stem}_{safe_tag(Path(args.model).stem)}_{tracker_label}"
    annotated_path = args.output_dir / f"{run_tag}.mp4"
    csv_path = args.detections_dir / f"{run_tag}.csv"

    model = YOLO(model_reference)
    if model.task != "detect":
        raise ValueError(f"Expected a detection checkpoint, but task is {model.task!r}")
    print(f"Tracker: {tracker_label} ({tracker_type}, ReID enabled: {reid_enabled})")
    print(f"Requested device: {args.device}; resolved device: {device}")

    writer = cv2.VideoWriter(str(annotated_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not create annotated video: {annotated_path}")

    frame_count = 0
    row_count = 0
    track_ids: set[int] = set()
    trails: dict[int, deque[tuple[int, int]]] = {}
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            csv_writer.writeheader()
            results = model.track(source=str(input_video), stream=True, persist=True,
                                  conf=args.conf, imgsz=args.imgsz, classes=args.classes,
                                  device=device, vid_stride=1, tracker=str(tracker_path),
                                  save=False, verbose=False)
            for frame_index, result in enumerate(results):
                frame = result.orig_img.copy()
                boxes = result.boxes
                tracks = []
                if boxes is not None and len(boxes):
                    xyxy = boxes.xyxy.detach().cpu().tolist()
                    confidences = boxes.conf.detach().cpu().tolist()
                    class_ids = boxes.cls.detach().cpu().to(torch.int64).tolist()
                    ids = boxes.id.detach().cpu().to(torch.int64).tolist() if boxes.id is not None else []
                    for index, (coordinates, confidence, class_id) in enumerate(zip(xyxy, confidences, class_ids)):
                        x1, y1, x2, y2 = (float(value) for value in coordinates)
                        track_id = int(ids[index]) if index < len(ids) else None
                        center = (round((x1 + x2) / 2), round((y1 + y2) / 2))
                        if track_id is not None:
                            track_ids.add(track_id)
                            trails.setdefault(track_id, deque(maxlen=args.trail_length))
                        tracks.append((track_id, x1, y1, x2, y2, class_id, float(confidence), center))
                        class_name = str(result.names[int(class_id)])
                        csv_writer.writerow({"video": input_video.name, "frame": frame_index,
                            "time_seconds": f"{frame_index / fps:.6f}", "tracker": tracker_label,
                            "track_id": "" if track_id is None else track_id, "class_id": int(class_id),
                            "class_name": class_name, "confidence": f"{float(confidence):.6f}",
                            "x1": f"{x1:.3f}", "y1": f"{y1:.3f}", "x2": f"{x2:.3f}", "y2": f"{y2:.3f}",
                            "center_x": f"{center[0]:.3f}", "center_y": f"{center[1]:.3f}",
                            "width": f"{x2 - x1:.3f}", "height": f"{y2 - y1:.3f}"})
                        row_count += 1
                draw_tracks(frame, tracks, trails, result.names)
                writer.write(frame)
                frame_count += 1
    finally:
        writer.release()

    print(f"Frames processed: {frame_count}")
    print(f"Tracked rows written: {row_count}")
    print(f"Unique track IDs: {len(track_ids)}")
    print(f"Annotated video: {annotated_path.resolve()}")
    print(f"Detection CSV: {csv_path.resolve()}")


if __name__ == "__main__":
    main()
