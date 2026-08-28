#!/usr/bin/env python3
"""H12 v5 - detector-level signal with temporal smoothing.

H12 v4 uses instantaneous n_distinct_horiz_dirs which is noisy
on 3-ball juggling (cascade has moments when all balls drift
the same direction). H12 v5 smooths the n_distinct_dirs signal
over a small temporal window (W=10 frames) to get a more
robust classification.

Heuristic:
  - smoothed_dirs = median(n_distinct_dirs over ±W frames)
  - smoothed_dirs == 2 → CASCADE_3+_DETECTOR
  - smoothed_dirs == 1 → FOUNTAIN_3+_DETECTOR
  - otherwise → MIXED_3+
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Temporal smoothing window (frames)
W = 10


def load_tracklet_points(stem: str) -> dict:
    out = defaultdict(list)
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tid = int(r["track_id"])
            out[tid].append((int(r["frame"]), float(r["center_x"]),
                             float(r["center_y"])))
    for tid in out:
        out[tid].sort()
    return out


def per_frame_dirs(tracklets: dict) -> dict:
    """Returns {frame: n_distinct_horiz_dirs}.

    A ball is "moving" if |vx| > 1.0 px/frame. A direction is +1
    (right) or -1 (left). For frames with multiple balls, the value
    is the count of distinct horizontal directions across all balls
    in that frame (so 0, 1, or 2).
    """
    out = {}
    for tid, points in tracklets.items():
        for i, (f, x, y) in enumerate(points):
            if i == 0:
                continue
            prev_f, prev_x, _ = points[i - 1]
            vx = (x - prev_x) / max(1, f - prev_f)
            if abs(vx) > 1.0:
                if f not in out:
                    out[f] = set()
                out[f].add(1 if vx > 0 else -1)
    return {f: len(s) for f, s in out.items()}


def smooth_dirs(per_frame_dirs: dict, frames: list) -> dict:
    """Returns {frame: median(n_distinct_horiz_dirs over ±W frames)}.

    For each frame, take all frames in [f-W, f+W] that are in per_frame_dirs,
    compute the median n_distinct_horiz_dirs, and use that as the smoothed
    value.
    """
    out = {}
    for f in frames:
        neighbors = []
        for df in range(-W, W + 1):
            d = per_frame_dirs.get(f + df, 0)
            neighbors.append(d)
        neighbors.sort()
        n = len(neighbors)
        if n % 2 == 0:
            median = (neighbors[n // 2 - 1] + neighbors[n // 2]) / 2
        else:
            median = neighbors[n // 2]
        out[f] = int(median)
    return out


def classify_pattern_v5(f: int, smoothed_dirs: int, n_total: int,
                          n_in_hand_left: int, n_in_hand_right: int) -> tuple:
    if n_total == 0:
        return "NO_BALL", 1.0
    if n_total == 1:
        return "SINGLE_BALL", 0.5
    if n_total == 2:
        if n_in_hand_left == 1 and n_in_hand_right == 1:
            return "TWO_BALL_HELD", 0.5
        return "TWO_BALL", 0.5
    if n_total >= 3:
        if smoothed_dirs == 2:
            return "CASCADE_3+_DETECTOR_SMOOTHED", 0.7
        if smoothed_dirs == 1:
            return "FOUNTAIN_3+_DETECTOR_SMOOTHED", 0.7
        if smoothed_dirs == 0:
            return "MIXED_3+_UNCONFIRMED", 0.3
        return "MIXED_3+", 0.4
    return "UNKNOWN", 0.0


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H12 v5 with temporal smoothing) ===")
        tracklets = load_tracklet_points(stem)
        per_frame = per_frame_dirs(tracklets)
        print(f"  loaded {len(tracklets)} tracklets")

        # Load census
        census = {}
        with (H1_DATA / f"per_frame_census_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                census[int(r["frame"])] = {
                    "n_in_hand_left": int(r["n_in_hand_left"]),
                    "n_in_hand_right": int(r["n_in_hand_right"]),
                    "n_total": int(r["n_total_balls"]),
                }

        frames = sorted(census.keys())
        smoothed = smooth_dirs(per_frame, frames)
        print(f"  smoothed_dirs distribution:")
        sd_buckets = defaultdict(int)
        for f, sd in smoothed.items():
            sd_buckets[sd] += 1
        for sd in sorted(sd_buckets):
            print(f"    {sd}: {sd_buckets[sd]} frames")

        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        for f in frames:
            c = census[f]
            sd = smoothed.get(f, 0)
            pattern, conf = classify_pattern_v5(
                f, sd, c["n_total"], c["n_in_hand_left"], c["n_in_hand_right"])
            results.append({
                "frame": f,
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total"],
                "instant_dirs": per_frame.get(f, 0),
                "smoothed_dirs": sd,
                "pattern": pattern,
                "confidence": conf,
            })
            pattern_counts[pattern] += 1

        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        out = H1_DATA / f"pattern_inference_v5_{stem}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out.name}")

        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "pattern_counts": dict(pattern_counts),
            "pct_patterns": {p: 100 * n / n_total_frames
                              for p, n in pattern_counts.items()},
        }

    out = H1_DATA / "h12_v5_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
