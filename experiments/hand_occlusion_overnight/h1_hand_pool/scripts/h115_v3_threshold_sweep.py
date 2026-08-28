#!/usr/bin/env python3
"""H115 v3: extended H114 v1 threshold sweep on 29 QA'd H20-KEPT candidates.

HYPOTHESIS:
  H115 v2 found that H114 v1 (T_d=40, T_j=250) fires on 4/115 H20-KEPT
  candidates and hits 0/29 of the visually-QA'd subset (insufficient
  data to evaluate precision/recall). The chosen T_d=40 was at the
  edge of H112's [25, 40] flat region.

  H115 v3 sweeps a finer threshold grid to find the OPTIMAL operating
  point for the H20-KEPT QA'd subset. The question is: is there a
  threshold (T_d, T_j) that separates REAL from FALSE on the 29
  visually-QA'd H20-KEPT candidates with high precision/recall?

  If yes, H114 v1 would be a useful pre-filter for H21-style chain
  augmentation (H115 v3 integration test).
  If no, H114 v1 is confirmed not informative for the H20-KEPT pool,
  and the H17->H20->H28->H31 negative finding chain holds.

Per master §15: thresholds are declared before reading outcomes.
  T_d ∈ {25, 30, 40, 50, 60, 80}
  T_j ∈ {80, 100, 150, 200, 250, 300}
  36 cells.

Outputs:
  - data/h115_v3_threshold_grid.csv: 36 cells with precision/recall
  - data/h115_v3_optimal.json: best operating point
  - reports/h115_v3_section.md: summary written into h115_report.md
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

# H115 v3 declared thresholds (per master §15)
T_D_VALUES = [25, 30, 40, 50, 60, 80]
T_J_VALUES = [80, 100, 150, 200, 250, 300]

H20_KEPT = H1_DATA / "h115_h20_kept_per_edge.csv"
H24_QA = H1_DATA / "h24_visual_qa_verdicts.csv"
H28_QA = H1_DATA / "h28_visual_qa_verdicts.csv"
OUT_GRID = H1_DATA / "h115_v3_threshold_grid.csv"
OUT_OPT = H1_DATA / "h115_v3_optimal.json"


def spatial_jump(src_last_xy, tgt_first_xy):
    """Euclidean distance from source's last (x,y) to target's first (x,y)."""
    if src_last_xy is None or tgt_first_xy is None:
        return None
    dx = tgt_first_xy[0] - src_last_xy[0]
    dy = tgt_first_xy[1] - src_last_xy[1]
    return math.sqrt(dx * dx + dy * dy)


def main():
    # Load H20-KEPT per-edge with QA verdicts (deduplicate by edge key)
    rows = []
    seen = set()
    with H20_KEPT.open() as f:
        for row in csv.DictReader(f):
            if not row.get("visual_qa_verdict"):
                continue
            key = (row["stem"], int(row["src"]), int(row["tgt"]),
                   row["visual_qa_verdict"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    print(f"Loaded {len(rows)} deduped QA'd H20-KEPT candidates")

    # Per-row outcome categories
    def is_real(r): return r["visual_qa_verdict"] == "REAL"
    def is_true(r): return r["visual_qa_verdict"] in ("REAL", "PARTIAL")
    def is_false(r): return r["visual_qa_verdict"] == "FALSE"

    n_real = sum(1 for r in rows if is_real(r))
    n_true = sum(1 for r in rows if is_true(r))
    n_false = sum(1 for r in rows if is_false(r))
    print(f"  REAL: {n_real}, REAL+PARTIAL: {n_true}, FALSE: {n_false}")
    print()

    # Pre-compute fires for each (T_d, T_j) cell
    def fires(r, T_d, T_j):
        if r["end_d"] == "" or r["start_d"] == "":
            return False
        try:
            ed = float(r["end_d"])
            sd = float(r["start_d"])
            sj = float(r["spatial_jump"])
        except ValueError:
            return False
        return ed > T_d and sd > T_d and sj > T_j

    # Sweep grid
    grid = []
    for T_d in T_D_VALUES:
        for T_j in T_J_VALUES:
            kept = [r for r in rows if not fires(r, T_d, T_j)]
            rejected = [r for r in rows if fires(r, T_d, T_j)]
            n_kept = len(kept)
            n_rej = len(rejected)
            n_kept_real = sum(1 for r in kept if is_real(r))
            n_kept_true = sum(1 for r in kept if is_true(r))
            n_rej_real = sum(1 for r in rejected if is_real(r))
            n_rej_true = sum(1 for r in rejected if is_true(r))
            grid.append({
                "T_d": T_d,
                "T_j": T_j,
                "n_kept": n_kept,
                "n_rejected": n_rej,
                "n_kept_real": n_kept_real,
                "n_kept_true": n_kept_true,
                "n_rej_real": n_rej_real,
                "n_rej_true": n_rej_true,
                "precision_kept_real": n_kept_real / n_kept if n_kept else 0,
                "precision_kept_true": n_kept_true / n_kept if n_kept else 0,
                "precision_rej_real": n_rej_real / n_rej if n_rej else 0,
                "precision_rej_true": n_rej_true / n_rej if n_rej else 0,
                "recall_kept_real": n_kept_real / n_real if n_real else 0,
                "recall_kept_true": n_kept_true / n_true if n_true else 0,
            })

    # Find cells with both non-zero REJECTIONS and non-zero FIRES
    # A useful filter: it must catch at least 1 FALSE (precision work)
    # without dropping at least 1 REAL (recall preserved)
    # Score: precision_rej_real (high = filter catches REAL) is bad;
    #        precision_rej_true (REAL+PARTIAL) is more nuanced
    # Best filter: n_rejected >= 1 AND precision_rej_real == 0 (no REAL caught by mistake)
    #             AND n_kept_true / n_true (recall) == 1.0 (no REAL dropped)
    print("=" * 70)
    print("H115 v3 threshold grid (sorted by precision_kept_real descending)")
    print("=" * 70)
    print(f"{'T_d':>5} {'T_j':>5} | {'n_kept':>7} {'n_rej':>5} | "
          f"{'P_kept_REAL':>13} {'P_kept_TRUE':>13} | "
          f"{'R_kept_REAL':>13} {'R_kept_TRUE':>13}")
    print("-" * 70)
    for g in sorted(grid, key=lambda x: (-x["precision_kept_real"], -x["T_d"], -x["T_j"])):
        print(f"{g['T_d']:>5} {g['T_j']:>5} | {g['n_kept']:>7} {g['n_rejected']:>5} | "
              f"{g['precision_kept_real']:>13.3f} {g['precision_kept_true']:>13.3f} | "
              f"{g['recall_kept_real']:>13.3f} {g['recall_kept_true']:>13.3f}")

    # Save grid
    with OUT_GRID.open("w", newline="") as f:
        if grid:
            w = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
            w.writeheader()
            w.writerows(grid)
    print(f"\nWrote {OUT_GRID} ({len(grid)} cells)")

    # Identify OPTIMAL operating points under multiple criteria
    # Criterion 1: catches at least 1 FALSE, drops no REAL, max precision_kept_true
    crit1 = [g for g in grid if g["n_rejected"] >= 1 and g["recall_kept_real"] == 1.0]
    if crit1:
        best1 = max(crit1, key=lambda x: x["precision_kept_true"])
    else:
        best1 = None
    # Criterion 2: catches at least 1 FALSE, no constraint on REAL drops
    crit2 = [g for g in grid if g["n_rejected"] >= 1]
    if crit2:
        best2 = max(crit2, key=lambda x: (x["precision_kept_true"], -x["n_rejected"]))
    else:
        best2 = None
    # Criterion 3: matches the H114 v1 default (40, 250)
    best3 = next((g for g in grid if g["T_d"] == 40 and g["T_j"] == 250), None)

    opt = {
        "H115_v3_thresholds_swept": {
            "T_d": T_D_VALUES,
            "T_j": T_J_VALUES,
        },
        "n_qa": len(rows),
        "n_qa_real": n_real,
        "n_qa_true": n_true,
        "n_qa_false": n_false,
        "best_criterion_1_catches_false_drops_no_real": best1,
        "best_criterion_2_catches_at_least_one_false": best2,
        "h114_v1_default_40_250": best3,
    }
    with OUT_OPT.open("w") as f:
        json.dump(opt, f, indent=2)
    print(f"Wrote {OUT_OPT}")

    print()
    print("=" * 70)
    print("OPTIMAL OPERATING POINTS")
    print("=" * 70)
    if best1:
        print(f"Best (catches FALSE, drops no REAL, max P_kept_TRUE): "
              f"T_d={best1['T_d']}, T_j={best1['T_j']}")
        print(f"  n_kept={best1['n_kept']}, n_rej={best1['n_rejected']}, "
              f"P_kept_TRUE={best1['precision_kept_true']:.3f}, "
              f"R_kept_TRUE={best1['recall_kept_true']:.3f}")
    else:
        print("No threshold catches >=1 FALSE without dropping >=1 REAL.")
    if best3:
        print(f"H114 v1 default (40, 250): n_kept={best3['n_kept']}, "
              f"n_rej={best3['n_rejected']}, "
              f"P_kept_TRUE={best3['precision_kept_true']:.3f}, "
              f"R_kept_TRUE={best3['recall_kept_true']:.3f}")


if __name__ == "__main__":
    main()
