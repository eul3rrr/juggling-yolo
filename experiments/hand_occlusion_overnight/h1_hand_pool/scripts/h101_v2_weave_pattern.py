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

Method (v2 — window-based phase detection):
1. Compute per-frame features from YOLO balls (no pose, no chain):
   - n_balls: count of YOLO sports ball detections
   - mean_conf: mean confidence of detections
   - min_conf: min confidence
   - spectral_concentration: FFT of the n_balls time series
2. Phase detection: rolling 30-frame window. Peak balls/frame in window
   is the "phase category".  Categorize by peak_balls: 0=NOTHING,
   1=ONE_BALL, 2=TWO_BALL, 3+=MULTI_BALL.  Adjacent windows with the
   same category form a phase.  Substantial phases: n_frames >= 5 windows
   (each window contributes 1 frame's "vote" so we accumulate).
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
PHASES_CSV = OUT_DIR / f"h101_v2_phases_{STEM}.csv"
SUMMARY_JSON = OUT_DIR / f"h101_v2_summary.json"
PER_FRAME_CSV = OUT_DIR / f"h101_v2_per_frame_{STEM}.csv"

WINDOW_SIZE = 30  # frames per phase-detection window
STEP_SIZE = 15    # step between consecutive windows
N_BALLS_HI = 3    # peak >= 3 => MULTI_BALL category


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


def cat_from_peak(peak):
    if peak == 0:
        return 0
    if peak == 1:
        return 1
    if peak == 2:
        return 2
    return 3


def cat_name(cat):
    return {0: "NOTHING", 1: "ONE_BALL", 2: "TWO_BALL", 3: "MULTI_BALL"}.get(cat, "?")


def main():
    print(f"=== H101 v2: weave_colored_317_330 window-based phase inference ===")
    balls = load_per_frame_balls()
    print(f"Loaded {len(balls)} frames with detections.")

    # Per-frame features
    per_frame = {}
    for frame in sorted(balls.keys()):
        dets = balls[frame]
        confs = [d[2] for d in dets]
        per_frame[frame] = {
            "n_balls": len(dets),
            "mean_conf": statistics.mean(confs),
            "min_conf": min(confs),
            "max_conf": max(confs),
        }

    # Build windows
    if not per_frame:
        print("No data.")
        return
    fmin, fmax = min(per_frame.keys()), max(per_frame.keys())
    windows = []  # list of (start, end, cat, peak_n, mean_n, mean_conf, n_det, n_total)
    for w_start in range(0, fmax + 1, STEP_SIZE):
        w_end = min(w_start + WINDOW_SIZE - 1, fmax)
        # Use a 1-step extension: at most 1 step beyond for last window
        if w_end - w_start < WINDOW_SIZE - 1 and w_start > 0:
            # Pad by extending backwards
            w_start = max(0, w_end - WINDOW_SIZE + 1)
        # Per-window stats
        peak = 0
        n_total = 0
        n_det = 0
        confs = []
        for f in range(w_start, w_end + 1):
            n = per_frame.get(f, {"n_balls": 0})["n_balls"]
            n_total += n
            if f in per_frame:
                n_det += 1
                confs.append(per_frame[f]["mean_conf"])
            peak = max(peak, n)
        mean_n = n_total / WINDOW_SIZE
        mean_conf = statistics.mean(confs) if confs else 0.0
        cat = cat_from_peak(peak)
        windows.append({
            "start": w_start, "end": w_end,
            "peak": peak, "cat": cat,
            "mean_n": mean_n, "mean_conf": mean_conf,
            "n_det": n_det,
        })
    print(f"Built {len(windows)} windows of {WINDOW_SIZE} frames (step {STEP_SIZE}).")

    # Phase detection: merge adjacent windows with same cat
    phases = []
    cur_cat = windows[0]["cat"]
    cur_start = windows[0]["start"]
    cur_end = windows[0]["end"]
    cur_window_indices = [0]
    for i in range(1, len(windows)):
        w = windows[i]
        if w["cat"] == cur_cat and w["start"] == cur_end + 1:
            cur_end = w["end"]
            cur_window_indices.append(i)
        else:
            phases.append({
                "cat": cur_cat,
                "start": cur_start,
                "end": cur_end,
                "n_windows": len(cur_window_indices),
                "n_frames": cur_end - cur_start + 1,
                "window_indices": list(cur_window_indices),
            })
            cur_cat = w["cat"]
            cur_start = w["start"]
            cur_end = w["end"]
            cur_window_indices = [i]
    phases.append({
        "cat": cur_cat, "start": cur_start, "end": cur_end,
        "n_windows": len(cur_window_indices),
        "n_frames": cur_end - cur_start + 1,
        "window_indices": list(cur_window_indices),
    })
    # Substantial filter: n_frames >= 30 (>= 1 window)
    SUB_MIN = 30
    substantial = [p for p in phases if p["n_frames"] >= SUB_MIN]
    print(f"\nAll phases: {len(phases)}")
    print(f"Substantial phases (n_frames >= {SUB_MIN}): {len(substantial)}")
    for p in substantial:
        confs = []
        n_balls = []
        for idx in p["window_indices"]:
            w = windows[idx]
            for f in range(w["start"], w["end"] + 1):
                if f in per_frame:
                    confs.append(per_frame[f]["mean_conf"])
                    n_balls.append(per_frame[f]["n_balls"])
        mean_conf = statistics.mean(confs) if confs else 0.0
        mean_n = statistics.mean(n_balls) if n_balls else 0.0
        std_n = statistics.stdev(n_balls) if len(n_balls) > 1 else 0.0
        spec_conc = compute_spectral_concentration(n_balls)
        p["mean_conf"] = mean_conf
        p["mean_n"] = mean_n
        p["std_n"] = std_n
        p["spec_conc"] = spec_conc
        print(f"  cat={cat_name(p['cat'])} f={p['start']}-{p['end']} n={p['n_frames']} "
              f"mean_conf={mean_conf:.3f} mean_n={mean_n:.2f} spec_conc={spec_conc:.3f}")

    # Apply H100 v4 conf+spec_conc guard
    GUARD_CONF_MIN = 0.50
    GUARD_SPEC_CONC_MIN = 0.13
    for p in substantial:
        conf_pass = p["mean_conf"] >= GUARD_CONF_MIN
        spec_pass = p["spec_conc"] >= GUARD_SPEC_CONC_MIN
        p["conf_pass"] = conf_pass
        p["spec_pass"] = spec_pass
        p["guard_pass"] = conf_pass and spec_pass

    n_passes = sum(1 for p in substantial if p["guard_pass"])
    n_fails_conf = sum(1 for p in substantial if not p["conf_pass"] and p["spec_pass"])
    n_fails_spec = sum(1 for p in substantial if p["conf_pass"] and not p["spec_pass"])
    n_fails_both = sum(1 for p in substantial if not p["conf_pass"] and not p["spec_pass"])
    print(f"\nH100 v4 conf+spec_conc guard results ({len(substantial)} substantial phases):")
    print(f"  Pass (JUGGLING): {n_passes}")
    print(f"  Fail conf only: {n_fails_conf}")
    print(f"  Fail spec only: {n_fails_spec}")
    print(f"  Fail both (low quality): {n_fails_both}")

    # Phases CSV
    with open(PHASES_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["phase_start", "phase_end", "n_frames", "n_balls_category",
                    "mean_conf", "mean_n_balls", "std_n_balls", "spectral_concentration",
                    "conf_pass", "spec_pass", "guard_pass"])
        for p in substantial:
            w.writerow([p["start"], p["end"], p["n_frames"],
                        cat_name(p["cat"]),
                        f"{p['mean_conf']:.4f}",
                        f"{p['mean_n']:.2f}",
                        f"{p['std_n']:.3f}",
                        f"{p['spec_conc']:.4f}",
                        p["conf_pass"], p["spec_pass"], p["guard_pass"]])
    print(f"\nPhases CSV: {PHASES_CSV}")

    # Per-frame CSV (just for reference)
    with open(PER_FRAME_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "n_balls", "mean_conf", "min_conf", "max_conf"])
        for f in sorted(per_frame.keys()):
            v = per_frame[f]
            w.writerow([f, v["n_balls"], f"{v['mean_conf']:.4f}",
                        f"{v['min_conf']:.4f}", f"{v['max_conf']:.4f}"])
    print(f"Per-frame features: {PER_FRAME_CSV}")

    summary = {
        "method": "H101 v2: weave_colored_317_330 window-based phase inference + H100 v4 conf+spec_conc guard",
        "stem": STEM,
        "n_frames_with_detections": len(per_frame),
        "frame_range": [fmin, fmax],
        "n_balls_distribution": dict(Counter(per_frame[f]["n_balls"] for f in per_frame)),
        "window_size": WINDOW_SIZE,
        "step_size": STEP_SIZE,
        "n_windows": len(windows),
        "n_substantial_phases": len(substantial),
        "sub_min": SUB_MIN,
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
        "phases": [
            {k: v for k, v in p.items() if k != "window_indices"}
            for p in substantial
        ],
    }
    with open(SUMMARY_JSON, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Summary: {SUMMARY_JSON}")
    print(f"\nH101 v2 done.")


if __name__ == "__main__":
    main()
