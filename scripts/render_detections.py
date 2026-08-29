#!/usr/bin/env python3
"""Render a detection CSV as bounding-box overlay on the source video.

Used by the yolo26l vs yolo26x confidence-threshold sweep: the sweep
CSVs were derived by offline filtering of a conf=0.05 inference, so
detect_video.py (which always infers) cannot be reused to visualize
them. This script simply draws the saved bounding boxes onto the
original video and writes an MP4.

Each detection is drawn with its confidence in the label.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def render(input_video: Path, detections_csv: Path, output_mp4: Path,
           min_conf: float = 0.0, max_conf: float = 1.0) -> None:
    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {input_video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_mp4), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not create output video: {output_mp4}")

    per_frame: dict[int, list[dict[str, str]]] = {}
    with detections_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = float(row["confidence"])
            if c < min_conf or c > max_conf:
                continue
            per_frame.setdefault(int(row["frame"]), []).append(row)

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for det in per_frame.get(frame_idx, []):
            x1 = int(float(det["x1"]))
            y1 = int(float(det["y1"]))
            x2 = int(float(det["x2"]))
            y2 = int(float(det["y2"]))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{det['class_name']} {float(det['confidence']):.2f}"
            cv2.putText(frame, label, (x1, max(0, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"Rendered {frame_idx} frames (of {total}) -> {output_mp4}")
    print(f"  source detections: {detections_csv}")
    print(f"  conf range drawn: [{min_conf}, {max_conf}]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_video", type=Path)
    parser.add_argument("detections_csv", type=Path)
    parser.add_argument("output_mp4", type=Path)
    parser.add_argument("--min-conf", type=float, default=0.0)
    parser.add_argument("--max-conf", type=float, default=1.0)
    args = parser.parse_args()
    render(args.input_video, args.detections_csv, args.output_mp4,
           args.min_conf, args.max_conf)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover