#!/usr/bin/env python3
"""
H96 — H90 NEW signal properly integrated with H94 v4 (fix v5 bug + add H90 NEW for FOUNTAIN_3+).

Background
==========
H94 v4 (max_aloft=2, pct_ge1=0.92) achieves 17/3/1/0 (P=0.944, R=1.000,
acc=0.952) on the 21 H93 corrected phases. The 1 remaining FP is
f=482-594 YouTube STATIC_HOLD (FOUNTAIN_3+), which the H69+guard wrongly
suppresses (pct_ge1=1.0 > 0.92).

H90 NEW signal (from H90 v3): c40.pct_ge3<0.40 AND (c40.max_aloft>=4 OR
drop_pct_ge3>0.38).

H94 v5 attempted to add H90 NEW for FOUNTAIN_3+ but had a BUG:
`compute_aloft_features_with_conf` only returned c00_*/c40_* fields, NOT
plain `pct_ge1`. The rule's `aloft.get("pct_ge1", 0)` returned 0 (default),
so the H69+guard did NOT block H69 from firing on f=482-594 (0 < 0.92
trivially). This is why v5 shows f=482-594 as caught by "H69+guard" but
it's actually a bug — the real H94 v4 (which uses the un-conf'd
`compute_aloft_features`) does NOT catch f=482-594.

H96 v1 properly computes BOTH the v4 pct_ge1 (for the H43/H69 guard)
AND the c40 features (for the H90 NEW signal), and tests whether H90
NEW catches f=482-594 without false-rejecting f=800-861 (the real
5-ball cascade).

Hypothesis
==========
H90 NEW (c40.pct_ge3<0.40 AND (c40.max_aloft>=4 OR drop_pct_ge3>0.38))
should fire ONLY on f=482-594 STATIC_HOLD (c40g3=0.36, max_aloft=4) and
NOT on f=800-861 (c40g3=0.25, max_aloft=3, drop=0.34<0.38) — making
H96 v1 able to recover the 1 H94 v4 FP without false-rejecting any
real juggling.

H96 v1 rule (for FOUNTAIN_3+):
    H43+guard: conf<0.55 AND pct_ge1<0.92
    H69+guard: spec_conc<0.15 AND pct_ge1<0.92
    H90 NEW: c40.pct_ge3<0.40 AND (c40.max_aloft>=4 OR drop_pct_ge3>0.38)
    H74v4: var<0.20 AND uLR<=1
    H78: mean_diff>10

H96 v2 rule: H96 v1 but H90 NEW requires ONLY the c40.max_aloft>=4 path
(stricter, ignores drop_pct_ge3>0.38 which might be noisy).

H96 v3 rule: H96 v1 but H90 NEW uses c40.pct_ge3<0.30 (stricter
threshold, might avoid the f=800-861 confusion if c40g3 is borderline).

H96 v4 rule: H96 v1 but H90 NEW requires c40.max_aloft>=4 AND
c40.pct_ge3<0.40 (both, not OR — much stricter).

Method
======
1. Compute BOTH v4-style aloft features (for pct_ge1 guard) AND
   v5-style c40 features (for H90 NEW).
2. Test H96 v1, v2, v3, v4 on H93 corrected GT (21 phases).
3. Cross-validate on 113 manual review pairs (H59 GT) via H77.
"""
from __future__ import annotations

import csv
import json
import glob
import math
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


