#!/usr/bin/env python3
"""H9 contact sheet — visualize a chain's gaps.

Show chain 30 [51, 52, 54, 59, 63] on the identical video. This chain
has the most gap frames (66 of 181) and is dominated by hand events.
Visualize:
- End of each tracklet (last 2-3 frames)
- Start of each tracklet (first 2-3 frames)
- The gap windows (where detector dropout occurred)
"""
from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h9"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLOR_LEFT = (0, 165, 255)
COLOR_RIGHT = (255, 128, 0)
COLORS = [(0, 200, 0), (200, 200, 0), (200, 0, 200), (0, 200, 200),
          (200, 100, 100)]  # 5 distinct colors for 5 tracklets


def load_tracklet_points(stem, tid):
    out = []
    candidates = [
        WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv",
        WORKTREE / "detections" / f"{stem}_yolo26s_botsort.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                if "track_id" not in r:
                    continue
                if int(r["track_id"]) == tid:
                    out.append((int(r["frame"]), float(r["center_x"]),
                                float(r["center_y"])))
        if out:
            break
    out.sort()
    return out


def load_wrist_frames(stem):
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                out[fr] = {
                    "left": (float(r["left_wrist_x"]), float(r["left_wrist_y"]),
                             float(r.get("left_wrist_confidence", 0))),
                    "right": (float(r["right_wrist_x"]), float(r["right_wrist_y"]),
                              float(r.get("right_wrist_confidence", 0))),
                }
            except (ValueError, KeyError):
                continue
    return out


def render_sheet(stem, frames, tracklets, title, subtitle, out_path,
                 show_xy=True):
    video_path = VIDEOS_DIR / f"{stem}.mp4"
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ok, first = cap.read()
    if not ok:
        return
    H, W = first.shape[:2]
    tile_w = 320
    tile_h = int(H * tile_w / W)
    cols = 6
    rows = (len(frames) + cols - 1) // cols
    sheet_h = 110 + rows * tile_h
    sheet_w = cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)
    cv2.putText(sheet, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, subtitle, (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, "ORANGE=image-LEFT, BLUE=image-RIGHT",
                (8, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, "5 colors = 5 tracklets (t51=green, t52=yellow, t54=magenta, t59=cyan, t63=red)",
                (8, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    wrist_frames = load_wrist_frames(stem)
    tids_data = {tid: load_tracklet_points(stem, tid) for tid, _, _ in tracklets}
    tids_by_f = {tid: {t[0]: t for t in pts} for tid, pts in tids_data.items()}

    for i, fr in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok:
            continue
        # Force resize to (tile_h, tile_w) - some frames may have
        # slightly different shapes due to aspect-ratio rounding
        if img.shape[:2] != (tile_h, tile_w):
            img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        if fr in wrist_frames:
            w = wrist_frames[fr]
            for tag, color in [("left", COLOR_LEFT), ("right", COLOR_RIGHT)]:
                x, y, conf = w[tag]
                if conf > 0.1:
                    cx = int(x * tile_w / W)
                    cy = int(y * tile_h / H)
                    cv2.circle(img, (cx, cy), 9, color, 2)
        for tid, color, label in tracklets:
            by_f = tids_by_f[tid]
            if fr in by_f:
                f, x, y = by_f[fr]
                cx = int(x * tile_w / W)
                cy = int(y * tile_h / H)
                cv2.circle(img, (cx, cy), 5, color, -1)
                if show_xy:
                    cv2.putText(img, f"{label}", (cx + 8, cy - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
        row = i // cols
        col = i % cols
        y0 = 110 + row * tile_h
        x0 = col * tile_w
        # Final safety: ensure exact shape
        if sheet[y0:y0 + tile_h, x0:x0 + tile_w].shape != img.shape:
            print(f"  skip frame {fr}: tile {sheet[y0:y0+tile_h, x0:x0+tile_w].shape} vs img {img.shape}")
            continue
        sheet[y0:y0 + tile_h, x0:x0 + tile_w] = img
    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path}")


def main():
    stem = "identical_balls_trick_000_018"
    # Chain 30: [51, 52, 54, 59, 63]
    # Key frames: end of each + start of each + gap windows
    frames = []
    # t51 (f=765-766): 765, 766
    frames.extend([765, 766])
    # gap 51->52 (f=767-774): 770, 773
    frames.extend([770, 773])
    # t52 (f=775-780): 775, 776, 777
    frames.extend([775, 776, 777])
    # gap 52->54 (f=781-796): 785, 790, 795
    frames.extend([785, 790, 795])
    # t54 (f=797-830): 797, 798, 820, 830
    frames.extend([797, 798, 820, 830])
    # gap 54->59 (f=831-855): 840, 850
    frames.extend([840, 850])
    # t59 (f=856-872): 856, 860, 870
    frames.extend([856, 860, 870])
    # gap 59->63 (f=873-889): 880, 885
    frames.extend([880, 885])
    # t63 (f=890-945): 890, 920, 945
    frames.extend([890, 920, 945])
    render_sheet(
        stem=stem,
        frames=frames,
        tracklets=[(51, COLORS[0], "t51"), (52, COLORS[1], "t52"),
                   (54, COLORS[2], "t54"), (59, COLORS[3], "t59"),
                   (63, COLORS[4], "t63")],
        title="H9 chain 30: [51, 52, 54, 59, 63] - 5 tids, 4 gaps, 66 gap frames",
        subtitle=("Detector dropouts between tracklets. Most are real hand-hold "
                  "phases (3 HAND_TRANSITIONS). t54 covers f=797-830 (34pts) "
                  "is the longest mid-air segment."),
        out_path=OUT_DIR / "chain30_object_permanence.png",
        show_xy=True,
    )


if __name__ == "__main__":
    main()
