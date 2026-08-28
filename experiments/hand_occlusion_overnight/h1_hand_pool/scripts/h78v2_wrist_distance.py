"""
H78 v2: Detailed wrist-distance temporal analysis.

Hypothesis refinement: The crossed-arm trick (f=890-936) and the
real FOUNTAIN (f=631-669) might both have similar mean wrist distances
but DIFFERENT temporal patterns. A crossed-arm pattern has the wrists
locked close together (low std), while a real FOUNTAIN has the wrists
cycling apart and together (high std).

Method: For each H70 substantial phase, compute additional statistics:
- std_wrist_dist
- range_wrist_dist (max - min)
- pct_frames_wrists_very_close (< 80 px)
- pct_frames_wrists_very_far (> 200 px)
- mean_diff_wrist_dist (avg of |Δ wrist_dist|)
- median_diff_wrist_dist

Plus spectral analysis: does wrist_dist have a dominant frequency
similar to the ball-aloft pattern?

For FOUNTAIN_3+ phases, compare:
- real FOUNTAIN (3 phases) vs misclass (3 phases)
- within-stem and cross-stem
"""

import csv
import json
import math
import os
from pathlib import Path

H70_PHASES = {
    "identical_balls_trick_000_018": [
        ("FOUNTAIN_3+", 631, 669, "FOUNTAIN"),
        ("FOUNTAIN_3+", 890, 936, "OTHER_CROSSED_ARM"),
        ("FOUNTAIN_3+", 977, 1011, "FOUNTAIN"),
        ("CASCADE_3+", 685, 716, "MANIPULATION"),
        ("CASCADE_3+", 733, 766, "STATIC_HOLD"),
    ],
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": [
        ("MIXED_3+_UNCONFIRMED", 2, 71, "STATIC_DEMO"),
        ("MIXED_3+", 114, 255, "JUGGLING_STARTUP"),
        ("FOUNTAIN_3+", 339, 374, "FOUNTAIN"),
        ("FOUNTAIN_3+", 482, 594, "STATIC_HOLD"),
        ("FOUNTAIN_3+", 800, 861, "CASCADE"),
        ("MIXED_3+", 769, 799, "JUGGLING"),
    ],
}