def compute_aloft_combined(balls_c0, balls_c4, wrists, start, end):
    """Compute aloft features using c0 (no conf filter) for H87+max_aloft + c4 features for H90 NEW.
    CRITICAL: must use ALL frames, not just frames where BOTH c0 and c4 have data. Otherwise
    H87+max_aloft's pct_ge3 changes (e.g., f=685-716 changes from 0.16 to 0.21)."""
    n_aloft_0, n_aloft_4 = [], []
    for f in range(start, end + 1):
        if f not in wrists:
            continue
        w = wrists[f]
        n0, n4 = 0, 0
        if f in balls_c0:
            for (bx, by, _) in balls_c0[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n0 += 1
        if f in balls_c4:
            for (bx, by, _) in balls_c4[f]:
                aloft = True
                if w["lw"] is not None and dist((bx, by), w["lw"]) < ALOFT_RADIUS:
                    aloft = False
                if w["rw"] is not None and dist((bx, by), w["rw"]) < ALOFT_RADIUS:
                    aloft = False
                if aloft:
                    n4 += 1
        # Include frame if EITHER c0 or c4 has data (so H87+max_aloft uses c0-only frames)
        if f in balls_c0:
            n_aloft_0.append(n0)
        if f in balls_c4:
            n_aloft_4.append(n4)
    if not n_aloft_0:
        return None
    n0 = len(n_aloft_0)
    n4 = len(n_aloft_4)
    pct_ge3_0 = sum(1 for x in n_aloft_0 if x >= 3) / n0
    pct_ge3_4 = sum(1 for x in n_aloft_4 if x >= 3) / max(1, n4)
    return {
        "pct_ge1": sum(1 for x in n_aloft_0 if x >= 1) / n0,  # c00 pct_ge1 for guard
        "pct_ge2": sum(1 for x in n_aloft_0 if x >= 2) / n0,
        "pct_ge3": pct_ge3_0,
        "max_aloft": max(n_aloft_0),
        "c00_pct_ge1": sum(1 for x in n_aloft_0 if x >= 1) / n0,
        "c00_pct_ge3": pct_ge3_0,
        "c00_max_aloft": max(n_aloft_0),
        "c40_pct_ge3": pct_ge3_4,
        "c40_max_aloft": max(n_aloft_4) if n4 > 0 else 0,
        "drop_pct_ge3": pct_ge3_0 - pct_ge3_4,
        "n_frames": n0,
        "n_frames_c4": n4,
    }


def load_h40v2():
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                r_v = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, int(r["frame"]))] = (l, r_v)
    return out


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


def load_h78():
    out = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = float(r["mean_diff_per_frame"])
    return out


def compute_h74_signals(h40v2, stem, start, end):
    lrs, Ls, Rs = [], [], []
    for f in range(start, end + 1):
        if (stem, f) in h40v2:
            l, r = h40v2[(stem, f)]
            lrs.append(l + r)
            Ls.append(l)
            Rs.append(r)
    if not lrs:
        return None
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    return {
        "var": var,
        "unique_LR": len(set(round(v, 2) for v in lrs)),
        "unique_L": len(set(round(v, 2) for v in Ls)),
        "unique_R": len(set(round(v, 2) for v in Rs)),
        "mean_LR": mean,
        "max_LR": max(lrs),
        "min_LR": min(lrs),
    }


# H96 v1: H94 v4 + H90 NEW (c40g3<0.40 AND (max4>=4 OR drop>0.38))
def h96_v1_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft,
                    pct_ge1_thr=0.92, max_aloft_thr=2):
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        drop = aloft.get("drop_pct_ge3", 0) if aloft else 0
        if conf < 0.55 and pct_ge1 < pct_ge1_thr:
            return True, "H43+guard"
        if spec_conc < 0.15 and pct_ge1 < pct_ge1_thr:
            return True, "H69+guard"
        # H90 NEW (properly integrated, requires BOTH aloft features and pct_ge1 check)
        if c40_pct_ge3 < 0.40 and (c40_max_aloft >= 4 or drop > 0.38):
            return True, "H90_NEW"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < 0.20 and max_aloft >= max_aloft_thr:
            return True, "H87+max_aloft"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


# H96 v2: H96 v1 with H90 NEW requiring ONLY c40.max_aloft>=4 (no drop path)
def h96_v2_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft,
                    pct_ge1_thr=0.92, max_aloft_thr=2):
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        if conf < 0.55 and pct_ge1 < pct_ge1_thr:
            return True, "H43+guard"
        if spec_conc < 0.15 and pct_ge1 < pct_ge1_thr:
            return True, "H69+guard"
        if c40_pct_ge3 < 0.40 and c40_max_aloft >= 4:  # STRICTER: no drop path
            return True, "H90_NEW_strict"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < 0.20 and max_aloft >= max_aloft_thr:
            return True, "H87+max_aloft"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


