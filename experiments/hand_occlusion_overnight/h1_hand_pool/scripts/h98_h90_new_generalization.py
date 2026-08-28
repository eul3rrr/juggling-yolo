#!/usr/bin/env python3
"""
H98 — Investigate whether H90 NEW generalizes to MIXED_3+ and CASCADE_3+.

Hypothesis
==========
H90 NEW (c40.pct_ge3<0.40 AND c40.max_aloft>=4) currently applies to
FOUNTAIN_3+ only. The question: would applying it to MIXED_3+ /
CASCADE_3+ cause false rejects of real juggling phases?

If the H93 corrected GT shows that NO real juggling MIXED_3+ or
CASCADE_3+ phase has c40g3<0.40 AND c40.max_aloft>=4, then H90 NEW
can be safely applied to all patterns.

Method
======
1. Compute c4 aloft features for ALL 21 H93 phases (not just FOUNTAIN_3+).
2. Report the H90 NEW firing rate per pattern (FOUNTAIN_3+,
   MIXED_3+, CASCADE_3+).
3. For any pattern where H90 NEW would fire on a real juggling
   phase, mark as a false-positive risk.
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


def compute_c4_aloft(balls_c4, wrists, start, end):
    n_aloft_4 = []
    for f in range(start, end + 1):
        if f not in wrists or f not in balls_c4:
            continue
        w = wrists[f]
        n = 0
        for (bx, by, _) in balls_c4[f]:
            aloft = True
            if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                aloft = False
            if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                aloft = False
            if aloft:
                n += 1
        n_aloft_4.append(n)
    if not n_aloft_4:
        return None
    n = len(n_aloft_4)
    return {
        "c40_pct_ge3": sum(1 for x in n_aloft_4 if x >= 3) / n,
        "c40_max_aloft": max(n_aloft_4),
        "n_frames": n,
    }


def main():
    print("=" * 80)
    print("H98 — Investigate H90 NEW generalization to MIXED_3+ and CASCADE_3+")
    print("=" * 80)

    balls_c4 = {stem: load_balls(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute c4 aloft for all 21 phases
    c4_signals = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_c4_aloft(balls_c4[stem], wrists_data[stem], start, end)
        if a:
            c4_signals[key] = a

    # Report per-pattern H90 NEW firing
    print("\n=== H90 NEW (c40g3<0.40 AND c40.max_aloft>=4) per-phase ===")
    print(f"{'phase':<35} {'pattern':<22} {'verdict':<22} {'c40g3':>6} {'c40mx':>5} {'H90NEW':>7}")
    firing = {"FOUNTAIN_3+": {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
              "MIXED_3+":   {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
              "CASCADE_3+": {"TP": 0, "TN": 0, "FP": 0, "FN": 0}}
    for key in sorted(CORRECTED_GT.keys()):
        stem, start, end = key
        sig = c4_signals.get(key)
        if sig is None:
            continue
        pattern, verdict = CORRECTED_GT[key]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        h90new = (sig["c40_pct_ge3"] < 0.40 and sig["c40_max_aloft"] >= 4)
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {pattern:<22} {verdict:<22} {sig['c40_pct_ge3']:>6.2f} {sig['c40_max_aloft']:>5} {str(h90new):>7}")
        if h90new:
            if is_real: outcome = "FN_risk"  # would be a false reject
            else: outcome = "TN"  # would correctly reject a misclass
        else:
            if is_real: outcome = "TP"  # correctly kept
            else: outcome = "FP"  # wrongly kept
        if pattern.startswith("MIXED"):
            pkey = "MIXED_3+"
        else:
            pkey = pattern
        # Map to TP/TN/FP/FN
        if h90new:
            if is_real: firing[pkey]["FN"] += 1
            else: firing[pkey]["TN"] += 1
        else:
            if is_real: firing[pkey]["TP"] += 1
            else: firing[pkey]["FP"] += 1

    print("\n=== H90 NEW firing rate per pattern (would-be rejections) ===")
    print(f"{'pattern':<15} {'TP':>4} {'TN':>4} {'FP':>4} {'FN':>4}  (FN=real juggling wrongly rejected, FP=misclass wrongly kept)")
    for p in ["FOUNTAIN_3+", "MIXED_3+", "CASCADE_3+"]:
        f = firing[p]
        print(f"{p:<15} {f['TP']:>4} {f['TN']:>4} {f['FP']:>4} {f['FN']:>4}")

    # Apply H90 NEW universally and check impact
    print("\n=== Universal H90 NEW (apply to all patterns) ===")
    for c40g3_thr in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        TP = TN = FP = FN = 0
        iTP = iTN = iFP = iFN = 0
        yTP = yTN = yFP = yFN = 0
        per_phase = []
        for key, (pattern, verdict) in sorted(CORRECTED_GT.items()):
            sig = c4_signals.get(key)
            if sig is None:
                continue
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            h90new = (sig["c40_pct_ge3"] < c40g3_thr and sig["c40_max_aloft"] >= 4)
            keep = not h90new
            if is_real and keep: outcome = "TP"
            elif is_misclass and not keep: outcome = "TN"
            elif is_misclass and keep: outcome = "FP"
            elif is_real and not keep: outcome = "FN"
            else: outcome = "?"
            if key[0].startswith("ident"):
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
            per_phase.append((key, outcome))

        p = TP / max(1, TP+FP)
        r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        mark = ""
        if TP == 17 and TN == 1 and FP == 3 and FN == 0:
            mark = " <-- c40g3=0.40 (no FN)"
        elif TP == 17 and TN == 1 and FP == 3 and FN == 1:
            mark = " <-- 1 FN (real juggling wrongly rejected)"
        elif TP == 16 and TN == 2 and FP == 3 and FN == 0:
            mark = " <-- 1 more TN but 1 more FN"
        print(f"  c40g3<{c40g3_thr}: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}{mark}")

    # Save summary
    summary = {
        "H98_methodology": "Investigate H90 NEW (c40g3<0.40 AND c40.max_aloft>=4) generalization to MIXED_3+ and CASCADE_3+",
        "per_pattern_firing": firing,
        "universal_h90_new_sensitivity": {
            f"c40g3<{t}": {"TP": 0} for t in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
        },
        "per_phase_c4": {
            f"{k[0]}_{k[1]}_{k[2]}": {
                "pattern": CORRECTED_GT[k][0],
                "verdict": CORRECTED_GT[k][1],
                "c40_pct_ge3": v["c40_pct_ge3"],
                "c40_max_aloft": v["c40_max_aloft"],
                "h90new_fires": v["c40_pct_ge3"] < 0.40 and v["c40_max_aloft"] >= 4,
            } for k, v in c4_signals.items()
        }
    }
    with open(f"{H1_DATA}/h98_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h98_summary.json")


if __name__ == "__main__":
    main()
