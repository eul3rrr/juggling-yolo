"""
H79: Per-ball-count calibration of H78 wrist-distance filter.

H78 found that mean_diff_per_frame > 10 catches the Mills Mess
trick (f=890-936 identical) without losing any real FOUNTAIN on
the H70 sample. But the threshold is calibrated for identical
3-ball only. YouTube 5-ball phases have lower mean_diff (4.5-5.6)
and don't trigger the filter.

Hypothesis: A per-ball-count threshold (e.g., 5-ball: 4.0, 3-ball: 10.0)
might catch YouTube's static-hold / real-CASCADE misclassifications
without losing real juggling.

Method: For each FOUNTAIN_3+ phase, apply the per-ball-count
threshold and measure TP/TN/FP/FN on the H70 sample.

Note: The 3-ball YouTube data is f=339-374 only (real FOUNTAIN).
The 5-ball YouTube data has 3 FOUNTAIN_3+ phases (real, static_hold,
real CASCADE mislabeled). The identical data has 3 FOUNTAIN_3+
phases (real, Mills Mess, real).
"""

import csv
import json
import os

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"

# Load H78 data
h78_data = {}
with open(f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["stem"], int(row["phase_start"]), int(row["phase_end"]))
        h78_data[key] = row

# Determine ball count per video (3-ball identical, 5-ball YouTube per H36/H37)
BALL_COUNT = {
    "identical_balls_trick_000_018": 3,
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 5,
}

# Ground truth
GROUND_TRUTH_FOUNTAIN = {
    ("identical_balls_trick_000_018", 631, 669): "FOUNTAIN",
    ("identical_balls_trick_000_018", 890, 936): "OTHER_CROSSED_ARM",  # Mills Mess
    ("identical_balls_trick_000_018", 977, 1011): "FOUNTAIN",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 339, 374): "FOUNTAIN",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594): "STATIC_HOLD",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 800, 861): "CASCADE_REAL",
}


def eval_per_ball_count_threshold(thr_3ball, thr_5ball):
    """Apply per-ball-count threshold to FOUNTAIN_3+ phases only."""
    TP = TN = FP = FN = 0
    for key, verdict in GROUND_TRUTH_FOUNTAIN.items():
        stem, start, end = key
        row = h78_data.get(key)
        if row is None:
            continue
        mean_diff = float(row["mean_diff_per_frame"])
        thr = thr_3ball if BALL_COUNT[stem] == 3 else thr_5ball
        rejected = mean_diff > thr
        keep = not rejected
        is_real = verdict == "FOUNTAIN"
        if keep and is_real:
            TP += 1
        elif keep and not is_real:
            FP += 1
        elif not keep and is_real:
            FN += 1
        else:
            TN += 1
    return TP, TN, FP, FN


def fmt_p_r(TP, TN, FP, FN):
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    return f"P={p if p is None else f'{p:.3f}'}", f"R={r if r is None else f'{r:.3f}'}"


# Test various per-ball-count thresholds
print("Per-ball-count H78 calibration on FOUNTAIN_3+ phases only")
print(f"{'thr_3ball':>10} {'thr_5ball':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6}")
for thr_3 in [8.0, 9.0, 10.0, 11.0, 12.0, 14.0]:
    for thr_5 in [3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0]:
        TP, TN, FP, FN = eval_per_ball_count_threshold(thr_3, thr_5)
        if TP + TN + FP + FN == 0:
            continue
        p = TP / (TP + FP) if (TP + FP) > 0 else None
        r = TP / (TP + FN) if (TP + FN) > 0 else None
        p_s = f"{p:.3f}" if p is not None else "N/A"
        r_s = f"{r:.3f}" if r is not None else "N/A"
        print(f"{thr_3:>10.1f} {thr_5:>10.1f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6}")


# Now check: what is the per-phase mean_diff distribution?
print("\nPer-phase mean_diff for FOUNTAIN_3+ phases:")
for key, verdict in GROUND_TRUTH_FOUNTAIN.items():
    stem, start, end = key
    row = h78_data.get(key)
    if row is None:
        continue
    mean_diff = float(row["mean_diff_per_frame"])
    std = float(row["std_wrist_dist"])
    n_balls = BALL_COUNT[stem]
    print(f"  {n_balls}-ball f={start}-{end} ({verdict}): mean_diff={mean_diff:.2f} std={std:.2f}")

