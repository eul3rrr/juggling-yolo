#!/usr/bin/env python3
"""H12 v4/v5 late-phase contact sheet for visual QA.

The H12 v2 contact sheet already showed the late phase (f=890-1050) on
identical is dominated by FOUNTAIN_3+, which is visually a cascade.
This script generates a contact sheet specifically for the late phase
showing the v2, v4, and v5 classifications side-by-side for inspection.

Also extracts 6 actual frames from the late phase for vision_analyze.
"""
from __future__ import annotations

import csv
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v4"
H1_CS.mkdir(parents=True, exist_ok=True)

STEM = "identical_balls_trick_000_018"
LATE_FRAMES = [890, 920, 950, 980, 1010, 1040]

# BGR colors for OpenCV
PATTERN_COLORS_BGR = {
    "FOUNTAIN_3+": (0, 170, 255),
    "FOUNTAIN_3+_DETECTOR": (0, 170, 255),
    "FOUNTAIN_3+_DETECTOR_SMOOTHED": (0, 170, 255),
    "CASCADE_3+_DETECTOR": (68, 255, 68),
    "CASCADE_3+_DETECTOR_SMOOTHED": (68, 255, 68),
    "CASCADE_3+": (68, 255, 68),
    "MIXED_3+": (170, 68, 255),
    "MIXED_3+_UNCONFIRMED": (170, 68, 255),
    "TWO_BALL": (255, 136, 68),
    "SINGLE_BALL": (255, 220, 136),
    "NO_BALL": (128, 128, 128),
}


def load_classifications(stem: str) -> dict:
    """{frame: {v2: pattern, v4: pattern, v5: pattern}}"""
    out = {}
    for ver in ("v2", "v4", "v5"):
        path = H1_DATA / f"pattern_inference_{ver}_{stem}.csv"
        with path.open() as fh:
            for r in csv.DictReader(fh):
                f = int(r["frame"])
                if f not in out:
                    out[f] = {}
                out[f][ver] = r["pattern"]
    return out


def main():
    import cv2
    import numpy as np

    classifications = load_classifications(STEM)

    # Build the 6-frame contact sheet with per-frame classifications
    # Videos live in the main juggling-yolo workspace, not this worktree
    video_path = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos") / f"{STEM}.mp4"
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video: {video_path} ({fps} fps)")

    img_h, img_w = 540, 960
    pad = 10
    label_h = 50
    n_rows = len(LATE_FRAMES)
    n_cols = 2
    H = (img_h + label_h + pad) * n_rows + pad
    W = img_w * n_cols + pad * 3
    sheet = np.full((H, W, 3), 255, dtype=np.uint8)

    for row, f in enumerate(LATE_FRAMES):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frame = cap.read()
        if not ok:
            print(f"  failed to read frame {f}")
            continue
        # Resize
        frame = cv2.resize(frame, (img_w, img_h))
        # Annotate classifications on top of frame
        cls = classifications.get(f, {})
        v2_pat = cls.get("v2", "?")
        v4_pat = cls.get("v4", "?")
        v5_pat = cls.get("v5", "?")
        v2_color = PATTERN_COLORS_BGR.get(v2_pat, (200, 200, 200))
        v4_color = PATTERN_COLORS_BGR.get(v4_pat, (200, 200, 200))
        v5_color = PATTERN_COLORS_BGR.get(v5_pat, (200, 200, 200))
        cv2.rectangle(frame, (0, 0), (img_w, 30), (255, 255, 255), -1)
        cv2.putText(frame, f"v2: {v2_pat}", (10, 22),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, v2_color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"v4: {v4_pat}", (260, 22),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, v4_color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"v5: {v5_pat}", (550, 22),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, v5_color, 1, cv2.LINE_AA)

        y0 = (img_h + label_h + pad) * row + pad
        sheet[y0:y0 + img_h, pad:pad + img_w] = frame
        # Frame label below
        cv2.putText(sheet, f"f={f}", (pad + 10, y0 + img_h + 30),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)

    cap.release()

    out = H1_CS / "late_phase_visual_qa.png"
    cv2.imwrite(str(out), sheet)
    print(f"  wrote: {out.name}")


if __name__ == "__main__":
    main()
