#!/usr/bin/env python3
"""H1 v2 contact sheet generator.

Renders six-frame contact sheets for:
  - the original 4 v1 inspected events (mapped to v2 by (stem, frame, event_type))
  - a curated selection of v2 filter events
  - the 3 v2 surviving hand-links

Output PNGs go to h1_hand_pool/contact_sheets_v2/ (a new directory; v1 sheets
are preserved under contact_sheets/).
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
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS_V1 = H1_DIR / "contact_sheets"          # preserve v1 sheets
H1_CS_V2 = H1_DIR / "contact_sheets_v2"      # new v2 sheets

WRIST_CONF_MIN = 0.5

# Color palette (BGR)
COLOR_LEFT = (255, 128, 64)
COLOR_RIGHT = (64, 200, 255)
COLOR_PREV = (0, 255, 0)
COLOR_THIS = (0, 0, 255)
COLOR_NEXT = (255, 0, 255)
COLOR_FILTERED = (128, 128, 128)  # gray for filtered-out events


def load_tracklets(stem: str) -> dict[int, list]:
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


def find_neighbor_tids(tracks, tid, frame, hand, is_entry, max_gap=30):
    """Find the previous tracklet ending just before, and the next tracklet
    starting just after, this event frame."""
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
            if last < frame and (frame - last) <= max_gap and last >= frame - max_gap:
                if prev is None or last > prev[1]:
                    prev = (cand_tid, last)
        else:
            if first > frame and (first - frame) <= max_gap and first <= frame + max_gap:
                if nxt is None or first < nxt[1]:
                    nxt = (cand_tid, first)
    return (prev[0] if prev else None, nxt[0] if nxt else None)


def draw_sheet(stem, video_key, event, tracks, wrists, out_path):
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    f_event = event["frame"]
    involved_tid = event.get("tid")
    is_entry = event["event_type"] in ("ENTRY", "UNCONTEXTED_ENTRY")
    prev_tid, next_tid = find_neighbor_tids(
        tracks, involved_tid or -1, f_event, event["hand"], is_entry, max_gap=30,
    )

    deltas = [-12, -6, -2, 0, 3, 10]
    frames = [max(0, f_event + d) for d in deltas]
    n = len(frames)
    tile_w, tile_h = 320, 180
    grid_w = tile_w * 3
    grid_h = tile_h * 2 + 60

    sheet = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    sheet[:] = (32, 32, 32)

    # Color the header based on event type
    color_for_type = {
        "ENTRY": (180, 255, 180),
        "EXIT": (180, 220, 255),
        "AMBIGUOUS_POOL_EXIT": (180, 200, 255),
        "UNMATCHED_EXIT": (200, 200, 200),
        "UNRESOLVED_HELD_OR_LOST": (180, 180, 180),
        "EXPIRED_HELD": (140, 140, 140),
        "STALE_TOKEN_THROW": (100, 100, 100),
        "WRIST_MOTION_THROW": (100, 100, 100),
        "THROW_NO_LEAVE": (100, 100, 100),
        "UNCONTEXTED_ENTRY": (140, 140, 100),
    }
    header_color = color_for_type.get(event["event_type"], (200, 200, 200))

    header = (f"v2 {event['event_type']}  hand={event['hand']}  "
              f"frame={f_event}  t={f_event/fps:.3f}s  tid={involved_tid}  "
              f"dist={event.get('dist','')}  slope={event.get('slope','')}  "
              f"pre_d={event.get('pre_depth','')}  pool={event.get('pool_depth','')}")
    cv2.putText(sheet, header, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                header_color, 1, cv2.LINE_AA)
    cv2.putText(sheet, f"video: {video_key}", (8, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1, cv2.LINE_AA)
    notes = event.get("notes", "")
    if notes:
        cv2.putText(sheet, f"notes: {notes[:90]}", (8, 56),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (160, 160, 160), 1, cv2.LINE_AA)

    for i, (d, fr) in enumerate(zip(deltas, frames)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok or img is None:
            continue
        img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
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
            x0, y0 = visible[-1][1], visible[-1][2]
            x0 = int(x0 * tile_w / 1280.0)
            y0 = int(y0 * tile_h / 720.0)
            cv2.circle(img, (x0, y0), 3, color, -1)

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


def main():
    H1_CS_V2.mkdir(parents=True, exist_ok=True)
    events = load_events()

    # Curated set 1: the 4 v1 inspected events (mapped to v2 by stem+frame+type)
    # v1 reported these (from contact_sheets/):
    #   ev0001 UNMATCHED_EXIT identical f=27
    #   ev0002 ENTRY identical f=31
    #   ev0006 AMBIG_POOL_EXIT identical f=51
    #   ev0004 ENTRY youtube f=102
    v1_anchors = [
        ("identical_balls_trick_000_018", 27, "UNMATCHED_EXIT", "v1_ev0001"),
        ("identical_balls_trick_000_018", 31, None, "v1_ev0002"),  # could be ENTRY or UNCONTEXTED_ENTRY
        ("identical_balls_trick_000_018", 51, None, "v1_ev0006"),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 102, None, "v1_ev0004"),
    ]
    picked = []
    for stem, fr, et, name in v1_anchors:
        cands = [e for e in events if e["stem"] == stem and e["frame"] == fr]
        if et is not None:
            cands = [e for e in cands if e["event_type"] == et]
        if cands:
            picked.append((name, cands[0]))
        elif cands == [] and et is not None:
            # try any event at that frame
            cands = [e for e in events if e["stem"] == stem and e["frame"] == fr]
            if cands:
                picked.append((name, cands[0]))

    # Curated set 2: the 3 surviving v2 hand-links
    with (H1_DATA / "hand_links.csv").open() as fh:
        links = list(csv.DictReader(fh))
    for i, l in enumerate(links, 1):
        # find the EXIT event for to_tid
        exit_ev = [e for e in events
                   if e["stem"] == l["stem"] and e["tid"] == int(l["to_tid"])
                   and e["event_type"] in ("EXIT", "AMBIGUOUS_POOL_EXIT")][0]
        picked.append((f"v2_link_{i}_{l['kind']}_to_{l['to_tid']}", exit_ev))

    # Curated set 3: sample of v2 filter events
    # pick first 2 of each filter type per video
    by_stem_type = defaultdict(list)
    for e in events:
        if e["event_type"] in ("THROW_NO_LEAVE", "UNCONTEXTED_ENTRY", "EXPIRED_HELD", "STALE_TOKEN_THROW"):
            by_stem_type[(e["stem"], e["event_type"])].append(e)
    for (stem, et), evs in sorted(by_stem_type.items()):
        for e in evs[:2]:
            picked.append((f"v2_filter_{et}_{int(e['frame'])}", e))

    tracks_cache = {}
    wrists_cache = {}
    rendered = 0
    for label, ev in picked:
        stem = ev["stem"]
        if stem not in tracks_cache:
            tracks_cache[stem] = load_tracklets(stem)
        if stem not in wrists_cache:
            wrists_cache[stem] = load_wrist_frames(stem)
        out_name = f"{label}_{ev['event_type']}_f{ev['frame']}.png"
        out_path = H1_CS_V2 / out_name
        ok = draw_sheet(
            stem, ev["video"], ev,
            tracks_cache[stem], wrists_cache[stem], out_path,
        )
        if ok:
            rendered += 1
    print(f"Rendered {rendered} v2 contact sheets to {H1_CS_V2}")


if __name__ == "__main__":
    main()
