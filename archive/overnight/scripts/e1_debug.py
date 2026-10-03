#!/usr/bin/env python3
"""Debug why LS/ballistic fits predict so much worse than 2-point CV."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DETECT_DIR = PROJECT_ROOT / "detections"
TIME_SCALE = 30.0

STEM = "identical_balls_trick_000_018"

tracks: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
with (DETECT_DIR / f"{STEM}_norfair_dt50_hc5.csv").open(newline="") as fh:
    for row in csv.DictReader(fh):
        if row.get("observed") != "1":
            continue
        tracks[int(row["track_id"])].append(
            (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
        )
for tid in tracks:
    tracks[tid].sort()

cands = []
with (DETECT_DIR / f"{STEM}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
    cands.extend(csv.DictReader(fh))

labels = {}
with (DETECT_DIR / "stitch_review_labels.csv").open(newline="") as fh:
    for row in csv.DictReader(fh):
        if STEM in row["video"]:
            labels[(int(row["source_tracklet"]), int(row["candidate_tracklet"]))] = row["label"]

# Pick a few labeled pairs spanning low/high cv2 error.
picked = []
for c in cands:
    key = (int(c["source_tracklet"]), int(c["candidate_tracklet"]))
    if key in labels:
        picked.append((float(c["prediction_error"]), key, c))
picked.sort()
show = picked[:2] + picked[len(picked)//2:len(picked)//2+2] + picked[-2:]

for err, key, c in show:
    src_id, cand_id = key
    pts = tracks[src_id]
    qf = int(c["candidate_start_frame"])
    qx, qy = float(c["candidate_start_x"]), float(c["candidate_start_y"])
    print(f"\n=== src={src_id} cand={cand_id} label={labels[key]} cv2_err={err:.1f} "
          f"gap={c['gap_frames']} src_end_f={pts[-1][0]} qframe={qf} target=({qx:.0f},{qy:.0f})")
    tail = pts[-12:]
    print("  tail pts:", " ".join(f"({f},{x:.0f},{y:.0f})" for f, x, y in tail))
    # manual fits
    frames = np.array([p[0] for p in tail], dtype=float)
    xs = np.array([p[1] for p in tail], dtype=float)
    ys = np.array([p[2] for p in tail], dtype=float)
    t_ref = frames.mean()
    tau = (frames - t_ref) / TIME_SCALE
    tq = (qf - t_ref) / TIME_SCALE
    cx = np.polyfit(tau, xs, 1)
    cy_lin = np.polyfit(tau, ys, 1)
    cy_bal = np.polyfit(tau, ys, 2)
    px_lin, py_lin = np.polyval(cx, tq), np.polyval(cy_lin, tq)
    px_bal, py_bal = np.polyval(cx, tq), np.polyval(cy_bal, tq)
    # 2pt cv reproduction
    (f1, x1, y1), (f2, x2, y2) = pts[-2], pts[-1]
    h = qf - f2
    cv_pred = (x2 + (x2-x1)/(f2-f1)*h, y2 + (y2-y1)/(f2-f1)*h)
    print(f"  LS-linear pred ({px_lin:.0f},{py_lin:.0f}) d={math.hypot(px_lin-qx, py_lin-qy):.0f}")
    print(f"  ballistic  pred ({px_bal:.0f},{py_bal:.0f}) d={math.hypot(px_bal-qx, py_bal-qy):.0f}")
    print(f"  2pt-cv     pred ({cv_pred[0]:.0f},{cv_pred[1]:.0f}) d={math.hypot(cv_pred[0]-qx, cv_pred[1]-qy):.0f}")
    print(f"  y-coef bal (a2,a1,a0)={tuple(np.round(cy_bal,1))} -> implied accel px/frame^2 = {2*cy_bal[0]/TIME_SCALE**2:.3f}")
