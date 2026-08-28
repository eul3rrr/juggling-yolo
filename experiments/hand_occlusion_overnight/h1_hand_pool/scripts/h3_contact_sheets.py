#!/usr/bin/env python3
"""H3 — Render contact sheets for v4d links that have stationary clusters.

For each v4d hand-link with at least one stationary cluster of low-conf
detections, render a contact sheet showing the from_frame, to_frame, and
the cluster frames. Each frame shows:
  - The wrist position (orange circle for L, blue for R)
  - Incoming tracklet (yellow)
  - Outgoing tracklet (magenta)
  - All sports-ball detections in the frame (cyan; low-conf = yellow)
  - Cluster frames highlighted in orange
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
SHIPPED = WORKTREE / "detections"
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS_H3 = H1_DIR / "contact_sheets_h3"
H1_CS_H3.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")

WRIST_CONF_MIN = 0.5
COLOR_LEFT = (255, 128, 64)     # orange (BGR)
COLOR_RIGHT = (64, 200, 255)    # blue (BGR)
COLOR_FROM = (0, 255, 255)      # yellow: from tracklet
COLOR_TO = (255, 0, 255)        # magenta: to tracklet
COLOR_SB = (255, 255, 0)        # yellow: sports ball (low conf)
COLOR_SB_HI = (0, 255, 0)       # green: sports ball (high conf)
COLOR_OTHER = (180, 180, 180)   # gray: other tracklets
COLOR_CLUSTER = (0, 165, 255)   # orange: cluster highlight
COLOR_TEXT = (255, 255, 255)


def load_tracklets(stem: str) -> dict[int, list]:
    out = defaultdict(list)
    path = SHIPPED / f"{stem}_norfair_dt50_hc5.csv"
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed") != "1":
                continue
            out[int(row["track_id"])].append((
                int(row["frame"]),
                float(row["center_x"]),
                float(row["center_y"]),
                float(row["confidence"]),
            ))
    for tid in out:
        out[tid].sort(key=lambda p: p[0])
    return dict(out)


def load_wrist_frames(stem: str) -> dict[int, dict]:
    out = {}
    path = SHIPPED / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            f = int(row["frame"])
            e = out.setdefault(f, {"left": None, "right": None})
            for side in ("left", "right"):
                x = row.get(f"{side}_wrist_x")
                y = row.get(f"{side}_wrist_y")
                c = row.get(f"{side}_wrist_confidence")
                if x is None or y is None or c is None:
                    continue
                c = float(c)
                if c < WRIST_CONF_MIN:
                    continue
                e[side] = (float(x), float(y), c)
    return out


def load_sb(stem: str) -> list:
    for suffix in ["_yolo26s_all-classes.csv", "_yolo26s_classes-32.csv"]:
        path = SHIPPED / f"{stem}{suffix}"
        if path.exists():
            break
    else:
        return []
    out = []
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            if "class_name" in r and r["class_name"] != "sports ball":
                continue
            try:
                out.append((int(r["frame"]), float(r["center_x"]),
                            float(r["center_y"]), float(r["confidence"])))
            except (ValueError, KeyError):
                continue
    return out


def load_norfair_index(stem: str) -> dict:
    out = {}
    path = SHIPPED / f"{stem}_norfair_dt50_hc5.csv"
    if not path.exists():
        return out
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                out[(int(r["frame"]),
                     round(float(r["center_x"])),
                     round(float(r["center_y"])))] = int(r["track_id"])
            except (ValueError, KeyError):
                continue
    return out


def find_tid(nf_index, fr, x, y, max_dist=4):
    for d in range(max_dist + 1):
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                k = (fr, round(x) + dx, round(y) + dy)
                if k in nf_index:
                    return nf_index[k]
    return None


def render_sheet(stem: str, link: dict, clusters: list, max_panels: int = 8):
    cap_path = VIDEOS_DIR / f"{stem}.mp4"
    if not cap_path.exists():
        print(f"  could not find video {cap_path}")
        return None
    cap = cv2.VideoCapture(str(cap_path))
    if not cap.isOpened():
        print(f"  could not open video {cap_path}")
        return None
    pose = load_wrist_frames(stem)
    sb = load_sb(stem)
    nf_index = load_norfair_index(stem)
    from_tid = link["from_tid"]
    to_tid = link["to_tid"]
    hand = link["hand"]

    # Pick frames: MUST include cluster frames (the held-ball phase)
    # then pad with from_frame, to_frame, and intermediate frames
    cluster_frames = []
    for cl in clusters:
        cluster_frames.extend(cl["frames"])
    # Cluster frames are the priority
    frames_to_show = sorted(set(cluster_frames))
    # Add from_frame and to_frame
    if link["from_frame"] not in frames_to_show:
        frames_to_show.append(link["from_frame"])
    if link["to_frame"] not in frames_to_show:
        frames_to_show.append(link["to_frame"])
    # If we have room, add intermediate frames between cluster and to_frame
    frames_to_show = sorted(set(frames_to_show))
    if len(frames_to_show) < max_panels:
        # Add 1-2 intermediate frames
        span = link["to_frame"] - link["from_frame"]
        for i in range(1, 4):
            mid = link["from_frame"] + (span * i // 4)
            if mid not in frames_to_show and len(frames_to_show) < max_panels:
                frames_to_show.append(mid)
    frames_to_show = sorted(set(frames_to_show))[:max_panels]

    cluster_set = set()
    for cl in clusters:
        cluster_set.update(cl["frames"])

    annotated = []
    for fr in frames_to_show:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, frame = cap.read()
        if not ok:
            continue
        # Wrist
        w_pose = pose.get(fr, {})
        if hand in w_pose and w_pose[hand] is not None:
            wx, wy, _ = w_pose[hand]
            color = COLOR_LEFT if hand == "left" else COLOR_RIGHT
            cv2.circle(frame, (int(wx), int(wy)), 14, color, 2)
        # All sports-ball detections
        sb_in_frame = [d for d in sb if d[0] == fr]
        for (sf, sx, sy, sc) in sb_in_frame:
            tid = find_tid(nf_index, sf, sx, sy)
            if tid == from_tid:
                color = COLOR_FROM
                thick = 2
            elif tid == to_tid:
                color = COLOR_TO
                thick = 2
            elif sc < 0.4:
                color = COLOR_SB
                thick = 1
            else:
                color = COLOR_SB_HI
                thick = 1
            cv2.circle(frame, (int(sx), int(sy)), 6, color, thick)
            if sc < 0.4:
                cv2.putText(frame, f"{sc:.2f}", (int(sx) + 8, int(sy) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
        # Cluster highlight
        if fr in cluster_set:
            for (sf, sx, sy, sc) in sb_in_frame:
                if sc < 0.4:
                    cv2.circle(frame, (int(sx), int(sy)), 14, COLOR_CLUSTER, 2)
        # Frame label
        label = f"f={fr}"
        if fr == link["from_frame"]:
            label += " (CATCH)"
        elif fr == link["to_frame"]:
            label += " (THROW)"
        elif fr in cluster_set:
            label += " (cluster)"
        cv2.rectangle(frame, (0, 0), (220, 30), (0, 0, 0), -1)
        cv2.putText(frame, label, (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 2)
        annotated.append(frame)

    cap.release()
    if not annotated:
        return None

    panel_h = annotated[0].shape[0]
    panel_w = annotated[0].shape[1]
    grid = np.zeros((panel_h, panel_w * len(annotated), 3), dtype=np.uint8)
    for i, fr in enumerate(annotated):
        grid[:, i * panel_w:(i + 1) * panel_w] = fr
    # Resize to 50% for compactness
    grid = cv2.resize(grid, (grid.shape[1] // 2, grid.shape[0] // 2))
    out_name = f"{stem}_link_{from_tid}_to_{to_tid}_{hand}_h3cluster.png"
    out_path = H1_CS_H3 / out_name
    cv2.imwrite(str(out_path), grid)
    return out_path


def main():
    with (H1_DATA / "h3_v3_summary.json").open() as fh:
        data = json.load(fh)

    for r in data["per_link"]:
        if r["n_stationary_clusters"] == 0:
            continue
        l = r["link"]
        link = {
            "stem": l["stem"],
            "from_tid": l["from_tid"],
            "to_tid": l["to_tid"],
            "hand": l["hand"],
            "from_frame": l["from_frame"],
            "to_frame": l["to_frame"],
        }
        out = render_sheet(l["stem"], link, r["stationary_clusters"])
        if out:
            print(f"  rendered: {out.name}")


if __name__ == "__main__":
    main()
