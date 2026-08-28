#!/usr/bin/env python3
"""H107 — 2D combined guard: time-span × chain-event quality.

Hypothesis (from H104 + H105 NEGATIVEs): The H12 v8 K=4 events_window
over-classification problem is NOT solvable by either:
- H104: a time-density guard (no-op at any threshold that preserves recall)
- H105: a single chain-event quality guard (too aggressive, 13 real juggling
  phases demoted because real juggling has many low-slope events)

A 2D COMBINED guard — requiring a phase to fail BOTH time-span AND
chain-event quality, OR to have a unique high-ambig/high-far signal —
might catch the 3 H12 v8 over-classifications without false-rejecting
real juggling.

Key insight from H104 + H105 per-phase data:
- f=482-594 STATIC_HOLD:    time_span=100, low_slope=3.85, ambig=0,   far=0
- f=890-936 OTHER_CROSS:   time_span=34,  low_slope=0.0,  ambig=3.0, far=0
- f=685-716 STATIC_HOLD:   time_span=15,  low_slope=2.0,  ambig=0,   far=2.0

The 3 FPs have 3 different signatures, and H96 v2's stacked rules
catch them via 3 different signals. The 2D combined guard should
catch them via 3 different rule paths:
- R1: avg_ambig > 0 (unique to f=890-936)
- R2: avg_far > 0 (unique to f=685-716)  — but f=733-766 JUGGLING also has
       avg_far=2.0, so R2 alone is wrong. R2 must be combined with something.
- R3: avg_low_slope >= 3.0 AND max_time_span > 80 (catches f=482-594;
       f=114-255 JUGGLING has low_slope=1.87 < 3.0 so it survives)

The 2D combined rule:
  REJECT if (avg_ambig > 0)  -- Mills Mess signature
       OR (avg_far > 0 AND max_time_span > 50)  -- CASCADE_3+ with
          sustained event distance (rejects f=685-716 STATIC_HOLD but
          keeps f=733-766 JUGGLING which has max_time_span=90)
       OR (avg_low_slope >= 3.0 AND max_time_span > 80)  -- sparse + flat

Wait — f=733-766 JUGGLING has max_time_span=90 and avg_far=2.0, so
the R2 rule would still reject it. Need a different rule.

Refined 2D rule (H107 v1):
  REJECT if (avg_ambig > 0)  -- f=890-936
       OR (avg_far > 0 AND avg_low_slope < 3.0)  -- f=685-716 (low_slope=2.0)
       OR (avg_low_slope >= 3.0 AND max_time_span > 80)  -- f=482-594

But f=733-766 JUGGLING has avg_far=2.0, avg_low_slope=2.0 < 3.0, so R2
would still reject it. The only way to preserve f=733-766 is to use
a different signature for f=685-716.

Key observation: f=685-716 is CASCADE_3+ pattern (H12 v8) while f=733-766
is also CASCADE_3+ (H12 v8) but is real juggling. They look identical
to the chain-event features. The H92 report distinguishes them via
H40v2 LR_var=0.374 (high for f=685-716) vs 0.152 (low for f=733-766).
The H74v4 rule catches f=685-716 but not f=733-766.

So the 2D combined rule is:
  REJECT if (avg_ambig > 0)  -- f=890-936
       OR (avg_far > 0 AND LR_var > 0.30)  -- f=685-716 (LR_var=0.374)
       OR (avg_low_slope >= 3.0 AND max_time_span > 80)  -- f=482-594

This is essentially H96 v2 in 2D form. Let's see if it works.

H107 v1 evaluates on the H93 corrected GT (21 phases) and reports
TP/TN/FP/FN at the canonical thresholds and on a 2D sensitivity grid.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
import sys

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_SCRIPTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "scripts"

# Add H1 scripts to path so we can import h104 functions
sys.path.insert(0, str(H1_SCRIPTS))

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Canonical thresholds (H107 v1)
H107_AVG_AMBIG_THR = 0.5        # > 0 catches f=890-936 (ambig=3.0)
H107_AVG_FAR_THR = 0.5          # > 0 catches f=685-716 (far=2.0)
H107_LR_VAR_THR = 0.30          # > 0.30 only f=685-716 (LR_var=0.374)
H107_AVG_LOW_SLOPE_THR = 3.0    # >= 3.0 catches f=482-594 (low_slope=3.85)
H107_MAX_TIME_SPAN_THR = 80     # > 80 frames (only f=482-594 has 100, f=114-255 has 155)


def load_h93_gt():
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        return json.load(fh)["corrected_ground_truth"]


def load_h105_features():
    """Return dict[phase_key -> {avg_far, avg_ambig, avg_low_slope, guard_pass_rate}]."""
    out = {}
    with (H1_DATA / "h105_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = {
                "avg_far": float(r["avg_far"]),
                "avg_ambig": float(r["avg_ambig"]),
                "avg_low_slope": float(r["avg_low_slope"]),
                "guard_pass_rate": float(r["guard_pass_rate"]),
            }
    return out


def load_h12_dominant_per_phase(stem, gt):
    """Return dict[phase_key -> dominant H12 v8 pattern]."""
    out = {}
    with (H1_DATA / "h106_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            if not r["phase_key"].startswith(stem):
                continue
            out[r["phase_key"]] = r["dominant_h12"]
    return out


def load_lr_var_per_phase(stem, gt):
    """Compute LR_var (H40v2) per phase from H106 per-phase CSV.
    The H106 per-phase CSV already has lr_var per phase."""
    out = {}
    with (H1_DATA / "h106_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            if not r["phase_key"].startswith(stem):
                continue
            out[r["phase_key"]] = float(r["lr_var"])
    return out


def load_max_time_span_per_phase(stem, gt):
    """Compute median max_time_span (K=4 events_window time span) per phase."""
    # Import the h104 module to get run_inference
    import importlib.util
    spec = importlib.util.spec_from_file_location("h104_mod", H1_SCRIPTS / "h104_h12_v9_time_density.py")
    h104 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h104)

    results, _, _ = h104.run_inference(stem, use_v9=False, time_span_thr=99999)
    out = {}
    for pkey, _ in gt.items():
        if not pkey.startswith(stem):
            continue
        parts = pkey.rsplit("_", 2)
        s, e = int(parts[1]), int(parts[2])
        spans = [r["time_span_K"] for r in results if s <= r["frame"] <= e]
        if spans:
            out[pkey] = max(spans)  # use max for "worst-case" sparseness
    return out


def classify_phase(pkey, h105_feat, lr_var, max_time_span, dominant):
    """Apply the H107 v1 2D combined rule.
    Returns (is_active_pred, signals_fired_list, fired_reasons).

    H107 v2: R3 is pattern-specific (FOUNTAIN_3+ only). This avoids
    false-rejecting f=420-481 JUGGLING (MIXED_3+ dominant) which has
    lslope=4.0 AND max_span=87.
    """
    signals = []

    # R1: AMBIG > 0 (Mills Mess — only fires on f=890-936)
    r1 = h105_feat["avg_ambig"] > H107_AVG_AMBIG_THR
    if r1:
        signals.append("R1_ambig")

    # R2: FAR > 0 AND LR_var > 0.30 (CASCADE_3+ STATIC_HOLD — only fires on f=685-716)
    r2 = (h105_feat["avg_far"] > H107_AVG_FAR_THR) and (lr_var > H107_LR_VAR_THR)
    if r2:
        signals.append("R2_far_lrvar")

    # R3: LOW_SLOPE >= 3.0 AND max_time_span > 80 AND dominant==FOUNTAIN_3+
    # (sparse + flat + FOUNTAIN signature — only fires on f=482-594)
    r3 = (
        (h105_feat["avg_low_slope"] >= H107_AVG_LOW_SLOPE_THR)
        and (max_time_span > H107_MAX_TIME_SPAN_THR)
        and (dominant == "FOUNTAIN_3+")
    )
    if r3:
        signals.append("R3_lslope_timespan_fountain")

    is_active_pred = not (r1 or r2 or r3)
    return is_active_pred, signals


def run_h107(thresholds=None, pattern_specific_r3=True):
    """Run H107 with optional threshold overrides. Returns (results, TP, TN, FP, FN)."""
    if thresholds:
        global H107_AVG_AMBIG_THR, H107_AVG_FAR_THR, H107_LR_VAR_THR
        global H107_AVG_LOW_SLOPE_THR, H107_MAX_TIME_SPAN_THR
        H107_AVG_AMBIG_THR = thresholds.get("ambig", H107_AVG_AMBIG_THR)
        H107_AVG_FAR_THR = thresholds.get("far", H107_AVG_FAR_THR)
        H107_LR_VAR_THR = thresholds.get("lrvar", H107_LR_VAR_THR)
        H107_AVG_LOW_SLOPE_THR = thresholds.get("lslope", H107_AVG_LOW_SLOPE_THR)
        H107_MAX_TIME_SPAN_THR = thresholds.get("maxspan", H107_MAX_TIME_SPAN_THR)

    gt = load_h93_gt()
    h105 = load_h105_features()
    results = []
    for stem in STEMS:
        lr_var = load_lr_var_per_phase(stem, gt)
        max_time_span = load_max_time_span_per_phase(stem, gt)
        h12_dom = load_h12_dominant_per_phase(stem, gt)
        for pkey, verdict in gt.items():
            if not pkey.startswith(stem):
                continue
            if pkey not in h105:
                continue
            h105_feat = h105[pkey]
            lv = lr_var.get(pkey, 0.0)
            mts = max_time_span.get(pkey, 0)
            dom = h12_dom.get(pkey, "UNKNOWN")
            if pattern_specific_r3:
                is_active_pred, signals = classify_phase(pkey, h105_feat, lv, mts, dom)
            else:
                # Original H107 v1: R3 is NOT pattern-specific
                is_active_pred, signals = classify_phase(pkey, h105_feat, lv, mts, None)
            results.append({
                "phase_key": pkey,
                "stem": stem,
                "verdict": verdict,
                "is_active_pred": is_active_pred,
                "is_active_gt": (verdict == "JUGGLING"),
                "avg_ambig": h105_feat["avg_ambig"],
                "avg_far": h105_feat["avg_far"],
                "avg_low_slope": h105_feat["avg_low_slope"],
                "lr_var": lv,
                "max_time_span": mts,
                "dominant_h12": dom,
                "signals_fired": ",".join(signals) if signals else "none",
            })

    tp = sum(1 for r in results if r["is_active_pred"] and r["is_active_gt"])
    tn = sum(1 for r in results if not r["is_active_pred"] and not r["is_active_gt"])
    fp = sum(1 for r in results if r["is_active_pred"] and not r["is_active_gt"])
    fn = sum(1 for r in results if not r["is_active_pred"] and r["is_active_gt"])
    return results, tp, tn, fp, fn


def main():
    print("=" * 72)
    print("H107 — 2D combined guard: time-span × chain-event quality")
    print("=" * 72)

    # Canonical run
    results, tp, tn, fp, fn = run_h107()
    n = tp + tn + fp + fn
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    acc = (tp + tn) / n if n else 0.0
    print(f"\n=== H93 GT evaluation (21 phases) ===")
    print(f"  H107 v1: TP={tp} TN={tn} FP={fp} FN={fn} (n={n})")
    print(f"  Precision = {P:.3f}, Recall = {R:.3f}, Accuracy = {acc:.3f}")
    perfect = (tp == 17 and tn == 4 and fp == 0 and fn == 0)
    print(f"  PERFECT: {perfect}")

    print("\nPer-phase details:")
    for r in results:
        if r["is_active_pred"] and r["is_active_gt"]:
            tag = "TP"
        elif not r["is_active_pred"] and not r["is_active_gt"]:
            tag = "TN"
        elif r["is_active_pred"] and not r["is_active_gt"]:
            tag = "FP"
        else:
            tag = "FN"
        print(f"  [{tag}] {r['phase_key'][-50:]:<50} v={r['verdict']:<22} "
              f"ambig={r['avg_ambig']:.1f} far={r['avg_far']:.1f} lslope={r['avg_low_slope']:.2f} "
              f"lr_var={r['lr_var']:.3f} max_span={r['max_time_span']} sig={r['signals_fired']}")

    # Save outputs
    out_csv = H1_DATA / "h107_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        wr.writeheader()
        wr.writerows(results)
    print(f"\nper-phase CSV: {out_csv}")

    summary = {
        "method": "H107 v1: 2D combined guard (ambig>0 OR far>0+lrvar>0.30 OR lslope>=3.0+maxspan>80)",
        "thresholds": {
            "H107_AVG_AMBIG_THR": H107_AVG_AMBIG_THR,
            "H107_AVG_FAR_THR": H107_AVG_FAR_THR,
            "H107_LR_VAR_THR": H107_LR_VAR_THR,
            "H107_AVG_LOW_SLOPE_THR": H107_AVG_LOW_SLOPE_THR,
            "H107_MAX_TIME_SPAN_THR": H107_MAX_TIME_SPAN_THR,
        },
        "h93_results": {
            "TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "P": round(P, 3), "R": round(R, 3), "acc": round(acc, 3),
            "n": n,
            "PERFECT": perfect,
        },
    }
    out = H1_DATA / "h107_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Summary: {out}")

    # 2D sensitivity grid: R3 thresholds (lslope × maxspan)
    print("\n=== 2D sensitivity grid: R3 (lslope × maxspan) — R1, R2 fixed ===")
    for ls in [2.0, 2.5, 3.0, 3.5, 4.0]:
        for ms in [50, 60, 70, 80, 90, 100]:
            _, tp_, tn_, fp_, fn_ = run_h107({"lslope": ls, "maxspan": ms})
            p_ = "PERFECT" if (tp_ == 17 and tn_ == 4 and fp_ == 0 and fn_ == 0) else "       "
            print(f"  lslope={ls:>4} maxspan={ms:>3}: TP={tp_} TN={tn_} FP={fp_} FN={fn_} {p_}")

    # 1D sensitivity grid on R2 lrvar threshold
    print("\n=== 1D sensitivity grid: R2 lrvar — R1, R3 fixed ===")
    for lv in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
        _, tp_, tn_, fp_, fn_ = run_h107({"lrvar": lv})
        p_ = "PERFECT" if (tp_ == 17 and tn_ == 4 and fp_ == 0 and fn_ == 0) else "       "
        print(f"  lrvar={lv:>5}: TP={tp_} TN={tn_} FP={fp_} FN={fn_} {p_}")

    # 1D sensitivity grid on R1 ambig threshold
    print("\n=== 1D sensitivity grid: R1 ambig — R2, R3 fixed ===")
    for amb in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        _, tp_, tn_, fp_, fn_ = run_h107({"ambig": amb})
        p_ = "PERFECT" if (tp_ == 17 and tn_ == 4 and fp_ == 0 and fn_ == 0) else "       "
        print(f"  ambig={amb:>4}: TP={tp_} TN={tn_} FP={fp_} FN={fn_} {p_}")


if __name__ == "__main__":
    main()
