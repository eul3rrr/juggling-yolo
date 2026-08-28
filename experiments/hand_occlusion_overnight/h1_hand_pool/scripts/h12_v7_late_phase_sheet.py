#!/usr/bin/env python3
"""H12 v7 contact sheet for the late phase f=890-1050 to verify
the FOUNTAIN_3+ classification.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
sys.path.insert(0, str(WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "scripts"))

import cv2

VIDEO = "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/identical_balls_trick_000_018.mp4"
OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h12v7"
OUT.mkdir(parents=True, exist_ok=True)

# Sample 6 frames from the late phase
sample_frames = [890, 920, 950, 980, 1010, 1040]

cap = cv2.VideoCapture(VIDEO)
panels = []
for f in sample_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if not ret:
        continue
    # Resize to half
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (w // 2, h // 2))
    # Add frame label
    cv2.putText(frame, f"f={f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    panels.append(frame)
cap.release()

# 2x3 grid
top = cv2.hconcat(panels[:3])
bot = cv2.hconcat(panels[3:])
sheet = cv2.vconcat([top, bot])
out_path = OUT / "late_phase_f890_1040.png"
cv2.imwrite(str(out_path), sheet)
print(f"saved {out_path}")
