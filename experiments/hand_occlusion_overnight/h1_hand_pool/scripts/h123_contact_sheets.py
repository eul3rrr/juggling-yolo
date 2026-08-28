#!/usr/bin/env python3
"""H123 contact sheets: enlarged visual QA of H121 RAW_REJECTS cases.

Goal: tighten the H122 80% precision bound by visual QA of 10 more
RAW_REJECTS (2 identical + 8 YouTube). The 2 remaining identical
RAW_REJECTS are 40->41 and 43->45; the 8 YouTube cases are
stratified across diverse structural signatures (raw_end_dist,
raw_end_slope, sj_raw, feat_n_pts).

Selection rationale:
- 40->41 (identical, n_pts=33): the only longer identical RAW_REJECTS.
  raw_end_slope=-0.31 (nearly stationary). H7v2's "catch" signature
  was triggered by feat_end_slope=-1.39.
- 43->45 (identical, n_pts=2): the shortest RAW_REJECTS. Catch/throw
  signature is noise from 4 raw points.
- 2->8, 9->13, 22->26, 26->31 (YouTube): high raw_end_dist (51-67)
  and high sj_raw (112-152). The "edge looks like a cross-hand
  handoff at the raw scale" cases.
- 14->17 (YouTube): the only RAW_REJECTS with raw_end_slope negative
  (-0.21, nearly stationary at end). Tests a different signature.
- 3->6, 30->37, 33->36 (YouTube): small sj_raw (49-81). The
  "spatially small but catch signature lost" cases.

The stratified sample is intentionally diverse to test whether the
H122 80% precision holds across different failure modes.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h123"
CONTACT_SHEETS_OUT.mkdir(parents=True, exist_ok=True)

# (stem, src_tid, tgt_tid, src_last_frame_feat, src_last_frame_raw,
#  src_end_slope_feat, src_end_slope_raw, selection_rationale)
CASES = [
    # === identical (2 remaining RAW_REJECTS) ===
    # 40->41: only longer identical RAW_REJECTS; n_pts=33, raw_end_slope=-0.31 (stationary)
    ("identical_balls_trick_000_018", 40, 41, 582, 587, -1.39, -0.31,
     "only longer identical RAW_REJECTS, stationary at end"),
    # 43->45: shortest RAW_REJECTS (n_pts=2); signature is noise
    ("identical_balls_trick_000_018", 43, 45, 622, 626, None, -0.36,
     "shortest RAW_REJECTS, catch/throw signature is noise"),

    # === YouTube (8 stratified) ===
    # 2->8: high raw_end_dist (54.8), high sj_raw (121.2)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 8, 72, 77, 0.92, 6.89,
     "high raw_d 54.8, high sj_raw 121.2 (cross-hand handoff?)"),
    # 3->6: small sj_raw (49.0), medium raw_d (31.6)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 3, 6, 22, 27, 0.95, 10.04,
     "small sj_raw 49.0 (spatially small but signature lost)"),
    # 9->13: high raw_d (66.9), high sj_raw (119.8)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 9, 13, 256, 261, 1.75, 8.65,
     "high raw_d 66.9, high sj_raw 119.8"),
    # 14->17: only RAW_REJECTS with raw_end_slope negative (-0.21)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 14, 17, 375, 379, 2.15, -0.21,
     "only negative raw_end_slope (-0.21) RAW_REJECTS"),
    # 22->26: medium sj_raw (112.3)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 22, 26, 644, 649, -0.29, 7.32,
     "medium sj_raw 112.3, large feat->raw jump in dist (10.6->51.5)"),
    # 26->31: largest sj_raw (152.1)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 26, 31, 717, 722, 0.94, 6.49,
     "largest sj_raw 152.1 (cross-hand handoff at raw scale)"),
    # 30->37: small sj_raw (81.3), high feat_n_pts (119)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 30, 37, 845, 850, 1.09, 6.74,
     "small sj_raw 81.3, long source tracklet (119 pts)"),
    # 33->36: small sj_raw (62.5), high feat_end_dist (24.95)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 33, 36, 818, 820, 2.94, 7.83,
     "small sj_raw 62.5, high feat_end_dist 24.95 (right at threshold)"),
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
    selection_rationale,
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
    canvas_h = plot_h + 2 * pad + 220

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
        draw.ellipse([wl[0] - 8, wl[1] - 8, wl[0] + 8, wl[1] + 8],
                     outline="orange", width=1)
    if wrist_r_raw:
        wr = plot_xy(wrist_r_raw[0], wrist_r_raw[1])
        draw.ellipse([wr[0] - 8, wr[1] - 8, wr[0] + 8, wr[1] + 8],
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
    feat_s_text = f"{end_slope_feat:.2f}" if end_slope_feat is not None else "n/a"
    draw.text((pad, vy),
              f"src end_slope: feat={feat_s_text} raw={end_slope_raw:.2f}  "
              f"(H7v2 says feat is 'catch' iff slope<-1.0)",
              fill="darkred", font=font_small)
    draw.text((pad, vy + 18),
              f"in_h7v3plus3={in_h7v3plus3} (RECLASSIFIED_HAND_TRANSITION)",
              fill="black", font=font_small)
    draw.text((pad, vy + 36),
              f"Rationale: {selection_rationale}",
              fill="black", font=font_small)
    draw.text((pad, vy + 56),
              "QUESTION: at the raw last frame, is the source tracklet 'descending into hand' (catch) "
              "or 'ascending away from hand' (post-throw)?",
              fill="black", font=font_small)
    draw.text((pad, vy + 74),
              "QUESTION: does the source tracklet contain a V-shape (descent then ascent) within a single tracklet?",
              fill="black", font=font_small)
    draw.text((pad, vy + 92),
              "QUESTION: is this a real catch-throw transition or a tracker artifact?",
              fill="black", font=font_small)

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def main():
    tf = load_tracklet_features()

    for case in CASES:
        stem, src_tid, tgt_tid, src_last_frame_feat, src_last_frame_raw, end_slope_feat, end_slope_raw, rationale = case
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

        title = f"H123 RAW_REJECTS: {stem} {src_tid}->{tgt_tid}"
        out_path = CONTACT_SHEETS_OUT / f"h123_{stem}_{src_tid}_{tgt_tid}.png"
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
            rationale,
        )


if __name__ == "__main__":
    main()
