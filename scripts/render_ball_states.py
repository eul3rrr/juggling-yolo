#!/usr/bin/env python3
"""Review video for scripts/track_identities.py output.

Each ball keeps one colour and number for a whole segment:
  filled disc    detected position
  hollow ring    position predicted along a flight arc (no detection)
  square + L/R   held; drawn at the wrist when the ball itself is not detected
  HUD line       every ball's state, including hidden ones with no position
  grey cross     detections no identity took (unassigned or clutter)
Only frames inside the processed segments are written.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tracking.tracklets import load_observed_tracklets  # noqa: E402

PALETTE = [(60, 60, 255), (60, 220, 60), (255, 150, 40), (40, 220, 255),
           (255, 60, 220), (255, 255, 80), (150, 90, 255), (200, 200, 200)]
GREY = (150, 150, 150)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _text(image, text: str, origin: tuple[int, int], color, scale: float = 0.6) -> None:
    cv2.putText(image, text, origin, FONT, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(image, text, origin, FONT, scale, color, 1 if scale < 0.6 else 2, cv2.LINE_AA)


def load_states(path: Path, only: set[int] | None) -> dict[int, list[dict]]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if only and int(row["segment_index"]) not in only:
                continue
            by_frame[int(row["frame"])].append(row)
    return by_frame


def load_links(path: Path) -> dict[tuple[int, int], dict]:
    """Chosen links keyed by (segment, target track) so they can be shown on arrival."""
    with path.open(newline="", encoding="utf-8") as f:
        return {(int(r["segment_index"]), int(r["target_track_id"])): r for r in csv.DictReader(f)}


def load_dropped(path: Path) -> set[int]:
    with path.open(newline="", encoding="utf-8") as f:
        return {int(r["track_id"]) for r in csv.DictReader(f)}


def dropped_points(tracklets_csv: Path, dropped: set[int]) -> dict[int, list[tuple[float, float, int]]]:
    by_frame: dict[int, list[tuple[float, float, int]]] = defaultdict(list)
    for tid, tracklet in load_observed_tracklets(tracklets_csv).items():
        if tid in dropped:
            for frame, x, y in tracklet.points:
                by_frame[frame].append((x, y, tid))
    return by_frame


def draw_frame(image, rows: list[dict], frame: int, fps: float, scale: float,
               trails: dict, notes: dict, links: dict, crosses: list) -> None:
    def pt(x: float, y: float) -> tuple[int, int]:
        return int(round(x * scale)), int(round(y * scale))

    for x, y, tid in crosses:
        cx, cy = pt(x, y)
        cv2.drawMarker(image, (cx, cy), GREY, cv2.MARKER_TILTED_CROSS, 14, 2)
        _text(image, f"t{tid}", (cx + 9, cy - 9), GREY, 0.4)
    segment = rows[0]["segment_index"] if rows else ""
    _text(image, f"segment {segment}   frame {frame}   {frame / fps:.2f}s", (12, 26), (255, 255, 255))
    for row in sorted(rows, key=lambda r: int(r["ball_id"])):
        ball = int(row["ball_id"])
        key = (row["segment_index"], ball)
        color = PALETTE[(ball - 1) % len(PALETTE)]
        state, hand, source = row["state"], row["hand"], row["position_source"]
        label = {"AIRBORNE": "air", "HIDDEN": "HIDDEN"}.get(state, f"held {hand or '?'}")
        if source in ("predicted", "interpolated"):
            label += " (predicted)"
        _text(image, f"{ball}  {label}", (12, 26 + 26 * ball), color)
        if row["track_id"]:
            link = links.get((int(row["segment_index"]), int(row["track_id"])))
            if link and int(link["target_start_frame"]) == frame:
                notes[key] = (frame, f"{link['kind']} {link['hand']}".strip())
        if not row["x"]:
            trails[key].clear()
            continue
        center = pt(float(row["x"]), float(row["y"]))
        trail = trails[key]
        trail.append(center)
        for a, b in zip(trail, list(trail)[1:]):
            cv2.line(image, a, b, color, 2, cv2.LINE_AA)
        if source == "wrist":
            cv2.rectangle(image, (center[0] - 11, center[1] - 11), (center[0] + 11, center[1] + 11), color, 2)
        elif state == "HELD":
            cv2.circle(image, center, 9, color, -1, cv2.LINE_AA)
            cv2.rectangle(image, (center[0] - 14, center[1] - 14), (center[0] + 14, center[1] + 14), color, 2)
        elif source == "detection":
            cv2.circle(image, center, 10, color, -1, cv2.LINE_AA)
        else:
            cv2.circle(image, center, 12, color, 2, cv2.LINE_AA)
        tag = str(ball) + (f" {hand[0]}" if state == "HELD" and hand else "")
        _text(image, tag, (center[0] + 15, center[1] - 12), color, 0.7)
        note = notes.get(key)
        if note and frame - note[0] <= fps * 0.6:
            _text(image, note[1], (center[0] + 15, center[1] + 14), (255, 255, 255), 0.5)


def render(video: Path, states: dict[int, list[dict]], links: dict, crosses: dict,
           output: Path, max_height: int) -> int:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {video}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = min(1.0, max_height / height)
    size = (int(round(width * scale)) // 2 * 2, int(round(height * scale)) // 2 * 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    trails: dict = defaultdict(lambda: deque(maxlen=max(4, int(fps * 0.3))))
    notes: dict = {}
    frames = sorted(states)
    written, position = 0, -1
    for frame in frames:
        if frame != position + 1:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = capture.read()
        position = frame
        if not ok:
            break
        if scale != 1.0:
            image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        draw_frame(image, states[frame], frame, fps, scale, trails, notes, links, crosses.get(frame, []))
        writer.write(image)
        written += 1
    writer.release()
    capture.release()
    # mp4v does not play in browsers; re-encode to H.264 when ffmpeg is available.
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", str(output)], check=True)
        raw.unlink()
    else:
        raw.replace(output)
    return written


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--identity-dir", type=Path, required=True, help="output dir of track_identities.py")
    p.add_argument("--tracklets", type=Path, default=None, help="draw detections no identity took")
    p.add_argument("--only-segment", type=int, action="append", default=None)
    p.add_argument("--max-height", type=int, default=720)
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    only = set(args.only_segment) if args.only_segment else None
    states = load_states(args.identity_dir / "ball_states.csv", only)
    if not states:
        raise SystemExit("No ball states to render for that selection")
    links = load_links(args.identity_dir / "links.csv")
    crosses = {}
    if args.tracklets:
        crosses = dropped_points(args.tracklets, load_dropped(args.identity_dir / "dropped_tracklets.csv"))
    suffix = "" if not only else "_seg" + "-".join(str(i) for i in sorted(only))
    output = args.output or args.identity_dir / f"review{suffix}.mp4"
    written = render(args.video, states, links, crosses, output, args.max_height)
    print(f"Wrote {written} frames to {output}")


if __name__ == "__main__":
    main()
