#!/usr/bin/env python3
"""H2 — Contact sheets for the longest H2 chains (chain 38 and chain 53).

These are 8-tracklet and 5-tracklet chains respectively, on the
identical video. They contain the most interesting mix of
hand-edges and air-edges and are the most informative cases
for visual QA.

The contact sheet shows all the tracklets in the chain, color-coded:
- Yellow: tracklets in the chain
- Magenta: the FROM tracklet of a hand-edge
- Cyan: the TO tracklet of a hand-edge
- Blue: the source tracklet of a BALLISTIC edge
- Light yellow: the candidate tracklet of a BALLISTIC edge

The output is a 2x4 grid (chain 38 has 8 tracklets) showing the
focus frame (middle of the chain) and the surrounding context.
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
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_CS_H2 = H1_DATA.parent / "contact_sheets_h2"
H1_CS_H2.mkdir(parents=True, exist_ok=True)

# BGR colors
COLOR_LEFT_WRIST = (255, 128, 64)
COLOR_RIGHT_WRIST = (64, 200, 255)
COLOR_CHAIN = (180, 180, 0)         # dark yellow: in-chain tracklets
COLOR_HAND_FROM = (0, 200, 255)     # cyan: hand-edge FROM
COLOR_HAND_TO = (255, 0, 255)       # magenta: hand-edge TO
COLOR_AIR_FROM = (200, 100, 100)    # blue-ish: air-edge source
COLOR_AIR_TO = (100, 100, 200)      # red-ish: air-edge candidate
COLOR_TEXT = (255, 255, 255)


def load_tracklets(stem: str) -> dict[int, list]:
    out = {}
    with (SHIPPED / f"{stem}_norfair_dt50_hc5.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r.get("observed") != "1":
                continue
            tid = int(r["track_id"])
            out.setdefault(tid, []).append((
                int(r["frame"]),
                float(r["center_x"]),
                float(r["center_y"]),
                float(r["confidence"]),
            ))
    for tid in out:
        out[tid].sort(key=lambda p: p[0])
    return out


def load_wrist_frames(stem: str) -> dict[int, dict]:
    out = {}
    with (SHIPPED / f"{stem}_yolo26s-pose.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            e = out.setdefault(f, {"left": None, "right": None})
            for side in ("left", "right"):
                x = r.get(f"{side}_wrist_x")
                y = r.get(f"{side}_wrist_y")
                c = r.get(f"{side}_wrist_confidence")
                if x is None or y is None or c is None:
                    continue
                c = float(c)
                if c < 0.5:
                    continue
                e[side] = (float(x), float(y), c)
    return out


def load_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


def load_h2_chains(stem: str) -> list[dict]:
    with (H1_DATA / f"h2_chains_{stem}.csv").open() as fh:
        return [{
            "chain_id": int(r["chain_id"]),
            "n_tracklets": int(r["n_tracklets"]),
            "first_frame": int(r["first_frame"]),
            "last_frame": int(r["last_frame"]),
            "n_hand_edges": int(r["n_hand_edges"]),
            "n_air_edges": int(r["n_air_edges"]),
            "tids": [int(t) for t in r["tids"].split(",") if t],
        } for r in csv.DictReader(fh)]


def load_h2_edges(stem: str) -> list[dict]:
    with (H1_DATA / f"h2_edges_{stem}.csv").open() as fh:
        return [{
            "from_tid": int(r["from_tid"]),
            "to_tid": int(r["to_tid"]),
            "edge_type": r["edge_type"],
            "metadata": r["metadata"],
        } for r in csv.DictReader(fh)]


def draw_chain_sheet(stem: str, video_key: str, chain: dict, edges: list[dict],
                     tracks: dict, wrists: dict, feats: dict, out_path: Path):
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        print(f"  video not found: {video_path}")
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Pick 8 frames evenly across the chain's frame range
    fmin, fmax = chain["first_frame"], chain["last_frame"]
    if fmax - fmin < 7:
        deltas = [0] * 8
    else:
        step = (fmax - fmin) / 7
        deltas = [int(round(fmin + i * step)) - fmin for i in range(8)]
    frames = [max(0, fmin + d) for d in deltas]
    n = len(frames)
    cols, rows = 4, 2
    tile_w, tile_h = 320, 180
    grid_w = tile_w * cols
    grid_h = tile_h * rows + 90
    sheet = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    sheet[:] = (32, 32, 32)

    # Header
    header = (f"H2 chain {chain['chain_id']}  tids {chain['tids']}  "
              f"({chain['n_tracklets']} tracklets, "
              f"{chain['n_hand_edges']} hand + {chain['n_air_edges']} air)")
    cv2.putText(sheet, header[:160], (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (180, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"video: {video_key}  f={fmin}..{fmax}",
                (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1, cv2.LINE_AA)
    # Edge list
    edge_text = "edges: " + ", ".join(f"{e['from_tid']}->{e['to_tid']}({e['edge_type'][:3]})" for e in edges)
    cv2.putText(sheet, edge_text[:160], (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.3,
                (180, 180, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, edge_text[160:320] if len(edge_text) > 160 else "",
                (8, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (180, 180, 255), 1, cv2.LINE_AA)

    # Classify edges for color coding
    hand_from_set = {e["from_tid"] for e in edges if "HAND_TRANSITION" in e["edge_type"]}
    hand_to_set = {e["to_tid"] for e in edges if "HAND_TRANSITION" in e["edge_type"]}
    air_from_set = {e["from_tid"] for e in edges if e["edge_type"] == "BALLISTIC"}
    air_to_set = {e["to_tid"] for e in edges if e["edge_type"] == "BALLISTIC"}

    for i, fr in enumerate(frames):
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
            cv2.circle(img, (x, y), 10, COLOR_LEFT_WRIST, 2)
            cv2.putText(img, "L", (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        COLOR_LEFT_WRIST, 1, cv2.LINE_AA)
        if wr.get("right"):
            x, y, _ = wr["right"]
            x = int(x * tile_w / 1280.0)
            y = int(y * tile_h / 720.0)
            cv2.circle(img, (x, y), 10, COLOR_RIGHT_WRIST, 2)
            cv2.putText(img, "R", (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        COLOR_RIGHT_WRIST, 1, cv2.LINE_AA)

        for tid in chain["tids"]:
            if tid not in tracks:
                continue
            pts = tracks[tid]
            if not pts:
                continue
            visible = [(f, x, y) for (f, x, y, c) in pts
                       if fr - 30 <= f <= fr + 30]
            if not visible:
                continue
            # Pick color based on role
            if tid in hand_from_set:
                color = COLOR_HAND_FROM
            elif tid in hand_to_set:
                color = COLOR_HAND_TO
            elif tid in air_from_set:
                color = COLOR_AIR_FROM
            elif tid in air_to_set:
                color = COLOR_AIR_TO
            else:
                color = COLOR_CHAIN
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

        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    COLOR_TEXT, 1, cv2.LINE_AA)
        col = i % cols
        row = i // cols
        sheet[90 + row * tile_h: 90 + (row + 1) * tile_h,
              col * tile_w: (col + 1) * tile_w] = img

    cap.release()
    cv2.imwrite(str(out_path), sheet)
    return True


def main():
    stems = {
        "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    }
    tracks_cache, wrists_cache, feats_cache, edges_cache = {}, {}, {}, {}
    rendered = 0
    for stem, video_key in stems.items():
        tracks_cache[stem] = load_tracklets(stem)
        wrists_cache[stem] = load_wrist_frames(stem)
        feats_cache[stem] = load_features(stem)
        edges_cache[stem] = load_h2_edges(stem)
        chains = load_h2_chains(stem)
        # Pick the longest 5 chains
        chains.sort(key=lambda c: -c["n_tracklets"])
        for chain in chains[:5]:
            chain_edges = [e for e in edges_cache[stem]
                           if e["from_tid"] in chain["tids"]
                           and e["to_tid"] in chain["tids"]]
            out_name = (f"chain_{chain['chain_id']}_"
                        f"n{chain['n_tracklets']}_h{chain['n_hand_edges']}_a{chain['n_air_edges']}.png")
            out_path = H1_CS_H2 / out_name
            ok = draw_chain_sheet(
                stem, video_key, chain, chain_edges,
                tracks_cache[stem], wrists_cache[stem], feats_cache[stem],
                out_path,
            )
            if ok:
                rendered += 1
                print(f"  rendered {out_name}")
    print(f"Rendered {rendered} H2 chain contact sheets to {H1_CS_H2}")


if __name__ == "__main__":
    main()
