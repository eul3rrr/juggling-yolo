#!/usr/bin/env python3
"""
H89 — H87 with YOLO confidence thresholding.

Hypothesis: The H87 hypothesis (balls aloft) failed on YouTube because
YOLO confuses background features with sports balls (H4/H66 finding).
These false-positive detections likely have LOWER YOLO confidence than
true ball detections. A confidence floor should filter most FPs while
preserving true juggling detections.

Test: re-run the H87 "balls aloft" metric with confidence floor
{0.20, 0.30, 0.40, 0.50, 0.60, 0.70} and see which threshold recovers
YouTube juggling discrimination without losing the identical catches.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
DETECTIONS = WORKTREE / "detections"
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

BALLS_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s_all-classes.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s_classes-32.csv",
}
POSE_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}

ALOFT_RADIUS = 100  # px from wrist (same as H87)


def load_balls_with_conf(stem: str, min_conf: float = 0.0) -> dict:
    """Load sports ball detections filtered by minimum confidence."""
    out = {}
    fpath = DETECTIONS / BALLS_CSV[stem]
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r["class_name"] == "sports ball":
                conf = float(r["confidence"])
                if conf < min_conf:
                    continue
                frame = int(r["frame"])
                if frame not in out:
                    out[frame] = []
                out[frame].append((float(r["center_x"]), float(r["center_y"]), conf))
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
            n_aloft_frame = 0
            for (bx, by, _conf) in balls[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n_aloft_frame += 1
            n_aloft.append(n_aloft_frame)
            n_total.append(len(balls[f]))
    return n_aloft, n_total


# Ground truth (21 phases from H87)
GT = {
    ("identical_balls_trick_000_018", 263, 312): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 411, 450): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 549, 578): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 631, 669): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 685, 716): ("CASCADE_3+", "MANIPULATION"),
    ("identical_balls_trick_000_018", 733, 766): ("CASCADE_3+", "STATIC_HOLD"),
    ("identical_balls_trick_000_018", 890, 936): ("FOUNTAIN_3+", "OTHER_CROSSED_ARM"),
    ("identical_balls_trick_000_018", 977, 1011): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 1029, 1049): ("FOUNTAIN_3+", "OTHER_STATIC_HOLD"),
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


def analyze(min_conf: float) -> dict:
    """Run the H87-style analysis with a YOLO confidence floor."""
    balls_data = {stem: load_balls_with_conf(stem, min_conf) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    phase_signals = {}
    for key, gt in GT.items():
        stem, start, end = key
        n_aloft, n_total = compute_aloft_per_frame(balls_data[stem], wrists_data[stem], start, end)
        if not n_aloft:
            phase_signals[key] = {"verdict": gt[1], "pct_ge3": None, "n_frames": 0}
            continue
        pct_ge3 = sum(1 for n in n_aloft if n >= 3) / len(n_aloft)
        mean_total = sum(n_total) / len(n_total)
        max_aloft = max(n_aloft)
        mean_aloft = sum(n_aloft) / len(n_aloft)
        phase_signals[key] = {
            "verdict": gt[1],
            "pattern": gt[0],
            "pct_ge3": pct_ge3,
            "mean_total": mean_total,
            "max_aloft": max_aloft,
            "mean_aloft": mean_aloft,
            "n_frames": len(n_aloft),
        }
    return phase_signals, balls_data


def main():
    print("=" * 80)
    print("H89 — H87 with YOLO confidence thresholding")
    print("=" * 80)

    # Confidence floor sweep
    confidence_floors = [0.0, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]

    all_results = {}
    for min_conf in confidence_floors:
        print(f"\n=== Confidence floor: {min_conf:.2f} ===")
        phase_signals, balls_data = analyze(min_conf)

        # Per-phase table
        print(f"\n{'phase':<35} {'verdict':<22} {'pct_ge3':>7} {'mean_aloft':>10} {'max_aloft':>9}")
        for key, sig in sorted(phase_signals.items()):
            stem, start, end = key
            label = f"{stem[:5]} f={start}-{end}"
            pct = f"{sig['pct_ge3']:.2f}" if sig['pct_ge3'] is not None else "N/A"
            ma = f"{sig['mean_aloft']:.2f}" if sig.get('mean_aloft') is not None else "N/A"
            mx = f"{sig['max_aloft']}" if sig.get('max_aloft') is not None else "N/A"
            print(f"{label:<35} {sig['verdict']:<22} {pct:>7} {ma:>10} {mx:>9}")

        # Discrimination: H87-style reject if pct_ge3 < threshold
        print(f"\n  H87 (reject if pct_ge3 < thr) per conf-floor {min_conf:.2f}:")
        for thr in [0.05, 0.10, 0.20, 0.30, 0.50]:
            TP = TN = FP = FN = 0
            for key, sig in phase_signals.items():
                if sig["pct_ge3"] is None:
                    continue
                is_real = sig["verdict"] in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
                is_misclass = sig["verdict"] in (
                    "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                    "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
                )
                rejected = sig["pct_ge3"] < thr
                keep = not rejected
                if is_real and keep:
                    TP += 1
                elif is_misclass and not keep:
                    TN += 1
                elif is_misclass and keep:
                    FP += 1
                elif is_real and not keep:
                    FN += 1
            p = TP / max(1, TP + FP)
            r = TP / max(1, TP + FN)
            acc = (TP + TN) / max(1, TP + TN + FP + FN)
            print(f"    thr={thr}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  acc={acc:.3f}")

        # Per-stem discrimination
        for stem_filter in ["all", "ident", "youtu"]:
            print(f"\n  Per-stem {stem_filter}:")
            for thr in [0.05, 0.10, 0.20, 0.30, 0.50]:
                TP = TN = FP = FN = 0
                for key, sig in phase_signals.items():
                    if sig["pct_ge3"] is None:
                        continue
                    if stem_filter == "ident" and not key[0].startswith("ident"):
                        continue
                    if stem_filter == "youtu" and not key[0].startswith("youtu"):
                        continue
                    is_real = sig["verdict"] in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
                    is_misclass = sig["verdict"] in (
                        "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                        "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
                    )
                    rejected = sig["pct_ge3"] < thr
                    keep = not rejected
                    if is_real and keep:
                        TP += 1
                    elif is_misclass and not keep:
                        TN += 1
                    elif is_misclass and keep:
                        FP += 1
                    elif is_real and not keep:
                        FN += 1
                p = TP / max(1, TP + FP)
                r = TP / max(1, TP + FN)
                acc = (TP + TN) / max(1, TP + TN + FP + FN)
                print(f"    thr={thr}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  acc={acc:.3f}")

        all_results[min_conf] = phase_signals

    # Save
    out = {}
    for min_conf, sigs in all_results.items():
        out_key = f"conf{min_conf:.2f}"
        out[out_key] = {}
        for key, sig in sigs.items():
            out[out_key][f"{key[0]}_{key[1]}_{key[2]}"] = sig
    with open(f"{H1_DATA}/h89_yolo_conf_filter.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {H1_DATA}/h89_yolo_conf_filter.json")


if __name__ == "__main__":
    main()
