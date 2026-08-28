#!/usr/bin/env python3
"""H72 - Contact sheets for the 6 un-QA'd H70 substantial phases.

H70 reports 20 substantial phases (>= 20 frames) across both videos.
H65 visual QA'd 7 FOUNTAIN_3+ phases.
H71 multi-rater QA'd 7 MIXED_3+ / UNCONFIRMED phases (5 KEEP + 2 REJECT).
6 substantial phases have NO visual QA yet:

- CASCADE_3+ f=685-716 identical (conc=0.498, very high -- expect CASCADE)
- MIXED_3+ f=267-298 YouTube (conc=0.175, above 0.15 KEEP)
- MIXED_3+ f=375-410 YouTube (conc=0.216, above 0.15 KEEP)
- MIXED_3+ f=420-481 YouTube (conc=0.165, above 0.15 KEEP)
- MIXED_3+ f=595-643 YouTube (conc=0.170, above 0.15 KEEP)
- MIXED_3+ f=862-899 YouTube (conc=0.249, above 0.15 KEEP)

Hypothesis: All 6 should be confirmed as real juggling by multi-rater
visual QA. The H70 KEEP threshold (spec_conc >= 0.15) is already
validated on the 5 H71 KEEP MIXED phases. These 6 additional phases
will increase the validation sample to 11 KEEP phases.
"""
from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
CONTACT_DIR = H1_DIR / "contact_sheets_h72"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATHS = {
    "identical_balls_trick_000_018": PROJECT / "videos" / "identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        PROJECT / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# 6 un-QA'd H70 substantial phases
PHASES_TO_INSPECT = [
    # CASCADE_3+ (1): should be confirmed as CASCADE
    ("identical_balls_trick_000_018", 685, 716, "CASCADE_3+_keep_conc_0.498"),
    # YouTube MIXED_3+ KEEP (5): all above 0.15 spec_conc
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 267, 298, "MIXED_3+_keep_conc_0.175"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 375, 410, "MIXED_3+_keep_conc_0.216"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 420, 481, "MIXED_3+_keep_conc_0.165"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 595, 643, "MIXED_3+_keep_conc_0.170"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 862, 899, "MIXED_3+_keep_conc_0.249"),
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


for stem, start, end, label in PHASES_TO_INSPECT:
    print(f"\n=== {stem} {label} f={start}-{end} ===")
    render_contact_sheet(VIDEO_PATHS[stem], start, end, label, stem)
