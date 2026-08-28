"""
H83: H74v3 with per-hand variation check.

H74v2 (var<0.20 AND unique_LR<=2) wrongly rejects f=267-298
YouTube MIXED_3+ JUGGLING (unique_LR=1) because the 5-ball
juggler has perfect hand-occupancy stability (L=1.0, R=1.0).

The f=267-298 case is unique in having BOTH L=1.0 ALWAYS AND
R=1.0 ALWAYS. Real static holds have variation in at least
one hand (e.g., f=733-766 STATIC_HOLD identical has L=1.0 but
R varies 0-1).

H74v3 hypothesis: A real static hold has variation in at least
one hand. A real 5-ball juggling pattern with stable LR=2.0
has BOTH hands at maximum. The discriminator is:
- H74v3 = var < 0.20 AND (unique_L > 1 OR unique_R > 1)

Test on all 19 H70 substantial phases.
"""

import csv
import json
import os
import glob

DATA_DIR = "/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data"

# Load H40v2 with per-hand tracking
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


def h74_v3(stem, start, end):
    lrs = []
    Ls = []
    Rs = []
    for f in range(start, end + 1):
        if (stem, f) in h40v2_data:
            l, r = h40v2_data[(stem, f)]
            lrs.append(l + r)
            Ls.append(l)
            Rs.append(r)
    if not lrs:
        return False, 0, 0, 0, 0
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    unique_LR = len(set(round(v, 2) for v in lrs))
    unique_L = len(set(round(v, 2) for v in Ls))
    unique_R = len(set(round(v, 2) for v in Rs))
    rejected = (var < 0.20) and (unique_L > 1 or unique_R > 1)
    return rejected, var, unique_LR, unique_L, unique_R


def h71_rejects(pattern, spec_conc):
    if not pattern.startswith("MIXED_3+"):
        return False
    return spec_conc < 0.10


# Per-phase H74v3 detail
print("Per-phase H74v3 detail (var<0.20 AND (unique_L>1 OR unique_R>1)):")
print(f"{'phase':<35} {'verdict':<22} {'var':>6} {'uLR':>3} {'uL':>3} {'uR':>3} {'h74v3':>5}")
for key, gt in sorted(GROUND_TRUTH.items()):
    stem, start, end = key
    rejected, var, uLR, uL, uR = h74_v3(stem, start, end)
    label = f"{stem[:5]} f={start}-{end}"
    verdict = gt[1]
    print(f"{label:<35} {verdict:<22} {var:>6.3f} {uLR:>3} {uL:>3} {uR:>3} {str(rejected):>5}")


# End-to-end stack comparison
print("\n=== End-to-end stack comparison (all 19 phases) ===")
for stack_name, h74_fn, h78_thr in [
    ("H75v2 (H43 OR H69 OR H74v2)", "v2", 999),
    ("H82 v1 (H75v2 OR H78 mean_diff>10)", "v2", 10),
    ("H83 v1 (H43 OR H69 OR H74v3 OR H78 mean_diff>10)", "v3", 10),
    ("H83 v2 (H43 OR H69 OR H74v3 OR H78 mean_diff>8)", "v3", 8),
    ("H83 v3 (H43 OR H69 OR H74v3 OR H78 mean_diff>14)", "v3", 14),
]:
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
        if h74_fn == "v2":
            # H74v2 logic
            rejected_v1, var, uLR, uL, uR = h74_v3(stem, start, end)
            h74_rej = rejected_v1
        else:  # v3
            h74_rej, var, uLR, uL, uR = h74_v3(stem, start, end)
        h78 = (mean_diff > h78_thr) and pattern == "FOUNTAIN_3+"
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
    fpr = FP / (FP + TN) if (FP + TN) > 0 else None
    acc = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else None
    print(f"{stack_name}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p if p is None else f'{p:.3f}'}  R={r if r is None else f'{r:.3f}'}  FPR={fpr if fpr is None else f'{fpr:.3f}'}  acc={acc if acc is None else f'{acc:.3f}'}")

# Save
results = {}
for key, gt in GROUND_TRUTH.items():
    stem, start, end = key
    rejected, var, uLR, uL, uR = h74_v3(stem, start, end)
    results[f"{stem}_{start}_{end}"] = {
        "verdict": gt[1],
        "var": round(var, 4),
        "unique_LR": uLR,
        "unique_L": uL,
        "unique_R": uR,
        "h74v3_rejects": rejected,
    }

with open(f"{DATA_DIR}/h83_h74v3.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nWrote {DATA_DIR}/h83_h74v3.json")
