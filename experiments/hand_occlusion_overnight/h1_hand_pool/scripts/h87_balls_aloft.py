#!/usr/bin/env python3
"""
H87 — Ball-detection-based "balls aloft" signal as 5-ball discriminator.

Hypothesis: A real 5-ball juggling pattern has 3+ balls aloft at any
given moment. A static hold has 0-1 balls aloft. The "balls aloft"
metric (# YOLO sports ball detections > 100 px from both wrists)
should distinguish:

- f=267-298 JUGGLING_5BALL_STABLE: should have n_aloft >= 3
- f=733-766 STATIC_HOLD: should have n_aloft = 0
- f=375-410 JUGGLING_5BALL_CYCLING: should have n_aloft >= 3

This addresses the H82 v1 limitation where H40v2 hand-occupancy
saturates for 5-ball jugglers with stable LR=2.0.
"""
from __future__ import annotations

import csv
import json
import math
import glob
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
DETECTIONS = WORKTREE / "detections"
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# Filenames vary by stem
BALLS_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s_all-classes.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s_classes-32.csv",
}
POSE_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}

ALOFT_RADIUS = 100  # px from wrist


def load_balls(stem: str) -> dict:
    out = {}
    fpath = DETECTIONS / BALLS_CSV[stem]
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r["class_name"] == "sports ball":
                frame = int(r["frame"])
                if frame not in out:
                    out[frame] = []
                out[frame].append((float(r["center_x"]), float(r["center_y"])))
    return out


def load_wrists(stem: str) -> dict:
    out = {}
    fpath = DETECTIONS / POSE_CSV[stem]
    with open(fpath) as f:
        for r in csv.DictReader(f):
            frame = int(r["frame"])
            lw_conf = float(r["left_wrist_confidence"])
            rw_conf = float(r["right_wrist_confidence"])
            out[frame] = {
                "lw": (float(r["left_wrist_x"]), float(r["left_wrist_y"])) if lw_conf > 0.1 else None,
                "rw": (float(r["right_wrist_x"]), float(r["right_wrist_y"])) if rw_conf > 0.1 else None,
            }
    return out


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def compute_aloft_per_frame(balls, wrists, start, end):
    """Returns (n_aloft_per_frame, n_total_per_frame) for the phase range."""
    n_aloft = []
    n_total = []
    for f in range(start, end + 1):
        if f in balls and f in wrists:
            w = wrists[f]
            n = 0
            for b in balls[f]:
                aloft = True
                if w["lw"] is not None and dist(b, w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist(b, w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n += 1
            n_aloft.append(n)
            n_total.append(len(balls[f]))
    return n_aloft, n_total


# Ground truth
GT = {
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

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def main():
    print("=" * 80)
    print("H87 — Ball-detection-based 'balls aloft' signal")
    print("=" * 80)

    # Pre-load per stem
    balls_data = {stem: load_balls(stem) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    for stem in STEMS:
        n_balls = sum(len(v) for v in balls_data[stem].values())
        n_frames = len(balls_data[stem])
        print(f"  {stem}: {n_balls} ball detections across {n_frames} frames")

    # Per-phase analysis
    print(f"\nPer-phase balls-aloft analysis:")
    print(f"{'phase':<35} {'verdict':<22} {'n_total':>7} {'n_aloft_mean':>12} {'n_aloft_max':>11} {'pct_ge1':>7} {'pct_ge2':>7} {'pct_ge3':>7}")

    phase_signals = {}
    for key, gt in sorted(GT.items()):
        stem, start, end = key
        n_aloft, n_total = compute_aloft_per_frame(balls_data[stem], wrists_data[stem], start, end)
        if not n_aloft:
            print(f"  {stem[:5]} f={start}-{end} {gt[1]:<22}: NO_DATA")
            continue
        mean_aloft = sum(n_aloft) / len(n_aloft)
        max_aloft = max(n_aloft)
        mean_total = sum(n_total) / len(n_total)
        pct_ge1 = sum(1 for n in n_aloft if n >= 1) / len(n_aloft)
        pct_ge2 = sum(1 for n in n_aloft if n >= 2) / len(n_aloft)
        pct_ge3 = sum(1 for n in n_aloft if n >= 3) / len(n_aloft)
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {gt[1]:<22} {mean_total:>7.2f} {mean_aloft:>12.2f} {max_aloft:>11} {pct_ge1:>7.2f} {pct_ge2:>7.2f} {pct_ge3:>7.2f}")
        phase_signals[key] = {
            "verdict": gt[1],
            "mean_total": mean_total,
            "mean_aloft": mean_aloft,
            "max_aloft": max_aloft,
            "pct_ge1": pct_ge1,
            "pct_ge2": pct_ge2,
            "pct_ge3": pct_ge3,
        }

    # Try to discriminate static-hold from juggling
    # Hypothesis: a static hold has pct_ge3 < 0.10 (rarely 3+ balls aloft)
    # A 5-ball juggling pattern has pct_ge3 > 0.30 (frequently 3+ balls aloft)
    print(f"\n=== pct_ge3 distribution by verdict class ===")
    by_verdict = {}
    for key, sig in phase_signals.items():
        v = sig["verdict"]
        if v not in by_verdict:
            by_verdict[v] = []
        by_verdict[v].append(sig["pct_ge3"])
    for v, vals in sorted(by_verdict.items()):
        if vals:
            print(f"  {v:<22}: pct_ge3 mean={sum(vals)/len(vals):.2f} n={len(vals)} values={[round(x,2) for x in vals]}")

    # Test discrimination: H87 = reject if pct_ge3 < threshold
    # A real juggling phase should have pct_ge3 > threshold
    # A static hold should have pct_ge3 < threshold
    for thr in [0.05, 0.10, 0.20, 0.30, 0.50]:
        TP = TN = FP = FN = 0
        for key, sig in phase_signals.items():
            is_real = sig["verdict"] in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = sig["verdict"] in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                                              "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")
            rejected = sig["pct_ge3"] < thr
            keep = not rejected
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        print(f"  H87 (reject if pct_ge3 < {thr}): TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  acc={acc:.3f}")

    # Try also mean_aloft and max_aloft
    print(f"\n=== mean_aloft threshold ===")
    for thr in [0.5, 1.0, 1.5, 2.0]:
        TP = TN = FP = FN = 0
        for key, sig in phase_signals.items():
            is_real = sig["verdict"] in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = sig["verdict"] in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                                              "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")
            rejected = sig["mean_aloft"] < thr
            keep = not rejected
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        print(f"  H87 mean_aloft (reject if < {thr}): TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  acc={acc:.3f}")

    # Save signals
    out_signals = {}
    for key, sig in phase_signals.items():
        out_signals[f"{key[0]}_{key[1]}_{key[2]}"] = sig
    with open(f"{H1_DATA}/h87_balls_aloft.json", "w") as f:
        json.dump(out_signals, f, indent=2)
    print(f"\nWrote {H1_DATA}/h87_balls_aloft.json")


if __name__ == "__main__":
    main()
