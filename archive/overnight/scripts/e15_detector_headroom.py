#!/usr/bin/env python3
"""E15: detector headroom probe on dropout frames.

Frames where observed balls were missed (e.g. obs=0 at f950) are re-run through
YOLO at relaxed settings (lower conf, higher imgsz, lower IoU) to measure how
many missed balls become detectable. Also quantifies the conf distribution of
missed vs caught balls. Uses the existing venv ultralytics install.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
OUT_DIR = BASE / "data"
SHIPPED = PROJECT / "detections"
VIDEO = PROJECT / "videos" / "identical_balls_trick_000_018.mp4"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

CONF_GRID = (0.05, 0.10, 0.15)
IMGSZ_GRID = (960, 1280)
SAMPLE_FRAMES_STEP = 25


def main() -> None:
    from ultralytics import YOLO

    model = YOLO("yolo26s.pt")
    cap = cv2.VideoCapture(str(VIDEO))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sample_frames = list(range(0, total, SAMPLE_FRAMES_STEP))

    # ground truth proxy: observed points per frame from the dt50_hc5 run
    tracks = observed_masked_legacy("identical_balls_trick_000_018")
    gt_by_frame = defaultdict(list)
    for pts in tracks.values():
        for f, x, y in pts:
            gt_by_frame[f].append((x, y))

    results = defaultdict(lambda: {"frames": 0, "gt_balls": 0, "matched": 0, "fps_dets": 0})
    detail = []
    for frame in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, img = cap.read()
        if not ok:
            continue
        gt = gt_by_frame.get(frame, [])
        for conf in CONF_GRID:
            for imgsz in IMGSZ_GRID:
                res = model.predict(img, conf=conf, iou=0.3, imgsz=imgsz, verbose=False)[0]
                boxes = res.boxes
                dets = []
                for b in boxes:
                    cls = int(b.cls[0])
                    if cls != 32:
                        continue
                    x1, y1, x2, y2 = b.xyxy[0].tolist()
                    dets.append(((x1 + x2) / 2, (y1 + y2) / 2, float(b.conf[0])))
                key = f"conf{conf}_sz{imgsz}"
                r = results[key]
                r["frames"] += 1
                r["gt_balls"] += len(gt)
                r["fps_dets"] += len(dets)
                for gx, gy in gt:
                    if any(math_hypot(dx - gx, dy - gy) <= 40 for dx, dy, _ in dets):
                        r["matched"] += 1
                if conf == CONF_GRID[0] and imgsz == IMGSZ_GRID[-1]:
                    detail.append({
                        "frame": frame,
                        "gt": len(gt),
                        "n_dets": len(dets),
                        "confs": [round(d[2], 3) for d in dets],
                    })
    cap.release()
    summary = {}
    for key, r in results.items():
        recall = r["matched"] / r["gt_balls"] if r["gt_balls"] else None
        summary[key] = {
            "recall_vs_norfair_obs": round(recall, 4) if recall is not None else None,
            "mean_dets_per_frame": round(r["fps_dets"] / r["frames"], 2),
        }
        print(f"{key}: {summary[key]}")
    (OUT_DIR / "e15_detector_headroom.json").write_text(
        json.dumps({"summary": summary, "sample": detail[:20]}, indent=2)
    )
    print("wrote data/e15_detector_headroom.json")


def math_hypot(a: float, b: float) -> float:
    return float(np.hypot(a, b))


if __name__ == "__main__":
    main()