POSE_FILES = {
    "identical_balls_trick_000_018": "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"
CSV_PATH = f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv"
SUMMARY_PATH = f"{DATA_DIR}/h78v2_summary.json"


def load_pose(pose_path):
    poses = {}
    with open(pose_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            lx = float(row["left_wrist_x"]) if row["left_wrist_x"] else None
            ly = float(row["left_wrist_y"]) if row["left_wrist_y"] else None
            rx = float(row["right_wrist_x"]) if row["right_wrist_x"] else None
            ry = float(row["right_wrist_y"]) if row["right_wrist_y"] else None
            poses[frame] = (lx, ly, rx, ry)
    return poses


def wrist_dist(pose):
    lx, ly, rx, ry = pose
    if None in (lx, ly, rx, ry):
        return None
    return math.sqrt((lx - rx) ** 2 + (ly - ry) ** 2)


def stats_for_phase(poses, start, end):
    dists = []
    for f in range(start, end + 1):
        if f in poses:
            d = wrist_dist(poses[f])
            if d is not None:
                dists.append((f, d))
    if not dists:
        return None

    values = [d for _, d in dists]
    n = len(values)
    mean = sum(values) / n
    sorted_v = sorted(values)
    median = sorted_v[n // 2] if n % 2 == 1 else (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2
    min_d = sorted_v[0]
    max_d = sorted_v[-1]
    std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5

    # Frame-to-frame diff
    diffs = [abs(values[i+1] - values[i]) for i in range(n-1)]
    mean_diff = sum(diffs) / len(diffs) if diffs else 0
    max_diff = max(diffs) if diffs else 0

    # Periodicity: autocorrelation peak
    # Using a simple ACF over lags 1..min(n//2, 20)
    if n >= 5:
        max_lag = min(n // 2, 20)
        norm = sum((v - mean) ** 2 for v in values)
        if norm > 0:
            ac_peaks = []
            for lag in range(1, max_lag + 1):
                ac = sum((values[i] - mean) * (values[i+lag] - mean) for i in range(n - lag)) / norm
                ac_peaks.append((lag, ac))
            ac_peak_lag, ac_peak_val = max(ac_peaks, key=lambda x: x[1])
        else:
            ac_peak_lag, ac_peak_val = 0, 0
    else:
        ac_peak_lag, ac_peak_val = 0, 0

    # Thresholds
    pct_lt80 = sum(1 for v in values if v < 80) / n
    pct_lt100 = sum(1 for v in values if v < 100) / n
    pct_gt200 = sum(1 for v in values if v > 200) / n
    pct_gt250 = sum(1 for v in values if v > 250) / n

    # Range
    range_d = max_d - min_d

    return {
        "n_frames": n,
        "mean_wrist_dist": round(mean, 2),
        "median_wrist_dist": round(median, 2),
        "min_wrist_dist": round(min_d, 2),
        "max_wrist_dist": round(max_d, 2),
        "range_wrist_dist": round(range_d, 2),
        "std_wrist_dist": round(std, 2),
        "mean_diff_per_frame": round(mean_diff, 2),
        "max_diff_per_frame": round(max_diff, 2),
        "ac_peak_lag": ac_peak_lag,
        "ac_peak_value": round(ac_peak_val, 3),
        "pct_lt80": round(pct_lt80, 3),
        "pct_lt100": round(pct_lt100, 3),
        "pct_gt200": round(pct_gt200, 3),
        "pct_gt250": round(pct_gt250, 3),
    }


def main():
    results = []
    for stem, phases in H70_PHASES.items():
        poses = load_pose(POSE_FILES[stem])
        for pattern, start, end, verdict in phases:
            stats = stats_for_phase(poses, start, end)
            if stats is None:
                continue
            row = {
                "stem": stem,
                "pattern": pattern,
                "phase_start": start,
                "phase_end": end,
                "verdict": verdict,
                **stats,
            }
            results.append(row)
            print(f"  {stem[:5]} {pattern} f={start}-{end} ({verdict}): mean={stats['mean_wrist_dist']} std={stats['std_wrist_dist']} range={stats['range_wrist_dist']} ac_peak={stats['ac_peak_value']}@lag{stats['ac_peak_lag']}")

    if results:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nWrote {CSV_PATH}")

    # Summary
    fountain_real = [r for r in results if r["pattern"] == "FOUNTAIN_3+" and r["verdict"] == "FOUNTAIN"]
    fountain_misclass = [r for r in results if r["pattern"] == "FOUNTAIN_3+" and r["verdict"] != "FOUNTAIN"]

    def mean_stat(rows, key):
        if not rows:
            return None
        return round(sum(r[key] for r in rows) / len(rows), 2)

    summary = {
        "n_phases": len(results),
        "real_fountain": {
            "n": len(fountain_real),
            "mean_wrist_dist": mean_stat(fountain_real, "mean_wrist_dist"),
            "std_wrist_dist": mean_stat(fountain_real, "std_wrist_dist"),
            "mean_diff_per_frame": mean_stat(fountain_real, "mean_diff_per_frame"),
            "pct_lt80": mean_stat(fountain_real, "pct_lt80"),
            "pct_gt200": mean_stat(fountain_real, "pct_gt200"),
            "ac_peak_value": mean_stat(fountain_real, "ac_peak_value"),
        },
        "misclass_fountain": {
            "n": len(fountain_misclass),
            "mean_wrist_dist": mean_stat(fountain_misclass, "mean_wrist_dist"),
            "std_wrist_dist": mean_stat(fountain_misclass, "std_wrist_dist"),
            "mean_diff_per_frame": mean_stat(fountain_misclass, "mean_diff_per_frame"),
            "pct_lt80": mean_stat(fountain_misclass, "pct_lt80"),
            "pct_gt200": mean_stat(fountain_misclass, "pct_gt200"),
            "ac_peak_value": mean_stat(fountain_misclass, "ac_peak_value"),
        },
        "per_phase": results,
    }

    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {SUMMARY_PATH}")
    print("\nSummary by FOUNTAIN class:")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_phase"}, indent=2))


if __name__ == "__main__":
    main()
