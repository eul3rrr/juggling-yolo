#!/usr/bin/env python3
"""
H94 — Refine H40v2 LR_variance to avoid false STATIC_HOLD labels on 3-ball patterns.

Background
==========
H93 multi-rater visual QA re-labeling of all 21 H70 phases revealed
that 2/9 identical phases (f=733-766, f=1029-1049) are H40v2 false
STATIC_HOLD labels — they are real 3-ball juggling patterns where
H40v2 LR_variance saturates at "both hands always hold 1 ball" = LR=2.0.

The H82 v1 stack (H43 OR H69 OR H74v2 OR H78 OR H71) on the CORRECTED
ground truth has:
- TP=15, TN=3, FP=1, FN=2 (P=0.938, R=0.882, acc=0.857)

The 2 FN are:
- f=733-766 (was STATIC_HOLD, now JUGGLING per H93): H74v2 wrongly rejects
  (var=0.152, unique_LR=2 → both within thresholds)
- f=1029-1049 (was OTHER_STATIC_HOLD, now JUGGLING per H93): H43 wrongly
  rejects (conf=0.463 < 0.55, FOUNTAIN_3+ pattern)

Hypothesis
==========
H74v4 = var<0.20 AND unique_LR<=1 (truly constant state, not just
stable cycling). A real static hold has exactly 1 unique LR state
(LR=2.0 means both hands are 100% occupied). A juggling pattern that
happens to cycle through LR=2.0 (both hands momentarily hold 1 ball)
will have unique_LR > 1 because the hands don't always both have
exactly 1 ball — they vary.

Additionally, the H43 FOUNTAIN_3+ low-confidence filter (conf < 0.55)
should be tightened to conf < 0.45 for 3-ball patterns because the
H12 v8 conf is poorly calibrated for 3-ball patterns (f=1029-1049
is conf=0.463 which is real juggling per H93).

H94 v1 rule (H74v4 only):
    REJECT if var<0.20 AND unique_LR<=1 (truly constant)
H94 v2 rule (H74v4 + H43 tightening for 3-ball):
    REJECT if (H43 with conf<0.45) OR H69 OR H74v4 OR H78 OR H71

Method
======
1. Load H40v2 LR data for both videos
2. Load H70 phase data with pattern/conf/spec_conc
3. Load H78 mean_diff data
4. Compute H74v4 = var<0.20 AND unique_LR<=1
5. Test on the H93 CORRECTED ground truth (21 phases)
6. Sensitivity grid: unique_LR threshold ∈ {1, 2, 3} × var threshold ∈ {0.15, 0.20, 0.25, 0.30}
7. Sensitivity grid: H43 conf threshold ∈ {0.40, 0.45, 0.50, 0.55}
"""
from __future__ import annotations

import csv
import json
import glob
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H93 CORRECTED ground truth (post-multi-rater-visual-QA)
CORRECTED_GT = {
    ("identical_balls_trick_000_018", 263, 312): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 411, 450): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 549, 578): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 631, 669): ("FOUNTAIN_3+", "JUGGLING"),  # H93 corrected
    ("identical_balls_trick_000_018", 685, 716): ("CASCADE_3+", "STATIC_HOLD"),  # H93 corrected
    ("identical_balls_trick_000_018", 733, 766): ("CASCADE_3+", "JUGGLING"),  # H93 corrected
    ("identical_balls_trick_000_018", 890, 936): ("FOUNTAIN_3+", "OTHER_CROSSED_ARM"),
    ("identical_balls_trick_000_018", 977, 1011): ("FOUNTAIN_3+", "JUGGLING"),  # H93 corrected
    ("identical_balls_trick_000_018", 1029, 1049): ("FOUNTAIN_3+", "JUGGLING"),  # H93 corrected
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 339, 374): ("FOUNTAIN_3+", "JUGGLING"),  # H93 corrected
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594): ("FOUNTAIN_3+", "STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 800, 861): ("FOUNTAIN_3+", "JUGGLING"),  # H93 corrected
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71): ("MIXED_3+_UNCONFIRMED", "STATIC_HOLD"),  # H93 corrected
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 114, 255): ("MIXED_3+", "JUGGLING"),  # H93 corrected
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


def load_h40v2() -> dict:
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                r_v = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, int(r["frame"]))] = (l, r_v)
    return out


def load_h70_phases() -> dict:
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


def load_h78() -> dict:
    out = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = float(r["mean_diff_per_frame"])
    return out


def compute_h74_signals(h40v2, stem, start, end):
    lrs, Ls, Rs = [], [], []
    for f in range(start, end + 1):
        if (stem, f) in h40v2:
            l, r = h40v2[(stem, f)]
            lrs.append(l + r)
            Ls.append(l)
            Rs.append(r)
    if not lrs:
        return None
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    return {
        "var": var,
        "unique_LR": len(set(round(v, 2) for v in lrs)),
        "unique_L": len(set(round(v, 2) for v in Ls)),
        "unique_R": len(set(round(v, 2) for v in Rs)),
        "mean_LR": mean,
        "max_LR": max(lrs),
        "min_LR": min(lrs),
    }


