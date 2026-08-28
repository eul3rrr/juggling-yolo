#!/usr/bin/env python3
"""H50 contact sheets: render the 3 changed-pattern windows for visual QA.

Renders 3 contact sheets for the 3 H45-confirmed identity switches on
identical that H50 dropped, with overlay of:
  - the unfiltered (H12 v8 baseline) and filtered (H50) pattern labels
  - the dropped CATCH/THROW events
  - the chain involved

Uses cv2.VideoCapture from the existing H1 v3 contact sheet renderer.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h50"
H1_CS.mkdir(exist_ok=True)

# Reuse the H1 v3 contact sheet renderer
sys.path.insert(0, str(H1_DIR / "scripts"))
from h1_contact_sheets_v3 import (  # noqa: E402
    load_tracklets, load_wrist_frames, VIDEOS_DIR,
)

import cv2
import numpy as np


# Custom color palette for the H50 sheet
COLOR_LEFT = (0, 165, 255)  # orange (BGR)
COLOR_RIGHT = (255, 80, 80)  # blue (BGR)
COLOR_FROM = (0, 255, 255)  # yellow
COLOR_TO = (255, 255, 0)    # cyan
COLOR_TEXT = (255, 255, 255)


def draw_h50_sheet(stem: str, video_key: str, from_tid: int, to_tid: int,
                    f_focus: int, f_catch: int, f_throw: int,
                    chain_id: int, flight_time: int,
                    unf_pattern: str, filt_pattern: str,
                    out_path: Path, drop_label: str) -> bool:
    """Render a 6-frame contact sheet for an H50 dropped (CATCH, THROW)."""
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        print(f"  Video not found: {video_path}")
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tracks = load_tracklets(stem)
    wrists = load_wrist_frames(stem)
    f_event = f_throw  # focus on the THROW (the dropped event)

    # 6 frames: catch, last-clear, contact, throw, after-throw, later
    deltas = [-25, -12, -5, 0, 5, 15]
    frames = [max(0, f_event + d) for d in deltas]
    n = len(frames)
    tile_w, tile_h = 320, 180
    grid_w = tile_w * 3
    grid_h = tile_h * 2 + 90
    sheet = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    sheet[:] = (32, 32, 32)

    # header
    header = (f"H50 dropped pair: chain {chain_id} {from_tid}->{to_tid}  "
              f"hand=drops  flight={flight_time}f  focus=f{f_event}  "
              f"t={f_event/fps:.3f}s")
    cv2.putText(sheet, header[:160], (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (180, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet,
                f"CATCH@ f{f_catch}  THROW@ f{f_throw}  PATTERN unf={unf_pattern} filt={filt_pattern}",
                (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, drop_label, (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.3,
                (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"video: {video_key}", (8, 78), cv2.FONT_HERSHEY_SIMPLEX,
                0.3, (160, 160, 160), 1, cv2.LINE_AA)

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

        for label, tid, color, win in (
            ("from", from_tid, COLOR_FROM, (fr - 30, fr + 1)),
            ("to", to_tid, COLOR_TO, (fr - 1, fr + 30)),
        ):
            if tid is None or tid not in tracks:
                continue
            pts = tracks[tid]
            if not pts:
                continue
            visible = [(f, x, y) for (f, x, y, c) in pts
                       if win[0] <= f <= win[1]]
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
            cv2.circle(img, (x0, y0), 4, color, -1)

        # Mark this frame as CATCH or THROW
        if fr == f_catch:
            cv2.putText(img, "CATCH", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 0), 1, cv2.LINE_AA)
        elif fr == f_throw:
            cv2.putText(img, "THROW", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255), 1, cv2.LINE_AA)

        cv2.putText(img, f"{d:+d}f  f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, COLOR_TEXT, 1, cv2.LINE_AA)
        col = i % 3
        row = i // 3
        sheet[90 + row * tile_h: 90 + (row + 1) * tile_h,
              col * tile_w: (col + 1) * tile_w] = img

    cap.release()
    cv2.imwrite(str(out_path), sheet)
    return True


def main():
    print("=== H50 contact sheets ===")
    stem = "identical_balls_trick_000_018"
    video_key = "videos/identical_balls_trick_000_018.mp4"

    # Dropped events on identical:
    # chain 13: from_tid=21 (or 23) -> to_tid=23, CATCH@207, THROW@232, ft=3
    # chain 23: from_tid=37 (or earlier) -> to_tid=37, CATCH@522, THROW@533, ft=1
    # chain 30: from_tid=52 -> to_tid=52, CATCH@766, THROW@775, ft=5
    sheets = [
        {"chain_id": 13, "from_tid": 21, "to_tid": 23,
         "f_catch": 207, "f_throw": 232, "ft": 3,
         "unf_pat": "FOUNTAIN_3+", "filt_pat": "MIXED_3+",
         "label": "drop13_ft3_chain13_207_232"},
        {"chain_id": 23, "from_tid": 35, "to_tid": 37,
         "f_catch": 522, "f_throw": 533, "ft": 1,
         "unf_pat": "MIXED_3+", "filt_pat": "CASCADE_3+",
         "label": "drop23_ft1_chain23_522_533"},
        {"chain_id": 30, "from_tid": 52, "to_tid": 54,
         "f_catch": 766, "f_throw": 775, "ft": 5,
         "unf_pat": "MIXED_3+", "filt_pat": "CASCADE_3+",
         "label": "drop30_ft5_chain30_766_775"},
    ]
    # Note: the (from_tid, to_tid) are the tracklet pair from the chain.
    # Verify with the actual h7v3pure chain definitions:
    chains = {}
    with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            chains[int(r["chain_id"])] = r

    for s in sheets:
        cid = s["chain_id"]
        tids = [int(t) for t in chains[cid]["tids"].split(",") if t]
        print(f"  chain {cid} tids={tids}")
        # Find the (from, to) for the dropped event
        all_events = []
        with (H1_DATA / f"chain_events_h35_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                all_events.append(r)
        for e in all_events:
            if int(e["chain_id"]) == cid and int(e["event_frame"]) == s["f_throw"] and e["event"] == "THROW":
                s["to_tid"] = int(e["tid"])
                s["from_tid"] = int(e["prev_tid"])
                print(f"    THROW@ f={e['event_frame']} from_tid={s['from_tid']} to_tid={s['to_tid']}")
        for e in all_events:
            if int(e["chain_id"]) == cid and int(e["event_frame"]) == s["f_catch"] and e["event"] == "CATCH":
                print(f"    CATCH@ f={e['event_frame']} to_tid={e['tid']}")
        out_path = H1_CS / f"{s['label']}.png"
        ok = draw_h50_sheet(
            stem, video_key, s["from_tid"], s["to_tid"],
            f_focus=s["f_throw"], f_catch=s["f_catch"], f_throw=s["f_throw"],
            chain_id=cid, flight_time=s["ft"],
            unf_pattern=s["unf_pat"], filt_pattern=s["filt_pat"],
            out_path=out_path,
            drop_label=f"DROPPED: identity switch (flight={s['ft']}f, H45 confirmed)",
        )
        if ok:
            print(f"    Wrote: {out_path.name}")
        else:
            print(f"    FAILED: {out_path.name}")

    print(f"\nContact sheets in: {H1_CS}")


if __name__ == "__main__":
    main()
