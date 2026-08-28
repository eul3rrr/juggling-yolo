#!/usr/bin/env python3
"""H40 v2 - sustained hand-occupancy signal (requires ball within
60 px of wrist for >= 3 consecutive frames).

HYPOTHESIS:
  H40 v1's per-frame "ball within 108 px" signal is too sensitive —
  it counts balls passing through the hand region (not held).
  A stricter signal: ball within 60 px of wrist for >= 3 consecutive
  frames. This catches held balls but rejects fast fly-bys.

ALGORITHM:
  1. Compute per-frame (ball, distance) to each wrist
  2. Find runs of >= 3 consecutive frames where a ball is within
     60 px of a wrist
  3. If such a run exists, mark all frames in the run as HAND_OCCUPIED
  4. Compare with H12 v8 patterns
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H40 v2 thresholds
HAND_REACH_SUSTAINED = 100.0  # px
MIN_RUN_FRAMES = 3


def load_pose(stem: str) -> dict:
    pose_path = PROJECT / "detections" / f"{stem}_yolo26s-pose.csv"
    if not pose_path.exists():
        return {}
    by_frame = {}
    with pose_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            lx = float(r["left_wrist_x"])
            ly = float(r["left_wrist_y"])
            lc = float(r["left_wrist_confidence"])
            rx = float(r["right_wrist_x"])
            ry = float(r["right_wrist_y"])
            rc = float(r["right_wrist_confidence"])
            lw = (lx, ly) if lc >= 0.3 else None
            rw = (rx, ry) if rc >= 0.3 else None
            by_frame[f] = (lw, rw)
    return by_frame


def load_detections(stem: str) -> dict:
    det_path = PROJECT / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    if not det_path.exists():
        return {}
    by_frame = defaultdict(list)
    with det_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            x = float(r["center_x"])
            y = float(r["center_y"])
            c = float(r["confidence"])
            if c >= 0.3:
                by_frame[f].append((x, y, c))
    return by_frame


def find_sustained_occupancy(pose: dict, dets: dict, max_dist: float, min_run: int
                              ) -> dict:
    """For each frame, return (L, R) sustained occupancy based on
    whether any ball has been within `max_dist` of a wrist for the
    preceding `min_run` frames.

    We use a sliding window of `min_run` frames: frame f is "L held"
    if any ball in frames [f - min_run + 1, f] was within max_dist
    of the left wrist.
    """
    # First compute per-frame per-wrist closest ball distance
    per_frame_dist = {}
    for f in (set(pose.keys()) & set(dets.keys())):
        lw, rw = pose.get(f, (None, None))
        frame_dets = dets.get(f, [])
        if not frame_dets or lw is None:
            per_frame_dist[f] = (None, None)
            continue
        min_l = min((((x - lw[0]) ** 2 + (y - lw[1]) ** 2) ** 0.5)
                    for (x, y, c) in frame_dets) if frame_dets and lw else None
        min_r = min((((x - rw[0]) ** 2 + (y - rw[1]) ** 2) ** 0.5)
                    for (x, y, c) in frame_dets) if frame_dets and rw else None
        per_frame_dist[f] = (min_l, min_r)

    # Apply sliding window
    out = {}
    sorted_frames = sorted(per_frame_dist.keys())
    for i, f in enumerate(sorted_frames):
        # Check if any frame in [f - min_run + 1, f] has min_l <= max_dist
        L = 0
        R = 0
        for w in range(min_run):
            j = i - w
            if j < 0:
                break
            prev_f = sorted_frames[j]
            if prev_f < f - min_run + 1:
                break
            min_l, min_r = per_frame_dist[prev_f]
            if min_l is not None and min_l <= max_dist:
                L = 1
            if min_r is not None and min_r <= max_dist:
                R = 1
        out[f] = (L, R)
    return out


def load_h12v8(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (r["pattern"], float(r["confidence"]))
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H40 v2: sustained hand-occupancy) ===")
        pose = load_pose(stem)
        dets = load_detections(stem)
        h12 = load_h12v8(stem)
        if not pose or not dets:
            print("  no data")
            continue
        sust = find_sustained_occupancy(pose, dets, HAND_REACH_SUSTAINED, MIN_RUN_FRAMES)
        all_frames = sorted(sust.keys())
        n_total = len(all_frames)
        n_with_l = sum(1 for f in all_frames if sust[f][0] > 0)
        n_with_r = sum(1 for f in all_frames if sust[f][1] > 0)
        n_with_any = sum(1 for f in all_frames if sust[f][0] > 0 or sust[f][1] > 0)
        print(f"  Sustained hand-occupancy: L={n_with_l}, R={n_with_r}, any={n_with_any} (out of {n_total})")
        print(f"  L%={n_with_l*100/n_total:.1f}, R%={n_with_r*100/n_total:.1f}, any%={n_with_any*100/n_total:.1f}")

        # By H12 v8 pattern
        n_by_pattern = defaultdict(int)
        n_by_pattern_with_occ = defaultdict(int)
        for f in all_frames:
            p = h12.get(f, (None, 0))[0]
            if p:
                n_by_pattern[p] += 1
                if sust[f][0] > 0 or sust[f][1] > 0:
                    n_by_pattern_with_occ[p] += 1
        print(f"\n  H40 v2 sustained-occupancy rate by H12 v8 pattern:")
        for p, n in sorted(n_by_pattern.items(), key=lambda x: -x[1]):
            if n > 0:
                rate = n_by_pattern_with_occ[p] * 100 / n
                print(f"    {p}: {n_by_pattern_with_occ[p]}/{n} = {rate:.1f}%")

        # Cross-check: FOUNTAIN_3+ should have predominantly L or R
        # (single-hand dominant)
        print(f"\n  FOUNTAIN_3+ sustained (L, R) distribution:")
        fountain_states = defaultdict(int)
        for f in all_frames:
            if h12.get(f, (None, 0))[0] == "FOUNTAIN_3+":
                L, R = sust[f]
                fountain_states[(L, R)] += 1
        total = sum(fountain_states.values())
        for (L, R), c in sorted(fountain_states.items(), key=lambda x: -x[1]):
            print(f"    L={L} R={R}: {c} ({c*100/total:.1f}%)")
        # Pure single-hand (one hand only): L=1 R=0 or L=0 R=1
        single_hand = sum(c for (L, R), c in fountain_states.items()
                          if (L, R) in [(1, 0), (0, 1)])
        print(f"    pure single-hand: {single_hand} ({single_hand*100/total:.1f}%)")

        # Write per-frame output
        out_csv = H1_DATA / f"h40v2_continuous_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = ["frame", "L40v2", "R40v2", "h12_pattern", "h12_conf"]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for f in all_frames:
                L, R = sust[f]
                pat, conf = h12.get(f, ("", 0.0))
                w.writerow({"frame": f, "L40v2": L, "R40v2": R,
                            "h12_pattern": pat, "h12_conf": conf})
        print(f"  wrote: {out_csv.name} ({len(all_frames)} rows)")

        summary["videos"][stem] = {
            "n_frames": n_total,
            "n_with_L40v2": n_with_l,
            "n_with_R40v2": n_with_r,
            "n_with_any40v2": n_with_any,
            "pattern_occupancy_rate": {
                p: round(n_by_pattern_with_occ[p] * 100 / max(1, n), 1)
                for p, n in n_by_pattern.items()
            },
            "fountain_pure_single_hand_pct": round(single_hand * 100 / max(1, total), 1),
        }

    out = H1_DATA / "h40v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
