#!/usr/bin/env python3
"""
H94 v5 — H74v4 + H87+max_aloft + H43/H69 pct_ge1 guard + H90 NEW (FOUNTAIN_3+).

Background
==========
H94 v4 (max_aloft=2 + pct_ge1=0.92) achieves 95.2% accuracy on H93
corrected GT (17/3/1/0). The 1 FP is f=482-594 STATIC_HOLD (YouTube),
which the H69+guard wrongly suppresses (pct_ge1=1.0 > 0.92).

Hypothesis
==========
Adding the H90 NEW signal (c40<0.40 AND (max_4>=4 OR drop>0.38)) for
FOUNTAIN_3+ pattern only should catch f=482-594 without affecting
f=800-861 (the only FOUNTAIN_3+ that was wrongly kept in H94 v4).

H94 v5 rule:
    FOUNTAIN_3+:
      H43+guard: conf<0.55 AND pct_ge1<0.92
      H69+guard: spec_conc<0.15 AND pct_ge1<0.92
      H90 NEW: c40_pct_ge3<0.40 AND (max_4>=4 OR drop>0.38)  [NEW]
      H74v4: var<0.20 AND uLR<=1
      H78: mean_diff>10
    CASCADE_3+:
      H87+max_aloft guard: pct_ge3<0.20 AND max_aloft>=2
      H74v4: var<0.20 AND uLR<=1
    MIXED_3+:
      H71: spec_conc<0.10

Method
======
1. Load H40v2 + H70 + H78 + H90 phase features (with c40 + max_4 + drop)
2. Test H94 v5 on H93 corrected GT (21 phases)
3. Test on the 113 manual review pairs (H59 GT)
"""
from __future__ import annotations

import csv
import json
import glob
import math
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


def compute_aloft_features(balls, wrists, start, end):
    n_aloft = []
    for f in range(start, end + 1):
        if f in balls and f in wrists:
            w = wrists[f]
            n = 0
            for (bx, by, _) in balls[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n += 1
            n_aloft.append(n)
    if not n_aloft:
        return None
    n = len(n_aloft)
    return {
        "pct_ge1": sum(1 for x in n_aloft if x >= 1) / n,
        "pct_ge3": sum(1 for x in n_aloft if x >= 3) / n,
        "max_aloft": max(n_aloft),
        "n_frames": n,
    }


def compute_aloft_features_with_conf(balls_c0, balls_c4, wrists, start, end):
    """Compute aloft features at conf=0.0 and conf=0.4 for H90 NEW signal."""
    n_aloft_0, n_aloft_4 = [], []
    for f in range(start, end + 1):
        if f in balls_c0 and f in balls_c4 and f in wrists:
            w = wrists[f]
            n0, n4 = 0, 0
            for (bx, by, _) in balls_c0[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n0 += 1
            for (bx, by, _) in balls_c4[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n4 += 1
            n_aloft_0.append(n0)
            n_aloft_4.append(n4)
    if not n_aloft_0 or not n_aloft_4:
        return None
    n = len(n_aloft_0)
    pct_ge3_0 = sum(1 for x in n_aloft_0 if x >= 3) / n
    pct_ge3_4 = sum(1 for x in n_aloft_4 if x >= 3) / n
    return {
        "c00_pct_ge1": sum(1 for x in n_aloft_0 if x >= 1) / n,
        "c00_pct_ge3": pct_ge3_0,
        "c00_max_aloft": max(n_aloft_0),
        "c40_pct_ge3": pct_ge3_4,
        "c40_max_aloft": max(n_aloft_4),
        "drop_pct_ge3": pct_ge3_0 - pct_ge3_4,
        "n_frames": n,
    }


def load_h40v2():
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                r_v = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, int(r["frame"]))] = (l, r_v)
    return out


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


def load_h78():
    out = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = float(r["mean_diff_per_frame"])
    return out


def compute_h74_signals(h40v2, stem, start, end):
    lrs = []
    for f in range(start, end + 1):
        if (stem, f) in h40v2:
            l, r_v = h40v2[(stem, f)]
            lrs.append(l + r_v)
    if not lrs:
        return None
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    return {
        "var": var,
        "unique_LR": len(set(round(v, 2) for v in lrs)),
    }


def h94_v5_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft,
                    pct_ge1_thr=0.92, max_aloft_thr=2):
    """H94 v5: H74v4 + H87+max_aloft guard + H43/H69 pct_ge1 guard + H90 NEW (FOUNTAIN_3+)."""
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 0) if aloft else 0
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        drop = aloft.get("drop_pct_ge3", 0) if aloft else 0
        if conf < 0.55 and pct_ge1 < pct_ge1_thr:
            return True, "H43+guard"
        if spec_conc < 0.15 and pct_ge1 < pct_ge1_thr:
            return True, "H69+guard"
        # H90 NEW: c40<0.40 AND (max_4>=4 OR drop>0.38)
        if c40_pct_ge3 < 0.40 and (c40_max_aloft >= 4 or drop > 0.38):
            return True, "H90_NEW"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < 0.20 and max_aloft >= max_aloft_thr:
            return True, "H87+max_aloft"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def evaluate(gt_dict, signals, h74_signals, h78_data, aloft_signals,
             decision_fn, name="", pct_ge1_thr=0.92, max_aloft_thr=2):
    TP = TN = FP = FN = 0
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    per_phase = []
    for key, gt in sorted(gt_dict.items()):
        stem, start, end = key
        sig = signals.get(key)
        h74 = h74_signals.get(key)
        aloft = aloft_signals.get(key)
        if sig is None or h74 is None or aloft is None:
            continue
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        mean_diff = h78_data.get(key, 0)
        rej, reason = decision_fn(sig["pattern"], sig["conf"], sig["spec_conc"],
                                   h74, mean_diff, aloft, pct_ge1_thr, max_aloft_thr)
        keep = not rej
        if is_real and keep: outcome = "TP"
        elif is_misclass and not keep: outcome = "TN"
        elif is_misclass and keep: outcome = "FP"
        elif is_real and rej: outcome = "FN"
        else: outcome = "?"
        if stem.startswith("ident"):
            if outcome == "TP": iTP += 1
            elif outcome == "TN": iTN += 1
            elif outcome == "FP": iFP += 1
            elif outcome == "FN": iFN += 1
        else:
            if outcome == "TP": yTP += 1
            elif outcome == "TN": yTN += 1
            elif outcome == "FP": yFP += 1
            elif outcome == "FN": yFN += 1
        if outcome == "TP": TP += 1
        elif outcome == "TN": TN += 1
        elif outcome == "FP": FP += 1
        elif outcome == "FN": FN += 1
        per_phase.append((key, gt, outcome, reason))
    p = TP / max(1, TP+FP)
    r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    pi = iTP / max(1, iTP+iFP)
    ri = iTP / max(1, iTP+iFN)
    ai = (iTP+iTN) / max(1, iTP+iTN+iFP+iFN)
    py = yTP / max(1, yTP+yFP)
    ry = yTP / max(1, yTP+yFN)
    ay = (yTP+yTN) / max(1, yTP+yTN+yFP+yFN)
    return {
        "name": name, "pct_ge1_thr": pct_ge1_thr, "max_aloft_thr": max_aloft_thr,
        "combined": (TP, TN, FP, FN, p, r, acc),
        "ident": (iTP, iTN, iFP, iFN, pi, ri, ai),
        "youtu": (yTP, yTN, yFP, yFN, py, ry, ay),
        "per_phase": per_phase,
    }


