#!/usr/bin/env python3
"""H40 - continuous per-frame hand-occupancy signal from raw detector
+ pose data (NOT chain-driven).

HYPOTHESIS:
  H36 only emits hand-occupancy state at chain events. H39 v1/v2
  over-rejected real FOUNTAIN_3+ phases because H36 reports HOLD
  state during chain-event gaps even when the juggler's hands ARE
  occupied.

  A continuous per-frame hand-occupancy signal — checking for any
  detected ball within hand reach (108 px) of either wrist at
  every frame — would be a more reliable signal.

EXPECTED:
  - 50-80% of frames in h7v3plus3 chains have a hand-occupancy
    signal (some HOLD frames because of detector dropouts)
  - The signal correlates with CASCADE_3+ (high) and FOUNTAIN_3+
    (mixed) pattern classifications
  - This signal is independent of H36 chain events

ALGORITHM:
  1. Load pose data (wrist positions per frame)
  2. Load detector data (ball positions per frame)
  3. For each frame, find all detected balls within 108 px of
     left or right wrist
  4. If L=0: no ball within 108 px of left wrist
     If L=1: exactly 1 ball within 108 px of left wrist
     (similarly for R)
  5. Per-frame (L, R, A_continuous) state where
     A_continuous = total_balls - L - R
  6. Compare with H36 chain-driven state
  7. Compare with H12 v8 pattern labels
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

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Thresholds (declared from physical geometry)
HAND_REACH_PX = 108.0


def load_pose(stem: str) -> dict:
    """Return {frame: (left_wrist, right_wrist, l_conf, r_conf)}
    where wrist is (x, y) or None if missing."""
    pose_path = PROJECT / "detections" / f"{stem}_yolo26s-pose.csv"
    if not pose_path.exists():
        return {}
    by_frame = {}
    with pose_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            lx = float(r["left_wrist_x"])
            ly = float(r["left_wrist_y"])
            lc = float(r["left_wrist_confidence"])
            rx = float(r["right_wrist_x"])
            ry = float(r["right_wrist_y"])
            rc = float(r["right_wrist_confidence"])
            lw = (lx, ly) if lc >= 0.3 else None
            rw = (rx, ry) if rc >= 0.3 else None
            by_frame[f] = (lw, rw, lc, rc)
    return by_frame


def load_detections(stem: str) -> dict:
    """Return {frame: [(x, y, conf), ...]} for all detected balls
    (use norfair_dt50_hc5 — the production detector used in H7)."""
    det_path = PROJECT / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    if not det_path.exists():
        return {}
    by_frame = defaultdict(list)
    with det_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            x = float(r["center_x"])
            y = float(r["center_y"])
            c = float(r["confidence"])
            if c >= 0.3:  # only confident detections
                by_frame[f].append((x, y, c))
    return by_frame


def continuous_hand_occupancy(pose: dict, dets: dict, hand_reach: float = HAND_REACH_PX
                              ) -> dict:
    """For each frame, compute (L, R, A_continuous) based on
    detector + pose proximity. L = balls within hand_reach of left
    wrist, R = balls within hand_reach of right wrist.

    A frame with no detections (or no pose) returns L=R=0 and
    A_continuous = None.
    """
    out = {}
    all_frames = set(pose.keys()) | set(dets.keys())
    for f in all_frames:
        lw, rw, lc, rc = pose.get(f, (None, None, 0.0, 0.0))
        frame_dets = dets.get(f, [])
        if not frame_dets:
            out[f] = (0, 0, 0, None, None)
            continue
        L = 0
        R = 0
        n_dets = len(frame_dets)
        for (x, y, c) in frame_dets:
            if lw is not None:
                d_l = ((x - lw[0]) ** 2 + (y - lw[1]) ** 2) ** 0.5
                if d_l <= hand_reach:
                    L += 1
                    continue  # only count once per ball (left wins over right)
            if rw is not None:
                d_r = ((x - rw[0]) ** 2 + (y - rw[1]) ** 2) ** 0.5
                if d_r <= hand_reach:
                    R += 1
        A = max(0, n_dets - L - R)
        out[f] = (L, R, A, n_dets, n_dets)
    return out


def load_h36(stem: str) -> dict:
    """Load H36 (L, R, A) state per frame."""
    out = {}
    with (H1_DATA / f"h36_per_frame_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (int(r["L"]), int(r["R"]), int(r["A"]))
    return out


def load_h12v8(stem: str) -> dict:
    """Load H12 v8 pattern per frame."""
    out = {}
    with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (r["pattern"], float(r["confidence"]))
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H40: continuous hand-occupancy) ===")
        pose = load_pose(stem)
        dets = load_detections(stem)
        h36 = load_h36(stem)
        h12 = load_h12v8(stem)
        if not pose:
            print(f"  no pose data found")
            continue
        if not dets:
            print(f"  no detection data found")
            continue
        print(f"  pose frames: {len(pose)}")
        print(f"  detection frames: {len(dets)} (with at least 1 det)")

        # Compute continuous state
        cont = continuous_hand_occupancy(pose, dets)
        all_frames = sorted(cont.keys())
        print(f"  continuous state frames: {len(all_frames)}")

        # Aggregate stats
        n_with_l = sum(1 for f in all_frames if cont[f][0] > 0)
        n_with_r = sum(1 for f in all_frames if cont[f][1] > 0)
        n_with_any = sum(1 for f in all_frames if cont[f][0] > 0 or cont[f][1] > 0)
        n_total = len(all_frames)
        print(f"  Frames with L>0: {n_with_l} ({n_with_l*100/n_total:.1f}%)")
        print(f"  Frames with R>0: {n_with_r} ({n_with_r*100/n_total:.1f}%)")
        print(f"  Frames with L>0 or R>0: {n_with_any} ({n_with_any*100/n_total:.1f}%)")

        # Compare with H36
        n_h36_l = sum(1 for f in all_frames if h36.get(f, (0, 0, 0))[0] > 0)
        n_h36_r = sum(1 for f in all_frames if h36.get(f, (0, 0, 0))[1] > 0)
        n_h36_any = sum(1 for f in all_frames if h36.get(f, (0, 0, 0))[0] > 0
                        or h36.get(f, (0, 0, 0))[1] > 0)
        print(f"\n  H36 chain-driven state (for comparison):")
        print(f"    Frames with L>0: {n_h36_l} ({n_h36_l*100/n_total:.1f}%)")
        print(f"    Frames with R>0: {n_h36_r} ({n_h36_r*100/n_total:.1f}%)")
        print(f"    Frames with L>0 or R>0: {n_h36_any} ({n_h36_any*100/n_total:.1f}%)")

        # Compare with H12 v8 patterns
        n_by_pattern = defaultdict(int)
        n_by_pattern_with_occ = defaultdict(int)
        for f in all_frames:
            p = h12.get(f, (None, 0))[0]
            if p:
                n_by_pattern[p] += 1
                if cont[f][0] > 0 or cont[f][1] > 0:
                    n_by_pattern_with_occ[p] += 1
        print(f"\n  H40 hand-occupancy rate by H12 v8 pattern:")
        for p, n in sorted(n_by_pattern.items(), key=lambda x: -x[1]):
            if n > 0:
                rate = n_by_pattern_with_occ[p] * 100 / n
                print(f"    {p}: {n_by_pattern_with_occ[p]}/{n} = {rate:.1f}%")

        # Write per-frame output
        out_csv = H1_DATA / f"h40_continuous_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = ["frame", "L40", "R40", "A40", "n_dets", "L36", "R36", "A36",
                          "h12_pattern", "h12_conf"]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for f in all_frames:
                L40, R40, A40, n_dets, _ = cont[f]
                L36, R36, A36 = h36.get(f, (0, 0, 0))
                pat, conf = h12.get(f, ("", 0.0))
                w.writerow({"frame": f, "L40": L40, "R40": R40, "A40": A40,
                            "n_dets": n_dets, "L36": L36, "R36": R36, "A36": A36,
                            "h12_pattern": pat, "h12_conf": conf})
        print(f"  wrote: {out_csv.name} ({len(all_frames)} rows)")

        summary["videos"][stem] = {
            "n_frames": n_total,
            "n_with_L40": n_with_l,
            "n_with_R40": n_with_r,
            "n_with_any40": n_with_any,
            "n_with_L36": n_h36_l,
            "n_with_R36": n_h36_r,
            "n_with_any36": n_h36_any,
            "pattern_occupancy_rate": {
                p: round(n_by_pattern_with_occ[p] * 100 / max(1, n), 1)
                for p, n in n_by_pattern.items()
            },
        }

    out = H1_DATA / "h40_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
