#!/usr/bin/env python3
"""H12 v1 vs v2 comparison contact sheet.

Shows the same video timeline twice (v1 on top, v2 on bottom) so the
qualitative difference is visible at a glance.
"""
from __future__ import annotations

import csv
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v2"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Color scheme
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


def render_v1_v2_comparison(stem: str, v1_results: list[dict],
                              v2_results: list[dict], out_path: Path):
    """Render 4-row comparison: v1 pattern, v1 conf, v2 pattern, v2 conf."""
    import cv2
    import numpy as np

    n = len(v1_results)
    if n == 0:
        return
    fmin = v1_results[0]["frame"]
    fmax = v1_results[-1]["frame"]
    fspan = max(1, fmax - fmin)
    W = 1800
    H_row = 60
    H_total = H_row * 4 + 80
    img = np.full((H_total, W, 3), 255, dtype=np.uint8)

    def draw_row(row_y0: int, results: list[dict], title: str,
                 conf_color: tuple = (255, 68, 68)):
        H = H_row
        confs = np.array([r["confidence"] for r in results])
        # pattern band
        for r in results:
            c = PATTERN_COLORS_BGR.get(r["pattern"], (255, 255, 255))
            x0 = int((r["frame"] - fmin) / fspan * (W - 20)) + 10
            x1 = int((r["frame"] + 1 - fmin) / fspan * (W - 20)) + 10
            x1 = max(x1, x0 + 1)
            cv2.rectangle(img, (x0, row_y0), (x1, row_y0 + H), c, -1)
        cv2.putText(img, title, (5, row_y0 + H - 5), cv2.FONT_HERSHEY_SIMPLEX,
                     0.4, (0, 0, 0), 1, cv2.LINE_AA)
        # confidence line below
        row2_y = row_y0 + H + 2
        for i in range(1, n):
            x0 = int((results[i - 1]["frame"] - fmin) / fspan * (W - 20)) + 10
            x1 = int((results[i]["frame"] - fmin) / fspan * (W - 20)) + 10
            y0 = row2_y + H - int(confs[i - 1] * H)
            y1 = row2_y + H - int(confs[i] * H)
            cv2.line(img, (x0, y0), (x1, y1), conf_color, 1, cv2.LINE_AA)
        cv2.putText(img, f"{title} conf", (5, row2_y + H - 5),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)

    draw_row(30, v1_results, "v1", conf_color=(0, 0, 200))
    draw_row(30 + H_row * 2 + 4, v2_results, "v2", conf_color=(0, 128, 0))

    # Title
    cv2.putText(img, f"{stem}: H12 v1 vs v2", (10, 20),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    # Legend
    legend_y0 = H_total - 30
    x_cur = 10
    all_patterns = sorted(set([r["pattern"] for r in v1_results] +
                              [r["pattern"] for r in v2_results]))
    for pattern in all_patterns:
        c = PATTERN_COLORS_BGR.get(pattern, (255, 255, 255))
        cv2.rectangle(img, (x_cur, legend_y0), (x_cur + 14, legend_y0 + 14),
                       c, -1)
        cv2.putText(img, pattern, (x_cur + 18, legend_y0 + 11),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)
        text_w = len(pattern) * 7
        x_cur += 20 + text_w

    cv2.imwrite(str(out_path), img)
    print(f"  wrote: {out_path.name}")


def main():
    for stem in STEMS:
        v1 = []
        with (H1_DATA / f"pattern_inference_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v1.append({
                    "frame": int(r["frame"]),
                    "pattern": r["pattern"],
                    "confidence": float(r["confidence"]),
                })
        v2 = []
        with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v2.append({
                    "frame": int(r["frame"]),
                    "pattern": r["pattern"],
                    "confidence": float(r["confidence"]),
                })
        out_path = H1_CS / f"comparison_{stem}.png"
        render_v1_v2_comparison(stem, v1, v2, out_path)


if __name__ == "__main__":
    main()
