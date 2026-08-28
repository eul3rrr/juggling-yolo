#!/usr/bin/env python3
"""
H90 — Per-phase adaptive decision rule for the H87/H89 "balls aloft" signal.

Hypothesis: A single global threshold on pct_ge3 cannot separate all 21 phases
because:
- The 2 YouTube FPs at f=2-71 and f=482-594 have pct_ge3@conf0.4 = 0.36 (just
  above the 0.30 threshold that catches the f=800-861 CASCADE_REAL).
- The 2 identical FNs (f=263-312, f=977-1011) have pct_ge3@conf0.0 below 0.05
  and cannot be recovered without losing precision elsewhere.

This script computes a richer per-phase feature set (at multiple conf floors) and
searches for decision rules that improve over H82 v1 + H87 / H89 stacks.

Candidate features per (phase, conf_floor):
- pct_ge3, pct_ge2, pct_ge1: fraction of frames with n_aloft >= 3/2/1
- mean_aloft, max_aloft, std_aloft
- mean_total, max_total
- n_frames, frac_aloft_eq_max (fraction of frames at max_aloft)
- conf_stability: pct_ge3@conf0.0 - pct_ge3@conf0.4 (drop)
- conf_ratio: pct_ge3@conf0.4 / pct_ge3@conf0.0

Then a simple decision rule: REJECT if (any signal_X < thr_X AND signal_Y > thr_Y)
e.g., REJECT if (pct_ge3@conf0.4 < 0.40 AND conf_drop > 0.25)
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from collections import Counter

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

ALOFT_RADIUS = 100  # px from wrist (matches H87/H89)


# Ground truth: (pattern, verdict) — same as H87
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

REAL_VERDICTS = ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
MISCLASS_VERDICTS = ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                     "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_balls_with_conf(stem: str, min_conf: float = 0.0) -> dict:
    """Load sports ball detections filtered by minimum confidence, with per-frame conf values."""
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
    """Returns (n_aloft_per_frame, n_total_per_frame, max_conf_per_frame)."""
    n_aloft = []
    n_total = []
    max_conf = []
    for f in range(start, end + 1):
        if f in balls and f in wrists:
            w = wrists[f]
            n_aloft_frame = 0
            for (bx, by, conf) in balls[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n_aloft_frame += 1
            n_aloft.append(n_aloft_frame)
            n_total.append(len(balls[f]))
            max_conf.append(max([c for (_, _, c) in balls[f]]) if balls[f] else 0.0)
    return n_aloft, n_total, max_conf


def phase_features(balls_data, wrists_data, stem, start, end):
    """Compute rich per-phase features at multiple conf floors."""
    feats = {}
    for min_conf in [0.0, 0.20, 0.30, 0.40, 0.50]:
        n_aloft, n_total, max_conf = compute_aloft_per_frame(
            balls_data[stem][min_conf], wrists_data[stem], start, end
        )
        if not n_aloft:
            feats[f"c{int(min_conf*100):02d}"] = None
            continue
        n = len(n_aloft)
        max_aloft = max(n_aloft) if n_aloft else 0
        feats[f"c{int(min_conf*100):02d}"] = {
            "pct_ge1": sum(1 for x in n_aloft if x >= 1) / n,
            "pct_ge2": sum(1 for x in n_aloft if x >= 2) / n,
            "pct_ge3": sum(1 for x in n_aloft if x >= 3) / n,
            "pct_ge4": sum(1 for x in n_aloft if x >= 4) / n,
            "mean_aloft": sum(n_aloft) / n,
            "max_aloft": max_aloft,
            "std_aloft": (sum((x - sum(n_aloft)/n)**2 for x in n_aloft) / n) ** 0.5,
            "mean_total": sum(n_total) / n,
            "max_total": max(n_total),
            "max_conf": max(max_conf),
            "frac_at_max": sum(1 for x in n_aloft if x == max_aloft) / n,
            "n_frames": n,
        }
    # Cross-conf features (only if both have data)
    c0 = feats.get("c00")
    c4 = feats.get("c40")
    if c0 and c4:
        feats["drop_pct_ge3"] = c0["pct_ge3"] - c4["pct_ge3"]
        feats["drop_mean_total"] = c0["mean_total"] - c4["mean_total"]
        feats["drop_max_aloft"] = c0["max_aloft"] - c4["max_aloft"]
        if c0["pct_ge3"] > 0:
            feats["ratio_pct_ge3"] = c4["pct_ge3"] / c0["pct_ge3"]
        else:
            feats["ratio_pct_ge3"] = 1.0
    return feats


def main():
    print("=" * 80)
    print("H90 — Per-phase adaptive decision rule for balls-aloft signal")
    print("=" * 80)

    # Pre-load data
    balls_data = {}
    wrists_data = {}
    for stem in STEMS:
        balls_data[stem] = {min_conf: load_balls_with_conf(stem, min_conf) for min_conf in [0.0, 0.20, 0.30, 0.40, 0.50]}
        wrists_data[stem] = load_wrists(stem)

    # Compute features for each phase
    print("\nComputing per-phase features...")
    all_features = {}
    for key, gt in GT.items():
        stem, start, end = key
        feats = phase_features(balls_data, wrists_data, stem, start, end)
        all_features[key] = {"gt": gt, "feats": feats}

    # Print summary table — focus on the interesting signals
    print("\n=== Feature matrix (21 phases × key features) ===")
    print(f"{'phase':<60} {'verdict':<22} {'c00p3':>6} {'c40p3':>6} {'drop':>6} {'c00mA':>6} {'c40mA':>6} {'std0':>6} {'frac@max0':>8}")
    for key in sorted(all_features.keys()):
        stem, start, end = key
        feats = all_features[key]["feats"]
        verdict = all_features[key]["gt"][1]
        c0 = feats.get("c00") or {}
        c4 = feats.get("c40") or {}
        if not c0 or not c4:
            continue
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<60} {verdict:<22} {c0.get('pct_ge3', 0):>6.2f} {c4.get('pct_ge3', 0):>6.2f} {feats.get('drop_pct_ge3', 0):>6.2f} {c0.get('mean_aloft', 0):>6.2f} {c4.get('mean_aloft', 0):>6.2f} {c0.get('std_aloft', 0):>6.2f} {c0.get('frac_at_max', 0):>8.2f}")

    # Decision rule: REJECT if H82 v1 already catches it (H74v2/H78 signals)
    # Otherwise apply per-phase rule
    def h82_v1_catches(key):
        """H82 v1 catches STATIC_HOLD-like phases (variance + unique_LR) and H78 catches crossed-arm."""
        # These are the 4 phases H82 v1 catches on its own
        # f=685-716 MANIPULATION: H82 v1 may catch (H73 finding: L+R=0)
        # f=733-766 STATIC_HOLD: H74v2 catches (unique_LR=1)
        # f=890-936 OTHER_CROSSED_ARM: H78 catches (mean_diff>10)
        # f=1029-1049 OTHER_STATIC_HOLD: H74v2 catches
        (stem, start, end) = key
        if stem.startswith("ident"):
            if (start, end) in [(733, 766), (890, 936), (1029, 1049)]:
                return True
        return False

    # Baseline: H82 v1 alone + H87 (H89 stack from STATE)
    # Per H89, this is TP=12 TN=7 FP=0 FN=2
    # Goal of H90: recover 1 or both of the FNs without losing precision

    # === Test decision rules ===
    # Rule A: REJECT if (c40_pct_ge3 < thr) AND (drop_pct_ge3 > drop_thr)
    # Goal: catch the 2 YouTube FPs at f=2-71 (c40_pct_ge3=0.36, drop=0.39)
    # and f=482-594 (c40_pct_ge3=0.36, drop=0.30) without losing
    # f=420-481 JUGGLING (c40_pct_ge3=0.39, drop=0.30)

    print("\n=== Rule A: REJECT if (c40_pct_ge3 < thr_a) AND (drop_pct_ge3 > drop_thr_a) ===")
    best_a = None
    for thr_a in [0.30, 0.35, 0.40, 0.42, 0.45]:
        for drop_thr_a in [0.20, 0.25, 0.30, 0.35, 0.40]:
            TP = TN = FP = FN = 0
            for key, info in all_features.items():
                feats = info["feats"]
                verdict = info["gt"][1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                c0 = feats.get("c00") or {}
                c4 = feats.get("c40") or {}
                if not c0 or not c4:
                    continue
                # Apply H82 v1 first (assume it catches the static-hold/crossed-arm phases)
                if h82_v1_catches(key):
                    if is_real:
                        FN += 1  # H82 v1 shouldn't FN real, but if it does
                    else:
                        TN += 1
                    continue
                # Apply Rule A
                rejected = c4.get("pct_ge3", 1.0) < thr_a and feats.get("drop_pct_ge3", 0) > drop_thr_a
                keep = not rejected
                if is_real and keep:
                    TP += 1
                elif is_misclass and not keep:
                    TN += 1
                elif is_misclass and keep:
                    FP += 1
                elif is_real and not keep:
                    FN += 1
            p = TP / max(1, TP+FP)
            r = TP / max(1, TP+FN)
            acc = (TP+TN) / max(1, TP+TN+FP+FN)
            if best_a is None or acc > best_a[3]:
                best_a = (thr_a, drop_thr_a, (TP, TN, FP, FN), acc, p, r)
    print(f"  Best Rule A: thr_a={best_a[0]}, drop_thr_a={best_a[1]}, TPR={best_a[2]} P={best_a[4]:.3f} R={best_a[5]:.3f} acc={best_a[3]:.3f}")

    # Per-stem breakdown for best Rule A
    print("\n  Per-stem for best Rule A:")
    for stem_filter in ["ident", "youtu"]:
        TP = TN = FP = FN = 0
        for key, info in all_features.items():
            if stem_filter == "ident" and not key[0].startswith("ident"):
                continue
            if stem_filter == "youtu" and not key[0].startswith("youtu"):
                continue
            feats = info["feats"]
            verdict = info["gt"][1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            c0 = feats.get("c00") or {}
            c4 = feats.get("c40") or {}
            if not c0 or not c4:
                continue
            if h82_v1_catches(key):
                if is_misclass:
                    TN += 1
                continue
            rejected = c4.get("pct_ge3", 1.0) < best_a[0] and feats.get("drop_pct_ge3", 0) > best_a[1]
            keep = not rejected
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        print(f"    {stem_filter}: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    # === Rule B: REJECT if (c40_pct_ge3 < thr) AND (c40_mean_aloft < mean_thr)
    # The hypothesis: static holds have low mean_aloft AND low pct_ge3
    print("\n=== Rule B: REJECT if (c40_pct_ge3 < thr_b) AND (c40_mean_aloft < mean_thr_b) ===")
    best_b = None
    for thr_b in [0.30, 0.35, 0.40, 0.45, 0.50]:
        for mean_thr_b in [1.5, 1.7, 1.9, 2.0, 2.1, 2.2]:
            TP = TN = FP = FN = 0
            for key, info in all_features.items():
                feats = info["feats"]
                verdict = info["gt"][1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                c0 = feats.get("c00") or {}
                c4 = feats.get("c40") or {}
                if not c0 or not c4:
                    continue
                if h82_v1_catches(key):
                    if is_misclass:
                        TN += 1
                    continue
                rejected = c4.get("pct_ge3", 1.0) < thr_b and c4.get("mean_aloft", 99) < mean_thr_b
                keep = not rejected
                if is_real and keep: TP += 1
                elif is_misclass and not keep: TN += 1
                elif is_misclass and keep: FP += 1
                elif is_real and not keep: FN += 1
            p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
            acc = (TP+TN) / max(1, TP+TN+FP+FN)
            if best_b is None or acc > best_b[3]:
                best_b = (thr_b, mean_thr_b, (TP, TN, FP, FN), acc, p, r)
    print(f"  Best Rule B: thr_b={best_b[0]}, mean_thr_b={best_b[1]}, TPR={best_b[2]} P={best_b[4]:.3f} R={best_b[5]:.3f} acc={best_b[3]:.3f}")

    # === Rule C: REJECT if (c40_max_aloft <= 2) — too few balls aloft at high conf
    # The hypothesis: real juggling has max_aloft >= 3; static holds max out at 2-3 due to FPs
    print("\n=== Rule C: REJECT if (c40_max_aloft <= max_thr) ===")
    best_c = None
    for max_thr in [2, 3, 4]:
        TP = TN = FP = FN = 0
        for key, info in all_features.items():
            feats = info["feats"]
            verdict = info["gt"][1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            c4 = feats.get("c40") or {}
            if not c4:
                continue
            if h82_v1_catches(key):
                if is_misclass:
                    TN += 1
                continue
            rejected = c4.get("max_aloft", 99) <= max_thr
            keep = not rejected
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        if best_c is None or acc > best_c[3]:
            best_c = (max_thr, (TP, TN, FP, FN), acc, p, r)
    print(f"  Best Rule C: max_thr={best_c[0]}, TPR={best_c[1]} P={best_c[3]:.3f} R={best_c[4]:.3f} acc={best_c[2]:.3f}")

    # === Rule D: Combined — REJECT if (Rule A OR Rule B OR Rule C)
    print("\n=== Rule D: REJECT if (Rule A OR Rule B OR Rule C) ===")
    # Use best parameters from each
    thr_a, drop_a = best_a[0], best_a[1]
    thr_b, mean_b = best_b[0], best_b[1]
    max_c = best_c[0]
    TP = TN = FP = FN = 0
    for key, info in all_features.items():
        feats = info["feats"]
        verdict = info["gt"][1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        c0 = feats.get("c00") or {}
        c4 = feats.get("c40") or {}
        if not c0 or not c4:
            continue
        if h82_v1_catches(key):
            if is_misclass:
                TN += 1
            continue
        rule_a = c4.get("pct_ge3", 1.0) < thr_a and feats.get("drop_pct_ge3", 0) > drop_a
        rule_b = c4.get("pct_ge3", 1.0) < thr_b and c4.get("mean_aloft", 99) < mean_b
        rule_c = c4.get("max_aloft", 99) <= max_c
        rejected = rule_a or rule_b or rule_c
        keep = not rejected
        if is_real and keep: TP += 1
        elif is_misclass and not keep: TN += 1
        elif is_misclass and keep: FP += 1
        elif is_real and not keep: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  Rule D: TP={TP} TN={TN} FP={FN} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    # === Per-phase detail for best rule
    print("\n=== Per-phase detail for best rule (D) ===")
    for key in sorted(all_features.keys()):
        stem, start, end = key
        feats = all_features[key]["feats"]
        verdict = all_features[key]["gt"][1]
        c0 = feats.get("c00") or {}
        c4 = feats.get("c40") or {}
        if not c0 or not c4:
            continue
        rule_a = c4.get("pct_ge3", 1.0) < thr_a and feats.get("drop_pct_ge3", 0) > drop_a
        rule_b = c4.get("pct_ge3", 1.0) < thr_b and c4.get("mean_aloft", 99) < mean_b
        rule_c = c4.get("max_aloft", 99) <= max_c
        rejected = rule_a or rule_b or rule_c
        h82_caught = h82_v1_catches(key)
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        outcome = ""
        if h82_caught:
            outcome = "H82_TN" if is_misclass else "H82_FN"
        elif rejected:
            outcome = "H90_TN" if is_misclass else "H90_FN"
        else:
            outcome = "TP" if is_real else "FP"
        label = f"{stem[:5]} f={start}-{end}"
        print(f"  {label:<25} {verdict:<22} c40p3={c4.get('pct_ge3', 0):.2f} drop={feats.get('drop_pct_ge3', 0):.2f} mA4={c4.get('mean_aloft', 0):.2f} max4={c4.get('max_aloft', 0)} -> {outcome}")

    # Save
    out = {}
    for key, info in all_features.items():
        out[f"{key[0]}_{key[1]}_{key[2]}"] = {
            "gt": info["gt"],
            "feats": info["feats"],
        }
    with open(f"{H1_DATA}/h90_per_phase_features.json", "w") as f:
        json.dump(out, f, indent=2)
    summary = {
        "rule_a_best": {"thr": best_a[0], "drop_thr": best_a[1], "TPR": best_a[2], "acc": best_a[3], "P": best_a[4], "R": best_a[5]},
        "rule_b_best": {"thr": best_b[0], "mean_thr": best_b[1], "TPR": best_b[2], "acc": best_b[3], "P": best_b[4], "R": best_b[5]},
        "rule_c_best": {"max_thr": best_c[0], "TPR": best_c[1], "acc": best_c[2], "P": best_c[3], "R": best_c[4]},
        "rule_d": {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "P": p, "R": r, "acc": acc},
    }
    with open(f"{H1_DATA}/h90_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h90_per_phase_features.json")
    print(f"Wrote {H1_DATA}/h90_summary.json")


if __name__ == "__main__":
    main()