def main():
    h40v2 = load_h40v2()
    h70 = load_h70_phases()
    h78 = load_h78()

    # Load balls at conf=0.0 and conf=0.4
    print("Loading ball detections and pose...")
    balls_c0 = {stem: load_balls(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute aloft features (with conf=0.0 and conf=0.4 for H90 NEW)
    aloft_signals = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_aloft_features_with_conf(balls_c0[stem], balls_c4[stem],
                                              wrists_data[stem], start, end)
        if a:
            aloft_signals[key] = a

    EXTRA_SIGNALS = {
        ("identical_balls_trick_000_018", 733, 766): {
            "pattern": "CASCADE_3+", "n_frames": 34, "conf": 0.620, "spec_conc": 0.165,
        },
        ("identical_balls_trick_000_018", 1029, 1049): {
            "pattern": "FOUNTAIN_3+", "n_frames": 21, "conf": 0.463, "spec_conc": 0.140,
        },
    }
    all_signals = {**h70, **EXTRA_SIGNALS}

    h74_signals = {}
    for key in CORRECTED_GT.keys():
        sig = compute_h74_signals(h40v2, *key)
        if sig:
            h74_signals[key] = sig

    print("=" * 80)
    print("H94 v5 — H74v4 + H87+max_aloft + H43/H69 pct_ge1 guard + H90 NEW (FOUNTAIN_3+)")
    print("=" * 80)

    # Per-phase features
    print("\nPer-phase features (including H90 NEW signals):")
    print(f"{'phase':<35} {'verdict':<22} {'c40g3':>6} {'c40mx':>5} {'drop':>5} {'c00g1':>6} {'c00mx':>5} {'H90NEW':>6}")
    for key in sorted(CORRECTED_GT.keys()):
        stem, start, end = key
        sig = aloft_signals.get(key)
        if sig is None:
            continue
        verdict = CORRECTED_GT[key][1]
        label = f"{stem[:5]} f={start}-{end}"
        h90new = (sig["c40_pct_ge3"] < 0.40 and (sig["c40_max_aloft"] >= 4 or sig["drop_pct_ge3"] > 0.38))
        print(f"{label:<35} {verdict:<22} {sig['c40_pct_ge3']:>6.2f} {sig['c40_max_aloft']:>5} {sig['drop_pct_ge3']:>5.2f} {sig['c00_pct_ge1']:>6.2f} {sig['c00_max_aloft']:>5} {str(h90new):>6}")

    # Sensitivity grid
    print("\n=== H94 v5 2D sensitivity grid (max_aloft_thr × pct_ge1_thr) ===")
    print(f"{'max_aloft':>10} {'pct_ge1':>8} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
    for max_a in [1, 2, 3, 4]:
        for pct_g in [0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 1.00]:
            r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, aloft_signals,
                         h94_v5_decision, "H94 v5", pct_ge1_thr=pct_g, max_aloft_thr=max_a)
            c = r["combined"]
            mark = ""
            if c[0] == 17 and c[1] == 4 and c[2] == 0 and c[3] == 0:
                mark = " <-- PERFECT"
            print(f"{max_a:>10} {pct_g:>8.2f} {c[0]:>3} {c[1]:>3} {c[2]:>3} {c[3]:>3} {c[4]:>6.3f} {c[5]:>6.3f} {c[6]:>6.3f}{mark}")

    # Show per-phase for chosen threshold
    chosen = (2, 0.92)
    print(f"\n=== H94 v5 per-phase (max_aloft={chosen[0]}, pct_ge1={chosen[1]}) ===")
    r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, aloft_signals,
                 h94_v5_decision, "H94 v5", pct_ge1_thr=chosen[1], max_aloft_thr=chosen[0])
    c = r["combined"]
    i = r["ident"]
    y = r["youtu"]
    print(f"  Combined: TP={c[0]} TN={c[1]} FP={c[2]} FN={c[3]} P={c[4]:.3f} R={c[5]:.3f} acc={c[6]:.3f}")
    print(f"  ident:    TP={i[0]} TN={i[1]} FP={i[2]} FN={i[3]} P={i[4]:.3f} R={i[5]:.3f} acc={i[6]:.3f}")
    print(f"  youtu:    TP={y[0]} TN={y[1]} FP={y[2]} FN={y[3]} P={y[4]:.3f} R={y[5]:.3f} acc={y[6]:.3f}")

    print(f"\n{'phase':<35} {'verdict':<22} {'outcome':<3} {'reason':<15}")
    for (key, gt, outcome, reason) in r["per_phase"]:
        stem, start, end = key
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {gt[1]:<22} {outcome:<3} {reason:<15}")

    # Save summary
    summary = {
        "H94_v5_methodology": "H74v4 + H87+max_aloft + H43/H69 pct_ge1 guard + H90 NEW (FOUNTAIN_3+)",
        "sensitivity_grid": {},
        "chosen": {"max_aloft_thr": chosen[0], "pct_ge1_thr": chosen[1]},
        "stack_results": {
            "H94_v5": {
                "combined": {"TP": c[0], "TN": c[1], "FP": c[2], "FN": c[3],
                             "P": round(c[4], 3), "R": round(c[5], 3), "acc": round(c[6], 3)},
                "ident": {"TP": i[0], "TN": i[1], "FP": i[2], "FN": i[3],
                          "P": round(i[4], 3), "R": round(i[5], 3), "acc": round(i[6], 3)},
                "youtu": {"TP": y[0], "TN": y[1], "FP": y[2], "FN": y[3],
                          "P": round(y[4], 3), "R": round(y[5], 3), "acc": round(y[6], 3)},
            }
        }
    }
    for max_a in [1, 2, 3, 4]:
        for pct_g in [0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 1.00]:
            r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, aloft_signals,
                         h94_v5_decision, "H94 v5", pct_ge1_thr=pct_g, max_aloft_thr=max_a)
            c = r["combined"]
            i = r["ident"]
            y = r["youtu"]
            summary["sensitivity_grid"][f"maxA_{max_a}_pctG_{pct_g}"] = {
                "combined": {"TP": c[0], "TN": c[1], "FP": c[2], "FN": c[3],
                             "P": round(c[4], 3), "R": round(c[5], 3), "acc": round(c[6], 3)},
                "ident": {"TP": i[0], "TN": i[1], "FP": i[2], "FN": i[3],
                          "P": round(i[4], 3), "R": round(i[5], 3), "acc": round(i[6], 3)},
                "youtu": {"TP": y[0], "TN": y[1], "FP": y[2], "FN": y[3],
                          "P": round(y[4], 3), "R": round(y[5], 3), "acc": round(y[6], 3)},
            }
    with open(f"{H1_DATA}/h94_v5_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h94_v5_summary.json")


if __name__ == "__main__":
    main()
