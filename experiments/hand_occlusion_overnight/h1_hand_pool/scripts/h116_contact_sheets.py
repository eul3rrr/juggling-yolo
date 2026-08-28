"""H116 contact sheets: visual QA of 5 H114 v1 strict (T_d=25, T_j=200) fires
on un-QA'd H20-KEPT candidates.

H115 v3 found 21 un-QA fires in the unfiltered 115-row H20-KEPT pool.
H116 selects 5 representative cases (covering the diversity of structural
signatures) and renders endpoint-based contact sheets using pose data
from production tracking.

Hypothesis: H114 v1 strict is a useful *candidate flagger* (not just
validator). If visual QA shows that most fires are FALSE (cross-ball
artifacts), the rule is informative for candidate mining. If most are
REAL/PARTIAL, the rule is over-aggressive and would wrongly reject
real catch-throws.

Cases (all on identical_balls_trick_000_018):
- 18->22: V_DEEP, end_d=33, start_d=297, sj=460 (very far start)
- 31->39: V_SHALLOW, end_d=469, start_d=63, sj=342 (very far end)
- 60->65: V_FLAT, end_d=436, start_d=98, sj=473 (very far end, largest jump)
- 24->28: V_SHALLOW, end_d=61, start_d=238, sj=234 (mid-range)
- 12->18: V_DEEP, end_d=35, start_d=289, sj=468 (very far start)
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h116"
CONTACT_SHEETS_OUT.mkdir(parents=True, exist_ok=True)

# (stem, src_tid, tgt_tid, end_d, start_d, sj, vshape, in_h7v3plus3)
CASES = [
    ("identical_balls_trick_000_018", 18, 22, 32.77, 297.23, 460.03, "V_DEEP", False),
    ("identical_balls_trick_000_018", 31, 39, 468.66, 62.73, 342.00, "V_SHALLOW", False),
    ("identical_balls_trick_000_018", 60, 65, 436.11, 98.22, 472.95, "FLAT", False),
    ("identical_balls_trick_000_018", 24, 28, 60.58, 238.21, 234.31, "V_SHALLOW", False),
    ("identical_balls_trick_000_018", 12, 18, 34.62, 288.80, 468.48, "V_DEEP", False),
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
    title, out_path, edge_label,
    wrist_l, wrist_r,
    end_d_l, end_d_r, start_d_l, start_d_r,
    vshape, in_h7v3plus3, sj, end_d, start_d,
):
    from PIL import Image, ImageDraw, ImageFont

    all_xs = [src_first_xy[0], src_last_xy[0], tgt_first_xy[0], tgt_last_xy[0],
              wrist_l[0], wrist_r[0]]
    all_ys = [src_first_xy[1], src_last_xy[1], tgt_first_xy[1], tgt_last_xy[1],
              wrist_l[1], wrist_r[1]]
    min_x, max_x = min(all_xs) - 80, max(all_xs) + 80
    min_y, max_y = min(all_ys) - 80, max(all_ys) + 80
    if max_x - min_x < 200:
        max_x = min_x + 200
    if max_y - min_y < 200:
        max_y = min_y + 200

    sheet_w, sheet_h = 900, 500
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    pad = 30
    plot_w = sheet_w - 2 * pad
    plot_h = sheet_h - 2 * pad - 100

    def plot_xy(x, y):
        px = (x - min_x) / (max_x - min_x) * (plot_w - 20) + pad + 10
        py = (y - min_y) / (max_y - min_y) * (plot_h - 20) + pad + 10
        return px, py

    # Color based on H114 v1 strict verdict (always fires for these cases)
    color = "darkred"
    draw.text((pad, 5), f"{title}  [{edge_label}]", fill=color, font=font)
    draw.text(
        (pad, 25),
        f"src=tid{src_tid} (n={n_pts_src})  tgt=tid{tgt_tid} (n={n_pts_tgt})  "
        f"vshape={vshape}  h7v3={in_h7v3plus3}",
        fill="black", font=font_small,
    )

    draw.rectangle([pad, pad + 30, pad + plot_w, pad + 30 + plot_h], outline="gray")

    # Wrist positions
    plw = plot_xy(wrist_l[0], wrist_l[1])
    prw = plot_xy(wrist_r[0], wrist_r[1])
    r = 10
    draw.ellipse([plw[0] - r, plw[1] - r, plw[0] + r, plw[1] + r], outline="purple", width=2)
    draw.text((plw[0] + 12, plw[1] - 5), f"L_wrist f={src_last_frame}", fill="purple", font=font_small)
    draw.ellipse([prw[0] - r, prw[1] - r, prw[0] + r, prw[1] + r], outline="darkgreen", width=2)
    draw.text((prw[0] + 12, prw[1] - 5), f"R_wrist f={tgt_first_frame}", fill="darkgreen", font=font_small)

    # Source tracklet: orange
    p_sf = plot_xy(src_first_xy[0], src_first_xy[1])
    p_sl = plot_xy(src_last_xy[0], src_last_xy[1])
    draw.ellipse([p_sf[0] - 5, p_sf[1] - 5, p_sf[0] + 5, p_sf[1] + 5], outline="orange", width=2)
    draw.line([p_sf[0], p_sf[1], p_sl[0], p_sl[1]], fill="orange", width=2)
    draw.ellipse([p_sl[0] - 7, p_sl[1] - 7, p_sl[0] + 7, p_sl[1] + 7], fill="orange")
    draw.text((p_sf[0] + 8, p_sf[1] - 18), f"src_start f={src_first_frame}", fill="orange", font=font_small)
    draw.text(
        (p_sl[0] + 8, p_sl[1] - 5),
        f"src_end f={src_last_frame}\nd_l={end_d_l:.1f} d_r={end_d_r:.1f}",
        fill="black", font=font_small,
    )

    # Target tracklet: blue
    p_tf = plot_xy(tgt_first_xy[0], tgt_first_xy[1])
    p_tl = plot_xy(tgt_last_xy[0], tgt_last_xy[1])
    draw.ellipse([p_tf[0] - 7, p_tf[1] - 7, p_tf[0] + 7, p_tf[1] + 7], fill="blue")
    draw.line([p_tf[0], p_tf[1], p_tl[0], p_tl[1]], fill="blue", width=2)
    draw.ellipse([p_tl[0] - 5, p_tl[1] - 5, p_tl[0] + 5, p_tl[1] + 5], outline="blue", width=2)
    draw.text(
        (p_tf[0] + 8, p_tf[1] - 5),
        f"tgt_start f={tgt_first_frame}\nd_l={start_d_l:.1f} d_r={start_d_r:.1f}",
        fill="black", font=font_small,
    )
    draw.text((p_tl[0] + 8, p_tl[1] - 5), f"tgt_end f={tgt_last_frame}", fill="blue", font=font_small)

    # Jump arrow
    draw.line([p_sl[0], p_sl[1], p_tf[0], p_tf[1]], fill="red", width=1)
    actual_jump = math.hypot(tgt_first_xy[0] - src_last_xy[0], tgt_first_xy[1] - src_last_xy[1])
    midx = (p_sl[0] + p_tf[0]) / 2
    midy = (p_sl[1] + p_tf[1]) / 2
    draw.text(
        (midx, midy - 25),
        f"jump: {actual_jump:.1f}px\ngap: {tgt_first_frame - src_last_frame}f",
        fill="red", font=font_small,
    )

    # Verdict box
    vy = pad + 30 + plot_h + 10
    verdict_text = (
        f"VERDICT: H114 v1 strict (T_d=25, T_j=200) FIRES.  "
        f"sj={sj:.1f}  end_d={end_d:.1f}  start_d={start_d:.1f}.  "
        f"src.end to L/R = {end_d_l:.1f}/{end_d_r:.1f}, "
        f"tgt.start to L/R = {start_d_l:.1f}/{start_d_r:.1f}.  "
        f"vshape={vshape}.  "
        f"in_h7v3plus3={in_h7v3plus3}."
    )
    draw.text((pad, vy), verdict_text, fill=color, font=font_small)
    draw.text(
        (pad, vy + 20),
        "QUESTION: is this a real catch-throw, a hand-borne passage, or a tracker artifact?",
        fill="black", font=font_small,
    )

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def main():
    global n_pts_src, n_pts_tgt  # used in the contact sheet text

    tf = load_tracklet_features()
    stem = "identical_balls_trick_000_018"

    for case in CASES:
        stem_, src, tgt, end_d, start_d, sj, vshape, in_chain = case
        src_f = tf.get((stem_, src))
        tgt_f = tf.get((stem_, tgt))
        if src_f is None or tgt_f is None:
            print(f"  ({src}->{tgt}): tracklet features not found, skip")
            continue

        n_pts_src = src_f["n_pts"]
        n_pts_tgt = tgt_f["n_pts"]

        src_last = (src_f["last_x"], src_f["last_y"])
        src_first = (src_f["first_x"], src_f["first_y"])
        tgt_first = (tgt_f["first_x"], tgt_f["first_y"])
        tgt_last = (tgt_f["last_x"], tgt_f["last_y"])

        # Wrist at catch frame (src.last_frame)
        wrist_l_catch, wrist_r_catch = load_pose(stem_, src_f["last_frame"])
        if wrist_l_catch is None or wrist_r_catch is None:
            wrist_l_catch, wrist_r_catch = load_pose(stem_, tgt_f["first_frame"])
        if wrist_l_catch is None:
            wrist_l_catch = (640, 360)  # image center
        if wrist_r_catch is None:
            wrist_r_catch = wrist_l_catch

        end_d_l = math.hypot(src_last[0] - wrist_l_catch[0], src_last[1] - wrist_l_catch[1])
        end_d_r = math.hypot(src_last[0] - wrist_r_catch[0], src_last[1] - wrist_r_catch[1])
        start_d_l = math.hypot(tgt_first[0] - wrist_l_catch[0], tgt_first[1] - wrist_l_catch[1])
        start_d_r = math.hypot(tgt_first[0] - wrist_r_catch[0], tgt_first[1] - wrist_r_catch[1])

        edge_label = f"H114_STRICT: end={end_d:.0f} start={start_d:.0f} sj={sj:.0f}"
        title = f"H116: {stem_} {src}->{tgt} (H114 v1 strict FIRES)"

        out_name = f"h116_{src}_{tgt}_vshape-{vshape}.png"
        out_path = CONTACT_SHEETS_OUT / out_name

        make_contact_sheet(
            src_tid=src, tgt_tid=tgt,
            src_first_frame=src_f["first_frame"], src_last_frame=src_f["last_frame"],
            src_first_xy=src_first, src_last_xy=src_last,
            tgt_first_frame=tgt_f["first_frame"], tgt_last_frame=tgt_f["last_frame"],
            tgt_first_xy=tgt_first, tgt_last_xy=tgt_last,
            title=title, out_path=out_path, edge_label=edge_label,
            wrist_l=wrist_l_catch, wrist_r=wrist_r_catch,
            end_d_l=end_d_l, end_d_r=end_d_r, start_d_l=start_d_l, start_d_r=start_d_r,
            vshape=vshape, in_h7v3plus3=in_chain, sj=sj, end_d=end_d, start_d=start_d,
        )


if __name__ == "__main__":
    main()
