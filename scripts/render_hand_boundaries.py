#!/usr/bin/env python3
"""Browser-compatible diagnostic renderer for independent hand boundaries."""
from __future__ import annotations

import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

import hand_overlay


STRONG_NORMALIZED = 0.35
POSSIBLE_NORMALIZED = 0.70
STRONG_RAW_PX = 60.0
POSSIBLE_RAW_PX = 130.0
BOUNDARY_CONTEXT = 15
TRAIL_LENGTH = 12


def nearest_hand(ball_xy, wrists):
    available = [(side, xy) for side, xy in wrists.items() if xy is not None]
    if not available:
        return None
    side, xy = min(available, key=lambda item: float(np.hypot(ball_xy[0] - item[1][0], ball_xy[1] - item[1][1])))
    return side, float(np.hypot(ball_xy[0] - xy[0], ball_xy[1] - xy[1]))


def proximity_radii(body_scale):
    if body_scale is not None and body_scale >= 5.0:
        return STRONG_NORMALIZED * body_scale, POSSIBLE_NORMALIZED * body_scale, "normalized"
    return STRONG_RAW_PX, POSSIBLE_RAW_PX, "raw"


def proximity_band(normalized_distance, raw_distance):
    if normalized_distance is not None:
        if normalized_distance <= STRONG_NORMALIZED:
            return "VERY_NEAR"
        if normalized_distance <= POSSIBLE_NORMALIZED:
            return "POSSIBLE"
        return "FAR"
    if raw_distance is not None and raw_distance <= STRONG_RAW_PX:
        return "VERY_NEAR"
    if raw_distance is not None and raw_distance <= POSSIBLE_RAW_PX:
        return "POSSIBLE"
    return "FAR"


def wrist_xy(value):
    return None if value is None else (float(value[0]), float(value[1]))


def load_observed_tracklets(path: Path):
    by_frame = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed") != "1":
                continue
            point = (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            by_frame[point[0]].append((int(row["track_id"]), point[1], point[2]))
    return by_frame


def load_assessments(path: Path):
    grouped = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["boundary_type"], int(row["track_id"]), int(row["boundary_frame"]))
            grouped[key][row["hand"]] = row
    return dict(grouped)


def index_boundary_events(assessments):
    event_keys = sorted(assessments)
    def lookup(frame):
        return [event for event in event_keys if abs(event[2] - frame) <= BOUNDARY_CONTEXT]
    return lookup


def verdict_text(row):
    if row.get("ambiguous") == "1":
        return "HAND: ambiguous L/R"
    return f"HAND: {'yes' if row.get('hand_evidence') == '1' else 'no'} ({row.get('evidence_reason', '')})"


def ffmpeg_command(width, height, fps, output: Path):
    return ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.6f}", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(output)]


def _pose_row(rows):
    if not rows:
        return None
    return rows[0]


def _put(frame, text, xy, color=(255, 255, 255), scale=0.48, thickness=1):
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _fmt_metric(row, prefix):
    px = row.get(prefix + "_distance_px", "")
    norm = row.get(prefix + "_distance_normalized", "")
    if not px:
        return "n/a"
    return f"{float(px):.0f}px" + (f" / {float(norm):.2f}sw" if norm else "")


def _draw_panel(frame, events, width, height):
    if not events:
        return
    lines = []
    for kind, tid, boundary_frame in events:
        rows = assessments_global[(kind, tid, boundary_frame)]
        left, right = rows.get("LEFT"), rows.get("RIGHT")
        if left is None or right is None:
            continue
        lines.append(f"{kind} T{tid} @{boundary_frame}")
        lines.append(f"LEFT  {left['proximity_band']:<9} {_fmt_metric(left, 'endpoint')}  {left['motion']}")
        lines.append(f"RIGHT {right['proximity_band']:<9} {_fmt_metric(right, 'endpoint')}  {right['motion']}")
        for side, row in (("L", left), ("R", right)):
            if row.get("recent_min_distance_px"):
                lines.append(f"recent min {side}: {_fmt_metric(row, 'recent_min')}")
        lines.append(verdict_text(left))
        if left.get("ambiguous") == "1":
            lines.append("preferred hand: none")
        elif left.get("preferred_hand"):
            lines.append(f"preferred: {left['preferred_hand']}")
        lines.append("")
    if not lines:
        return
    lines = lines[:22]
    panel_h = min(height - 45, 25 + 19 * len(lines))
    panel_w = min(width - 20, 490)
    x0, y0 = 10, height - panel_h - 10
    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, y0), (x0 + panel_w, y0 + panel_h), (12, 18, 28), -1)
    cv2.addWeighted(overlay, 0.86, frame, 0.14, 0, frame)
    y = y0 + 20
    for line in lines:
        _put(frame, line, (x0 + 10, y), (235, 240, 245), 0.43)
        y += 18


