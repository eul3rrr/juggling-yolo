#!/usr/bin/env python3
"""H12 v2 contact sheet - visualize pattern phases on a per-frame timeline.

Generates a contact sheet showing the pattern timeline with key frames
extracted from each substantial phase. Uses OpenCV (no matplotlib needed).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v2"
H1_CS.mkdir(parents=True, exist_ok=True)

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# BGR colors for OpenCV
PATTERN_COLORS_BGR = {
    "NO_BALL": (128, 128, 128),
    "SINGLE_BALL": (255, 220, 136),
    "TWO_BALL": (255, 136, 68),
    "TWO_BALL_HELD": (136, 68, 34),
    "TWO_BALL_ONE_HAND": (255, 68, 170),
    "CASCADE_3+": (68, 255, 68),
    "FOUNTAIN_3+": (0, 170, 255),
    "MIXED_3+": (170, 68, 255),
    "MIXED_3+_UNCONFIRMED": (170, 68, 255),
    "CASCADE_3+_UNCONFIRMED": (136, 255, 136),
    "UNKNOWN": (68, 68, 68),
}


def render_timeline(stem: str, results: list[dict], phases: list[dict],
                     out_path: Path):
    """Render a 3-row timeline using OpenCV:
    Row 1: per-frame pattern label as colored bands
    Row 2: confidence line plot
    Row 3: n_total line plot
    """
    import cv2
    import numpy as np

    if not results:
        return
    frames = np.array([r["frame"] for r in results])
    patterns = [r["pattern"] for r in results]
    confs = np.array([r["confidence"] for r in results])
    n_total = np.array([r["n_total"] for r in results])

    n_frames = len(frames)
    fmin, fmax = int(frames[0]), int(frames[-1])
    fspan = max(1, fmax - fmin)

    # Image dimensions
    W = 1800
    H_row1 = 80
    H_row2 = 80
    H_row3 = 80
    H_legend = 60
    H_total = H_row1 + H_row2 + H_row3 + H_legend + 20

    img = np.full((H_total, W, 3), 255, dtype=np.uint8)

    # Row 1: pattern bands
    row1_y0 = 30
    row1_y1 = row1_y0 + H_row1
    for i, r in enumerate(results):
        c = PATTERN_COLORS_BGR.get(r["pattern"], (255, 255, 255))
        x0 = int((r["frame"] - fmin) / fspan * (W - 20)) + 10
        x1 = int((r["frame"] + 1 - fmin) / fspan * (W - 20)) + 10
        x1 = max(x1, x0 + 1)
        cv2.rectangle(img, (x0, row1_y0), (x1, row1_y1), c, -1)
    cv2.putText(img, "pattern", (5, row1_y0 + 50), cv2.FONT_HERSHEY_SIMPLEX,
                 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    # Row 2: confidence line
    row2_y0 = row1_y1 + 10
    row2_y1 = row2_y0 + H_row2
    for i in range(1, n_frames):
        x0 = int((frames[i - 1] - fmin) / fspan * (W - 20)) + 10
        x1 = int((frames[i] - fmin) / fspan * (W - 20)) + 10
        y0 = row2_y1 - int(confs[i - 1] * (H_row2 - 10))
        y1 = row2_y1 - int(confs[i] * (H_row2 - 10))
        cv2.line(img, (x0, y0), (x1, y1), (255, 68, 68), 1, cv2.LINE_AA)
    cv2.putText(img, "confidence", (5, row2_y0 + 50), cv2.FONT_HERSHEY_SIMPLEX,
                 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(img, (10, row2_y1), (W - 10, row2_y1), (0, 0, 0), 1)

    # Row 3: n_total line
    row3_y0 = row2_y1 + 10
    row3_y1 = row3_y0 + H_row3
    nmax = max(n_total.max(), 1)
    for i in range(1, n_frames):
        x0 = int((frames[i - 1] - fmin) / fspan * (W - 20)) + 10
        x1 = int((frames[i] - fmin) / fspan * (W - 20)) + 10
        y0 = row3_y1 - int(n_total[i - 1] / nmax * (H_row3 - 10))
        y1 = row3_y1 - int(n_total[i] / nmax * (H_row3 - 10))
        cv2.line(img, (x0, y0), (x1, y1), (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, f"n_total (max={nmax})", (5, row3_y0 + 50),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(img, (10, row3_y1), (W - 10, row3_y1), (0, 0, 0), 1)

    # Legend
    legend_y0 = row3_y1 + 10
    x_cur = 10
    for pattern in sorted(set(patterns)):
        c = PATTERN_COLORS_BGR.get(pattern, (255, 255, 255))
        cv2.rectangle(img, (x_cur, legend_y0), (x_cur + 18, legend_y0 + 18),
                       c, -1)
        cv2.putText(img, pattern, (x_cur + 22, legend_y0 + 14),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        # approximate text width
        text_w = len(pattern) * 9
        x_cur += 30 + text_w

    # Title at top
    cv2.putText(img, f"{stem}: H12 v2 pattern timeline", (10, 20),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    # Phase annotations: only substantial phases
    for ph in phases:
        if int(ph["n_frames"]) >= 30:
            x = int((int(ph["start_frame"]) + int(ph["end_frame"])) // 2 - fmin
                     ) / fspan * (W - 20) + 10
            label = f"{ph['pattern']}\n{ph['n_frames']}f\n{float(ph['avg_confidence']):.2f}"
            # 3 lines of text
            for k, line in enumerate(label.split("\n")):
                cv2.putText(img, line, (int(x), row1_y0 - 8 - k * 12),
                             cv2.FONT_HERSHEY_SIMPLEX, 0.4, (50, 50, 50),
                             1, cv2.LINE_AA)
            cv2.line(img, (int(x), row1_y0), (int(x), row1_y1),
                      (100, 100, 100), 1)

    cv2.imwrite(str(out_path), img)
    print(f"  wrote: {out_path.name}")


def main():
    for stem in STEMS:
        results = []
        with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                r["frame"] = int(r["frame"])
                r["n_total"] = int(r["n_total"])
                r["confidence"] = float(r["confidence"])
                results.append(r)

        phases = []
        with (H1_DATA / f"pattern_phases_v2_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                phases.append(r)

        out_path = H1_CS / f"timeline_{stem}.png"
        render_timeline(stem, results, phases, out_path)


if __name__ == "__main__":
    main()
