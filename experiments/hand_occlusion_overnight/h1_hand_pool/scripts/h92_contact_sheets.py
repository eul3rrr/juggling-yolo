#!/usr/bin/env python3
"""
H92 contact sheets — visual QA on the 2 H92-recovered identical phases.

H92 v1 recovers:
- f=263-312 (JUGGLING, identical 3-ball)
- f=977-1011 (FOUNTAIN, identical 3-ball)

Render 4-frame contact sheets for visual confirmation that these
are indeed real juggling/FOUNTAIN phases, not misclassifications.

Also render contact sheets for the 2 STATIC_HOLD phases (f=733-766,
f=1029-1049) for comparison: they should be static, not juggling.
"""
from __future__ import annotations
import csv
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
CONTACT_DIR = H1_DIR / "contact_sheets_h92"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATHS = {
    "identical_balls_trick_000_018": PROJECT
    / "videos" / "identical_balls_trick_000_018.mp4",
}

# 2 H92-recovered + 2 H92-correctly-still-TN STATIC_HOLDs
PHASES_TO_INSPECT = [
    ("identical_balls_trick_000_018", 263, 312, "H92_TP_juggling_recovered"),
    ("identical_balls_trick_000_018", 977, 1011, "H92_TP_fountain_recovered"),
    ("identical_balls_trick_000_018", 733, 766, "H92_TN_static_hold_control"),
    ("identical_balls_trick_000_018", 1029, 1049, "H92_TN_static_hold_control2"),
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


for stem, start, end, label in PHASES_TO_INSPECT:
    print(f"\nRendering {stem} f={start}-{end} ({label})")
    render_contact_sheet(VIDEO_PATHS[stem], start, end, label, stem)
