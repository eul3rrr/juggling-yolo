"""
H82 v2: Sensitivity grid for H74v2 (var < 0.20 AND unique_LR <= THR).
"""

import csv
import json
import os
import glob

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"

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

h78_data = {}
with open(f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["stem"], int(row["phase_start"]), int(row["phase_end"]))
        h78_data[key] = row

phase_signals = {}
for fpath in glob.glob(f"{DATA_DIR}/h70_phases_*.csv"):
    with open(fpath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            stem = os.path.basename(fpath).replace("h70_phases_", "").replace(".csv", "")
            key = (stem, int(row["phase_start"]), int(row["phase_end"]))
            phase_signals[key] = {
                "pattern": row["pattern"],
                "n_frames": int(row["n_frames"]),
                "mean_confidence": float(row["mean_confidence"]),
                "spectral_concentration": float(row["spectral_concentration"]),
            }

GROUND_TRUTH = {
    ("identical_balls_trick_000_018", 631, 669): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 685, 716): ("CASCADE_3+", "MANIPULATION"),
    ("identical_balls_trick_000_018", 733, 766): ("CASCADE_3+", "STATIC_HOLD"),
    ("identical_balls_trick_000_018", 890, 936): ("FOUNTAIN_3+", "OTHER_CROSSED_ARM"),
    ("identical_balls_trick_000_018", 977, 1011): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 1029, 1049): ("FOUNTAIN_3+", "OTHER_STATIC_HOLD"),
    ("identical_balls_trick_000_018", 263, 312): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 411, 450): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 549, 578): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 339, 374): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594): ("FOUNTAIN_3+", "STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 800, 861): ("FOUNTAIN_3+", "CASCADE_REAL"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71): ("MIXED_3+_UNCONFIRMED", "STATIC_DEMO"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 114, 255): ("MIXED_3+", "JUGGLING_STARTUP"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 267, 298): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 308, 338): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 375, 410): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 420, 481): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 595, 643): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 769, 799): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 862, 899): ("MIXED_3+", "JUGGLING"),
}


def h74(stem, start, end, unique_max):
    lrs = []
    for f in range(start, end + 1):
        if (stem, f) in h40v2_data:
            l, r = h40v2_data[(stem, f)]
            lrs.append(l + r)
    if not lrs:
        return False, 0, 0
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    unique_LR = len(set(round(v, 2) for v in lrs))
    rejected = (var < 0.20) and (unique_LR <= unique_max)
    return rejected, var, unique_LR


def h71_rejects(pattern, spec_conc):
    if not pattern.startswith("MIXED_3+"):
        return False
    return spec_conc < 0.10


# Sensitivity grid: unique_LR threshold
print("Sensitivity grid for H74v2 unique_LR threshold (H75v2 + H78 mean_diff>10):")
print(f"{'thr_unique':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
for thr_unique in [1, 2, 3, 4, 5, 6]:
    TP = TN = FP = FN = 0
    for key, signals in phase_signals.items():
        stem, start, end = key
        pattern = signals["pattern"]
        h12_conf = signals["mean_confidence"]
        spec_conc = signals["spectral_concentration"]
        h78_row = h78_data.get(key, {})
        mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0

        gt = GROUND_TRUTH.get(key, (pattern, "UNKNOWN"))
        gt_verdict = gt[1]
        is_real = gt_verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
        is_misclass = gt_verdict in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM", "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")

        h43 = (h12_conf < 0.55) and pattern == "FOUNTAIN_3+"
        h69 = (spec_conc < 0.15) and pattern == "FOUNTAIN_3+"
        h74_rej, _, _ = h74(stem, start, end, thr_unique)
        h78 = (mean_diff > 10) and pattern == "FOUNTAIN_3+"
        h71 = h71_rejects(pattern, spec_conc)

        rejected = h43 or h69 or h74_rej or h78 or h71
        keep = not rejected

        if is_real and keep:
            TP += 1
        elif is_misclass and not keep:
            TN += 1
        elif is_misclass and keep:
            FP += 1
        elif is_real and not keep:
            FN += 1

    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    acc = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else None
    p_s = f"{p:.3f}" if p is not None else "N/A"
    r_s = f"{r:.3f}" if r is not None else "N/A"
    acc_s = f"{acc:.3f}" if acc is not None else "N/A"
    print(f"{thr_unique:>10} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6} {acc_s:>6}")


# Also try different LR_var thresholds
print("\nSensitivity grid for H74v2 LR_var threshold (unique_LR<=2 fixed):")
print(f"{'thr_var':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
for thr_var in [0.10, 0.15, 0.18, 0.20, 0.22, 0.25, 0.30]:
    TP = TN = FP = FN = 0
    for key, signals in phase_signals.items():
        stem, start, end = key
        pattern = signals["pattern"]
        h12_conf = signals["mean_confidence"]
        spec_conc = signals["spectral_concentration"]
        h78_row = h78_data.get(key, {})
        mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0

        gt = GROUND_TRUTH.get(key, (pattern, "UNKNOWN"))
        gt_verdict = gt[1]
        is_real = gt_verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
        is_misclass = gt_verdict in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM", "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")

        h43 = (h12_conf < 0.55) and pattern == "FOUNTAIN_3+"
        h69 = (spec_conc < 0.15) and pattern == "FOUNTAIN_3+"
        # Custom H74 with custom var threshold
        lrs = []
        for f in range(start, end + 1):
            if (stem, f) in h40v2_data:
                l, r = h40v2_data[(stem, f)]
                lrs.append(l + r)
        if lrs:
            n = len(lrs)
            mean = sum(lrs) / n
            var = sum((v - mean) ** 2 for v in lrs) / n
            unique_LR = len(set(round(v, 2) for v in lrs))
            h74_rej = (var < thr_var) and (unique_LR <= 2)
        else:
            h74_rej = False
        h78 = (mean_diff > 10) and pattern == "FOUNTAIN_3+"
        h71 = h71_rejects(pattern, spec_conc)

        rejected = h43 or h69 or h74_rej or h78 or h71
        keep = not rejected

        if is_real and keep:
            TP += 1
        elif is_misclass and not keep:
            TN += 1
        elif is_misclass and keep:
            FP += 1
        elif is_real and not keep:
            FN += 1

    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    acc = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else None
    p_s = f"{p:.3f}" if p is not None else "N/A"
    r_s = f"{r:.3f}" if r is not None else "N/A"
    acc_s = f"{acc:.3f}" if acc is not None else "N/A"
    print(f"{thr_var:>10.2f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6} {acc_s:>6}")
