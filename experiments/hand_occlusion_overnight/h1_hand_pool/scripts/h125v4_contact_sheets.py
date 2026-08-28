#!/usr/bin/env python3
"""H125 v4 contact sheets: visual QA of NEW edges that survive H112 + H114 v1 strict.

H125 v4 (union_h112_h114_25_200) admits 13 NEW V4 edges:
  - 12 identical: (25, 27), (9, 12), (66, 69), (53, 58), (54, 57), (10, 11),
    (44, 53), (14, 19), (6, 15), (4, 7), (63, 65), (73, 75)
  - 1 YouTube: (10, 11)

Plus the 2 wrong edges (6->15 identical, 10->11 YouTube) are included to
characterize the precision floor.

Selection: render contact sheets for ALL 13 surviving NEW edges + the
2 wrong edges. H125 report's H125 v3 contact sheet only sampled 5 of
the 14 NEW V3 edges; H125 v4 is more comprehensive.

Output: contact_sheets_h125v4/ directory
"""
from __future__ import annotations

import csv
import math
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
OUT_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h125v4"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_tracklet_features():
    tf = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["tid"]))
            tf[key] = {
                "first_frame": int(row["first_frame"]),
                "last_frame": int(row["last_frame"]),
                "n_pts": int(row["n_pts"]),
                "end_dist": float(row["end_dist"]) if row["end_dist"] else 0.0,
                "start_dist": float(row["start_dist"]) if row["start_dist"] else 0.0,
                "end_x": float(row["last_x"]),
                "end_y": float(row["last_y"]),
                "first_x": float(row["first_x"]),
                "first_y": float(row["first_y"]),
            }
    return tf


def load_detections(stem):
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
    out = []
    path = DETECTIONS / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as f:
        for r in csv.DictReader(f):
            out.append(r)
    return out


def get_wrist_xy(pose_rows, frame, hand='L'):
    if hand == 'L':
        kp_idx = 9
    else:
        kp_idx = 10
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


