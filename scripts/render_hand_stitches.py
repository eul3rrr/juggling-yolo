#!/usr/bin/env python3
"""Simplified hand-only identity-flow diagnostic renderer."""
from __future__ import annotations

import argparse
import colorsys
import csv
import subprocess
from collections import defaultdict
from pathlib import Path

import cv2

import hand_overlay

TRAIL_LENGTH = 12
ANNOUNCEMENT_FRAMES = 25


def _pairs(rows):
    return [(int(r["source_track_id"]), int(r["target_track_id"])) for r in rows]


def derive_display_chains(links, track_ids):
    parent = {int(t): int(t) for t in track_ids}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    for a, b in links:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[rb] = ra
    roots = {}
    for t in sorted(parent):
        roots.setdefault(find(t), len(roots) + 1)
    return {t: roots[find(t)] for t in sorted(parent)}


def assign_display_ids(links, track_ids):
    return derive_display_chains(links, track_ids)


def display_colors(display_ids):
    ids = sorted(set(display_ids.values()))
    colors = {}
    for i, hid in enumerate(ids):
        r, g, b = colorsys.hsv_to_rgb(i / max(1, len(ids)), 0.78, 0.95)
        colors[hid] = (round(b * 255), round(g * 255), round(r * 255))
    return colors


def parse_pending(value):
    out = []
    for token in (value or "").split(";"):
        token = token.strip()
        if not token or not token.startswith("T") or ":{" not in token:
            continue
        tid, hands = token[1:].split(":", 1)
        try:
            out.append((int(tid), hands))
        except ValueError:
            continue
    return out


def parse_trace_pending(value):
    return parse_pending(value)


def index_associations(rows):
    return {(int(r["target_track_id"]), int(r["target_start_frame"])): r for r in rows}


def index_unmatched(rows):
    return {(int(r["track_id"]), int(r["boundary_frame"])): r for r in rows}


def status_for_unmatched(reason):
    return {
        "VIDEO_START_EXIT": "no predecessor: video start",
        "VIDEO_END_PENDING_ENTRY": "pending at video end",
        "UNRESOLVED_PENDING_ENTRY": "pending unresolved",
        "NO_COMPATIBLE_PENDING_SOURCE": "NO COMPATIBLE PENDING SOURCE",
        "EXPIRED_PENDING_SOURCE": "pending source expired",
    }.get(reason, reason)


def ffmpeg_command(width, height, fps, output: Path):
    return ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.6f}", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(output)]


