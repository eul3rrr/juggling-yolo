#!/usr/bin/env python3
"""Render a 6-frame contact sheet for chain 14 identical."""

import csv
import sys
import cv2
import numpy as np
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
VIDEO = "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/identical_balls_trick_000_018.mp4"
CHAIN_CSV = WORKTREE / "experiments/hand_occlusion_overnight/h1_hand_pool/data/h7v3plus3_chains_identical_balls_trick_000_018.csv"
DETECT_CSV = WORKTREE / "detections" / "identical_balls_trick_000_018_norfair_dt50_hc5.csv"
OUT = WORKTREE / "experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h55/chain14_identical_h55v2.png"

# Find chain 14
chain = None
with CHAIN_CSV.open() as fh:
    for r in csv.DictReader(fh):
        if r["chain_id"] == "14":
            tids = [int(t) for t in r["tids"].split(",") if t.strip()]
            chain = {"tids": tids,
                     "first_frame": int(r["first_frame"]),
                     "last_frame": int(r["last_frame"])}
            break
if chain is None:
    print("chain 14 not found", file=sys.stderr)
    sys.exit(1)

# Load detections for chain 14's tracklets
det_per_tid = {}
with DETECT_CSV.open() as fh:
    for r in csv.DictReader(fh):
        tid = int(r["track_id"])
        if tid in chain["tids"]:
            det_per_tid.setdefault(tid, []).append(
                (int(r["frame"]), float(r["center_x"]), float(r["center_y"])))

# Pick 6 representative frames: f-2 of first tracklet, middle of each tracklet
# Spread across chain
f_start = chain["first_frame"]
f_end = chain["last_frame"]
sample_frames = [f_start, f_start + (f_end - f_start) // 5,
                 f_start + 2 * (f_end - f_start) // 5,
                 f_start + 3 * (f_end - f_start) // 5,
                 f_start + 4 * (f_end - f_start) // 5, f_end]

# Open video
cap = cv2.VideoCapture(str(VIDEO))
frames = []
for f in sample_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, img = cap.read()
    if not ret:
        print(f"failed to read frame {f}", file=sys.stderr)
        continue
    # Annotate with circles
    for tid, dets in det_per_tid.items():
        # Find closest detection
        closest = min(dets, key=lambda d: abs(d[0] - f))
        if abs(closest[0] - f) <= 2:
            x, y = int(closest[1]), int(closest[2])
            color = (0, 165, 255) if tid in chain["tids"][:1] else (255, 100, 100)
            cv2.circle(img, (x, y), 18, color, 3)
            cv2.putText(img, f"t{tid}", (x+20, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(img, f"f={f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    frames.append(img)
cap.release()

# Build 2x3 grid
if not frames:
    print("no frames", file=sys.stderr)
    sys.exit(1)
h, w = frames[0].shape[:2]
grid = np.zeros((2 * h, 3 * w, 3), dtype=np.uint8)
for i, img in enumerate(frames[:6]):
    r, c = divmod(i, 3)
    grid[r*h:(r+1)*h, c*w:(c+1)*w] = img
# Title
header = np.zeros((60, 3*w, 3), dtype=np.uint8)
cv2.putText(header, f"H55 v2 chain 14 (g_cv=1.089, multi-tid UNCERTAIN v10, demoted to LOW v11)",
            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
out_full = np.vstack([header, grid])
OUT.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(OUT), out_full)
print(f"Wrote {OUT}")