# H96 v3: H96 v1 with c40.pct_ge3<0.30 (stricter, avoid f=800-861)
def h96_v3_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft,
                    pct_ge1_thr=0.92, max_aloft_thr=2):
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        drop = aloft.get("drop_pct_ge3", 0) if aloft else 0
        if conf < 0.55 and pct_ge1 < pct_ge1_thr:
            return True, "H43+guard"
        if spec_conc < 0.15 and pct_ge1 < pct_ge1_thr:
            return True, "H69+guard"
        if c40_pct_ge3 < 0.30 and (c40_max_aloft >= 4 or drop > 0.38):  # STRICTER c40g3
            return True, "H90_NEW_v3"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < 0.20 and max_aloft >= max_aloft_thr:
            return True, "H87+max_aloft"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


# H96 v4: H96 v1 with H90 NEW requiring BOTH c40.max_aloft>=4 AND c40.pct_ge3<0.40 (AND not OR)
def h96_v4_decision(pattern, conf, spec_conc, h74_sig, mean_diff, aloft,
                    pct_ge1_thr=0.92, max_aloft_thr=2):
    if pattern == "FOUNTAIN_3+":
        pct_ge1 = aloft.get("pct_ge1", 0) if aloft else 0
        c40_pct_ge3 = aloft.get("c40_pct_ge3", 1) if aloft else 1
        c40_max_aloft = aloft.get("c40_max_aloft", 0) if aloft else 0
        drop = aloft.get("drop_pct_ge3", 0) if aloft else 0
        if conf < 0.55 and pct_ge1 < pct_ge1_thr:
            return True, "H43+guard"
        if spec_conc < 0.15 and pct_ge1 < pct_ge1_thr:
            return True, "H69+guard"
        if c40_pct_ge3 < 0.40 and c40_max_aloft >= 4 and drop > 0.20:  # BOTH
            return True, "H90_NEW_AND"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        pct_ge3 = aloft.get("pct_ge3", 0) if aloft else 0
        max_aloft = aloft.get("max_aloft", 0) if aloft else 0
        if pct_ge3 < 0.20 and max_aloft >= max_aloft_thr:
            return True, "H87+max_aloft"
        if h74_sig["var"] < 0.20 and h74_sig["unique_LR"] <= 1:
            return True, "H74v4"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def evaluate(gt_dict, signals, h74_signals, h78_data, aloft_signals,
             decision_fn, name="", pct_ge1_thr=0.92, max_aloft_thr=2):
    TP = TN = FP = FN = 0
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    per_phase = []
    for key, gt in sorted(gt_dict.items()):
        stem, start, end = key
        sig = signals.get(key)
        h74 = h74_signals.get(key)
        aloft = aloft_signals.get(key)
        if sig is None or h74 is None or aloft is None:
            continue
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        mean_diff = h78_data.get(key, 0)
        rej, reason = decision_fn(sig["pattern"], sig["conf"], sig["spec_conc"],
                                   h74, mean_diff, aloft, pct_ge1_thr, max_aloft_thr)
        keep = not rej
        if is_real and keep: outcome = "TP"
        elif is_misclass and not keep: outcome = "TN"
        elif is_misclass and keep: outcome = "FP"
        elif is_real and rej: outcome = "FN"
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
        if outcome == "TP": TP += 1
        elif outcome == "TN": TN += 1
        elif outcome == "FP": FP += 1
        elif outcome == "FN": FN += 1
        per_phase.append((key, gt, outcome, reason))
    p = TP / max(1, TP+FP)
    r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    pi = iTP / max(1, iTP+iFP)
    ri = iTP / max(1, iTP+iFN)
    ai = (iTP+iTN) / max(1, iTP+iTN+iFP+iFN)
    py = yTP / max(1, yTP+yFP)
    ry = yTP / max(1, yTP+yFN)
    ay = (yTP+yTN) / max(1, yTP+yTN+yFP+yFN)
    return {
        "name": name,
        "combined": (TP, TN, FP, FN, p, r, acc),
        "ident": (iTP, iTN, iFP, iFN, pi, ri, ai),
        "youtu": (yTP, yTN, yFP, yFN, py, ry, ay),
        "per_phase": per_phase,
    }


