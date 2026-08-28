#!/usr/bin/env python3
"""H122 contact sheets: visual QA of representative RAW_REJECTS cases.

Goal: characterize the false-positive rate of H7v2 reclassification
by visually inspecting a sample of edges where tracklet_features-based
H7v2 said "reclassify" but raw data would say "don't reclassify".

Selection: 5 cases spanning both videos, diverse structural signatures:
  - identical 22->27: very large orig jump (190 px), tiny raw jump (37 px)
  - identical 3->8: large orig jump (227 px), orig slope -23.6 descending,
                    raw slope +21.3 ascending (very strong)
  - identical 64->68: orig slope +8.0 ascending, raw slope +13.2 ascending
  - youtube 1->9: orig slope -11.7 (H7v2 catch), raw slope +11.2 ascending
  - youtube 17->24: orig slope -4.9 (H7v2 catch), raw slope +10.2 ascending
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h122"
CONTACT_SHEETS_OUT.mkdir(parents=True, exist_ok=True)

# (stem, src_tid, tgt_tid, src_last_frame_feat, src_last_frame_raw,
#  src_end_slope_feat, src_end_slope_raw, src_last_xy_feat, src_last_xy_raw)
CASES = [
    # 22->27: the H112-discovered FP. orig_jump=190, raw_jump=37
    ("identical_balls_trick_000_018", 22, 27, 252, 257, -7.84, 30.65),
    # 3->8: the H120-suspect edge. orig_slope=-23.6, raw_slope=+21.3
    ("identical_balls_trick_000_018", 3, 8, 31, 36, -23.59, 21.27),
    # 64->68: orig_slope=+7.98, raw_slope=+13.25 (both ascending)
    ("identical_balls_trick_000_018", 64, 68, 964, 969, 7.98, 13.25),
    # 1->9 (YouTube): orig_slope=-11.66, raw_slope=+11.19 (flip sign)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 1, 9, 102, 107, -11.66, 11.19),
    # 17->24 (YouTube): orig_slope=-4.91, raw_slope=+10.25 (flip sign)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 17, 24, 582, 585, -4.91, 10.25),
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


def load_raw_tracklet(stem, tid):
    """Load raw (frame, x, y) points for a tracklet."""
    raw_path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    pts = []
    with raw_path.open() as f:
        for row in csv.DictReader(f):
            if int(row["track_id"]) == tid:
                pts.append((int(row["frame"]), float(row["center_x"]), float(row["center_y"])))
    pts.sort()
    return pts


def load_pose(stem, frame):
    """Load left/right wrist positions at a given frame."""
    pose_file = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not pose_file.exists():
        return None, None
    try:
        with pose_file.open() as f:
            for row in csv.DictReader(f):
                if int(row["frame"]) == frame:
                    lw = (float(row["left_wrist_x"]), float(row["left_wrist_y"]))
                    rw = (float(row["right_wrist_x"]), float(row["right_wrist_y"]))
                    return lw, rw
    except (OSError, KeyError, ValueError):
        pass
    return None, None


def make_contact_sheet(
    src_pts, tgt_pts,
    src_first_frame, src_last_frame_raw, src_last_frame_feat,
    src_first_xy, src_last_xy_raw, src_last_xy_feat,
    tgt_first_frame, tgt_last_frame,
    tgt_first_xy, tgt_last_xy,
    title, out_path,
    wrist_l_feat, wrist_r_feat, wrist_l_raw, wrist_r_raw,
    end_slope_feat, end_slope_raw,
    sj_feat, sj_raw, in_h7v3plus3, stem, src_tid, tgt_tid,
):
    from PIL import Image, ImageDraw, ImageFont

    all_xs = [src_first_xy[0], src_last_xy_feat[0], src_last_xy_raw[0], tgt_first_xy[0], tgt_last_xy[0]]
    all_ys = [src_first_xy[1], src_last_xy_feat[1], src_last_xy_raw[1], tgt_first_xy[1], tgt_last_xy[1]]
    for w in [wrist_l_feat, wrist_r_feat, wrist_l_raw, wrist_r_raw]:
        if w:
            all_xs.append(w[0])
            all_ys.append(w[1])
    min_x, max_x = min(all_xs) - 80, max(all_xs) + 80
    min_y, max_y = min(all_ys) - 80, max(all_ys) + 80

    pad = 30
    plot_w = 800
    plot_h = int(plot_w * (max_y - min_y) / (max_x - min_x)) if (max_x > min_x) else 600
    canvas_w = plot_w + 2 * pad
    canvas_h = plot_h + 2 * pad + 200

    sheet = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    draw.text((pad, 5), title, fill="black", font=font)

    def plot_xy(x, y):
        px = pad + (x - min_x) / (max_x - min_x) * plot_w
        py = pad + (y - min_y) / (max_y - min_y) * plot_h
        return (px, py)

    draw.rectangle([pad, pad, pad + plot_w, pad + plot_h], outline="gray")

    # Wrists at feat midpoint (orange = L, blue = R)
    if wrist_l_feat:
        wl = plot_xy(wrist_l_feat[0], wrist_l_feat[1])
        draw.ellipse([wl[0] - 12, wl[1] - 12, wl[0] + 12, wl[1] + 12],
                     outline="orange", width=2)
        draw.text((wl[0] + 14, wl[1] - 6), "L (feat)", fill="orange", font=font_small)
    if wrist_r_feat:
        wr = plot_xy(wrist_r_feat[0], wrist_r_feat[1])
        draw.ellipse([wr[0] - 12, wr[1] - 12, wr[0] + 12, wr[1] + 12],
                     outline="blue", width=2)
        draw.text((wr[0] + 14, wr[1] - 6), "R (feat)", fill="blue", font=font_small)
    if wrist_l_raw:
        wl = plot_xy(wrist_l_raw[0], wrist_l_raw[1])
        draw.ellipse([wl[0] - 12, wl[1] - 12, wl[0] + 12, wl[1] + 12],
                     outline="orange", width=1)
    if wrist_r_raw:
        wr = plot_xy(wrist_r_raw[0], wrist_r_raw[1])
        draw.ellipse([wr[0] - 12, wr[1] - 12, wr[0] + 12, wr[1] + 12],
                     outline="blue", width=1)

    # Source raw trajectory
    if len(src_pts) >= 2:
        for i in range(1, len(src_pts)):
            p1 = plot_xy(src_pts[i - 1][1], src_pts[i - 1][2])
            p2 = plot_xy(src_pts[i][1], src_pts[i][2])
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill="red", width=1)

    # Target raw trajectory
    if len(tgt_pts) >= 2:
        for i in range(1, len(tgt_pts)):
            p1 = plot_xy(tgt_pts[i - 1][1], tgt_pts[i - 1][2])
            p2 = plot_xy(tgt_pts[i][1], tgt_pts[i][2])
            draw.line([p1[0], p1[1], p2[0], p2[1]], fill="blue", width=1)

    # Source start/end
    p_sf = plot_xy(src_first_xy[0], src_first_xy[1])
    p_sl_feat = plot_xy(src_last_xy_feat[0], src_last_xy_feat[1])
    p_sl_raw = plot_xy(src_last_xy_raw[0], src_last_xy_raw[1])
    draw.ellipse([p_sf[0] - 6, p_sf[1] - 6, p_sf[0] + 6, p_sf[1] + 6], fill="darkred")
    draw.ellipse([p_sl_feat[0] - 5, p_sl_feat[1] - 5, p_sl_feat[0] + 5, p_sl_feat[1] + 5],
                 outline="darkred", width=2)
    draw.ellipse([p_sl_raw[0] - 5, p_sl_raw[1] - 5, p_sl_raw[0] + 5, p_sl_raw[1] + 5],
                 outline="darkred", width=3)
    draw.text((p_sf[0] + 6, p_sf[1] - 5), f"src_start f={src_first_frame}",
              fill="black", font=font_small)
    draw.text((p_sl_feat[0] + 6, p_sl_feat[1] - 5),
              f"src_end (feat) f={src_last_frame_feat}",
              fill="darkred", font=font_small)
    draw.text((p_sl_raw[0] + 6, p_sl_raw[1] + 6),
              f"src_end (raw) f={src_last_frame_raw}",
              fill="darkred", font=font_small)

    # Target start/end
    p_tf = plot_xy(tgt_first_xy[0], tgt_first_xy[1])
    p_tl = plot_xy(tgt_last_xy[0], tgt_last_xy[1])
    draw.ellipse([p_tf[0] - 6, p_tf[1] - 6, p_tf[0] + 6, p_tf[1] + 6], fill="darkblue")
    draw.ellipse([p_tl[0] - 5, p_tl[1] - 5, p_tl[0] + 5, p_tl[1] + 5],
                 outline="darkblue", width=2)
    draw.text((p_tf[0] + 6, p_tf[1] - 5),
              f"tgt_start f={tgt_first_frame}",
              fill="black", font=font_small)
    draw.text((p_tl[0] + 6, p_tl[1] - 5), f"tgt_end f={tgt_last_frame}",
              fill="darkblue", font=font_small)

    # Spatial jumps
    draw.line([p_sl_feat[0], p_sl_feat[1], p_tf[0], p_tf[1]], fill="gray", width=1)
    draw.line([p_sl_raw[0], p_sl_raw[1], p_tf[0], p_tf[1]], fill="magenta", width=2)
    midx = (p_sl_raw[0] + p_tf[0]) / 2
    midy = (p_sl_raw[1] + p_tf[1]) / 2
    draw.text((midx, midy - 30),
              f"feat_jump: {sj_feat:.1f}px (gray)\nraw_jump: {sj_raw:.1f}px (magenta)\ngap: {tgt_first_frame - src_last_frame_feat}f",
              fill="black", font=font_small)

    # Bottom text
    vy = pad + 30 + plot_h + 10
    draw.text((pad, vy),
              f"src end_slope: feat={end_slope_feat:.2f} raw={end_slope_raw:.2f}  "
              f"(H7v2 says feat is 'catch' iff slope<-1.0)",
              fill="darkred", font=font_small)
    draw.text((pad, vy + 18),
              f"in_h7v3plus3={in_h7v3plus3} (RECLASSIFIED_HAND_TRANSITION)",
              fill="black", font=font_small)
    draw.text((pad, vy + 36),
              "QUESTION: at the raw last frame, is the source tracklet 'descending into hand' (catch) "
              "or 'ascending away from hand' (post-throw)?",
              fill="black", font=font_small)

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def main():
    tf = load_tracklet_features()

    for case in CASES:
        stem, src_tid, tgt_tid, src_last_frame_feat, src_last_frame_raw, end_slope_feat, end_slope_raw = case
        src_f = tf.get((stem, src_tid))
        tgt_f = tf.get((stem, tgt_tid))
        if not src_f or not tgt_f:
            print(f"  missing features for {stem} {src_tid}->{tgt_tid}")
            continue

        src_pts = load_raw_tracklet(stem, src_tid)
        tgt_pts = load_raw_tracklet(stem, tgt_tid)
        if not src_pts or not tgt_pts:
            print(f"  missing raw data for {stem} {src_tid}->{tgt_tid}")
            continue

        # Raw last xy at frame src_last_frame_raw
        raw_at = next((p for p in src_pts if p[0] == src_last_frame_raw), None)
        if raw_at is None:
            # nearest
            raw_at = min(src_pts, key=lambda p: abs(p[0] - src_last_frame_raw))
        src_last_xy_raw = (raw_at[1], raw_at[2])
        src_last_xy_feat = (src_f["last_x"], src_f["last_y"])

        # Wrists at feat midpoint and raw midpoint
        gap_mid_feat = (src_f["last_frame"] + tgt_f["first_frame"]) // 2
        gap_mid_raw = (src_last_frame_raw + tgt_f["first_frame"]) // 2
        wrist_l_feat, wrist_r_feat = load_pose(stem, gap_mid_feat)
        wrist_l_raw, wrist_r_raw = load_pose(stem, gap_mid_raw)

        # Spatial jumps
        sj_feat = math.hypot(tgt_f["first_x"] - src_f["last_x"], tgt_f["first_y"] - src_f["last_y"])
        sj_raw = math.hypot(tgt_f["first_x"] - src_last_xy_raw[0], tgt_f["first_y"] - src_last_xy_raw[1])

        in_chain = True  # all H121 cases are in h7v3plus3 (RECLASSIFIED)

        title = f"H122 RAW_REJECTS: {stem} {src_tid}->{tgt_tid}"
        out_path = CONTACT_SHEETS_OUT / f"h122_{stem}_{src_tid}_{tgt_tid}.png"
        make_contact_sheet(
            src_pts, tgt_pts,
            src_f["first_frame"], src_last_frame_raw, src_f["last_frame"],
            (src_f["first_x"], src_f["first_y"]),
            src_last_xy_raw, src_last_xy_feat,
            tgt_f["first_frame"], tgt_f["last_frame"],
            (tgt_f["first_x"], tgt_f["first_y"]),
            (tgt_f["last_x"], tgt_f["last_y"]),
            title, out_path,
            wrist_l_feat, wrist_r_feat, wrist_l_raw, wrist_r_raw,
            end_slope_feat, end_slope_raw,
            sj_feat, sj_raw, in_chain, stem, src_tid, tgt_tid,
        )


if __name__ == "__main__":
    main()
