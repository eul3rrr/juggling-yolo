#!/usr/bin/env python3
"""
H86 — H83 v3 (per-hand H74v3) vs H82 v1 (H74v2) on all 21 H70 phases.

Hypothesis: H74v3 (var<0.20 AND (unique_L>1 OR unique_R>1)) is a
better H74 refinement than H74v2 (var<0.20 AND unique_LR<=2) because
it can preserve f=267-298 (5-ball juggler with both hands at 1.0
continuously) while still catching static holds.

Result: H74v3 = H74v2 numerically on the H70 sample. Both stacks
achieve 90.5% accuracy on all 21 phases. The 1 FN fix (f=267-298
JUGGLING KEEPS) is offset by 1 new FN (f=375-410 JUGGLING REJECTS).

H86 also documents the 5-ball saturation finding and suggests
alternative signals (ball-detection based, periodicity based).
"""
from __future__ import annotations

import csv
import json
import glob
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_h40v2() -> dict:
    out = {}
    for fpath in glob.glob(f"{H1_DATA}/h40v2_continuous_*.csv"):
        stem = Path(fpath).stem.replace("h70_phases_", "").replace("h40v2_continuous_", "")
        with open(fpath) as fh:
            for r in csv.DictReader(fh):
                l = float(r["L40v2"]) if r["L40v2"] not in ("", "None") else 0
                r_v = float(r["R40v2"]) if r["R40v2"] not in ("", "None") else 0
                out[(stem, int(r["frame"]))] = (l, r_v)
    return out


def load_h70_phases() -> dict:
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


def load_h78() -> dict:
    out = {}
    with open(f"{H1_DATA}/h78v2_wrist_distance_per_phase.csv") as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = float(r["mean_diff_per_frame"])
    return out


# 21-phase ground truth (includes the 2 phases NOT in h70_phases)
GROUND_TRUTH = {
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

# Manual signal inputs for the 2 phases NOT in h70_phases
EXTRA_SIGNALS = {
    ("identical_balls_trick_000_018", 733, 766): {
        "pattern": "CASCADE_3+",
        "n_frames": 34,
        "conf": 0.620,  # H73 finding
        "spec_conc": 0.165,
    },
    ("identical_balls_trick_000_018", 1029, 1049): {
        "pattern": "FOUNTAIN_3+",
        "n_frames": 21,
        "conf": 0.463,  # from H65 (below H43 threshold)
        "spec_conc": 0.140,
    },
}


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
        "mean_L": sum(Ls) / n,
        "mean_R": sum(Rs) / n,
    }


