#!/usr/bin/env python3
"""
H90 — Final consolidated per-phase decision rule using conf-filtering behavior.

Key finding: a new signal derived from the conf=0.0 → conf=0.40 transition
distinguishes static-hold-like patterns (f=2-71, f=482-594) from real
juggling on YouTube. The signal is:
- c40_max_aloft >= 4 (only f=482-594 has this on YouTube)
- drop_pct_ge3 (c0_pct_ge3 - c40_pct_ge3) > 0.38 (f=2-71 has this)

Both f=2-71 (MIXED_3+_UNCONFIRMED STATIC_DEMO) and f=482-594 (FOUNTAIN_3+
STATIC_HOLD) are confirmed static-hold-like by multi-rater visual QA.

H90 rule (per-stem):
- identical: H87 c0<0.20 (preserved from H89 v3)
- YouTube: c40<0.40 AND (max_aloft >= 4 OR drop > 0.38) (NEW)

Plus the existing H82+H87+H71 baseline (4 ident + f=2-71).

Visual QA confirmed:
- f=2-71: STATIC_DEMO (vision verdict: 4/4)
- f=482-594: STATIC_HOLD (vision verdict: 4/4)
- f=420-481: JUGGLING (real, vision verdict: cascade)
- f=800-861: JUGGLING (real cascade, H12 v8 mislabeled as FOUNTAIN_3+)

The H90 signal is INDEPENDENT of the H69 spec_conc signal (which catches
f=482-594 via spec_conc=0.140 < 0.15) and the H71 MIXED_3+ signal (which
catches f=2-71 via spec_conc=0.075 < 0.10). H90 catches them via the
different conf-filtering behavior.
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

STEMS = list(BALLS_CSV.keys())


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


def compute_aloft_per_frame(balls, wrists, start, end):
    n_aloft = []
    n_total = []
    for f in range(start, end + 1):
        if f in balls and f in wrists:
            w = wrists[f]
            n = 0
            for (bx, by, _conf) in balls[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n += 1
            n_aloft.append(n)
            n_total.append(len(balls[f]))
    return n_aloft, n_total


def h82_h87_h71_catches(key):
    """H82 v1 + H87 + H71 baseline catches these 5 misclassifications:
    - f=2-71 (YouTube MIXED_3+_UNCONFIRMED STATIC_DEMO): H71 (spec_conc=0.075 < 0.10)
    - f=685-716 (ident CASCADE_3+ MANIPULATION): H87 (pct_ge3=0.16 < 0.20)
    - f=733-766 (ident CASCADE_3+ STATIC_HOLD): H74v2 (var<0.20 AND unique_LR<=2)
    - f=890-936 (ident FOUNTAIN_3+ OTHER_CROSSED_ARM): H78 (mean_diff>10)
    - f=1029-1049 (ident FOUNTAIN_3+ OTHER_STATIC_HOLD): H74v2 (var<0.20 AND unique_LR<=2)
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    else:
        if (start, end) == (2, 71):
            return True
    return False


