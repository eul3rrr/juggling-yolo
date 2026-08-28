#!/usr/bin/env python3
"""H17 contact sheets: render V-shape trajectory for strict-positive candidates.

Renders compact 6-frame contact sheets for the most informative
H17 candidates:
  1. The 2 v4d-rejected links (35->40 identical, 15->25 youtube)
  2. A small sample of the 149 strict V-shape positives from the
     broader search (e6c_not_in_h7v2 and adjacent) -- visual QA
     to estimate precision

Uses cv2 (same as h14_contact_sheets.py).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/scripts")))
from h17_v_shape_recovery import (
    H17_THRESHOLDS, H17_OUT, WORKTREE,
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
    v_shape_check, get_h7v2_admitted_pairs,
)

import cv2
import numpy as np


def find_video_path(stem):
    candidates = [
        WORKTREE / "videos" / f"{stem}.mp4",
        Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos") / f"{stem}.mp4",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def read_frame(video_path, frame_idx):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def draw_text(img, x, y, text, color=(0, 0, 0), scale=0.6, thickness=2):
    """Render text with a small white background for legibility."""
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    cv2.rectangle(img, (int(x), int(y - th - 4)), (int(x + tw), int(y)), (255, 255, 255), -1)
    cv2.putText(img, text, (int(x), int(y - 2)), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)


def draw_circle(img, x, y, color, radius, thickness=2):
    cv2.circle(img, (int(x), int(y)), radius, color, thickness)


def draw_hand_marker(img, wrist, color, label=""):
    if wrist is None:
        return
    x, y = wrist
    draw_circle(img, x, y, color, 14, 3)
    draw_circle(img, x, y, color, 4, 2)
    if label:
        draw_text(img, x + 18, y - 6, label, color=color, scale=0.5, thickness=1)


def render_contact_sheet(stem, from_tid, to_tid, kind, v_result, out_path):
    """Render 6-frame contact sheet showing approach, V-apex, throw."""
    video_path = find_video_path(stem)
    if video_path is None:
        print(f"  no video for {stem}")
        return False

    src_dets = load_per_det_tracklet(stem, from_tid)
    tgt_dets = load_per_det_tracklet(stem, to_tid)
    if not src_dets or not tgt_dets:
        print(f"  no dets for {stem}:{from_tid}->{to_tid}")
        return False

    # 6 frames: 3 from source tail, V-apex, 3 from target head
    tail_n = 3
    head_n = 3
    src_tail = src_dets[-tail_n:]
    tgt_head = tgt_dets[:head_n]

    # V-apex frame
    apex = v_result.get("apex")
    apex_frame = apex[2] if apex else (src_dets[-1][0] + tgt_dets[0][0]) // 2

    frames = []
    for (fr, x, y, c) in src_tail:
        frames.append((fr, x, y, from_tid, "src"))
    frames.append((apex_frame, apex[0], apex[1], -1, "apex") if apex else (apex_frame, 0, 0, -1, "apex"))
    for (fr, x, y, c) in tgt_head:
        frames.append((fr, x, y, to_tid, "tgt"))

    wrist_frames = load_wrist_frames(stem)
    LEFT_COLOR = (0, 165, 255)  # orange
    RIGHT_COLOR = (255, 100, 0)  # blue
    SRC_COLOR = (0, 255, 0)
    TGT_COLOR = (255, 0, 255)
    APEX_COLOR = (0, 255, 255)

    panels = []
    for (fr, x, y, tid, role) in frames:
        img = read_frame(video_path, fr)
        if img is None:
            print(f"  failed to read frame {fr}")
            return False

        # Draw wrists
        w = find_closest_wrist(wrist_frames, fr, max_diff=5)
        if w is not None:
            draw_hand_marker(img, w["left"], LEFT_COLOR, "L")
            draw_hand_marker(img, w["right"], RIGHT_COLOR, "R")

        # Draw ball
        if role == "src":
            draw_circle(img, x, y, SRC_COLOR, 8, 2)
            label = f"t{from_tid} f={fr}"
        elif role == "tgt":
            draw_circle(img, x, y, TGT_COLOR, 8, 2)
            label = f"t{to_tid} f={fr}"
        else:
            draw_circle(img, x, y, APEX_COLOR, 12, 3)
            label = f"APEX f={fr}"

        draw_text(img, 10, 28, label, color=(0, 0, 0), scale=0.7, thickness=2)
        draw_text(img, 10, img.shape[0] - 12,
                  f"{from_tid}->{to_tid} | {kind} | min_d={v_result['min_hand_dist']:.1f} ratio={v_result['ratio']:.2f}",
                  color=(0, 0, 0), scale=0.5, thickness=1)
        panels.append(img)

    if not panels:
        return False

    # Tile in 2x3 grid
    h, w = panels[0].shape[:2]
    n_cols = 3
    n_rows = 2
    sheet = np.zeros((h * n_rows, w * n_cols, 3), dtype=np.uint8)
    for i, p in enumerate(panels[:n_cols * n_rows]):
        r, c = divmod(i, n_cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = p

    # Title bar
    title_h = 30
    sheet_with_title = np.zeros((h * n_rows + title_h, w * n_cols, 3), dtype=np.uint8)
    sheet_with_title[title_h:, :, :] = sheet
    title = f"H17 {stem}: {from_tid}->{to_tid} [{kind}] hand={v_result['which_hand']} V={v_result['classification']}"
    draw_text(sheet_with_title, 10, title_h - 8, title, color=(255, 255, 255), scale=0.8, thickness=2)

    cv2.imwrite(str(out_path), sheet_with_title)
    return True


def main():
    H17_OUT.mkdir(parents=True, exist_ok=True)
    print(f"H17 contact sheets -> {H17_OUT}")

    # Load the strict v-shape positives
    strict_path = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data" / "h17_strict_v_shape_positives.csv"
    rows = []
    with strict_path.open() as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    print(f"Loaded {len(rows)} strict V-shape positives")

    # Group by stem and kind
    v4d_rows = [r for r in rows if r["kind"] == "v4d_rejected"]
    e6c_rows = [r for r in rows if r["kind"] == "e6c_not_in_h7v2"]
    adj_rows = [r for r in rows if r["kind"] == "adjacent"]
    print(f"  v4d_rejected: {len(v4d_rows)}")
    print(f"  e6c_not_in_h7v2: {len(e6c_rows)}")
    print(f"  adjacent: {len(adj_rows)}")

    # Render the v4d-rejected first (most important)
    for r in v4d_rows:
        stem = r["stem"]
        from_tid = int(r["from_tid"])
        to_tid = int(r["to_tid"])
        v_result = {
            "min_hand_dist": float(r["min_hand_dist"]),
            "max_hand_dist": 0,
            "ratio": float(r["ratio"]),
            "which_hand": r["which_hand"],
            "classification": r["vshape"],
            "apex": (float(r["apex_x"]), float(r["apex_y"]), int(r["apex_frame"]))
                if r["apex_frame"] else None,
        }
        out = H17_OUT / f"{stem}_v4drej_{from_tid}_to_{to_tid}.png"
        if render_contact_sheet(stem, from_tid, to_tid, "v4d_rejected", v_result, out):
            print(f"  rendered {out.name}")

    # Render a sample of e6c_not_in_h7v2 (the most informative subset)
    # Take 4 from each video to get visual coverage
    by_stem_e6c = {}
    for r in e6c_rows:
        by_stem_e6c.setdefault(r["stem"], []).append(r)
    for stem, rs in by_stem_e6c.items():
        # Take a representative sample: low err first, then some medium
        rs_sorted = sorted(rs, key=lambda x: float(x.get("min_hand_dist", 0)))
        sample = rs_sorted[:6]  # 6 most stringent (lowest min_d) per video
        for r in sample:
            from_tid = int(r["from_tid"])
            to_tid = int(r["to_tid"])
            v_result = {
                "min_hand_dist": float(r["min_hand_dist"]),
                "max_hand_dist": 0,
                "ratio": float(r["ratio"]),
                "which_hand": r["which_hand"],
                "classification": r["vshape"],
                "apex": (float(r["apex_x"]), float(r["apex_y"]), int(r["apex_frame"]))
                    if r["apex_frame"] else None,
            }
            out = H17_OUT / f"{stem}_e6cnot_{from_tid}_to_{to_tid}.png"
            if render_contact_sheet(stem, from_tid, to_tid, "e6c_not_in_h7v2", v_result, out):
                print(f"  rendered {out.name}")

    # Render a small sample of adjacent (most stringent: lowest min_d)
    by_stem_adj = {}
    for r in adj_rows:
        by_stem_adj.setdefault(r["stem"], []).append(r)
    for stem, rs in by_stem_adj.items():
        # Sort by min_d, take top 8 (most stringent)
        rs_sorted = sorted(rs, key=lambda x: float(x.get("min_hand_dist", 0)))
        sample = rs_sorted[:8]
        for r in sample:
            from_tid = int(r["from_tid"])
            to_tid = int(r["to_tid"])
            v_result = {
                "min_hand_dist": float(r["min_hand_dist"]),
                "max_hand_dist": 0,
                "ratio": float(r["ratio"]),
                "which_hand": r["which_hand"],
                "classification": r["vshape"],
                "apex": (float(r["apex_x"]), float(r["apex_y"]), int(r["apex_frame"]))
                    if r["apex_frame"] else None,
            }
            out = H17_OUT / f"{stem}_adj_{from_tid}_to_{to_tid}.png"
            if render_contact_sheet(stem, from_tid, to_tid, "adjacent", v_result, out):
                print(f"  rendered {out.name}")


if __name__ == "__main__":
    main()
