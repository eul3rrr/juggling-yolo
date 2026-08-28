#!/usr/bin/env python3
"""H12 v4/v5 post-hoc analysis: pattern phase detection, sensitivity grid,
side-by-side v2 vs v4 vs v5 comparison.

Builds on h12_v4_detector_signal.py and h12_v5_smoothed_signal.py outputs.
This script:

  1. Detects substantial pattern phases (n_frames >= 20) per video for
     v4 (instantaneous detector signal) and v5 (smoothed).
  2. Computes a sensitivity grid on W (smoothing window) in {5, 10, 20, 30}
     to test if the operating point is in a flat region.
  3. Writes a side-by-side comparison table:
     v2 (event-log) vs v4 (instantaneous detector) vs v5 (smoothed detector)
  4. Saves a JSON summary and a Markdown summary.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Sensitivity grid on smoothing window W
W_VALUES = [5, 10, 20, 30]


def load_tracklet_points(stem: str) -> dict:
    out = defaultdict(list)
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tid = int(r["track_id"])
            out[tid].append((int(r["frame"]), float(r["center_x"]),
                             float(r["center_y"])))
    for tid in out:
        out[tid].sort()
    return out


def per_frame_dirs(tracklets: dict) -> dict:
    """{frame: n_distinct_horiz_dirs}.

    A ball is "moving" if |vx| > 1.0 px/frame. A direction is +1 (right)
    or -1 (left). For frames with multiple balls, returns count of
    distinct horizontal directions (so 0, 1, or 2).
    """
    out = {}
    for tid, points in tracklets.items():
        for i, (f, x, y) in enumerate(points):
            if i == 0:
                continue
            prev_f, prev_x, _ = points[i - 1]
            vx = (x - prev_x) / max(1, f - prev_f)
            if abs(vx) > 1.0:
                if f not in out:
                    out[f] = set()
                out[f].add(1 if vx > 0 else -1)
    return {f: len(s) for f, s in out.items()}


def smooth_dirs(per_frame_dirs: dict, frames: list, W: int) -> dict:
    """{frame: median(n_distinct_horiz_dirs over +/-W frames)}."""
    out = {}
    for f in frames:
        neighbors = []
        for df in range(-W, W + 1):
            neighbors.append(per_frame_dirs.get(f + df, 0))
        neighbors.sort()
        n = len(neighbors)
        if n % 2 == 0:
            median = (neighbors[n // 2 - 1] + neighbors[n // 2]) / 2
        else:
            median = neighbors[n // 2]
        out[f] = int(median)
    return out


def classify_v5(smoothed_dirs: int, n_total: int,
                n_in_hand_left: int, n_in_hand_right: int) -> tuple:
    if n_total == 0:
        return "NO_BALL", 1.0
    if n_total == 1:
        return "SINGLE_BALL", 0.5
    if n_total == 2:
        if n_in_hand_left == 1 and n_in_hand_right == 1:
            return "TWO_BALL_HELD", 0.5
        return "TWO_BALL", 0.5
    if n_total >= 3:
        if smoothed_dirs == 2:
            return "CASCADE_3+_DETECTOR_SMOOTHED", 0.7
        if smoothed_dirs == 1:
            return "FOUNTAIN_3+_DETECTOR_SMOOTHED", 0.7
        if smoothed_dirs == 0:
            return "MIXED_3+_UNCONFIRMED", 0.3
        return "MIXED_3+", 0.4
    return "UNKNOWN", 0.0


def detect_phases(results: list[dict], min_frames: int = 20) -> list[dict]:
    """Find substantial pattern phases (n_frames >= min_frames).

    Returns list of {start_frame, end_frame, pattern, n_frames,
    avg_confidence, pct_pattern}.
    """
    phases = []
    if not results:
        return phases
    cur_pattern = results[0]["pattern"]
    cur_start = int(results[0]["frame"])
    cur_confs = [float(results[0]["confidence"])]

    def emit(end_frame):
        n_frames = end_frame - cur_start + 1
        if n_frames >= min_frames:
            phases.append({
                "start_frame": cur_start,
                "end_frame": end_frame,
                "pattern": cur_pattern,
                "n_frames": n_frames,
                "avg_confidence": sum(cur_confs) / len(cur_confs),
            })

    for r in results[1:]:
        if r["pattern"] == cur_pattern:
            cur_confs.append(float(r["confidence"]))
            continue
        emit(int(r["frame"]) - 1)
        cur_pattern = r["pattern"]
        cur_start = int(r["frame"])
        cur_confs = [float(r["confidence"])]
    emit(int(results[-1]["frame"]))
    return phases


def pct_distribution(rows: list[dict]) -> dict:
    n = len(rows)
    counts = Counter(r["pattern"] for r in rows)
    return {p: 100 * c / n for p, c in counts.items()}, dict(counts)


def main():
    summary = {"videos": {}, "sensitivity": {}}

    # Build per-W sensitivity for v5
    sens_v5 = {}
    for W in W_VALUES:
        sens_v5[W] = {}
        for stem in STEMS:
            tracklets = load_tracklet_points(stem)
            per_frame = per_frame_dirs(tracklets)
            census = {}
            with (H1_DATA / f"per_frame_census_{stem}.csv").open() as fh:
                for r in csv.DictReader(fh):
                    census[int(r["frame"])] = {
                        "n_in_hand_left": int(r["n_in_hand_left"]),
                        "n_in_hand_right": int(r["n_in_hand_right"]),
                        "n_total": int(r["n_total_balls"]),
                    }
            frames = sorted(census.keys())
            smoothed = smooth_dirs(per_frame, frames, W)
            results = []
            for f in frames:
                c = census[f]
                sd = smoothed.get(f, 0)
                pattern, conf = classify_v5(
                    sd, c["n_total"], c["n_in_hand_left"], c["n_in_hand_right"])
                results.append({"frame": f, "pattern": pattern,
                                "confidence": conf})
            pct, counts = pct_distribution(results)
            sens_v5[W][stem] = {
                "pct": pct,
                "counts": counts,
                "n_frames": len(results),
            }

    summary["sensitivity"] = sens_v5

    # Per-video analysis: v2 (event-log), v4 (instantaneous), v5 (smoothed)
    for stem in STEMS:
        # v2 (event-log)
        v2 = []
        with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v2.append(r)
        v2_pct, v2_counts = pct_distribution(v2)
        v2_phases = detect_phases(v2, min_frames=20)

        # v4 (instantaneous)
        v4 = []
        with (H1_DATA / f"pattern_inference_v4_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v4.append(r)
        v4_pct, v4_counts = pct_distribution(v4)
        v4_phases = detect_phases(v4, min_frames=20)

        # v5 (smoothed, W=10)
        v5 = []
        with (H1_DATA / f"pattern_inference_v5_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v5.append(r)
        v5_pct, v5_counts = pct_distribution(v5)
        v5_phases = detect_phases(v5, min_frames=20)

        # Late phase check (f=890-1050, the v2-misclassify zone)
        def late_pct(rows):
            late = [r for r in rows
                    if 890 <= int(r["frame"]) <= 1050]
            return pct_distribution(late)[0]

        v2_late = late_pct(v2)
        v4_late = late_pct(v4)
        v5_late = late_pct(v5)

        # CASCADE-class total (sanity: CASCADE_3+, CASCADE_3+_DETECTOR, etc.)
        def cascade_total(pct_dict):
            return sum(v for k, v in pct_dict.items() if "CASCADE" in k)
        def fountain_total(pct_dict):
            return sum(v for k, v in pct_dict.items() if "FOUNTAIN" in k)

        summary["videos"][stem] = {
            "v2_event_log": {"pct": v2_pct, "counts": v2_counts,
                              "n_substantial_phases": len(v2_phases),
                              "late_pct": v2_late},
            "v4_instantaneous": {"pct": v4_pct, "counts": v4_counts,
                                  "n_substantial_phases": len(v4_phases),
                                  "late_pct": v4_late},
            "v5_smoothed_W10": {"pct": v5_pct, "counts": v5_counts,
                                "n_substantial_phases": len(v5_phases),
                                "late_pct": v5_late},
            "cascade_pct": {
                "v2": cascade_total(v2_pct),
                "v4": cascade_total(v4_pct),
                "v5": cascade_total(v5_pct),
            },
            "fountain_pct": {
                "v2": fountain_total(v2_pct),
                "v4": fountain_total(v4_pct),
                "v5": fountain_total(v5_pct),
            },
        }

    out = H1_DATA / "h12_v4v5_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Saved: {out}")

    # Print compact comparison
    print()
    for stem in STEMS:
        v = summary["videos"][stem]
        print(f"=== {stem} ===")
        print(f"  v2 (event-log)         : CASCADE={v['cascade_pct']['v2']:.1f}%, "
              f"FOUNTAIN={v['fountain_pct']['v2']:.1f}%, "
              f"sub_phases={v['v2_event_log']['n_substantial_phases']}, "
              f"late_3+={sum(v['v2_event_log']['late_pct'].get(k, 0) for k in v['v2_event_log']['late_pct'] if '3+' in k):.1f}%")
        print(f"  v4 (instantaneous)     : CASCADE={v['cascade_pct']['v4']:.1f}%, "
              f"FOUNTAIN={v['fountain_pct']['v4']:.1f}%, "
              f"sub_phases={v['v4_instantaneous']['n_substantial_phases']}, "
              f"late_3+={sum(v['v4_instantaneous']['late_pct'].get(k, 0) for k in v['v4_instantaneous']['late_pct'] if '3+' in k):.1f}%")
        print(f"  v5 (smoothed W=10)     : CASCADE={v['cascade_pct']['v5']:.1f}%, "
              f"FOUNTAIN={v['fountain_pct']['v5']:.1f}%, "
              f"sub_phases={v['v5_smoothed_W10']['n_substantial_phases']}, "
              f"late_3+={sum(v['v5_smoothed_W10']['late_pct'].get(k, 0) for k in v['v5_smoothed_W10']['late_pct'] if '3+' in k):.1f}%")
        print(f"  late phase (f=890-1050) CASCADE/FOUNTAIN split:")
        for vname, vpct in [("v2", v2_late), ("v4", v4_late), ("v5", v5_late)]:
            cs = {k: round(v, 1) for k, v in vpct.items()
                  if "CASCADE" in k or "FOUNTAIN" in k or "MIXED" in k}
            print(f"    {vname}: {cs}")

    # Sensitivity grid print
    print()
    print("=== W (smoothing window) sensitivity on identical ===")
    for W in W_VALUES:
        s = sens_v5[W]["identical_balls_trick_000_018"]
        print(f"  W={W:2d}: CASCADE={s['pct'].get('CASCADE_3+_DETECTOR_SMOOTHED', 0):.1f}%, "
              f"FOUNTAIN={s['pct'].get('FOUNTAIN_3+_DETECTOR_SMOOTHED', 0):.1f}%, "
              f"MIXED_UNCONFIRMED={s['pct'].get('MIXED_3+_UNCONFIRMED', 0):.1f}%")


if __name__ == "__main__":
    main()
