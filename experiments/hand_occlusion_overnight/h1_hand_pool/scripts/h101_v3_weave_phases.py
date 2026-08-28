#!/usr/bin/env python3
"""
H101 v3 — weave_colored_317_330 phase analysis + H100 v4 guard sensitivity.

Visual QA (via vision_analyze) confirmed: the weave video is
**3-ball CASCADE pattern, active juggling throughout** (7/7
sampled frames). The H100 v4 conf+spec_conc guard (conf>=0.50)
fails on this video because its conf distribution is lower
(mean 0.45 vs identical/YouTube ~0.55-0.65).

H101 v3:
1. Compute substantial phases via 60-frame non-overlapping windows
   (clear, non-overlapping phase boundaries).
2. Compute H12 v8-style per-phase features:
   - mean_conf, max_conf, min_conf
   - peak_n_balls, mean_n_balls, std_n_balls, pct_ge3
   - spectral_concentration (on n_balls time series)
3. Apply H100 v4 conf+spec_conc guard with original thresholds
   (conf>=0.50, spec_conc>=0.13) AND with relaxed thresholds
   to characterize the threshold-video-dependence.
4. Output a 2D threshold grid (conf_min × spec_conc_min) showing
   how many phases pass for each combination. The ideal guard
   should pass all REAL juggling phases and reject STATIC_HOLD.
   Since visual QA confirms ALL phases are JUGGLING, the
   flat-region guards that pass all 6 phases are the candidates.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
DETECTIONS = WORKTREE / "detections"

STEM = "weave_colored_317_330"
BALLS_CSV = DETECTIONS / "weave_colored_317_330_yolo26s_classes-32.csv"
OUT_DIR = H1_DATA
PHASES_CSV = OUT_DIR / f"h101_v3_phases_{STEM}.csv"
GRID_CSV = OUT_DIR / f"h101_v3_grid_{STEM}.csv"
SUMMARY_JSON = OUT_DIR / f"h101_v3_summary.json"

PHASE_LEN = 60  # frames per phase (60 = ~2 sec at 30 fps)


def load_per_frame_balls():
    out = {}
    with open(BALLS_CSV) as f:
        r = csv.DictReader(f)
        for row in r:
            if row["class_name"] != "sports ball":
                continue
            frame = int(row["frame"])
            out.setdefault(frame, []).append(
                (float(row["center_x"]), float(row["center_y"]), float(row["confidence"]))
            )
    return out


def compute_spectral_concentration(values):
    if len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    centered = [v - mean for v in values]
    nfreqs = max(1, n // 2)
    amps = []
    for k in range(1, nfreqs + 1):
        re = sum(c * math.cos(2 * math.pi * k * i / n) for i, c in enumerate(centered))
        im = sum(c * math.sin(2 * math.pi * k * i / n) for i, c in enumerate(centered))
        amps.append((re * re + im * im) ** 0.5)
    if not amps or sum(amps) == 0:
        return 0.0
    return max(amps) / sum(amps)


def main():
    print(f"=== H101 v3: weave_colored_317_330 phase analysis + H100 v4 guard sensitivity ===")
    balls = load_per_frame_balls()
    print(f"Loaded {len(balls)} frames with detections.")

    fmax = max(balls.keys())
    fmin = min(balls.keys())
    print(f"Frame range: {fmin}-{fmax}")

    # Build non-overlapping 60-frame phases
    phases = []
    for w_start in range(fmin, fmax + 1, PHASE_LEN):
        w_end = min(w_start + PHASE_LEN - 1, fmax)
        if w_start > w_end:
            break
        # Per-phase features
        n_balls_seq = []
        confs = []
        centers = []
        for f in range(w_start, w_end + 1):
            n = len(balls.get(f, []))
            n_balls_seq.append(n)
            if f in balls:
                for (cx, cy, c) in balls[f]:
                    confs.append(c)
                    centers.append((cx, cy))
        if not confs:
            continue
        mean_conf = statistics.mean(confs)
        max_conf = max(confs)
        min_conf = min(confs)
        peak_n = max(n_balls_seq)
        mean_n = statistics.mean(n_balls_seq)
        std_n = statistics.stdev(n_balls_seq) if len(n_balls_seq) > 1 else 0.0
        pct_ge3 = sum(1 for n in n_balls_seq if n >= 3) / len(n_balls_seq)
        spec_conc = compute_spectral_concentration(n_balls_seq)
        phases.append({
            "start": w_start, "end": w_end, "n_frames": w_end - w_start + 1,
            "mean_conf": mean_conf, "max_conf": max_conf, "min_conf": min_conf,
            "peak_n": peak_n, "mean_n": mean_n, "std_n": std_n, "pct_ge3": pct_ge3,
            "spec_conc": spec_conc,
        })
    print(f"\nNon-overlapping {PHASE_LEN}-frame phases: {len(phases)}")
    for p in phases:
        print(f"  f={p['start']}-{p['end']} mean_conf={p['mean_conf']:.3f} "
              f"peak_n={p['peak_n']} mean_n={p['mean_n']:.2f} spec_conc={p['spec_conc']:.3f}")

    # 2D threshold grid for the H100 v4 conf+spec_conc guard
    conf_levels = [0.20, 0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
    spec_levels = [0.05, 0.10, 0.13, 0.15, 0.20, 0.25, 0.30, 0.40]
    grid = {}
    for t1 in conf_levels:
        grid[t1] = {}
        for t2 in spec_levels:
            passes = sum(1 for p in phases if p["mean_conf"] >= t1 and p["spec_conc"] >= t2)
            grid[t1][t2] = passes

    # Find flat region: cells where all 6 phases pass
    n_phases = len(phases)
    perfect_cells = []
    for t1 in conf_levels:
        for t2 in spec_levels:
            if grid[t1][t2] == n_phases:
                perfect_cells.append((t1, t2))
    print(f"\nH100 v4 conf+spec_conc guard 2D grid (cells where all {n_phases} phases pass):")
    for t1, t2 in perfect_cells:
        print(f"  conf>={t1:.2f} spec_conc>={t2:.2f}: PASS ALL")
    if not perfect_cells:
        # Find the max-pass cell
        max_pass = max(grid[t1][t2] for t1 in conf_levels for t2 in spec_levels)
        max_cells = [(t1, t2) for t1 in conf_levels for t2 in spec_levels if grid[t1][t2] == max_pass]
        print(f"  No cell passes all {n_phases}. Max passes: {max_pass}/{n_phases} at:")
        for t1, t2 in max_cells:
            print(f"    conf>={t1:.2f} spec_conc>={t2:.2f}")

    # Phases CSV
    with open(PHASES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["phase_start", "phase_end", "n_frames",
                    "mean_conf", "min_conf", "max_conf",
                    "peak_n_balls", "mean_n_balls", "std_n_balls", "pct_ge3",
                    "spectral_concentration"])
        for p in phases:
            w.writerow([p["start"], p["end"], p["n_frames"],
                        f"{p['mean_conf']:.4f}", f"{p['min_conf']:.4f}", f"{p['max_conf']:.4f}",
                        p["peak_n"], f"{p['mean_n']:.2f}", f"{p['std_n']:.3f}", f"{p['pct_ge3']:.2f}",
                        f"{p['spec_conc']:.4f}"])
    print(f"\nPhases CSV: {PHASES_CSV}")

    # Grid CSV
    with open(GRID_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["conf_min"] + [f"spec>={t2:.2f}" for t2 in spec_levels])
        for t1 in conf_levels:
            w.writerow([f"conf>={t1:.2f}"] + [grid[t1][t2] for t2 in spec_levels])
    print(f"Grid CSV: {GRID_CSV}")

    summary = {
        "method": "H101 v3: weave_colored_317_330 non-overlapping 60-frame phase analysis + H100 v4 guard 2D sensitivity",
        "stem": STEM,
        "visual_qa_verdict": "3-ball CASCADE pattern, active juggling throughout",
        "n_frames_with_detections": len(balls),
        "frame_range": [fmin, fmax],
        "phase_length": PHASE_LEN,
        "n_phases": len(phases),
        "phases": phases,
        "guard_thresholds_tested": {
            "conf_levels": conf_levels,
            "spec_levels": spec_levels,
        },
        "guard_grid": {str(t1): {str(t2): grid[t1][t2] for t2 in spec_levels}
                       for t1 in conf_levels},
        "perfect_cells": [{"conf_min": c, "spec_conc_min": s} for c, s in perfect_cells],
        "n_perfect_cells": len(perfect_cells),
        "flat_region_summary": (
            f"All {n_phases} phases pass with conf_min>={perfect_cells[0][0]:.2f} "
            f"AND spec_conc_min>={perfect_cells[0][1]:.2f} (and all weaker thresholds)."
            if perfect_cells else
            f"No cell passes all {n_phases} phases. Max passes: "
            f"{max(grid[t1][t2] for t1 in conf_levels for t2 in spec_levels)}/{n_phases}."
        ),
    }
    with open(SUMMARY_JSON, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Summary: {SUMMARY_JSON}")
    print(f"\nH101 v3 done.")


if __name__ == "__main__":
    main()
