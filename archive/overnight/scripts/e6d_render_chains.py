#!/usr/bin/env python3
"""E6d: render calibrated wide-gap chains on the source video for visual QA."""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402
from e6c_wide_universe_v2 import bal8_predict, calibrate_per_video, gate_for  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
OUT_DIR = BASE / "reports"
STEM = "identical_balls_trick_000_018"
VIDEO_PATH = PROJECT / "videos" / f"{STEM}.mp4"
MAX_GAP = 30


def main() -> None:
    tracks = observed_masked_legacy(STEM)
    cal = calibrate_per_video(tracks)

    cand_rows = []
    for sid in sorted(tracks):
        sp = tracks[sid]
        if len(sp) < 3:
            continue
        end_f = sp[-1][0]
        for cid in sorted(tracks):
            if cid == sid:
                continue
            cp = tracks[cid]
            if not cp or cp[0][0] <= end_f:
                continue
            gap = cp[0][0] - end_f - 1
            if gap > MAX_GAP:
                continue
            qb = bal8_predict(sp, cp[0][0])
            err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
            if err_b is None or err_b >= gate_for(cal, gap):
                continue
            cand_rows.append({"sid": sid, "cid": cid, "gap": gap, "bal8": err_b})

    # normalized-cost successor assignment
    all_ids = sorted(tracks)
    n_t = len(all_ids)
    idx = {t: i for i, t in enumerate(all_ids)}
    cost = np.full((n_t, 2 * n_t), 1e9)
    cost[:, n_t:] = 1.0
    for r in cand_rows:
        rel = r["bal8"] / gate_for(cal, r["gap"])
        si, ci = idx[r["sid"]], idx[r["cid"]]
        if cost[si, ci] > rel:
            cost[si, ci] = rel
    ri, ci = linear_sum_assignment(cost)
    links = {(all_ids[a], all_ids[b]) for a, b in zip(ri, ci) if b < n_t and cost[a, b] < 1e9}

    # union-find chains
    parent = {t: t for t in all_ids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s, c in sorted(links):
        rs, rc = find(s), find(c)
        if rs != rc:
            parent[rs] = rc
    roots = sorted({find(t) for t in all_ids})
    palette = []
    for i in range(len(roots)):
        hue = int(180 * i / max(len(roots), 1)) % 180
        hsv_pixel = np.full((1, 1, 3), hue, dtype=np.uint8)
        hsv_pixel[..., 1] = 230
        hsv_pixel[..., 2] = 255
        bgr = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0, 0]
        palette.append([int(bgr[0]), int(bgr[1]), int(bgr[2])])
    root_color = {r: palette[i] for i, r in enumerate(roots)}
    gap_by_link = {}
    for r in cand_rows:
        gap_by_link[(r["sid"], r["cid"])] = r["gap"]

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    fps_out = cap.get(cv2.CAP_PROP_FPS)
    out_path = OUT_DIR / f"e6d_chains_{STEM}.mp4"
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps_out, (1280, 720)
    )

    points_by_frame: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    for tid, pts in tracks.items():
        for f, x, y in pts:
            points_by_frame[f].append((tid, x, y))

    trail_len = 45
    frame_idx = 0
    history: dict[int, list[tuple[float, float]]] = defaultdict(list)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for tid, x, y in points_by_frame.get(frame_idx, []):
            history[tid].append((x, y))
        for tid, pts_hist in history.items():
            col = root_color[find(tid)]
            recent = pts_hist[-trail_len:]
            for p0, p1 in zip(recent[:-1], recent[1:]):
                cv2.line(frame, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), col, 1)
        # bridges for long-gap links active near this frame
        for s, c in links:
            gap = gap_by_link.get((s, c), 0)
            if gap <= 10:
                continue
            sp, cp = tracks[s], tracks[c]
            a = sp[-1]
            b = cp[0]
            if b[0] - 20 <= frame_idx <= b[0] + 15:
                cv2.arrowedLine(
                    frame, (int(a[1]), int(a[2])), (int(b[1]), int(b[2])),
                    (30, 220, 255), 2, tipLength=0.03,
                )
                mid = (int((a[1] + b[1]) / 2), int((a[2] + b[2]) / 2))
                cv2.putText(frame, f"{s}->{c} gap{gap}", mid,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 220, 255), 1)
        for tid, x, y in points_by_frame.get(frame_idx, []):
            col = root_color[find(tid)]
            cv2.circle(frame, (int(x), int(y)), 4, col, -1)
            cv2.putText(frame, f"c{find(tid)}", (int(x) + 5, int(y) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1)
        n_active = len(points_by_frame.get(frame_idx, []))
        cv2.putText(frame, f"f{frame_idx} obs={n_active} chains={len(links)}",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        writer.write(frame)
        frame_idx += 1
        if frame_idx >= 1079:
            break
    cap.release()
    writer.release()

    # sample frames for vision inspection
    frames_dir = OUT_DIR / "frames"
    frames_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(out_path))
    for target in (150, 400, 700, 950):
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, fr = cap.read()
        if ok:
            cv2.imwrite(str(frames_dir / f"e6d_f{target}.png"), fr)
    cap.release()
    print(f"wrote {out_path}")
    print(f"links={len(links)}, chains={len(set(find(t) for t in all_ids))}")
    print("sample frames:", sorted(p.name for p in frames_dir.glob('*.png')))


if __name__ == "__main__":
    main()
