#!/usr/bin/env python3
"""
H90 v3 — Per-phase rule using max_aloft@conf0.4 == 4 as a STATIC_HOLD signal.

Key insight from H90 v2: f=482-594 STATIC_HOLD is the ONLY YouTube phase where
c40_max_aloft = 4. Real juggling has c40_max_aloft = 3 (after conf filter removes
some FPs, the count drops to 3).

Hypothesis: REJECT if (c40_pct_ge3 < 0.40 AND c40_max_aloft >= 4)

Plus a complementary rule for f=2-71 STATIC_DEMO: REJECT if (c40_pct_ge3 < 0.40
AND drop_max == 0) — meaning the max_aloft didn't decrease after conf filter.

Let me test.
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# Re-load per-frame data to compute more features
import csv
import math

DETECTIONS = WORKTREE / "detections"
BALLS_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s_all-classes.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s_classes-32.csv",
}
POSE_CSV = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018_yolo26s-pose.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_yolo26s-pose.csv",
}
ALOFT_RADIUS = 100

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


def load_balls_with_conf(stem: str, min_conf: float = 0.0) -> dict:
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


def compute_per_frame(balls, wrists, start, end):
    """For each frame, return n_aloft, max_conf_aloft, n_total."""
    n_aloft = []
    max_conf_aloft = []
    n_total = []
    for f in range(start, end + 1):
        if f in balls and f in wrists:
            w = wrists[f]
            n = 0
            max_c = 0.0
            for (bx, by, conf) in balls[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n += 1
                    if conf > max_c:
                        max_c = conf
            n_aloft.append(n)
            max_conf_aloft.append(max_c)
            n_total.append(len(balls[f]))
    return n_aloft, max_conf_aloft, n_total


STEMS = list(BALLS_CSV.keys())


def h82_v1_catches(key):
    """H82 v1 + H87 stack catches these 4 identical misclassifications:
    - f=685-716: H87
    - f=733-766: H74v2
    - f=890-936: H78
    - f=1029-1049: H74v2
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    return False