def h82_decision(pattern, conf, spec_conc, lr_var, unique_lr, mean_diff):
    """H82 v1: H74v2 = var<0.20 AND unique_LR<=2"""
    if pattern == "FOUNTAIN_3+":
        if conf < 0.55:
            return True, "H43"
        if spec_conc < 0.15:
            return True, "H69"
        if lr_var < 0.20 and unique_lr <= 2:
            return True, "H74v2"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if lr_var < 0.20 and unique_lr <= 2:
            return True, "H74v2"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def h83_decision(pattern, conf, spec_conc, lr_var, unique_L, unique_R, mean_diff):
    """H83 v3: H74v3 = var<0.20 AND (unique_L>1 OR unique_R>1)"""
    if pattern == "FOUNTAIN_3+":
        if conf < 0.55:
            return True, "H43"
        if spec_conc < 0.15:
            return True, "H69"
        if lr_var < 0.20 and (unique_L > 1 or unique_R > 1):
            return True, "H74v3"
        if mean_diff > 10:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if lr_var < 0.20 and (unique_L > 1 or unique_R > 1):
            return True, "H74v3"
        return False, "KEPT"
    elif pattern.startswith("MIXED_3+"):
        if spec_conc < 0.10:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def main():
    h40v2 = load_h40v2()
    h70 = load_h70_phases()
    h78 = load_h78()
    all_signals = {**h70, **EXTRA_SIGNALS}

    print("=" * 80)
    print("H86 — H83 v3 vs H82 v1 on all 21 H70 phases")
    print("=" * 80)

    # Per-phase comparison
    print(f"\nPer-phase H82 v1 vs H83 v3 (all 21 phases):")
    print(f"{'phase':<35} {'verdict':<22} {'var':>6} {'uLR':>3} {'uL':>3} {'uR':>3} {'H82v1':<12} {'H83v3':<12}")

    diff_count = 0
    for key in sorted(GROUND_TRUTH.keys()):
        stem, start, end = key
        sig = all_signals.get(key)
        if sig is None:
            print(f"  {key}: NO_SIGNAL")
            continue
        h74 = compute_h74_signals(h40v2, stem, start, end)
        if h74 is None:
            print(f"  {key}: NO_H40V2")
            continue
        gt = GROUND_TRUTH[key]
        h82_rej, h82_reason = h82_decision(
            sig["pattern"], sig["conf"], sig["spec_conc"],
            h74["var"], h74["unique_LR"], h78.get(key, 0))
        h83_rej, h83_reason = h83_decision(
            sig["pattern"], sig["conf"], sig["spec_conc"],
            h74["var"], h74["unique_L"], h74["unique_R"], h78.get(key, 0))
        diff = "DIFF" if h82_rej != h83_rej else ""
        if h82_rej != h83_rej:
            diff_count += 1
        label = f"{stem[:5]} f={start}-{end}"
        print(f"{label:<35} {gt[1]:<22} {h74['var']:>6.3f} {h74['unique_LR']:>3} {h74['unique_L']:>3} {h74['unique_R']:>3} {h82_reason:<12} {h83_reason:<12} {diff}")
    print(f"\nPhase-level differences: {diff_count}")

    # End-to-end comparison
    print(f"\n=== End-to-end stack comparison (all 21 phases) ===")
    for name, dec_fn in [
        ("H82 v1 (H75v2 + H78 mean_diff>10)", h82_decision),
        ("H83 v3 (H74v3) + H78 mean_diff>10", h83_decision),
    ]:
        TP = TN = FP = FN = 0
        for key, gt in GROUND_TRUTH.items():
            sig = all_signals.get(key)
            if sig is None:
                continue
            h74 = compute_h74_signals(h40v2, *key)
            if h74 is None:
                continue
            if dec_fn.__name__ == "h82_decision":
                rej, _ = dec_fn(sig["pattern"], sig["conf"], sig["spec_conc"],
                                h74["var"], h74["unique_LR"], h78.get(key, 0))
            else:
                rej, _ = dec_fn(sig["pattern"], sig["conf"], sig["spec_conc"],
                                h74["var"], h74["unique_L"], h74["unique_R"], h78.get(key, 0))
            keep = not rej
            is_real = gt[1] in ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
            is_misclass = gt[1] in ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                                    "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")
            if is_real and keep: TP += 1
            elif is_misclass and not keep: TN += 1
            elif is_misclass and keep: FP += 1
            elif is_real and not keep: FN += 1
        p = TP / max(1, TP+FP)
        r = TP / max(1, TP+FN)
        acc = (TP+TN) / max(1, TP+TN+FP+FN)
        fpr = FP / max(1, FP+TN)
        print(f"  {name}: TP={TP} TN={TN} FP={FP} FN={FN}  P={p:.3f}  R={r:.3f}  FPR={fpr:.3f}  acc={acc:.3f}")

    # Save h74 signals for each phase
    signals_summary = {}
    for key in sorted(GROUND_TRUTH.keys()):
        stem, start, end = key
        h74 = compute_h74_signals(h40v2, stem, start, end)
        if h74 is None:
            continue
        signals_summary[f"{stem}_{start}_{end}"] = {
            "pattern": all_signals[key]["pattern"],
            "gt_verdict": GROUND_TRUTH[key][1],
            **h74,
        }
    with open(f"{H1_DATA}/h86_h74_signals.json", "w") as fh:
        json.dump(signals_summary, fh, indent=2)
    print(f"\nWrote {H1_DATA / 'h86_h74_signals.json'}")


if __name__ == "__main__":
    main()
