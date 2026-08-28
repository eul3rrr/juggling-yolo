#!/usr/bin/env python3
"""H66 - Continuous "balls aloft" (A) signal as FOUNTAIN_3+ post-filter.

H65 found that H12 v8 FOUNTAIN_3+ accuracy is only 43% on the 7
substantial FOUNTAIN_3+ phases (3/7 = FOUNTAIN, 4/7 = OTHER or CASCADE).
The 4 wrong cases break down as:
- 2 OTHER (static hold / trick) on identical (890-936, 1029-1049)
- 1 OTHER (static hold) on YouTube (482-594)
- 1 CASCADE (alt-hand) on YouTube (800-861)

H43 (H12 v8 confidence < 0.55) is a high-precision post-filter but
low-recall: only 1/4 wrong-on-identical has conf < 0.55.

HYPOTHESIS:
A real FOUNTAIN_3+ phase has multiple balls aloft in the air at any
given time (the signature of synchronized parallel throws). A static
hold has 0-1 balls aloft (because the balls are in the hands). A
CASCADE has fewer balls aloft because hands alternate.

A per-frame "balls aloft" (A) count — derived from YOLO detections
that are NOT within reach of either hand — should discriminate
"FOUNTAIN" from "HOLD" and "CASCADE".

ALGORITHM:
1. Load per-frame YOLO detections and pose wrist positions.
2. For each frame, compute:
   - L = # balls within 100 px of left wrist
   - R = # balls within 100 px of right wrist
   - A = # balls NOT within 100 px of either wrist
3. For each substantial FOUNTAIN_3+ phase (>= 20 frames), compute:
   - mean_A, pct_A_ge2 (fraction of frames with >= 2 balls aloft)
   - max_A, min_A
4. Test a threshold on pct_A_ge2: phases below threshold are
   rejected (re-labeled as NOT_FOUNTAIN).
5. Compare H66-rejected vs H65-visual-verdict and H43-rejected.

Output:
  - data/h66_phases_*.csv (per-phase A statistics)
  - data/h66_rejected_phases_*.csv (phases below threshold)
  - data/h66_summary.json
  - reports/h66_report.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
DET_DIR = PROJECT / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H66 thresholds
HAND_REACH = 100.0  # px
# Threshold: fraction of frames with >= 2 balls aloft to call it FOUNTAIN
# Initial guess based on H65 analysis: FOUNTAIN mean 46.3%, OTHER mean 28.8%
PCT_A_GE2_THRESHOLD = 0.30  # below 30% = NOT_FOUNTAIN (drop)


def load_pose(stem: str) -> dict:
    pose_path = DET_DIR / f"{stem}_yolo26s-pose.csv"
    by_frame = {}
    for r in csv.DictReader(open(pose_path)):
        f = int(r["frame"])
        lx = float(r["left_wrist_x"])
        ly = float(r["left_wrist_y"])
        lc = float(r["left_wrist_confidence"])
        rx = float(r["right_wrist_x"])
        ry = float(r["right_wrist_y"])
        rc = float(r["right_wrist_confidence"])
        lw = (lx, ly) if lc >= 0.3 else None
        rw = (rx, ry) if rc >= 0.3 else None
        by_frame[f] = (lw, rw)
    return by_frame


def load_dets(stem: str) -> dict:
    det_path = DET_DIR / f"{stem}_norfair_dt50_hc5.csv"
    by_frame = defaultdict(list)
    for r in csv.DictReader(open(det_path)):
        f = int(r["frame"])
        x = float(r["center_x"])
        y = float(r["center_y"])
        c = float(r["confidence"])
        if c >= 0.5:
            by_frame[f].append((x, y, c))
    return by_frame


def per_frame_A(pose: dict, dets: dict, start: int, end: int) -> list[int]:
    """For each frame in [start, end], return # balls aloft (A)."""
    A_per_frame = []
    for f in range(start, end + 1):
        if f not in pose or f not in dets:
            continue
        lw, rw = pose[f]
        frame_dets = dets.get(f, [])
        A = 0
        for (x, y, c) in frame_dets:
            d_l = ((x - lw[0])**2 + (y - lw[1])**2)**0.5 if lw else 9999
            d_r = ((x - rw[0])**2 + (y - rw[1])**2)**0.5 if rw else 9999
            if min(d_l, d_r) > HAND_REACH:
                A += 1
        A_per_frame.append(A)
    return A_per_frame


