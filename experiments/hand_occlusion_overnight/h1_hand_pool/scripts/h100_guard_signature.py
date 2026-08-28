#!/usr/bin/env python3
"""
H100 — pct_ge1 guard signature analysis.

H99 found that guard_pct_ge1_thr=0.92 is the WEAKEST LINK in the H96
v2 stack. Raising it above 0.92 immediately loses 2 real juggling
phases (f=1029-1049 and f=800-861) to FN because the H43/H69 logic
rejects them based on low conf / low spec_conc.

This experiment characterizes the signature of the 2 protected phases
to see if there's a more robust signal that can replace the brittle
hard cap at 0.92.

Hypothesis
==========
The 2 protected phases have HIGH pct_ge1 (c0 aloft) but LOW c40_pct_ge3
(conf>=0.4 aloft) — the signature of "real juggling with low detector
confidence". A more discriminating guard could be:
  "Real juggling is characterized by ALMOST ALWAYS having at least
  1 ball aloft (low-confidence OK), with the high-confidence
  detections being concentrated near a small number of frames
  (the throws)."

Method
======
1. Compute pct_ge1, c40_pct_ge3, c40_max_aloft, and additional
   aloft features (n_frames_with_c40_det, fraction of c4 frames
   where c4 fires at all, etc.) for all 21 H93 phases.
2. Compare the 2 protected phases (f=1029-1049, f=800-861) to:
   - The 4 TN phases (catches, real misclassifications)
   - The 15 other TP phases (real juggling, no rejection)
3. Find a feature combination that separates "real juggling"
   from "real misclassification" without the brittle 0.92 cap.

This is NOT a stack replacement — it's a guard-replacement
investigation. The H96 v2 stack rules are unchanged.
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

# H93 CORRECTED ground truth
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
    """Extended aloft features for guard signature analysis.

    Computes aloft counts at 4 confidence levels (0.0, 0.4, 0.6, 0.8)
    plus several aggregate features that might separate real juggling
    from real misclassifications without the brittle 0.92 cap.
    """
    n_aloft = {0: [], 4: [], 6: [], 8: []}
    frames_with_c0, frames_with_c4 = [], []
    n_aloft_0_dist = []  # full distribution
    for f in range(start, end + 1):
        if f not in wrists:
            continue
        w = wrists[f]
        counts = {}
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
            counts[conf_level] = n
        if f in balls_c0:
            n_aloft[0].append(counts[0])
            n_aloft_0_dist.append(counts[0])
        if f in balls_c4:
            n_aloft[4].append(counts[4])
        if f in balls_c6:
            n_aloft[6].append(counts[6])
        if f in balls_c8:
            n_aloft[8].append(counts[8])
        if f in balls_c0:
            frames_with_c0.append(f)
        if f in balls_c4:
            frames_with_c4.append(f)
    if not n_aloft[0]:
        return None
    n0 = len(n_aloft[0])
    n4 = max(1, len(n_aloft[4]))
    pct_ge1 = sum(1 for x in n_aloft[0] if x >= 1) / n0
    pct_ge2 = sum(1 for x in n_aloft[0] if x >= 2) / n0
    pct_ge3 = sum(1 for x in n_aloft[0] if x >= 3) / n0
    c40_pct_ge3 = sum(1 for x in n_aloft[4] if x >= 3) / n4
    c60_pct_ge1 = sum(1 for x in n_aloft[6] if x >= 1) / max(1, len(n_aloft[6]))
    c60_pct_ge3 = sum(1 for x in n_aloft[6] if x >= 3) / max(1, len(n_aloft[6]))
    c80_pct_ge1 = sum(1 for x in n_aloft[8] if x >= 1) / max(1, len(n_aloft[8]))
    # New features for guard-replacement investigation
    c0_to_c4_ratio = c40_pct_ge3 / max(0.001, pct_ge3)  # c4 / c0 pct_ge3
    c0_to_c6_ratio = c60_pct_ge3 / max(0.001, pct_ge3)  # c6 / c0 pct_ge3
    # "Stuck" detector signature: high c0_pct_ge1 with c4 max_aloft < c0 max_aloft
    c0_max = max(n_aloft[0]) if n_aloft[0] else 0
    c4_max = max(n_aloft[4]) if n_aloft[4] else 0
    return {
        # Basic features
        "pct_ge1": pct_ge1,
        "pct_ge2": pct_ge2,
        "pct_ge3": pct_ge3,
        "max_aloft": c0_max,
        "c40_pct_ge3": c40_pct_ge3,
        "c40_max_aloft": c4_max,
        "c60_pct_ge1": c60_pct_ge1,
        "c60_pct_ge3": c60_pct_ge3,
        "c80_pct_ge1": c80_pct_ge1,
        # Guard-replacement candidates
        "c0_to_c4_pct_ge3_ratio": c0_to_c4_ratio,
        "c0_to_c6_pct_ge3_ratio": c0_to_c6_ratio,
        "c0_minus_c4_max_aloft": c0_max - c4_max,
        "n_frames_with_c0": n0,
        "n_frames_with_c4": len(n_aloft[4]),
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
    print("H100 — pct_ge1 guard signature analysis")
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

    # Per-phase feature report
    print("\n" + "=" * 80)
    print("Per-phase features (sorted by H96 v2 outcome):")
    print("=" * 80)
    rows = []
    for key, gt in sorted(CORRECTED_GT.items()):
        sig = all_signals.get(key)
        a = extended_aloft.get(key)
        if sig is None or a is None:
            continue
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        is_protected = key[1] in (1029, 800) and key[2] in (1049, 861)
        rows.append({
            "key": key, "gt": gt, "sig": sig, "a": a,
            "is_real": is_real, "is_misclass": is_misclass,
            "is_protected": is_protected,
        })
    # Group by verdict
    print(f"\n{'Phase':30s} {'Pattern':18s} {'verdict':25s} "
          f"{'pct_ge1':>8s} {'pct_ge3':>8s} {'c40g3':>8s} "
          f"{'c40ma':>6s} {'c60g1':>8s} {'c0/c4':>8s} {'c0-c4ma':>8s}")
    print("-" * 130)
    print("REAL JUGGLING PHASES (TP / no rejection):")
    for r in rows:
        if r["is_real"] and not r["is_protected"]:
            a = r["a"]
            print(f"  {r['key'][0][:25]:25s} f={r['key'][1]}-{r['key'][2]:4d} "
                  f"{r['gt'][0]:18s} {r['gt'][1]:25s} "
                  f"{a['pct_ge1']:>8.3f} {a['pct_ge3']:>8.3f} {a['c40_pct_ge3']:>8.3f} "
                  f"{a['c40_max_aloft']:>6d} {a['c60_pct_ge1']:>8.3f} "
                  f"{a['c0_to_c4_pct_ge3_ratio']:>8.3f} {a['c0_minus_c4_max_aloft']:>8d}")
    print("\nREAL JUGGLING PHASES PROTECTED BY pct_ge1 GUARD (would FN without it):")
    for r in rows:
        if r["is_protected"]:
            a = r["a"]
            print(f"  {r['key'][0][:25]:25s} f={r['key'][1]}-{r['key'][2]:4d} "
                  f"{r['gt'][0]:18s} {r['gt'][1]:25s} "
                  f"{a['pct_ge1']:>8.3f} {a['pct_ge3']:>8.3f} {a['c40_pct_ge3']:>8.3f} "
                  f"{a['c40_max_aloft']:>6d} {a['c60_pct_ge1']:>8.3f} "
                  f"{a['c0_to_c4_pct_ge3_ratio']:>8.3f} {a['c0_minus_c4_max_aloft']:>8d}")
    print("\nMISCLASS PHASES (TN, correctly rejected):")
    for r in rows:
        if r["is_misclass"]:
            a = r["a"]
            print(f"  {r['key'][0][:25]:25s} f={r['key'][1]}-{r['key'][2]:4d} "
                  f"{r['gt'][0]:18s} {r['gt'][1]:25s} "
                  f"{a['pct_ge1']:>8.3f} {a['pct_ge3']:>8.3f} {a['c40_pct_ge3']:>8.3f} "
                  f"{a['c40_max_aloft']:>6d} {a['c60_pct_ge1']:>8.3f} "
                  f"{a['c0_to_c4_pct_ge3_ratio']:>8.3f} {a['c0_minus_c4_max_aloft']:>8d}")

    # Find discriminating features between REAL (protected) and MISCLASS
    print("\n" + "=" * 80)
    print("Discriminating features (REAL protected vs MISCLASS):")
    print("=" * 80)
    real_protected = [r for r in rows if r["is_protected"]]
    misclass = [r for r in rows if r["is_misclass"]]
    print(f"\n{'Feature':25s} {'REAL_protected':>16s} {'MISCLASS':>10s} {'separable?':>14s}")
    for feat in ["pct_ge1", "pct_ge2", "pct_ge3", "c40_pct_ge3",
                 "c60_pct_ge1", "c60_pct_ge3", "c80_pct_ge1",
                 "c0_to_c4_pct_ge3_ratio", "c0_to_c6_pct_ge3_ratio",
                 "c0_minus_c4_max_aloft", "c40_max_aloft", "max_aloft"]:
        rp_vals = [r["a"][feat] for r in real_protected]
        mc_vals = [r["a"][feat] for r in misclass]
        rp_str = ", ".join(f"{v:.3f}" for v in rp_vals) if rp_vals else "-"
        mc_str = ", ".join(f"{v:.3f}" for v in mc_vals) if mc_vals else "-"
        # Check if any value separates (max of min-class < min of max-class)
        try:
            if all(isinstance(v, (int, float)) for v in rp_vals + mc_vals):
                max_min = max(min(rp_vals), min(mc_vals))
                min_max = min(max(rp_vals), max(mc_vals))
                separable = "YES" if max_min < min_max else "overlap"
            else:
                separable = "n/a"
        except (TypeError, ValueError):
            separable = "n/a"
        print(f"  {feat:25s} {rp_str:>16s} {mc_str:>10s} {separable:>14s}")

    # === Test guard-replacement candidates on the H93 sample ===
    print("\n" + "=" * 80)
    print("Guard-replacement candidates (H43+H69 alternatives):")
    print("=" * 80)

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

    def evaluate_with_guard(gt_dict, signals, aloft_signals, guard_fn, thr):
        """Evaluate with a custom guard function."""
        TP = TN = FP = FN = 0
        for key, gt in sorted(gt_dict.items()):
            sig = signals.get(key)
            a = aloft_signals.get(key)
            if sig is None or a is None:
                continue
            if sig["pattern"] != "FOUNTAIN_3+":
                continue  # guard only matters for FOUNTAIN_3+
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            # H43 + H69 with the custom guard
            guard = guard_fn(a)
            would_h43 = sig["conf"] < thr["h43_conf_thr"] and guard
            would_h69 = sig["spec_conc"] < thr["h69_spec_conc_thr"] and guard
            rej = would_h43 or would_h69
            if is_real and not rej: TP += 1
            elif is_misclass and rej: TN += 1
            elif is_misclass and not rej: FP += 1
            elif is_real and rej: FN += 1
        return TP, TN, FP, FN

    # Test guard candidates
    guard_candidates = [
        ("default pct_ge1<0.92", lambda a: a["pct_ge1"] < 0.92),
        ("c60_pct_ge1<0.50", lambda a: a["c60_pct_ge1"] < 0.50),
        ("c60_pct_ge1<0.30", lambda a: a["c60_pct_ge1"] < 0.30),
        ("c60_pct_ge1<0.20", lambda a: a["c60_pct_ge1"] < 0.20),
        ("c0/c4 ratio>0.20", lambda a: a["c0_to_c4_pct_ge3_ratio"] > 0.20),
        ("c0/c4 ratio>0.30", lambda a: a["c0_to_c4_pct_ge3_ratio"] > 0.30),
        ("c0/c4 ratio>0.50", lambda a: a["c0_to_c4_pct_ge3_ratio"] > 0.50),
        ("c80_pct_ge1<0.30", lambda a: a["c80_pct_ge1"] < 0.30),
        ("c80_pct_ge1<0.20", lambda a: a["c80_pct_ge1"] < 0.20),
        ("c80_pct_ge1<0.10", lambda a: a["c80_pct_ge1"] < 0.10),
        ("max_aloft>=2 (c0 only)", lambda a: a["max_aloft"] >= 2),
        ("max_aloft>=3 (c0 only)", lambda a: a["max_aloft"] >= 3),
    ]
    print(f"\n{'Guard candidate':40s} {'TP':>4s} {'TN':>4s} {'FP':>4s} {'FN':>4s} {'comment':>30s}")
    print("-" * 100)
    for name, guard_fn in guard_candidates:
        TP, TN, FP, FN = evaluate_with_guard(CORRECTED_GT, all_signals, extended_aloft, guard_fn, H96_DEFAULTS)
        comment = "PERFECT 17/4/0/0" if (TP == 17 and TN == 4 and FP == 0 and FN == 0) else \
                  ("loses real" if FN > 0 else "loses TN" if TN < 4 else "no effect")
        print(f"  {name:40s} {TP:>4d} {TN:>4d} {FP:>4d} {FN:>4d} {comment:>30s}")

    # === Save summary JSON ===
    summary = {
        "h100_methodology": "pct_ge1 guard signature analysis (extended aloft features)",
        "real_protected": [
            {"key": list(r["key"]), "verdict": r["gt"][1],
             **{k: r["a"][k] for k in ["pct_ge1", "pct_ge2", "pct_ge3", "c40_pct_ge3",
                                          "c60_pct_ge1", "c60_pct_ge3", "c80_pct_ge1",
                                          "c0_to_c4_pct_ge3_ratio", "c0_to_c6_pct_ge3_ratio",
                                          "c0_minus_c4_max_aloft", "c40_max_aloft", "max_aloft"]}}
            for r in rows if r["is_protected"]
        ],
        "misclass": [
            {"key": list(r["key"]), "verdict": r["gt"][1],
             **{k: r["a"][k] for k in ["pct_ge1", "pct_ge2", "pct_ge3", "c40_pct_ge3",
                                          "c60_pct_ge1", "c60_pct_ge3", "c80_pct_ge1",
                                          "c0_to_c4_pct_ge3_ratio", "c0_to_c6_pct_ge3_ratio",
                                          "c0_minus_c4_max_aloft", "c40_max_aloft", "max_aloft"]}}
            for r in rows if r["is_misclass"]
        ],
    }
    with open(f"{H1_DATA}/h100_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {H1_DATA}/h100_summary.json")


if __name__ == "__main__":
    main()