def make_contact_sheet(stem, src_tid, tgt_tid, src_last_frame, tgt_first_frame,
                       src_xy_path, tgt_xy_path, src_wrist_dist, tgt_wrist_dist,
                       h59_label):
    """Render a 6-frame contact sheet: approach, last clear, contact, mid-hold, first outgoing, post-throw."""
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
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    src_first = src_xy_path[0][0] if src_xy_path else src_last_frame
    tgt_last = tgt_xy_path[-1][0] if tgt_xy_path else tgt_first_frame + 30
    mid = (src_last_frame + tgt_first_frame) // 2

    frame_offsets = [
        ("approach", max(src_first, src_last_frame - 20)),
        ("last clear", src_last_frame - 3),
        ("contact/disappear", src_last_frame),
        ("middle of hold", mid),
        ("first outgoing", tgt_first_frame + 2),
        ("shortly after throw", tgt_first_frame + 8),
    ]

    pose_rows = load_pose(stem)

    images = []
    for label, frame_idx in frame_offsets:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_idx + 5, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1))
            ret, frame = cap.read()
            if not ret:
                continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame_rgb.shape

        src_pts = [(f, x, y) for (f, x, y) in src_xy_path if abs(f - frame_idx) <= 5]
        tgt_pts = [(f, x, y) for (f, x, y) in tgt_xy_path if abs(f - frame_idx) <= 5]
        for (f, x, y) in src_pts:
            cv2.circle(frame_rgb, (int(x), int(y)), 8, (255, 165, 0), 2)  # orange source
        for (f, x, y) in tgt_pts:
            cv2.circle(frame_rgb, (int(x), int(y)), 8, (0, 100, 255), 2)  # blue target
        for hand_label in ['L', 'R']:
            wx, wy = get_wrist_xy(pose_rows, frame_idx, hand_label)
            if wx is not None and wy is not None:
                color = (255, 0, 0) if hand_label == 'L' else (0, 255, 0)
                cv2.circle(frame_rgb, (int(wx), int(wy)), 12, color, 3)
                cv2.putText(frame_rgb, hand_label, (int(wx) + 15, int(wy)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.putText(frame_rgb, f'{label} f={frame_idx}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame_rgb, f'src_end={src_wrist_dist:.1f} tgt_start={tgt_wrist_dist:.1f} H59={h59_label}',
                    (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        images.append(frame_rgb)
    cap.release()

    if not images:
        return None
    rows, cols = 2, 3
    h, w, _ = images[0].shape
    grid = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        grid[r * h:(r + 1) * h, c * w:(c + 1) * w, :] = img
    return grid


def main():
    tf = load_tracklet_features()

    # Load H59 review labels for context
    review_map = {}
    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        for r in csv.DictReader(f):
            review_map[(r['stem'], int(r['source']), int(r['candidate']))] = r['label']

    # 13 NEW V4 edges (12 identical + 1 YouTube) that survive H112 + H114 v1 strict
    cases = [
        # identical: 12 surviving NEW V4 edges
        ("identical_balls_trick_000_018", 25, 27),
        ("identical_balls_trick_000_018", 9, 12),
        ("identical_balls_trick_000_018", 66, 69),
        ("identical_balls_trick_000_018", 53, 58),
        ("identical_balls_trick_000_018", 54, 57),
        ("identical_balls_trick_000_018", 10, 11),
        ("identical_balls_trick_000_018", 44, 53),
        ("identical_balls_trick_000_018", 14, 19),
        ("identical_balls_trick_000_018", 6, 15),   # WRONG per reviewer
        ("identical_balls_trick_000_018", 4, 7),
        ("identical_balls_trick_000_018", 63, 65),
        ("identical_balls_trick_000_018", 73, 75),
        # YouTube: 1 surviving NEW V4 edge
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11),  # WRONG per reviewer
    ]

    for stem, src, tgt in cases:
        print(f'\n=== {stem[:20]} {src}->{tgt} ===')
        h59_label = review_map.get((stem, src, tgt), "not_in_review")
        src_tf = tf.get((stem, src), {})
        tgt_tf = tf.get((stem, tgt), {})
        if not src_tf or not tgt_tf:
            print(f'  missing features')
            continue
        src_last_frame = src_tf['last_frame']
        tgt_first_frame = tgt_tf['first_frame']
        sj = math.hypot(tgt_tf['first_x'] - src_tf['end_x'],
                        tgt_tf['first_y'] - src_tf['end_y'])
        print(f'  H59={h59_label} src last_f={src_last_frame} tgt first_f={tgt_first_frame} '
              f'n_pts={src_tf["n_pts"]}/{tgt_tf["n_pts"]} '
              f'src_end_d={src_tf["end_dist"]:.1f} tgt_start_d={tgt_tf["start_dist"]:.1f} sj={sj:.1f}')

        dets = load_detections(stem)
        src_xy = sorted([(d['frame'], d['x'], d['y']) for d in dets if d['track_id'] == src])
        tgt_xy = sorted([(d['frame'], d['x'], d['y']) for d in dets if d['track_id'] == tgt])
        print(f'  src pts: {len(src_xy)} tgt pts: {len(tgt_xy)}')

        pose_rows = load_pose(stem)
        src_wx, src_wy = get_wrist_xy(pose_rows, src_last_frame, 'L')
        src_wrx, src_wry = get_wrist_xy(pose_rows, src_last_frame, 'R')
        if src_xy and src_wx is not None:
            sx, sy = src_xy[-1][1], src_xy[-1][2]
            dl = math.hypot(sx - src_wx, sy - src_wy)
            dr = math.hypot(sx - src_wrx, sy - src_wry)
        else:
            dl = dr = -1
        tgt_wx, tgt_wy = get_wrist_xy(pose_rows, tgt_first_frame, 'L')
        tgt_wrx, tgt_wry = get_wrist_xy(pose_rows, tgt_first_frame, 'R')
        if tgt_xy and tgt_wx is not None:
            tx, ty = tgt_xy[0][1], tgt_xy[0][2]
            dl2 = math.hypot(tx - tgt_wx, ty - tgt_wy)
            dr2 = math.hypot(tx - tgt_wrx, ty - tgt_wry)
        else:
            dl2 = dr2 = -1

        grid = make_contact_sheet(stem, src, tgt, src_last_frame, tgt_first_frame,
                                  src_xy, tgt_xy, min(dl, dr), min(dl2, dr2), h59_label)
        if grid is not None:
            out_path = OUT_DIR / f'h125v4_{stem[:20]}_{src}_{tgt}.png'
            cv2.imwrite(str(out_path), cv2.cvtColor(grid, cv2.COLOR_RGB2BGR))
            print(f'  saved: {out_path}')


if __name__ == '__main__':
    main()
