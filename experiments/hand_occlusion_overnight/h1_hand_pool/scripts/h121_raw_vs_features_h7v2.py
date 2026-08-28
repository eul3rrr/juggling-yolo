#!/usr/bin/env python3
"""H121 — H7v2 reclassification at scale using RAW tracklet data.

Master §11 / H120 future research 2: "H122: Investigate the 3→8
(RECLASSIFIED_HAND_TRANSITION) edge more carefully. ... A targeted
investigation of the H7v2 reclassification criteria for cross-hand
edges with large spatial jumps could identify other latent chain FPs."

HYPOTHESIS: tracklet_features.csv (the input to H7v2) is truncated
relative to the raw detection data. H7v2's catch/throw signature
(end_dist <= 108 AND end_slope < -1.0) uses the LAST frame in
tracklet_features, which is 2-12 frames before the raw tracklet's
actual last frame. This may cause H7v2 to misclassify a tracklet
that's still descending (ball at edge of reach) as a "catch" even
though the raw data shows the ball continuing to descend to the hand
(or further).

APPROACH (declared before reading outcomes):
  1. For each RECLASSIFIED_HAND_TRANSITION edge in h7v3plus3, load
     BOTH:
       - tracklet_features: end_dist, end_slope, end_side, last_x, last_y
       - raw detections: every (frame, x, y, conf) point in the tracklet
  2. Compute H7v2's reclassification rule using raw data:
     - src_is_catch: min_dist(src_last_pos) <= 108 AND end_slope < -1.0
     - tgt_is_throw: min_dist(tgt_first_pos) <= 108 AND start_slope > 1.0
     - gap constraint: tgt.first_frame - src.last_frame <= 20
  3. Compare H7v2_orig (tracklet_features) vs H7v2_raw.
  4. Compute spatial jump for both versions.
  5. Categorize each edge: STILL_RECLASSIFIED (both agree),
     RAW_REJECTS (raw would not reclassify), ORIG_REJECTS (raw would
     reclassify but features wouldn't — should be empty since edges
     are already in h7v3plus3).

INPUTS:
  - tracklet_features.csv
  - detections/<stem>_norfair_dt50_hc5.csv
  - detections/<stem>_yolo26s-pose.csv
  - h7v3plus3_admitted_edges_<stem>.csv (RECLASSIFIED_HAND_TRANSITION only)

OUTPUTS:
  - data/h121_per_edge.csv: per-edge raw vs features comparison
  - data/h121_summary.json: per-stem counts
  - reports/h121_report.md: written report
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
DETECTIONS = WORKTREE / "detections"

# H7v2 declared thresholds (from H7v2 script header)
HAND_REACH_PX = 108
MAX_GAP_FOR_RECLASSIFY_FRAMES = 20
CATCH_SLOPE_PX_PER_FRAME = -1.0
THROW_SLOPE_PX_PER_FRAME = 1.0
MIN_TRACKLET_LEN = 3

# 3-frame slope window (matches H7v2's actual implementation)
SLOPE_WINDOW = 3

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def load_pose(stem: str) -> dict:
    """Load per-frame wrist positions."""
    pose = {}
    pose_path = DETECTIONS / f"{stem}_yolo26s-pose.csv"
    if not pose_path.exists():
        return pose
    with pose_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            L = (float(r["left_wrist_x"]), float(r["left_wrist_y"])) if r["left_wrist_x"] else None
            R = (float(r["right_wrist_x"]), float(r["right_wrist_y"])) if r["right_wrist_x"] else None
            pose[f] = {"left": L, "right": R}
    return pose


def load_raw_tracklets(stem: str) -> dict:
    """Load raw (frame, x, y, conf) points per track_id."""
    raw = {}
    raw_path = DETECTIONS / f"{stem}_norfair_dt50_hc5.csv"
    if not raw_path.exists():
        return raw
    with raw_path.open() as fh:
        for r in csv.DictReader(fh):
            t = int(r["track_id"])
            raw.setdefault(t, []).append((
                int(r["frame"]), float(r["center_x"]), float(r["center_y"]),
                float(r["confidence"])
            ))
    for t in raw:
        raw[t].sort()
    return raw


def load_features(stem: str) -> dict:
    """Load tracklet_features.csv rows for the stem."""
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            def _f(s):
                if not s:
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "first_xy": (float(r["first_x"]), float(r["first_y"])),
                "last_xy": (float(r["last_x"]), float(r["last_y"])),
                "end_dist": _f(r["end_dist"]),
                "start_dist": _f(r["start_dist"]),
                "end_slope": _f(r["end_slope"]),
                "start_slope": _f(r["start_slope"]),
                "end_side": r["end_side"] or None,
                "start_side": r["start_side"] or None,
            }
    return out


def dist(a, b):
    if not a or not b:
        return None
    return math.hypot(a[0]-b[0], a[1]-b[1])


def compute_end_slope_from_points(points, n=SLOPE_WINDOW):
    """Compute average y-slope over last n points."""
    if len(points) < 2:
        return None
    last_n = points[-n:]
    slopes = []
    for i in range(1, len(last_n)):
        df = last_n[i][0] - last_n[i-1][0]
        dy = last_n[i][2] - last_n[i-1][2]
        if df > 0:
            slopes.append(dy / df)
    return sum(slopes) / len(slopes) if slopes else None


def compute_start_slope_from_points(points, n=SLOPE_WINDOW):
    """Compute average y-slope over first n points."""
    if len(points) < 2:
        return None
    first_n = points[:n]
    slopes = []
    for i in range(1, len(first_n)):
        df = first_n[i][0] - first_n[i-1][0]
        dy = first_n[i][2] - first_n[i-1][2]
        if df > 0:
            slopes.append(dy / df)
    return sum(slopes) / len(slopes) if slopes else None


def h7v2_reclassify(src_pts, tgt_pts, pose, reach=HAND_REACH_PX,
                    max_gap=MAX_GAP_FOR_RECLASSIFY_FRAMES,
                    catch_slope=CATCH_SLOPE_PX_PER_FRAME,
                    throw_slope=THROW_SLOPE_PX_PER_FRAME,
                    min_n=MIN_TRACKLET_LEN):
    """Apply H7v2 reclassification rule from raw points + pose."""
    if not src_pts or not tgt_pts:
        return None, "missing_data"
    gap = tgt_pts[0][0] - src_pts[-1][0]
    if gap > max_gap:
        return False, f"gap_too_large_{gap}"

    src_last_frame = src_pts[-1][0]
    src_last_pos = (src_pts[-1][1], src_pts[-1][2])
    src_pose = pose.get(src_last_frame, {})
    src_dL = dist(src_last_pos, src_pose.get("left"))
    src_dR = dist(src_last_pos, src_pose.get("right"))
    src_d = min((d for d in [src_dL, src_dR] if d is not None), default=None)
    src_slope = compute_end_slope_from_points(src_pts)

    if len(src_pts) >= min_n and src_d is not None and src_d <= reach \
            and src_slope is not None and src_slope < catch_slope:
        return True, (f"src_catch_dist={src_d:.1f}_"
                      f"slope={src_slope:.2f}_"
                      f"side={'left' if src_dL is not None and src_dL <= src_dR else 'right'}")

    tgt_first_frame = tgt_pts[0][0]
    tgt_first_pos = (tgt_pts[0][1], tgt_pts[0][2])
    tgt_pose = pose.get(tgt_first_frame, {})
    tgt_dL = dist(tgt_first_pos, tgt_pose.get("left"))
    tgt_dR = dist(tgt_first_pos, tgt_pose.get("right"))
    tgt_d = min((d for d in [tgt_dL, tgt_dR] if d is not None), default=None)
    tgt_slope = compute_start_slope_from_points(tgt_pts)

    if len(tgt_pts) >= min_n and tgt_d is not None and tgt_d <= reach \
            and tgt_slope is not None and tgt_slope > throw_slope:
        return True, (f"tgt_throw_dist={tgt_d:.1f}_"
                      f"slope={tgt_slope:.2f}_"
                      f"side={'left' if tgt_dL is not None and tgt_dL <= tgt_dR else 'right'}")

    return False, "no_catch_throw_signature"


def load_reclassified_edges(stem: str) -> list:
    """Load RECLASSIFIED_HAND_TRANSITION edges from h7v3plus3."""
    rows = []
    with (H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["edge_type"] == "RECLASSIFIED_HAND_TRANSITION":
                rows.append({
                    "from": int(r["from_tid"]),
                    "to": int(r["to_tid"]),
                    "cost": float(r["cost"]),
                    "reason": r.get("reclassify_reason", ""),
                })
    return rows


def main():
    summary = {}
    all_rows = []
    for stem, video in STEMS.items():
        pose = load_pose(stem)
        raw = load_raw_tracklets(stem)
        feat = load_features(stem)
        edges = load_reclassified_edges(stem)

        per_edge = []
        n_still = 0
        n_raw_rejects = 0
        n_sj100_raw = 0
        n_sj200_raw = 0
        n_sj100_orig = 0
        n_sj200_orig = 0
        for e in edges:
            src_pts = raw.get(e["from"])
            tgt_pts = raw.get(e["to"])
            sf = feat.get(e["from"])
            tf = feat.get(e["to"])
            if not src_pts or not tgt_pts or not sf or not tf:
                continue

            # H7v2 reclassification using raw data
            reclass_raw, reason_raw = h7v2_reclassify(src_pts, tgt_pts, pose)

            # H7v2 reclassification using tracklet_features (original = True)
            reclass_orig = True  # All these edges are in h7v3plus3 because H7v2 reclassified them

            # Compute spatial jump
            sj_raw = dist((src_pts[-1][1], src_pts[-1][2]), (tgt_pts[0][1], tgt_pts[0][2]))
            sj_orig = dist(sf["last_xy"], tf["first_xy"])

            n_sj100_raw += int(sj_raw and sj_raw > 100)
            n_sj200_raw += int(sj_raw and sj_raw > 200)
            n_sj100_orig += int(sj_orig and sj_orig > 100)
            n_sj200_orig += int(sj_orig and sj_orig > 200)

            n_still += int(reclass_raw is True)
            n_raw_rejects += int(reclass_raw is False)

            per_edge.append({
                "stem": stem,
                "from": e["from"],
                "to": e["to"],
                "feat_n_pts": sf["n_pts"],
                "raw_n_pts": len(src_pts),
                "feat_last_frame": sf["last_frame"],
                "raw_last_frame": src_pts[-1][0],
                "feat_last_xy": sf["last_xy"],
                "raw_last_xy": (src_pts[-1][1], src_pts[-1][2]),
                "feat_end_dist": sf["end_dist"],
                "raw_end_dist": min(
                    (d for d in [dist((src_pts[-1][1], src_pts[-1][2]), pose.get(src_pts[-1][0], {}).get("left")),
                                 dist((src_pts[-1][1], src_pts[-1][2]), pose.get(src_pts[-1][0], {}).get("right"))]
                     if d is not None), default=None),
                "feat_end_slope": sf["end_slope"],
                "raw_end_slope": compute_end_slope_from_points(src_pts),
                "feat_start_dist": tf["start_dist"],
                "raw_start_dist": min(
                    (d for d in [dist((tgt_pts[0][1], tgt_pts[0][2]), pose.get(tgt_pts[0][0], {}).get("left")),
                                 dist((tgt_pts[0][1], tgt_pts[0][2]), pose.get(tgt_pts[0][0], {}).get("right"))]
                     if d is not None), default=None),
                "feat_start_slope": tf["start_slope"],
                "raw_start_slope": compute_start_slope_from_points(tgt_pts),
                "sj_raw": sj_raw,
                "sj_orig": sj_orig,
                "h7v2_orig": reclass_orig,
                "h7v2_raw": reclass_raw,
                "h7v2_raw_reason": reason_raw,
                "verdict": "STILL_RECLASSIFIED" if reclass_raw else "RAW_REJECTS",
            })

        summary[stem] = {
            "n_reclassified": len(per_edge),
            "n_still_reclassified": n_still,
            "n_raw_rejects": n_raw_rejects,
            "n_sj_gt_100_raw": n_sj100_raw,
            "n_sj_gt_200_raw": n_sj200_raw,
            "n_sj_gt_100_orig": n_sj100_orig,
            "n_sj_gt_200_orig": n_sj200_orig,
        }
        all_rows.extend(per_edge)

        print(f"\n=== {stem} ===")
        print(f"  n RECLASSIFIED edges: {len(per_edge)}")
        print(f"  n STILL reclassified (raw agrees): {n_still}")
        print(f"  n RAW REJECTS: {n_raw_rejects}")
        print(f"  Spatial jump > 100 (raw): {n_sj100_raw}")
        print(f"  Spatial jump > 200 (raw): {n_sj200_raw}")
        print(f"  Spatial jump > 100 (orig): {n_sj100_orig}")
        print(f"  Spatial jump > 200 (orig): {n_sj200_orig}")

    # Save outputs
    out_csv = H1_DATA / "h121_per_edge.csv"
    with out_csv.open("w", newline="") as fh:
        cols = ["stem", "from", "to", "feat_n_pts", "raw_n_pts", "feat_last_frame", "raw_last_frame",
                "feat_last_xy", "raw_last_xy", "feat_end_dist", "raw_end_dist", "feat_end_slope",
                "raw_end_slope", "feat_start_dist", "raw_start_dist", "feat_start_slope",
                "raw_start_slope", "sj_raw", "sj_orig", "h7v2_orig", "h7v2_raw", "h7v2_raw_reason", "verdict"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            row = {k: r[k] for k in cols}
            # Convert tuples to strings for CSV
            for k in ["feat_last_xy", "raw_last_xy"]:
                if row[k] is not None:
                    row[k] = f"({row[k][0]:.1f},{row[k][1]:.1f})"
            w.writerow(row)
    print(f"\nWrote {out_csv}")

    out_json = H1_DATA / "h121_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Wrote {out_json}")

    # Print RAW_REJECTS table for both stems
    print("\n\n=== RAW_REJECTS (edges where tracklet_features-based H7v2 said YES but raw data says NO) ===")
    print(f"{'stem':<25} {'from':>4} {'to':>4}  feat_n  raw_n  feat_lf  raw_lf  sj_raw  sj_orig  raw_d  raw_slope  reason")
    for r in all_rows:
        if r["verdict"] == "RAW_REJECTS":
            d_s = f"{r['raw_end_dist']:.1f}" if r['raw_end_dist'] is not None else "NA"
            s_s = f"{r['raw_end_slope']:.2f}" if r['raw_end_slope'] is not None else "NA"
            sj_r = f"{r['sj_raw']:.1f}" if r['sj_raw'] is not None else "NA"
            sj_o = f"{r['sj_orig']:.1f}" if r['sj_orig'] is not None else "NA"
            print(f"  {r['stem'][:24]:<25} {r['from']:>4} {r['to']:>4}  {r['feat_n_pts']:>6}  {r['raw_n_pts']:>5}  {r['feat_last_frame']:>4}    {r['raw_last_frame']:>4}    {sj_r:>5}  {sj_o:>5}    {d_s:>5}  {s_s:>5}     {r['h7v2_raw_reason'][:50]}")


if __name__ == "__main__":
    main()