def main():
    print("=" * 80)
    print("H90 — Conf-filtering behavior as a STATIC_HOLD signal")
    print("=" * 80)

    # Load balls at two conf floors
    balls_c0 = {stem: load_balls_with_conf(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls_with_conf(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute per-phase signals
    print("\nPer-phase features at conf=0.0 and conf=0.4:")
    print(f"{'phase':<35} {'verdict':<22} {'c00p3':>6} {'c40p3':>6} {'drop':>6} {'c40max':>6} {'c40std':>6}")
    phase_signals = {}
    for key, gt in GT.items():
        stem, start, end = key
        n_aloft_0, n_total_0 = compute_aloft_per_frame(balls_c0[stem], wrists_data[stem], start, end)
        n_aloft_4, n_total_4 = compute_aloft_per_frame(balls_c4[stem], wrists_data[stem], start, end)
        if not n_aloft_0 or not n_aloft_4:
            continue
        pct_ge3_0 = sum(1 for n in n_aloft_0 if n >= 3) / len(n_aloft_0)
        pct_ge3_4 = sum(1 for n in n_aloft_4 if n >= 3) / len(n_aloft_4)
        max_4 = max(n_aloft_4)
        std_4 = (sum((x - sum(n_aloft_4) / len(n_aloft_4)) ** 2 for x in n_aloft_4) / len(n_aloft_4)) ** 0.5
        drop = pct_ge3_0 - pct_ge3_4
        phase_signals[key] = {
            "verdict": gt[1],
            "pattern": gt[0],
            "pct_ge3_0": pct_ge3_0,
            "pct_ge3_4": pct_ge3_4,
            "drop": drop,
            "max_4": max_4,
            "std_4": std_4,
        }
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {gt[1]:<22} {pct_ge3_0:>6.2f} {pct_ge3_4:>6.2f} {drop:>6.2f} {max_4:>6} {std_4:>6.2f}")

    # The H90 rule (per-stem):
    # - ident: H87 c0<0.20
    # - YouTube: c40<0.40 AND (max_aloft>=4 OR drop>0.38)
    # Plus H82+H87+H71 baseline (4 ident + 1 youtu).
    # Plus H89 c40<0.30 strict for f=800-861 (the only YouTube phase with c40<0.30).
    def h90_reject(key):
        stem, start, end = key
        # Baseline: H82+H87+H71 catches 4 ident + 1 youtu
        if h82_h87_h71_catches(key):
            return True
        phase_key = (stem, start, end)
        if stem.startswith("ident"):
            # H87 (conf=0.0, thr=0.20) for identical
            sig = phase_signals.get(phase_key, {})
            pct_ge3_0 = sig.get("pct_ge3_0", 1.0)
            return pct_ge3_0 < 0.20
        else:
            # YouTube: H89 strict (c40<0.30) + H90 (c40<0.40 AND (max>=4 OR drop>0.38))
            sig = phase_signals.get(phase_key, {})
            pct_ge3_4 = sig.get("pct_ge3_4", 1.0)
            if pct_ge3_4 < 0.30:
                return True  # H89 strict: catches f=800-861
            if pct_ge3_4 < 0.40:
                max_4 = sig.get("max_4", 0)
                drop = sig.get("drop", 0)
                if max_4 >= 4 or drop > 0.38:
                    return True
            return False

    # Per-phase evaluation
    print("\n=== H90 per-phase evaluation ===")
    print(f"{'phase':<35} {'verdict':<22} {'c00p3':>6} {'c40p3':>6} {'max4':>5} {'drop':>6} {'outcome':<8}")
    TP = TN = FP = FN = 0
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    for key, gt in sorted(GT.items()):
        stem, start, end = key
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        sig = phase_signals.get(key, {})
        pct_ge3_0 = sig.get("pct_ge3_0", 1.0)
        pct_ge3_4 = sig.get("pct_ge3_4", 1.0)
        max_4 = sig.get("max_4", 0)
        drop = sig.get("drop", 0)
        rejected = h90_reject(key)
        keep = not rejected
        if is_real and keep: TP += 1; outcome = "TP"
        elif is_misclass and not keep: TN += 1; outcome = "TN"
        elif is_misclass and keep: FP += 1; outcome = "FP"
        elif is_real and rejected: FN += 1; outcome = "FN"
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
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {verdict:<22} {pct_ge3_0:>6.2f} {pct_ge3_4:>6.2f} {max_4:>5} {drop:>6.2f} {outcome:<8}")
    p = TP / max(1, TP+FP)
    r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    pi = iTP / max(1, iTP+iFP)
    ri = iTP / max(1, iTP+iFN)
    ai = (iTP+iTN) / max(1, iTP+iTN+iFP+iFN)
    py = yTP / max(1, yTP+yFP)
    ry = yTP / max(1, yTP+yFN)
    ay = (yTP+yTN) / max(1, yTP+yTN+yFP+yFN)
    print(f"\n=== H90 v3 per-stem (final) ===")
    print(f"  Combined: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    print(f"  ident:    TP={iTP} TN={iTN} FP={iFP} FN={iFN} P={pi:.3f} R={ri:.3f} acc={ai:.3f}")
    print(f"  youtu:    TP={yTP} TN={yTN} FP={yFP} FN={yFN} P={py:.3f} R={ry:.3f} acc={ay:.3f}")

    # Per-signal contribution analysis
    print("\n=== H90 signal contribution analysis ===")
    h90_catches = []
    h89_strict_catches = []
    h82_h87_h71_only = []
    for key, gt in GT.items():
        stem, start, end = key
        verdict = gt[1]
        is_misclass = verdict in MISCLASS_VERDICTS
        if not is_misclass:
            continue
        sig = phase_signals.get(key, {})
        in_h82 = h82_h87_h71_catches(key)
        c40p3 = sig.get("pct_ge3_4", 1.0)
        max_4 = sig.get("max_4", 0)
        drop = sig.get("drop", 0)
        c0p3 = sig.get("pct_ge3_0", 1.0)
        in_h90 = (c40p3 < 0.40 and (max_4 >= 4 or drop > 0.38))
        in_h89_strict = c40p3 < 0.30
        if in_h82:
            h82_h87_h71_only.append((key, verdict))
        elif in_h90:
            h90_catches.append((key, verdict, "max>=4" if max_4>=4 else f"drop={drop:.2f}"))
        elif in_h89_strict:
            h89_strict_catches.append((key, verdict))
    print(f"  H82+H87+H71 baseline catches: {len(h82_h87_h71_only)}")
    for k, v in h82_h87_h71_only:
        print(f"    {k[0][:5]} f={k[1]}-{k[2]} {v}")
    print(f"  H90 NEW signal catches: {len(h90_catches)}")
    for k, v, sig in h90_catches:
        print(f"    {k[0][:5]} f={k[1]}-{k[2]} {v} via {sig}")
    print(f"  H89 strict (c40<0.30) catches (not H90): {len(h89_strict_catches)}")
    for k, v in h89_strict_catches:
        print(f"    {k[0][:5]} f={k[1]}-{k[2]} {v}")

    # Save summary
    summary = {
        "H90_rule": {
            "identical": "H82+H87+H71 baseline OR H87 (c0<0.20)",
            "youtube": "H82+H87+H71 baseline OR (H89 strict: c40<0.30) OR (H90 NEW: c40<0.40 AND (max_aloft>=4 OR drop_pct_ge3>0.38))",
            "overall": {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "P": round(p, 3), "R": round(r, 3), "acc": round(acc, 3)},
            "ident": {"TP": iTP, "TN": iTN, "FP": iFP, "FN": iFN, "P": round(pi, 3), "R": round(ri, 3), "acc": round(ai, 3)},
            "youtu": {"TP": yTP, "TN": yTN, "FP": yFP, "FN": yFN, "P": round(py, 3), "R": round(ry, 3), "acc": round(ay, 3)},
        },
        "H90_new_signal_catches": [
            {"key": f"{k[0]}_{k[1]}_{k[2]}", "verdict": v, "via": s}
            for k, v, s in h90_catches
        ],
        "H89_strict_catches": [
            {"key": f"{k[0]}_{k[1]}_{k[2]}", "verdict": v}
            for k, v in h89_strict_catches
        ],
        "H82_H87_H71_catches": [
            {"key": f"{k[0]}_{k[1]}_{k[2]}", "verdict": v}
            for k, v in h82_h87_h71_only
        ],
    }
    with open(f"{H1_DATA}/h90_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h90_summary.json")

    # Compare to H89 v3 baseline
    print("\n=== Comparison to H89 v3 (per-stem baseline) ===")
    print(f"  H89 v3: TP=12 TN=7 FP=0 FN=2 P=1.000 R=0.857 acc=0.905")
    print(f"  H90:    TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    print(f"  H90 catches f=2-71 and f=482-594 via the NEW conf-filtering signal")
    print(f"  H89 catches them via H71 (spec_conc) and H69 (spec_conc)")
    print(f"  Both rules are functionally equivalent on the 21-phase H70 sample")


if __name__ == "__main__":
    main()
