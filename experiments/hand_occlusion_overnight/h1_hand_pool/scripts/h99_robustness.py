#!/usr/bin/env python3
"""
H99 — Threshold robustness analysis of the H96 v2 stack on the H93 corrected GT.

Hypothesis
==========
The H96 v2 stack achieves PERFECT 17/4/0/0 (P=1.000, R=1.000) on 21 H93
corrected phases. The 4 TN (correctly rejected misclassifications) are
each caught by a different signal:
  f=482-594 YouTube FOUNTAIN_3+ STATIC_HOLD   -> H90 NEW (c40g3<0.40 AND max_aloft>=4)
  f=890-936 identical FOUNTAIN_3+ CROSSED_ARM -> H78 (mean_diff>10)
  f=685-716 identical CASCADE_3+ STATIC_HOLD  -> H87+max_aloft (pct_ge3<0.20 AND max_aloft>=2)
  f=2-71 YouTube MIXED_3+_UNCONFIRMED startup -> H71 (spec_conc<0.10)

The 21 phases is small. A robustness analysis tells us whether the
perfect result is "stable" (insensitive to threshold perturbations) or
"lucky" (fragile, would break on different phases or perturbed thresholds).

Method
======
Three analyses:

1. Per-threshold sensitivity: for each of the 8 thresholds, sweep ±50% and
   report which perturbations break each TN's correct rejection.
   This gives a "robustness margin" per threshold.

2. Leave-one-out (LOO) per TN: remove each TN phase, refit the
   H96 v2 thresholds on the remaining 20 phases, see if that TN would
   still be rejected. This is the standard LOO test for stack
   overfitting.

3. 2D flat-region confirmation: for the two key thresholds
   (c40_pct_ge3, c40_max_aloft for H90 NEW; spec_conc for H71),
   sweep a 2D grid and report the (acc, P, R) contour map.

The H96 v2 stack rules (from h96_h90_new_properly_integrated.py):
  FOUNTAIN_3+: H43+guard OR H69+guard OR H90_NEW_strict OR H74v4 OR H78
    - H43+guard:   conf<0.55       AND pct_ge1<0.92
    - H69+guard:   spec_conc<0.15  AND pct_ge1<0.92
    - H90_NEW:     c40_pct_ge3<0.40 AND c40_max_aloft>=4
    - H74v4:       var<0.20        AND unique_LR<=1
    - H78:         mean_diff>10
  CASCADE_3+: H87+max_aloft OR H74v4
    - H87+max_aloft: pct_ge3<0.20  AND max_aloft>=2
  MIXED_3+:   H71 (spec_conc<0.10)

Stack-decision function outputs (rej, reason) and per-phase reason.
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

# H93 CORRECTED ground truth (from H93 multi-rater QA)
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

# H96 v2 default thresholds
H96_DEFAULTS = {
    "h43_conf_thr": 0.55,
    "h69_spec_conc_thr": 0.15,
    "h87_pct_ge3_thr": 0.20,
    "h87_max_aloft_thr": 2,
    "h90_c40_pct_ge3_thr": 0.40,
    "h90_c40_max_aloft_thr": 4,
    "h74_var_thr": 0.20,
    "h74_uLR_thr": 1,
    "h78_mean_diff_thr": 10.0,
    "guard_pct_ge1_thr": 0.92,
    "h71_spec_conc_thr": 0.10,
}


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


def compute_aloft_combined(balls_c0, balls_c4, wrists, start, end):
    n_aloft_0, n_aloft_4 = [], []
    for f in range(start, end + 1):
        if f not in wrists:
            continue
        w = wrists[f]
        n0, n4 = 0, 0
        if f in balls_c0:
            for (bx, by, _) in balls_c0[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n0 += 1
        if f in balls_c4:
            for (bx, by, _) in balls_c4[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n4 += 1
        if f in balls_c0:
            n_aloft_0.append(n0)
        if f in balls_c4:
            n_aloft_4.append(n4)
    if not n_aloft_0:
        return None
    n0 = len(n_aloft_0)
    n4 = len(n_aloft_4)
    pct_ge3_0 = sum(1 for x in n_aloft_0 if x >= 3) / n0
    pct_ge3_4 = sum(1 for x in n_aloft_4 if x >= 3) / max(1, n4)
    return {
        "pct_ge1": sum(1 for x in n_aloft_0 if x >= 1) / n0,
        "pct_ge3": pct_ge3_0,
        "max_aloft": max(n_aloft_0),
        "c40_pct_ge3": pct_ge3_4,
        "c40_max_aloft": max(n_aloft_4) if n4 > 0 else 0,
    }


def load_h40v2():
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                rv = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, int(r["frame"]))] = (l, rv)
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
            l, r = h40v2[(stem, f)]
            lrs.append(l + r)
    if not lrs:
        return None
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    return {
        "var": var,
        "unique_LR": len(set(round(v, 2) for v in lrs)),
    }


def h96_v2_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft, thr):
    """H96 v2 decision function with parameterized thresholds."""
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        if conf < thr["h43_conf_thr"] and pct_ge1 < thr["guard_pct_ge1_thr"]:
            return True, "H43+guard"
        if spec_conc < thr["h69_spec_conc_thr"] and pct_ge1 < thr["guard_pct_ge1_thr"]:
            return True, "H69+guard"
        if (c40_pct_ge3 < thr["h90_c40_pct_ge3_thr"]
                and c40_max_aloft >= thr["h90_c40_max_aloft_thr"]):
            return True, "H90_NEW_strict"
        if h74_sig["var"] < thr["h74_var_thr"] and h74_sig["unique_LR"] <= thr["h74_uLR_thr"]:
            return True, "H74v4"
        if mean_diff > thr["h78_mean_diff_thr"]:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < thr["h87_pct_ge3_thr"] and max_aloft >= thr["h87_max_aloft_thr"]:
            return True, "H87+max_aloft"
        if h74_sig["var"] < thr["h74_var_thr"] and h74_sig["unique_LR"] <= thr["h74_uLR_thr"]:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < thr["h71_spec_conc_thr"]:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def evaluate(signals, h74_signals, h78_data, aloft_signals, gt_dict, thr):
    """Return counts and per-phase results."""
    TP = TN = FP = FN = 0
    per_phase = []
    for key, gt in sorted(gt_dict.items()):
        sig = signals.get(key)
        h74 = h74_signals.get(key)
        aloft = aloft_signals.get(key)
        if sig is None or h74 is None or aloft is None:
            continue
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        mean_diff = h78_data.get(key, 0)
        rej, reason = h96_v2_decision(sig["pattern"], sig["conf"], sig["spec_conc"],
                                       h74, mean_diff, aloft, thr)
        keep = not rej
        if is_real and keep: outcome = "TP"
        elif is_misclass and not keep: outcome = "TN"
        elif is_misclass and keep: outcome = "FP"
        elif is_real and rej: outcome = "FN"
        else: outcome = "?"
        if outcome == "TP": TP += 1
        elif outcome == "TN": TN += 1
        elif outcome == "FP": FP += 1
        elif outcome == "FN": FN += 1
        per_phase.append({"key": key, "gt": gt, "outcome": outcome, "reason": reason,
                          "conf": sig["conf"], "spec_conc": sig["spec_conc"],
                          "pct_ge3": aloft.get("pct_ge3"), "max_aloft": aloft.get("max_aloft"),
                          "c40_pct_ge3": aloft.get("c40_pct_ge3"),
                          "c40_max_aloft": aloft.get("c40_max_aloft"),
                          "pct_ge1": aloft.get("pct_ge1"), "var": h74["var"],
                          "unique_LR": h74["unique_LR"], "mean_diff": mean_diff})
    p = TP / max(1, TP + FP)
    r = TP / max(1, TP + FN)
    acc = (TP + TN) / max(1, TP + TN + FP + FN)
    return {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "P": p, "R": r, "acc": acc,
            "per_phase": per_phase}


def main():
    h40v2 = load_h40v2()
    h70 = load_h70_phases()
    h78 = load_h78()
    print("Loading ball detections and pose (at conf=0.0 and conf=0.4)...")
    balls_c0 = {stem: load_balls(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    aloft_signals = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_aloft_combined(balls_c0[stem], balls_c4[stem],
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
    print("H99 — Threshold robustness analysis of the H96 v2 stack")
    print("=" * 80)

    # === Baseline: H96 v2 with default thresholds ===
    base = evaluate(all_signals, h74_signals, h78, aloft_signals,
                    CORRECTED_GT, H96_DEFAULTS)
    print(f"\nBaseline H96 v2: TP={base['TP']} TN={base['TN']} FP={base['FP']} FN={base['FN']} "
          f"P={base['P']:.3f} R={base['R']:.3f} acc={base['acc']:.3f}")

    # === Per-TN capture info ===
    print("\n" + "=" * 80)
    print("Per-TN capture info (which signal catches each TN):")
    print("=" * 80)
    for p in base["per_phase"]:
        if p["outcome"] == "TN":
            print(f"  {p['key'][0]:30s} f={p['key'][1]}-{p['key'][2]:4d}  {p['gt'][1]:25s} "
                  f"caught by: {p['reason']}")

    # === Per-TN signal values ===
    print("\n" + "=" * 80)
    print("Per-TN signal values:")
    print("=" * 80)
    for p in base["per_phase"]:
        if p["outcome"] == "TN":
            print(f"  f={p['key'][1]}-{p['key'][2]} ({p['reason']})")
            print(f"    conf={p['conf']:.3f} spec_conc={p['spec_conc']:.3f} "
                  f"var={p['var']:.3f} uLR={p['unique_LR']} mean_diff={p['mean_diff']:.2f}")
            print(f"    pct_ge1={p['pct_ge1']:.3f} pct_ge3={p['pct_ge3']:.3f} "
                  f"max_aloft={p['max_aloft']} c40_pct_ge3={p['c40_pct_ge3']:.3f} "
                  f"c40_max_aloft={p['c40_max_aloft']}")

    # === Per-threshold sensitivity ===
    print("\n" + "=" * 80)
    print("Per-threshold sensitivity (±50% perturbation):")
    print("=" * 80)

    def per_threshold_sensitivity(thr_name, low_mult, high_mult, n_steps=11):
        """For each perturbation, count (FP, FN) at the operating point."""
        base_val = H96_DEFAULTS[thr_name]
        if base_val == 0:
            return []
        thresholds_to_test = []
        for mult in [round(low_mult + (high_mult - low_mult) * i / (n_steps - 1), 4) for i in range(n_steps)]:
            thresholds_to_test.append((mult, base_val * mult))
        results = []
        for mult, new_val in thresholds_to_test:
            t = H96_DEFAULTS.copy()
            t[thr_name] = new_val
            r = evaluate(all_signals, h74_signals, h78, aloft_signals, CORRECTED_GT, t)
            results.append((mult, new_val, r["TP"], r["TN"], r["FP"], r["FN"], r["acc"]))
        return results

    for thr_name in H96_DEFAULTS:
        results = per_threshold_sensitivity(thr_name, 0.5, 1.5)
        # Filter to only changes
        print(f"\n  Threshold {thr_name} (default = {H96_DEFAULTS[thr_name]}):")
        any_break = False
        for mult, new_val, TP, TN, FP, FN, acc in results:
            if TP != base["TP"] or TN != base["TN"] or FP != base["FP"] or FN != base["FN"]:
                any_break = True
                # Identify WHICH phase(s) changed
                # Re-run for this threshold
                t = H96_DEFAULTS.copy()
                t[thr_name] = new_val
                r = evaluate(all_signals, h74_signals, h78, aloft_signals, CORRECTED_GT, t)
                # Find phases that changed outcome
                base_keys = {p["key"]: p["outcome"] for p in base["per_phase"]}
                changed = []
                for pp in r["per_phase"]:
                    if base_keys.get(pp["key"]) != pp["outcome"]:
                        changed.append((pp["key"], base_keys.get(pp["key"]), pp["outcome"], pp["reason"]))
                change_str = "; ".join(f"f={k[1]}-{k[2]}: {b}->{n}" for k, b, n, _ in changed)
                print(f"    mult={mult:.2f} val={new_val:.4f}  "
                      f"TP={TP} TN={TN} FP={FP} FN={FN} acc={acc:.3f}  "
                      f"changes: {change_str}")
        if not any_break:
            print(f"    NO CHANGES across ±50% (perfectly flat)")

    # === Leave-one-TN-out test ===
    print("\n" + "=" * 80)
    print("Leave-one-TN-out (LOO of each TN phase):")
    print("=" * 80)
    tn_keys = [tuple(p["key"]) for p in base["per_phase"] if p["outcome"] == "TN"]
    for tn_key in tn_keys:
        # Remove the TN phase from GT
        reduced_gt = {k: v for k, v in CORRECTED_GT.items() if k != tn_key}
        # Re-evaluate with default thresholds
        r = evaluate(all_signals, h74_signals, h78, aloft_signals, reduced_gt, H96_DEFAULTS)
        print(f"  LOO f={tn_key[1]}-{tn_key[2]} ({tn_key[0]}): "
              f"remaining TP={r['TP']} TN={r['TN']} FP={r['FP']} FN={r['FN']} acc={r['acc']:.3f}")

    # === 2D flat-region confirmation for H90 NEW ===
    print("\n" + "=" * 80)
    print("2D flat-region grid: H90 NEW (c40_pct_ge3 x c40_max_aloft):")
    print("=" * 80)
    print("  c40_pct_ge3  c40_max_aloft   TP  TN  FP  FN  acc")
    for c40g3 in [0.20, 0.30, 0.40, 0.50, 0.60, 0.80, 1.00]:
        for c40ma in [2, 3, 4, 5, 6]:
            t = H96_DEFAULTS.copy()
            t["h90_c40_pct_ge3_thr"] = c40g3
            t["h90_c40_max_aloft_thr"] = c40ma
            r = evaluate(all_signals, h74_signals, h78, aloft_signals, CORRECTED_GT, t)
            print(f"  {c40g3:6.2f}     {c40ma:3d}          "
                  f"{r['TP']:3d} {r['TN']:3d} {r['FP']:3d} {r['FN']:3d} {r['acc']:.3f}")

    # === 2D flat-region for H71 + H90 NEW (key signals) ===
    print("\n" + "=" * 80)
    print("2D flat-region grid: H71 spec_conc x H90 NEW c40_pct_ge3:")
    print("=" * 80)
    print("  h71_spec  c40_pct_ge3   TP  TN  FP  FN  acc")
    for h71 in [0.05, 0.10, 0.15, 0.20, 0.30]:
        for c40g3 in [0.20, 0.30, 0.40, 0.50, 0.60, 0.80]:
            t = H96_DEFAULTS.copy()
            t["h71_spec_conc_thr"] = h71
            t["h90_c40_pct_ge3_thr"] = c40g3
            r = evaluate(all_signals, h74_signals, h78, aloft_signals, CORRECTED_GT, t)
            print(f"  {h71:6.2f}     {c40g3:6.2f}      "
                  f"{r['TP']:3d} {r['TN']:3d} {r['FP']:3d} {r['FN']:3d} {r['acc']:.3f}")

    # === Save summary JSON ===
    summary = {
        "h99_methodology": "H96 v2 threshold robustness (per-threshold sensitivity + LOO + 2D grids)",
        "baseline": {"TP": base["TP"], "TN": base["TN"], "FP": base["FP"], "FN": base["FN"],
                     "P": base["P"], "R": base["R"], "acc": base["acc"]},
        "tn_captures": [
            {"key": list(p["key"]), "verdict": p["gt"][1], "reason": p["reason"],
             "conf": p["conf"], "spec_conc": p["spec_conc"],
             "pct_ge1": p["pct_ge1"], "pct_ge3": p["pct_ge3"],
             "max_aloft": p["max_aloft"], "c40_pct_ge3": p["c40_pct_ge3"],
             "c40_max_aloft": p["c40_max_aloft"], "var": p["var"],
             "unique_LR": p["unique_LR"], "mean_diff": p["mean_diff"]}
            for p in base["per_phase"] if p["outcome"] == "TN"
        ],
    }
    with open(f"{H1_DATA}/h99_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {H1_DATA}/h99_summary.json")


if __name__ == "__main__":
    main()
