"""
H78: Wrist-distance signal as FOUNTAIN_3+ / CASCADE_3+ discriminator.

Hypothesis: A crossed-arm pattern (like f=890-936 identical) has
the two wrists in close proximity (arms are crossed in front of
the body). A real FOUNTAIN (f=631-669) has the wrists apart
(normal juggler stance). A static hold (f=482-594 YouTube) has
similar close wrist distance to a crossed-arm pattern.

Method: For each H70 substantial phase, compute per-frame
|wrist_L - wrist_R| Euclidean distance, then aggregate:
- mean_wrist_dist
- median_wrist_dist
- min_wrist_dist
- std_wrist_dist
- pct_frames_wrists_close (wrist_dist < 100 px)
- pct_frames_wrists_far (wrist_dist > 200 px)

Then test the hypothesis: real FOUNTAIN has HIGH wrist distance
(arms apart), misclassified FOUNTAIN (OTHER) has LOW wrist
distance (arms crossed or static hold).
"""

import csv
import json
import math
import os
from pathlib import Path

# H70 substantial phases (from h70_phases_*.csv)
H70_PHASES = {
    "identical_balls_trick_000_018": [
        ("MIXED_3+", 263, 312, None),
        ("MIXED_3+", 411, 450, None),
        ("MIXED_3+", 549, 578, None),
        ("FOUNTAIN_3+", 631, 669, "FOUNTAIN"),  # real FOUNTAIN
        ("CASCADE_3+", 685, 716, "MANIPULATION"),  # misclass
        ("FOUNTAIN_3+", 890, 936, "OTHER"),  # misclass - crossed-arm
        ("FOUNTAIN_3+", 977, 1011, "FOUNTAIN"),  # real FOUNTAIN
    ],
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": [
        ("MIXED_3+_UNCONFIRMED", 2, 71, "STATIC_DEMO"),
        ("MIXED_3+", 114, 255, "JUGGLING_STARTUP"),
        ("MIXED_3+", 267, 298, "JUGGLING"),
        ("MIXED_3+", 308, 338, "JUGGLING"),
        ("FOUNTAIN_3+", 339, 374, "FOUNTAIN"),  # real FOUNTAIN
        ("MIXED_3+", 375, 410, "JUGGLING"),
        ("MIXED_3+", 420, 481, "JUGGLING"),
        ("FOUNTAIN_3+", 482, 594, "STATIC_HOLD"),  # misclass
        ("MIXED_3+", 595, 643, "JUGGLING"),
        ("MIXED_3+", 769, 799, "JUGGLING"),
        ("FOUNTAIN_3+", 800, 861, "CASCADE"),  # misclass - real CASCADE
        ("MIXED_3+", 862, 899, "JUGGLING"),
    ],
}