# H82 v1 baseline rule (the H70-evaluated baseline; fails on f=733-766, f=1029-1049 on corrected GT)
def h82_v1_decision(pattern, conf, spec_conc, h74_sig, mean_diff):
    """H82 v1: H74v2 = var<0.20 AND unique_LR<=2"""
    if pattern == "FOUNTAIN_3+":
        if conf < 0.55:
            return True, "H43"
        if spec_conc < 0.15:
            return True, "H69"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 2:
            return True, "H74v2"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 2:
            return True, "H74v2"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


# H94 v1 rule: H74v4 = var<0.20 AND unique_LR<=1 (truly constant)
def h94_v1_decision(pattern, conf, spec_conc, h74_sig, mean_diff):
    """H94 v1: H74v4 = var<0.20 AND unique_LR<=1 (truly constant state)"""
    if pattern == "FOUNTAIN_3+":
        if conf < 0.55:
            return True, "H43"
        if spec_conc < 0.15:
            return True, "H69"
        # H94 v1: require unique_LR <= 1 (truly constant)
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


# H94 v2 rule: H74v4 + tightened H43 (conf<0.45 for 3-ball only)
def h94_v2_decision(pattern, conf, spec_conc, h74_sig, mean_diff):
    """H94 v2: H74v4 + tighten H43 to conf<0.45 (only fires on truly low-conf FOUNTAIN_3+)"""
    if pattern == "FOUNTAIN_3+":
        if conf < 0.45:  # H94 v2: tightened from 0.55
            return True, "H43-tight"
        if spec_conc < 0.15:
            return True, "H69"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def evaluate(gt_dict, signals, h74_signals, h78_data, decision_fn, name=""):
    """Evaluate a decision function on the 21 phases; return per-stem and combined metrics."""
    TP = TN = FP = FN = 0
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    per_phase = []
    for key, gt in sorted(gt_dict.items()):
        stem, start, end = key
        sig = signals.get(key)
        h74 = h74_signals.get(key)
        if sig is None or h74 is None:
            continue
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        mean_diff = h78_data.get(key, 0)
        rej, reason = decision_fn(sig["pattern"], sig["conf"], sig["spec_conc"],
                                   h74, mean_diff)
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
        "name": name,
        "combined": (TP, TN, FP, FN, p, r, acc),
        "ident": (iTP, iTN, iFP, iFN, pi, ri, ai),
        "youtu": (yTP, yTN, yFP, yFN, py, ry, ay),
        "per_phase": per_phase,
    }


