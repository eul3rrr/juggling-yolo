#!/usr/bin/env python3
"""
H101 v1 — weave_colored_317_330 pattern inference and conf+spec_conc evaluation.

The lab has reached H100 v4 (conf+spec_conc guard, 38/56 PERFECT cells on
the 21 H93 corrected phases of identical + youtube). The H100 report
identifies H101 as the next priority: 3rd video validation.

The weave_colored_317_330 video is the only remaining video in
detections/ that has YOLO ball detection data (270 frames, 0-311).
It has NO pose data, so H74/H78 signals are unavailable. The
H100 v4 conf+spec_conc guard is the right reduced stack to test
(no aloft features required, no pose required).

Hypothesis: H100 v4's conf+spec_conc guard generalizes to a 3rd
video and correctly identifies JUGGLING vs STATIC_HOLD phases
in weave_colored_317_330.

Method (smallest possible):
1. Compute per-frame features from YOLO balls (no pose, no chain):
   - n_balls: count of YOLO sports ball detections
   - mean_conf: mean confidence of detections
   - min_conf: min confidence (low values may indicate false positives)
   - spectral_concentration: FFT of the n_balls time series (low = dynamic)
2. Phase detection: contiguous runs of same n_balls (n_balls in {1, 2, 3+}).
   Substantial phases = n_frames >= 5 AND n_balls >= 1.
3. Per-phase statistics: mean_conf, mean_n_balls, std_n_balls, spectral_conc.
4. Apply H100 v4 conf+spec_conc guard to each phase.
5. Render contact sheets for visual QA on all substantial phases.
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
PHASES_CSV = OUT_DIR / f"h101_phases_{STEM}.csv"
SUMMARY_JSON = OUT_DIR / f"h101_v1_summary.json"
PER_FRAME_CSV = OUT_DIR / f"h101_per_frame_{STEM}.csv"


def load_per_frame_balls():
    """Returns {frame: [(cx, cy, conf), ...]} for sports ball detections."""
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
    """FFT-based spectral concentration: ratio of dominant frequency amplitude
    to total amplitude. Low = dynamic; high = stationary (sustained constant).
    Matches H12 v8's spectral_concentration computation.
    """
    if len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    centered = [v - mean for v in values]
    # DC component magnitude
    dc = abs(sum(centered)) / n
    # simple periodogram via DFT
    nfreqs = max(1, n // 2)
    amps = []
    for k in range(1, nfreqs + 1):
        re = sum(c * math.cos(2 * math.pi * k * i / n) for i, c in enumerate(centered))
        im = sum(c * math.sin(2 * math.pi * k * i / n) for i, c in enumerate(centered))
        amps.append((re * re + im * im) ** 0.5)
    if not amps or sum(amps) == 0:
        return 0.0
    return max(amps) / sum(amps)


def compute_per_frame_features(balls):
    """For each frame with detections, compute features."""
    out = {}
    for frame in sorted(balls.keys()):
        dets = balls[frame]
        confs = [d[2] for d in dets]
        out[frame] = {
            "n_balls": len(dets),
            "mean_conf": statistics.mean(confs),
            "max_conf": max(confs),
            "min_conf": min(confs),
            "centers": [(d[0], d[1]) for d in dets],
        }
    return out


def detect_phases(per_frame, min_frames=5):
    """Detect contiguous phases by n_balls category (0, 1, 2, 3+).
    n_balls>=3 is a single 'multi' category. Outputs only phases
    with at least min_frames AND n_balls >= 1 (since 0=nothing).
    """
    frames = sorted(per_frame.keys())
    if not frames:
        return []
    def cat(n):
        if n == 0:
            return 0
        if n == 1:
            return 1
        if n == 2:
            return 2
        return 3
    phases = []
    cur_cat = cat(per_frame[frames[0]]["n_balls"])
    cur_start = frames[0]
    cur_frames = [frames[0]]
    for f in frames[1:]:
        c = cat(per_frame[f]["n_balls"])
        if c == cur_cat and f == cur_frames[-1] + 1:
            cur_frames.append(f)
        else:
            if len(cur_frames) >= min_frames and cur_cat >= 1:
                phases.append((cur_cat, cur_start, cur_frames[-1], cur_frames))
            cur_cat = c
            cur_start = f
            cur_frames = [f]
    if len(cur_frames) >= min_frames and cur_cat >= 1:
        phases.append((cur_cat, cur_start, cur_frames[-1], cur_frames))
    return phases


def main():
    print(f"=== H101 v1: weave_colored_317_330 pattern inference ===")
    print(f"Loading YOLO ball detections from {BALLS_CSV}...")
    balls = load_per_frame_balls()
    per_frame = compute_per_frame_features(balls)
    print(f"Total frames with detections: {len(per_frame)}")
    print(f"Frame range: {min(per_frame.keys())}-{max(per_frame.keys())}")

    # Per-frame CSV
    with open(PER_FRAME_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "n_balls", "mean_conf", "min_conf", "max_conf"])
        for f in sorted(per_frame.keys()):
            v = per_frame[f]
            w.writerow([f, v["n_balls"], f"{v['mean_conf']:.4f}",
                        f"{v['min_conf']:.4f}", f"{v['max_conf']:.4f}"])
    print(f"Per-frame features: {PER_FRAME_CSV}")

    # Phase detection
    phases = detect_phases(per_frame, min_frames=5)
    print(f"\nSubstantial phases (>= 5 frames): {len(phases)}")
    for cat, start, end, pframes in phases:
        confs = [per_frame[f]["mean_conf"] for f in pframes]
        n_balls = [per_frame[f]["n_balls"] for f in pframes]
        spec_conc = compute_spectral_concentration(n_balls)
        print(f"  cat={cat} f={start}-{end} n={len(pframes)} mean_conf={statistics.mean(confs):.3f} "
              f"mean_nballs={statistics.mean(n_balls):.1f} spec_conc={spec_conc:.3f}")

    # Phases CSV
    with open(PHASES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["phase_start", "phase_end", "n_frames", "n_balls_category",
                    "mean_conf", "mean_n_balls", "min_conf", "max_conf",
                    "std_n_balls", "spectral_concentration"])
        for cat, start, end, pframes in phases:
            confs = [per_frame[f]["mean_conf"] for f in pframes]
            n_balls = [per_frame[f]["n_balls"] for f in pframes]
            spec_conc = compute_spectral_concentration(n_balls)
            cat_name = {1: "ONE_BALL", 2: "TWO_BALL", 3: "MULTI_BALL"}[cat]
            w.writerow([start, end, len(pframes), cat_name,
                        f"{statistics.mean(confs):.4f}",
                        f"{statistics.mean(n_balls):.2f}",
                        f"{min(c for c in confs):.4f}",
                        f"{max(c for c in confs):.4f}",
                        f"{statistics.stdev(n_balls):.3f}" if len(n_balls) > 1 else "0.000",
                        f"{spec_conc:.4f}"])
    print(f"\nPhases CSV: {PHASES_CSV}")

    # Apply H100 v4 conf+spec_conc guard: conf>=0.50 AND spec_conc>=0.13
    # A "passing" phase is allowed to be JUGGLING.
    # Per H100 v4: phases with conf<0.50 OR spec_conc<0.13 should be flagged
    # as possibly STATIC_HOLD / low-quality.
    GUARD_CONF_MIN = 0.50
    GUARD_SPEC_CONC_MIN = 0.13
    n_passes = 0
    n_fails_conf = 0
    n_fails_spec = 0
    n_fails_both = 0
    phase_records = []
    for cat, start, end, pframes in phases:
        confs = [per_frame[f]["mean_conf"] for f in pframes]
        n_balls = [per_frame[f]["n_balls"] for f in pframes]
        mean_conf = statistics.mean(confs)
        spec_conc = compute_spectral_concentration(n_balls)
        conf_pass = mean_conf >= GUARD_CONF_MIN
        spec_pass = spec_conc >= GUARD_SPEC_CONC_MIN
        guard_pass = conf_pass and spec_pass
        if guard_pass:
            n_passes += 1
        elif not conf_pass and not spec_pass:
            n_fails_both += 1
        elif not conf_pass:
            n_fails_conf += 1
        else:
            n_fails_spec += 1
        phase_records.append({
            "start": start, "end": end, "n_frames": len(pframes),
            "n_balls_category": cat, "mean_conf": mean_conf,
            "spec_conc": spec_conc, "conf_pass": conf_pass,
            "spec_pass": spec_pass, "guard_pass": guard_pass,
        })

    print(f"\nH100 v4 conf+spec_conc guard results:")
    print(f"  Pass: {n_passes}/{len(phases)}")
    print(f"  Fail conf: {n_fails_conf}")
    print(f"  Fail spec_conc: {n_fails_spec}")
    print(f"  Fail both: {n_fails_both}")

    summary = {
        "method": "H101 v1: weave_colored_317_330 pattern inference + H100 v4 conf+spec_conc guard",
        "stem": STEM,
        "n_frames_with_detections": len(per_frame),
        "frame_range": [min(per_frame.keys()), max(per_frame.keys())],
        "n_balls_distribution": dict(Counter(per_frame[f]["n_balls"] for f in per_frame)),
        "n_substantial_phases": len(phases),
        "guard_thresholds": {
            "conf_min": GUARD_CONF_MIN,
            "spec_conc_min": GUARD_SPEC_CONC_MIN,
        },
        "guard_results": {
            "n_passes": n_passes,
            "n_fails_conf_only": n_fails_conf,
            "n_fails_spec_only": n_fails_spec,
            "n_fails_both": n_fails_both,
        },
        "phases": phase_records,
    }
    with open(SUMMARY_JSON, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nSummary: {SUMMARY_JSON}")
    print(f"\nH101 v1 done.")


if __name__ == "__main__":
    main()