def load_fountain_phases(stem: str) -> list[tuple]:
    """Load substantial FOUNTAIN_3+ phases (>= 20 frames) from H50-filtered
    pattern_phases CSV. Returns list of (start, end, n, mean_conf) tuples.
    """
    path = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(path)):
        if row["pattern"] == "FOUNTAIN_3+":
            n = int(row["n_frames"])
            if n >= 20:
                out.append((
                    int(row["start_frame"]),
                    int(row["end_frame"]),
                    n,
                    float(row["avg_confidence"]),
                ))
    return sorted(out, key=lambda x: x[0])


def main() -> None:
    summary = {"videos": {}}

    for stem in STEMS:
        print(f"\n=== {stem} ===")
        pose = load_pose(stem)
        dets = load_dets(stem)
        phases = load_fountain_phases(stem)
        print(f"  found {len(phases)} substantial FOUNTAIN_3+ phases (>= 20 frames)")

        # Per-phase A statistics
        per_phase = []
        for start, end, n, conf in phases:
            A = per_frame_A(pose, dets, start, end)
            n_real = len(A)
            if n_real == 0:
                continue
            mean_A = sum(A) / n_real
            max_A = max(A)
            pct_A_ge2 = sum(1 for a in A if a >= 2) / n_real
            pct_A_ge1 = sum(1 for a in A if a >= 1) / n_real
            rejected = pct_A_ge2 < PCT_A_GE2_THRESHOLD
            per_phase.append({
                "phase_start": start,
                "phase_end": end,
                "n_frames": n,
                "mean_confidence": round(conf, 3),
                "mean_A": round(mean_A, 3),
                "max_A": max_A,
                "pct_A_ge1": round(pct_A_ge1, 3),
                "pct_A_ge2": round(pct_A_ge2, 3),
                "h66_rejected": rejected,
            })
            print(f"  phase f={start}-{end}, n={n}, conf={conf:.3f}, "
                  f"mean_A={mean_A:.2f}, max_A={max_A}, "
                  f"pct_A_ge2={pct_A_ge2:.2%} "
                  f"{'REJECT' if rejected else 'KEEP'}")

        # Write per-phase CSV
        out_csv = H1_DATA / f"h66_phases_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(per_phase)
        print(f"  wrote: {out_csv.name}")

        # Write rejected CSV
        rejected = [p for p in per_phase if p["h66_rejected"]]
        out_rej = H1_DATA / f"h66_rejected_phases_{stem}.csv"
        with out_rej.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(rejected)
        print(f"  wrote: {out_rej.name} ({len(rejected)} rejected)")

        summary["videos"][stem] = {
            "n_phases": len(per_phase),
            "n_rejected": len(rejected),
            "rejection_rate": round(len(rejected) / len(per_phase), 3) if per_phase else 0,
            "phases": per_phase,
        }

    summary["methodology"] = {
        "filter": "h66: continuous balls-aloft pct_A_ge2 >= PCT_A_GE2_THRESHOLD",
        "PCT_A_GE2_THRESHOLD": PCT_A_GE2_THRESHOLD,
        "HAND_REACH": HAND_REACH,
        "n_total_phases": sum(s["n_phases"] for s in summary["videos"].values()),
        "n_total_rejected": sum(s["n_rejected"] for s in summary["videos"].values()),
    }

    out = H1_DATA / "h66_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
