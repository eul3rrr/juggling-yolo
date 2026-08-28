#!/usr/bin/env python3
"""H120 contact sheets: visual QA of 7 NEW H120 v2 fires (not in H114 strict).

Selection: 7 cases that fire Rule B (cross-hand handoff) but NOT Rule A
(H114 v1 strict). All have spatial_jump < 200 (below H114 strict) and
cross-hand transition (R->L or L->R) with min(end_d, start_d) > 30.

Cases (all on identical_balls_trick_000_018):
  e6c_not_in_h7v2: 14->19, 25->26
  adjacent_vshape: 1->8, 10->12, 15->19, 63->68, 70->73

Hypothesis: Rule B (cross-hand handoff with both endpoints > 30 px and
spatial_jump 100-200) should be a useful additional signal for cross-ball
tracker artifacts that the H114 v1 strict rule (which requires BOTH endpoints
> 25 AND spatial_jump > 200) misses because the spatial_jump is too small.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h120"
CONTACT_SHEETS_OUT.mkdir(parents=True, exist_ok=True)

# (stem, src_tid, tgt_tid, vshape, in_h7v3plus3, kind, sj, end_d, start_d, end_side, start_side)
CASES = [
    # e6c_not_in_h7v2
    ("identical_balls_trick_000_018", 14, 19, "V_SHALLOW", False, "e6c_not_in_h7v2", 102.76, 52.69, 68.92, "right", "left"),
    ("identical_balls_trick_000_018", 25, 26, "V_DEEP", False, "e6c_not_in_h7v2", 132.81, 64.9, 42.28, "right", "left"),
    # adjacent_vshape
    ("identical_balls_trick_000_018", 1, 8, "V_SHALLOW", False, "adjacent_vshape", 172.57, 77.85, 71.47, "right", "left"),
    ("identical_balls_trick_000_018", 10, 12, "V_SHALLOW", False, "adjacent_vshape", 166.19, 87.39, 119.4, "right", "left"),
    ("identical_balls_trick_000_018", 15, 19, "V_DEEP", False, "adjacent_vshape", 124.93, 38.27, 68.92, "right", "left"),
    ("identical_balls_trick_000_018", 63, 68, "V_DEEP", False, "adjacent_vshape", 181.87, 63.06, 36.23, "left", "right"),
    ("identical_balls_trick_000_018", 70, 73, "V_DEEP", False, "adjacent_vshape", 199.1, 33.94, 51.71, "left", "right"),
]


def load_tracklet_features():
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
                "n_pts": int(row["n_pts"]),
            }
    return tf


def load_pose(stem: str, frame: int):
    """Load left/right wrist positions at a given frame from production pose CSV."""
    pose_file = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not pose_file.exists():
        return None, None
    try:
        with pose_file.open() as f:
            r = csv.DictReader(f)
            for row in r:
                if int(row["frame"]) == frame:
                    lw = (float(row["left_wrist_x"]), float(row["left_wrist_y"]))
                    rw = (float(row["right_wrist_x"]), float(row["right_wrist_y"]))
                    return lw, rw
    except (OSError, KeyError, ValueError):
        pass
    return None, None


def make_contact_sheet(
    src_tid, tgt_tid,
    src_first_frame, src_last_frame,
    src_first_xy, src_last_xy,
    tgt_first_frame, tgt_last_frame,
    tgt_first_xy, tgt_last_xy,
    title, out_path,
    wrist_l, wrist_r,
    end_d_l, end_d_r, start_d_l, start_d_r,
    vshape, in_h7v3plus3, sj, end_d, start_d, kind, end_side, start_side,
):
    from PIL import Image, ImageDraw, ImageFont

    all_xs = [src_first_xy[0], src_last_xy[0], tgt_first_xy[0], tgt_last_xy[0]]
    all_ys = [src_first_xy[1], src_last_xy[1], tgt_first_xy[1], tgt_last_xy[1]]
    if wrist_l:
        all_xs.append(wrist_l[0])
        all_ys.append(wrist_l[1])
    if wrist_r:
        all_xs.append(wrist_r[0])
        all_ys.append(wrist_r[1])
    min_x, max_x = min(all_xs) - 80, max(all_xs) + 80
    min_y, max_y = min(all_ys) - 80, max(all_ys) + 80

    pad = 30
    plot_w = 800
    plot_h = int(plot_w * (max_y - min_y) / (max_x - min_x)) if (max_x > min_x) else 600
    canvas_w = plot_w + 2 * pad
    canvas_h = plot_h + 2 * pad + 100

    sheet = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    draw.text((pad, 5), title, fill="black", font=font)

    def plot_xy(x, y):
        px = pad + (x - min_x) / (max_x - min_x) * plot_w
        py = pad + (y - min_y) / (max_y - min_y) * plot_h
        return (px, py)

    draw.rectangle([pad, pad, pad + plot_w, pad + plot_h], outline="gray")

    if wrist_l:
        wl = plot_xy(wrist_l[0], wrist_l[1])
        draw.ellipse([wl[0] - 14, wl[1] - 14, wl[0] + 14, wl[1] + 14],
                     outline="orange", width=3)
        draw.ellipse([wl[0] - 4, wl[1] - 4, wl[0] + 4, wl[1] + 4],
                     fill="orange")
        draw.text((wl[0] + 18, wl[1] - 6), "L", fill="orange", font=font_small)
    if wrist_r:
        wr = plot_xy(wrist_r[0], wrist_r[1])
        draw.ellipse([wr[0] - 14, wr[1] - 14, wr[0] + 14, wr[1] + 14],
                     outline="blue", width=3)
        draw.ellipse([wr[0] - 4, wr[1] - 4, wr[0] + 4, wr[1] + 4],
                     fill="blue")
        draw.text((wr[0] + 18, wr[1] - 6), "R", fill="blue", font=font_small)

    p_sf = plot_xy(src_first_xy[0], src_first_xy[1])
    p_sl = plot_xy(src_last_xy[0], src_last_xy[1])
    draw.ellipse([p_sf[0] - 7, p_sf[1] - 7, p_sf[0] + 7, p_sf[1] + 7], fill="red")
    draw.line([p_sf[0], p_sf[1], p_sl[0], p_sl[1]], fill="red", width=2)
    draw.ellipse([p_sl[0] - 5, p_sl[1] - 5, p_sl[0] + 5, p_sl[1] + 5], outline="red", width=2)
    draw.text(
        (p_sf[0] + 8, p_sf[1] - 5),
        f"src_start f={src_first_frame}",
        fill="black", font=font_small,
    )
    draw.text(
        (p_sl[0] + 8, p_sl[1] - 5),
        f"src_end f={src_last_frame}\nside={end_side}\nd_l={end_d_l:.1f} d_r={end_d_r:.1f}",
        fill="red", font=font_small,
    )

    p_tf = plot_xy(tgt_first_xy[0], tgt_first_xy[1])
    p_tl = plot_xy(tgt_last_xy[0], tgt_last_xy[1])
    draw.ellipse([p_tf[0] - 7, p_tf[1] - 7, p_tf[0] + 7, p_tf[1] + 7], fill="blue")
    draw.line([p_tf[0], p_tf[1], p_tl[0], p_tl[1]], fill="blue", width=2)
    draw.ellipse([p_tl[0] - 5, p_tl[1] - 5, p_tl[0] + 5, p_tl[1] + 5], outline="blue", width=2)
    draw.text(
        (p_tf[0] + 8, p_tf[1] - 5),
        f"tgt_start f={tgt_first_frame}\nside={start_side}\nd_l={start_d_l:.1f} d_r={start_d_r:.1f}",
        fill="black", font=font_small,
    )
    draw.text((p_tl[0] + 8, p_tl[1] - 5), f"tgt_end f={tgt_last_frame}", fill="blue", font=font_small)

    draw.line([p_sl[0], p_sl[1], p_tf[0], p_tf[1]], fill="red", width=1)
    actual_jump = math.hypot(tgt_first_xy[0] - src_last_xy[0], tgt_first_xy[1] - src_last_xy[1])
    midx = (p_sl[0] + p_tf[0]) / 2
    midy = (p_sl[1] + p_tf[1]) / 2
    draw.text(
        (midx, midy - 25),
        f"jump: {actual_jump:.1f}px\ngap: {tgt_first_frame - src_last_frame}f",
        fill="red", font=font_small,
    )

    vy = pad + 30 + plot_h + 10
    verdict_text = (
        f"H120 v2 Rule B FIRES (cross-hand handoff, sj<200, both > 30 px).  "
        f"kind={kind}.  sj={sj:.1f}  end_d={end_d:.1f}  start_d={start_d:.1f}.  "
        f"sides: {end_side}->{start_side}.  vshape={vshape}.  in_h7v3plus3={in_h7v3plus3}."
    )
    draw.text((pad, vy), verdict_text, fill="darkred", font=font_small)
    draw.text(
        (pad, vy + 20),
        "QUESTION: is this a real catch-throw (cross-hand), or a cross-ball tracker artifact?",
        fill="black", font=font_small,
    )

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def main():
    tf = load_tracklet_features()

    for case in CASES:
        stem, src_tid, tgt_tid, vshape, in_chain, kind, sj, end_d, start_d, end_side, start_side = case
        src_f = tf.get((stem, src_tid))
        tgt_f = tf.get((stem, tgt_tid))
        if not src_f or not tgt_f:
            print(f"  missing features for {stem} {src_tid}->{tgt_tid}")
            continue

        gap_mid = (src_f["last_frame"] + tgt_f["first_frame"]) // 2
        wrist_l, wrist_r = load_pose(stem, gap_mid)

        if wrist_l and wrist_r:
            end_d_l = math.hypot(src_f["last_x"] - wrist_l[0], src_f["last_y"] - wrist_l[1])
            end_d_r = math.hypot(src_f["last_x"] - wrist_r[0], src_f["last_y"] - wrist_r[1])
            start_d_l = math.hypot(tgt_f["first_x"] - wrist_l[0], tgt_f["first_y"] - wrist_l[1])
            start_d_r = math.hypot(tgt_f["first_x"] - wrist_r[0], tgt_f["first_y"] - wrist_r[1])
        else:
            end_d_l = end_d_r = start_d_l = start_d_r = 0.0

        title = f"H120 v2 NEW (B only): {stem} {src_tid}->{tgt_tid}  ({vshape}, {kind}, gap={tgt_f['first_frame'] - src_f['last_frame']})"
        out_path = CONTACT_SHEETS_OUT / f"h120v2_{stem}_{src_tid}_{tgt_tid}.png"
        make_contact_sheet(
            src_tid, tgt_tid,
            src_f["first_frame"], src_f["last_frame"],
            (src_f["first_x"], src_f["first_y"]),
            (src_f["last_x"], src_f["last_y"]),
            tgt_f["first_frame"], tgt_f["last_frame"],
            (tgt_f["first_x"], tgt_f["first_y"]),
            (tgt_f["last_x"], tgt_f["last_y"]),
            title, out_path,
            wrist_l, wrist_r,
            end_d_l, end_d_r, start_d_l, start_d_r,
            vshape, in_chain, sj, end_d, start_d, kind, end_side, start_side,
        )


if __name__ == "__main__":
    main()
