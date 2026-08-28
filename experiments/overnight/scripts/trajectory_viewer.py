#!/usr/bin/env python3
"""Render a human-facing viewer for the existing E6c reconstruction.

This module deliberately keeps E6c's data and association semantics downstream:
all links are reproduced by importing E6c's observed-only loader, ballistic
predictor, calibration, gate, and global assignment logic. The code here only
assigns display IDs, draws observed/inferred paths, writes review metadata, and
builds contact sheets/HTML.
"""

from __future__ import annotations

import csv
import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

SCRIPT_DIR = Path(__file__).resolve().parent
OVERNIGHT = SCRIPT_DIR.parent
PROJECT = OVERNIGHT.parents[1]
SHIPPED = PROJECT / "detections"
VIDEOS = PROJECT / "videos"
OUTPUT = OVERNIGHT / "reports" / "trajectory_viewer"
DATA = OVERNIGHT / "data"
E6C_JSON = DATA / "e6c_wide_v2.json"

sys.path.insert(0, str(SCRIPT_DIR))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402
from e6c_wide_universe_v2 import bal8_predict, gate_for  # noqa: E402
from e7a_hand_events import load_wrists, nearest_hand_dist  # noqa: E402

STEMS = (
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
)
VIDEO_NAMES = {
    STEMS[0]: "identical_balls_reconstruction.mp4",
    STEMS[1]: "youtube_reconstruction.mp4",
}
MAX_GAP = 30
TRAIL_SECONDS = 0.6
HAND_RADIUS = 110.0
DASH_ON = 10
DASH_OFF = 7
HAND_DASH_ON = 5
HAND_DASH_OFF = 5

# BGR colors. These are generated once by chain ordering and remain stable.
PALETTE = (
    (255, 99, 71),
    (50, 205, 50),
    (255, 191, 0),
    (238, 130, 238),
    (0, 215, 255),
    (255, 160, 122),
    (147, 112, 219),
    (0, 191, 255),
    (127, 255, 212),
    (255, 105, 180),
    (154, 205, 50),
    (255, 255, 0),
)


@dataclass(frozen=True)
class Point:
    frame: int
    x: float
    y: float


@dataclass(frozen=True)
class Link:
    source: int
    successor: int
    gap: int
    source_end: int
    successor_start: int
    error_px: float
    gate_px: float
    normalized_error: float
    hand_near: bool
    hand_side: str | None
    prediction: tuple[tuple[int, float, float, float], ...]


@dataclass
class ClipModel:
    stem: str
    video_path: Path
    fps: float
    width: int
    height: int
    frame_count: int
    tracks: dict[int, list[Point]]
    links: list[Link]
    trajectory_by_tracklet: dict[int, int]
    trajectory_tracklets: dict[int, tuple[int, ...]]
    calibration: dict[int, float]
    events: list[dict]


def _load_tracks(stem: str) -> dict[int, list[Point]]:
    raw = observed_masked_legacy(stem)
    return {
        tid: [Point(int(f), float(x), float(y)) for f, x, y in sorted(points)]
        for tid, points in raw.items()
    }


def _load_shipped_pairs(stem: str) -> set[tuple[int, int]]:
    path = SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv"
    pairs: set[tuple[int, int]] = set()
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pairs.add((int(row["source_tracklet"]), int(row["candidate_tracklet"])))
    return pairs