def _load_association_data(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_trace(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _put(frame, text, xy, color=(240, 240, 240), scale=0.48, thickness=1):
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _hand_point(row, side):
    if row is None:
        return None
    return getattr(row, "left_wrist" if side == "LEFT" else "right_wrist")


def _draw_chip(frame, text, center, color):
    x, y = int(center[0]), int(center[1])
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1)
    cv2.rectangle(frame, (x - 6, y - th - 8), (x + tw + 8, y + 5), (15, 20, 28), -1)
    cv2.rectangle(frame, (x - 6, y - th - 8), (x + tw + 8, y + 5), color, 2)
    _put(frame, text, (x, y - 2), color, 0.46, 1)


def _draw_pending(frame, pending, pose, display_ids, colors):
    if not pending:
        return
    wrists = {"LEFT": _hand_point(pose, "LEFT"), "RIGHT": _hand_point(pose, "RIGHT")}
    for tid, hand_set in pending:
        hid = display_ids.get(tid, tid)
        color = colors.get(hid, (220, 220, 220))
        sides = [s for s in ("LEFT", "RIGHT") if s in hand_set]
        if len(sides) == 1 and wrists[sides[0]] is not None:
            p = wrists[sides[0]]
            _draw_chip(frame, f"{sides[0][0]}: pending HID{hid} (T{tid})", (p[0] + 14, p[1] - 20), color)
        else:
            valid = [wrists[s] for s in sides if wrists[s] is not None]
            if valid:
                center = (sum(p[0] for p in valid) / len(valid), min(p[1] for p in valid) - 38)
            else:
                center = (30, 115)
            _draw_chip(frame, f"AMB: pending HID{hid} (T{tid}) {hand_set}", center, color)


def _draw_pose(frame, pose):
    if pose is None:
        return
    for side, color in (("LEFT", (255, 170, 40)), ("RIGHT", (40, 180, 255))):
        wrist = _hand_point(pose, side)
        elbow = getattr(pose, side.lower() + "_elbow")
        if elbow is not None and wrist is not None:
            cv2.line(frame, (round(elbow[0]), round(elbow[1])), (round(wrist[0]), round(wrist[1])), color, 2, cv2.LINE_AA)
        if wrist is not None:
            cv2.circle(frame, (round(wrist[0]), round(wrist[1])), 7, color, -1, cv2.LINE_AA)
            _put(frame, "L" if side == "LEFT" else "R", (round(wrist[0]) + 10, round(wrist[1]) - 8), color, 0.62, 2)


def _draw_stitch_banner(frame, row, width):
    text = f"HAND STITCH   T{row['source_track_id']} -> T{row['target_track_id']}   {row['resolved_hand']}   {row['match_rule']}"
    cv2.rectangle(frame, (width - 570, 48), (width - 12, 84), (20, 70, 35), -1)
    _put(frame, text, (width - 555, 72), (150, 255, 170), 0.46, 2)


def _draw_status_banner(frame, text, width, color=(240, 210, 100)):
    cv2.rectangle(frame, (width - 570, 48), (width - 12, 84), (20, 25, 35), -1)
    _put(frame, text, (width - 555, 72), color, 0.46, 2)


def render(video_path, tracklets_path, hands_path, events_path, associations_path, trace_path, unmatched_path, output):
    associations = _load_association_data(associations_path)
    trace = _load_trace(trace_path)
    unmatched = _load_association_data(unmatched_path)
    track_rows = []
    by_frame = defaultdict(list)
    by_track = defaultdict(list)
    with tracklets_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("observed") != "1":
                continue
            item = (int(r["track_id"]), float(r["center_x"]), float(r["center_y"]))
            by_frame[int(r["frame"])].append(item)
            by_track[item[0]].append((int(r["frame"]), item[1], item[2]))
    track_ids = sorted(by_track)
    display_ids = assign_display_ids(_pairs(associations), track_ids)
    colors = display_colors(display_ids)
    assoc_lookup = index_associations(associations)
    unmatched_lookup = index_unmatched(unmatched)
    trace_by_frame = defaultdict(list)
    for r in trace:
        trace_by_frame[int(r["frame"])].append(r)
    hands = hand_overlay.load_hands_by_frame(hands_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(ffmpeg_command(width, height, fps, output), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    latest_pending = []
    latest_action = ""
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            current = by_frame.get(frame_index, [])
            pose = hands.get(frame_index, [None])[0]
            _draw_pose(frame, pose)
            for tid, x, y in current:
                points = [(fx, px, py) for fx, px, py in by_track[tid] if frame_index - TRAIL_LENGTH <= fx <= frame_index]
                points.sort()
                color = colors[display_ids[tid]]
                for a, b in zip(points, points[1:]):
                    cv2.line(frame, (round(a[1]), round(a[2])), (round(b[1]), round(b[2])), color, 3, cv2.LINE_AA)
                cv2.circle(frame, (round(x), round(y)), 9, color, -1, cv2.LINE_AA)
                _put(frame, f"HID{display_ids[tid]} / T{tid}", (round(x) + 12, round(y) - 9), color, 0.46, 2)
            rows_here = trace_by_frame.get(frame_index, [])
            if rows_here:
                latest_action = rows_here[-1]["action"]
                for tr in rows_here:
                    if tr.get("pending_after") is not None:
                        latest_pending = parse_trace_pending(tr.get("pending_after", ""))
            _draw_pending(frame, latest_pending, pose, display_ids, colors)
            stitch = assoc_lookup.get(next(((tid, frame_index) for tid, *_ in current), (-1, -1)))
            # A target can be announced even if its observation is not in the current frame map.
            target_rows = [r for (tid, fr), r in assoc_lookup.items() if fr <= frame_index < fr + ANNOUNCEMENT_FRAMES]
            if target_rows:
                _draw_stitch_banner(frame, target_rows[-1], width)
            unmatched_rows = [r for (tid, fr), r in unmatched_lookup.items() if fr <= frame_index < fr + ANNOUNCEMENT_FRAMES and r["event_type"] == "HAND_EXIT"]
            if unmatched_rows and not target_rows:
                r = unmatched_rows[-1]
                _draw_status_banner(frame, f"HAND EXIT T{r['track_id']}   {status_for_unmatched(r['reason'])}", width, (100, 190, 255))
            if any(r["event_type"] == "HAND_EXIT" and r["reason"] == "VIDEO_START_EXIT" for r in unmatched_lookup.values()) and frame_index <= 22:
                for r in unmatched:
                    if r["reason"] == "VIDEO_START_EXIT" and int(r["boundary_frame"]) == frame_index:
                        _draw_status_banner(frame, f"T{r['track_id']} starts near hand   no predecessor: video start", width, (210, 210, 150))
            if latest_pending and frame_index >= 1078 - 8:
                _draw_status_banner(frame, "pending at video end", width, (210, 210, 150))
            cv2.rectangle(frame, (0, 0), (width, 38), (15, 20, 28), -1)
            _put(frame, f"frame {frame_index}   {frame_index / fps:.3f}s   observed raw tracks: {len(current)}", (10, 25), (240, 240, 240), 0.52)
            cv2.rectangle(frame, (0, height - 34), (width, height), (15, 20, 28), -1)
            _put(frame, f"pending: {_pending_text_display(latest_pending, display_ids)}    last action: {latest_action}", (10, height - 12), (220, 220, 220), 0.40)
            process.stdin.write(frame.tobytes())
            frame_index += 1
    finally:
        cap.release()
        process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    if process.wait() != 0:
        raise RuntimeError(stderr[-2000:])
    return frame_index


def _pending_text_display(pending, display_ids):
    return ";".join(f"HID{display_ids.get(tid, tid)}:{hands}" for tid, hands in pending) or "none"


def main():
    p=argparse.ArgumentParser(); p.add_argument("--video",type=Path,required=True); p.add_argument("--tracklets",type=Path,required=True); p.add_argument("--hands",type=Path,required=True); p.add_argument("--events",type=Path,required=True); p.add_argument("--associations",type=Path,required=True); p.add_argument("--trace",type=Path,required=True); p.add_argument("--unmatched",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(); print(f"rendered frames: {render(a.video,a.tracklets,a.hands,a.events,a.associations,a.trace,a.unmatched,a.output)}"); print(f"output: {a.output}")


if __name__ == "__main__": main()
