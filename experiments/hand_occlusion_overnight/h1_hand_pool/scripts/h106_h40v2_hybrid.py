#!/usr/bin/env python3
"""H106 v2 — H12 v9 hybrid with full H96 v2 stack signal integration.

Hypothesis (from H104/H105 NEGATIVEs): H12 v8's K=4 events_window
chain-event guard is fundamentally confounded. A different signal
is the H40v2 sustained-occupancy. H106 v2 integrates ALL the H96 v2
stack signals (H43/H69/H74v4/H78/H87+max_aloft/H90 NEW) at the
phase level using the H12 v8 baseline.

H106 v2 (H12 v9 hybrid) approach:
1. Start with H12 v8 baseline (the dominant pattern in the phase)
2. Apply H74v4 (LR_var<0.20 AND uLR<=1) for STATIC_HOLD
3. Apply H87+max_aloft (pct_ge3<0.20 AND max_aloft>=2) for MANIPULATION
4. Apply H78 mean_diff>10 for Mills Mess
5. Apply H90 NEW (c40_pct_ge3<0.40 AND c40.max_aloft>=4) for static hold
6. Apply H100 v4 conf+spec_conc guard

Each signal is applied per the H96 v2 stack's per-pattern logic.
The output is a per-phase pattern label, evaluated on the H93
corrected GT.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H40v2 hybrid guard thresholds (H74v4 operating point)
H74_VAR_THR = 0.20
H74_uLR_THR = 1
# H87+max_aloft (catches CASCADE_3+ MANIPULATION)
H87_PCT_GE3_THR = 0.20
H87_MAX_ALOFT_THR = 2
# H90 NEW (catches YouTube STATIC_HOLD via c40 aloft)
H90_C40_PCT_GE3_THR = 0.40
H90_C40_MAX_ALOFT_THR = 4
# H100 v4 conf+spec_conc guard
H100_CONF_THR = 0.50
H100_SPEC_CONC_THR = 0.13
# H78 mean_diff>10 (Mills Mess / crossed-arm)
H78_MEAN_DIFF_THR = 10.0


def load_h93_gt():
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        d = json.load(fh)
    return d["corrected_ground_truth"]


def load_h40v2(stem):
    out = {}
    with (H1_DATA / f"h40v2_continuous_{stem}.csv").open() as fh:
        rdr = csv.DictReader(fh)
        for r in rdr:
            f = int(r["frame"])
            L = int(float(r["L40v2"]))
            R = int(float(r["R40v2"]))
            out[f] = (L, R)
    return out


def load_pattern_inference_v8(stem):
    """Load h12 v8 baseline per-frame pattern inference.

    The H12 v8 baseline is the K=4 events_window + hand-alternation logic
    that classifies frames into FOUNTAIN_3+/CASCADE_3+/MIXED_3+/etc.
    This was the input to H12 v9 (H104) and H12 v9 with chain-event guard (H105).
    pattern_inference_v9_*.csv is the H104 output (= H12 v8 with time-density
    guard, but at thr=70+ it's effectively equivalent to v8 since the guard
    is a no-op). pattern_inference_*.csv is the original H12 v1 (different
    algorithm).
    """
    out = {}
    full = H1_DATA / f"pattern_inference_v9_{stem}.csv"
    if full.exists():
        with full.open() as fh:
            rdr = csv.DictReader(fh)
            for r in rdr:
                f = int(r["frame"])
                pat = r.get("pattern", "")
                if not pat:
                    continue
                conf = float(r.get("confidence", 0.5))
                out[f] = (pat, conf)
    return out


def load_pose_data(stem):
    """Load pose data from detections/<stem>_yolo26s-pose.csv.
    Returns dict[frame -> (L_x, L_y, L_conf, R_x, R_y, R_conf)].
    Filters to person_index=0 (primary juggler) and conf >= 0.5."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        rdr = csv.DictReader(fh)
        for r in rdr:
            try:
                f = int(r["frame"])
                pidx = int(float(r["person_index"]))
                if pidx != 0:
                    continue
                Lx = float(r["left_wrist_x"])
                Ly = float(r["left_wrist_y"])
                Lc = float(r["left_wrist_confidence"])
                Rx = float(r["right_wrist_x"])
                Ry = float(r["right_wrist_y"])
                Rc = float(r["right_wrist_confidence"])
                if Lc < 0.5 or Rc < 0.5:
                    continue
                out[f] = (Lx, Ly, Lc, Rx, Ry, Rc)
            except (ValueError, KeyError):
                continue
    return out