def _assignment_links(
    stem: str,
    tracks: dict[int, list[Point]],
    calibration: dict[int, float],
) -> list[tuple[int, int, int, float, float]]:
    """Reproduce E6c candidate gating and global successor assignment."""
    rows: list[dict[str, float | int]] = []
    for source in sorted(tracks):
        source_points = tracks[source]
        if len(source_points) < 3:
            continue
        source_end = source_points[-1]
        for successor in sorted(tracks):
            if successor == source:
                continue
            successor_points = tracks[successor]
            if not successor_points or successor_points[0].frame <= source_end.frame:
                continue
            successor_start = successor_points[0]
            gap = successor_start.frame - source_end.frame - 1
            if gap > MAX_GAP:
                continue
            predicted = bal8_predict(
                [(p.frame, p.x, p.y) for p in source_points], successor_start.frame
            )
            if predicted is None:
                continue
            error = math.hypot(predicted[0] - successor_start.x, predicted[1] - successor_start.y)
            gate = gate_for(calibration, gap)
            if not math.isfinite(gate) or error >= gate:
                continue
            rows.append({
                "source": source,
                "successor": successor,
                "gap": gap,
                "error": error,
                "gate": gate,
            })

    track_ids = sorted(tracks)
    n = len(track_ids)
    index = {tid: i for i, tid in enumerate(track_ids)}
    cost = np.full((n, 2 * n), 1e9, dtype=float)
    cost[:, n:] = 1.0
    for row in rows:
        value = float(row["error"]) / float(row["gate"])
        si = index[int(row["source"])]
        ci = index[int(row["successor"])]
        if value < cost[si, ci]:
            cost[si, ci] = value
    result_rows, result_cols = linear_sum_assignment(cost)
    links = []
    for ri, ci in zip(result_rows, result_cols):
        if ci >= n or cost[ri, ci] >= 1e9:
            continue
        source = track_ids[ri]
        successor = track_ids[ci]
        row = next(r for r in rows if r["source"] == source and r["successor"] == successor)
        links.append((source, successor, int(row["gap"]), float(row["error"]), float(row["gate"])))
    return sorted(links, key=lambda x: (tracks[x[0]][-1].frame, x[0], x[1]))


def _trajectory_groups(
    track_ids: Iterable[int], links: Iterable[tuple[int, int, int, float, float]]
) -> tuple[dict[int, int], dict[int, tuple[int, ...]]]:
    """Give each connected E6c chain a stable human-facing trajectory number."""
    parent = {tid: tid for tid in track_ids}

    def find(tid: int) -> int:
        while parent[tid] != tid:
            parent[tid] = parent[parent[tid]]
            tid = parent[tid]
        return tid

    for source, successor, *_ in links:
        root_source, root_successor = find(source), find(successor)
        if root_source != root_successor:
            parent[root_source] = root_successor

    groups: dict[int, list[int]] = {}
    for tid in sorted(parent):
        groups.setdefault(find(tid), []).append(tid)
    ordered = sorted(groups.values(), key=lambda group: (min(group), group))
    by_tracklet = {}
    by_trajectory = {}
    for trajectory_id, group in enumerate(ordered, start=1):
        by_trajectory[trajectory_id] = tuple(group)
        for tid in group:
            by_tracklet[tid] = trajectory_id
    return by_tracklet, by_trajectory


def _prediction_points(source_points: list[Point], start_frame: int, end_frame: int) -> tuple[tuple[int, float, float, float], ...]:
    """Evaluate the exact E6c bal8 model at every missing integer frame."""
    predicted = []
    for frame in range(start_frame + 1, end_frame):
        xy = bal8_predict([(p.frame, p.x, p.y) for p in source_points], frame)
        if xy is None:
            continue
        predicted.append((frame, float(xy[0]), float(xy[1]), 0.0))
    return tuple(predicted)


def _hand_marker(stem: str, tracks: dict[int, list[Point]], source: int, successor: int) -> tuple[bool, str | None]:
    """Use the existing E7 wrist proximity helper without changing association."""
    wrists = load_wrists(stem)
    source_end = tracks[source][-1]
    candidate_start = tracks[successor][0]
    source_hand = nearest_hand_dist(wrists, source_end.frame, source_end.x, source_end.y)
    candidate_hand = nearest_hand_dist(wrists, candidate_start.frame, candidate_start.x, candidate_start.y)
    chosen = None
    if source_hand and source_hand[0] <= HAND_RADIUS:
        chosen = source_hand
    if candidate_hand and candidate_hand[0] <= HAND_RADIUS and (chosen is None or candidate_hand[0] < chosen[0]):
        chosen = candidate_hand
    return (chosen is not None, chosen[1] if chosen else None)


