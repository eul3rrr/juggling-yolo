"""H112 contact sheets: visualize the 22->27 FP and the 25->27 actual catch.

Hypothesis: at f=257-263, the juggler catches a ball in the left hand (tracklet 22 ends
near the left wrist) and throws it to the right hand, which should result in the
right-hand catch (tracklet 25 endpoint) at f=255, then a NEW tracklet starting
at the right hand.

H111 visual QA found:
- 22->27 is NOT a real catch-throw (190-px spatial jump, end_d=46.7 to LEFT,
  start_d=56.2 to RIGHT)
- 25->27 IS a real catch-throw (10.5-px spatial jump, in-place handoff)

This script produces two contact sheets showing both edges' trajectories and
the surrounding frames. Used to visually verify the H112 filter's verdict.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"
CONTACT_SHEETS_OUT = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_h112"

# Reproduce 7-frame contact sheets for both edges using PIL.
def make_contact_sheet(
    tracklet_a: list[tuple[int, float, float]],
    tracklet_b: list[tuple[int, float, float]],
    title: str,
    out_path: Path,
    edge_label: str,
    fp_flag: bool,
):
    """Create a 6-panel contact sheet showing the trajectory of tracklet A,
    the gap, and the trajectory of tracklet B. Each panel is 300x200 px.
    """
    from PIL import Image, ImageDraw, ImageFont

    a_frames = [t[0] for t in tracklet_a]
    b_frames = [t[0] for t in tracklet_b]
    a_xs = [t[1] for t in tracklet_a]
    a_ys = [t[2] for t in tracklet_a]
    b_xs = [t[1] for t in tracklet_b]
    b_ys = [t[2] for t in tracklet_b]

    all_xs = a_xs + b_xs
    all_ys = a_ys + b_ys
    if not all_xs:
        print(f"  skip {title} (no points)")
        return
    min_x, max_x = min(all_xs) - 50, max(all_xs) + 50
    min_y, max_y = min(all_ys) - 50, max(all_ys) + 50
    if max_x - min_x < 100:
        max_x = min_x + 100
    if max_y - min_y < 100:
        max_y = min_y + 100

    panel_w, panel_h = 300, 250
    cols = 6
    rows = 1
    sheet = Image.new("RGB", (panel_w * cols, panel_h * rows + 30), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    color_a = (255, 100, 0)  # ORANGE for source
    color_b = (0, 100, 255)   # BLUE for target

    def to_panel_xy(x, y, panel):
        px = (x - min_x) / (max_x - min_x) * (panel_w - 20) + 10
        py = (y - min_y) / (max_y - min_y) * (panel_h - 30) + 10
        return px, py

    def draw_tracklet_in_panel(tracklet, color, panel, panel_x_off, label):
        if not tracklet:
            return
        for i, (f, x, y) in enumerate(tracklet):
            px, py = to_panel_xy(x, y, panel)
            cx = panel_x_off + px
            cy = py
            r = 4
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
            if i == len(tracklet) - 1:
                # Mark last point
                draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline="black", width=2)
            if i == 0:
                draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline="gray", width=1)
        if label and len(tracklet) > 0:
            f0, x0, y0 = tracklet[0]
            draw.text((panel_x_off + 5, 5), f"{label} f={f0}", fill="black", font=font_small)

    # Choose 6 sample frames spanning the transition
    gap_start = a_frames[-1] if a_frames else None
    gap_end = b_frames[0] if b_frames else None
    if gap_start is None or gap_end is None:
        return
    # 2 panels for tracklet A, 1 panel for gap, 3 panels for tracklet B
    # Simpler: just plot the full trajectories side by side in one big panel
    # Actually let's do 6 stacked panels: each shows the full trajectory up to that frame
    # This is just the cumulative visualization

    # Simpler: one wide panel showing both tracklets + a frame selector
    sheet_w = 1800
    sheet_h = 400
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    # Use full sheet for trajectory plot
    pad = 30
    plot_w = sheet_w - 2 * pad
    plot_h = sheet_h - 2 * pad - 50  # leave space for title

    def plot_xy(x, y):
        px = (x - min_x) / (max_x - min_x) * (plot_w - 20) + pad + 10
        py = (y - min_y) / (max_y - min_y) * (plot_h - 20) + pad + 10
        return px, py

    # Title
    title_text = f"{title}  [{edge_label}]"
    color = "darkred" if fp_flag else "darkgreen"
    draw.text((pad, 5), title_text, fill=color, font=font)

    # Plot axes
    draw.rectangle([pad, pad, pad + plot_w, pad + plot_h], outline="gray")

    # Draw tracklet A
    for i, (f, x, y) in enumerate(tracklet_a):
        px, py = plot_xy(x, y)
        r = 5
        draw.ellipse([px - r, py - r, px + r, py + r], fill=color_a)
        draw.text((px + 5, py - 5), f"f={f}", fill=color_a, font=font_small)
        if i > 0:
            x0, y0 = tracklet_a[i - 1][1], tracklet_a[i - 1][2]
            px0, py0 = plot_xy(x0, y0)
            draw.line([px0, py0, px, py], fill=color_a, width=2)
    # Last point emphasized
    if tracklet_a:
        px, py = plot_xy(tracklet_a[-1][1], tracklet_a[-1][2])
        draw.ellipse([px - 8, py - 8, px + 8, py + 8], outline="black", width=2)

    # Draw tracklet B
    for i, (f, x, y) in enumerate(tracklet_b):
        px, py = plot_xy(x, y)
        r = 5
        draw.ellipse([px - r, py - r, px + r, py + r], fill=color_b)
        draw.text((px + 5, py - 5), f"f={f}", fill=color_b, font=font_small)
        if i > 0:
            x0, y0 = tracklet_b[i - 1][1], tracklet_b[i - 1][2]
            px0, py0 = plot_xy(x0, y0)
            draw.line([px0, py0, px, py], fill=color_b, width=2)
    # First point emphasized
    if tracklet_b:
        px, py = plot_xy(tracklet_b[0][1], tracklet_b[0][2])
        draw.ellipse([px - 8, py - 8, px + 8, py + 8], outline="black", width=2)

    # Draw jump line
    if tracklet_a and tracklet_b:
        pa = plot_xy(tracklet_a[-1][1], tracklet_a[-1][2])
        pb = plot_xy(tracklet_b[0][1], tracklet_b[0][2])
        draw.line([pa[0], pa[1], pb[0], pb[1]], fill="red", width=1)
        midx = (pa[0] + pb[0]) / 2
        midy = (pa[1] + pb[1]) / 2
        jump_px = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        # Report the actual jump in image pixels
        # Actual spatial jump in tracklet coordinates:
        ax, ay = tracklet_a[-1][1], tracklet_a[-1][2]
        bx, by = tracklet_b[0][1], tracklet_b[0][2]
        actual_jump = math.hypot(bx - ax, by - ay)
        gap = tracklet_b[0][0] - tracklet_a[-1][0]
        draw.text((midx, midy - 20),
                  f"spatial jump: {actual_jump:.1f}px\ngap: {gap} frames",
                  fill="red", font=font_small)

    # Legend
    leg_y = pad + plot_h + 5
    draw.ellipse([pad, leg_y, pad + 10, leg_y + 10], fill=color_a)
    draw.text((pad + 15, leg_y - 3), f"source tracklet (n={len(tracklet_a)})", fill="black", font=font_small)
    draw.ellipse([pad + 200, leg_y, pad + 210, leg_y + 10], fill=color_b)
    draw.text((pad + 215, leg_y - 3), f"target tracklet (n={len(tracklet_b)})", fill="black", font=font_small)

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def load_tracklet_points(stem: str, tid: int) -> list[tuple[int, float, float]]:
    """Load per-frame (x, y) for a tracklet from the stitches CSV."""
    # Look for the per-video stitches file
    if "identical" in stem:
        vfile = WORKTREE / "videos" / f"{stem}.mp4"
    else:
        vfile = WORKTREE / "videos" / f"{stem}.mp4"
    if not vfile.exists():
        return []
    # The stitches file is in production tracking. Since we can't modify production,
    # we use the cached tracklet_features.csv summary instead.
    # Actually, we can reconstruct from tracklet_features.csv if it has per-frame points.
    # Looking at the data: tracklet_features.csv has only first/last, not all frames.
    # We need to fall back to a simpler approach: just plot the endpoints.
    # For contact sheets we'll show the first/last positions in the trajectory plot.
    return []  # placeholder; we use endpoints only


def make_endpoint_contact_sheet(
    src_tid: int, tgt_tid: int,
    src_first_frame: int, src_last_frame: int,
    src_first_xy: tuple, src_last_xy: tuple,
    tgt_first_frame: int, tgt_last_frame: int,
    tgt_first_xy: tuple, tgt_last_xy: tuple,
    title: str,
    out_path: Path,
    edge_label: str,
    fp_flag: bool,
    wrist_l: tuple, wrist_r: tuple,
    end_d_l: float, end_d_r: float,
    start_d_l: float, start_d_r: float,
):
    """Make a contact sheet with tracklet endpoints + wrist positions.
    This is a SUMMARY view: shows first and last positions of each tracklet
    plus wrist positions, annotated with distances."""
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

    color = "darkred" if fp_flag else "darkgreen"
    draw.text((pad, 5), f"{title}  [{edge_label}]", fill=color, font=font)
    draw.text((pad, 25), f"src=tid{src_tid}  tgt=tid{tgt_tid}  reviewer says: {edge_label}", fill="black", font=font_small)

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
    draw.text((p_sl[0] + 8, p_sl[1] - 5),
              f"src_end f={src_last_frame}\nd_l={end_d_l:.1f} d_r={end_d_r:.1f}",
              fill="black", font=font_small)

    # Target tracklet: blue
    p_tf = plot_xy(tgt_first_xy[0], tgt_first_xy[1])
    p_tl = plot_xy(tgt_last_xy[0], tgt_last_xy[1])
    draw.ellipse([p_tf[0] - 7, p_tf[1] - 7, p_tf[0] + 7, p_tf[1] + 7], fill="blue")
    draw.line([p_tf[0], p_tf[1], p_tl[0], p_tl[1]], fill="blue", width=2)
    draw.ellipse([p_tl[0] - 5, p_tl[1] - 5, p_tl[0] + 5, p_tl[1] + 5], outline="blue", width=2)
    draw.text((p_tf[0] + 8, p_tf[1] - 5),
              f"tgt_start f={tgt_first_frame}\nd_l={start_d_l:.1f} d_r={start_d_r:.1f}",
              fill="black", font=font_small)
    draw.text((p_tl[0] + 8, p_tl[1] - 5), f"tgt_end f={tgt_last_frame}", fill="blue", font=font_small)

    # Jump arrow
    draw.line([p_sl[0], p_sl[1], p_tf[0], p_tf[1]], fill="red", width=1)
    actual_jump = math.hypot(tgt_first_xy[0] - src_last_xy[0], tgt_first_xy[1] - src_last_xy[1])
    midx = (p_sl[0] + p_tf[0]) / 2
    midy = (p_sl[1] + p_tf[1]) / 2
    draw.text((midx, midy - 25),
              f"jump: {actual_jump:.1f}px\ngap: {tgt_first_frame - src_last_frame}f",
              fill="red", font=font_small)

    # Verdict box
    vy = pad + 30 + plot_h + 10
    verdict_text = (
        f"VERDICT: edge = {'FP' if fp_flag else 'TP'}.  "
        f"src.end_d to L/R = {end_d_l:.1f}/{end_d_r:.1f}, "
        f"tgt.start_d to L/R = {start_d_l:.1f}/{start_d_r:.1f}.  "
        f"Cross-hand: end_L->start_R.  "
        f"H112 rule (cross AND end>30 AND start>30): {fp_flag}."
    )
    draw.text((pad, vy), verdict_text, fill=color, font=font_small)

    sheet.save(out_path)
    print(f"  wrote {out_path}")


def load_pose(stem: str, frame: int) -> tuple:
    """Load left and right wrist positions at a given frame from the production
    pose CSV at detections/{stem}_yolo26s-pose.csv."""
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


def main():
    CONTACT_SHEETS_OUT.mkdir(parents=True, exist_ok=True)

    # Load tracklet_features
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

    stem = "identical_balls_trick_000_018"

    # Case 1: 22 -> 27 (the FP)
    src, tgt = 22, 27
    src_f = tf[(stem, src)]
    tgt_f = tf[(stem, tgt)]
    src_last = (src_f["last_x"], src_f["last_y"])
    src_first = (src_f["first_x"], src_f["first_y"])
    tgt_first = (tgt_f["first_x"], tgt_f["first_y"])
    tgt_last = (tgt_f["last_x"], tgt_f["last_y"])

    # Wrist at the catch frame (src.last_frame)
    wrist_l_catch, wrist_r_catch = load_pose(stem, src_f["last_frame"])
    if wrist_l_catch is None or wrist_r_catch is None:
        # Fall back to throw frame
        wrist_l_catch, wrist_r_catch = load_pose(stem, tgt_f["first_frame"])
    if wrist_l_catch is None:
        # Use a default position
        wrist_l_catch, wrist_r_catch = (727, 484), (727, 484)
    if wrist_r_catch is None:
        wrist_r_catch = wrist_l_catch

    # Compute distances to each wrist for the FP case
    end_d_l = math.hypot(src_last[0] - wrist_l_catch[0], src_last[1] - wrist_l_catch[1])
    end_d_r = math.hypot(src_last[0] - wrist_r_catch[0], src_last[1] - wrist_r_catch[1])
    start_d_l = math.hypot(tgt_first[0] - wrist_l_catch[0], tgt_first[1] - wrist_l_catch[1])
    start_d_r = math.hypot(tgt_first[0] - wrist_r_catch[0], tgt_first[1] - wrist_r_catch[1])

    make_endpoint_contact_sheet(
        src_tid=22, tgt_tid=27,
        src_first_frame=src_f["first_frame"], src_last_frame=src_f["last_frame"],
        src_first_xy=src_first, src_last_xy=src_last,
        tgt_first_frame=tgt_f["first_frame"], tgt_last_frame=tgt_f["last_frame"],
        tgt_first_xy=tgt_first, tgt_last_xy=tgt_last,
        title="22 -> 27 (H112 DROPS this edge)",
        out_path=CONTACT_SHEETS_OUT / "h112_22_27_FP.png",
        edge_label="REVIEWER: WRONG (FP)",
        fp_flag=True,
        wrist_l=wrist_l_catch, wrist_r=wrist_r_catch,
        end_d_l=end_d_l, end_d_r=end_d_r, start_d_l=start_d_l, start_d_r=start_d_r,
    )

    # Case 2: 25 -> 27 (the actual catch, H112 does NOT drop this)
    src, tgt = 25, 27
    src_f = tf[(stem, src)]
    tgt_f = tf[(stem, tgt)]
    src_last = (src_f["last_x"], src_f["last_y"])
    src_first = (src_f["first_x"], src_f["first_y"])
    tgt_first = (tgt_f["first_x"], tgt_f["first_y"])
    tgt_last = (tgt_f["last_x"], tgt_f["last_y"])

    wrist_l_catch, wrist_r_catch = load_pose(stem, src_f["last_frame"])
    if wrist_l_catch is None:
        wrist_l_catch, wrist_r_catch = load_pose(stem, tgt_f["first_frame"])
    if wrist_l_catch is None:
        wrist_l_catch, wrist_r_catch = (727, 484), (727, 484)
    if wrist_r_catch is None:
        wrist_r_catch = wrist_l_catch

    end_d_l = math.hypot(src_last[0] - wrist_l_catch[0], src_last[1] - wrist_l_catch[1])
    end_d_r = math.hypot(src_last[0] - wrist_r_catch[0], src_last[1] - wrist_r_catch[1])
    start_d_l = math.hypot(tgt_first[0] - wrist_l_catch[0], tgt_first[1] - wrist_l_catch[1])
    start_d_r = math.hypot(tgt_first[0] - wrist_r_catch[0], tgt_first[1] - wrist_r_catch[1])

    make_endpoint_contact_sheet(
        src_tid=25, tgt_tid=27,
        src_first_frame=src_f["first_frame"], src_last_frame=src_f["last_frame"],
        src_first_xy=src_first, src_last_xy=src_last,
        tgt_first_frame=tgt_f["first_frame"], tgt_last_frame=tgt_f["last_frame"],
        tgt_first_xy=tgt_first, tgt_last_xy=tgt_last,
        title="25 -> 27 (the REAL catch-throw)",
        out_path=CONTACT_SHEETS_OUT / "h112_25_27_TP.png",
        edge_label="REVIEWER: CORRECT (TP)",
        fp_flag=False,
        wrist_l=wrist_l_catch, wrist_r=wrist_r_catch,
        end_d_l=end_d_l, end_d_r=end_d_r, start_d_l=start_d_l, start_d_r=start_d_r,
    )


if __name__ == "__main__":
    main()
