#!/usr/bin/env python3
"""H68 - per-n_total threshold calibration for H66 + H43 stacked.

H67 (end-to-end impact) found that H66 at threshold 0.30 is too
strict for 3-ball FOUNTAIN (loses the 977-1011 real FOUNTAIN).
H67 recommended lowering to 0.20.

H68: test a per-n_total threshold (different threshold for 3-ball
and 5-ball FOUNTAIN) to maximize precision on rejects without
losing real FOUNTAIN.

HYPOTHESIS:
A per-n_total threshold should catch 2/4 wrong FOUNTAIN_3+ phases:
- 3-ball: threshold 0.20 catches 1029-1049 (static hold), preserves
  977-1011 (real FOUNTAIN with only 1 ball aloft at a time).
- 5-ball: threshold 0.45 catches 800-861 (alt-hand CASCADE), preserves
  339-374 (real FOUNTAIN with 2-3 balls aloft).

The 482-594 (static hold) cannot be caught by H66 (YOLO false
positives on background features per H4).

The 890-936 (crossed-arm trick) cannot be caught by H66 (arms cross
above hands look like "balls aloft" to YOLO).

So H43 + H66 (per-n_total) should catch 2/4 wrong cases at 0% false
rejects on real FOUNTAIN.

METHOD:
1. Reject FOUNTAIN_3+ phases if:
   - 3-ball (n_total=3): pct_A_ge2 < 0.20 (or conf < 0.55 via H43)
   - 5-ball (n_total=5): pct_A_ge2 < 0.45 (or conf < 0.55 via H43)
2. Apply to H65 sample (7 phases) and compute precision/recall.
3. Apply to H50-filtered per-frame pattern data and measure end-to-end
   impact.

Output:
  - data/h68_phases_*.csv
  - data/h68_rejected_phases_*.csv
  - data/h68_per_frame_*.csv
  - data/h68_summary.json
  - reports/h68_report.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DET_DIR = PROJECT / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H68 per-n_total thresholds
H43_CONF_THRESHOLD = 0.55
PCT_A_GE2_THRESHOLDS = {
    3: 0.20,  # 3-ball FOUNTAIN
    5: 0.45,  # 5-ball FOUNTAIN
}
HAND_REACH = 100.0  # px


def load_pose(stem: str) -> dict:
    pose_path = DET_DIR / f"{stem}_yolo26s-pose.csv"
    by_frame = {}
    for r in csv.DictReader(open(pose_path)):
        f = int(r["frame"])
        lx = float(r["left_wrist_x"]); ly = float(r["left_wrist_y"]); lc = float(r["left_wrist_confidence"])
        rx = float(r["right_wrist_x"]); ry = float(r["right_wrist_y"]); rc = float(r["right_wrist_confidence"])
        lw = (lx, ly) if lc >= 0.3 else None
        rw = (rx, ry) if rc >= 0.3 else None
        by_frame[f] = (lw, rw)
    return by_frame


def load_dets(stem: str) -> dict:
    det_path = DET_DIR / f"{stem}_norfair_dt50_hc5.csv"
    by_frame = defaultdict(list)
    for r in csv.DictReader(open(det_path)):
        f = int(r["frame"])
        x = float(r["center_x"]); y = float(r["center_y"]); c = float(r["confidence"])
        if c >= 0.5:
            by_frame[f].append((x, y, c))
    return by_frame


def per_frame_A(pose: dict, dets: dict, start: int, end: int) -> list[int]:
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
    # n_total is 3 for identical, 5 for YouTube
    n_total_per_stem = {
        "identical_balls_trick_000_018": 3,
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 5,
    }

    summary = {"videos": {}}

    for stem in STEMS:
        print(f"\n=== {stem} (n_total={n_total_per_stem[stem]}) ===")
        n_total = n_total_per_stem[stem]
        threshold = PCT_A_GE2_THRESHOLDS[n_total]
        print(f"  H68 pct_A_ge2 threshold for n_total={n_total}: {threshold}")

        pose = load_pose(stem)
        dets = load_dets(stem)
        phases = load_fountain_phases(stem)
        print(f"  {len(phases)} substantial FOUNTAIN_3+ phases (>= 20 frames)")

        per_phase = []
        for start, end, n, conf in phases:
            A = per_frame_A(pose, dets, start, end)
            n_real = len(A)
            if n_real == 0:
                continue
            mean_A = sum(A) / n_real
            max_A = max(A)
            pct_A_ge2 = sum(1 for a in A if a >= 2) / n_real
            h43_rej = conf < H43_CONF_THRESHOLD
            h66_rej = pct_A_ge2 < threshold
            h68_rej = h43_rej or h66_rej
            per_phase.append({
                "phase_start": start,
                "phase_end": end,
                "n_frames": n,
                "n_total": n_total,
                "mean_confidence": round(conf, 3),
                "mean_A": round(mean_A, 3),
                "max_A": max_A,
                "pct_A_ge2": round(pct_A_ge2, 3),
                "threshold": threshold,
                "h43_rejected": h43_rej,
                "h66_rejected": h66_rej,
                "h68_rejected": h68_rej,
            })
            print(f"  phase f={start}-{end}, n={n}, conf={conf:.3f}, "
                  f"pct_A_ge2={pct_A_ge2:.2%} (thr={threshold}), "
                  f"H43={'R' if h43_rej else 'K'} H66={'R' if h66_rej else 'K'} "
                  f"H68={'REJECT' if h68_rej else 'KEEP'}")

        out_csv = H1_DATA / f"h68_phases_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(per_phase)

        rejected = [p for p in per_phase if p["h68_rejected"]]
        out_rej = H1_DATA / f"h68_rejected_phases_{stem}.csv"
        with out_rej.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
            w.writeheader()
            w.writerows(rejected)

        summary["videos"][stem] = {
            "n_phases": len(per_phase),
            "n_rejected": len(rejected),
            "n_total": n_total,
            "threshold": threshold,
            "phases": per_phase,
        }

    # End-to-end per-frame impact
    print("\n=== Per-frame end-to-end impact ===")
    summary["end_to_end"] = {}
    for stem in STEMS:
        n_total = n_total_per_stem[stem]
        threshold = PCT_A_GE2_THRESHOLDS[n_total]
        h68_rej_phases = {(int(p["phase_start"]), int(p["phase_end"]))
                          for p in summary["videos"][stem]["phases"]
                          if p["h68_rejected"]}

        per_frame_path = H1_DATA / f"pattern_inference_h50_{stem}.csv"
        rows = list(csv.DictReader(open(per_frame_path)))

        out_pf = H1_DATA / f"h68_per_frame_{stem}.csv"
        with out_pf.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "h50_pattern", "h50_confidence", "h68_pattern",
                        "h43_rejected", "h66_rejected", "h68_rejected"])
            n_changed = 0
            for r in rows:
                frame = int(r["frame"])
                pattern = r["pattern"]
                conf = float(r["confidence"])
                h43 = "yes" if (pattern == "FOUNTAIN_3+" and conf < H43_CONF_THRESHOLD) else "no"
                h66 = "no"
                for (s, e) in h68_rej_phases:
                    if s <= frame <= e and pattern == "FOUNTAIN_3+":
                        h66 = "yes"
                        break
                new = pattern
                if h43 == "yes" or h66 == "yes":
                    new = "FOUNTAIN_LOW_CONF"
                    n_changed += 1
                w.writerow([frame, pattern, f"{conf:.3f}", new, h43, h66,
                            "yes" if new != pattern else "no"])
        print(f"  {stem}: {n_changed}/{len(rows)} frames changed ({n_changed/len(rows)*100:.1f}%)")
        summary["end_to_end"][stem] = {
            "n_frames": len(rows),
            "n_changed": n_changed,
            "pct_changed": round(n_changed / len(rows) * 100, 2),
        }

    summary["methodology"] = {
        "filters_stacked": "H43 (conf < 0.55) + H66 (per-n_total pct_A_ge2 < threshold)",
        "thresholds": PCT_A_GE2_THRESHOLDS,
        "H43_threshold": H43_CONF_THRESHOLD,
        "HAND_REACH": HAND_REACH,
    }

    out = H1_DATA / "h68_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
