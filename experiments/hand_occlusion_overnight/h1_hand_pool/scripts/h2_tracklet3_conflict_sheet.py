#!/usr/bin/env python3
"""H2 conflict resolver — render a side-by-side contact sheet for the
tracklet-3 conflict (3 -> {hand=9, air=8}) on the identical video.

The conflict is:
  - E6c says 3->8 (BALLISTIC, err=18.31) — mid-air
  - v4d says 3->9 (HAND_TRANSITION, tok_age=20, hand=left) — held then thrown

We want to see all three tracklets and the two possible successor candidates
side-by-side, on the actual video frames, with wrist positions overlaid.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h2_conflict"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Color mapping (image coords; "left" / "right" image side)
COLOR_LEFT = (0, 165, 255)   # orange (BGR)
COLOR_RIGHT = (255, 128, 0)  # blue
COLOR_T3 = (0, 200, 0)       # green: tracklet 3
COLOR_T8 = (200, 200, 0)     # yellow: tracklet 8 (air candidate)
COLOR_T9 = (200, 0, 200)     # magenta: tracklet 9 (hand candidate)
COLOR_WRIST = (255, 255, 255)


def load_tracklet_points(stem: str, tid: int) -> list[tuple[int, float, float, float]]:
    """Load a tracklet's (frame, x, y, score) for the given stem+tid."""
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
                try:
                    # norfair columns: frame,time_seconds,track_id,confidence,center_x,center_y,observed
                    # botsort columns:  video,frame,time_seconds,tracker,track_id,...,confidence,center_x,center_y,...
                    if "track_id" in r:
                        tid_field = "track_id"
                    else:
                        continue
                    if int(r[tid_field]) == tid:
                        out.append((int(r["frame"]), float(r["center_x"]), float(r["center_y"]), float(r.get("confidence", 0))))
                except (ValueError, KeyError):
                    continue
    out.sort()
    return out


def load_wrist_frames(stem: str) -> dict:
    """Return {frame: {'left': (x,y), 'right': (x,y)}} from the pose CSV."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                lx = float(r["left_wrist_x"]); ly = float(r["left_wrist_y"])
                rx = float(r["right_wrist_x"]); ry = float(r["right_wrist_y"])
                lconf = float(r.get("left_wrist_confidence", 0))
                rconf = float(r.get("right_wrist_confidence", 0))
                out[fr] = {
                    "left": (lx, ly, lconf),
                    "right": (rx, ry, rconf),
                }
            except (ValueError, KeyError):
                continue
    return out


def find_closest_wrist(wrist_frames: dict, frame: int, max_diff: int = 5):
    if not wrist_frames:
        return None
    # find nearest frame within max_diff
    if frame in wrist_frames:
        return wrist_frames[frame]
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def main():
    stem = "identical_balls_trick_000_018"
    video_key = f"videos/{stem}.mp4"
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        print(f"Video not found: {video_path}")
        return
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    t3 = load_tracklet_points(stem, 3)
    t8 = load_tracklet_points(stem, 8)
    t9 = load_tracklet_points(stem, 9)
    wrist_frames = load_wrist_frames(stem)

    print(f"t3: {len(t3)} pts, frames {t3[0][0]}-{t3[-1][0]}")
    print(f"t8: {len(t8)} pts, frames {t8[0][0]}-{t8[-1][0]}")
    print(f"t9: {len(t9)} pts, frames {t9[0][0]}-{t9[-1][0]}")

    # Build the contact-sheet frames:
    # 1) t3 frames: every 4th frame from t3[0] to t3[-1]
    # 2) t8 frames: all (only 4 points)
    # 3) t9 frames: every 4th frame from t9[0] to t9[-1]
    # 4) hand-edge-relevant frames: f=27..32 (catch), f=49..54 (throw)
    t3_frames = [t[0] for t in t3][::3]
    t8_frames = [t[0] for t in t8]
    t9_frames = [t[0] for t in t9][::3]
    catch_frames = [27, 29, 31, 32, 33]   # t3's endpoint neighborhood
    throw_frames = [49, 51, 52, 54, 56]   # t9's start neighborhood

    all_frames = t3_frames + t8_frames + t9_frames + catch_frames + throw_frames
    all_frames = sorted(set(all_frames))
    print(f"Rendering {len(all_frames)} frames")

    # Frame index for quick lookup
    t3_by_f = {t[0]: t for t in t3}
    t8_by_f = {t[0]: t for t in t8}
    t9_by_f = {t[0]: t for t in t9}

    # Get tile size from one frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ok, first = cap.read()
    if not ok:
        print("Could not read frame 0")
        return
    H, W = first.shape[:2]
    # scale down to 360 wide
    tile_w = 360
    tile_h = int(H * tile_w / W)
    print(f"first frame shape={first.shape}, tile=({tile_h},{tile_w})")
    cols = 6
    rows = (len(all_frames) + cols - 1) // cols
    sheet_h = 30 + rows * tile_h
    sheet_w = cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)
    cv2.putText(sheet, f"Tracklet-3 conflict: t3->{{t8 (air), t9 (hand)}} on {video_key}",
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"frames: t3 [{t3[0][0]}-{t3[-1][0]}], t8 [{t8[0][0]}-{t8[-1][0]}], t9 [{t9[0][0]}-{t9[-1][0]}]",
                (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(sheet, "ORANGE=image-LEFT hand, BLUE=image-RIGHT hand, GREEN=t3, YELLOW=t8, MAGENTA=t9",
                (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    for i, fr in enumerate(all_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok:
            print(f"  could not read frame {fr}")
            continue
        # Always resize to (tile_h, tile_w) to handle variable source size
        img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        if img.shape != (tile_h, tile_w, 3):
            print(f"  WARN: frame {fr} resized to {img.shape}, expected ({tile_h},{tile_w},3)")

        # Draw wrists
        w = find_closest_wrist(wrist_frames, fr, max_diff=3)
        if w is not None:
            for tag, color in [("left", COLOR_LEFT), ("right", COLOR_RIGHT)]:
                x, y, conf = w[tag]
                if conf > 0.1:
                    cx = int(x * tile_w / W)
                    cy = int(y * tile_h / H)
                    cv2.circle(img, (cx, cy), 8, color, 2)
                    cv2.putText(img, f"{tag[0].upper()}", (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

        # Draw tracklet points
        for (tag, by_f, color) in [
            ("t3", t3_by_f, COLOR_T3),
            ("t8", t8_by_f, COLOR_T8),
            ("t9", t9_by_f, COLOR_T9),
        ]:
            if fr in by_f:
                x, y, conf = by_f[fr][1], by_f[fr][2], by_f[fr][3]
                cx = int(x * tile_w / W)
                cy = int(y * tile_h / H)
                cv2.circle(img, (cx, cy), 4, color, -1)

        # Overlay text
        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)

        # Place in grid
        row = i // cols
        col = i % cols
        y0 = 70 + row * tile_h
        x0 = col * tile_w
        # Ensure img has the right shape (some video frames may have different aspect)
        if img.shape[0] != tile_h or img.shape[1] != tile_w:
            print(f"  FORCE resize: frame {fr} was {img.shape}, target ({tile_h},{tile_w},3)")
            img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        if y0 + tile_h > sheet.shape[0] or x0 + tile_w > sheet.shape[1]:
            print(f"  OUT OF BOUNDS: i={i} y0={y0} sheet_h={sheet.shape[0]}")
            continue
        sheet[y0:y0 + tile_h, x0:x0 + tile_w] = img

    out_path = OUT_DIR / "tracklet3_conflict.png"
    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
