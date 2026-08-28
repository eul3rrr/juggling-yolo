"""
H78 v4: H43 OR H69 OR H74 OR H78 (wrist-distance) stacked FOUNTAIN_3+ post-filter.

Adds a new rejection criterion: H78 wrist-distance signal
(pct_gt200 > 0.4 OR pct_lt80 < 0.05).

The hypothesis: H78 catches the crossed-arm trick (f=890-936)
which no other filter catches. Should be additive to H43+H69+H74.

Test on the 19-phase H70 sample with H65+H72+H73 ground truth.
"""

import csv
import json
import math
import os
from pathlib import Path

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"
REPORT_PATH = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/reports/h78_report.md"
CSV_OUT = f"{DATA_DIR}/h78v4_stack_per_phase.csv"
SUMMARY_OUT = f"{DATA_DIR}/h78v4_summary.json"

# Load H78 wrist data
h78_data = {}
with open(f"{DATA_DIR}/h78v2_wrist_distance_per_phase.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["stem"], int(row["phase_start"]), int(row["phase_end"]))
        h78_data[key] = row

# H40v2 sustained-occupancy (LR variance) - need to load
h40v2_data = {}
H40V2_FILE = f"{DATA_DIR}/h40v2_continuous_*.csv"
import glob
for fpath in glob.glob(f"{DATA_DIR}/h40v2_continuous_*.csv"):
    stem = os.path.basename(fpath).replace("h40v2_continuous_", "").replace(".csv", "")
    with open(fpath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            l = float(row["L40v2"]) if row["L40v2"] not in ("", "None") else 0
            r = float(row["R40v2"]) if row["R40v2"] not in ("", "None") else 0
            h40v2_data[(stem, frame)] = (l, r)

# Ground truth: H65 + H72 + H73 verdicts (same as H76 used)
GROUND_TRUTH = {
    # stem -> (start, end) -> verdict
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


def h78_rejects(key):
    """Apply H78 wrist-distance filter. Returns True if rejected."""
    row = h78_data.get(key)
    if row is None:
        return False
    pct_gt200 = float(row["pct_gt200"])
    pct_lt80 = float(row["pct_lt80"])
    mean_diff = float(row["mean_diff_per_frame"])
    # New H78 signal: high stance variability (crossed-arm) OR arms never close (not held)
    if pct_gt200 > 0.4 or pct_lt80 < 0.05:
        return True
    return False


def h43_rejects(key, pattern, h12_conf):
    """H43: H12 v8 conf < 0.55. Only for FOUNTAIN_3+ phases."""
    if pattern != "FOUNTAIN_3+":
        return False
    return h12_conf < 0.55


def h69_rejects(key, pattern, spec_conc):
    """H69: spec_conc < 0.15. Only for FOUNTAIN_3+ phases."""
    if pattern != "FOUNTAIN_3+":
        return False
    return spec_conc < 0.15


def h74_rejects(key, stem, start, end):
    """H74: H40v2 L+R variance < 0.20. Only for FOUNTAIN_3+ / CASCADE_3+."""
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


def h71_rejects(key, pattern, spec_conc):
    """H71: spec_conc < 0.10 for MIXED_3+."""
    if not pattern.startswith("MIXED_3+"):
        return False
    return spec_conc < 0.10


# Load H70 phase data with all signal values
H70_PHASE_FILE_PATTERN = f"{DATA_DIR}/h70_phases_*.csv"
phase_signals = {}  # (stem, start, end) -> signals dict
for fpath in glob.glob(H70_PHASE_FILE_PATTERN):
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
                "ac_peak_value": float(row["ac_peak_value"]),
            }

# Now apply all filters
results = []
for key, signals in phase_signals.items():
    stem, start, end = key
    pattern = signals["pattern"]
    h12_conf = signals["mean_confidence"]
    spec_conc = signals["spectral_concentration"]

    h43 = h43_rejects(key, pattern, h12_conf)
    h69 = h69_rejects(key, pattern, spec_conc)
    h74 = h74_rejects(key, stem, start, end)
    h78 = h78_rejects(key)
    h71 = h71_rejects(key, pattern, spec_conc)

    h75_rejected = h43 or h69 or h74  # H75 stack
    h78_stack_rejected = h43 or h69 or h74 or h78  # H78 stack

    # Get ground truth
    gt = GROUND_TRUTH.get(key, (pattern, "UNKNOWN"))
    gt_pattern, gt_verdict = gt

    is_real = gt_verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
    is_misclass = gt_verdict in (
        "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
        "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
    )

    results.append({
        "stem": stem,
        "phase_start": start,
        "phase_end": end,
        "pattern": pattern,
        "gt_verdict": gt_verdict,
        "h12_conf": h12_conf,
        "spec_conc": spec_conc,
        "h43_rejects": h43,
        "h69_rejects": h69,
        "h74_rejects": h74,
        "h78_rejects": h78,
        "h71_rejects": h71,
        "h75_rejected": h75_rejected,
        "h78_stack_rejected": h78_stack_rejected,
        "is_real": is_real,
        "is_misclass": is_misclass,
    })

# Save
os.makedirs(DATA_DIR, exist_ok=True)
with open(CSV_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    writer.writeheader()
    writer.writerows(results)
print(f"Wrote {CSV_OUT}")


def eval_stack(rejected_col, results):
    TP = sum(1 for r in results if r["is_real"] and not r[rejected_col])
    TN = sum(1 for r in results if r["is_misclass"] and r[rejected_col])
    FP = sum(1 for r in results if r["is_misclass"] and not r[rejected_col])
    FN = sum(1 for r in results if r["is_real"] and r[rejected_col])
    return TP, TN, FP, FN


# End-to-end eval
print("\n=== End-to-end eval (all 19 phases) ===")
for col, name in [
    ("h75_rejected", "H43 OR H69 OR H74 (H75 stack)"),
    ("h78_stack_rejected", "H43 OR H69 OR H74 OR H78 (H78 stack)"),
    ("h78_rejects", "H78 only"),
    ("h71_rejects", "H71 only (MIXED)"),
]:
    TP, TN, FP, FN = eval_stack(col, results)
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    fpr = FP / (FP + TN) if (FP + TN) > 0 else None
    print(f"{name}:")
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN}  P={p}  R={r}  FPR={fpr}")
    if TP + TN + FP + FN > 0:
        acc = (TP + TN) / (TP + TN + FP + FN)
        print(f"  accuracy={acc:.3f}")


# Per-pattern breakdown
print("\n=== Per-pattern breakdown ===")
patterns = set(r["pattern"] for r in results)
for pat in sorted(patterns):
    pat_results = [r for r in results if r["pattern"] == pat]
    print(f"\n{pat} (n={len(pat_results)}):")
    for r in pat_results:
        verd = r["gt_verdict"]
        keep75 = not r["h75_rejected"]
        keep78 = not r["h78_stack_rejected"]
        keep_h78_only = not r["h78_rejects"]
        keep_h71 = not r["h71_rejects"]
        diff = "" if keep75 == keep78 else " <-- DIFF"
        print(f"  f={r['phase_start']}-{r['phase_end']} ({verd}): H75_keep={keep75} H78_stack_keep={keep78} H78_only={keep_h78_only} H71={keep_h71}{diff}")


# Summary JSON
summary = {
    "n_phases": len(results),
    "h75_stack": eval_stack("h75_rejected", results),
    "h78_stack": eval_stack("h78_stack_rejected", results),
    "h78_only": eval_stack("h78_rejects", results),
    "h71_only": eval_stack("h71_rejects", results),
}
# Add precision/recall
def add_metrics(s):
    TP, TN, FP, FN = s
    p = TP / (TP + FP) if (TP + FP) > 0 else None
    r = TP / (TP + FN) if (TP + FN) > 0 else None
    fpr = FP / (FP + TN) if (FP + TN) > 0 else None
    acc = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else None
    return {
        "TP": TP, "TN": TN, "FP": FP, "FN": FN,
        "precision": round(p, 3) if p is not None else None,
        "recall": round(r, 3) if r is not None else None,
        "FPR": round(fpr, 3) if fpr is not None else None,
        "accuracy": round(acc, 3) if acc is not None else None,
    }

for k in list(summary.keys()):
    summary[k] = add_metrics(summary[k])

with open(SUMMARY_OUT, "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nWrote {SUMMARY_OUT}")
print(json.dumps(summary, indent=2))
