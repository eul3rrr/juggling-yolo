#!/usr/bin/env python3
"""H75 - H43 + H69 + H74 stacked FOUNTAIN_3+ post-filter.

Hypothesis: The combination of H43 (conf < 0.55), H69 (spec_conc < 0.15),
and H74 (LR_variance < 0.20) should catch ALL 4 misclassified FOUNTAIN_3+
phases on the H65 sample while preserving all 3 real FOUNTAIN phases.

The H74 stack adds a new dimension (L+R temporal variance) that catches
the 5-ball static hold (f=482-594, var=0.135) which the H43+H69 stack
already catches via spec_conc, but is a useful backstop in case spec_conc
is noisy on similar phases.

Per-phase evaluation on the H65 sample (7 FOUNTAIN_3+ phases):
- f=631-669 identical: REAL_FOUNTAIN (h65=FOUNTAIN)
- f=890-936 identical: OTHER (h65=OTHER, crossed-arm trick)
- f=977-1011 identical: REAL_FOUNTAIN (h65=FOUNTAIN)
- f=1029-1049 identical: OTHER (h65=OTHER, static hold)
- f=339-374 YouTube: REAL_FOUNTAIN (h65=FOUNTAIN)
- f=482-594 YouTube: OTHER (h65=OTHER, static hold)
- f=800-861 YouTube: OTHER (h65=OTHER, real CASCADE misclassified)

Plus 1 additional H73 case:
- f=733-766 identical: CASCADE_3+ (STATIC_HOLD per H72, var=0.157)

Test H43 + H69 + H74 stacked rejection.
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

# Per-phase ground truth (H65 + H72 + H73)
GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        (631, 669): "REAL_FOUNTAIN",
        (685, 716): "MANIPULATION_TRICK",
        (733, 766): "STATIC_HOLD",
        (890, 936): "OTHER_NOT_FOUNTAIN",  # crossed-arm trick
        (977, 1011): "REAL_FOUNTAIN",
        (1029, 1049): "OTHER_NOT_FOUNTAIN",  # 2-ball exercise
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (339, 374): "REAL_FOUNTAIN",
        (482, 594): "OTHER_NOT_FOUNTAIN",  # 5-ball static hold
        (800, 861): "OTHER_NOT_FOUNTAIN",  # real CASCADE misclassified
    },
}

# Default thresholds
H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20


def load_h69_phases(stem: str) -> dict[tuple[int, int], dict]:
    """Load H69 phase data keyed by (start, end)."""
    p = H1_DATA / f"h69_phases_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        s = int(row["phase_start"])
        e = int(row["phase_end"])
        out[(s, e)] = {
            "conf": float(row["mean_confidence"]),
            "spec_conc": float(row["spectral_concentration"]),
            "h69_rejected": row["h69_rejected"] == "True",
            "h65_verdict": row["h65_verdict"],
        }
    return out


def load_h40v2(stem: str) -> dict[int, tuple[int, int]]:
    """Load H40v2 sustained-occupancy as frame -> (L40v2, R40v2)."""
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        f = int(row["frame"])
        l = int(row["L40v2"])
        r = int(row["R40v2"])
        out[f] = (l, r)
    return out


def compute_lr_variance(h40v2: dict[int, tuple[int, int]], start: int, end: int) -> float:
    """Compute LR_variance for a phase range."""
    LR_series = []
    for f in range(start, end + 1):
        if f not in h40v2:
            continue
        l, r = h40v2[f]
        LR_series.append(l + r)
    if not LR_series or len(LR_series) < 2:
        return 0.0
    return statistics.variance(LR_series)


def main() -> None:
    summary = {"videos": {}}
    print("H75 - H43 + H69 + H74 stacked FOUNTAIN_3+ post-filter")
    print("=" * 80)

    # Track per-phase rejection by each filter
    all_phases = []
    n_real_kept = 0
    n_real_rejected = 0
    n_misclass_caught = 0
    n_misclass_missed = 0

    for stem in STEMS:
        h69 = load_h69_phases(stem)
        h40v2 = load_h40v2(stem)
        gt = GROUND_TRUTH.get(stem, {})

        per_phase_records = []
        for (s, e), info in sorted(h69.items()):
            conf = info["conf"]
            spec_conc = info["spec_conc"]
            lr_var = compute_lr_variance(h40v2, s, e)

            # Individual filter decisions
            h43_reject = conf < H43_CONF_THR
            h69_reject = spec_conc < H69_SPEC_CONC_THR
            h74_reject = lr_var < H74_LR_VAR_THR

            # Stacked: REJECT if any filter rejects
            stacked_reject = h43_reject or h69_reject or h74_reject

            # Ground truth
            gt_verdict = gt.get((s, e), "N/A")

            # Decision correctness
            if gt_verdict == "REAL_FOUNTAIN":
                if stacked_reject:
                    n_real_rejected += 1
                    correct = False  # false reject
                else:
                    n_real_kept += 1
                    correct = True
            elif gt_verdict in ("OTHER_NOT_FOUNTAIN", "STATIC_HOLD", "MANIPULATION_TRICK"):
                if stacked_reject:
                    n_misclass_caught += 1
                    correct = True  # true reject
                else:
                    n_misclass_missed += 1
                    correct = False  # false keep
            else:
                correct = None

            record = {
                "stem": stem,
                "start": s,
                "end": e,
                "pattern": "FOUNTAIN_3+",  # H69 only has FOUNTAIN_3+ in this dataset
                "conf": round(conf, 3),
                "spec_conc": round(spec_conc, 3),
                "lr_variance": round(lr_var, 3),
                "h43_reject": h43_reject,
                "h69_reject": h69_reject,
                "h74_reject": h74_reject,
                "stacked_reject": stacked_reject,
                "gt_verdict": gt_verdict,
                "correct": correct,
            }
            per_phase_records.append(record)
            all_phases.append(record)

            filter_str = "".join([
                "H43" if h43_reject else ".",
                "H69" if h69_reject else ".",
                "H74" if h74_reject else ".",
            ])
            print(f"  f={s}-{e} ({stem[:10]}) gt={gt_verdict:<25} "
                  f"conf={conf:.3f} conc={spec_conc:.3f} var={lr_var:.3f} "
                  f"-> reject={stacked_reject} [{filter_str}] {'OK' if correct else 'WRONG'}")
        summary["videos"][stem] = {
            "n_phases": len(per_phase_records),
            "phases": per_phase_records,
        }

    # Aggregate stats
    print(f"\n=== Stack performance ===")
    print(f"  REAL_FOUNTAIN kept: {n_real_kept}, rejected: {n_real_rejected}")
    print(f"  Misclassified caught: {n_misclass_caught}, missed: {n_misclass_missed}")
    n_real = n_real_kept + n_real_rejected
    n_mis = n_misclass_caught + n_misclass_missed
    if n_real > 0:
        print(f"  Real-FOUNTAIN recall: {n_real_kept}/{n_real} = {n_real_kept/n_real:.2%}")
    if n_mis > 0:
        print(f"  Misclassified rejection precision: {n_misclass_caught}/{n_mis} = {n_misclass_caught/n_mis:.2%}")

    # Compare with H43 + H69 alone (no H74)
    print(f"\n=== Comparison: H43 + H69 (no H74) ===")
    h4369_real_kept = sum(1 for r in all_phases
                          if r["gt_verdict"] == "REAL_FOUNTAIN"
                          and not (r["h43_reject"] or r["h69_reject"]))
    h4369_real_rejected = sum(1 for r in all_phases
                              if r["gt_verdict"] == "REAL_FOUNTAIN"
                              and (r["h43_reject"] or r["h69_reject"]))
    h4369_mis_caught = sum(1 for r in all_phases
                            if r["gt_verdict"] != "REAL_FOUNTAIN" and r["gt_verdict"] != "N/A"
                            and (r["h43_reject"] or r["h69_reject"]))
    h4369_mis_missed = sum(1 for r in all_phases
                           if r["gt_verdict"] != "REAL_FOUNTAIN" and r["gt_verdict"] != "N/A"
                           and not (r["h43_reject"] or r["h69_reject"]))
    print(f"  REAL_FOUNTAIN kept: {h4369_real_kept}, rejected: {h4369_real_rejected}")
    print(f"  Misclassified caught: {h4369_mis_caught}, missed: {h4369_mis_missed}")

    summary["all_phases"] = all_phases
    summary["stats"] = {
        "n_total": len(all_phases),
        "n_real_kept": n_real_kept,
        "n_real_rejected": n_real_rejected,
        "n_misclass_caught": n_misclass_caught,
        "n_misclass_missed": n_misclass_missed,
        "thresholds": {
            "H43_conf": H43_CONF_THR,
            "H69_spec_conc": H69_SPEC_CONC_THR,
            "H74_lr_var": H74_LR_VAR_THR,
        },
    }
    out = H1_DATA / "h75_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
