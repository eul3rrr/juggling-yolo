#!/usr/bin/env python3
"""
H100 v2 — Combined guard signature analysis.

H100 v1 found that c80_pct_ge1 separates REAL protected phases (low)
from MISCLASS phases (high), with overlap at c80_pct_ge1 ∈ [0.25, 0.40].

Combined signal: pct_ge1 > 0.92 AND c80_pct_ge1 < 0.50 might work as
a more robust guard than the brittle pct_ge1 > 0.92 hard cap.
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
    print("H100 v2 — Combined guard signature analysis")
    print("=" * 80)
    print("\nComputing extended aloft features for all 21 H93 phases...")

    extended_aloft = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_extended_aloft(balls_c0[stem], balls_c4[stem],
                                    balls_c6[stem], balls_c8[stem],
                                    wrists_data[stem], start, end)
        if a:
            extended_aloft[key] = a

    H96_DEFAULTS = {
        "h43_conf_thr": 0.55,
        "h69_spec_conc_thr": 0.15,
        "h90_c40_pct_ge3_thr": 0.40,
        "h90_c40_max_aloft_thr": 4,
    }

    def evaluate_with_guard(gt_dict, signals, aloft_signals, guard_fn, thr, name=""):
        """Evaluate with a custom guard function. Returns (TP, TN, FP, FN)."""
        TP = TN = FP = FN = 0
        per_phase = []
        for key, gt in sorted(gt_dict.items()):
            sig = signals.get(key)
            a = aloft_signals.get(key)
            if sig is None or a is None:
                continue
            if sig["pattern"] != "FOUNTAIN_3+":
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            guard = guard_fn(a)
            would_h43 = sig["conf"] < thr["h43_conf_thr"] and guard
            would_h69 = sig["spec_conc"] < thr["h69_spec_conc_thr"] and guard
            rej = would_h43 or would_h69
            if is_real and not rej: TP += 1
            elif is_misclass and rej: TN += 1
            elif is_misclass and not rej: FP += 1
            elif is_real and rej: FN += 1
            per_phase.append((key, is_real, is_misclass, rej, a["pct_ge1"],
                              a["pct_ge3"], a["c40_pct_ge3"], a["c60_pct_ge1"], a["c80_pct_ge1"]))
        return TP, TN, FP, FN, per_phase

    # Per-FOUNTAIN_3+-phase table
    print("\n" + "=" * 80)
    print("FOUNTAIN_3+ phases (n=7):")
    print("=" * 80)
    print(f"{'Phase':30s} {'verdict':18s} {'pct_ge1':>8s} {'pct_ge3':>8s} "
          f"{'c40g3':>8s} {'c60g1':>8s} {'c80g1':>8s} {'conf':>6s} {'spec_c':>7s}")
    f3_phases = []
    for key, gt in sorted(CORRECTED_GT.items()):
        if gt[0] != "FOUNTAIN_3+":
            continue
        sig = all_signals.get(key)
        a = extended_aloft.get(key)
        if sig is None or a is None:
            continue
        f3_phases.append((key, gt, sig, a))
        print(f"  {key[0][:25]:25s} f={key[1]}-{key[2]:4d} {gt[1]:18s} "
              f"{a['pct_ge1']:>8.3f} {a['pct_ge3']:>8.3f} {a['c40_pct_ge3']:>8.3f} "
              f"{a['c60_pct_ge1']:>8.3f} {a['c80_pct_ge1']:>8.3f} "
              f"{sig['conf']:>6.3f} {sig['spec_conc']:>7.3f}")

    # Test combined guards
    print("\n" + "=" * 80)
    print("Guard candidates (FOUNTAIN_3+ only):")
    print("=" * 80)
    print(f"{'Guard candidate':50s} {'TP':>3s} {'TN':>3s} {'FP':>3s} {'FN':>3s} {'acc':>6s} {'comment':>30s}")
    print("-" * 130)

    guard_candidates = [
        ("default pct_ge1<0.92", lambda a: a["pct_ge1"] < 0.92),
        ("pct_ge1<0.92 AND c80_pct_ge1<0.50", lambda a: a["pct_ge1"] < 0.92 and a["c80_pct_ge1"] < 0.50),
        ("pct_ge1<0.92 AND c80_pct_ge1<0.30", lambda a: a["pct_ge1"] < 0.92 and a["c80_pct_ge1"] < 0.30),
        ("pct_ge1<0.92 AND c60_pct_ge1<0.50", lambda a: a["pct_ge1"] < 0.92 and a["c60_pct_ge1"] < 0.50),
        ("pct_ge1<0.92 AND c60_pct_ge1<0.30", lambda a: a["pct_ge1"] < 0.92 and a["c60_pct_ge1"] < 0.30),
        ("pct_ge1<0.92 AND pct_ge3<0.20", lambda a: a["pct_ge1"] < 0.92 and a["pct_ge3"] < 0.20),
        ("pct_ge1<0.92 AND pct_ge3<0.10", lambda a: a["pct_ge1"] < 0.92 and a["pct_ge3"] < 0.10),
        ("pct_ge1<0.95", lambda a: a["pct_ge1"] < 0.95),
        ("pct_ge1<1.00 (no cap)", lambda a: a["pct_ge1"] < 1.00),
        ("always True (no guard)", lambda a: True),
        ("pct_ge1<0.92 OR c80_pct_ge1<0.20", lambda a: a["pct_ge1"] < 0.92 or a["c80_pct_ge1"] < 0.20),
        ("pct_ge1<0.92 OR c60_pct_ge1<0.20", lambda a: a["pct_ge1"] < 0.92 or a["c60_pct_ge1"] < 0.20),
    ]
    for name, guard_fn in guard_candidates:
        TP, TN, FP, FN, _ = evaluate_with_guard(CORRECTED_GT, all_signals, extended_aloft, guard_fn, H96_DEFAULTS)
        acc = (TP + TN) / max(1, TP + TN + FP + FN)
        comment = "PERFECT" if (TP == 5 and TN == 2 and FP == 0 and FN == 0) else \
                  ("loses real" if FN > 0 else "loses TN" if TN < 2 else "no effect")
        print(f"  {name:50s} {TP:>3d} {TN:>3d} {FP:>3d} {FN:>3d} {acc:>6.3f} {comment:>30s}")

    # Combined approach: test the FULL H96 v2 stack (not just FOUNTAIN_3+)
    print("\n" + "=" * 80)
    print("FULL stack evaluation with custom guards:")
    print("=" * 80)
    print("Pattern-specific: H43+H69 apply only to FOUNTAIN_3+")

    def h96_decision_with_guard(pattern, conf, spec_conc, h74_sig, mean_diff, aloft, thr, guard_fn):
        if pattern == "FOUNTAIN_3+":
            pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
            c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
            c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
            guard = guard_fn(aloft) if aloft else True
            if conf < thr["h43_conf_thr"] and guard:
                return True, "H43+guard"
            if spec_conc < thr["h69_spec_conc_thr"] and guard:
                return True, "H69+guard"
            if c40_pct_ge3 < thr["h90_c40_pct_ge3_thr"] and c40_max_aloft >= thr["h90_c40_max_aloft_thr"]:
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

    # We need h40v2 for h74. Load it.
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
    h40v2 = load_h40v2()

    def load_h78():
        out = {}
        with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
            for r in csv.DictReader(fh):
                key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
                out[key] = float(r["mean_diff_per_frame"])
        return out
    h78 = load_h78()

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

    def evaluate_full(gt_dict, signals, h74_signals, h78_data, aloft_signals, guard_fn, thr):
        TP = TN = FP = FN = 0
        per_phase = []
        for key, gt in sorted(gt_dict.items()):
            sig = signals.get(key)
            h74 = h74_signals.get(key)
            a = aloft_signals.get(key)
            if sig is None or h74 is None or a is None:
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            mean_diff = h78_data.get(key, 0)
            rej, reason = h96_decision_with_guard(sig["pattern"], sig["conf"], sig["spec_conc"],
                                                   h74, mean_diff, a, thr, guard_fn)
            if is_real and not rej: TP += 1
            elif is_misclass and not rej: FP += 1
            elif is_misclass and rej: TN += 1
            elif is_real and rej: FN += 1
            per_phase.append((key, is_real, is_misclass, rej, reason))
        return TP, TN, FP, FN

    print(f"\n{'Guard candidate':50s} {'TP':>3s} {'TN':>3s} {'FP':>3s} {'FN':>3s} {'acc':>6s} {'comment':>30s}")
    print("-" * 130)
    for name, guard_fn in guard_candidates:
        TP, TN, FP, FN = evaluate_full(CORRECTED_GT, all_signals, h74_signals, h78, extended_aloft, guard_fn, H96_FULL)
        acc = (TP + TN) / max(1, TP + TN + FP + FN)
        comment = "PERFECT 17/4/0/0" if (TP == 17 and TN == 4 and FP == 0 and FN == 0) else \
                  ("loses real" if FN > 0 else "loses TN" if TN < 4 else "no effect")
        print(f"  {name:50s} {TP:>3d} {TN:>3d} {FP:>3d} {FN:>3d} {acc:>6.3f} {comment:>30s}")

    # Save summary
    summary = {
        "h100v2_methodology": "Combined guard signature analysis (FOUNTAIN_3+ features)",
        "fountain_phases": [
            {"key": list(key), "verdict": gt[1],
             "pct_ge1": a["pct_ge1"], "pct_ge3": a["pct_ge3"],
             "c40_pct_ge3": a["c40_pct_ge3"], "c60_pct_ge1": a["c60_pct_ge1"],
             "c80_pct_ge1": a["c80_pct_ge1"],
             "conf": sig["conf"], "spec_conc": sig["spec_conc"]}
            for key, gt, sig, a in f3_phases
        ],
    }
    with open(f"{H1_DATA}/h100v2_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {H1_DATA}/h100v2_summary.json")


if __name__ == "__main__":
    main()
