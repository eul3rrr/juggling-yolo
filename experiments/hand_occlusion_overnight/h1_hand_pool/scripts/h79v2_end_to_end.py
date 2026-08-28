"""
H79 v2: H75 + per-ball-count H78 end-to-end on all 19 H70 substantial phases.

Key question: does the per-ball-count calibration help end-to-end
on the H70 sample (not just FOUNTAIN_3+ only)?
"""

import csv
import json
import os
import glob

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"

# Load H78 data
h78_data = {}
with open(f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["stem"], int(row["phase_start"]), int(row["phase_end"]))
        h78_data[key] = row

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
                "n_frames": int(row["n_frames"]),
                "mean_confidence": float(row["mean_confidence"]),
                "spectral_concentration": float(row["spectral_concentration"]),
            }

# Load H40v2
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

# Ball count
BALL_COUNT = {
    "identical_balls_trick_000_018": 3,
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 5,
}

# Ground truth
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


def h71_rejects(pattern, spec_conc):
    if not pattern.startswith("MIXED_3+"):
        return False
    return spec_conc < 0.10


def eval_stack(thr_3, thr_5, results, name):
    TP = TN = FP = FN = 0
    for r in results:
        rejected = r["rejected"]
        keep = not rejected
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
    print(f"{name}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p if p is None else f'{p:.3f}'}  R={recall if recall is None else f'{recall:.3f}'}  FPR={fpr if fpr is None else f'{fpr:.3f}'}  acc={acc if acc is None else f'{acc:.3f}'}")
    return TP, TN, FP, FN, p, recall, fpr, acc


# Build results for each per-ball-count threshold
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

    h78_row = h78_data.get(key, {})
    mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0

    all_results.append({
        "stem": stem,
        "phase_start": start,
        "phase_end": end,
        "pattern": pattern,
        "gt_verdict": gt_verdict,
        "is_real": is_real,
        "is_misclass": is_misclass,
        "h43": (h12_conf < 0.55) and pattern == "FOUNTAIN_3+",
        "h69": (spec_conc < 0.15) and pattern == "FOUNTAIN_3+",
        "h74": h74_rejects(stem, start, end),
        "h78_mean_diff": mean_diff,
        "h71": h71_rejects(pattern, spec_conc),
        "n_balls": BALL_COUNT[stem],
    })


# Test different per-ball-count thresholds
print("Per-ball-count H78 threshold grid (H75 + per-ball-count H78 + H71):")
print(f"{'thr_3ball':>10} {'thr_5ball':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'FPR':>6} {'acc':>6}")
for thr_3 in [8.0, 10.0, 12.0, 14.0]:
    for thr_5 in [4.0, 4.5, 5.0, 5.5]:
        for r in all_results:
            thr = thr_3 if r["n_balls"] == 3 else thr_5
            h78_triggered = (r["h78_mean_diff"] > thr) and r["pattern"] == "FOUNTAIN_3+"
            r["rejected"] = r["h43"] or r["h69"] or r["h74"] or h78_triggered or r["h71"]
        eval_stack(thr_3, thr_5, all_results, f"thr_3={thr_3} thr_5={thr_5}")


# Now: H75 + H78 single threshold (10) for reference
print("\nFor reference, H75 + H78 single threshold (10):")
for r in all_results:
    h78_triggered = (r["h78_mean_diff"] > 10) and r["pattern"] == "FOUNTAIN_3+"
    r["rejected"] = r["h43"] or r["h69"] or r["h74"] or h78_triggered or r["h71"]
eval_stack(10, 10, all_results, "H78 single thr=10")


# Per-phase detail for the optimal per-ball-count setting
print("\n\n=== Per-phase detail for thr_3=10, thr_5=4.5 ===")
for r in all_results:
    thr = 10 if r["n_balls"] == 3 else 4.5
    h78_triggered = (r["h78_mean_diff"] > thr) and r["pattern"] == "FOUNTAIN_3+"
    rejected = r["h43"] or r["h69"] or r["h74"] or h78_triggered or r["h71"]
    keep = not rejected
    diff_marker = "  <-- DIFF" if r["pattern"] == "FOUNTAIN_3+" else ""
    print(f"  {r['stem'][:5]} {r['pattern']} f={r['phase_start']}-{r['phase_end']} ({r['gt_verdict']}): mean_diff={r['h78_mean_diff']:.2f} (thr={thr}) keep={keep}{diff_marker}")
