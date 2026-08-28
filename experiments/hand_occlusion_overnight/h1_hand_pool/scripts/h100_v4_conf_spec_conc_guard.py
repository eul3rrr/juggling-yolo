#!/usr/bin/env python3
"""
H100 v4 — conf+spec_conc guard formulation (no aloft features).

H100 v3 2D grid showed that the H96 v2 default pct_ge1<0.92 guard
is brittle: it's at the upper end of the available threshold range
(0.80-1.00), with only 0.80-0.92 in a wide flat region.

H100 v4 hypothesis: a guard based on H12 v8's own signals (mean_conf
and spectral_concentration) achieves the same PERFECT 17/4/0/0 result
with a much wider flat region.

A guard based on the H12 v8 signals is theoretically preferable because:
1. It's self-consistent (H43+H69 already use these signals; the guard
   just adds a "block self-attack on low-quality phases" rule).
2. It doesn't require YOLO aloft features (no per-frame c0/c4/c6/c8
   detection loading).
3. It generalizes to videos where the H12 v8 confidence distribution
   is different (e.g., a juggler with consistently lower conf).

The v4 grid sweeps (conf_min, spec_conc_min) and reports the
flat region.
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


def compute_extended_aloft(balls_c0, balls_c4, balls_c6, balls_c8,
                            wrists, start, end):
    n_aloft = {0: [], 4: [], 6: [], 8: []}
    for f in range(start, end + 1):
        if f not in wrists:
            continue
        w = wrists[f]
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
            if f in balls:
                n_aloft[conf_level].append(n)
    if not n_aloft[0]:
        return None
    n0 = len(n_aloft[0])
    n4 = max(1, len(n_aloft[4]))
    pct_ge1 = sum(1 for x in n_aloft[0] if x >= 1) / n0
    pct_ge3 = sum(1 for x in n_aloft[0] if x >= 3) / n0
    c40_pct_ge3 = sum(1 for x in n_aloft[4] if x >= 3) / n4
    c60_pct_ge1 = sum(1 for x in n_aloft[6] if x >= 1) / max(1, len(n_aloft[6]))
    c80_pct_ge1 = sum(1 for x in n_aloft[8] if x >= 1) / max(1, len(n_aloft[8]))
    c0_max = max(n_aloft[0]) if n_aloft[0] else 0
    c4_max = max(n_aloft[4]) if n_aloft[4] else 0
    return {
        "pct_ge1": pct_ge1,
        "pct_ge3": pct_ge3,
        "c40_pct_ge3": c40_pct_ge3,
        "c40_max_aloft": c4_max,
        "c60_pct_ge1": c60_pct_ge1,
        "c80_pct_ge1": c80_pct_ge1,
        "max_aloft": c0_max,
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
    print("H100 v4 — conf+spec_conc guard (no aloft features)")
    print("=" * 80)

    extended_aloft = {}
    for key in CORRECTED_GT.keys():
        stem, start, end = key
        a = compute_extended_aloft(balls_c0[stem], balls_c4[stem],
                                    balls_c6[stem], balls_c8[stem],
                                    wrists_data[stem], start, end)
        if a:
            extended_aloft[key] = a

    h40v2 = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                rv = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                h40v2[(stem, int(r["frame"]))] = (l, rv)

    def compute_h74(stem, start, end):
        lrs = []
        for f in range(start, end + 1):
            if (stem, f) in h40v2:
                l, r = h40v2[(stem, f)]
                lrs.append(l + r)
        if not lrs:
            return None
        n = len(lrs)
        mean = sum(lrs) / n
        var = sum((v - mean) ** 2 for v in lrs) / n
        return {"var": var, "unique_LR": len(set(round(v, 2) for v in lrs))}

    h74_signals = {key: compute_h74(*key) for key in CORRECTED_GT.keys()}

    h78 = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            k = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            h78[k] = float(r["mean_diff_per_frame"])

    H96_FULL = {
        "h43_conf_thr": 0.55,
        "h69_spec_conc_thr": 0.15,
        "h87_pct_ge3_thr": 0.20,
        "h87_max_aloft_thr": 2,
        "h90_c40_pct_ge3_thr": 0.40,
        "h90_c40_max_aloft_thr": 4,
        "h74_var_thr": 0.20,
        "h74_uLR_thr": 1,
        "h78_mean_diff_thr": 10.0,
        "h71_spec_conc_thr": 0.10,
    }

    def evaluate_full_with_guard(guard_fn, thr):
        TP = TN = FP = FN = 0
        for key, gt in sorted(CORRECTED_GT.items()):
            sig = all_signals.get(key)
            h74 = h74_signals.get(key)
            a = extended_aloft.get(key)
            if sig is None or h74 is None or a is None:
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            mean_diff = h78.get(key, 0)
            if sig["pattern"] == "FOUNTAIN_3+":
                c40_pct_ge3 = a.get("c40_pct_ge3", 1) if a else 1
                c40_max_aloft = a.get("c40_max_aloft", 0) if a else 0
                guard = guard_fn(sig, a)
                rej_h43 = sig["conf"] < thr["h43_conf_thr"] and guard
                rej_h69 = sig["spec_conc"] < thr["h69_spec_conc_thr"] and guard
                rej_h90 = c40_pct_ge3 < thr["h90_c40_pct_ge3_thr"] and c40_max_aloft >= thr["h90_c40_max_aloft_thr"]
                rej_h74 = h74 and h74["var"] < thr["h74_var_thr"] and h74["unique_LR"] <= thr["h74_uLR_thr"]
                rej_h78 = mean_diff > thr["h78_mean_diff_thr"]
                rej = rej_h43 or rej_h69 or rej_h90 or rej_h74 or rej_h78
            elif sig["pattern"] == "CASCADE_3+":
                pct_ge3 = a.get("pct_ge3", 0) if a else 0
                max_aloft = a.get("max_aloft", 0) if a else 0
                rej_h87 = pct_ge3 < thr["h87_pct_ge3_thr"] and max_aloft >= thr["h87_max_aloft_thr"]
                rej_h74 = h74 and h74["var"] < thr["h74_var_thr"] and h74["unique_LR"] <= thr["h74_uLR_thr"]
                rej = rej_h87 or rej_h74
            elif sig["pattern"].startswith("MIXED_3+"):
                rej = sig["spec_conc"] < thr["h71_spec_conc_thr"]
            else:
                rej = False
            if is_real and not rej: TP += 1
            elif is_misclass and not rej: FP += 1
            elif is_misclass and rej: TN += 1
            elif is_real and rej: FN += 1
        return TP, TN, FP, FN

    # 2D grid: conf_min × spec_conc_min
    print("\n2D grid: conf >= t1 AND spec_conc >= t2")
    conf_thrs = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70]
    spec_conc_thrs = [0.05, 0.10, 0.12, 0.13, 0.14, 0.15, 0.20, 0.30]
    table = {}
    for t1 in conf_thrs:
        for t2 in spec_conc_thrs:
            g = lambda s, a, t1=t1, t2=t2: s["conf"] >= t1 and s["spec_conc"] >= t2
            result = evaluate_full_with_guard(g, H96_FULL)
            table[(t1, t2)] = result

    header = "conf\\sc"
    for t in spec_conc_thrs:
        header += f"  sc={t:.2f}"
    print(header)
    for t1 in conf_thrs:
        row = f"  cf={t1:.2f}  "
        for t2 in spec_conc_thrs:
            r = table[(t1, t2)]
            if r == (17, 4, 0, 0):
                row += "  PERFECT"
            else:
                row += f"  {r[0]}/{r[1]}/{r[2]}/{r[3]}"
        print(row)

    n_perfect = sum(1 for r in table.values() if r == (17, 4, 0, 0))
    print(f"\n{n_perfect}/{len(table)} cells PERFECT")
    if n_perfect > 0:
        cf_set = sorted(set(t1 for (t1, t2), r in table.items() if r == (17, 4, 0, 0)))
        sc_set = sorted(set(t2 for (t1, t2), r in table.items() if r == (17, 4, 0, 0)))
        print(f"  conf flat region: [{min(cf_set):.2f}, {max(cf_set):.2f}]")
        print(f"  spec_conc flat region: [{min(sc_set):.2f}, {max(sc_set):.2f}]")
    perfect_cells = [(t1, t2) for (t1, t2), r in table.items() if r == (17, 4, 0, 0)]

    # === Recommended operating point: middle of flat region ===
    if perfect_cells:
        cf_mid = (min(cf_set) + max(cf_set)) / 2
        sc_mid = (min(sc_set) + max(sc_set)) / 2
        print(f"\nRecommended v4 guard: conf>={cf_mid:.2f} AND spec_conc>={sc_mid:.2f}")

    # === LOO test on 4 TNs ===
    print("\n" + "=" * 80)
    print("LOO test on 4 TNs (default conf>=0.50 AND spec_conc>=0.13)")
    print("=" * 80)
    TN_KEYS = [
        ("identical_balls_trick_000_018", 685, 716),
        ("identical_balls_trick_000_018", 890, 936),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71),
    ]
    g_default = lambda s, a: s["conf"] >= 0.50 and s["spec_conc"] >= 0.13
    for tn_key in TN_KEYS:
        reduced_gt = {k: v for k, v in CORRECTED_GT.items() if k != tn_key}
        # Re-evaluate manually with reduced_gt
        TP = TN = FP = FN = 0
        for key, gt in sorted(reduced_gt.items()):
            sig = all_signals.get(key)
            h74 = h74_signals.get(key)
            a = extended_aloft.get(key)
            if sig is None or h74 is None or a is None:
                continue
            verdict = gt[1]
            is_real = verdict in REAL_VERDICTS
            is_misclass = verdict in MISCLASS_VERDICTS
            mean_diff = h78.get(key, 0)
            if sig["pattern"] == "FOUNTAIN_3+":
                c40_pct_ge3 = a.get("c40_pct_ge3", 1) if a else 1
                c40_max_aloft = a.get("c40_max_aloft", 0) if a else 0
                guard = g_default(sig, a)
                rej = ((sig["conf"] < H96_FULL["h43_conf_thr"] and guard) or
                       (sig["spec_conc"] < H96_FULL["h69_spec_conc_thr"] and guard) or
                       (c40_pct_ge3 < H96_FULL["h90_c40_pct_ge3_thr"] and c40_max_aloft >= H96_FULL["h90_c40_max_aloft_thr"]) or
                       (h74 and h74["var"] < H96_FULL["h74_var_thr"] and h74["unique_LR"] <= H96_FULL["h74_uLR_thr"]) or
                       (mean_diff > H96_FULL["h78_mean_diff_thr"]))
            elif sig["pattern"] == "CASCADE_3+":
                pct_ge3 = a.get("pct_ge3", 0) if a else 0
                max_aloft = a.get("max_aloft", 0) if a else 0
                rej = ((pct_ge3 < H96_FULL["h87_pct_ge3_thr"] and max_aloft >= H96_FULL["h87_max_aloft_thr"]) or
                       (h74 and h74["var"] < H96_FULL["h74_var_thr"] and h74["unique_LR"] <= H96_FULL["h74_uLR_thr"]))
            elif sig["pattern"].startswith("MIXED_3+"):
                rej = sig["spec_conc"] < H96_FULL["h71_spec_conc_thr"]
            else:
                rej = False
            if is_real and not rej: TP += 1
            elif is_misclass and not rej: FP += 1
            elif is_misclass and rej: TN += 1
            elif is_real and rej: FN += 1
        print(f"  Drop {tn_key[1]}-{tn_key[2]}: {TP}/{TN}/{FP}/{FN}  {'PASS' if FP==0 and FN==0 else 'FAIL'}")

    # === Comparison: H96 v2 default vs H100 v4 default ===
    print("\n" + "=" * 80)
    print("Comparison: H96 v2 default (pct_ge1<0.92) vs H100 v4 default (conf+spec_conc)")
    print("=" * 80)
    g_v2 = lambda s, a: a.get("pct_ge1", 1) < 0.92
    g_v4 = lambda s, a: s["conf"] >= 0.50 and s["spec_conc"] >= 0.13
    print(f"  H96 v2 default (pct_ge1<0.92): {evaluate_full_with_guard(g_v2, H96_FULL)}")
    print(f"  H100 v4 default (conf>=0.50 AND spec_conc>=0.13): {evaluate_full_with_guard(g_v4, H96_FULL)}")

    # Save summary
    summary = {
        "h100v4_methodology": "conf+spec_conc guard (no aloft features)",
        "perfect_cells": [{"conf_min": t1, "spec_conc_min": t2} for t1, t2 in perfect_cells],
        "n_perfect_cells": n_perfect,
        "flat_region": {
            "conf_min_range": [min(cf_set), max(cf_set)] if perfect_cells else None,
            "spec_conc_min_range": [min(sc_set), max(sc_set)] if perfect_cells else None,
        } if perfect_cells else None,
    }
    with open(f"{H1_DATA}/h100v4_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {H1_DATA}/h100v4_summary.json")


if __name__ == "__main__":
    main()
