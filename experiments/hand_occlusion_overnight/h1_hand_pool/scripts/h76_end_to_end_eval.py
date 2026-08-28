#!/usr/bin/env python3
"""H76 - end-to-end precision/recall of full h7v3plus3 + H10 v11 v3 + H12 v8
+ H50 + H70/H71/H75 v1 stack on the FULL 20-phase H70 sample.

H59 was evaluated on the 113 manual review pairs (stitch_review_labels.csv),
not on the H70 phases. H76 re-runs the H59 methodology on the 20 H70
substantial phases with the full ground truth from H65 + H71 + H72 + H73.

Ground truth (H65/H71/H72/H73 verdicts on all 20 phases):
- FOUNTAIN_3+ (7):
  - f=631-669 identical: REAL_FOUNTAIN
  - f=890-936 identical: OTHER (crossed-arm trick)
  - f=977-1011 identical: REAL_FOUNTAIN
  - f=1029-1049 identical: OTHER (2-ball exercise)
  - f=339-374 YouTube: REAL_FOUNTAIN
  - f=482-594 YouTube: OTHER (5-ball static hold)
  - f=800-861 YouTube: OTHER (CASCADE misclassified)
- CASCADE_3+ (1):
  - f=685-716 identical: MANIPULATION_TRICK (not a true cascade)
- MIXED_3+ (10, all confirmed as real juggling by H71/H72):
  - f=263-312, f=411-450, f=549-578 identical: REAL
  - f=114-255 YouTube: REAL (JUGGLING_STARTUP, H71 false positive)
  - f=308-338, f=769-799 YouTube: REAL
  - f=267-298, f=375-410, f=420-481, f=595-643, f=862-899 YouTube: REAL
- MIXED_3+_UNCONFIRMED (1):
  - f=2-71 YouTube: STATIC (correctly rejected by H70)
- 1 more CASCADE_3+ in H70 (f=733-766): STATIC_HOLD

Wait, H70 had only 1 CASCADE_3+ (f=685-716) in the original sample. But
H72's H73 found f=733-766 is also CASCADE_3+ in H70's data.

Let me check H70's actual phase list.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Comprehensive ground truth for all 20 H70 phases
# Tuple: (stem, start, end, h12_pattern, gt_real, gt_class, verdict_source)
GROUND_TRUTH = {
    # identical: 7 substantial phases
    "identical_balls_trick_000_018": {
        (263, 312): ("MIXED_3+", "JUGGLING", "H71"),
        (411, 450): ("MIXED_3+", "JUGGLING", "H71"),
        (549, 578): ("MIXED_3+", "JUGGLING", "H71"),
        (631, 669): ("FOUNTAIN_3+", "FOUNTAIN", "H65"),
        (685, 716): ("CASCADE_3+", "MANIPULATION_TRICK", "H72"),
        (733, 766): ("CASCADE_3+", "STATIC_HOLD", "H73"),
        (890, 936): ("FOUNTAIN_3+", "OTHER", "H65"),  # crossed-arm
        (977, 1011): ("FOUNTAIN_3+", "FOUNTAIN", "H65"),
        (1029, 1049): ("FOUNTAIN_3+", "OTHER", "H65"),  # 2-ball exercise
    },
    # YouTube: 12 substantial phases
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (2, 71): ("MIXED_3+_UNCONFIRMED", "STATIC", "H71"),  # startup
        (114, 255): ("MIXED_3+", "JUGGLING_STARTUP", "H71"),
        (267, 298): ("MIXED_3+", "JUGGLING", "H72"),
        (308, 338): ("MIXED_3+", "JUGGLING", "H71"),
        (339, 374): ("FOUNTAIN_3+", "FOUNTAIN", "H65"),
        (375, 410): ("MIXED_3+", "JUGGLING", "H72"),
        (420, 481): ("MIXED_3+", "JUGGLING", "H72"),
        (482, 594): ("FOUNTAIN_3+", "STATIC_HOLD", "H74"),
        (595, 643): ("MIXED_3+", "JUGGLING", "H72"),
        (769, 799): ("MIXED_3+", "JUGGLING", "H71"),
        (800, 861): ("FOUNTAIN_3+", "CASCADE", "H65"),
        (862, 899): ("MIXED_3+", "JUGGLING", "H72"),
    },
}

# Thresholds for the full stack
H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20
H71_SPEC_CONC_KEEP = 0.15
H71_SPEC_CONC_REJECT = 0.10


def load_h70_phases(stem: str) -> dict[tuple[int, int], dict]:
    p = H1_DATA / f"h70_phases_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        s = int(row["phase_start"])
        e = int(row["phase_end"])
        out[(s, e)] = {
            "pattern": row["pattern"],
            "conf": float(row["mean_confidence"]),
            "spec_conc": float(row["spectral_concentration"]),
        }
    return out


def load_h40v2(stem: str) -> dict[int, tuple[int, int]]:
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        f = int(row["frame"])
        out[f] = (int(row["L40v2"]), int(row["R40v2"]))
    return out


def compute_lr_var(h40v2: dict, start: int, end: int) -> float:
    series = []
    for f in range(start, end + 1):
        if f in h40v2:
            l, r = h40v2[f]
            series.append(l + r)
    return statistics.variance(series) if len(series) > 1 else 0.0


def filter_decision(pattern: str, conf: float, spec_conc: float, lr_var: float) -> tuple[bool, str]:
    """Returns (is_rejected, reason)."""
    # H75 stack: H43 OR H69 OR H74
    if pattern == "FOUNTAIN_3+":
        h43 = conf < H43_CONF_THR
        h69 = spec_conc < H69_SPEC_CONC_THR
        h74 = lr_var < H74_LR_VAR_THR
        if h43:
            return True, "H43"
        if h69:
            return True, "H69"
        if h74:
            return True, "H74"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        # H74 only (per H75 recommendation)
        h74 = lr_var < H74_LR_VAR_THR
        if h74:
            return True, "H74"
        return False, "KEPT"
    elif pattern == "MIXED_3+":
        # H71 v1: KEEP at spec_conc >= 0.15, REJECT at spec_conc < 0.10
        # 0.10 <= spec_conc < 0.15: MIXED_3+_LOW_CONF (research signal, not rejected)
        if spec_conc < H71_SPEC_CONC_REJECT:
            return True, "H71_REJECT"
        return False, "KEPT"
    elif pattern == "MIXED_3+_UNCONFIRMED":
        # Per H71: spec_conc < 0.10 = REJECT (correct for f=2-71 with conc=0.075)
        if spec_conc < H71_SPEC_CONC_REJECT:
            return True, "H71_REJECT"
        return False, "KEPT"
    else:
        return False, "KEPT"


def main() -> None:
    summary = {"videos": {}}
    print("H76 - end-to-end precision/recall of full stack on 20-phase H70 sample")
    print("=" * 80)

    all_results = []
    n_total = 0
    n_correct_keep = 0  # real juggling kept
    n_correct_reject = 0  # misclassified rejected
    n_wrong_keep = 0  # misclassified kept (false positive)
    n_wrong_reject = 0  # real juggling rejected (false negative)

    for stem in STEMS:
        h70 = load_h70_phases(stem)
        h40v2 = load_h40v2(stem)
        gt = GROUND_TRUTH[stem]

        per_phase_records = []
        for (s, e), info in sorted(h70.items()):
            pattern = info["pattern"]
            conf = info["conf"]
            spec_conc = info["spec_conc"]
            lr_var = compute_lr_var(h40v2, s, e)
            is_rejected, reason = filter_decision(pattern, conf, spec_conc, lr_var)

            gt_pattern, gt_class, gt_source = gt.get((s, e), ("?", "?", "?"))

            # "Real juggling" if gt_class in {JUGGLING, JUGGLING_STARTUP, FOUNTAIN, CASCADE}
            # "Misclassified" if gt_class in {OTHER, STATIC, MANIPULATION_TRICK, STATIC_HOLD}
            is_real = gt_class in ("JUGGLING", "JUGGLING_STARTUP", "FOUNTAIN", "CASCADE")
            is_misclass = not is_real and gt_class != "?"

            # Decision correctness
            if is_real and not is_rejected:
                correct = "TP"
                n_correct_keep += 1
            elif is_misclass and is_rejected:
                correct = "TN"
                n_correct_reject += 1
            elif is_real and is_rejected:
                correct = "FN"
                n_wrong_reject += 1
            elif is_misclass and not is_rejected:
                correct = "FP"
                n_wrong_keep += 1
            else:
                correct = "?"

            n_total += 1
            record = {
                "stem": stem,
                "start": s,
                "end": e,
                "pattern": pattern,
                "gt_class": gt_class,
                "gt_source": gt_source,
                "conf": round(conf, 3),
                "spec_conc": round(spec_conc, 3),
                "lr_var": round(lr_var, 3),
                "is_rejected": is_rejected,
                "reason": reason,
                "is_real": is_real,
                "decision": correct,
            }
            per_phase_records.append(record)
            all_results.append(record)
            print(f"  f={s}-{e} ({pattern}) gt={gt_class:<20} "
                  f"conf={conf:.3f} conc={spec_conc:.3f} var={lr_var:.3f} "
                  f"-> {'REJECT' if is_rejected else 'KEEP':<6} [{reason}] {correct}")

        summary["videos"][stem] = {
            "n_phases": len(per_phase_records),
            "phases": per_phase_records,
        }

    # Aggregate stats
    n_real = sum(1 for r in all_results if r["is_real"])
    n_misclass = sum(1 for r in all_results if not r["is_real"] and r["gt_class"] != "?")
    n_kept = sum(1 for r in all_results if not r["is_rejected"])
    n_rejected = sum(1 for r in all_results if r["is_rejected"])

    print(f"\n=== Summary ===")
    print(f"  Total phases: {n_total}")
    print(f"  Real juggling: {n_real}, Misclassified: {n_misclass}")
    print(f"  Kept: {n_kept}, Rejected: {n_rejected}")
    print(f"  TP (real kept): {n_correct_keep}")
    print(f"  TN (misclass rejected): {n_correct_reject}")
    print(f"  FP (misclass kept): {n_wrong_keep}")
    print(f"  FN (real rejected): {n_wrong_reject}")
    if n_real > 0:
        print(f"  Real recall: {n_correct_keep}/{n_real} = {n_correct_keep/n_real:.1%}")
        print(f"  Real FN: {n_wrong_reject}/{n_real} = {n_wrong_reject/n_real:.1%}")
    if n_misclass > 0:
        print(f"  Misclass rejection precision: {n_correct_reject}/{n_misclass} = {n_correct_reject/n_misclass:.1%}")
        print(f"  Misclass FP: {n_wrong_keep}/{n_misclass} = {n_wrong_keep/n_misclass:.1%}")

    # Per-pattern breakdown
    print(f"\n=== Per-pattern breakdown ===")
    by_pattern = {}
    for r in all_results:
        by_pattern.setdefault(r["pattern"], []).append(r)
    for pat, rs in sorted(by_pattern.items()):
        n_p = len(rs)
        n_p_real = sum(1 for r in rs if r["is_real"])
        n_p_mis = sum(1 for r in rs if not r["is_real"] and r["gt_class"] != "?")
        n_p_rej = sum(1 for r in rs if r["is_rejected"])
        n_p_real_rej = sum(1 for r in rs if r["is_real"] and r["is_rejected"])
        n_p_mis_rej = sum(1 for r in rs if not r["is_real"] and r["is_rejected"] and r["gt_class"] != "?")
        print(f"  {pat:<25} n={n_p} real={n_p_real} mis={n_p_mis} "
              f"rejected={n_p_rej} (real_rej={n_p_real_rej}, mis_rej={n_p_mis_rej})")

    summary["all_results"] = all_results
    summary["stats"] = {
        "n_total": n_total,
        "n_real": n_real,
        "n_misclass": n_misclass,
        "n_kept": n_kept,
        "n_rejected": n_rejected,
        "TP": n_correct_keep,
        "TN": n_correct_reject,
        "FP": n_wrong_keep,
        "FN": n_wrong_reject,
    }
    out = H1_DATA / "h76_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
