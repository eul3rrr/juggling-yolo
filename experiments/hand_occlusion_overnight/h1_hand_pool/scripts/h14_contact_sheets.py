#!/usr/bin/env python3
"""H14 contact sheets: render V-shape trajectory for each interesting edge.

Uses cv2 (matches the convention of h1_contact_sheets_v3, h7v2_contact_sheets, etc.).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/scripts")))
from h14_v_shape import (
    H14_THRESHOLDS, H14_OUT, WORKTREE,
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
    v_shape_check, get_h7v2_ballistic, get_h7v2_reclassified, get_v4d_links,
)

import cv2
import numpy as np


def find_video_path(stem):
    candidates = [
        WORKTREE / "videos" / f"{stem}.mp4",
        # Fallback: main juggling-yolo workspace (the videos dir is symlinked/shared)
        Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos") / f"{stem}.mp4",
        Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/data/raw") / f"{stem}.mp4",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def read_frame(video_path, frame_idx):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def draw_circle(img, x, y, color, radius, thickness=2):
    cv2.circle(img, (int(x), int(y)), radius, color, thickness)


def render_contact_sheet(stem, from_tid, to_tid, kind, v_result, out_path):
    """Render a 6-frame contact sheet with trajectory overlay.
    Layout: 2x3 grid of 6 frames.
    """
    src_dets = load_per_det_tracklet(stem, from_tid)
    tgt_dets = load_per_det_tracklet(stem, to_tid)
    if not src_dets or not tgt_dets:
        return False

    wrist_frames = load_wrist_frames(stem)
    video_path = find_video_path(stem)
    if video_path is None:
        print(f"  no video for {stem}")
        return False

    src_tail = src_dets[-3:]
    tgt_head = tgt_dets[:3]
    src_last_frame = src_tail[-1][0]
    tgt_first_frame = tgt_head[0][0]
    mid_frame = (src_last_frame + tgt_first_frame) // 2

    pick_frames = (
        [src_dets[max(0, len(src_dets) - 3 + i)][0] for i in range(3)]
        + [mid_frame]
        + [tgt_dets[i][0] for i in range(min(2, len(tgt_dets)))]
    )

    frames = []
    for fr in pick_frames:
        f = read_frame(video_path, fr)
        if f is None:
            return False
        frames.append((fr, f))

    # Draw overlays
    orange = (0, 165, 255)  # BGR
    blue = (255, 0, 0)
    red = (0, 0, 255)
    green = (0, 255, 0)

    rendered = []
    for (fr, img) in frames:
        img = img.copy()
        # Source detections
        for (d_fr, d_x, d_y, d_c) in src_dets:
            if abs(d_fr - fr) <= 2:
                cv2.circle(img, (int(d_x), int(d_y)), 14, orange, 2)
                cv2.putText(img, f"t{from_tid}", (int(d_x) + 16, int(d_y) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, orange, 1, cv2.LINE_AA)
        # Target detections
        for (d_fr, d_x, d_y, d_c) in tgt_dets:
            if abs(d_fr - fr) <= 2:
                cv2.circle(img, (int(d_x), int(d_y)), 14, blue, 2)
                cv2.putText(img, f"t{to_tid}", (int(d_x) + 16, int(d_y) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, blue, 1, cv2.LINE_AA)
        # Wrists
        w = find_closest_wrist(wrist_frames, fr)
        if w:
            for (hand_name, color) in [("left", red), ("right", green)]:
                if hand_name in w:
                    wx, wy = w[hand_name]
                    cv2.circle(img, (int(wx), int(wy)), 12, color, -1)
        # Frame label
        cv2.putText(img, f"f={fr}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
        rendered.append(img)

    # Build 2x3 grid
    h, w = rendered[0].shape[:2]
    grid = np.zeros((h * 2, w * 3, 3), dtype=np.uint8)
    for i, img in enumerate(rendered):
        r = i // 3
        c = i % 3
        grid[r * h:(r + 1) * h, c * w:(c + 1) * w] = img

    # Top text bar
    bar_h = 60
    bar = np.zeros((bar_h, grid.shape[1], 3), dtype=np.uint8)
    title = f"{stem}  {from_tid}->{to_tid}  kind={kind}  V-shape={v_result['classification']}  min_d={v_result['min_hand_dist']:.1f}  ratio={v_result['ratio']:.2f}  hand={v_result['which_hand']}"
    cv2.putText(bar, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    legend2 = f"ORANGE = source (t{from_tid})   BLUE = target (t{to_tid})   RED = left wrist   GREEN = right wrist"
    cv2.putText(bar, legend2, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    canvas = np.vstack([bar, grid])
    cv2.imwrite(str(out_path), canvas)
    return True


def main():
    import json
    with open(WORKTREE / "experiments/hand_occlusion_overnight/h1_hand_pool/data/h14_summary.json") as f:
        data = json.load(f)

    # Find all BALLISTIC edges with V_DEEP / V_SHALLOW (potential hidden catch-throws)
    interesting = [e for e in data["per_edge"] if e["kind"] == "ballistic" and e["classification"] in ("V_DEEP", "V_SHALLOW")]
    print(f"Rendering {len(interesting)} BALLISTIC V_DEEP/V_SHALLOW contact sheets:")

    for e in interesting:
        stem = e["stem"]
        ftid = e["from_tid"]
        ttid = e["to_tid"]
        kind = "ballistic"
        wrist_frames = load_wrist_frames(stem)
        v = v_shape_check({"stem": stem, "from_tid": ftid, "to_tid": ttid, "gap": e["gap"]}, wrist_frames)
        if v is None:
            print(f"  SKIP {ftid}->{ttid} (no v_shape)")
            continue
        # Build filename
        stem_short = stem[:25].replace("/", "_")
        out_path = H14_OUT / f"{stem_short}_{kind}_{ftid}_{ttid}_{e['classification']}.png"
        ok = render_contact_sheet(stem, ftid, ttid, kind, v, out_path)
        if ok:
            print(f"  {ftid}->{ttid} {e['classification']} -> {out_path.name}")
        else:
            print(f"  {ftid}->{ttid} {e['classification']} -> RENDER FAILED")

    # Also render one control case: a reclassified edge (should be V_DEEP) and a flat ballistic
    print("\nControl cases:")
    reclass = [e for e in data["per_edge"] if e["kind"] == "reclassified" and e["classification"] == "V_DEEP"]
    if reclass:
        e = reclass[0]
        wrist_frames = load_wrist_frames(e["stem"])
        v = v_shape_check({"stem": e["stem"], "from_tid": e["from_tid"], "to_tid": e["to_tid"], "gap": e["gap"]}, wrist_frames)
        if v:
            stem_short = e["stem"][:25].replace("/", "_")
            out_path = H14_OUT / f"{stem_short}_reclass_{e['from_tidid'] if 'from_tidid' in e else e['from_tid']}_{e['to_tid']}_V_DEEP.png"
            ok = render_contact_sheet(e["stem"], e["from_tid"], e["to_tid"], "reclassified", v, out_path)
            print(f"  {e['from_tid']}->{e['to_tid']} reclass V_DEEP -> {out_path.name if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
