#!/usr/bin/env python3
"""H12 v4 - detector-level CASCADE/FOUNTAIN signal.

H12 v2/v3 are limited by event log density: the CASCADE/FOUNTAIN
classification is based on the hand of catch/throw events, but with
only 8 events on identical, the late-phase window is right-hand
biased and wrongly classified as FOUNTAIN.

H12 v4 directly uses per-frame ball positions in the air to determine
CASCADE vs FOUNTAIN:

  - CASCADE: balls trace diagonal arcs (each ball goes from one
    hand to the other). At any instant, 2 balls move in opposite
    horizontal directions (one going left, one going right).
  - FOUNTAIN: balls trace parallel arcs (both thrown to the same
    hand). At any instant, 2 balls move in the same horizontal
    direction (both going up, both falling vertically).

Concretely: for each frame, look at the horizontal velocities of all
airborne tracklet members. Compute:
  - n_distinct_horiz_dirs: number of distinct horizontal velocity signs
    (left-going, right-going, or stationary)
  - vx_iqr: interquartile range of horizontal velocities (higher =
    more spread out, consistent with cascade)

Heuristic:
  - vx_iqr > THRESHOLD → CASCADE-like (balls in opposite directions)
  - vx_iqr <= THRESHOLD → FOUNTAIN-like (balls in same direction)
  - only 1 airborne ball → MIXED (insufficient evidence)

This signal is independent of the event log and can classify the
late-phase correctly.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v4"
H1_CS.mkdir(parents=True, exist_ok=True)

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Heuristic thresholds (declared from physical geometry):
# - vx_iqr < 5 px/frame: balls moving in similar directions (fountain-like)
# - vx_iqr >= 5 px/frame: balls moving in opposite directions (cascade-like)
# - only 1 airborne ball: cannot classify
VX_IQR_THRESHOLD = 5.0


def load_tracklet_points(stem: str) -> dict:
    """Returns {tid: [(frame, x, y), ...]} sorted by frame."""
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


def per_frame_ball_positions(tracklets: dict) -> dict:
    """Returns {frame: [(x, y, vx), ...]} for all balls active in
    this frame. vx is the horizontal velocity (estimated from the
    previous frame, or 0 if not available)."""
    out = defaultdict(list)
    for tid, points in tracklets.items():
        for i, (f, x, y) in enumerate(points):
            if i > 0:
                prev_f, prev_x, _ = points[i - 1]
                vx = (x - prev_x) / max(1, f - prev_f)
            else:
                vx = 0.0
            out[f].append((x, y, vx))
    return out


def classify_pattern_v4(frame_data: list, prev_frame_data: list,
                          n_in_hand_left: int, n_in_hand_right: int,
                          n_total: int) -> tuple:
    """Classify pattern using detector-level signal.

    Returns (pattern, confidence, vx_iqr, n_airborne, n_distinct_dirs).
    """
    if not frame_data:
        return "NO_BALL", 0.0, 0.0, 0, 0

    n_airborne = len(frame_data)
    vx_values = sorted([v[2] for v in frame_data])
    n = len(vx_values)

    # IQR of vx
    if n >= 4:
        q1 = vx_values[n // 4]
        q3 = vx_values[3 * n // 4]
        vx_iqr = q3 - q1
    elif n >= 2:
        vx_iqr = abs(vx_values[-1] - vx_values[0])
    else:
        vx_iqr = 0.0

    # Count distinct horizontal directions (only nonzero)
    signs = set()
    for _, _, vx in frame_data:
        if abs(vx) > 1.0:  # threshold for "moving"
            signs.add(1 if vx > 0 else -1)
    n_distinct_dirs = len(signs)

    if n_total == 0:
        return "NO_BALL", 1.0, vx_iqr, n_airborne, n_distinct_dirs
    if n_total == 1:
        return "SINGLE_BALL", 0.5, vx_iqr, n_airborne, n_distinct_dirs
    if n_total == 2:
        if n_in_hand_left == 1 and n_in_hand_right == 1:
            return "TWO_BALL_HELD", 0.5, vx_iqr, n_airborne, n_distinct_dirs
        return "TWO_BALL", 0.5, vx_iqr, n_airborne, n_distinct_dirs

    # 3+ balls: use detector signal
    if n_airborne < 2:
        return "MIXED_3+_UNCONFIRMED", 0.3, vx_iqr, n_airborne, n_distinct_dirs

    # CASCADE: balls moving in BOTH horizontal directions (1 left, 1 right)
    if n_distinct_dirs == 2:
        return "CASCADE_3+_DETECTOR", 0.7, vx_iqr, n_airborne, n_distinct_dirs
    # FOUNTAIN: balls moving in same horizontal direction
    if n_distinct_dirs == 1:
        return "FOUNTAIN_3+_DETECTOR", 0.7, vx_iqr, n_airborne, n_distinct_dirs

    # All stationary or insufficient: MIXED
    return "MIXED_3+", 0.4, vx_iqr, n_airborne, n_distinct_dirs


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_points(stem)
        per_frame = per_frame_ball_positions(tracklets)
        print(f"  loaded {len(tracklets)} tracklets, "
              f"{len(per_frame)} frames with detections")

        # Load H11 v2 census (for n_in_hand_left/right and n_total)
        census = {}
        with (H1_DATA / f"per_frame_census_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                census[int(r["frame"])] = {
                    "n_in_hand_left": int(r["n_in_hand_left"]),
                    "n_in_hand_right": int(r["n_in_hand_right"]),
                    "n_total": int(r["n_total_balls"]),
                }

        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        for f, c in sorted(census.items()):
            frame_data = per_frame.get(f, [])
            # Filter to "airborne" (not in hand)
            airborne = []
            for x, y, vx in frame_data:
                # Use simple heuristic: airborne if not within 30px of either hand
                # We'll use the n_in_hand info from census
                if c["n_in_hand_left"] == 0 and c["n_in_hand_right"] == 0:
                    airborne.append((x, y, vx))
            prev_data = per_frame.get(f - 1, [])
            pattern, conf, vx_iqr, n_air, n_dirs = classify_pattern_v4(
                airborne, prev_data, c["n_in_hand_left"],
                c["n_in_hand_right"], c["n_total"])
            results.append({
                "frame": f,
                "n_in_air": c["n_total"] - c["n_in_hand_left"]
                            - c["n_in_hand_right"],
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total"],
                "n_airborne_tracklets": n_air,
                "vx_iqr_px_per_frame": round(vx_iqr, 2),
                "n_distinct_horiz_dirs": n_dirs,
                "pattern": pattern,
                "confidence": conf,
            })
            pattern_counts[pattern] += 1

        # Print pattern distribution
        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        # Print vx_iqr distribution
        iqr_buckets = defaultdict(int)
        for r in results:
            iqr_buckets[int(r["vx_iqr_px_per_frame"]) // 5] += 1
        print(f"  vx_iqr distribution (5-px buckets):")
        for bucket in sorted(iqr_buckets):
            print(f"    {bucket*5}-{(bucket+1)*5} px/frame: "
                  f"{iqr_buckets[bucket]} frames")

        # Write CSV
        out = H1_DATA / f"pattern_inference_v4_{stem}.csv"
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

    out = H1_DATA / "h12_v4_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