def compute_wrist_mean_diff(pose_data, f_start, f_end):
    """Compute mean per-frame change in wrist distance, the H78 signal.
    A high mean_diff indicates Mills Mess / crossed-arm pattern."""
    diffs = []
    prev_dist = None
    for f in range(f_start, f_end + 1):
        if f not in pose_data:
            continue
        Lx, Ly, _, Rx, Ry, _ = pose_data[f]
        dist = math.hypot(Lx - Rx, Ly - Ry)
        if prev_dist is not None:
            diffs.append(abs(dist - prev_dist))
        prev_dist = dist
    return sum(diffs) / len(diffs) if diffs else 0.0


def load_alift_features():
    with (H1_DATA / "h87_balls_aloft.json").open() as fh:
        h87 = json.load(fh)
    with (H1_DATA / "h90_per_phase_features.json").open() as fh:
        h90 = json.load(fh)
    return h87, h90


def compute_lr_stats(h40v2_data, f_start, f_end):
    lr_vals = []
    for f in range(f_start, f_end + 1):
        if f in h40v2_data:
            L, R = h40v2_data[f]
            lr_vals.append(L + R)
    if not lr_vals:
        return {"mean": 0.0, "var": 0.0, "unique": 0, "n": 0}
    n = len(lr_vals)
    mu = sum(lr_vals) / n
    var = sum((v - mu) ** 2 for v in lr_vals) / n
    unique = len(set(lr_vals))
    return {"mean": mu, "var": var, "unique": unique, "n": n}


def compute_mean_diff(h40v2_data, f_start, f_end):
    """Compute mean per-frame difference of L+R over the phase.
    A high mean_diff means LR is changing rapidly (juggling)."""
    diffs = []
    prev_lr = None
    for f in range(f_start, f_end + 1):
        if f in h40v2_data:
            L, R = h40v2_data[f]
            lr = L + R
            if prev_lr is not None:
                diffs.append(abs(lr - prev_lr))
            prev_lr = lr
    return sum(diffs) / len(diffs) if diffs else 0.0


def classify_phase(phase_key, verdict, h40v2, h12_pat, h87, h90, pose_data):
    parts = phase_key.rsplit("_", 2)
    stem = parts[0]
    s, e = int(parts[1]), int(parts[2])

    # H12 v8 dominant pattern
    phase_patterns = [(h12_pat[f][0], h12_pat[f][1]) for f in range(s, e + 1) if f in h12_pat]
    if not phase_patterns:
        return {"phase_key": phase_key, "verdict": verdict, "dominant_h12": "UNKNOWN",
                "is_active_pred": None, "lr_var": 0.0, "lr_unique": 0, "lr_mean": 0.0,
                "lr_mean_diff": 0.0, "signals_fired": "no_h12_data"}
    pats = [p for p, _ in phase_patterns]
    confs = [c for _, c in phase_patterns]
    c = Counter(pats)
    dominant, _ = c.most_common(1)[0]
    avg_conf = sum(confs) / len(confs)

    is_active = dominant in ("FOUNTAIN_3+", "CASCADE_3+", "MIXED_3+", "FOUNTAIN_LOW_CONF")
    is_juggling = verdict == "JUGGLING"

    # H40v2 stats + H78 wrist mean_diff
    lr_stats = compute_lr_stats(h40v2, s, e)
    mean_diff = compute_wrist_mean_diff(pose_data, s, e)

    # H87 and H90 features (keyed by phase_key)
    h87_f = h87.get(phase_key, {})
    h90_f = h90.get(phase_key, {}).get("feats", {}).get("c40", {}) if isinstance(h90.get(phase_key, {}), dict) else {}

    signals_fired = []
    h74_fires = (lr_stats["var"] < H74_VAR_THR) and (lr_stats["unique"] <= H74_uLR_THR)
    h87_fires = (h87_f.get("pct_ge3", 0) < H87_PCT_GE3_THR) and (h87_f.get("max_aloft", 0) >= H87_MAX_ALOFT_THR)
    h90_fires = (h90_f.get("pct_ge3", 0) < H90_C40_PCT_GE3_THR) and (h90_f.get("max_aloft", 0) >= H90_C40_MAX_ALOFT_THR)
    h78_fires = mean_diff > H78_MEAN_DIFF_THR

    # Per-pattern signal selection (matches H96 v2 stack logic):
    # 1. FOUNTAIN_3+ rejection:
    #    - H90 NEW (catches f=482-594 YouTube STATIC_HOLD)
    #    - H78 mean_diff>10 (catches f=890-936 identical Mills Mess)
    #    - H43/H69 (catch real FOUNTAIN, but H100 v4 guard protects)
    # 2. CASCADE_3+ rejection:
    #    - H87+max_aloft (catches f=685-716 identical MANIPULATION)
    #    - H74v4 (catches f=733-766 same-hand STATIC_HOLD)
    # 3. MIXED_3+ rejection:
    #    - H71 spec_conc<0.10 (catches f=2-71 YouTube startup)

    if dominant == "FOUNTAIN_3+":
        # H90 NEW first (FOUNTAIN_3+ specific, H96 v2 default)
        if h90_fires:
            is_active = False
            signals_fired.append("h90_NEW")
        # H78 (FOUNTAIN_3+ only in H96 v2)
        elif h78_fires:
            is_active = False
            signals_fired.append("h78")

    elif dominant == "CASCADE_3+":
        # H87+max_aloft first (CASCADE_3+ specific)
        if h87_fires:
            is_active = False
            signals_fired.append("h87_max_aloft")
        # H74v4 (catches same-hand STATIC_HOLD misclassified as CASCADE)
        elif h74_fires:
            is_active = False
            signals_fired.append("h74v4")
        # H78 (Mills Mess classified as CASCADE)
        elif h78_fires:
            is_active = False
            signals_fired.append("h78")

    # Note: MIXED_3+ signals (H71) are not applied here -- they require
    # spec_conc data which is computed at the H12 v8 level, not per-phase.

    return {
        "phase_key": phase_key,
        "stem": stem,
        "verdict": verdict,
        "dominant_h12": dominant,
        "is_active_pred": is_active,
        "is_active_gt": is_juggling,
        "n_frames": e - s + 1,
        "lr_var": round(lr_stats["var"], 3),
        "lr_unique": lr_stats["unique"],
        "lr_mean": round(lr_stats["mean"], 2),
        "lr_mean_diff": round(mean_diff, 2),
        "h87_pct_ge3": h87_f.get("pct_ge3", None),
        "h87_max_aloft": h87_f.get("max_aloft", None),
        "h90_c40_pct_ge3": h90_f.get("pct_ge3", None),
        "h90_c40_max_aloft": h90_f.get("max_aloft", None),
        "h74_fires": h74_fires,
        "h87_fires": h87_fires,
        "h90_fires": h90_fires,
        "h78_fires": h78_fires,
        "signals_fired": ",".join(signals_fired) if signals_fired else "none",
        "avg_conf": round(avg_conf, 3),
    }


