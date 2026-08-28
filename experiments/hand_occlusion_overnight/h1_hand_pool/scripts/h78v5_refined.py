"""
H78 v5: Refined H78 filter using HIGH mean_diff_per_frame as the
crossed-arm detector.

Looking at the data:
- f=890-936 (crossed-arm): mean_diff = 14.25, std = 65.72
- f=977-1011 (real FOUNTAIN wide): mean_diff = 4.33, std = 17.19
- f=631-669 (real FOUNTAIN tight): mean_diff = 7.76, std = 49.94

The crossed-arm trick has mean_diff > 12, while real FOUNTAIN phases
have mean_diff < 8 (tight) or 4 (wide).

The static hold (f=482-594, f=733-766) has mean_diff < 2.
The real CASCADE mislabel (f=800-861) has mean_diff = 4.89.

A HIGH mean_diff (> 10) catches the crossed-arm trick.
A LOW mean_diff (< 2) catches the static hold.

Stack: H78v5 = (mean_diff > 10) catches crossed-arm
"""

import csv
import json
import math
import os
import glob

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"

# Load H78 wrist data
h78_data = {}
with open(f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["stem"], int(row["phase_start"]), int(row["phase_end"]))
        h78_data[key] = row

# Load H40v2 sustained-occupancy for H74
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

# Ground truth (same as H76)
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


def h43_rejects(pattern, h12_conf):
    if pattern != "FOUNTAIN_3+":
        return False
    return h12_conf < 0.55


def h69_rejects(pattern, spec_conc):
    if pattern != "FOUNTAIN_3+":
        return False
    return spec_conc < 0.15


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


def h78_rejects_v5(key):
    """H78 v5: high mean_diff_per_frame (> 10) catches crossed-arm."""
    row = h78_data.get(key)
    if row is None:
        return False
    mean_diff = float(row["mean_diff_per_frame"])
    return mean_diff > 10.0


def h78_rejects_v5b(key):
    """H78 v5b: high mean_diff (> 10) AND high std (> 50)."""
    row = h78_data.get(key)
    if row is None:
        return False
    mean_diff = float(row["mean_diff_per_frame"])
    std = float(row["std_wrist_dist"])
    return mean_diff > 10.0 and std > 50.0


def h71_rejects(pattern, spec_conc):
    if not pattern.startswith("MIXED_3+"):
        return False
    return spec_conc < 0.10


