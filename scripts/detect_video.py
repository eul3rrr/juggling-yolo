#!/usr/bin/env python3
"""Run frame-by-frame Ultralytics YOLO detection on one video."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

# When invoked directly (./detect_video.py), the shebang initially selects the
# system Python. Re-execute with this experiment's isolated environment before
# importing third-party dependencies.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import torch
from ultralytics import YOLO

CSV_FIELDS = [
    "video",
    "frame",
    "time_seconds",
    "class_id",
    "class_name",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
    "center_x",
    "center_y",
    "width",
    "height",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run YOLO detection (not tracking) on every video frame."
    )
    parser.add_argument("input_video", type=Path)
    parser.add_argument("--model", default="yolo26s.pt")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument(
        "--classes",
        type=int,
        nargs="+",
        default=None,
        help="Optional COCO class IDs, for example: --classes 32",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    parser.add_argument(
        "--detections-dir", type=Path, default=PROJECT_ROOT / "detections"
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Ultralytics device, e.g. auto, cpu, 0, or 0,1",
    )
    return parser.parse_args()


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return "0" if torch.cuda.is_available() else "cpu"


def safe_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def video_metadata(path: Path) -> tuple[float, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(
            f"Invalid video metadata: fps={fps}, width={width}, height={height}"
        )
    return fps, width, height


def main() -> None:
    args = parse_args()
    input_video = args.input_video.resolve()
    if not input_video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf must be between 0 and 1")
    if args.imgsz <= 0:
        raise ValueError("--imgsz must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.detections_dir.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    model_reference = args.model
    project_model = PROJECT_ROOT / args.model
    if not Path(args.model).is_absolute() and project_model.is_file():
        model_reference = str(project_model)
    class_tag = "all-classes" if args.classes is None else "classes-" + "-".join(
        str(class_id) for class_id in args.classes
    )
    model_tag = safe_tag(Path(args.model).stem)
    run_tag = f"{input_video.stem}_{model_tag}_{class_tag}"
    annotated_path = args.output_dir / f"{run_tag}.mp4"
    csv_path = args.detections_dir / f"{run_tag}.csv"

    fps, width, height = video_metadata(input_video)
    model = YOLO(model_reference)
    if model.task != "detect":
        raise ValueError(
            f"Expected a detection checkpoint, but {args.model!r} has task {model.task!r}"
        )

    print(f"Input: {input_video}")
    print(f"Model: {model_reference} (task={model.task})")
    print(f"Requested device: {args.device}; resolved device: {device}")
    if device != "cpu" and torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(
        f"Settings: conf={args.conf}, imgsz={args.imgsz}, "
        f"classes={args.classes}, vid_stride=1"
    )

    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create annotated video: {annotated_path}")

    frame_count = 0
    detection_count = 0
    class_counts: Counter[str] = Counter()

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            csv_writer.writeheader()

            results = model.predict(
                source=str(input_video),
                stream=True,
                conf=args.conf,
                imgsz=args.imgsz,
                classes=args.classes,
                device=device,
                vid_stride=1,
                save=False,
                verbose=False,
            )
            for frame_index, result in enumerate(results):
                plotted = result.plot(boxes=True, labels=True, conf=True)
                if plotted.shape[1] != width or plotted.shape[0] != height:
                    plotted = cv2.resize(plotted, (width, height))
                writer.write(plotted)

                names = result.names
                boxes = result.boxes
                if boxes is not None:
                    xyxy = boxes.xyxy.detach().cpu().tolist()
                    confidences = boxes.conf.detach().cpu().tolist()
                    class_ids = boxes.cls.detach().cpu().to(torch.int64).tolist()
                    for coordinates, confidence, class_id in zip(
                        xyxy, confidences, class_ids, strict=True
                    ):
                        x1, y1, x2, y2 = (float(value) for value in coordinates)
                        class_name = str(names[int(class_id)])
                        csv_writer.writerow(
                            {
                                "video": input_video.name,
                                "frame": frame_index,
                                "time_seconds": f"{frame_index / fps:.6f}",
                                "class_id": int(class_id),
                                "class_name": class_name,
                                "confidence": f"{float(confidence):.6f}",
                                "x1": f"{x1:.3f}",
                                "y1": f"{y1:.3f}",
                                "x2": f"{x2:.3f}",
                                "y2": f"{y2:.3f}",
                                "center_x": f"{(x1 + x2) / 2.0:.3f}",
                                "center_y": f"{(y1 + y2) / 2.0:.3f}",
                                "width": f"{x2 - x1:.3f}",
                                "height": f"{y2 - y1:.3f}",
                            }
                        )
                        detection_count += 1
                        class_counts[class_name] += 1
                frame_count += 1
    finally:
        writer.release()

    print(f"Frames processed: {frame_count}")
    print(f"Detections written: {detection_count}")
    print(f"Class counts: {dict(class_counts.most_common())}")
    print(f"Annotated video: {annotated_path.resolve()}")
    print(f"Detection CSV: {csv_path.resolve()}")


if __name__ == "__main__":
    main()
