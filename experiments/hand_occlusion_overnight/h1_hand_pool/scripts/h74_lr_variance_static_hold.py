#!/usr/bin/env python3
"""H74 - H40v2 L+R temporal variance as static-hold detector.

Hypothesis: A real FOUNTAIN_3+ pattern has balls cycling through the
hands. H40v2 L+R should have HIGH temporal variance (cycling 0-2-1-2-...).
A static hold / manipulation trick has balls stable near the hands. L+R
should have LOW temporal variance (stable 1-1 or 2-0-...).

H73 found that H40v2 mean L+R is similar for real FOUNTAIN and
misclassified FOUNTAIN_3+ / CASCADE_3+ phases. The mean is a
low-information summary. The TEMPORAL VARIANCE of L+R should
discriminate:
- Real FOUNTAIN: high variance (balls in/out of hands)
- Static hold: low variance (balls stable in hands)
- Manipulation trick: low variance (balls in fixed body positions)

Cross-reference with H65 ground truth (3 real FOUNTAIN, 4 misclassified
FOUNTAIN_3+, 2 misclassified CASCADE_3+ on the H73 sample).
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

MIN_PHASE_FRAMES = 20

# Target pattern classes
TARGET_PATTERNS = {"CASCADE_3+", "FOUNTAIN_3+"}

# Ground truth verdicts from H65 (FOUNTAIN) and H72 (CASCADE_3+ identical)
GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        (631, 669): ("FOUNTAIN_3+", "REAL_FOUNTAIN"),
        (685, 716): ("CASCADE_3+", "MANIPULATION_TRICK"),
        (733, 766): ("CASCADE_3+", "STATIC_HOLD"),
        (890, 936): ("FOUNTAIN_3+", "OTHER_NOT_FOUNTAIN"),
        (977, 1011): ("FOUNTAIN_3+", "REAL_FOUNTAIN"),
        (1029, 1049): ("FOUNTAIN_3+", "OTHER_NOT_FOUNTAIN"),
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (339, 374): ("FOUNTAIN_3+", "REAL_FOUNTAIN"),
        (482, 594): ("FOUNTAIN_3+", "OTHER_NOT_FOUNTAIN"),
        (800, 861): ("FOUNTAIN_3+", "OTHER_NOT_FOUNTAIN"),  # h65 says CASCADE not FOUNTAIN
    },
}


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


def load_pattern_phases(stem: str) -> list[dict]:
    """Load all substantial pattern phases from H50-filtered data."""
    p = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(p)):
        n = int(row["n_frames"])
        if n >= MIN_PHASE_FRAMES:
            out.append({
                "start": int(row["start_frame"]),
                "end": int(row["end_frame"]),
                "n": n,
                "pattern": row["pattern"],
                "conf": float(row["avg_confidence"]),
            })
    return out


def temporal_stats(values: list[int]) -> dict:
    """Compute temporal statistics for a per-frame sequence."""
    if not values:
        return {}
    n = len(values)
    mean = sum(values) / n
    variance = statistics.variance(values) if n > 1 else 0.0
    stdev = variance ** 0.5
    # Range and mode
    vmin = min(values)
    vmax = max(values)
    # Number of direction changes (sign change of consecutive differences)
    diffs = [values[i+1] - values[i] for i in range(n - 1)]
    direction_changes = sum(1 for i in range(len(diffs) - 1) if diffs[i] * diffs[i+1] < 0)
    # Fraction of frames with L+R change
    n_changed = sum(1 for d in diffs if d != 0)
    return {
        "n": n,
        "mean": round(mean, 3),
        "variance": round(variance, 3),
        "stdev": round(stdev, 3),
        "min": vmin,
        "max": vmax,
        "n_direction_changes": direction_changes,
        "pct_changed": round(n_changed / max(n - 1, 1), 3),
    }


def main() -> None:
    summary = {"videos": {}}
    print("H74 - H40v2 L+R temporal variance as static-hold detector")
    print("=" * 80)

    all_phases = []
    for stem in STEMS:
        h40v2 = load_h40v2(stem)
        phases = load_pattern_phases(stem)
        print(f"\n=== {stem} ===")

        per_phase_records = []
        for ph in phases:
            if ph["pattern"] not in TARGET_PATTERNS:
                continue
            L_series = []
            R_series = []
            LR_series = []
            for f in range(ph["start"], ph["end"] + 1):
                if f not in h40v2:
                    continue
                l, r = h40v2[f]
                L_series.append(l)
                R_series.append(r)
                LR_series.append(l + r)
            if not LR_series:
                continue
            L_stats = temporal_stats(L_series)
            R_stats = temporal_stats(R_series)
            LR_stats = temporal_stats(LR_series)
            gt_pattern, gt_verdict = GROUND_TRUTH.get(stem, {}).get(
                (ph["start"], ph["end"]), ("N/A", "N/A"))

            record = {
                "stem": stem,
                "start": ph["start"],
                "end": ph["end"],
                "pattern": ph["pattern"],
                "n_frames": len(LR_series),
                "L_variance": L_stats["variance"],
                "L_stdev": L_stats["stdev"],
                "R_variance": R_stats["variance"],
                "R_stdev": R_stats["stdev"],
                "LR_variance": LR_stats["variance"],
                "LR_stdev": LR_stats["stdev"],
                "LR_direction_changes": LR_stats["n_direction_changes"],
                "LR_pct_changed": LR_stats["pct_changed"],
                "LR_range": LR_stats["max"] - LR_stats["min"],
                "LR_mean": LR_stats["mean"],
                "conf": round(ph["conf"], 3),
                "gt_pattern": gt_pattern,
                "gt_verdict": gt_verdict,
            }
            per_phase_records.append(record)
            all_phases.append(record)
            print(f"  {ph['pattern']:<13} f={ph['start']}-{ph['end']} "
                  f"gt={gt_verdict:<25} "
                  f"LR_mean={LR_stats['mean']:.2f} LR_var={LR_stats['variance']:.3f} "
                  f"LR_stdev={LR_stats['stdev']:.3f} LR_dir_chg={LR_stats['n_direction_changes']:3d} "
                  f"LR_pct_chg={LR_stats['pct_changed']:.2f}")
        summary["videos"][stem] = {
            "n_target_phases": len(per_phase_records),
            "phases": per_phase_records,
        }

    # Aggregate stats: compare variance to ground truth
    print(f"\n=== Summary: variance by ground truth verdict ===")
    by_verdict: dict[str, list] = {}
    for r in all_phases:
        by_verdict.setdefault(r["gt_verdict"], []).append(r)
    for verdict, rs in sorted(by_verdict.items()):
        n = len(rs)
        if n == 0:
            continue
        mean_var = sum(r["LR_variance"] for r in rs) / n
        mean_pct_chg = sum(r["LR_pct_changed"] for r in rs) / n
        mean_dir_chg = sum(r["LR_direction_changes"] for r in rs) / n
        print(f"  {verdict:<25} n={n} LR_var_mean={mean_var:.3f} "
              f"LR_pct_chg_mean={mean_pct_chg:.3f} LR_dir_chg_mean={mean_dir_chg:.1f}")

    # Try to find a threshold that separates real FOUNTAIN from misclassified
    print(f"\n=== Threshold search: separate REAL_FOUNTAIN from misclassified ===")
    real = [r for r in all_phases if r["gt_verdict"] == "REAL_FOUNTAIN"]
    mis = [r for r in all_phases if r["gt_verdict"] != "REAL_FOUNTAIN" and r["gt_verdict"] != "N/A"]
    print(f"  REAL_FOUNTAIN: {len(real)} phases")
    print(f"  misclassified: {len(mis)} phases")
    if real and mis:
        # Try LR_variance threshold
        for thr in [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
            n_real_kept = sum(1 for r in real if r["LR_variance"] >= thr)
            n_mis_rejected = sum(1 for r in mis if r["LR_variance"] < thr)
            print(f"  LR_variance >= {thr}: kept {n_real_kept}/{len(real)} real, "
                  f"rejected {n_mis_rejected}/{len(mis)} misclassified")

    summary["all_phases"] = all_phases
    summary["stats"] = {
        "n_target_phases": len(all_phases),
        "by_verdict": {v: len(p) for v, p in by_verdict.items()},
    }
    out = H1_DATA / "h74_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
