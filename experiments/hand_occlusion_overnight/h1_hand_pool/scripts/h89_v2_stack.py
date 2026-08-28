#!/usr/bin/env python3
"""
H89 v2 — Combine YOLO conf filter (H89) with H82 v1 stack.

H82 v1 = (H43 OR H69 OR H74v2) OR H78 mean_diff>10 (H78 fires on FOUNTAIN_3+ only)
Plus H71 spec_conc gate for MIXED_3+.

Question: Does the YOLO conf filter (H89) help on the YouTube side
when combined with H82 v1?

Strategy: H89 is an additional filter on top of H82 v1. Reject phase
if H82 v1 says reject OR H89 says reject. Try conf-floor 0.30, 0.40
with thr 0.30.
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
    return n_aloft


# Load h40v2, h70_phases, h78 data
def load_h40v2():
    out = {}
    for fpath in H1_DATA.glob("h40v2_continuous_*.csv"):
        stem = fpath.name.replace("h40v2_continuous_", "").replace(".csv", "")
        with open(fpath) as f:
            for r in csv.DictReader(f):
                frame = int(r["frame"])
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                rr = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, frame)] = (l, rr)
    return out


def load_h70_phases():
    out = {}
    for fpath in H1_DATA.glob("h70_phases_*.csv"):
        stem = fpath.name.replace("h70_phases_", "").replace(".csv", "")
        with open(fpath) as f:
            for r in csv.DictReader(f):
                out[(stem, int(r["phase_start"]), int(r["phase_end"]))] = {
                    "pattern": r["pattern"],
                    "mean_confidence": float(r["mean_confidence"]),
                    "spectral_concentration": float(r["spectral_concentration"]),
                }
    return out


def load_h78():
    out = {}
    fpath = H1_DATA / "h78v2_wrist_distance_per_phase.csv"
    if fpath.exists():
        with open(fpath) as f:
            for r in csv.DictReader(f):
                key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
                out[key] = r
    return out


# Ground truth
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


def h74v2_rejects(stem, start, end, h40_data):
    lrs = []
    for f in range(start, end + 1):
        if (stem, f) in h40_data:
            l, r = h40_data[(stem, f)]
            lrs.append(l + r)
    if not lrs:
        return False
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    unique_LR = len(set(round(v, 2) for v in lrs))
    return (var < 0.20) and (unique_LR <= 2)


def h82v1_filter(stem, start, end, pattern, conf, spec_conc, h40_data, h78_data):
    """Replicates H82 v1: (H43 OR H69 OR H74v2) OR H78 mean_diff>10; plus H71 for MIXED_3+."""
    h43 = (conf < 0.55) and pattern == "FOUNTAIN_3+"
    h69 = (spec_conc < 0.15) and pattern == "FOUNTAIN_3+"
    h74v2 = h74v2_rejects(stem, start, end, h40_data) and pattern in ("FOUNTAIN_3+", "CASCADE_3+")

    h78_key = (stem, start, end)
    h78_row = h78_data.get(h78_key, {})
    mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0
    h78 = (mean_diff > 10) and pattern == "FOUNTAIN_3+"

    h71 = pattern.startswith("MIXED_3+") and spec_conc < 0.10

    return h43 or h69 or h74v2 or h78 or h71


def main():
    print("=" * 80)
    print("H89 v2 — Combine YOLO conf filter with H82 v1 stack")
    print("=" * 80)

    h40_data = load_h40v2()
    h70_data = load_h70_phases()
    h78_data = load_h78()

    # Compute H87 metric for each conf floor
    conf_results = {}
    for min_conf in [0.0, 0.20, 0.30, 0.40, 0.50]:
        balls_data = {stem: load_balls_with_conf(stem, min_conf) for stem in STEMS}
        wrists_data = {stem: load_wrists(stem) for stem in STEMS}
        phase_data = {}
        for key, gt in GT.items():
            stem, start, end = key
            n_aloft = compute_aloft_per_frame(balls_data[stem], wrists_data[stem], start, end)
            if not n_aloft:
                phase_data[key] = {"pct_ge3": None}
                continue
            pct_ge3 = sum(1 for n in n_aloft if n >= 3) / len(n_aloft)
            phase_data[key] = {"pct_ge3": pct_ge3}
        conf_results[min_conf] = phase_data

    # Stack configurations: (label, conf_floor, h87_thr)
    # H82 v1 alone: conf=0.0, h87_thr=None
    # H82 v1 + H87: conf=0.0, h87_thr=0.20
    # H82 v1 + H89 (conf=0.40, thr=0.30): adds YouTube CASCADE_REAL catch
    stacks = [
        ("H82 v1 alone (baseline)", 0.0, None),
        ("H82 v1 + H87 thr=0.20 (H82+H87 baseline)", 0.0, 0.20),
        ("H82 v1 + H89 conf=0.30 thr=0.30", 0.30, 0.30),
        ("H82 v1 + H89 conf=0.30 thr=0.20", 0.30, 0.20),
        ("H82 v1 + H89 conf=0.40 thr=0.30", 0.40, 0.30),
        ("H82 v1 + H89 conf=0.40 thr=0.20", 0.40, 0.20),
        ("H82 v1 + H89 conf=0.40 thr=0.40", 0.40, 0.40),
    ]

    print(f"\n{'Stack':<55} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
    for label, conf_floor, h87_thr in stacks:
        TP = TN = FP = FN = 0
        for key, gt in GT.items():
            stem, start, end = key
            pattern, verdict = gt
            h70 = h70_data.get(key, {})
            h12_conf = h70.get("mean_confidence", 1.0)
            spec_conc = h70.get("spectral_concentration", 1.0)

            # H82 v1 filter
            h82_reject = h82v1_filter(stem, start, end, pattern, h12_conf, spec_conc, h40_data, h78_data)

            # H87 / H89 filter
            h87_reject = False
            if h87_thr is not None:
                pct_ge3 = conf_results[conf_floor][key]["pct_ge3"]
                if pct_ge3 is not None:
                    h87_reject = pct_ge3 < h87_thr

            rejected = h82_reject or h87_reject
            keep = not rejected

            is_real = verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = verdict in (
                "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
            )

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
        print(f"{label:<55} {TP:>3} {TN:>3} {FP:>3} {FN:>3} {p:>6.3f} {r:>6.3f} {acc:>6.3f}")

    # Per-stem breakdown for the best stack
    print("\n=== Per-stem for H82 v1 + H89 conf=0.40 thr=0.30 ===")
    conf_floor = 0.40
    h87_thr = 0.30
    for stem_filter in ["all", "ident", "youtu"]:
        TP = TN = FP = FN = 0
        for key, gt in GT.items():
            stem, start, end = key
            if stem_filter == "ident" and not stem.startswith("ident"):
                continue
            if stem_filter == "youtu" and not stem.startswith("youtu"):
                continue
            pattern, verdict = gt
            h70 = h70_data.get(key, {})
            h12_conf = h70.get("mean_confidence", 1.0)
            spec_conc = h70.get("spectral_concentration", 1.0)
            h82_reject = h82v1_filter(stem, start, end, pattern, h12_conf, spec_conc, h40_data, h78_data)
            pct_ge3 = conf_results[conf_floor][key]["pct_ge3"]
            h87_reject = pct_ge3 is not None and pct_ge3 < h87_thr
            rejected = h82_reject or h87_reject
            keep = not rejected
            is_real = verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = verdict in (
                "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
            )
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP + FP)
        r = TP / max(1, TP + FN)
        acc = (TP + TN) / max(1, TP + TN + FP + FN)
        print(f"  {stem_filter:<7}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  acc={acc:.3f}")

    # Save summary
    summary = {
        "stacks": [],
        "conf_floors": list(conf_results.keys()),
    }
    for label, conf_floor, h87_thr in stacks:
        TP = TN = FP = FN = 0
        for key, gt in GT.items():
            stem, start, end = key
            pattern, verdict = gt
            h70 = h70_data.get(key, {})
            h12_conf = h70.get("mean_confidence", 1.0)
            spec_conc = h70.get("spectral_concentration", 1.0)
            h82_reject = h82v1_filter(stem, start, end, pattern, h12_conf, spec_conc, h40_data, h78_data)
            h87_reject = False
            if h87_thr is not None:
                pct_ge3 = conf_results[conf_floor][key]["pct_ge3"]
                if pct_ge3 is not None:
                    h87_reject = pct_ge3 < h87_thr
            rejected = h82_reject or h87_reject
            keep = not rejected
            is_real = verdict in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = verdict in (
                "MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO"
            )
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP + FP)
        r = TP / max(1, TP + FN)
        acc = (TP + TN) / max(1, TP + TN + FP + FN)
        summary["stacks"].append({
            "label": label, "conf_floor": conf_floor, "h87_thr": h87_thr,
            "TP": TP, "TN": TN, "FP": FP, "FN": FN,
            "P": round(p, 3), "R": round(r, 3), "acc": round(acc, 3)
        })

    with open(f"{H1_DATA}/h89_v2_stack_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h89_v2_stack_summary.json")


if __name__ == "__main__":
    main()