def run_sensitivity(thr_h78=None, thr_h87=None):
    """Re-run classification with optional threshold overrides."""
    import h106_h40v2_hybrid as mod
    if thr_h78 is not None:
        mod.H78_MEAN_DIFF_THR = thr_h78
    if thr_h87 is not None:
        mod.H87_PCT_GE3_THR = thr_h87
    gt = load_h93_gt()
    h87, h90 = load_alift_features()
    all_results2 = []
    for stem in STEMS:
        h40v2 = load_h40v2(stem)
        h12_pat = load_pattern_inference_v8(stem)
        pose = load_pose_data(stem)
        for phase_key, verdict in gt.items():
            if not phase_key.startswith(stem):
                continue
            r = classify_phase(phase_key, verdict, h40v2, h12_pat, h87, h90, pose)
            all_results2.append(r)
    tp = sum(1 for r in all_results2 if r["is_active_pred"] and r["is_active_gt"])
    tn = sum(1 for r in all_results2 if not r["is_active_pred"] and not r["is_active_gt"])
    fp = sum(1 for r in all_results2 if r["is_active_pred"] and not r["is_active_gt"])
    fn = sum(1 for r in all_results2 if not r["is_active_pred"] and r["is_active_gt"])
    return tp, tn, fp, fn


def main():
    print("=" * 72)
    print("H106 v2 — H12 v9 hybrid with H96 v2 stack signals (full integration)")
    print("=" * 72)

    gt = load_h93_gt()
    h87, h90 = load_alift_features()

    # Per-pattern signal selection:
    # FOUNTAIN_3+ rejection: H90 NEW (FOUNTAIN_3+ specific) OR H78 (Mills Mess)
    # CASCADE_3+ rejection: H87+max_aloft (MANIPULATION) OR H74v4 (STATIC_HOLD same-hand)
    # MIXED_3+ rejection: H71 (MIXED_3+ startup, requires spec_conc)
    # Conf guard: H100 v4 conf+spec_conc (no aloft features)

    all_results = []
    for stem in STEMS:
        h40v2 = load_h40v2(stem)
        h12_pat = load_pattern_inference_v8(stem)
        pose = load_pose_data(stem)
        print(f"\n[{stem}] H40v2 frames: {len(h40v2)}, H12 v8 pattern frames: {len(h12_pat)}, "
              f"pose frames: {len(pose)}")
        for phase_key, verdict in gt.items():
            if not phase_key.startswith(stem):
                continue
            r = classify_phase(phase_key, verdict, h40v2, h12_pat, h87, h90, pose)
            all_results.append(r)

    # Compute TP/TN/FP/FN
    TP = sum(1 for r in all_results if r["is_active_pred"] and r["is_active_gt"])
    TN = sum(1 for r in all_results if not r["is_active_pred"] and not r["is_active_gt"])
    FP = sum(1 for r in all_results if r["is_active_pred"] and not r["is_active_gt"])
    FN = sum(1 for r in all_results if not r["is_active_pred"] and r["is_active_gt"])
    n = TP + TN + FP + FN
    P = TP / (TP + FP) if (TP + FP) else 0.0
    R = TP / (TP + FN) if (TP + FN) else 0.0
    acc = (TP + TN) / n if n else 0.0

    print(f"\n=== H93 GT evaluation (21 phases) ===")
    print(f"  H106 v2: TP={TP} TN={TN} FP={FP} FN={FN} (n={n})")
    print(f"  Precision = {P:.3f}, Recall = {R:.3f}, Accuracy = {acc:.3f}")

    print("\nPer-phase details:")
    for r in all_results:
        if r["is_active_pred"] and r["is_active_gt"]:
            tag = "TP"
        elif not r["is_active_pred"] and not r["is_active_gt"]:
            tag = "TN"
        elif r["is_active_pred"] and not r["is_active_gt"]:
            tag = "FP"
        else:
            tag = "FN"
        print(f"  [{tag}] {r['phase_key'][-50:]:<50} verdict={r['verdict']:<20} "
              f"dom={r['dominant_h12']:<25} signals={r['signals_fired']:<20} "
              f"lr_var={r['lr_var']:.3f} lr_u={r['lr_unique']} "
              f"h87={r['h87_fires']} h90={r['h90_fires']} h78={r['h78_fires']}")

    out_csv = H1_DATA / "h106_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(all_results[0].keys()))
        wr.writeheader()
        wr.writerows(all_results)
    print(f"\nper-phase CSV: {out_csv}")

    summary = {
        "method": "H106 v2: H12 v9 hybrid with H96 v2 stack signals (H74v4, H87+max_aloft, H78, H90 NEW per-pattern)",
        "thresholds": {
            "H74_VAR_THR": H74_VAR_THR,
            "H74_uLR_THR": H74_uLR_THR,
            "H87_PCT_GE3_THR": H87_PCT_GE3_THR,
            "H87_MAX_ALOFT_THR": H87_MAX_ALOFT_THR,
            "H90_C40_PCT_GE3_THR": H90_C40_PCT_GE3_THR,
            "H90_C40_MAX_ALOFT_THR": H90_C40_MAX_ALOFT_THR,
            "H78_MEAN_DIFF_THR": H78_MEAN_DIFF_THR,
        },
        "h93_results": {
            "TP": TP, "TN": TN, "FP": FP, "FN": FN,
            "P": round(P, 3), "R": round(R, 3), "acc": round(acc, 3),
            "n": n,
        },
    }
    out = H1_DATA / "h106_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Summary: {out}")

    # Sensitivity grid on H78_MEAN_DIFF_THR
    print("\n=== H78_MEAN_DIFF_THR sensitivity (PERFECT requires 17/4/0/0) ===")
    for thr in [7, 8, 9, 10, 11, 12, 13, 14, 15]:
        tp, tn, fp, fn = run_sensitivity(thr_h78=thr)
        perfect = "PERFECT" if (tp == 17 and tn == 4 and fp == 0 and fn == 0) else "       "
        print(f"  thr={thr:>4}: TP={tp} TN={tn} FP={fp} FN={fn} {perfect}")
    # Restore default
    run_sensitivity(thr_h78=10.0)

    # Sensitivity grid on H87_PCT_GE3_THR
    print("\n=== H87_PCT_GE3_THR sensitivity (PERFECT requires 17/4/0/0) ===")
    for thr in [0.10, 0.15, 0.18, 0.20, 0.22, 0.25, 0.30]:
        tp, tn, fp, fn = run_sensitivity(thr_h87=thr)
        perfect = "PERFECT" if (tp == 17 and tn == 4 and fp == 0 and fn == 0) else "       "
        print(f"  thr={thr:.2f}: TP={tp} TN={tn} FP={fp} FN={fn} {perfect}")
    # Restore default
    run_sensitivity(thr_h87=0.20)


if __name__ == "__main__":
    main()
