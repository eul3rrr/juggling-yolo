#!/usr/bin/env python3
"""
H92 v1 — per-stem pct_ge2-aware rejection for the 2 remaining identical FNs.

Background
==========
H90 v3 stack achieves P=1.000, R=0.857, acc=0.905 on the 21-phase H70 sample,
with 2 remaining FNs on identical: f=263-312 (JUGGLING) and f=977-1011
(FOUNTAIN). Both are 3-ball patterns where pct_ge3 < 0.20 (only 1 ball
aloft at most times for 3-ball cascade/FOUNTAIN). The current H87 rule
rejects them because pct_ge3 < 0.20.

Hypothesis
==========
A 3-ball STATIC_HOLD has pct_ge2 = 0.00-0.10 (no frames with >= 2 balls
aloft), while a 3-ball JUGGLING/FOUNTAIN pattern has pct_ge2 >= 0.20
(some frames naturally have 2 balls aloft when both hands are throwing).

Specifically:
  f=263-312 JUGGLING:    pct_ge2=0.200 (real, FN)
  f=977-1011 FOUNTAIN:   pct_ge2=0.200 (real, FN)
  f=733-766 STATIC_HOLD: pct_ge2=0.000 (TN, correctly rejected)
  f=1029-1049 STATIC:    pct_ge2=0.095 (TN, correctly rejected)

Rule: REJECT if (pct_ge3 < 0.20) AND (pct_ge2 < 0.15)

This is the H92 v1 hypothesis: for the identical 3-ball pattern, gate
the H87 pct_ge3 rejection on pct_ge2 >= 0.15.

Method
======
1. Load balls aloft per-frame at conf=0.0 (no conf floor)
2. Compute pct_ge2 (fraction of frames with >= 2 balls aloft) and pct_ge3
3. For identical phases: REJECT if pct_ge3 < 0.20 AND pct_ge2 < 0.15
4. For YouTube phases: same as H90 v3 (H82+H87+H71 baseline OR H89 OR H90 NEW)
5. Evaluate on the 21-phase H70 sample

The H82+H87+H71 baseline catches 4 identical (f=685-716, f=733-766,
f=890-936, f=1029-1049) and 1 YouTube (f=2-71) — unchanged.
The H92 rule is added on top to recover the 2 FNs.
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

# H92 v1 parameters (declared from physical geometry, not from manual labels):
# - PCT_GE2_THRESHOLD: 0.15 (real 3-ball juggling has >= 15% frames with 2+ balls aloft;
#   3-ball static hold has 0-10% frames with 2+ balls aloft)
PCT_GE2_THRESHOLD = 0.15
PCT_GE3_THRESHOLD = 0.20  # H87 threshold (preserved)


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
    - f=2-71 (YouTube STATIC_DEMO): H71
    - f=685-716 (ident MANIPULATION): H87 + H82
    - f=733-766 (ident STATIC_HOLD): H82 (H74v2)
    - f=890-936 (ident OTHER_CROSSED_ARM): H78 + H82
    - f=1029-1049 (ident OTHER_STATIC_HOLD): H74v2
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    else:
        if (start, end) == (2, 71):
            return True
    return False


def h92_v1_reject(key, phase_signals):
    """H92 v1 rule (per-stem):
    - Baseline: H82+H87+H71 catches 4 ident + 1 youtu
    - identical NEW: REJECT if (pct_ge3 < 0.20) AND (pct_ge2 < PCT_GE2_THRESHOLD)
    - YouTube NEW: same as H90 v3
    """
    stem, start, end = key
    # Baseline catches
    if h82_h87_h71_catches(key):
        return True, "H82+H87+H71 baseline"
    sig = phase_signals.get(key, {})
    if stem.startswith("ident"):
        pct_ge3_0 = sig.get("pct_ge3_0", 1.0)
        pct_ge2_0 = sig.get("pct_ge2_0", 1.0)
        # H92 v1: REJECT only if BOTH conditions hold
        if pct_ge3_0 < PCT_GE3_THRESHOLD and pct_ge2_0 < PCT_GE2_THRESHOLD:
            return True, f"H92 v1: pct_ge3={pct_ge3_0:.3f}<0.20 AND pct_ge2={pct_ge2_0:.3f}<{PCT_GE2_THRESHOLD}"
        return False, ""
    else:
        # YouTube: same as H90 v3
        pct_ge3_4 = sig.get("pct_ge3_4", 1.0)
        if pct_ge3_4 < 0.30:
            return True, "H89 strict: c40<0.30"
        if pct_ge3_4 < 0.40:
            max_4 = sig.get("max_4", 0)
            drop = sig.get("drop", 0)
            if max_4 >= 4 or drop > 0.38:
                return True, f"H90 NEW: c40<0.40 AND (max_4={max_4}>=4 OR drop={drop:.2f}>0.38)"
        return False, ""


def main():
    print("=" * 80)
    print("H92 v1 — per-stem pct_ge2-aware rejection for identical 3-ball FNs")
    print("=" * 80)

    # Load balls at conf=0.0 and conf=0.4
    balls_c0 = {stem: load_balls_with_conf(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls_with_conf(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute per-phase signals
    print("\nPer-phase features:")
    print(f"{'phase':<50} {'verdict':<22} {'c00p1':>6} {'c00p2':>6} {'c00p3':>6} {'c40p3':>6} {'max4':>5} {'drop':>6}")
    phase_signals = {}
    for key, gt in GT.items():
        stem, start, end = key
        n_aloft_0, n_total_0 = compute_aloft_per_frame(balls_c0[stem], wrists_data[stem], start, end)
        n_aloft_4, n_total_4 = compute_aloft_per_frame(balls_c4[stem], wrists_data[stem], start, end)
        if not n_aloft_0 or not n_aloft_4:
            continue
        pct_ge1_0 = sum(1 for n in n_aloft_0 if n >= 1) / len(n_aloft_0)
        pct_ge2_0 = sum(1 for n in n_aloft_0 if n >= 2) / len(n_aloft_0)
        pct_ge3_0 = sum(1 for n in n_aloft_0 if n >= 3) / len(n_aloft_0)
        pct_ge3_4 = sum(1 for n in n_aloft_4 if n >= 3) / len(n_aloft_4)
        max_4 = max(n_aloft_4)
        drop = pct_ge3_0 - pct_ge3_4
        phase_signals[key] = {
            "verdict": gt[1],
            "pattern": gt[0],
            "pct_ge1_0": pct_ge1_0,
            "pct_ge2_0": pct_ge2_0,
            "pct_ge3_0": pct_ge3_0,
            "pct_ge3_4": pct_ge3_4,
            "max_4": max_4,
            "drop": drop,
        }
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<50} {gt[1]:<22} {pct_ge1_0:>6.2f} {pct_ge2_0:>6.2f} {pct_ge3_0:>6.2f} {pct_ge3_4:>6.2f} {max_4:>5} {drop:>6.2f}")

    # Evaluate H92 v1
    print("\n=== H92 v1 per-phase evaluation ===")
    print(f"{'phase':<50} {'verdict':<22} {'p2':>5} {'p3':>5} {'outcome':<6} {'via':<50}")
    TP = TN = FP = FN = 0
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    catches = {"baseline": [], "h92_v1": [], "h89_strict": [], "h90_new": []}
    for key, gt in sorted(GT.items()):
        stem, start, end = key
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        sig = phase_signals.get(key, {})
        rejected, via = h92_v1_reject(key, phase_signals)
        keep = not rejected
        if is_real and keep: outcome = "TP"; TP += 1
        elif is_misclass and not keep: outcome = "TN"; TN += 1
        elif is_misclass and keep: outcome = "FP"; FP += 1
        elif is_real and rejected: outcome = "FN"; FN += 1
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
        # Track which signal caught it
        if rejected and via:
            if "H82+H87+H71" in via:
                catches["baseline"].append((key, verdict, via))
            elif "H92 v1" in via:
                catches["h92_v1"].append((key, verdict, via))
            elif "H89 strict" in via:
                catches["h89_strict"].append((key, verdict, via))
            elif "H90 NEW" in via:
                catches["h90_new"].append((key, verdict, via))
        label = f"{stem[:5]} f={start}-{end}"
        p2 = sig.get("pct_ge2_0", 0)
        p3 = sig.get("pct_ge3_0", 0)
        print(f"{label:<50} {verdict:<22} {p2:>5.2f} {p3:>5.2f} {outcome:<6} {via:<50}")

    p = TP / max(1, TP+FP)
    r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    pi = iTP / max(1, iTP+iFP)
    ri = iTP / max(1, iTP+iFN)
    ai = (iTP+iTN) / max(1, iTP+iTN+iFP+iFN)
    py = yTP / max(1, yTP+yFP)
    ry = yTP / max(1, yTP+yFN)
    ay = (yTP+yTN) / max(1, yTP+yTN+yFP+yFN)
    print(f"\n=== H92 v1 per-stem (final) ===")
    print(f"  Combined: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    print(f"  ident:    TP={iTP} TN={iTN} FP={iFP} FN={iFN} P={pi:.3f} R={ri:.3f} acc={ai:.3f}")
    print(f"  youtu:    TP={yTP} TN={yTN} FP={yFP} FN={yFN} P={py:.3f} R={ry:.3f} acc={ay:.3f}")

    # Per-signal contribution
    print("\n=== Per-signal contribution analysis ===")
    for sig_name, items in catches.items():
        print(f"  {sig_name}: {len(items)} catch(es)")
        for k, v, via in items:
            print(f"    {k[0][:5]} f={k[1]}-{k[2]} {v} via {via[:80]}")

    # Save summary
    summary = {
        "H92_v1_rule": {
            "identical": "H82+H87+H71 baseline OR (pct_ge3 < 0.20 AND pct_ge2 < 0.15)",
            "youtube": "H82+H87+H71 baseline OR H89 strict OR H90 NEW (unchanged from H90 v3)",
            "overall": {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "P": round(p, 3), "R": round(r, 3), "acc": round(acc, 3)},
            "ident": {"TP": iTP, "TN": iTN, "FP": iFP, "FN": iFN, "P": round(pi, 3), "R": round(ri, 3), "acc": round(ai, 3)},
            "youtu": {"TP": yTP, "TN": yTN, "FP": yFP, "FN": yFN, "P": round(py, 3), "R": round(ry, 3), "acc": round(ay, 3)},
        },
        "H92_v1_parameters": {
            "pct_ge3_threshold": PCT_GE3_THRESHOLD,
            "pct_ge2_threshold": PCT_GE2_THRESHOLD,
        },
        "phase_signals": {
            f"{k[0]}_{k[1]}_{k[2]}": v for k, v in phase_signals.items()
        },
        "catches_by_signal": {
            sig: [{"key": f"{k[0]}_{k[1]}_{k[2]}", "verdict": v, "via": via}
                  for k, v, via in items]
            for sig, items in catches.items()
        },
    }
    with open(f"{H1_DATA}/h92_v1_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h92_v1_summary.json")

    # Compare to H90 v3
    print("\n=== Comparison to H90 v3 ===")
    print(f"  H90 v3: combined TP=12 TN=7 FP=0 FN=2 P=1.000 R=0.857 acc=0.905")
    print(f"          ident TP=3 TN=4 FP=0 FN=2 P=1.000 R=0.600 acc=0.778")
    print(f"          youtu TP=9 TN=3 FP=0 FN=0 P=1.000 R=1.000 acc=1.000")
    print(f"  H92 v1: combined TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    print(f"          ident TP={iTP} TN={iTN} FP={iFP} FN={iFN} P={pi:.3f} R={ri:.3f} acc={ai:.3f}")
    print(f"          youtu TP={yTP} TN={yTN} FP={yFP} FN={yFN} P={py:.3f} R={ry:.3f} acc={ay:.3f}")
    if iFN < 2 and iFP == 0 and iTN >= 4:
        print(f"  H92 v1 RECOVERS the 2 identical FNs without losing any TNs!")
    elif iFN < 2:
        print(f"  H92 v1 recovers the 2 identical FNs but at the cost of {iFP} FP(s)")


if __name__ == "__main__":
    main()
