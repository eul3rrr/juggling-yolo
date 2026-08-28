#!/usr/bin/env python3
"""H90 contact sheet - visual QA on the 2 H90-caught YouTube phases + 1 H90-kept phase.

H90 NEW signal catches:
- f=2-71 (STATIC_DEMO): drop_pct_ge3 = 0.39 (>0.38) — H90 rule
- f=482-594 (STATIC_HOLD): c40_max_aloft = 4 (>=4) — H90 rule

H90-kept (real juggling):
- f=420-481 (JUGGLING): c40_max_aloft=3, drop=0.30, kept by H90

Render 4-frame contact sheets for visual confirmation.
Output: contact_sheets_h90/*.png
"""
from __future__ import annotations
import csv
from pathlib import Path

import cv2

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
CONTACT_DIR = H1_DIR / "contact_sheets_h90"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATHS = {
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": PROJECT
    / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
    "identical_balls_trick_000_018": PROJECT / "videos" / "identical_balls_trick_000_018.mp4",
}

# 2 H90-caught + 1 H90-kept (real juggling) for control
PHASES_TO_INSPECT = [
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71, "H90_TN_static_demo"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594, "H90_TN_static_hold"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 420, 481, "H90_TP_juggling_control"),
]


def render_contact_sheet(video_path, start, end, label, stem):
    """Render 4-frame contact sheet for a phase."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  cannot open {video_path}")
        return
    n_total = end - start + 1
    if n_total < 4:
        frame_indices = [start] * 4
    else:
        frame_indices = [start + int(n_total * i / 4) for i in range(4)]
    frames = []
    for f in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            print(f"  cannot read frame {f}")
            cap.release()
            return
        # Label with frame index
        cv2.putText(frame, f"f={f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        frames.append(frame)
    cap.release()
    # Stack vertically
    h, w = frames[0].shape[:2]
    sheet = np.zeros((h * 4, w, 3), dtype=np.uint8)
    for i, fr in enumerate(frames):
        sheet[i*h:(i+1)*h, :] = fr
    # Save
    out = CONTACT_DIR / f"{stem}_f{start}-{end}_{label}.png"
    cv2.imwrite(str(out), sheet)
    print(f"  wrote {out}")


import numpy as np
for stem, start, end, label in PHASES_TO_INSPECT:
    print(f"\nRendering {stem} f={start}-{end} ({label})")
    render_contact_sheet(VIDEO_PATHS[stem], start, end, label, stem)
