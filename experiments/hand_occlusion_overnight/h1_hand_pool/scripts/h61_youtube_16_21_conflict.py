#!/usr/bin/env python3
"""H61 - render side-by-side comparison contact sheet for the 16->21 vs
20->21 YouTube conflict.

The H22 episode (2026-08-28) concluded that the YouTube 16->21 edge
in the h7v3pure chain set is WRONG: tracklet 16 ends at f=468 (2
frames BEFORE t20's contact at f=471-473), and the real catch is
t20->t21 (V-shape min_d=5.3 vs t21's start_dist=35.3).

The 2024 manual stitch review (stitch_review_labels.csv) said
16->21 is "correct" (gap=8, prediction_error=194.41).

The h7v3plus3 chain set has the H22-rejected 16->21 edge removed
and the H22-KEPT 20->21 edge admitted (as H22_RECLASSIFIED_HAND_TRANSITION).

H61 renders a side-by-side contact sheet showing BOTH alternatives
for the catch at f=482 (where t21 starts):

- LEFT panel: 16->21 (tracklet 16 ends f=468, tracklet 21 starts f=482)
  showing the trajectory of t16 (f=343-468) and t21 (f=482-512).
- RIGHT panel: 20->21 (tracklet 20 ends f=473, tracklet 21 starts f=482)
  showing the trajectory of t20 (f=466-473) and t21 (f=482-512).

The right wrist position at f=471-473 is also shown as a reference
(where the catch physically happens).

The human can then visually judge: is 16->21 or 20->21 the real
catch+throw?

Outputs:
- contact_sheets_h61/youtube_16to21_vs_20to21.png (side-by-side)
- data/h61_pair_metadata.csv (the metadata for both edges)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_SCRIPTS = H1_DIR / "scripts"
H1_CS = H1_DIR / "contact_sheets_h61"
H1_CS.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(H1_SCRIPTS))
import h7_contact_sheets as h7cs  # type: ignore  # noqa: E402

STEM = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"
VIDEO_PATH = h7cs.VIDEOS_DIR / f"{STEM}.mp4"

# Tracklet metadata for both alternatives
LEFT_PAIR = {
    "label": "16->21 (H22-REJECTED, manual review says correct)",
    "tids": [16, 21],
    "colors": [(200, 200, 200), (0, 220, 220)],  # t16 grey, t21 yellow
    "descs": ["t16 (ends f=468, 2f before t20 contact)",
              "t21 (starts f=482, the catch target)"],
}
RIGHT_PAIR = {
    "label": "20->21 (H22-KEPT, in h7v3plus3 chain set)",
    "tids": [20, 21],
    "colors": [(0, 200, 0), (0, 220, 220)],  # t20 green, t21 yellow
    "descs": ["t20 (ends f=473, canonical contact tracklet)",
              "t21 (starts f=482, the catch target)"],
}

# Key frames
KEY_FRAMES_LEFT = [343, 380, 420, 450, 468, 473, 482, 495]  # t16 + t21
KEY_FRAMES_RIGHT = [466, 469, 471, 473, 482, 495, 510]  # t20 + t21


def render_pair_panel(
    pair: dict,
    frames: list[int],
    title: str,
    out_path: Path,
):
    """Render a single panel showing one alternative pair."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        print(f"Could not open {VIDEO_PATH}")
        return
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ok, first = cap.read()
    if not ok:
        return
    H, W = first.shape[:2]
    tile_w = 320
    tile_h = int(H * tile_w / W)
    cols = len(frames)
    sheet_h = 70 + tile_h + 30  # title + frames + spacer
    sheet_w = cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)
    cv2.putText(sheet, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet,
                "ORANGE=image-LEFT, BLUE=image-RIGHT wrist circles",
                (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                (200, 200, 200), 1, cv2.LINE_AA)

    wrist_frames = h7cs.load_wrist_frames(STEM)
    tids_data = {tid: h7cs.load_tracklet_points(STEM, tid)
                 for tid in pair["tids"]}
    tids_by_f = {tid: {t[0]: t for t in pts}
                 for tid, pts in tids_data.items()}

    for i, fr in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok:
            continue
        img = cv2.resize(img, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        # Wrist circles
        w = h7cs.find_closest_wrist(wrist_frames, fr, max_diff=3)
        if w is not None:
            for tag, color in [("left", h7cs.COLOR_LEFT), ("right", h7cs.COLOR_RIGHT)]:
                x, y, conf = w[tag]
                if conf > 0.1:
                    cx = int(x * tile_w / W)
                    cy = int(y * tile_h / H)
                    cv2.circle(img, (cx, cy), 9, color, 2)
                    cv2.putText(img, tag[0].upper(), (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        # Tracklets
        for tid, color in zip(pair["tids"], pair["colors"]):
            by_f = tids_by_f[tid]
            if fr in by_f:
                f, x, y = by_f[fr]
                cx = int(x * tile_w / W)
                cy = int(y * tile_h / H)
                cv2.circle(img, (cx, cy), 6, color, -1)
                cv2.putText(img, f"t{tid}({x:.0f},{y:.0f})", (cx + 8, cy - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        # Frame label
        cv2.putText(img, f"f={fr}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
        x0 = i * tile_w
        sheet[70:70 + tile_h, x0:x0 + tile_w] = img
    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path}")
    cap.release()


def render_comparison(
    left_panel_path: Path,
    right_panel_path: Path,
    out_path: Path,
):
    """Stack the two panels vertically into a side-by-side comparison."""
    left = cv2.imread(str(left_panel_path))
    right = cv2.imread(str(right_panel_path))
    if left is None or right is None:
        print("Could not load panels for comparison")
        return
    # Pad to same width if needed
    W = max(left.shape[1], right.shape[1])
    if left.shape[1] < W:
        pad = np.full((left.shape[0], W - left.shape[1], 3), 30, dtype=np.uint8)
        left = np.hstack([left, pad])
    if right.shape[1] < W:
        pad = np.full((right.shape[0], W - right.shape[1], 3), 30, dtype=np.uint8)
        right = np.hstack([right, pad])
    H = left.shape[0] + right.shape[0] + 50  # spacer
    combined = np.full((H, W, 3), 30, dtype=np.uint8)
    combined[:left.shape[0], :W] = left
    combined[left.shape[0] + 50:left.shape[0] + 50 + right.shape[0], :W] = right
    cv2.putText(combined,
                "H61 — YouTube 16->21 vs 20->21 catch+throw conflict (which is real?)",
                (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(combined,
                "TOP: 16->21 (H22-rejected; manual review said correct). "
                "BOTTOM: 20->21 (H22-KEPT, in h7v3plus3 chain set).",
                (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.imwrite(str(out_path), combined)
    print(f"Wrote {out_path}")


def main() -> None:
    left_path = H1_CS / f"youtube_16to21_{STEM}_h61.png"
    right_path = H1_CS / f"youtube_20to21_{STEM}_h61.png"
    combined_path = H1_CS / f"youtube_16to21_vs_20to21_{STEM}_h61.png"

    render_pair_panel(
        LEFT_PAIR, KEY_FRAMES_LEFT,
        title=f"{LEFT_PAIR['label']} — f={KEY_FRAMES_LEFT[0]} to {KEY_FRAMES_LEFT[-1]}",
        out_path=left_path,
    )
    render_pair_panel(
        RIGHT_PAIR, KEY_FRAMES_RIGHT,
        title=f"{RIGHT_PAIR['label']} — f={KEY_FRAMES_RIGHT[0]} to {KEY_FRAMES_RIGHT[-1]}",
        out_path=right_path,
    )
    render_comparison(left_path, right_path, combined_path)

    # Metadata CSV
    (H1_DATA / "h61_pair_metadata.csv").write_text(
        "alternative,from_tid,to_tid,from_end_frame,to_start_frame,gap_frames,"
        "v_shape_min_d,target_start_dist,in_h7v3plus3,in_manual_review,manual_label,"
        "h22_verdict,notes\n"
        "16->21 (REJECTED),16,21,468,482,14,?,35.3,False,True,correct,WRONG (tracklet 16 ends 2f before t20 contact),H22 said 16->21 is wrong\n"
        "20->21 (KEPT),20,21,473,482,9,5.3,35.3,True,False,not_in_review,CORRECT (canonical contact),H22 KEPT 20->21 in h7v3plus3\n"
    )
    print(f"Wrote {H1_DATA / 'h61_pair_metadata.csv'}")


if __name__ == "__main__":
    main()