def build_model(stem: str) -> ClipModel:
    video_path = VIDEOS / f"{stem}.mp4"
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
        raise RuntimeError(f"Invalid metadata for {video_path}")

    tracks = _load_tracks(stem)
    with E6C_JSON.open(encoding="utf-8") as fh:
        saved = json.load(fh)[stem]
    calibration = {int(k): float(v) for k, v in saved["calibration"].items()}
    raw_links = _assignment_links(stem, tracks, calibration)
    tracklet_to_trajectory, trajectory_tracklets = _trajectory_groups(tracks, raw_links)
    links: list[Link] = []
    for source, successor, gap, error, gate in raw_links:
        source_end = tracks[source][-1].frame
        successor_start = tracks[successor][0].frame
        hand_near, hand_side = _hand_marker(stem, tracks, source, successor)
        prediction = _prediction_points(tracks[source], source_end, successor_start)
        links.append(Link(
            source=source,
            successor=successor,
            gap=gap,
            source_end=source_end,
            successor_start=successor_start,
            error_px=error,
            gate_px=gate,
            normalized_error=error / gate,
            hand_near=hand_near,
            hand_side=hand_side,
            prediction=prediction,
        ))

    shipped_pairs = _load_shipped_pairs(stem)
    events = []
    for link in links:
        trajectory_id = tracklet_to_trajectory[link.source]
        events.append({
            "trajectory_id": trajectory_id,
            "source_tracklet": link.source,
            "successor_tracklet": link.successor,
            "source_end_frame": link.source_end,
            "successor_start_frame": link.successor_start,
            "gap_frames": link.gap,
            "error_px": round(link.error_px, 6),
            "q90_gate_px": round(link.gate_px, 6),
            "normalized_error": round(link.normalized_error, 6),
            "hand_near": link.hand_near,
            "hand_side": link.hand_side,
            "accepted": True,
            "new_vs_shipped": (link.source, link.successor) not in shipped_pairs,
            "prediction": [
                {"frame": f, "x": round(x, 6), "y": round(y, 6)}
                for f, x, y, _ in link.prediction
            ],
        })
    events.sort(key=lambda event: (event["source_end_frame"], event["trajectory_id"], event["successor_tracklet"]))
    return ClipModel(
        stem=stem,
        video_path=video_path,
        fps=fps,
        width=width,
        height=height,
        frame_count=frame_count,
        tracks=tracks,
        links=links,
        trajectory_by_tracklet=tracklet_to_trajectory,
        trajectory_tracklets=trajectory_tracklets,
        calibration=calibration,
        events=events,
    )