def render(video_path: Path, tracklets_path: Path, hands_path: Path, assessments_path: Path, output: Path):
    global assessments_global
    assessments_global = load_assessments(assessments_path)
    events_at = index_boundary_events(assessments_global)
    track_by_frame = load_observed_tracklets(tracklets_path)
    hands = hand_overlay.load_hands_by_frame(hands_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = ffmpeg_command(width, height, fps, output)
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            pose = _pose_row(hands.get(frame_index, []))
            wrists = {"LEFT": wrist_xy(pose.left_wrist) if pose else None,
                      "RIGHT": wrist_xy(pose.right_wrist) if pose else None}
            body_scale = pose.body_scale if pose else None
            inner, outer, radius_mode = proximity_radii(body_scale)
            # Pose skeleton: anatomical labels come from CSV columns, never x-position.
            if pose:
                segments = [(pose.left_shoulder, pose.left_elbow, (255, 170, 40)),
                            (pose.left_elbow, pose.left_wrist, (255, 170, 40)),
                            (pose.right_shoulder, pose.right_elbow, (40, 180, 255)),
                            (pose.right_elbow, pose.right_wrist, (40, 180, 255))]
                for a, b, color in segments:
                    if a is not None and b is not None:
                        cv2.line(frame, (round(a[0]), round(a[1])), (round(b[0]), round(b[1])), color, 2, cv2.LINE_AA)
                for side, color in (("LEFT", (255, 170, 40)), ("RIGHT", (40, 180, 255))):
                    xy = wrists[side]
                    if xy is None:
                        continue
                    c = (round(xy[0]), round(xy[1]))
                    cv2.circle(frame, c, round(outer), (color[0] // 3, color[1] // 3, color[2] // 3), 1, cv2.LINE_AA)
                    cv2.circle(frame, c, round(inner), color, 1, cv2.LINE_AA)
                    _put(frame, "L" if side == "LEFT" else "R", (c[0] + 8, c[1] - 8), color, 0.6, 2)
            current = track_by_frame.get(frame_index, [])
            for tid, x, y in current:
                trail = [(fx, px, py) for fx, points in track_by_frame.items() if frame_index - TRAIL_LENGTH <= fx <= frame_index
                         for track, px, py in points if track == tid]
                trail.sort()
                for a, b in zip(trail, trail[1:]):
                    cv2.line(frame, (round(a[1]), round(a[2])), (round(b[1]), round(b[2])), (220, 220, 220), 2, cv2.LINE_AA)
                ball = (round(x), round(y))
                nearest = nearest_hand((x, y), wrists)
                if nearest:
                    side, distance = nearest
                    xy = wrists[side]
                    norm = distance / body_scale if body_scale and body_scale >= 5 else None
                    band = proximity_band(norm, distance)
                    color = (0, 230, 255) if band == "VERY_NEAR" else (0, 165, 255) if band == "POSSIBLE" else (110, 110, 110)
                    cv2.line(frame, ball, (round(xy[0]), round(xy[1])), color, 4 if band == "VERY_NEAR" else 2, cv2.LINE_AA)
                    label = f"{'L' if side == 'LEFT' else 'R'} {distance:.0f}px" + (f" / {norm:.2f}sw" if norm is not None else "")
                    _put(frame, label, (ball[0] + 8, ball[1] + 18), color, 0.42, 1)
                cv2.circle(frame, ball, 8, (255, 255, 255), 2, cv2.LINE_AA)
                _put(frame, f"T{tid}", (ball[0] + 10, ball[1] - 8), (255, 255, 255), 0.5, 2)
            # Boundary marker and authoritative CSV panel.
            nearby = events_at(frame_index)
            exact = [e for e in nearby if e[2] == frame_index]
            for kind, tid, boundary_frame in exact:
                row = assessments_global[(kind, tid, boundary_frame)]["LEFT"]
                cv2.drawMarker(frame, (round(float(row["boundary_x"])), round(float(row["boundary_y"]))), (0, 0, 255), cv2.MARKER_CROSS, 22, 3)
                _put(frame, f"{kind} T{tid}", (round(float(row["boundary_x"])) + 12, round(float(row["boundary_y"])) + 28), (0, 0, 255), 0.65, 2)
            _draw_panel(frame, nearby, width, height)
            cv2.rectangle(frame, (0, 0), (width, 37), (15, 20, 28), -1)
            _put(frame, f"frame {frame_index}   {frame_index / fps:.3f}s   observed raw tracks: {len(current)}", (10, 25), (240, 240, 240), 0.52)
            legend = "T# raw tracklet | L/R anatomical | inner VERY_NEAR | outer POSSIBLE | line nearest hand | sw normalized"
            _put(frame, legend, (10, height - 12), (210, 210, 210), 0.38)
            process.stdin.write(frame.tobytes())
            frame_index += 1
    finally:
        cap.release()
        if process.stdin:
            process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed ({code}): {stderr[-2000:]}")
    return frame_index, cmd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--tracklets", type=Path, required=True)
    p.add_argument("--hands", type=Path, required=True)
    p.add_argument("--assessments", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    frames, _ = render(args.video, args.tracklets, args.hands, args.assessments, args.output)
    print(f"rendered frames: {frames}")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