def main():
    h40v2 = load_h40v2()
    h70 = load_h70_phases()
    h78 = load_h78()

    # H73/H86 extra signals for the 2 phases NOT in h70_phases
    EXTRA_SIGNALS = {
        ("identical_balls_trick_000_018", 733, 766): {
            "pattern": "CASCADE_3+", "n_frames": 34, "conf": 0.620, "spec_conc": 0.165,
        },
        ("identical_balls_trick_000_018", 1029, 1049): {
            "pattern": "FOUNTAIN_3+", "n_frames": 21, "conf": 0.463, "spec_conc": 0.140,
        },
    }
    all_signals = {**h70, **EXTRA_SIGNALS}

    # Compute h74 signals for all 21 phases
    h74_signals = {}
    for key in CORRECTED_GT.keys():
        sig = compute_h74_signals(h40v2, *key)
        if sig:
            h74_signals[key] = sig

    print("=" * 80)
    print("H94 — H74v4 (unique_LR<=1) and H43-tight (conf<0.45) refinements")
    print("Evaluated on H93 CORRECTED ground truth (21 phases)")
    print("=" * 80)

    # Per-phase H74 signals
    print("\nPer-phase H40v2 LR signals (all 21 phases):")
    print(f"{'phase':<35} {'verdict':<22} {'var':>6} {'uLR':>3} {'uL':>3} {'uR':>3} {'mean':>5} {'max':>4} {'min':>4}")
    for key in sorted(CORRECTED_GT.keys()):
        stem, start, end = key
        sig = all_signals.get(key)
        h74 = h74_signals.get(key)
        if sig is None or h74 is None:
            continue
        verdict = CORRECTED_GT[key][1]
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {verdict:<22} {h74['var']:>6.3f} {h74['unique_LR']:>3} {h74['unique_L']:>3} {h74['unique_R']:>3} {h74['mean_LR']:>5.2f} {h74['max_LR']:>4.1f} {h74['min_LR']:>4.1f}")

    # Evaluate H82 v1 (baseline) and H94 v1/v2 on corrected GT
    print("\n=== End-to-end stack comparison (H93 corrected GT) ===")
    results = []
    for name, dec_fn in [
        ("H82 v1 (H74v2 baseline)", h82_v1_decision),
        ("H94 v1 (H74v4 = var<0.20 AND uLR<=1)", h94_v1_decision),
        ("H94 v2 (H74v4 + H43-tight conf<0.45)", h94_v2_decision),
    ]:
        r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, dec_fn, name=name)
        results.append(r)
        c = r["combined"]
        i = r["ident"]
        y = r["youtu"]
        print(f"\n  {name}:")
        print(f"    combined: TP={c[0]} TN={c[1]} FP={c[2]} FN={c[3]} P={c[4]:.3f} R={c[5]:.3f} acc={c[6]:.3f}")
        print(f"    ident:    TP={i[0]} TN={i[1]} FP={i[2]} FN={i[3]} P={i[4]:.3f} R={i[5]:.3f} acc={i[6]:.3f}")
        print(f"    youtu:    TP={y[0]} TN={y[1]} FP={y[2]} FN={y[3]} P={y[4]:.3f} R={y[5]:.3f} acc={y[6]:.3f}")

    # Per-phase differences
    print("\n=== Per-phase H82v1 vs H94v1 vs H94v2 (H93 corrected GT) ===")
    print(f"{'phase':<35} {'verdict':<22} {'H82v1':<14} {'H94v1':<14} {'H94v2':<14}")
    for r in results[0]["per_phase"]:
        key, gt, _, _ = r
        h82_reason = r[3]
        # find h94v1, h94v2 reasons
        h94v1 = next((x for x in results[1]["per_phase"] if x[0] == key), None)
        h94v2 = next((x for x in results[2]["per_phase"] if x[0] == key), None)
        label = f"{key[0][:5]} f={key[1]}-{key[2]}"
        print(f"{label:<35} {gt[1]:<22} {h82_reason:<14} {h94v1[3] if h94v1 else '?':<14} {h94v2[3] if h94v2 else '?':<14}")

    # Sensitivity grid: unique_LR threshold × var threshold (H74v4)
    print("\n=== H74v4 sensitivity grid (var thr × uLR thr) ===")
    print(f"{'var_thr':>8} {'uLR_thr':>8} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
    for var_thr in [0.15, 0.18, 0.20, 0.22, 0.25, 0.30]:
        for uLR_thr in [1, 2, 3]:
            TP = TN = FP = FN = 0
            for key, gt in CORRECTED_GT.items():
                stem, start, end = key
                sig = all_signals.get(key)
                h74 = h74_signals.get(key)
                if sig is None or h74 is None:
                    continue
                verdict = gt[1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                # H74v4 = var<var_thr AND uLR<=uLR_thr
                h74v4 = h74["var"] < var_thr and h74["unique_LR"] <= uLR_thr
                if h74v4:
                    if is_real: FN += 1
                    else: TN += 1
                else:
                    if is_real: TP += 1
                    else: FP += 1
            p = TP / max(1, TP+FP)
            r = TP / max(1, TP+FN)
            acc = (TP+TN) / max(1, TP+TN+FP+FN)
            mark = ""
            if TP == 16 and TN == 5 and FP == 0 and FN == 0:
                mark = " <-- PERFECT"
            elif TP == 15 and TN == 4 and FP == 1 and FN == 1:
                mark = " <-- 95.2%"
            print(f"{var_thr:>8.2f} {uLR_thr:>8} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p:>6.3f} {r:>6.3f} {acc:>6.3f}{mark}")

    # Sensitivity grid: H43 conf threshold (alone, ignoring H74v4 for now)
    print("\n=== H43 conf threshold sensitivity (FOUNTAIN_3+ only, alone) ===")
    print(f"{'thr':>5} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3}")
    for thr in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        TP = TN = FP = FN = 0
        for key, gt in CORRECTED_GT.items():
            sig = all_signals.get(key)
            if sig is None or sig["pattern"] != "FOUNTAIN_3+":
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            if sig["conf"] < thr:
                if is_real: FN += 1
                else: TN += 1
            else:
                if is_real: TP += 1
                else: FP += 1
        print(f"{thr:>5.2f} {TP:>3} {TN:>3} {FP:>3} {FN:>3}")

    # Save summary
    summary = {
        "H94_methodology": "H74v4 (unique_LR<=1) + H43-tight (conf<0.45) refinements on H93 corrected GT",
        "corrected_gt": {f"{k[0]}_{k[1]}_{k[2]}": v[1] for k, v in CORRECTED_GT.items()},
        "h74_signals": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in h74_signals.items()},
        "stack_results": {
            r["name"]: {
                "combined": {"TP": r["combined"][0], "TN": r["combined"][1],
                             "FP": r["combined"][2], "FN": r["combined"][3],
                             "P": round(r["combined"][4], 3),
                             "R": round(r["combined"][5], 3),
                             "acc": round(r["combined"][6], 3)},
                "ident": {"TP": r["ident"][0], "TN": r["ident"][1],
                          "FP": r["ident"][2], "FN": r["ident"][3],
                          "P": round(r["ident"][4], 3),
                          "R": round(r["ident"][5], 3),
                          "acc": round(r["ident"][6], 3)},
                "youtu": {"TP": r["youtu"][0], "TN": r["youtu"][1],
                          "FP": r["youtu"][2], "FN": r["youtu"][3],
                          "P": round(r["youtu"][4], 3),
                          "R": round(r["youtu"][5], 3),
                          "acc": round(r["youtu"][6], 3)},
            }
            for r in results
        },
    }
    with open(f"{H1_DATA}/h94_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h94_summary.json")


if __name__ == "__main__":
    main()