def main():
    print("=" * 80)
    print("H90 v3 — per-phase rule using c40_max_aloft and conf distribution")
    print("=" * 80)

    balls_data = {stem: {c: load_balls_with_conf(stem, c) for c in [0.0, 0.40]} for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute per-frame signals
    print("\nPer-frame signals (n_aloft and max_conf_aloft at c=0.0 and c=0.4):")
    print(f"{'phase':<35} {'verdict':<22} {'mA0':>4} {'mA4':>4} {'mConfA0':>8} {'mConfA4':>8} {'drop_max':>8} {'drop_mA':>7}")
    per_phase = {}
    for key, gt in GT.items():
        stem, start, end = key
        n_aloft_0, max_conf_0, n_total_0 = compute_per_frame(balls_data[stem][0.0], wrists_data[stem], start, end)
        n_aloft_4, max_conf_4, n_total_4 = compute_per_frame(balls_data[stem][0.40], wrists_data[stem], start, end)
        if not n_aloft_0 or not n_aloft_4:
            continue
        mA0 = sum(n_aloft_0) / len(n_aloft_0)
        mA4 = sum(n_aloft_4) / len(n_aloft_4)
        # mean of max_conf_aloft (only when there are aloft balls)
        valid_0 = [c for c in max_conf_0 if c > 0]
        valid_4 = [c for c in max_conf_4 if c > 0]
        mConfA0 = sum(valid_0) / len(valid_0) if valid_0 else 0
        mConfA4 = sum(valid_4) / len(valid_4) if valid_4 else 0
        drop_max = max(n_aloft_0) - max(n_aloft_4)
        drop_mA = mA0 - mA4
        per_phase[key] = {
            "verdict": gt[1],
            "mA0": mA0,
            "mA4": mA4,
            "max_0": max(n_aloft_0),
            "max_4": max(n_aloft_4),
            "mConfA0": mConfA0,
            "mConfA4": mConfA4,
            "drop_max": drop_max,
            "drop_mA": drop_mA,
        }
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {gt[1]:<22} {mA0:>4.2f} {mA4:>4.2f} {mConfA0:>8.3f} {mConfA4:>8.3f} {drop_max:>8} {drop_mA:>7.2f}")

    # Now try several rules
    print("\n=== Rule F1: REJECT if c40_max_aloft == 4 ===")
    TP=TN=FP=FN=0
    for key, info in per_phase.items():
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            continue
        rejected = info['max_4'] == 4
        if is_real and not rejected: TP += 1
        elif is_misclass and rejected: TN += 1
        elif is_misclass and not rejected: FP += 1
        elif is_real and rejected: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    print("\n=== Rule F2: REJECT if c40_max_aloft == 4 AND c40_pct_ge3 < 0.40 ===")
    TP=TN=FP=FN=0
    for key, info in per_phase.items():
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            continue
        # c40 pct_ge3 needed from h90
        with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
            h90d = json.load(f)
        key_str = f"{key[0]}_{key[1]}_{key[2]}"
        h90feats = h90d.get(key_str, {}).get('feats', {})
        c4 = h90feats.get('c40', {}) or {}
        pct_ge3 = c4.get('pct_ge3', 1.0)
        rejected = info['max_4'] == 4 and pct_ge3 < 0.40
        if is_real and not rejected: TP += 1
        elif is_misclass and rejected: TN += 1
        elif is_misclass and not rejected: FP += 1
        elif is_real and rejected: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    print("\n=== Rule F3: REJECT if c40_max_aloft == 4 OR (c40_pct_ge3 < 0.30) ===")
    TP=TN=FP=FN=0
    for key, info in per_phase.items():
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            continue
        with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
            h90d = json.load(f)
        key_str = f"{key[0]}_{key[1]}_{key[2]}"
        h90feats = h90d.get(key_str, {}).get('feats', {})
        c4 = h90feats.get('c40', {}) or {}
        pct_ge3 = c4.get('pct_ge3', 1.0)
        rejected = info['max_4'] == 4 or pct_ge3 < 0.30
        if is_real and not rejected: TP += 1
        elif is_misclass and rejected: TN += 1
        elif is_misclass and not rejected: FP += 1
        elif is_real and rejected: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    # Try a stacked rule: F1 OR (F2 with conf=0.50)
    print("\n=== Rule F4: REJECT if c40_max_aloft == 4 OR (c50_pct_ge3 < 0.40) ===")
    balls_data_50 = {stem: load_balls_with_conf(stem, 0.50) for stem in STEMS}
    TP=TN=FP=FN=0
    for key, info in per_phase.items():
        stem, start, end = key
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            continue
        # c50 from new computation
        n_aloft_50, _, _ = compute_per_frame(balls_data_50[stem], wrists_data[stem], start, end)
        if n_aloft_50:
            pct_ge3_50 = sum(1 for n in n_aloft_50 if n >= 3) / len(n_aloft_50)
        else:
            pct_ge3_50 = 1.0
        rejected = info['max_4'] == 4 or pct_ge3_50 < 0.40
        if is_real and not rejected: TP += 1
        elif is_misclass and rejected: TN += 1
        elif is_misclass and not rejected: FP += 1
        elif is_real and rejected: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    # Try: REJECT if c40_max_aloft == 4 OR (c40_pct_ge3 < 0.30 AND drop_max >= 0)
    print("\n=== Rule F5: REJECT if c40_max_aloft == 4 OR (c40_pct_ge3 < 0.30 AND drop_max == 0) ===")
    TP=TN=FP=FN=0
    for key, info in per_phase.items():
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            continue
        with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
            h90d = json.load(f)
        key_str = f"{key[0]}_{key[1]}_{key[2]}"
        h90feats = h90d.get(key_str, {}).get('feats', {})
        c4 = h90feats.get('c40', {}) or {}
        pct_ge3 = c4.get('pct_ge3', 1.0)
        rejected = info['max_4'] == 4 or (pct_ge3 < 0.30 and info['drop_max'] == 0)
        if is_real and not rejected: TP += 1
        elif is_misclass and rejected: TN += 1
        elif is_misclass and not rejected: FP += 1
        elif is_real and rejected: FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")

    # Final attempt: per-stem rule
    print("\n=== Rule F6 (per-stem): H82+ (c40_max>=4 on youtu) OR (c40_pct_ge3<0.20 on ident) ===")
    TP=TN=FP=FN=0
    ident_TP=ident_TN=ident_FP=ident_FN=0
    youtu_TP=youtu_TN=youtu_FP=youtu_FN=0
    for key, info in per_phase.items():
        stem, start, end = key
        verdict = info['verdict']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            if is_misclass: TN += 1
            if stem.startswith("ident"): ident_TN += 1
            else: youtu_TN += 1
            continue
        with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
            h90d = json.load(f)
        key_str = f"{key[0]}_{key[1]}_{key[2]}"
        h90feats = h90d.get(key_str, {}).get('feats', {})
        c4 = h90feats.get('c40', {}) or {}
        pct_ge3 = c4.get('pct_ge3', 1.0)
        # Per-stem
        if stem.startswith("ident"):
            rejected = pct_ge3 < 0.20
        else:
            rejected = info['max_4'] == 4 or pct_ge3 < 0.30
        if is_real and not rejected:
            TP += 1
            if stem.startswith("ident"): ident_TP += 1
            else: youtu_TP += 1
        elif is_misclass and rejected:
            TN += 1
            if stem.startswith("ident"): ident_TN += 1
            else: youtu_TN += 1
        elif is_misclass and not rejected:
            FP += 1
            if stem.startswith("ident"): ident_FP += 1
            else: youtu_FP += 1
        elif is_real and rejected:
            FN += 1
            if stem.startswith("ident"): ident_FN += 1
            else: youtu_FN += 1
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  Combined: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    pi = ident_TP / max(1, ident_TP+ident_FP); ri = ident_TP / max(1, ident_TP+ident_FN)
    ai = (ident_TP+ident_TN) / max(1, ident_TP+ident_TN+ident_FP+ident_FN)
    py = youtu_TP / max(1, youtu_TP+youtu_FP); ry = youtu_TP / max(1, youtu_TP+youtu_FN)
    ay = (youtu_TP+youtu_TN) / max(1, youtu_TP+youtu_TN+youtu_FP+youtu_FN)
    print(f"  ident: TP={ident_TP} TN={ident_TN} FP={ident_FP} FN={ident_FN} P={pi:.3f} R={ri:.3f} acc={ai:.3f}")
    print(f"  youtu: TP={youtu_TP} TN={youtu_TN} FP={youtu_FP} FN={youtu_FN} P={py:.3f} R={ry:.3f} acc={ay:.3f}")

    # Per-phase detail for the best rule
    print("\n=== Per-phase detail for F6 (per-stem) ===")
    for key in sorted(per_phase.keys()):
        stem, start, end = key
        verdict = per_phase[key]['verdict']
        info = per_phase[key]
        with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
            h90d = json.load(f)
        key_str = f"{key[0]}_{key[1]}_{key[2]}"
        h90feats = h90d.get(key_str, {}).get('feats', {})
        c4 = h90feats.get('c40', {}) or {}
        pct_ge3 = c4.get('pct_ge3', 1.0)
        if stem.startswith("ident"):
            rule = f"c40p3={pct_ge3:.2f} ident rule (p3<0.20)"
            rejected = pct_ge3 < 0.20
        else:
            rule = f"c40p3={pct_ge3:.2f} max4={info['max_4']} youtu rule"
            rejected = info['max_4'] == 4 or pct_ge3 < 0.30
        h82 = h82_v1_catches(key)
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        outcome = "H82_TN" if h82 and is_misclass else "H82_TP" if h82 else (
            "FN" if rejected and is_real else
            "FP" if not rejected and is_misclass else
            "TN" if rejected and is_misclass else
            "TP")
        print(f"  {stem[:5]} f={start}-{end} {verdict:<22} {rule:<50} -> {outcome}")


if __name__ == "__main__":
    main()
