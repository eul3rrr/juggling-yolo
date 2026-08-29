#!/usr/bin/env python3
"""Build side-by-side detection comparison videos and Norfair tracklet videos.

The first mode (``compare-detections``) takes two annotated detection overlay
MP4s from the same input video (e.g. yolo26s vs yolo26l) and produces a
side-by-side MP4 with synchronized source frames and a title bar.

The second mode (``compare-segmentation``) takes a detection overlay and a
segmentation overlay for the same video and produces a side-by-side MP4
showing how the bbox-only detector compares against the bbox+mask
segmentation model.

The third mode (``compare-tracks``) takes two Norfair tracklet overlay MP4s
and produces a side-by-side MP4 for visual comparison of the tracker output.
Synchronized source frames are mandatory here because trajectory differences
must be interpreted against the same source frame.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import cv2
import numpy as np

TITLE_BAR_HEIGHT = 34


def _read_video(path: Path) -> tuple[cv2.VideoCapture, float, int, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError(f"Invalid metadata for {path}")
    return cap, fps, width, height


def _draw_title(frame: np.ndarray, title: str) -> None:
    cv2.rectangle(frame, (0, 0), (frame.shape[1], TITLE_BAR_HEIGHT), (20, 20, 20), -1)
    cv2.putText(frame, title, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)


def _concat(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return cv2.hconcat((left, right))


def _compare_two(
    left_path: Path,
    right_path: Path,
    left_title: str,
    right_title: str,
    output_path: Path,
) -> None:
    left_cap, left_fps, left_w, left_h = _read_video(left_path)
    right_cap, right_fps, right_w, right_h = _read_video(right_path)
    out_fps = min(left_fps, right_fps)
    out_w = left_w + right_w
    out_h = max(left_h, right_h)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        out_fps,
        (out_w, out_h),
    )
    if not writer.isOpened():
        left_cap.release()
        right_cap.release()
        raise RuntimeError(f"Could not create {output_path}")
    count = 0
    try:
        while True:
            ok_l, frame_l = left_cap.read()
            ok_r, frame_r = right_cap.read()
            if not ok_l or not ok_r:
                break
            if frame_l.shape[0] != left_h or frame_l.shape[1] != left_w:
                frame_l = cv2.resize(frame_l, (left_w, left_h))
            if frame_r.shape[0] != right_h or frame_r.shape[1] != right_w:
                frame_r = cv2.resize(frame_r, (right_w, right_h))
            if frame_l.shape[0] != out_h:
                frame_l = cv2.resize(frame_l, (out_w // 2, out_h))
            if frame_r.shape[0] != out_h:
                frame_r = cv2.resize(frame_r, (out_w // 2, out_h))
            _draw_title(frame_l, left_title)
            _draw_title(frame_r, right_title)
            writer.write(_concat(frame_l, frame_r))
            count += 1
    finally:
        left_cap.release()
        right_cap.release()
        writer.release()
    print(f"Frames: {count}; output: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build side-by-side comparison MP4s for detection / seg / tracks."
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    def _add_pair_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("left", type=Path)
        p.add_argument("right", type=Path)
        p.add_argument("--left-title", required=True)
        p.add_argument("--right-title", required=True)
        p.add_argument("--output", type=Path, required=True)

    det_p = sub.add_parser("compare-detections", help="Two detection overlays side by side.")
    _add_pair_args(det_p)

    seg_p = sub.add_parser(
        "compare-segmentation", help="Detection overlay vs segmentation overlay side by side."
    )
    _add_pair_args(seg_p)

    trk_p = sub.add_parser("compare-tracks", help="Two Norfair tracklet overlays side by side.")
    _add_pair_args(trk_p)

    args = parser.parse_args()
    if args.mode in ("compare-detections", "compare-segmentation", "compare-tracks"):
        _compare_two(args.left, args.right, args.left_title, args.right_title, args.output)


if __name__ == "__main__":
    main()