# Load H70 phase data
phase_signals = {}
for fpath in glob.glob(f"{DATA_DIR}/h70_phases_*.csv"):
    with open(fpath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            stem = os.path.basename(fpath).replace("h70_phases_", "").replace(".csv", "")
            key = (stem, int(row["phase_start"]), int(row["phase_end"]))
            phase_signals[key] = {
                "pattern": row["pattern"],
                "mean_confidence": float(row["mean_confidence"]),
                "spectral_concentration": float(row["spectral_concentration"]),
            }


def eval_filter(reject_fn, results, name):
    TP = TN = FP = FN = 0
    for r in results:
        keep = not r["rejected"]
        if r["is_real"] and keep:
            TP += 1
        elif r["is_misclass"] and not keep:
            TN += 1
        elif r["is_misclass"] and keep:
            FP += 1
        elif r["is_real"] and not keep:
            FN += 1
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    recall = TP / (TP + FN) if (TP + FN) > 0 else None
    fpr = FP / (FP + TN) if (FP + TN) > 0 else None
    acc = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else None
    print(f"{name}: TP={TP} TN={TN} FP={FP} FN={FN} P={p} R={recall} FPR={fpr} acc={acc}")
    return {"TP": TP, "TN": TN, "FP": FP, "FN": FN,
            "precision": round(p, 3) if p is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "FPR": round(fpr, 3) if fpr is not None else None,
            "accuracy": round(acc, 3) if acc is not None else None}


# Build results
all_results = []
for key, signals in phase_signals.items():
    stem, start, end = key
    pattern = signals["pattern"]
    h12_conf = signals["mean_confidence"]
    spec_conc = signals["spectral_concentration"]
    gt = GROUND_TRUTH.get(key, (pattern, "UNKNOWN"))
    gt_verdict = gt[1]
    is_real = gt_verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
    is_misclass = gt_verdict in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM", "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")

    h43 = h43_rejects(pattern, h12_conf)
    h69 = h69_rejects(pattern, spec_conc)
    h74 = h74_rejects(stem, start, end)
    h78v5 = h78_rejects_v5(key)
    h78v5b = h78_rejects_v5b(key)
    h71 = h71_rejects(pattern, spec_conc)

    h75_rejected = h43 or h69 or h74
    h78v5_stack = h75_rejected or h78v5
    h78v5b_stack = h75_rejected or h78v5b
    full_stack = h75_rejected or h78v5 or h71

    all_results.append({
        "stem": stem,
        "phase_start": start,
        "phase_end": end,
        "pattern": pattern,
        "gt_verdict": gt_verdict,
        "is_real": is_real,
        "is_misclass": is_misclass,
        "h43": h43, "h69": h69, "h74": h74,
        "h78v5": h78v5, "h78v5b": h78v5b, "h71": h71,
        "h75_rejected": h75_rejected,
        "h78v5_stack": h78v5_stack,
        "h78v5b_stack": h78v5b_stack,
        "full_stack": full_stack,
    })

print("\n=== End-to-end eval (19 phases) ===")
print("\n-- H75 stack (current best, no H78): --")
for r in all_results:
    r["rejected"] = r["h75_rejected"]
eval_filter(lambda r: r["h75_rejected"], all_results, "H75")

print("\n-- H78v5 stack (H75 OR mean_diff>10): --")
for r in all_results:
    r["rejected"] = r["h78v5_stack"]
eval_filter(lambda r: r["h78v5_stack"], all_results, "H78v5")

print("\n-- H78v5b stack (H75 OR (mean_diff>10 AND std>50)): --")
for r in all_results:
    r["rejected"] = r["h78v5b_stack"]
eval_filter(lambda r: r["h78v5b_stack"], all_results, "H78v5b")

print("\n-- Full stack (H75 OR H78v5 OR H71): --")
for r in all_results:
    r["rejected"] = r["full_stack"]
eval_filter(lambda r: r["full_stack"], all_results, "Full")

# Per-phase detail
print("\n=== Per-phase detail (key FOUNTAIN/CASCADE phases) ===")
key_phases = [r for r in all_results if r["pattern"] in ("FOUNTAIN_3+", "CASCADE_3+")]
for r in key_phases:
    print(f"  {r['stem'][:5]} {r['pattern']} f={r['phase_start']}-{r['phase_end']} ({r['gt_verdict']}): "
          f"H75_keep={not r['h75_rejected']} H78v5_keep={not r['h78v5_stack']} "
          f"h78v5_triggered={r['h78v5']} h43={r['h43']} h69={r['h69']} h74={r['h74']}")

# Sensitivity grid for H78 mean_diff threshold
print("\n=== Sensitivity grid: H78 mean_diff threshold (FOUNTAIN_3+ only) ===")
print(f"{'thr':>6} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6}")
for thr in [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 20.0]:
    TP = TN = FP = FN = 0
    for r in all_results:
        if r["pattern"] != "FOUNTAIN_3+":
            continue
        row = h78_data.get((r["stem"], r["phase_start"], r["phase_end"]))
        if not row:
            continue
        mean_diff = float(row["mean_diff_per_frame"])
        rejected = mean_diff > thr
        keep = not rejected
        is_real = r["gt_verdict"] == "FOUNTAIN"
        if keep and is_real:
            TP += 1
        elif keep and not is_real:
            FP += 1
        elif not keep and is_real:
            FN += 1
        else:
            TN += 1
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    rec = TP / (TP + FN) if (TP + FN) > 0 else None
    p_s = f"{p:.3f}" if p is not None else "N/A"
    r_s = f"{rec:.3f}" if rec is not None else "N/A"
    print(f"{thr:>6.1f} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p_s:>6} {r_s:>6}")
