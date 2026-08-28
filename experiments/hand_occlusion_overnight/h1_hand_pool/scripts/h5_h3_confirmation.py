#!/usr/bin/env python3
"""H5 — Apply H3 stationary-cluster as a downstream confidence flag on v4d links.

For each v4d hand-link, check whether an H3 v3 stationary cluster
exists in the held phase (between from_frame and to_frame, but not
in the first 5 or last 5 frames to avoid the catch/throw moments).

Output: hand_links_v4_v4d_throw7_full_with_h3.csv with new column
`h3_confirmed` (True/False).

H3 was previously confirmed to have 100% precision on identical
video (6/6 confirmed real held balls) and 1 false positive on the
youtube video. The `h3_confirmed` flag is a downstream-consumable
signal: chains that include H3-confirmed links are more trustworthy.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
DET = WORKTREE / "detections"
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# ----------------------------------------------------------------------
# H3 v3 thresholds (same as h3_low_conf_hand_region.py v3)
# ----------------------------------------------------------------------
H3_V3 = {
    "REACH_PX": 108,
    "LOW_CONF_THRESHOLD": 0.4,
    "STATIONARY_RADIUS_PX": 30,
    "STATIONARY_MIN_N": 3,
    "STATIONARY_MIN_SPAN": 5,
    "STATIONARY_MAX_GAP": 8,
    "HELD_PHASE_SKIP_FRAMES": 5,  # skip first/last N frames of link
}

V4D_LINKS_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"
OUT_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv"


def load_pose(stem):
    out = {}
    with (DET / f"{stem}_yolo26s-pose.csv").open() as fh:
        for r in csv.DictReader(fh):
            try:
                out[int(r["frame"])] = {
                    "left": (float(r["left_wrist_x"]), float(r["left_wrist_y"])),
                    "right": (float(r["right_wrist_x"]), float(r["right_wrist_y"])),
                }
            except (ValueError, KeyError):
                continue
    return out


def load_sb(stem):
    for suffix in ["_yolo26s_all-classes.csv", "_yolo26s_classes-32.csv"]:
        path = DET / f"{stem}{suffix}"
        if path.exists():
            break
    else:
        return []
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if "class_name" in r and r["class_name"] != "sports ball":
                continue
            try:
                out.append((int(r["frame"]), float(r["center_x"]), float(r["center_y"]),
                            float(r["confidence"])))
            except (ValueError, KeyError):
                continue
    return out


def load_norfair_index(stem):
    out = {}
    with (DET / f"{stem}_norfair_dt50_hc5.csv").open() as fh:
        for r in csv.DictReader(fh):
            try:
                out[(int(r["frame"]),
                     round(float(r["center_x"])),
                     round(float(r["center_y"])))] = int(r["track_id"])
            except (ValueError, KeyError):
                continue
    return out


def find_tid(nf_index, fr, x, y, max_dist=4):
    for d in range(max_dist + 1):
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                k = (fr, round(x) + dx, round(y) + dy)
                if k in nf_index:
                    return nf_index[k]
    return None


def find_wrist(pose, frame, hand, max_diff=3):
    if not pose:
        return None
    if frame in pose:
        return pose[frame][hand]
    nearest, best = None, max_diff + 1
    for fr, w in pose.items():
        d = abs(fr - frame)
        if d <= max_diff and d < best:
            best = d
            nearest = w
    return None if nearest is None else nearest[hand]


def build_st_grid(sb_list, grid_size=30):
    grid = defaultdict(list)
    for d in sb_list:
        gx = int(d[1] // grid_size)
        gy = int(d[2] // grid_size)
        grid[(gx, gy)].append(d)
    return grid


def find_stationary_cluster(seed_det, sb_list, grid, grid_size):
    fr, x, y, c = seed_det
    gx = int(x // grid_size)
    gy = int(y // grid_size)
    neighbors = []
    for dgx in range(-1, 2):
        for dgy in range(-1, 2):
            for d in grid.get((gx + dgx, gy + dgy), []):
                if d[3] >= H3_V3["LOW_CONF_THRESHOLD"]:
                    continue
                if abs(d[1] - x) > H3_V3["STATIONARY_RADIUS_PX"]:
                    continue
                if abs(d[2] - y) > H3_V3["STATIONARY_RADIUS_PX"]:
                    continue
                if d[0] < fr - 15 or d[0] > fr + 15:
                    continue
                neighbors.append(d)
    if len(neighbors) < H3_V3["STATIONARY_MIN_N"]:
        return None
    neighbors.sort(key=lambda d: d[0])
    clusters = []
    cur = [neighbors[0]]
    for d in neighbors[1:]:
        if d[0] - cur[-1][0] <= H3_V3["STATIONARY_MAX_GAP"]:
            cur.append(d)
        else:
            clusters.append(cur)
            cur = [d]
    clusters.append(cur)
    biggest = max(clusters, key=len)
    if len(biggest) < H3_V3["STATIONARY_MIN_N"]:
        return None
    span = biggest[-1][0] - biggest[0][0]
    if span < H3_V3["STATIONARY_MIN_SPAN"]:
        return None
    return biggest


def has_h3_confirmation(link: dict, pose, sb, nf_index, grid) -> bool:
    """Return True if the link has an H3 v3 stationary cluster in the
    HELD phase (excluding first/last 5 frames of the link)."""
    stem = link["stem"]
    from_tid = int(link["from_tid"])
    to_tid = int(link["to_tid"])
    hand = link["hand"]
    f1 = int(link["from_frame"]) + H3_V3["HELD_PHASE_SKIP_FRAMES"]
    f2 = int(link["to_frame"]) - H3_V3["HELD_PHASE_SKIP_FRAMES"]
    if f2 < f1:
        return False  # link too short

    # Find unassigned low-conf detections in the hand region
    candidates = []
    for d in sb:
        if d[0] < f1 or d[0] > f2:
            continue
        if d[3] >= H3_V3["LOW_CONF_THRESHOLD"]:
            continue
        w = find_wrist(pose, d[0], hand)
        if w is None:
            continue
        d_to_hand = ((d[1] - w[0]) ** 2 + (d[2] - w[1]) ** 2) ** 0.5
        if d_to_hand > H3_V3["REACH_PX"]:
            continue
        tid = find_tid(nf_index, d[0], d[1], d[2])
        if tid == from_tid or tid == to_tid:
            continue
        candidates.append(d)

    # Find stationary cluster
    for c in candidates:
        cl = find_stationary_cluster(c, candidates, grid, H3_V3["STATIONARY_RADIUS_PX"])
        if cl is not None:
            return True
    return False


def main():
    with V4D_LINKS_PATH.open() as fh:
        links = list(csv.DictReader(fh))

    # Group links by stem
    by_stem = defaultdict(list)
    for link in links:
        by_stem[link["stem"]].append(link)

    # Process per stem
    results = {}
    for stem, stem_links in by_stem.items():
        pose = load_pose(stem)
        sb = load_sb(stem)
        nf_index = load_norfair_index(stem)
        grid = build_st_grid(sb, grid_size=H3_V3["STATIONARY_RADIUS_PX"])
        for link in stem_links:
            key = (link["from_tid"], link["to_tid"])
            confirmed = has_h3_confirmation(link, pose, sb, nf_index, grid)
            results[key] = confirmed
            print(f"  {link['from_tid']:>3}->{link['to_tid']:<3}  {link['hand']:>5}  "
                  f"f={link['from_frame']:>4}..{link['to_frame']:<4}  "
                  f"h3_confirmed={confirmed}")

    # Write out v4d links with h3_confirmed flag
    n_confirmed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {n_confirmed}/{len(results)} links H3-confirmed")

    # Read original and add column
    with V4D_LINKS_PATH.open() as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys()) + ["h3_confirmed"]
    with OUT_PATH.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            key = (r["from_tid"], r["to_tid"])
            r["h3_confirmed"] = "True" if results.get(key, False) else "False"
            w.writerow(r)
    print(f"\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    main()
