#!/usr/bin/env python3
"""E7a: catch/throw event timing from reviewed stitches + pose wrists.

For each reviewed stitch pair, computes wrist-proximity timelines around the
source end and candidate start using the existing pose CSVs, then reports:
- distribution of nearest-hand distances at endpoints (already known weak);
- NEW: hand-approach signature = distance trend (decreasing?) in the last 5
  observed source frames vs first 5 candidate frames;
- whether wrong-labeled pairs more often LACK an approach signature at the
  source end (i.e. the ball was NOT going into a hand -> occlusion elsewhere).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}
WRIST_CONF_MIN = 0.5


def load_wrists(stem: str) -> dict[int, dict[str, tuple[float, float] | None]]:
    """frame -> {'left': (x,y)|None, 'right': (x,y)|None} from pose CSV."""
    path = SHIPPED / f"{stem}_yolo26s-pose.csv"
    out: dict[int, dict[str, tuple[float, float] | None]] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            f = int(row["frame"])
            entry = out.setdefault(f, {"left": None, "right": None})
            for side in ("left", "right"):
                conf = row.get(f"{side}_wrist_confidence")
                x = row.get(f"{side}_wrist_x")
                y = row.get(f"{side}_wrist_y")
                if conf and x and y and float(conf) >= WRIST_CONF_MIN:
                    entry[side] = (float(x), float(y))
    return out


def nearest_hand_dist(
    wrists: dict[int, dict], frame: int, x: float, y: float, tol: int = 2
) -> tuple[float, str] | None:
    best = None
    for f in range(frame - tol, frame + tol + 1):
        entry = wrists.get(f)
        if not entry:
            continue
        for side, xy in entry.items():
            if xy is None:
                continue
            d = math.hypot(xy[0] - x, xy[1] - y)
            if best is None or d < best[0]:
                best = (d, side)
    return best


def approach_slope(
    tracks: dict, tid: int, end_frame: int, wrists: dict, from_end: bool
) -> float | None:
    """Slope of nearest-hand distance over the last/first 5 observed frames."""
    pts = tracks.get(tid, [])
    if not pts:
        return None
    window = pts[-5:] if from_end else pts[:5]
    dists = []
    for f, x, y in window:
        nd = nearest_hand_dist(wrists, f, x, y)
        if nd is None:
            continue
        dists.append((f, nd[0]))
    if len(dists) < 3:
        return None
    fs = np.array([d[0] for d in dists], dtype=float)
    ds = np.array([d[1] for d in dists], dtype=float)
    if fs.max() == fs.min():
        return None
    return float(np.polyfit(fs, ds, 1)[0])  # px per frame


def main() -> None:
    results = []
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        wrists = load_wrists(stem)
        print(f"[{stem}] wrist frames available: {len(wrists)}")
        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            pairs = [
                (int(r["source_tracklet"]), int(r["candidate_tracklet"]), r["label"])
                for r in csv.DictReader(fh) if r["video"] == video_key
            ]
        for sid, cid, label in pairs:
            sp, cp = tracks.get(sid, []), tracks.get(cid, [])
            if not sp or not cp:
                continue
            src_slope = approach_slope(tracks, sid, sp[-1][0], wrists, from_end=True)
            cand_slope = approach_slope(tracks, cid, cp[0][0], wrists, from_end=False)
            src_d = nearest_hand_dist(wrists, sp[-1][0], sp[-1][1], sp[-1][2])
            cand_d = nearest_hand_dist(wrists, cp[0][0], cp[0][1], cp[0][2])
            results.append({
                "video": video_key, "stem": stem,
                "src": sid, "cand": cid, "label": label,
                "src_hand_slope": src_slope,
                "cand_hand_slope": cand_slope,
                "src_end_hand_dist": src_d[0] if src_d else None,
                "cand_start_hand_dist": cand_d[0] if cand_d else None,
                "src_side": src_d[1] if src_d else None,
                "cand_side": cand_d[1] if cand_d else None,
            })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "e7a_hand_events.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    # summary: approach-signature rates by label
    def rate(rows, key, thresh):
        vals = [r[key] for r in rows if r[key] is not None]
        if not vals:
            return None, 0
        return float(np.mean([v < thresh for v in vals])), len(vals)

    lines = ["# E7a: hand-approach signatures on reviewed stitches", ""]
    for label in ("correct", "wrong"):
        rows = [r for r in results if r["label"] == label]
        for key, thresh in (("src_hand_slope", 0.0), ("cand_hand_slope", 0.0)):
            frac, n = rate(rows, key, thresh)
            lines.append(f"- {label} {key} < 0 (approaching hand): "
                         f"{frac if frac is not None else 'n/a'} (n={n})")
    # medians
    for label in ("correct", "wrong"):
        rows = [r for r in results if r["label"] == label]
        for key in ("src_hand_slope", "cand_hand_slope", "src_end_hand_dist",
                    "cand_start_hand_dist"):
            vals = [r[key] for r in rows if r[key] is not None]
            if vals:
                lines.append(f"- {label} {key}: median={np.median(vals):.1f} n={len(vals)}")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "e7a_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