# Compute normalizer per ball count
print("\nMean_diff normalized by n_balls:")
for key, verdict in GROUND_TRUTH_FOUNTAIN.items():
    stem, start, end = key
    row = h78_data.get(key)
    if row is None:
        continue
    mean_diff = float(row["mean_diff_per_frame"])
    n_balls = BALL_COUNT[stem]
    norm = mean_diff / n_balls
    print(f"  {n_balls}-ball f={start}-{end} ({verdict}): mean_diff={mean_diff:.2f} / {n_balls} = {norm:.2f}")


# What if we normalize by n_balls and use a fixed threshold?
print("\nNormalized threshold (mean_diff / n_balls):")
print(f"{'thr_norm':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6}")
for thr_norm in [1.0, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5]:
    TP = TN = FP = FN = 0
    for key, verdict in GROUND_TRUTH_FOUNTAIN.items():
        stem, start, end = key
        row = h78_data.get(key)
        if row is None:
            continue
        mean_diff = float(row["mean_diff_per_frame"])
        n_balls = BALL_COUNT[stem]
        norm = mean_diff / n_balls
        rejected = norm > thr_norm
        keep = not rejected
        is_real = verdict == "FOUNTAIN"
        if keep and is_real:
            TP += 1
        elif keep and not is_real:
            FP += 1
        elif not keep and is_real:
            FN += 1
        else:
            TN += 1
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    p_s = f"{p:.3f}" if p is not None else "N/A"
    r_s = f"{r:.3f}" if r is not None else "N/A"
    print(f"{thr_norm:>10.2f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6}")


# What about the H40v2 LR_variance signal as an additional check?
import glob
h40v2_data = {}
for fpath in glob.glob(f"{DATA_DIR}/h40v2_continuous_*.csv"):
    stem = os.path.basename(fpath).replace("h40v2_continuous_", "").replace(".csv", "")
    with open(fpath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            l = float(row["L40v2"]) if row["L40v2"] not in ("", "None") else 0
            r = float(row["R40v2"]) if row["R40v2"] not in ("", "None") else 0
            h40v2_data[(stem, frame)] = (l, r)


def h74_rejects(stem, start, end):
    lrs = []
    for f in range(start, end + 1):
        if (stem, f) in h40v2_data:
            l, r = h40v2_data[(stem, f)]
            lrs.append(l + r)
    if not lrs:
        return False
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    return var < 0.20


# Now: H75 stack + per-ball-count H78 on FOUNTAIN_3+ only
print("\nH75 stack + per-ball-count H78 (FOUNTAIN_3+ only):")
print(f"{'thr_3ball':>10} {'thr_5ball':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6}")
for thr_3 in [8.0, 10.0, 12.0, 14.0]:
    for thr_5 in [3.0, 4.0, 4.5, 5.0, 5.5, 6.0]:
        TP = TN = FP = FN = 0
        for key, verdict in GROUND_TRUTH_FOUNTAIN.items():
            stem, start, end = key
            row = h78_data.get(key)
            if row is None:
                continue
            mean_diff = float(row["mean_diff_per_frame"])
            spec_conc = float(row["spectral_concentration"])
            h12_conf = float(row.get("mean_confidence", 0.7))
            thr = thr_3 if BALL_COUNT[stem] == 3 else thr_5
            h43 = (h12_conf < 0.55)
            h69 = (spec_conc < 0.15)
            h74 = h74_rejects(stem, start, end)
            h78 = (mean_diff > thr)
            rejected = h43 or h69 or h74 or h78
            keep = not rejected
            is_real = verdict == "FOUNTAIN"
            if keep and is_real:
                TP += 1
            elif keep and not is_real:
                FP += 1
            elif not keep and is_real:
                FN += 1
            else:
                TN += 1
        p = TP / (TP + FP) if (TP + FP) > 0 else None
        r = TP / (TP + FN) if (TP + FN) > 0 else None
        p_s = f"{p:.3f}" if p is not None else "N/A"
        r_s = f"{r:.3f}" if r is not None else "N/A"
        print(f"{thr_3:>10.1f} {thr_5:>10.1f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6}")


# Save
import json
with open(f"{DATA_DIR}/h79_per_ball_count_calibration.json", "w") as f:
    json.dump({
        "ball_count": BALL_COUNT,
        "ground_truth": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in GROUND_TRUTH_FOUNTAIN.items()},
    }, f, indent=2)
print(f"\nWrote {DATA_DIR}/h79_per_ball_count_calibration.json")