def main():
    h40v2 = load_h40v2()
    h70 = load_h70_phases()
    h78 = load_h78()

    print("Loading ball detections and pose (at conf=0.0 and conf=0.4)...")
    balls_c0 = {stem: load_balls(stem, 0.0) for stem in STEMS}
    balls_c4 = {stem: load_balls(stem, 0.40) for stem in STEMS}
    wrists_data = {stem: load_wrists(stem) for stem in STEMS}

    # Compute COMBINED aloft features (both c00 and c40)
    aloft_signals = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_aloft_combined(balls_c0[stem], balls_c4[stem],
                                    wrists_data[stem], start, end)
        if a:
            aloft_signals[key] = a

    EXTRA_SIGNALS = {
        ("identical_balls_trick_000_018", 733, 766): {
            "pattern": "CASCADE_3+", "n_frames": 34, "conf": 0.620, "spec_conc": 0.165,
        },
        ("identical_balls_trick_000_018", 1029, 1049): {
            "pattern": "FOUNTAIN_3+", "n_frames": 21, "conf": 0.463, "spec_conc": 0.140,
        },
    }
    all_signals = {**h70, **EXTRA_SIGNALS}

    h74_signals = {}
    for key in CORRECTED_GT.keys():
        sig = compute_h74_signals(h40v2, *key)
        if sig:
            h74_signals[key] = sig

    print("=" * 80)
    print("H96 — H90 NEW properly integrated with H94 v4 for FOUNTAIN_3+")
    print("=" * 80)

    # Per-phase H90 NEW signals
    print("\nPer-phase H90 NEW signal components (FOUNTAIN_3+ phases):")
    print(f"{'phase':<35} {'verdict':<22} {'c00g1':>6} {'c00g3':>6} {'c00mx':>5} {'c40g3':>6} {'c40mx':>5} {'drop':>5} {'H90NEW':>6}")
    for key in sorted(CORRECTED_GT.keys()):
        stem, start, end = key
        sig = all_signals.get(key)
        a = aloft_signals.get(key)
        if sig is None or a is None or sig["pattern"] != "FOUNTAIN_3+":
            continue
        verdict = CORRECTED_GT[key][1]
        label = f"{stem[:5]} f={start}-{end}"
        h90new = (a["c40_pct_ge3"] < 0.40 and (a["c40_max_aloft"] >= 4 or a["drop_pct_ge3"] > 0.38))
        print(f"{label:<35} {verdict:<22} {a['pct_ge1']:>6.2f} {a['pct_ge3']:>6.2f} {a['max_aloft']:>5} {a['c40_pct_ge3']:>6.2f} {a['c40_max_aloft']:>5} {a['drop_pct_ge3']:>5.2f} {str(h90new):>6}")

    # Compare 4 H96 variants + H94 v4 baseline
    print("\n=== H96 variants vs H94 v4 baseline (H93 corrected GT, 21 phases) ===")
    results = []
    for name, dec_fn in [
        ("H96 v1 (H94v4 + H90 NEW OR)", h96_v1_decision),
        ("H96 v2 (H90 NEW max>=4 only)", h96_v2_decision),
        ("H96 v3 (H90 NEW c40g3<0.30)", h96_v3_decision),
        ("H96 v4 (H90 NEW AND)", h96_v4_decision),
    ]:
        r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, aloft_signals,
                     dec_fn, name=name)
        results.append(r)
        c = r["combined"]
        i = r["ident"]
        y = r["youtu"]
        print(f"\n  {name}:")
        print(f"    combined: TP={c[0]} TN={c[1]} FP={c[2]} FN={c[3]} P={c[4]:.3f} R={c[5]:.3f} acc={c[6]:.3f}")
        print(f"    ident:    TP={i[0]} TN={i[1]} FP={i[2]} FN={i[3]} P={i[4]:.3f} R={i[5]:.3f} acc={i[6]:.3f}")
        print(f"    youtu:    TP={y[0]} TN={y[1]} FP={y[2]} FN={y[3]} P={y[4]:.3f} R={y[5]:.3f} acc={y[6]:.3f}")

    # Per-phase differences (only on the 6 FOUNTAIN_3+ phases)
    print("\n=== Per-phase FOUNTAIN_3+ decisions (H96 variants) ===")
    print(f"{'phase':<35} {'verdict':<22} {'H96v1':<14} {'H96v2':<14} {'H96v3':<14} {'H96v4':<14}")
    for r in results[0]["per_phase"]:
        key, gt, _, _ = r
        sig = all_signals.get(key)
        if sig is None or sig["pattern"] != "FOUNTAIN_3+":
            continue
        h96v1 = next((x for x in results[0]["per_phase"] if x[0] == key), None)
        h96v2 = next((x for x in results[1]["per_phase"] if x[0] == key), None)
        h96v3 = next((x for x in results[2]["per_phase"] if x[0] == key), None)
        h96v4 = next((x for x in results[3]["per_phase"] if x[0] == key), None)
        label = f"{key[0][:5]} f={key[1]}-{key[2]}"
        print(f"{label:<35} {gt[1]:<22} "
              f"{h96v1[3] if h96v1 else '?':<14} "
              f"{h96v2[3] if h96v2 else '?':<14} "
              f"{h96v3[3] if h96v3 else '?':<14} "
              f"{h96v4[3] if h96v4 else '?':<14}")

    # Sensitivity grid for v2: c40.max_aloft threshold for H90 NEW
    print("\n=== H96 v2 sensitivity: c40_max_aloft threshold (drop path disabled) ===")
    print(f"{'max4_thr':>10} {'c40g3_thr':>10} {'TP':>3} {'TN':>3} {'FP':>3} {'FN':>3} {'P':>6} {'R':>6} {'acc':>6}")
    for max4_thr in [3, 4, 5]:
        for c40g3_thr in [0.30, 0.35, 0.40, 0.45, 0.50]:
            def v2_with_thr(p, c, sc, h74, md, a, pthr=0.92, mathr=2, mt=max4_thr, ct=c40g3_thr):
                if p == "FOUNTAIN_3+":
                    pct_ge1 = a.get("pct_ge1", 0) if a else 0
                    c40_pct_ge3 = a.get("c40_pct_ge3", 1) if a else 1
                    c40_max_aloft = a.get("c40_max_aloft", 0) if a else 0
                    if c < 0.55 and pct_ge1 < pthr: return True, "H43+guard"
                    if sc < 0.15 and pct_ge1 < pthr: return True, "H69+guard"
                    if c40_pct_ge3 < ct and c40_max_aloft >= mt: return True, "H90_NEW"
                    if h74["var"] < 0.20 and h74["unique_LR"] <= 1: return True, "H74v4"
                    if md > 10: return True, "H78"
                    return False, "KEPT"
                elif p == "CASCADE_3+":
                    pct_ge3 = a.get("pct_ge3", 0) if a else 0
                    max_aloft = a.get("max_aloft", 0) if a else 0
                    if pct_ge3 < 0.20 and max_aloft >= mathr: return True, "H87+maxA"
                    if h74["var"] < 0.20 and h74["unique_LR"] <= 1: return True, "H74v4"
                    return False, "KEPT"
                elif p.startswith("MIXED_3+"):
                    if sc < 0.10: return True, "H71_REJECT"
                    return False, "KEPT"
                return False, "KEPT"
            r = evaluate(CORRECTED_GT, all_signals, h74_signals, h78, aloft_signals,
                         v2_with_thr, name=f"H96 v2 max4={max4_thr} c40g3<{c40g3_thr}")
            c = r["combined"]
            mark = " <-- PERFECT" if c[0]==17 and c[1]==4 and c[2]==0 and c[3]==0 else ""
            print(f"{max4_thr:>10} {c40g3_thr:>10.2f} {c[0]:>3} {c[1]:>3} {c[2]:>3} {c[3]:>3} {c[4]:>6.3f} {c[5]:>6.3f} {c[6]:>6.3f}{mark}")

    # Cross-validation on 113 manual review pairs
    print("\n=== Cross-validation on 113 manual review pairs (H59 GT) ===")
    with (H1_DATA / "h77_per_pair_eval.csv").open() as f:
        pairs = list(csv.DictReader(f))
    h77_kept_correct = sum(1 for p in pairs if p["h77_kept"] == "True" and p["label"] == "correct")
    h77_kept_wrong = sum(1 for p in pairs if p["h77_kept"] == "True" and p["label"] == "wrong")
    h77_conf_correct = sum(1 for p in pairs if p["h77_conf_or_uncertain"] == "True" and p["label"] == "correct")
    h77_conf_wrong = sum(1 for p in pairs if p["h77_conf_or_uncertain"] == "True" and p["label"] == "wrong")
    total_correct = sum(1 for p in pairs if p["label"] == "correct")
    total_wrong = sum(1 for p in pairs if p["label"] == "wrong")
    h77_p = h77_kept_correct / max(1, h77_kept_correct + h77_kept_wrong)
    h77_r = h77_kept_correct / max(1, total_correct)
    h77_conf_p = h77_conf_correct / max(1, h77_conf_correct + h77_conf_wrong)
    h77_conf_r = h77_conf_correct / max(1, total_correct)
    print(f"  H77 (= H94 v4 for 15 overlap): P={h77_p:.3f} R={h77_r:.3f}  (TP={h77_kept_correct} FP={h77_kept_wrong})")
    print(f"  H77 + (CONF or UNCER):          P={h77_conf_p:.3f} R={h77_conf_r:.3f}  (TP={h77_conf_correct} FP={h77_conf_wrong})")

    # Save summary
    summary = {
        "H96_methodology": "H90 NEW properly integrated (BOTH v4 pct_ge1 AND c40 features); v1=OR, v2=only c40.max>=4, v3=c40g3<0.30, v4=AND with drop>0.20",
        "h90_new_signals": {
            f"{k[0]}_{k[1]}_{k[2]}": {
                "pct_ge1": v.get("pct_ge1"),
                "c00_pct_ge3": v.get("c00_pct_ge3"),
                "c00_max_aloft": v.get("c00_max_aloft"),
                "c40_pct_ge3": v.get("c40_pct_ge3"),
                "c40_max_aloft": v.get("c40_max_aloft"),
                "drop_pct_ge3": v.get("drop_pct_ge3"),
            } for k, v in aloft_signals.items()
            if all_signals.get(k, {}).get("pattern") == "FOUNTAIN_3+"
        },
        "stack_results": {
            r["name"]: {
                "combined": {"TP": r["combined"][0], "TN": r["combined"][1],
                             "FP": r["combined"][2], "FN": r["combined"][3],
                             "P": round(r["combined"][4], 3),
                             "R": round(r["combined"][5], 3),
                             "acc": round(r["combined"][6], 3)},
                "ident": {"TP": r["ident"][0], "TN": r["ident"][1],
                          "FP": r["ident"][2], "FN": r["ident"][3],
                          "P": round(r["ident"][4], 3),
                          "R": round(r["ident"][5], 3),
                          "acc": round(r["ident"][6], 3)},
                "youtu": {"TP": r["youtu"][0], "TN": r["youtu"][1],
                          "FP": r["youtu"][2], "FN": r["youtu"][3],
                          "P": round(r["youtu"][4], 3),
                          "R": round(r["youtu"][5], 3),
                          "acc": round(r["youtu"][6], 3)},
            }
            for r in results
        },
        "operating_point": {
            "name": "H96 v2 (H90 NEW with c40.max_aloft>=4 only, drop path removed)",
            "rules": {
                "FOUNTAIN_3+": "H43+guard (conf<0.55 AND pct_ge1<0.92) OR H69+guard (spec_conc<0.15 AND pct_ge1<0.92) OR H90_NEW_strict (c40g3<0.40 AND c40.max_aloft>=4) OR H74v4 (var<0.20 AND uLR<=1) OR H78 (mean_diff>10)",
                "CASCADE_3+": "H87+max_aloft (pct_ge3<0.20 AND max_aloft>=2) OR H74v4 (var<0.20 AND uLR<=1)",
                "MIXED_3+": "H71 (spec_conc<0.10)"
            },
            "thresholds": {
                "c40_pct_ge3": 0.40,
                "c40_max_aloft": 4,
                "max_aloft_thr": 2,
                "pct_ge1_thr": 0.92,
            }
        }
    }
    with open(f"{H1_DATA}/h96_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {H1_DATA}/h96_summary.json")


if __name__ == "__main__":
    main()
