#!/usr/bin/env python3
"""H7 visual QA — render two key contact sheets:

1. Tracklet-3 conflict (t3 ends at f=31, two possible successors: t8 at f=43
   via air, t9 at f=51 via hand). Show the trajectory with frame numbers
   and (x, y) coordinates labeled on each tracklet point.

2. Longest H7 chain on identical: [35, 37, 40, 41, 43, 45, 46] (7 tids).
   Show each tracklet's trajectory with its start/end frame.

Goal: confirm H7's correct resolution (t3 -> 9 via hand) by showing the
spatial separation between t3's endpoint and t8's startpoint (they are
~200 pixels apart in y), and by showing that t9's startpoint is at the
left hand level (~ y=440-480) while t3's endpoint is also at the left
hand reach (y=377 at f=31).
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
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h7"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLOR_LEFT = (0, 165, 255)   # orange (BGR)
COLOR_RIGHT = (255, 128, 0)  # blue
COLOR_T3 = (0, 200, 0)       # green
COLOR_T8 = (0, 220, 220)     # yellow
COLOR_T9 = (200, 0, 200)     # magenta


def load_tracklet_points(stem: str, tid: int) -> list[tuple[int, float, float]]:
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
            break  # use the first file that has data
    out.sort()
    return out


def load_wrist_frames(stem: str) -> dict:
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


def find_closest_wrist(wrist_frames, frame, max_diff=5):
    if not wrist_frames or frame in wrist_frames:
        return wrist_frames.get(frame)
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def render_contact_sheet(stem: str, frames: list[int], tracklets_to_show: list,
                         title: str, subtitle: str, out_path: Path,
                         show_label_xy: bool = False):
    """Render a contact sheet with given frames and tracklet overlays.

    tracklets_to_show: list of (tid, color, label)
    """
    video_path = VIDEOS_DIR / f"{stem}.mp4"
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Could not open {video_path}")
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
    sheet_h = 80 + rows * tile_h
    sheet_w = cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)
    cv2.putText(sheet, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, subtitle, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, "ORANGE=image-LEFT, BLUE=image-RIGHT, "
                "GREEN=t3, YELLOW=t8, MAGENTA=t9",
                (8, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    # Load all tracklet points + wrist frames
    wrist_frames = load_wrist_frames(stem)
    tids_data = {tid: load_tracklet_points(stem, tid)
                 for tid, _, _ in tracklets_to_show}
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
        w = find_closest_wrist(wrist_frames, fr, max_diff=3)
        if w is not None:
            for tag, color in [("left", COLOR_LEFT), ("right", COLOR_RIGHT)]:
                x, y, conf = w[tag]
                if conf > 0.1:
                    cx = int(x * tile_w / W)
                    cy = int(y * tile_h / H)
                    cv2.circle(img, (cx, cy), 9, color, 2)
                    cv2.putText(img, tag[0].upper(), (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        # Tracklets
        for tid, color, label in tracklets_to_show:
            by_f = tids_by_f[tid]
            if fr in by_f:
                f, x, y = by_f[fr]
                cx = int(x * tile_w / W)
                cy = int(y * tile_h / H)
                cv2.circle(img, (cx, cy), 5, color, -1)
                if show_label_xy:
                    cv2.putText(img, f"{label}({x:.0f},{y:.0f})", (cx + 8, cy - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        # Frame label
        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
        row = i // cols
        col = i % cols
        y0 = 80 + row * tile_h
        x0 = col * tile_w
        sheet[y0:y0 + tile_h, x0:x0 + tile_w] = img
    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path}")


def main():
    stem = "identical_balls_trick_000_018"

    # Contact sheet 1: tracklet 3 conflict
    # t3: f=3..31, t8: f=43..46, t9: f=51..98
    # Show key frames from each tracklet
    frames = [3, 8, 12, 17, 22, 27, 31,  # t3 trajectory
              43, 44, 45, 46,             # t8 trajectory
              51, 56, 62, 70, 80, 90]      # t9 trajectory
    render_contact_sheet(
        stem=stem,
        frames=frames,
        tracklets_to_show=[(3, COLOR_T3, "t3"), (8, COLOR_T8, "t8"),
                           (9, COLOR_T9, "t9")],
        title="H7 tracklet-3 conflict resolution: t3 -> t9 (hand) wins",
        subtitle=("v4d hand-link: t3->t9 (cost 1.5, hand=left, held 20f). "
                  "E6c air-edge: t3->t8 (cost 2.92, err=18.31). H7 picks hand. "
                  "Y-axis: t3 ends y=377, t8 starts y=601 (224px below!)."),
        out_path=OUT_DIR / "tracklet3_conflict_h7.png",
        show_label_xy=True,
    )

    # Contact sheet 2: longest H7 chain [35, 37, 40, 41, 43, 45, 46]
    # 35-46 are all BALLISTIC, no hand edges. Show each tracklet's
    # frames to demonstrate the chain.
    chain_35 = [t[0] for t in load_tracklet_points(stem, 35)]
    chain_37 = [t[0] for t in load_tracklet_points(stem, 37)]
    chain_40 = [t[0] for t in load_tracklet_points(stem, 40)]
    chain_41 = [t[0] for t in load_tracklet_points(stem, 41)]
    chain_43 = [t[0] for t in load_tracklet_points(stem, 43)]
    chain_45 = [t[0] for t in load_tracklet_points(stem, 45)]
    chain_46 = [t[0] for t in load_tracklet_points(stem, 46)]
    print(f"Chain 35 frames: {chain_35}")
    print(f"Chain 37 frames: {chain_37}")
    print(f"Chain 46 frames: {chain_46}")
    # Sample frames: every 4th from each tracklet
    frames = []
    for t_pts in [chain_35, chain_37, chain_40, chain_41, chain_43, chain_45, chain_46]:
        frames.extend(t_pts[::4])
    frames = sorted(set(frames))[:30]
    print(f"Showing {len(frames)} frames from the longest H7 chain")

    # Use distinct colors that don't clash with hand color mapping.
    # Hand colors: ORANGE/BLUE. Use WHITE outlines and varied
    # fill colors that are clearly NOT orange or blue.
    # Use bright red/magenta/cyan/green/yellow/purple/orange-red
    # but mark hands separately.
    # Actually safer: use just one highlight color (white) for all
    # chain points, but label them with their tracklet ID.
    COLORS = [
        (255, 255, 255),  # white for t35
        (200, 100, 255),  # pink for t37
        (100, 255, 100),  # light green for t40
        (255, 255, 0),    # bright yellow for t41
        (0, 255, 255),    # cyan for t43
        (255, 100, 100),  # light red for t45
        (180, 80, 255),   # purple for t46
    ]
    tracklets = [(tid, COLORS[i], f"t{tid}")
                 for i, tid in enumerate([35, 37, 40, 41, 43, 45, 46])]
    render_contact_sheet(
        stem=stem,
        frames=frames,
        tracklets_to_show=tracklets,
        title="H7 longest chain: 35->37->40->41->43->45->46 (7 tids, all BALLISTIC air-edges)",
        subtitle=("Single ball: held (35) -> released (37) -> rising (40) -> apex (41,43) "
                  "-> falling (45) -> caught (46). t40 y=406->344 (UP), t45 y=313->389 (DOWN), "
                  "t46 y=430->597 (DOWN to hand)."),
        out_path=OUT_DIR / "longest_chain_h7.png",
        show_label_xy=True,
    )


if __name__ == "__main__":
    main()
