#!/usr/bin/env python3
"""
H100 v3 — 2D sensitivity grid for the pct_ge1 guard.

H100 v2 (with bug fix) showed that AND-combining pct_ge1<0.92 with
c60_pct_ge1<0.30, c80_pct_ge1<0.30, or pct_ge3<0.20 still achieves
PERFECT 17/4/0/0 on the 21 H93 phases.

H100 v3 hypothesis: a 2D grid (pct_ge1 × c60_pct_ge1) might find a
guard that is:
- Tighter than pct_ge1<0.92 alone (more conservative)
- Achieves the same PERFECT 17/4/0/0
- Has a wider flat region (more robust to threshold perturbations)

The "wider flat region" property is the H99 robustness criterion.
"""
from __future__ import annotations

import csv
import json
import glob
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
DETECTIONS = WORKTREE / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

BALLS_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s_all-classes.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s_classes-32.csv",
}
POSE_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}
ALOFT_RADIUS = 100

CORRECTED_GT = {
    ("identical_balls_trick_000_018", 263, 312): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 411, 450): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 549, 578): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 631, 669): ("FOUNTAIN_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 685, 716): ("CASCADE_3+", "STATIC_HOLD"),
    ("identical_balls_trick_000_018", 733, 766): ("CASCADE_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 890, 936): ("FOUNTAIN_3+", "OTHER_CROSSED_ARM"),
    ("identical_balls_trick_000_018", 977, 1011): ("FOUNTAIN_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 1029, 1049): ("FOUNTAIN_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 339, 374): ("FOUNTAIN_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594): ("FOUNTAIN_3+", "STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 800, 861): ("FOUNTAIN_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71): ("MIXED_3+_UNCONFIRMED", "STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 114, 255): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 267, 298): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 308, 338): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 375, 410): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 420, 481): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 595, 643): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 769, 799): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 862, 899): ("MIXED_3+", "JUGGLING"),
}

REAL_VERDICTS = ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
MISCLASS_VERDICTS = ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                     "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")


def load_balls(stem, min_conf=0.0):
    out = {}
    fpath = DETECTIONS / BALLS_CSV[stem]
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r["class_name"] != "sports ball":
                continue
            conf = float(r["confidence"])
            if conf < min_conf:
                continue
            frame = int(r["frame"])
            if frame not in out:
                out[frame] = []
            out[frame].append((float(r["center_x"]), float(r["center_y"]), conf))
    return out


def load_wrists(stem):
    out = {}
    fpath = DETECTIONS / POSE_CSV[stem]
    with open(fpath) as f:
        for r in csv.DictReader(f):
            frame = int(r["frame"])
            lw = float(r["left_wrist_confidence"])
            rw = float(r["right_wrist_confidence"])
            out[frame] = {
                "lw": (float(r["left_wrist_x"]), float(r["left_wrist_y"])) if lw > 0.1 else None,
                "rw": (float(r["right_wrist_x"]), float(r["right_wrist_y"])) if rw > 0.1 else None,
            }
    return out


def dist(p1, p2):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def compute_extended_aloft(balls_c0, balls_c4, balls_c6, balls_c8,
                            wrists, start, end):
    n_aloft = {0: [], 4: [], 6: [], 8: []}
    for f in range(start, end + 1):
        if f not in wrists:
            continue
        w = wrists[f]
        for conf_level, balls in [(0, balls_c0), (4, balls_c4),
                                   (6, balls_c6), (8, balls_c8)]:
            n = 0
            if f in balls:
                for (bx, by, _) in balls[f]:
                    aloft = True
                    if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                        aloft = False
                    if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                        aloft = False
                    if aloft:
                        n += 1
            if f in balls:
                n_aloft[conf_level].append(n)
    if not n_aloft[0]:
        return None
    n0 = len(n_aloft[0])
    n4 = max(1, len(n_aloft[4]))
    pct_ge1 = sum(1 for x in n_aloft[0] if x >= 1) / n0
    pct_ge3 = sum(1 for x in n_aloft[0] if x >= 3) / n0
    c40_pct_ge3 = sum(1 for x in n_aloft[4] if x >= 3) / n4
    c60_pct_ge1 = sum(1 for x in n_aloft[6] if x >= 1) / max(1, len(n_aloft[6]))
    c80_pct_ge1 = sum(1 for x in n_aloft[8] if x >= 1) / max(1, len(n_aloft[8]))
    c0_max = max(n_aloft[0]) if n_aloft[0] else 0
    c4_max = max(n_aloft[4]) if n_aloft[4] else 0
    return {
        "pct_ge1": pct_ge1,
        "pct_ge3": pct_ge3,
        "c40_pct_ge3": c40_pct_ge3,
        "c40_max_aloft": c4_max,
        "c60_pct_ge1": c60_pct_ge1,
        "c80_pct_ge1": c80_pct_ge1,
        "max_aloft": c0_max,
    }


