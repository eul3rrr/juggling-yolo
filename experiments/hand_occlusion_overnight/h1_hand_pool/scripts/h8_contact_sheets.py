#!/usr/bin/env python3
"""H8 visual QA — render the physics-violating chains for inspection.

H8 flagged edge 5->6 as physics-violating (residual 15px, 90px y-jump
in 1 frame between f=26 and f=27). Visualize the chain to confirm.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h8"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLOR_LEFT = (0, 165, 255)
COLOR_RIGHT = (255, 128, 0)
COLOR_T5 = (0, 200, 0)       # green
COLOR_T6 = (200, 200, 0)     # yellow
COLOR_T50 = (0, 200, 200)    # cyan
COLOR_T55 = (200, 0, 200)    # magenta


def load_tracklet_points(stem: str, tid: int):
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
    tile_w = 360
    tile_h = int(H * tile_w / W)
    cols = 6
    rows = (len(frames) + cols - 1) // cols
    sheet_h = 90 + rows * tile_h
    sheet_w = cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)
    cv2.putText(sheet, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, subtitle, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, "ORANGE=image-LEFT, BLUE=image-RIGHT",
                (8, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    wrist_frames = load_wrist_frames(stem)
    tids_data = {tid: load_tracklet_points(stem, tid) for tid, _, _ in tracklets}
    tids_by_f = {tid: {t[0]: t for t in pts} for tid, pts in tids_data.items()}

    for i, fr in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok:
            continue
        img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        if img.shape != (tile_h, tile_w, 3):
            img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        # Wrists
        if fr in wrist_frames:
            w = wrist_frames[fr]
            for tag, color in [("left", COLOR_LEFT), ("right", COLOR_RIGHT)]:
                x, y, conf = w[tag]
                if conf > 0.1:
                    cx = int(x * tile_w / W)
                    cy = int(y * tile_h / H)
                    cv2.circle(img, (cx, cy), 9, color, 2)
        # Tracklets
        for tid, color, label in tracklets:
            by_f = tids_by_f[tid]
            if fr in by_f:
                f, x, y = by_f[fr]
                cx = int(x * tile_w / W)
                cy = int(y * tile_h / H)
                cv2.circle(img, (cx, cy), 5, color, -1)
                if show_xy:
                    cv2.putText(img, f"{label}({x:.0f},{y:.0f})", (cx + 8, cy - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
        row = i // cols
        col = i % cols
        y0 = 90 + row * tile_h
        x0 = col * tile_w
        sheet[y0:y0 + tile_h, x0:x0 + tile_w] = img
    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path}")


def main():
    stem = "identical_balls_trick_000_018"

    # Chain 4: t5, t6 — physics-violating (90px y-jump at f=27)
    frames = list(range(20, 50))  # 30 frames
    render_sheet(
        stem=stem,
        frames=frames,
        tracklets=[(5, COLOR_T5, "t5"), (6, COLOR_T6, "t6")],
        title="H8 chain 4: t5->t6 FLAGGED as physics-violating",
        subtitle=("t5: f=21-26 y=564->489 (drops 75px in 5f). "
                  "t6: f=27-127 starts y=398. 90px y-jump in 1 frame. "
                  "E6c err=2.49 admitted the edge; H8 flags it."),
        out_path=OUT_DIR / "chain4_t5_t6_violating.png",
        show_xy=True,
    )

    # Chain 29: t50, t55 — physics-violating (residual 19.7)
    t50 = load_tracklet_points(stem, 50)
    t55 = load_tracklet_points(stem, 55)
    print(f"t50: f={t50[0][0]}-{t50[-1][0]}, n={len(t50)}")
    print(f"t55: f={t55[0][0]}-{t55[-1][0]}, n={len(t55)}")
    if t50 and t55:
        fmin = min(t50[0][0], t55[0][0])
        fmax = max(t50[-1][0], t55[-1][0])
        frames = list(range(fmin - 2, fmax + 3))
        render_sheet(
            stem=stem,
            frames=frames,
            tracklets=[(50, COLOR_T50, "t50"), (55, COLOR_T55, "t55")],
            title="H8 chain 29: t50->t55 FLAGGED as physics-violating",
            subtitle=("E6c ballistic edge between t50 and t55. "
                      "H8 fit residual 19.7 px (threshold 5.0)."),
            out_path=OUT_DIR / "chain29_t50_t55_violating.png",
            show_xy=True,
        )

    # Show a CONSISTENT chain for comparison: longest chain
    render_sheet(
        stem=stem,
        frames=list(range(507, 530)),
        tracklets=[(35, COLOR_T5, "t35"), (37, COLOR_T6, "t37"),
                   (40, COLOR_T50, "t40"), (41, COLOR_T55, "t41")],
        title="H8 longest chain (consistent): t35->t37->t40->t41",
        subtitle=("H8 physics check: per-edge residual < 5px (CONSISTENT). "
                  "Real juggling cycle: hold -> release -> rise -> apex."),
        out_path=OUT_DIR / "longest_chain_consistent.png",
        show_xy=True,
    )


if __name__ == "__main__":
    main()