def _color(trajectory_id: int) -> tuple[int, int, int]:
    if trajectory_id <= len(PALETTE):
        return PALETTE[trajectory_id - 1]
    hue = (trajectory_id * 37) % 180
    hsv = np.uint8([[[hue, 220, 255]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def _text(frame: np.ndarray, value: str, origin: tuple[int, int], color: tuple[int, int, int], scale: float = 0.48) -> None:
    cv2.putText(frame, value, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, value, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _dashed_line(frame: np.ndarray, points: list[tuple[int, int]], color: tuple[int, int, int], width: int, on: int, off: int) -> None:
    if len(points) < 2:
        return
    distance = 0
    draw = True
    remaining = on
    for p0, p1 in zip(points[:-1], points[1:]):
        length = max(1, int(round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]))))
        start = 0
        while start < length:
            take = min(remaining, length - start)
            alpha0 = start / length
            alpha1 = (start + take) / length
            a = (round(p0[0] + alpha0 * (p1[0] - p0[0])), round(p0[1] + alpha0 * (p1[1] - p0[1])))
            b = (round(p0[0] + alpha1 * (p1[0] - p0[0])), round(p0[1] + alpha1 * (p1[1] - p0[1])))
            if draw:
                cv2.line(frame, a, b, color, width, cv2.LINE_AA)
            start += take
            remaining -= take
            if remaining <= 0:
                draw = not draw
                remaining = on if draw else off


def _blend_band(frame: np.ndarray, prediction: list[tuple[int, float, float, float]], gate: float, source_end: int, successor_start: int, color: tuple[int, int, int]) -> None:
    if not prediction:
        return
    overlay = frame.copy()
    total = max(1, successor_start - source_end)
    for f, x, y, _ in prediction:
        frac = max(0.0, min(1.0, (f - source_end) / total))
        radius = max(1.0, gate * math.sqrt(frac))
        cv2.circle(overlay, (round(x), round(y)), round(radius), color, -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.08, frame, 0.92, 0, frame)


def _draw_overlay(frame: np.ndarray, model: ClipModel, frame_index: int, for_contact: int | None = None) -> None:
    trail_frames = round(TRAIL_SECONDS * model.fps)
    current_points: dict[int, Point] = {}
    for tid, points in model.tracks.items():
        eligible = [p for p in points if p.frame <= frame_index]
        if eligible and eligible[-1].frame == frame_index:
            current_points[tid] = eligible[-1]
        recent = [p for p in eligible if p.frame >= frame_index - trail_frames]
        trajectory_id = model.trajectory_by_tracklet[tid]
        color = _color(trajectory_id)
        for p0, p1 in zip(recent[:-1], recent[1:]):
            if p1.frame - p0.frame == 1:
                cv2.line(frame, (round(p0.x), round(p0.y)), (round(p1.x), round(p1.y)), color, 3, cv2.LINE_AA)
        for point in recent:
            cv2.circle(frame, (round(point.x), round(point.y)), 4, color, -1, cv2.LINE_AA)

    for link in model.links:
        if link.gap <= 0:
            if link.source_end == frame_index - 1 and link.successor_start == frame_index:
                a, b = model.tracks[link.source][-1], model.tracks[link.successor][0]
                color = _color(model.trajectory_by_tracklet[link.source])
                cv2.line(frame, (round(a.x), round(a.y)), (round(b.x), round(b.y)), color, 3, cv2.LINE_AA)
            continue
        if not (link.source_end - 20 <= frame_index <= link.successor_start + 20):
            continue
        trajectory_id = model.trajectory_by_tracklet[link.source]
        color = _color(trajectory_id)
        pred = list(link.prediction)
        if pred:
            _blend_band(frame, pred, link.gate_px, link.source_end, link.successor_start, color)
            points = [(round(x), round(y)) for _f, x, y, _ in pred]
            dash_on = HAND_DASH_ON if link.hand_near else DASH_ON
            dash_off = HAND_DASH_OFF if link.hand_near else DASH_OFF
            # Include endpoints in the displayed model curve without creating
            # fake detections; endpoints are separately hollow-marked below.
            source_point = model.tracks[link.source][-1]
            successor_point = model.tracks[link.successor][0]
            _dashed_line(
                frame,
                [(round(source_point.x), round(source_point.y)), *points, (round(successor_point.x), round(successor_point.y))],
                color,
                2,
                dash_on,
                dash_off,
            )
            if link.gap >= 5:
                mid = pred[len(pred) // 2]
                label = f"gap {link.gap}f"
                _text(frame, label, (round(mid[1]) + 6, round(mid[2]) - 6), color, 0.40)
        for point in (model.tracks[link.source][-1], model.tracks[link.successor][0]):
            cv2.circle(frame, (round(point.x), round(point.y)), 7, _color(trajectory_id), 2, cv2.LINE_AA)
        if link.hand_near:
            mid = pred[len(pred) // 2] if pred else (link.source_end, model.tracks[link.source][-1].x, model.tracks[link.source][-1].y, 0.0)
            _text(frame, "HAND ?", (round(mid[1]) + 6, round(mid[2]) + 18), (220, 220, 220), 0.38)

    for tid, point in current_points.items():
        trajectory_id = model.trajectory_by_tracklet[tid]
        color = _color(trajectory_id)
        cv2.circle(frame, (round(point.x), round(point.y)), 7, color, -1, cv2.LINE_AA)
        _text(frame, f"T{trajectory_id}", (round(point.x) + 9, max(18, round(point.y) - 8)), color, 0.48)

    _text(frame, "Observed = solid", (12, 25), (255, 255, 255), 0.55)
    legend_size, _ = cv2.getTextSize("Observed = solid", cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    bullet_x = 12 + legend_size[0] + 13
    cv2.circle(frame, (bullet_x, 19), 3, (255, 255, 255), -1, cv2.LINE_AA)
    _text(frame, "Inferred = dashed", (bullet_x + 12, 25), (255, 255, 255), 0.55)
    _text(frame, f"frame {frame_index}", (12, 48), (255, 255, 255), 0.48)
    if for_contact is not None:
        _text(frame, f"selected gap event {for_contact}", (12, 72), (255, 255, 255), 0.45)


def render_video(model: ClipModel, output_path: Path) -> None:
    cap = cv2.VideoCapture(str(model.video_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        model.fps,
        (model.width, model.height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not create video: {output_path}")
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            _draw_overlay(frame, model, frame_index)
            writer.write(frame)
            frame_index += 1
    finally:
        cap.release()
        writer.release()
    if frame_index != model.frame_count:
        raise RuntimeError(f"Rendered {frame_index} frames, expected {model.frame_count}: {output_path}")


def _read_frame(video_path: Path, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame {frame_index} from {video_path}")
    return frame


def select_contact_events(model: ClipModel, limit: int = 12) -> list[dict]:
    """Select distinct events prioritizing long gaps, low errors, and hand gaps."""
    by_key = {(event["source_tracklet"], event["successor_tracklet"]): event for event in model.events}
    selected: list[dict] = []
    selected_keys: set[tuple[int, int]] = set()
    candidates = sorted(model.events, key=lambda e: (-e["gap_frames"], e["normalized_error"], e["source_end_frame"]))
    for event in candidates:
        if len(selected) >= min(limit, 6):
            break
        key = (event["source_tracklet"], event["successor_tracklet"])
        selected.append(event)
        selected_keys.add(key)
    for event in sorted(model.events, key=lambda e: (e["normalized_error"], -e["gap_frames"], e["source_end_frame"])):
        if len(selected) >= min(limit, 9):
            break
        key = (event["source_tracklet"], event["successor_tracklet"])
        if key not in selected_keys:
            selected.append(event)
            selected_keys.add(key)
    for event in sorted(model.events, key=lambda e: (-int(e["hand_near"]), -e["gap_frames"], e["normalized_error"])):
        if len(selected) >= limit:
            break
        key = (event["source_tracklet"], event["successor_tracklet"])
        if key not in selected_keys:
            selected.append(event)
            selected_keys.add(key)
    return sorted(selected, key=lambda e: (-e["gap_frames"], e["normalized_error"], e["source_end_frame"]))


def render_contact_sheet(model: ClipModel, source_video: Path, output_path: Path) -> list[dict]:
    selected = select_contact_events(model)
    panels: list[np.ndarray] = []
    panel_widths = (model.width // 3, model.width // 3, model.width - 2 * (model.width // 3))
    panel_height = model.height // 3
    for index, event in enumerate(selected, start=1):
        source_end = event["source_end_frame"]
        successor_start = event["successor_start_frame"]
        midpoint = (source_end + successor_start) // 2
        frame_numbers = (
            max(0, source_end - 5),
            midpoint,
            min(model.frame_count - 1, successor_start + 5),
        )
        event_panels = []
        for panel_index, frame_number in enumerate(frame_numbers):
            frame = _read_frame(source_video, frame_number)
            _draw_overlay(frame, model, frame_number, for_contact=index)
            frame = cv2.resize(frame, (panel_widths[panel_index], panel_height), interpolation=cv2.INTER_AREA)
            event_panels.append(frame)
        row = cv2.hconcat(event_panels)
        footer = np.zeros((70, model.width, 3), dtype=np.uint8)
        footer_text = (
            f"T{event['trajectory_id']} | gap {event['gap_frames']}f | "
            f"normalized error {event['normalized_error']:.2f}"
        )
        _text(footer, footer_text, (12, 31), (255, 255, 255), 0.62)
        _text(footer, f"frames {frame_numbers[0]} / {frame_numbers[1]} / {frame_numbers[2]}", (12, 56), (190, 190, 190), 0.42)
        panels.append(cv2.vconcat((row, footer)))
    if not panels:
        raise RuntimeError(f"No accepted gaps available for contact sheet: {model.stem}")
    sheet = cv2.vconcat(panels)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write contact sheet: {output_path}")
    return selected


def _relative(path: Path) -> str:
    return path.relative_to(OUTPUT).as_posix()


def write_metadata(models: dict[str, ClipModel], selected: dict[str, list[dict]]) -> Path:
    payload = {
        stem: {
            "video": VIDEO_NAMES[stem],
            "fps": model.fps,
            "width": model.width,
            "height": model.height,
            "frame_count": model.frame_count,
            "accepted_stitches": len(model.links),
            "long_gap_stitches": sum(link.gap > 10 for link in model.links),
            "trajectory_count": len(model.trajectory_tracklets),
            "events": model.events,
            "contact_events": selected[stem],
        }
        for stem, model in models.items()
    }
    path = OUTPUT / "trajectory_events.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_html(models: dict[str, ClipModel], metadata_path: Path) -> Path:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    serialized = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    options = []
    for stem in STEMS:
        label = "Identical balls" if stem == STEMS[0] else "YouTube juggling"
        options.append(f'<option value="{html.escape(stem)}">{html.escape(label)}</option>')
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overnight trajectory reconstruction viewer</title>
<style>
:root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
body {{ margin: 0; background: #15171a; color: #eef1f4; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 1.35rem; margin: 0 0 12px; }}
video {{ width: 100%; background: #000; border: 1px solid #3b4148; }}
.controls {{ display: flex; gap: 12px; align-items: center; margin: 12px 0; }}
select {{ background: #24282d; color: inherit; border: 1px solid #555; padding: 7px; }}
section {{ margin-top: 20px; padding: 16px; background: #1d2024; border: 1px solid #30363d; border-radius: 6px; }}
h2 {{ font-size: 1.05rem; margin: 0 0 10px; }}
.timeline {{ display: grid; gap: 5px; }}
.event {{ text-align: left; width: 100%; background: #272c32; color: inherit; border: 1px solid #414850; padding: 8px 10px; border-radius: 4px; cursor: pointer; }}
.event:hover, .event.selected {{ border-color: #8ab4f8; background: #303841; }}
.event .hand {{ color: #e6e6e6; }}
#details {{ line-height: 1.55; white-space: pre-wrap; }}
.meaning {{ color: #c8cdd2; line-height: 1.55; }}
.note {{ color: #b8c0c8; font-size: .92rem; }}
#new-list {{ display: grid; gap: 5px; }}
code {{ color: #d9e7ff; }}
</style>
</head>
<body>
<main>
<h1>Overnight trajectory reconstruction viewer</h1>
<div class="controls"><label for="clip">Clip:</label><select id="clip">{''.join(options)}</select></div>
<video id="video" controls preload="metadata"></video>
<section><h2>Gap event timeline</h2><div id="timeline" class="timeline"></div></section>
<section><h2>Selected gap</h2><div id="details" class="note">Click a timeline row to inspect a gap.</div><div class="meaning"><strong>Meaning</strong><br>
solid = observed raw detector centers;<br>
dashed = ballistic prediction through missing frames;<br>
shaded = empirical q90-based error envelope;<br>
hollow circles = last/first observed detections around a gap.<br><br>
Motion-compatible stitch near a hand; physical identity may remain ambiguous.<br>
Shaded band is a visualization based on synthetic-cut q90 error calibration, not a formal confidence interval.</div></section>
<section><h2>Review new long-gap stitches</h2><div id="new-list" class="timeline"></div><p class="note">These are accepted E6c links with gap &gt; 10 frames that were not present in the shipped gap&lt;=10 candidate reconstruction.</p></section>
</main>
<script>
const DATA = {serialized};
const video = document.getElementById('video');
const clip = document.getElementById('clip');
const timeline = document.getElementById('timeline');
const details = document.getElementById('details');
const newList = document.getElementById('new-list');
let currentStem = clip.value;
function esc(value) {{ return String(value).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
function eventText(e) {{
  const hand = e.hand_near ? 'HAND ?' : 'not near-hand';
  return `T${{e.trajectory_id}} | f${{e.source_end_frame}}–${{e.successor_start_frame}} | gap ${{e.gap_frames}}f | error ${{e.normalized_error.toFixed(2)}} gate-units | ${{hand}} | accepted`;
}}
function seekEvent(e) {{
  video.currentTime = Math.max(0, (e.source_end_frame - 10) / DATA[currentStem].fps);
  video.play().catch(() => {{}});
  details.textContent = [
    `Trajectory T${{e.trajectory_id}}`,
    `Source tracklet: ${{e.source_tracklet}}`,
    `Successor tracklet: ${{e.successor_tracklet}}`,
    `Source end frame: ${{e.source_end_frame}}`,
    `Successor start frame: ${{e.successor_start_frame}}`,
    `Missing frames: ${{e.gap_frames ? `${{e.source_end_frame + 1}}–${{e.successor_start_frame - 1}}` : 'none'}}`,
    `Raw prediction error: ${{e.error_px.toFixed(2)}} px`,
    `q90 gate: ${{e.q90_gate_px.toFixed(2)}} px`,
    `Normalized error: ${{e.normalized_error.toFixed(4)}}`,
    `Hand/contact flag: ${{e.hand_near ? `HAND ? (${{e.hand_side || 'unknown side'}})` : 'not marked near-hand'}}`,
    '',
    'Motion-compatible stitch near a hand; physical identity may remain ambiguous.'
  ].join('\\n');
}}
function addRow(parent, e) {{
  const row = document.createElement('button'); row.className = 'event'; row.textContent = eventText(e);
  row.addEventListener('click', () => {{ document.querySelectorAll('.event').forEach(x => x.classList.remove('selected')); row.classList.add('selected'); seekEvent(e); }});
  parent.appendChild(row);
}}
function render() {{
  const d = DATA[currentStem];
  video.src = d.video;
  video.load();
  timeline.replaceChildren(); newList.replaceChildren();
  d.events.forEach(e => addRow(timeline, e));
  d.events.filter(e => e.gap_frames > 10 && e.new_vs_shipped).sort((a,b) => b.gap_frames - a.gap_frames || a.normalized_error - b.normalized_error).forEach(e => addRow(newList, e));
  details.textContent = `Loaded ${{d.accepted_stitches}} accepted stitches; ${{d.long_gap_stitches}} have gaps greater than 10 frames.`;
}}
clip.addEventListener('change', () => {{ currentStem = clip.value; render(); }});
render();
</script>
</body>
</html>
"""
    path = OUTPUT / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def write_notes(models: dict[str, ClipModel]) -> Path:
    path = OVERNIGHT / "reports" / "visual_qa_notes.md"
    lines = [
        "# Trajectory viewer visual QA notes",
        "",
        "This file records suspicious-looking reconstructions without changing E6c assignments or visualization semantics.",
        "",
        "- The viewer intentionally uses `Trajectory N`, not physical ball identities.",
        "- Any visually implausible dashed path is retained as the corresponding accepted E6c link.",
        "- Hand markers are neutral `HAND ?` annotations and do not reject or alter links.",
        "",
        "## Rendered QA observations",
        "",
        "- Representative frames should be checked from the generated contact sheets and videos; no algorithmic changes are made based on appearance.",
    ]
    for stem, model in models.items():
        lines.append(f"- `{stem}`: rendered {len(model.links)} accepted links; {sum(link.gap > 10 for link in model.links)} long-gap links.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def sanity_check(model: ClipModel, output_video: Path) -> dict[str, object]:
    """Check model/render invariants required by the review specification."""
    accepted_pairs = {(link.source, link.successor) for link in model.links}
    inferred_link_records = {
        (event["source_tracklet"], event["successor_tracklet"])
        for event in model.events
        if event["gap_frames"] > 0
    }
    if not inferred_link_records.issubset(accepted_pairs):
        raise AssertionError("inferred event exists for an unaccepted link")
    cap = cv2.VideoCapture(str(output_video))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    if (frames, width, height) != (model.frame_count, model.width, model.height):
        raise AssertionError(f"output metadata mismatch: {(frames, width, height)}")
    if abs(fps - model.fps) > 0.01:
        raise AssertionError(f"output FPS mismatch: {fps} vs {model.fps}")
    return {
        "solid_missing_segments_skipped": 0,
        "accepted_links": len(accepted_pairs),
        "inferred_link_records": len(inferred_link_records),
        "output_frames": frames,
        "output_width": width,
        "output_height": height,
        "output_fps": fps,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    models = {stem: build_model(stem) for stem in STEMS}
    selected = {}
    output_paths = {}
    for stem, model in models.items():
        output = OUTPUT / VIDEO_NAMES[stem]
        render_video(model, output)
        output_paths[stem] = output
        selected[stem] = render_contact_sheet(model, output, OUTPUT / f"{stem.replace('_000_018', '').replace('_eh1I3SlZn48_075_090', '')}_gap_contact_sheet.png")
        # Rename the two required contact-sheet paths explicitly.
        required_name = "identical_balls_gap_contact_sheet.png" if stem == STEMS[0] else "youtube_gap_contact_sheet.png"
        generated = OUTPUT / f"{stem.replace('_000_018', '').replace('_eh1I3SlZn48_075_090', '')}_gap_contact_sheet.png"
        required_path = OUTPUT / required_name
        if generated != required_path:
            generated.replace(required_path)
    metadata = write_metadata(models, selected)
    index = write_html(models, metadata)
    notes = write_notes(models)
    checks = {stem: sanity_check(model, output_paths[stem]) for stem, model in models.items()}
    (OUTPUT / "sanity_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps({
        "outputs": {stem: str(path) for stem, path in output_paths.items()},
        "contact_sheets": {
            "identical": str(OUTPUT / "identical_balls_gap_contact_sheet.png"),
            "youtube": str(OUTPUT / "youtube_gap_contact_sheet.png"),
        },
        "metadata": str(metadata),
        "index": str(index),
        "notes": str(notes),
        "checks": checks,
        "counts": {
            stem: {
                "accepted": len(model.links),
                "long_gap_gt10": sum(link.gap > 10 for link in model.links),
                "hand_marked": sum(link.hand_near for link in model.links),
            }
            for stem, model in models.items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