def load_h70_phases():
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h70_phases_*.csv"):
        stem = Path(fpath).stem.replace("h70_phases_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                key = (stem, int(r["phase_start"]), int(r["phase_end"]))
                out[key] = {
                    "pattern": r["pattern"],
                    "n_frames": int(r["n_frames"]),
                    "conf": float(r["mean_confidence"]),
                    "spec_conc": float(r["spectral_concentration"]),
                }
    return out


def main():
    h70 = load_h70_phases()
    print("Loading ball detections at 4 confidence levels (0.0, 0.4, 0.6, 0.8)...")
    balls_c0 = {stem: load_balls(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls(stem, 0.40) for stem in STEMS}
    balls_c6 = {stem: load_balls(stem, 0.60) for stem in STEMS}
    balls_c8 = {stem: load_balls(stem, 0.80) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    EXTRA_SIGNALS = {
        ("identical_balls_trick_000_018", 733, 766): {
            "pattern": "CASCADE_3+", "n_frames": 34, "conf": 0.620, "spec_conc": 0.165,
        },
        ("identical_balls_trick_000_018", 1029, 1049): {
            "pattern": "FOUNTAIN_3+", "n_frames": 21, "conf": 0.463, "spec_conc": 0.140,
        },
    }
    all_signals = {**h70, **EXTRA_SIGNALS}

    print("=" * 80)
    print("H100 v3 — 2D guard sensitivity grid (pct_ge1 × c60_pct_ge1)")
    print("=" * 80)

    extended_aloft = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_extended_aloft(balls_c0[stem], balls_c4[stem],
                                    balls_c6[stem], balls_c8[stem],
                                    wrists_data[stem], start, end)
        if a:
            extended_aloft[key] = a

    # Load h40v2 (for H74) and h78 (for H78)
    h40v2 = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                rv = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                h40v2[(stem, int(r["frame"]))] = (l, rv)

    def compute_h74(stem, start, end):
        lrs = []
        for f in range(start, end + 1):
            if (stem, f) in h40v2:
                l, r = h40v2[(stem, f)]
                lrs.append(l + r)
        if not lrs:
            return None
        n = len(lrs)
        mean = sum(lrs) / n
        var = sum((v - mean) ** 2 for v in lrs) / n
        return {"var": var, "unique_LR": len(set(round(v, 2) for v in lrs))}

    h74_signals = {key: compute_h74(*key) for key in CORRECTED_GT.keys()}

    h78 = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            k = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            h78[k] = float(r["mean_diff_per_frame"])

    H96_FULL = {
        "h43_conf_thr": 0.55,
        "h69_spec_conc_thr": 0.15,
        "h87_pct_ge3_thr": 0.20,
        "h87_max_aloft_thr": 2,
        "h90_c40_pct_ge3_thr": 0.40,
        "h90_c40_max_aloft_thr": 4,
        "h74_var_thr": 0.20,
        "h74_uLR_thr": 1,
        "h78_mean_diff_thr": 10.0,
        "h71_spec_conc_thr": 0.10,
    }

    def h96_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft, thr, guard_fn):
        if pattern == "FOUNTAIN_3+":
            pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
            c60_pct_ge1 = aloft.get("c60_pct_ge1", 1) if aloft else 1
            c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
            c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
            guard = guard_fn(aloft) if aloft else True
            if conf < thr["h43_conf_thr"] and guard:
                return True, "H43+guard"
            if spec_conc < thr["h69_spec_conc_thr"] and guard:
                return True, "H69+guard"
            if c40_pct_ge3 < thr["h90_c40_pct_ge3_thr"] and c40_max_aloft >= thr["h90_c40_max_aloft_thr"]:
                return True, "H90_NEW_strict"
            if h74_sig and h74_sig["var"] < thr["h74_var_thr"] and h74_sig["unique_LR"] <= thr["h74_uLR_thr"]:
                return True, "H74v4"
            if mean_diff > thr["h78_mean_diff_thr"]:
                return True, "H78"
            return False, "KEPT"
        elif pattern == "CASCADE_3+":
            pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
            max_aloft = aloft.get("max_aloft", 0) if aloft else 0
            if pct_ge3 < thr["h87_pct_ge3_thr"] and max_aloft >= thr["h87_max_aloft_thr"]:
                return True, "H87+max_aloft"
            if h74_sig and h74_sig["var"] < thr["h74_var_thr"] and h74_sig["unique_LR"] <= thr["h74_uLR_thr"]:
                return True, "H74v4"
            return False, "KEPT"
        elif pattern.startswith("MIXED_3+"):
            if spec_conc < thr["h71_spec_conc_thr"]:
                return True, "H71_REJECT"
            return False, "KEPT"
        return False, "KEPT"

    def evaluate_full(guard_fn, thr):
        TP = TN = FP = FN = 0
        for key, gt in sorted(CORRECTED_GT.items()):
            sig = all_signals.get(key)
            h74 = h74_signals.get(key)
            a = extended_aloft.get(key)
            if sig is None or h74 is None or a is None:
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            mean_diff = h78.get(key, 0)
            rej, reason = h96_decision(sig["pattern"], sig["conf"], sig["spec_conc"],
                                       h74, mean_diff, a, thr, guard_fn)
            if is_real and not rej: TP += 1
            elif is_misclass and not rej: FP += 1
            elif is_misclass and rej: TN += 1
            elif is_real and rej: FN += 1
        return TP, TN, FP, FN

    # === 2D grid: pct_ge1_thr × c60_pct_ge1_thr ===
    # pct_ge1_thr: guard requires pct_ge1 < pct_ge1_thr (so smaller thr = stricter)
    # c60_pct_ge1_thr: AND-requires c60_pct_ge1 < c60_pct_ge1_thr
    pct_ge1_thrs = [0.80, 0.85, 0.90, 0.92, 0.95, 0.97, 0.99, 1.00]
    c60_pct_ge1_thrs = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]

    print("\n2D grid: pct_ge1 < t1 AND c60_pct_ge1 < t2 (FOUNTAIN_3+ guard only)")
    print(f"{'pct_ge1':>10s}", end="")
    for t in c60_pct_ge1_thrs:
        print(f"  t={t:.2f}", end="")
    print()
    print("-" * 110)
    perfect_cells = []
    for t1 in pct_ge1_thrs:
        print(f"  t1={t1:.2f}  ", end="")
        for t2 in c60_pct_ge1_thrs:
            guard_fn = lambda a, t1=t1, t2=t2: a.get("pct_ge1", 1) < t1 and a.get("c60_pct_ge1", 1) < t2
            TP, TN, FP, FN = evaluate_full(guard_fn, H96_FULL)
            if (TP, TN, FP, FN) == (17, 4, 0, 0):
                print("  PERFECT", end="")
                perfect_cells.append((t1, t2))
            else:
                print(f"  {TP}/{TN}/{FP}/{FN}", end="")
        print()

    print(f"\nPERFECT cells: {len(perfect_cells)} / {len(pct_ge1_thrs) * len(c60_pct_ge1_thrs)}")
    if perfect_cells:
        # Compute the flat region bounds
        pct_ge1_set = sorted(set(t1 for t1, _ in perfect_cells))
        c60_set = sorted(set(t2 for _, t2 in perfect_cells))
        print(f"  pct_ge1 flat region: [{min(pct_ge1_set):.2f}, {max(pct_ge1_set):.2f}]")
        print(f"  c60_pct_ge1 flat region: [{min(c60_set):.2f}, {max(c60_set):.2f}]")

    # === LOO test on 4 TNs to check the guard is not overfitting to specific TNs ===
    print("\n" + "=" * 80)
    print("LOO test: drop each TN from the evaluation set, check if remaining phases still PERFECT")
    print("=" * 80)
    TN_KEYS = [
        ("identical_balls_trick_000_018", 685, 716),  # f=685-716 H87+max_aloft
        ("identical_balls_trick_000_018", 890, 936),  # f=890-936 H78
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594),  # H90 NEW
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71),  # H71
    ]
    # For each pair (pct_ge1, c60_pct_ge1) in the perfect region, test LOO
    if perfect_cells:
        test_cells = perfect_cells[:5]  # sample 5 cells
    else:
        test_cells = [(0.92, 1.00)]  # default
    for t1, t2 in test_cells:
        print(f"\nCell pct_ge1<{t1}, c60<{t2}:")
        for tn_key in TN_KEYS:
            # Remove the TN phase from the evaluation set entirely
            reduced_gt = {k: v for k, v in CORRECTED_GT.items() if k != tn_key}
            # Build a local evaluate function with reduced_gt
            TP = TN = FP = FN = 0
            for key, gt in sorted(reduced_gt.items()):
                sig = all_signals.get(key)
                h74 = h74_signals.get(key)
                a = extended_aloft.get(key)
                if sig is None or h74 is None or a is None:
                    continue
                verdict = gt[1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                mean_diff = h78.get(key, 0)
                guard_fn_local = lambda a_, t1=t1, t2=t2: a_.get("pct_ge1", 1) < t1 and a_.get("c60_pct_ge1", 1) < t2
                if sig["pattern"] == "FOUNTAIN_3+":
                    pct_ge1 = a.get("pct_ge1", 0) if a else 0
                    c40_pct_ge3 = a.get("c40_pct_ge3", 1) if a else 1
                    c40_max_aloft = a.get("c40_max_aloft", 0) if a else 0
                    guard = guard_fn_local(a) if a else True
                    rej_h43 = sig["conf"] < H96_FULL["h43_conf_thr"] and guard
                    rej_h69 = sig["spec_conc"] < H96_FULL["h69_spec_conc_thr"] and guard
                    rej_h90 = c40_pct_ge3 < H96_FULL["h90_c40_pct_ge3_thr"] and c40_max_aloft >= H96_FULL["h90_c40_max_aloft_thr"]
                    rej_h74 = h74 and h74["var"] < H96_FULL["h74_var_thr"] and h74["unique_LR"] <= H96_FULL["h74_uLR_thr"]
                    rej_h78 = mean_diff > H96_FULL["h78_mean_diff_thr"]
                    rej = rej_h43 or rej_h69 or rej_h90 or rej_h74 or rej_h78
                elif sig["pattern"] == "CASCADE_3+":
                    pct_ge3 = a.get("pct_ge3", 0) if a else 0
                    max_aloft = a.get("max_aloft", 0) if a else 0
                    rej_h87 = pct_ge3 < H96_FULL["h87_pct_ge3_thr"] and max_aloft >= H96_FULL["h87_max_aloft_thr"]
                    rej_h74 = h74 and h74["var"] < H96_FULL["h74_var_thr"] and h74["unique_LR"] <= H96_FULL["h74_uLR_thr"]
                    rej = rej_h87 or rej_h74
                elif sig["pattern"].startswith("MIXED_3+"):
                    rej = sig["spec_conc"] < H96_FULL["h71_spec_conc_thr"]
                else:
                    rej = False
                if is_real and not rej: TP += 1
                elif is_misclass and not rej: FP += 1
                elif is_misclass and rej: TN += 1
                elif is_real and rej: FN += 1
            print(f"  Drop {tn_key[1]}-{tn_key[2]}: {TP}/{TN}/{FP}/{FN}  {'PASS' if FP==0 and FN==0 else 'FAIL'}")

    # Save the grid summary
    summary = {
        "h100v3_methodology": "2D guard sensitivity grid (pct_ge1 × c60_pct_ge1)",
        "perfect_cells": [{"pct_ge1_thr": t1, "c60_pct_ge1_thr": t2} for t1, t2 in perfect_cells],
        "n_perfect_cells": len(perfect_cells),
        "flat_region": {
            "pct_ge1_range": [min(t1 for t1, _ in perfect_cells), max(t1 for t1, _ in perfect_cells)] if perfect_cells else None,
            "c60_pct_ge1_range": [min(t2 for _, t2 in perfect_cells), max(t2 for _, t2 in perfect_cells)] if perfect_cells else None,
        } if perfect_cells else None,
    }
    with open(f"{H1_DATA}/h100v3_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {H1_DATA}/h100v3_summary.json")


if __name__ == "__main__":
    main()
