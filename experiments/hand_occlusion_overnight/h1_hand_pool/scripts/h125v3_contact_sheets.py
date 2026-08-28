#!/usr/bin/env python3
"""H125 v3 contact sheets: visual QA of NEW CORRECT edges in h125_v3.

H125 v3 admits 14 NEW CORRECT edges that h7v3plus3 missed. We need
to visually verify these are real catch-throws, not tracker artifacts.

Selection: 5 cases spanning both videos and the cost range:
  - identical 4->7: cost=5.72 (highest correct cost)
  - identical 25->27: cost=3.26 (lowest correct cost)
  - identical 12->17: cost=5.59, gap=10 (long gap, REVIEW gap=10)
  - identical 9->12: cost=3.91, gap=0
  - youtube 16->21: cost=?
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    print("ERROR: opencv not available")
    raise

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h125v3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Tracklet features: first_frame, last_frame, n_pts
def load_tracklet_features():
    tf = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["tid"]))
            tf[key] = {
                "first_frame": int(row["first_frame"]),
                "last_frame": int(row["last_frame"]),
                "n_pts": int(row["n_pts"]),
            }
    return tf


def load_detections(stem):
    """Load all detections for a video."""
    out = []
    path = DETECTIONS / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as f:
        for r in csv.DictReader(f):
            out.append({
                "track_id": int(r["track_id"]),
                "frame": int(r["frame"]),
                "x": float(r["center_x"]),
                "y": float(r["center_y"]),
                "conf": float(r["confidence"]),
            })
    return out


def load_pose(stem):
    """Load pose (wrist positions) for a video."""
    out = []
    path = DETECTIONS / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as f:
        for r in csv.DictReader(f):
            out.append(r)
    return out


def get_wrist_xy(pose_rows, frame, hand='L'):
    """Get wrist position for a frame."""
    if hand == 'L':
        kp_idx = 9  # left wrist
    else:
        kp_idx = 10  # right wrist
    # Find a row matching the frame
    # The pose CSV has multiple keypoints per row, but format may differ
    # Just find the closest frame row
    for r in pose_rows:
        if r.get('frame') and int(float(r['frame'])) == frame:
            x_key = f"x{kp_idx}" if f"x{kp_idx}" in r else None
            y_key = f"y{kp_idx}" if f"y{kp_idx}" in r else None
            if x_key and y_key:
                try:
                    return float(r[x_key]), float(r[y_key])
                except (ValueError, TypeError):
                    continue
    return None, None


def make_contact_sheet(stem, src_tid, tgt_tid, src_last_frame, tgt_first_frame, src_xy_path, tgt_xy_path, src_wrist_dist, tgt_wrist_dist):
    """Render a 6-frame contact sheet showing approach, last clear, contact, mid-hold, first outgoing, post-throw."""
    # 6 frames: approach, last clear, contact, mid-hold, first outgoing, post-throw
    # Get video path - try lab worktree first, then the source workspace
    workspace_videos = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
    video_paths = {
        "identical_balls_trick_000_018": [
            WORKTREE / "videos" / "identical_balls_trick_000_018.mp4",
            workspace_videos / "identical_balls_trick_000_018.mp4",
        ],
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": [
            WORKTREE / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
            workspace_videos / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
        ],
    }
    video_path = None
    for p in video_paths[stem]:
        if p.exists():
            video_path = p
            break
    if video_path is None:
        print(f"  video not found in any of: {[str(p) for p in video_paths[stem]]}")
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  could not open {video_path}")
        return None

    # 6 frames: approach, last clear, contact, mid-hold, first outgoing, post-throw
    src_first = src_xy_path[0][0] if src_xy_path else src_last_frame
    src_last = src_last_frame
    tgt_first = tgt_first_frame
    tgt_last = tgt_xy_path[-1][0] if tgt_xy_path else tgt_first + 30
    mid = (src_last + tgt_first) // 2

    frame_offsets = [
        ("approach", max(src_first, src_last - 20)),
        ("last clear", src_last - 3),
        ("contact/disappear", src_last),
        ("middle of hold", mid),
        ("first outgoing", tgt_first + 2),
        ("shortly after throw", tgt_first + 8),
    ]

    # Get pose
    pose_rows = load_pose(stem)

    # Render
    images = []
    for label, frame_idx in frame_offsets:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            # try next frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_idx + 5, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1))
            ret, frame = cap.read()
            if not ret:
                continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame_rgb.shape

        # Find tracklet points near this frame
        # Source last points (last 5)
        src_pts = [(f, x, y) for (f, x, y) in src_xy_path if abs(f - frame_idx) <= 5]
        tgt_pts = [(f, x, y) for (f, x, y) in tgt_xy_path if abs(f - frame_idx) <= 5]
        # Plot
        for (f, x, y) in src_pts:
            cv2.circle(frame_rgb, (int(x), int(y)), 8, (255, 165, 0), 2)  # orange (left/source)
        for (f, x, y) in tgt_pts:
            cv2.circle(frame_rgb, (int(x), int(y)), 8, (0, 100, 255), 2)  # red (right/target)
        # Wrist
        for hand_label in ['L', 'R']:
            wx, wy = get_wrist_xy(pose_rows, frame_idx, hand_label)
            if wx is not None and wy is not None:
                color = (255, 0, 0) if hand_label == 'L' else (0, 255, 0)
                cv2.circle(frame_rgb, (int(wx), int(wy)), 12, color, 3)
                cv2.putText(frame_rgb, hand_label, (int(wx) + 15, int(wy)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        # Label
        cv2.putText(frame_rgb, f'{label} f={frame_idx}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame_rgb, f'src_end_d={src_wrist_dist:.1f} tgt_start_d={tgt_wrist_dist:.1f}',
                    (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        images.append(frame_rgb)
    cap.release()

    if not images:
        return None
    # Stack into 2x3 grid
    rows, cols = 2, 3
    h, w, _ = images[0].shape
    grid = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        grid[r * h:(r + 1) * h, c * w:(c + 1) * w] = img
    return grid


def main():
    tf = load_tracklet_features()
    # Load pose reference for wrist distances (placeholder)
    # Read the 5 cases
    cases = [
        # (stem, src, tgt)
        ("identical_balls_trick_000_018", 4, 7),    # gap=0 review, cost=5.72
        ("identical_balls_trick_000_018", 25, 27),  # gap=6 review, cost=3.26
        ("identical_balls_trick_000_018", 12, 17),  # gap=10 review, cost=5.59
        ("identical_balls_trick_000_018", 9, 12),   # gap=0 review, cost=3.91
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 16, 21),  # gap=8 review
    ]

    for stem, src, tgt in cases:
        print(f'\n=== {stem[:20]} {src}->{tgt} ===')
        # Get tracklet features
        src_tf = tf.get((stem, src), {})
        tgt_tf = tf.get((stem, tgt), {})
        if not src_tf or not tgt_tf:
            print(f'  missing features')
            continue
        src_last_frame = src_tf['last_frame']
        tgt_first_frame = tgt_tf['first_frame']
        print(f'  src last_frame={src_last_frame}, tgt first_frame={tgt_first_frame}, n_pts={src_tf["n_pts"]}/{tgt_tf["n_pts"]}')

        # Load detections
        dets = load_detections(stem)
        src_xy = sorted([(d['frame'], d['x'], d['y']) for d in dets if d['track_id'] == src])
        tgt_xy = sorted([(d['frame'], d['x'], d['y']) for d in dets if d['track_id'] == tgt])
        print(f'  src pts: {len(src_xy)} (range f={src_xy[0][0] if src_xy else "?"} to f={src_xy[-1][0] if src_xy else "?"})')
        print(f'  tgt pts: {len(tgt_xy)} (range f={tgt_xy[0][0] if tgt_xy else "?"} to f={tgt_xy[-1][0] if tgt_xy else "?"})')

        # Compute wrist distances
        pose_rows = load_pose(stem)
        src_wx, src_wy = get_wrist_xy(pose_rows, src_last_frame, 'L')
        src_wrx, src_wry = get_wrist_xy(pose_rows, src_last_frame, 'R')
        if src_xy and src_wx is not None:
            sx, sy = src_xy[-1][1], src_xy[-1][2]
            dl = math.hypot(sx - src_wx, sy - src_wy)
            dr = math.hypot(sx - src_wrx, sy - src_wry)
        else:
            dl = dr = -1
        print(f'  src end ({src_xy[-1][1]:.1f}, {src_xy[-1][2]:.1f}): dist L={dl:.1f}, R={dr:.1f}' if src_xy else '  no src xy')

        tgt_wx, tgt_wy = get_wrist_xy(pose_rows, tgt_first_frame, 'L')
        tgt_wrx, tgt_wry = get_wrist_xy(pose_rows, tgt_first_frame, 'R')
        if tgt_xy and tgt_wx is not None:
            tx, ty = tgt_xy[0][1], tgt_xy[0][2]
            dl2 = math.hypot(tx - tgt_wx, ty - tgt_wy)
            dr2 = math.hypot(tx - tgt_wrx, ty - tgt_wry)
        else:
            dl2 = dr2 = -1
        print(f'  tgt start ({tgt_xy[0][1]:.1f}, {tgt_xy[0][2]:.1f}): dist L={dl2:.1f}, R={dr2:.1f}' if tgt_xy else '  no tgt xy')

        # Render
        grid = make_contact_sheet(stem, src, tgt, src_last_frame, tgt_first_frame, src_xy, tgt_xy, min(dl, dr), min(dl2, dr2))
        if grid is not None:
            out_path = OUT_DIR / f'h125v3_{stem[:20]}_{src}_{tgt}.png'
            cv2.imwrite(str(out_path), cv2.cvtColor(grid, cv2.COLOR_RGB2BGR))
            print(f'  saved: {out_path}')


if __name__ == '__main__':
    main()
