#!/usr/bin/env python3
"""H70 v2 - contact sheets for KEEP MIXED_3+ phases to validate H69 specificity.

If H69 correctly catches non-juggling MIXED_3+ phases, then KEEP
MIXED_3+ phases (spec_conc >= 0.15) should be REAL juggling.
"""
from __future__ import annotations

from pathlib import Path
import cv2

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
CONTACT_DIR = H1_DIR / "contact_sheets_h70v2"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATHS = {
    "identical_balls_trick_000_018": PROJECT / "videos" / "identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        PROJECT / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# KEEP MIXED_3+ phases with HIGH spec_conc (should be real juggling)
PHASES_TO_INSPECT = [
    # identical MIXED_3+ with high conc
    ("identical_balls_trick_000_018", 263, 312, "MIXED_3+_keep_conc_0.182"),
    ("identical_balls_trick_000_018", 411, 450, "MIXED_3+_keep_conc_0.196"),
    ("identical_balls_trick_000_018", 549, 578, "MIXED_3+_keep_conc_0.332"),
    # youtube MIXED_3+ with high conc
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 308, 338, "MIXED_3+_keep_conc_0.235"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 769, 799, "MIXED_3+_keep_conc_0.214"),
]


def render_contact_sheet(video_path, start, end, label, stem):
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
            cap.release()
            return
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    h, w = frames[0].shape[:2]
    sheet = np.zeros((h, w * 4, 3), dtype=np.uint8)
    for i, fr in enumerate(frames):
        sheet[:, i * w:(i + 1) * w] = fr
    for i, f in enumerate(frame_indices):
        cv2.putText(sheet, f"f={f}", (i * w + 10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.putText(sheet, f"{label} f={start}-{end}", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    out = CONTACT_DIR / f"phase_{stem}_f{start}-{end}_{label}.png"
    cv2.imwrite(str(out), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(f"  wrote: {out.name}")


import numpy as np
for stem, start, end, label in PHASES_TO_INSPECT:
    print(f"\n=== {stem} {label} f={start}-{end} ===")
    render_contact_sheet(VIDEO_PATHS[stem], start, end, label, stem)
