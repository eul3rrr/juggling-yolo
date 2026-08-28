"""
H78 v3: Sensitivity grid for H78 wrist-distance filter on FOUNTAIN_3+ phases.

Test thresholds on:
- mean_diff_per_frame (a measure of wrist-distance variability)
- std_wrist_dist
- range_wrist_dist

For each threshold, count:
- TP: real FOUNTAIN kept
- TN: misclass FOUNTAIN rejected
- FP: misclass FOUNTAIN kept
- FN: real FOUNTAIN rejected

Ground truth: H65 + H72 + H73 visual QA verdicts.
"""

import csv
import json

CSV_PATH = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data/h78v2_wrist_distance_per_phase.csv"
DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"
GRID_PATH = f"{DATA_DIR}/h78v3_sensitivity_grid.json"

# Load H78v2 data
phases = []
with open(CSV_PATH) as f:
    reader = csv.DictReader(f)
    for row in reader:
        phases.append(row)

# Filter to FOUNTAIN_3+ phases
fountain_phases = [p for p in phases if p["pattern"] == "FOUNTAIN_3+"]
print(f"Found {len(fountain_phases)} FOUNTAIN_3+ phases:")
for p in fountain_phases:
    print(f"  {p['stem'][:5]} f={p['phase_start']}-{p['phase_end']} ({p['verdict']}): "
          f"mean_d={p['mean_diff_per_frame']} std={p['std_wrist_dist']} range={p['range_wrist_dist']}")


def eval_filter(threshold, key, op="gt"):
    """Apply filter, return TP/TN/FP/FN counts."""
    TP = TN = FP = FN = 0
    for p in fountain_phases:
        val = float(p[key])
        keep = (val > threshold) if op == "gt" else (val < threshold)
        is_real = p["verdict"] == "FOUNTAIN"
        if keep and is_real:
            TP += 1
        elif keep and not is_real:
            FP += 1
        elif not keep and is_real:
            FN += 1
        else:
            TN += 1
    precision = TP / (TP + FP) if (TP + FP) > 0 else None
    recall = TP / (TP + FN) if (TP + FN) > 0 else None
    return {
        "TP": TP, "TN": TN, "FP": FP, "FN": FN,
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
    }


# Sensitivity grid: try various thresholds
candidates = []

# mean_diff_per_frame: high = crossed-arm
for thr in [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0, 20.0]:
    candidates.append((f"mean_diff>{thr}", "mean_diff_per_frame", thr, "gt"))

# std_wrist_dist: high = crossed-arm or wide
for thr in [10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0]:
    candidates.append((f"std>{thr}", "std_wrist_dist", thr, "gt"))

# range_wrist_dist
for thr in [40.0, 60.0, 80.0, 100.0, 150.0, 200.0]:
    candidates.append((f"range>{thr}", "range_wrist_dist", thr, "gt"))

# pct_gt200: high = wide stance
for thr in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.70]:
    candidates.append((f"pct_gt200>{thr}", "pct_gt200", thr, "gt"))

# pct_lt80: low = arms not close
for thr in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]:
    candidates.append((f"pct_lt80<{thr}", "pct_lt80", thr, "lt"))

results = []
for name, key, thr, op in candidates:
    res = eval_filter(thr, key, op)
    res["filter"] = name
    res["threshold"] = thr
    res["key"] = key
    res["op"] = op
    results.append(res)

# Sort by recall+precision on rejects
# For FOUNTAIN_3+, we want to KEEP real and REJECT misclass
# High (TP + TN) is best
results_sorted = sorted(results, key=lambda r: (r["TP"] + r["TN"], -r["FP"] - r["FN"]), reverse=True)

print("\nSensitivity grid (top 30 by TP+TN):")
print(f"{'Filter':<25} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6}")
for r in results_sorted[:30]:
    p_str = f"{r['precision']:.3f}" if r['precision'] is not None else "  N/A"
    r_str = f"{r['recall']:.3f}" if r['recall'] is not None else "  N/A"
    print(f"{r['filter']:<25} {r['TP']:>3} {r['TN']:>3} {r['FP']:>3} {r['FN']:>3} {p_str:>6} {r_str:>6}")

# Write JSON
with open(GRID_PATH, "w") as f:
    json.dump({"results": results_sorted, "fountain_phases": fountain_phases}, f, indent=2)
print(f"\nWrote {GRID_PATH}")
