#!/usr/bin/env python3
"""H1 contact-sheet generator.

For each hand event, render a 6-frame contact sheet:
  frame-12, frame-6, frame-2, frame (event), frame+3, frame+10
overlaid with:
  - left/right wrist (from yolo26s-pose)
  - the relevant tracklet (the one involved in the event) drawn up to event
  - preceding tracklet (if any) showing approach
  - following tracklet (if any) showing divergence
  - colored event label, hand-pool depth

Saves a grid of contact sheets (one per event) to:
  experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets/

Then prints events to inspect.

Reads:
  - detections/<stem>_norfair_dt50_hc5.csv
  - detections/<stem>_yolo26s-pose.csv
  - h1_hand_pool/data/hand_events.csv
  - h1_hand_pool/data/tracklet_features.csv
  - h1_hand_pool/data/hand_inventory.csv
  - videos/<stem>.mp4 (read-only from parent juggling-yolo tree)

Writes only to h1_hand_pool/contact_sheets/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
SHIPPED = WORKTREE / "detections"
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets"

WRIST_CONF_MIN = 0.5

# Color palette (BGR)
COLOR_LEFT = (255, 128, 64)     # light blue
COLOR_RIGHT = (64, 200, 255)    # orange
COLOR_PREV = (0, 255, 0)        # green
COLOR_THIS = (0, 0, 255)        # red
COLOR_NEXT = (255, 0, 255)      # magenta


def load_tracklets(stem: str) -> dict[int, list[tuple[int, float, float, float]]]:
    """Return tid -> list of (frame, x, y, conf)."""
    out: dict[int, list] = defaultdict(list)
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
    """Return frame -> {'left': (x,y,conf), 'right': (x,y,conf)} or None per side."""
    out: dict[int, dict] = {}
    path = SHIPPED / f"{stem}_yolo26s-pose.csv"
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


def load_events() -> list[dict]:
    rows = []
    with (H1_DATA / "hand_events.csv").open(newline="") as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            if r["tid"]:
                r["tid"] = int(r["tid"])
            rows.append(r)
    return rows


def find_neighbor_tids(
    tracks: dict[int, list],
    tid: int,
    frame: int,
    hand: str,
    is_entry: bool,
    max_gap: int = 30,
) -> tuple[int | None, int | None]:
    """Find the previous tracklet ending just before this event, and the
    next tracklet starting just after this event, considering small gaps only.
    """
    # The "involved" tid is the one for which this is an ENTRY/EXIT.
    # For an ENTRY at frame F: prev = tracklet ending at or before F-1 with small gap
    # For an EXIT at frame F: next = tracklet starting at or after F+1 with small gap
    # We're using the event's hand for side hint but won't filter by it.
    candidates = sorted(tracks.items(), key=lambda kv: kv[1][0][0])
    prev = None
    nxt = None
    for cand_tid, pts in candidates:
        if cand_tid == tid:
            continue
        if not pts:
            continue
        first, last = pts[0][0], pts[-1][0]
        if is_entry:
            # find a tracklet ending at <= frame-1 with gap < max_gap
            if last < frame and (frame - last) <= max_gap and last >= frame - max_gap:
                if prev is None or last > prev[1]:
                    prev = (cand_tid, last)
        else:
            if first > frame and (first - frame) <= max_gap and first <= frame + max_gap:
                if nxt is None or first < nxt[1]:
                    nxt = (cand_tid, first)
    return (prev[0] if prev else None, nxt[0] if nxt else None)


def draw_contact_sheet(
    stem: str,
    video_key: str,
    event: dict,
    tracks: dict[int, list],
    wrists: dict[int, dict],
    out_path: Path,
) -> bool:
    """Render a 6-tile contact sheet for one event. Return True on success."""
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    f_event = event["frame"]
    is_entry = event["event_type"] in ("ENTRY",)
    involved_tid = event.get("tid")
    prev_tid, next_tid = find_neighbor_tids(
        tracks, involved_tid or -1, f_event, event["hand"], is_entry,
        max_gap=30,
    )

    # Window of frames: 6 frames spanning roughly 0.5s before/after
    deltas = [-12, -6, -2, 0, 3, 10]
    frames = [f_event + d for d in deltas]
    # Clamp to >=0
    frames = [max(0, f) for f in frames]
    n = len(frames)
    tile_w, tile_h = 320, 180  # downscaled from 1280x720
    grid_w = tile_w * 3
    grid_h = tile_h * 2 + 60  # extra room for header

    sheet = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    sheet[:] = (32, 32, 32)

    # Header text
    header = (f"{event['event_type']}  hand={event['hand']}  "
              f"frame={f_event}  t={f_event/fps:.3f}s  tid={involved_tid}  "
              f"dist={event['dist']}  slope={event['slope']}  "
              f"pre_depth={event['pre_depth']}  pool={event['pool_depth']}  "
              f"ambig={event['identity_ambiguous']}")
    cv2.putText(sheet, header, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"video: {video_key}", (8, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1, cv2.LINE_AA)

    for i, (d, fr) in enumerate(zip(deltas, frames)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok or img is None:
            continue
        # Downscale
        img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        # Overlay wrists
        wr = wrists.get(fr, {})
        if wr.get("left"):
            x, y, _ = wr["left"]
            x = int(x * tile_w / 1280.0)
            y = int(y * tile_h / 720.0)
            cv2.circle(img, (x, y), 10, COLOR_LEFT, 2)
            cv2.putText(img, "L", (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        COLOR_LEFT, 1, cv2.LINE_AA)
        if wr.get("right"):
            x, y, _ = wr["right"]
            x = int(x * tile_w / 1280.0)
            y = int(y * tile_h / 720.0)
            cv2.circle(img, (x, y), 10, COLOR_RIGHT, 2)
            cv2.putText(img, "R", (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        COLOR_RIGHT, 1, cv2.LINE_AA)

        # Draw tracklets: previous (if fr <= event frame), involved (if any),
        # next (if fr >= event frame).
        for label, tid, color in (
            ("prev", prev_tid, COLOR_PREV),
            ("this", involved_tid, COLOR_THIS),
            ("next", next_tid, COLOR_NEXT),
        ):
            if tid is None or tid not in tracks:
                continue
            pts = tracks[tid]
            if not pts:
                continue
            if label == "prev":
                visible = [(f, x, y) for (f, x, y, c) in pts
                           if f <= fr and f >= fr - 30]
            elif label == "this":
                if is_entry:
                    visible = [(f, x, y) for (f, x, y, c) in pts
                               if f <= fr and f >= fr - 30]
                else:
                    visible = [(f, x, y) for (f, x, y, c) in pts
                               if f >= fr and f <= fr + 30]
            else:
                visible = [(f, x, y) for (f, x, y, c) in pts
                           if f >= fr and f <= fr + 30]
            if not visible:
                continue
            for j in range(1, len(visible)):
                x0, y0 = visible[j - 1][1], visible[j - 1][2]
                x1, y1 = visible[j][1], visible[j][2]
                x0 = int(x0 * tile_w / 1280.0)
                y0 = int(y0 * tile_h / 720.0)
                x1 = int(x1 * tile_w / 1280.0)
                y1 = int(y1 * tile_h / 720.0)
                cv2.line(img, (x0, y0), (x1, y1), color, 2)
            # Mark the last visible point with a small circle
            x0, y0 = visible[-1][1], visible[-1][2]
            x0 = int(x0 * tile_w / 1280.0)
            y0 = int(y0 * tile_h / 720.0)
            cv2.circle(img, (x0, y0), 3, color, -1)

        # Frame label
        label = f"{d:+d}f  f={fr}"
        cv2.putText(img, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)

        col = i % 3
        row = i // 3
        sheet[60 + row * tile_h: 60 + (row + 1) * tile_h,
              col * tile_w: (col + 1) * tile_w] = img

    cap.release()
    cv2.imwrite(str(out_path), sheet)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-events", type=int, default=24)
    ap.add_argument("--stem", default=None,
                    help="restrict to one stem (default: both)")
    args = ap.parse_args()

    H1_CS.mkdir(parents=True, exist_ok=True)
    events = load_events()
    # Group by stem
    by_stem: dict[str, list] = defaultdict(list)
    for e in events:
        by_stem[e["stem"]].append(e)

    # Pick a curated selection: first N ENTRY/EXIT/AMBIGUOUS events per video.
    curations: list[dict] = []
    for stem, evs in by_stem.items():
        if args.stem and stem != args.stem:
            continue
        # Prefer non-UNRESOLVED, non-UNMATCHED events
        priority = ["ENTRY", "EXIT", "AMBIGUOUS_POOL_EXIT", "UNMATCHED_EXIT",
                    "UNRESOLVED_HELD_OR_LOST"]
        for et in priority:
            sub = [e for e in evs if e["event_type"] == et]
            for e in sub:
                curations.append(e)
                if len([c for c in curations if c["stem"] == stem]) >= args.max_events // 2:
                    break

    tracks_cache: dict[str, dict] = {}
    wrists_cache: dict[str, dict] = {}

    rendered = 0
    for ev in curations:
        stem = ev["stem"]
        if stem not in tracks_cache:
            tracks_cache[stem] = load_tracklets(stem)
        if stem not in wrists_cache:
            wrists_cache[stem] = load_wrist_frames(stem)
        out_name = (f"{stem}_ev{int(ev['event_id']):04d}_{ev['event_type']}_"
                    f"hand{ev['hand']}_f{ev['frame']}.png")
        out_path = H1_CS / out_name
        ok = draw_contact_sheet(
            stem, ev["video"], ev,
            tracks_cache[stem], wrists_cache[stem], out_path,
        )
        if ok:
            rendered += 1
    print(f"Rendered {rendered} contact sheets to {H1_CS}")


if __name__ == "__main__":
    main()
