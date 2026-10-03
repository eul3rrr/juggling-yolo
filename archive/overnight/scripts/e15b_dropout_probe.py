#!/usr/bin/env python3
"""E15b: detector headroom on DROPOUT frames (obs<3).

Finds frames where the dt50_hc5 run had fewer than 3 observed balls, saves the
frame images, and runs YOLO at a relaxed conf grid on exactly those frames,
reporting class-32 detection counts. Vision (human/agent) can then judge the
saved frames for true ball counts.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
OUT_DIR = BASE / "data"
FRAMES_DIR = BASE / "reports" / "frames" / "dropouts"
VIDEO = PROJECT / "videos" / "identical_balls_trick_000_018.mp4"
STEM = "identical_balls_trick_000_018"


def main() -> None:
    from ultralytics import YOLO

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    tracks = observed_masked_legacy(STEM)
    obs_count: dict[int, int] = defaultdict(int)
    for pts in tracks.values():
        for f, _x, _y in pts:
            obs_count[f] += 1
    dropouts = [f for f in range(1079) if obs_count.get(f, 0) < 3]
    print(f"dropout frames (obs<3): {len(dropouts)}")
    # sample up to 12 spread across the video
    sample = dropouts[:: max(1, len(dropouts) // 12)][:12]

    model = YOLO("yolo26s.pt")
    cap = cv2.VideoCapture(str(VIDEO))
    rows = []
    for frame in sample:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, img = cap.read()
        if not ok:
            continue
        img_path = FRAMES_DIR / f"dropout_f{frame}.png"
        cv2.imwrite(str(img_path), img)
        det_counts = {}
        for conf in (0.05, 0.15):
            res = model.predict(img, conf=conf, iou=0.3, imgsz=960, verbose=False)[0]
            n32 = sum(1 for c in res.boxes.cls if int(c) == 32)
            det_counts[f"conf{conf}"] = int(n32)
        rows.append({
            "frame": frame,
            "observed_in_run": obs_count.get(frame, 0),
            "yolo_c32": det_counts,
            "image": str(img_path.relative_to(BASE)),
        })
        print(rows[-1])
    cap.release()
    (OUT_DIR / "e15b_dropouts.json").write_text(json.dumps(rows, indent=2))
    print("wrote data/e15b_dropouts.json")


if __name__ == "__main__":
    main()