# Pose file path
POSE_FILES = {
    "identical_balls_trick_000_018": "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}

# Output paths
DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"
REPORT_PATH = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/reports/h78_report.md"
CSV_PATH = f"{DATA_DIR}/h78_wrist_distance_per_phase.csv"
SUMMARY_PATH = f"{DATA_DIR}/h78_summary.json"


def load_pose(pose_path):
    """Load pose data into a dict frame -> (left_wrist, right_wrist) tuples."""
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
    """Compute Euclidean distance between two wrists. Returns None if any is None."""
    lx, ly, rx, ry = pose
    if None in (lx, ly, rx, ry):
        return None
    return math.sqrt((lx - rx) ** 2 + (ly - ry) ** 2)


def stats_for_phase(poses, start, end):
    """Compute wrist distance statistics for one phase."""
    dists = []
    for f in range(start, end + 1):
        if f in poses:
            d = wrist_dist(poses[f])
            if d is not None:
                dists.append(d)
    if not dists:
        return None
    dists_sorted = sorted(dists)
    n = len(dists)
    mean = sum(dists) / n
    median = dists_sorted[n // 2] if n % 2 == 1 else (dists_sorted[n // 2 - 1] + dists_sorted[n // 2]) / 2
    min_d = dists_sorted[0]
    max_d = dists_sorted[-1]
    std = (sum((d - mean) ** 2 for d in dists) / n) ** 0.5
    pct_close = sum(1 for d in dists if d < 100) / n
    pct_far = sum(1 for d in dists if d > 200) / n
    pct_crossed = sum(1 for d in dists if d < 60) / n  # very close, likely crossed
    return {
        "n_frames_with_pose": n,
        "mean_wrist_dist": round(mean, 2),
        "median_wrist_dist": round(median, 2),
        "min_wrist_dist": round(min_d, 2),
        "max_wrist_dist": round(max_d, 2),
        "std_wrist_dist": round(std, 2),
        "pct_close_lt100": round(pct_close, 3),
        "pct_far_gt200": round(pct_far, 3),
        "pct_crossed_lt60": round(pct_crossed, 3),
    }


def main():
    results = []
    for stem, phases in H70_PHASES.items():
        pose_path = POSE_FILES[stem]
        poses = load_pose(pose_path)
        print(f"{stem}: {len(poses)} pose frames")
        for pattern, start, end, verdict in phases:
            stats = stats_for_phase(poses, start, end)
            if stats is None:
                print(f"  {pattern} f={start}-{end}: NO POSE DATA")
                continue
            row = {
                "stem": stem,
                "pattern": pattern,
                "phase_start": start,
                "phase_end": end,
                "n_frames": end - start + 1,
                "verdict": verdict if verdict else "JUGGLING",
                **stats,
            }
            results.append(row)
            print(f"  {pattern} f={start}-{end} ({verdict}): mean={stats['mean_wrist_dist']} med={stats['median_wrist_dist']} min={stats['min_wrist_dist']} cross={stats['pct_crossed_lt60']:.2f}")

    # Write CSV
    os.makedirs(DATA_DIR, exist_ok=True)
    if results:
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nWrote {CSV_PATH}")

    # Summary
    fountain_phases = [r for r in results if r["pattern"] == "FOUNTAIN_3+"]
    cascade_phases = [r for r in results if r["pattern"] == "CASCADE_3+"]
    mixed_phases = [r for r in results if r["pattern"].startswith("MIXED_3+")]

    # Real vs misclass FOUNTAIN
    real_fountain = [r for r in fountain_phases if r["verdict"] == "FOUNTAIN"]
    misclass_fountain = [r for r in fountain_phases if r["verdict"] != "FOUNTAIN"]

    def mean_stat(rows, key):
        if not rows:
            return None
        return round(sum(r[key] for r in rows) / len(rows), 2)

    summary = {
        "n_phases": len(results),
        "fountain_phases": len(fountain_phases),
        "cascade_phases": len(cascade_phases),
        "mixed_phases": len(mixed_phases),
        "real_fountain_phases": len(real_fountain),
        "misclass_fountain_phases": len(misclass_fountain),
        "real_fountain": {
            "n": len(real_fountain),
            "mean_wrist_dist": mean_stat(real_fountain, "mean_wrist_dist"),
            "median_wrist_dist": mean_stat(real_fountain, "median_wrist_dist"),
            "mean_pct_close": mean_stat(real_fountain, "pct_close_lt100"),
            "mean_pct_crossed": mean_stat(real_fountain, "pct_crossed_lt60"),
        },
        "misclass_fountain": {
            "n": len(misclass_fountain),
            "mean_wrist_dist": mean_stat(misclass_fountain, "mean_wrist_dist"),
            "median_wrist_dist": mean_stat(misclass_fountain, "median_wrist_dist"),
            "mean_pct_close": mean_stat(misclass_fountain, "pct_close_lt100"),
            "mean_pct_crossed": mean_stat(misclass_fountain, "pct_crossed_lt60"),
        },
    }
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {SUMMARY_PATH}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
