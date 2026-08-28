"""H114 contact sheets: PIL-based trajectory plots for the most informative cases.

Uses the tracklet_features.csv last_x/last_y and first_x/first_y endpoints to
build simple 2D trajectory diagrams. No video decoding required.

Cases:
1. 14->18 (wrong, NOT in chain, sj=321) — H114 prototype wrong edge
2. 3->8 (correct, IN chain, sj=227, RECLASSIFIED_HAND_TRANSITION) — H112-style
   anti-prototype (catch-throw with ball-not-at-hand)
3. 7->10 (correct, IN chain, sj=156, H26_RECLASSIFIED) — H26-discovered
   V_SHALLOW catch-throw
4. 65->69 (wrong, NOT in chain, sj=230) — same-hand wrong edge
"""
from __future__ import annotations
import csv
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h114"
CONTACT_SHEETS_OUT.mkdir(exist_ok=True)

# (stem, src_tid, tgt_tid, gap, end_d, start_d, sj, verdict, end_x, end_y, start_x, start_y)
CASES = [
    ("identical_balls_trick_000_018", 14, 18, 0, 52.69, 288.8, 321.47, "WRONG_not_in_chain"),
    ("identical_balls_trick_000_018", 3, 8, 6, 106.16, 71.47, 227.01, "CORRECT_in_chain_RECLASSIFIED"),
    ("identical_balls_trick_000_018", 7, 10, 2, 50.14, 71.95, 156.10, "CORRECT_in_chain_H26"),
    ("identical_balls_trick_000_018", 65, 69, 1, 242.74, 75.57, 230.64, "WRONG_not_in_chain"),
]

# Load tracklet features
tf = {}
with (H1_DATA / "tracklet_features.csv").open() as f:
    for row in csv.DictReader(f):
        key = (row["stem"], int(row["tid"]))
        tf[key] = {
            "end_dist": float(row["end_dist"]) if row["end_dist"] else None,
            "start_dist": float(row["start_dist"]) if row["start_dist"] else None,
            "end_side": row["end_side"] or None,
            "start_side": row["start_side"] or None,
            "last_x": float(row["last_x"]),
            "last_y": float(row["last_y"]),
            "first_x": float(row["first_x"]),
            "first_y": float(row["first_y"]),
            "last_frame": int(row["last_frame"]),
            "first_frame": int(row["first_frame"]),
        }

# Build a 6-panel contact sheet for each case
PANEL_W, PANEL_H = 320, 240
COLS, ROWS = 3, 2
SHEET_W = COLS * PANEL_W
SHEET_H = ROWS * PANEL_H + 60  # 60px title bar

# Get image canvas dimensions
EXAMPLE = tf.get(("identical_balls_trick_000_018", 1))
IMG_W, IMG_H = 1280, 720  # typical for this video


def draw_panel(panel_idx, frame_idx, src_xy, tgt_xy, sj, src_label, tgt_label, is_src_frame, is_tgt_frame):
    img = Image.new("RGB", (PANEL_W, PANEL_H), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw axes
    draw.line([(10, PANEL_H - 10), (PANEL_W - 10, PANEL_H - 10)], fill=(0, 0, 0))
    draw.line([(10, 10), (10, PANEL_H - 10)], fill=(0, 0, 0))

    # Title
    title = f"Frame f={frame_idx}"
    draw.text((10, 10), title, fill=(0, 0, 0))

    # Mark src endpoint if this is the src-end frame
    if is_src_frame and src_xy is not None:
        # Map (x, y) to panel coordinates. Image: (0,0)=top-left, (W, H)=bottom-right
        # Panel: (10,10)=top-left, (W-10, H-10)=bottom-right
        px = 10 + (src_xy[0] / IMG_W) * (PANEL_W - 20)
        py = 10 + (src_xy[1] / IMG_H) * (PANEL_H - 30)
        # Draw a circle and label
        r = 8
        draw.ellipse([(px - r, py - r), (px + r, py + r)], outline=(0, 100, 0), width=3)
        draw.text((px + 12, py), f"src (t={src_label})", fill=(0, 100, 0))

    # Mark tgt startpoint if this is the tgt-start frame
    if is_tgt_frame and tgt_xy is not None:
        px = 10 + (tgt_xy[0] / IMG_W) * (PANEL_W - 20)
        py = 10 + (tgt_xy[1] / IMG_H) * (PANEL_H - 30)
        r = 8
        draw.ellipse([(px - r, py - r), (px + r, py + r)], outline=(150, 0, 0), width=3)
        draw.text((px + 12, py), f"tgt (t={tgt_label})", fill=(150, 0, 0))

    return img


def render_case(stem, src_tid, tgt_tid, gap, end_d, start_d, sj, verdict):
    src_f = tf.get((stem, src_tid))
    tgt_f = tf.get((stem, tgt_tid))
    if src_f is None or tgt_f is None:
        print(f"  ({src_tid}->{tgt_tid}): tracklet features not found")
        return None

    f_src_end = src_f["last_frame"]
    f_tgt_start = tgt_f["first_frame"]
    f_gap_mid = (f_src_end + f_tgt_start) // 2

    panel_frames = [
        max(0, f_src_end - 3),
        max(0, f_src_end - 1),
        f_src_end,
        f_gap_mid,
        f_tgt_start,
        f_tgt_start + 3,
    ]

    src_xy = (src_f["last_x"], src_f["last_y"])
    tgt_xy = (tgt_f["first_x"], tgt_f["first_y"])

    # Build grid
    grid = Image.new("RGB", (SHEET_W, SHEET_H), (255, 255, 255))
    for i, f_idx in enumerate(panel_frames):
        r, c = i // COLS, i % COLS
        is_src_frame = (f_idx == f_src_end)
        is_tgt_frame = (f_idx == f_tgt_start)
        panel = draw_panel(
            i, f_idx, src_xy, tgt_xy, sj, str(src_tid), str(tgt_tid), is_src_frame, is_tgt_frame
        )
        grid.paste(panel, (c * PANEL_W, 60 + r * PANEL_H))

    # Title bar
    draw = ImageDraw.Draw(grid)
    title = (f"H114: {stem} {src_tid}->{tgt_tid} gap={gap}  "
             f"{verdict}  sj={sj:.1f}  end_d={end_d}  start_d={start_d}")
    draw.text((10, 20), title, fill=(0, 0, 0))

    out_name = f"h114_{src_tid}_{tgt_tid}_{verdict[:6]}.png"
    out_path = CONTACT_SHEETS_OUT / out_name
    grid.save(out_path)
    print(f"  Wrote {out_path}")
    return out_path


for case in CASES:
    print(f"Rendering {case[1]}->{case[2]} ({case[-1]})...")
    render_case(*case)

print()
print("Done.")
