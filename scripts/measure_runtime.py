#!/usr/bin/env python3
"""Measure model-only inference time for one detection model on a video.

Reuses the same Ultralytics API call as ``detect_video.py`` but discards the
overlay and CSV writing to get a pure-inference timing number.  The same
conf, imgsz, classes, vid_stride, and device are honored so the timing
matches what a real detection run does, frame for frame.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import torch
from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_video", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--classes", type=int, nargs="+", default=[32])
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    device = args.device if args.device != "auto" else (
        "0" if torch.cuda.is_available() else "cpu"
    )
    model_path = args.model
    project_path = PROJECT_ROOT / args.model
    if not Path(args.model).is_absolute() and project_path.is_file():
        model_path = str(project_path)
    cap = cv2.VideoCapture(str(args.input_video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    print(f"Video: {args.input_video}  fps={fps:.3f}  frames={total}")
    print(f"Model: {model_path}  device={device}  conf={args.conf}  imgsz={args.imgsz}  classes={args.classes}")
    model = YOLO(model_path)
    if device != "cpu" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.monotonic()
    n_processed = 0
    for result in model.predict(
        source=str(args.input_video),
        stream=True,
        conf=args.conf,
        imgsz=args.imgsz,
        classes=args.classes,
        device=device,
        vid_stride=1,
        save=False,
        verbose=False,
    ):
        n_processed += 1
    if device != "cpu" and torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.monotonic() - start
    fps_eff = n_processed / elapsed if elapsed > 0 else 0.0
    print(f"Frames: {n_processed}  time: {elapsed:.2f}s  effective_fps: {fps_eff:.2f}")
    if device != "cpu" and torch.cuda.is_available():
        peak_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
        print(f"Peak GPU memory: {peak_mb:.1f} MB")


if __name__ == "__main__":
    main()
