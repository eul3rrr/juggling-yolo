#!/usr/bin/env python3
"""H1 v3 — contact sheets for the NEW v3 hand-links (not in v2).

For each v3 setting (v3a throw3_soft, v3b throw5_soft, v3c throw7_soft),
we compute the link set minus the v2 link set, and render contact sheets
for each *new* link. The sheets show:

  - approach (frame - 6)
  - last clear ball (frame - 2)
  - contact (event frame)
  - first outgoing detection (event frame + 3)
  - shortly after (event frame + 10)

We render the FROM and TO tracklets in different colors, plus both
wrist positions, plus the relevant event annotations.

The goal is to visually confirm that each new v3 link is a real
catch-throw sequence (not a spurious mid-air pass through the hand
envelope).

Output: `h1_hand_pool/contact_sheets_v3/{label}_link_{N}_{kind}_{from_tid}_to_{to_tid}.png`
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
H1_CS_V3 = H1_DIR / "contact_sheets_v3"

WRIST_CONF_MIN = 0.5

# (BGR)
COLOR_LEFT = (255, 128, 64)
COLOR_RIGHT = (64, 200, 255)
COLOR_FROM = (0, 255, 255)      # yellow: from tracklet (incoming/catch)
COLOR_TO = (255, 0, 255)        # magenta: to tracklet (outgoing/throw)
COLOR_OTHER = (180, 180, 180)   # gray: other tracklets
COLOR_TEXT = (255, 255, 255)


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


def load_links(label: str) -> list[dict]:
    suf = label.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    suf = suf.replace("__", "_").strip("_")
    path = H1_DATA / f"hand_links_v3_{suf}.csv"
    if not path.exists():
        return []
    rows = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["from_frame"] = int(r["from_frame"])
            r["to_frame"] = int(r["to_frame"])
            r["from_dist"] = float(r["from_dist"])
            r["to_dist"] = float(r["to_dist"])
            r["from_slope"] = float(r["from_slope"])
            r["to_slope"] = float(r["to_slope"])
            r["tok_age_frames"] = int(r["tok_age_frames"])
            r["identity_ambiguous"] = (r["identity_ambiguous"] == "True")
            rows.append(r)
    return rows


def draw_link_sheet(stem: str, video_key: str, link: dict,
                    tracks: dict, wrists: dict, out_path: Path,
                    f_focus: int) -> bool:
    """Render a 6-frame contact sheet for a v3 hand-link.

    The focus frame is the link's EXIT (to_frame).
    """
    video_path = VIDEOS_DIR / Path(video_key).name
    if not video_path.exists():
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    f_event = f_focus
    from_tid = link["from_tid"]
    to_tid = link["to_tid"]
    hand = link["hand"]
    # 6 frames: approach / last clear / contact / after / mid-out / later
    deltas = [-12, -6, -2, 0, 3, 10]
    frames = [max(0, f_event + d) for d in deltas]
    n = len(frames)
    tile_w, tile_h = 320, 180
    grid_w = tile_w * 3
    grid_h = tile_h * 2 + 70
    sheet = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    sheet[:] = (32, 32, 32)

    # header
    header = (f"v3 link {from_tid}->{to_tid}  hand={hand}  kind={link['kind']}  "
              f"ambig={link['identity_ambiguous']}  tok_age={link['tok_age_frames']}f  "
              f"focus=f{f_event}  t={f_event/fps:.3f}s")
    cv2.putText(sheet, header[:160], (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (180, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"from f{link['from_frame']} (dist {link['from_dist']:.1f}, slope {link['from_slope']:.2f})  "
                       f"to f{link['to_frame']} (dist {link['to_dist']:.1f}, slope {link['to_slope']:.2f})",
                (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"video: {video_key}", (8, 56),
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

        # from-tid trail (yellow): all pts from t-30 to t+1 (incoming up to contact)
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

        cv2.putText(img, f"{d:+d}f  f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    COLOR_TEXT, 1, cv2.LINE_AA)

        col = i % 3
        row = i // 3
        sheet[70 + row * tile_h: 70 + (row + 1) * tile_h,
              col * tile_w: (col + 1) * tile_w] = img

    cap.release()
    cv2.imwrite(str(out_path), sheet)
    return True


def main():
    H1_CS_V3.mkdir(parents=True, exist_ok=True)

    # v2 links (to compute set difference)
    v2_links = []
    with (H1_DATA / "hand_links.csv").open() as fh:
        for r in csv.DictReader(fh):
            v2_links.append((r["stem"], int(r["from_tid"]), int(r["to_tid"])))
    v2_set = set(v2_links)

    # v3 settings to render
    settings = [
        "v3a_throw3_soft",
        "v3b_throw5_soft",
        "v3c_throw7_soft",
    ]
    tracks_cache, wrists_cache = {}, {}
    rendered = 0
    for label in settings:
        links = load_links(label)
        for i, l in enumerate(links, 1):
            key = (l["stem"], l["from_tid"], l["to_tid"])
            if key in v2_set:
                # already in v2; skip
                continue
            stem = l["stem"]
            if stem not in tracks_cache:
                tracks_cache[stem] = load_tracklets(stem)
                wrists_cache[stem] = load_wrist_frames(stem)
            out_name = (f"{label}_link_{i}_{l['kind']}_"
                        f"{l['from_tid']}_to_{l['to_tid']}_f{l['to_frame']}.png")
            out_path = H1_CS_V3 / out_name
            ok = draw_link_sheet(
                stem, l["video"], l,
                tracks_cache[stem], wrists_cache[stem],
                out_path, f_focus=l["to_frame"],
            )
            if ok:
                rendered += 1
                print(f"  rendered {out_name}")
    print(f"Rendered {rendered} v3 NEW link contact sheets to {H1_CS_V3}")


if __name__ == "__main__":
    main()
