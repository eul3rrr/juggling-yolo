#!/usr/bin/env python3
"""H70 contact sheet - visual QA on the 2 H70-rejected MIXED_3+ phases.

H69 spec_conc < 0.15 catches 2 MIXED_3+ phases on YouTube that may
be misclassified:
- 114-255: MIXED_3+, conf 0.705, spec_conc 0.124
- 2-71: MIXED_3+_UNCONFIRMED, conf 0.333, spec_conc 0.075

Render 4-frame contact sheets and inspect them visually.

Output: contact_sheets_h70/*.png
"""
from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
CONTACT_DIR = H1_DIR / "contact_sheets_h70"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATHS = {
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": PROJECT
    / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# The 2 H70-rejected MIXED phases
PHASES_TO_INSPECT = [
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71, "MIXED_3+_UNCONFIRMED"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 114, 255, "MIXED_3+"),
]


def render_contact_sheet(video_path, start, end, pattern_name, stem):
    """Render 4-frame contact sheet for a phase."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  cannot open {video_path}")
        return
    n_total = end - start + 1
    # 4 frames evenly spaced
    if n_total < 4:
        frame_indices = [start] * 4
    else:
        frame_indices = [
            start + int(n_total * i / 4) for i in range(4)
        ]
    frames = []
    for f in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            print(f"  cannot read frame {f}")
            cap.release()
            return
        # Convert BGR to RGB for display
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()

    # Stack horizontally
    h, w = frames[0].shape[:2]
    sheet = np.zeros((h, w * 4, 3), dtype=np.uint8)
    for i, fr in enumerate(frames):
        sheet[:, i * w:(i + 1) * w] = fr
    # Add frame labels
    for i, f in enumerate(frame_indices):
        cv2.putText(sheet, f"f={f}", (i * w + 10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    # Add pattern label
    cv2.putText(sheet, f"{pattern_name} f={start}-{end}", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    out = CONTACT_DIR / f"phase_{stem}_f{start}-{end}_{pattern_name}.png"
    cv2.imwrite(str(out), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(f"  wrote: {out.name}")


def main():
    for stem, start, end, pat in PHASES_TO_INSPECT:
        print(f"\n=== {stem} {pat} f={start}-{end} ===")
        render_contact_sheet(VIDEO_PATHS[stem], start, end, pat, stem)


if __name__ == "__main__":
    main()
