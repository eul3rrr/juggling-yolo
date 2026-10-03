#!/usr/bin/env python3
"""E8c: raw detection centers vs Kalman-smoothed estimates as observations.

Runs the constacc association but exports BOTH:
- estimate rows (as before), and
- raw detection centers for matched (observed) rows.

Then runs the synthetic-occlusion benchmark on contexts built from each.
If raw wins, the pipeline should export raw centers for observed rows.
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
from e4_synthetic_occlusion import fit_predict  # noqa: E402
from e8_norfair_models import (  # noqa: E402
    ConstantAccelerationFactory,
    OptimizedKalmanFilterFactory,
    load_detections,
)

BASE = Path(__file__).resolve().parents[1]
OUT_DIR = BASE / "data" / "e8"
GAPS = (2, 4, 6, 10, 15, 20, 30)
MIN_RUN = 12
DISTANCE_THRESHOLD = 50
HIT_COUNTER_MAX = 5


def run_export(stem: str, factory, out_prefix: str) -> None:
    by_frame = load_detections(stem)
    tracker = __import__("norfair").Tracker(
        distance_function="euclidean",
        distance_threshold=DISTANCE_THRESHOLD,
        hit_counter_max=HIT_COUNTER_MAX,
        filter_factory=factory,
    )
    rows = []
    for frame in sorted(by_frame):
        dets = [
            (__import__("norfair").Detection(points=np.array([[x, y]]), scores=np.array([c])), x, y, c)
            for x, y, c in by_frame[frame]
        ]
        active = tracker.update(detections=[d for d, *_ in dets])
        det_by_id = {id(d): (x, y) for d, x, y, _c in dets}
        for obj in active:
            ex, ey = obj.estimate[0]
            raw_x = raw_y = None
            if obj.last_detection is not None:
                raw = det_by_id.get(id(obj.last_detection))
                if raw:
                    raw_x, raw_y = raw
            rows.append({
                "frame": frame,
                "track_id": obj.id,
                "est_x": float(ex),
                "est_y": float(ey),
                "raw_x": raw_x,
                "raw_y": raw_y,
                "observed": int(raw_x is not None),
            })
    with (OUT_DIR / f"{stem}_{out_prefix}.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["frame", "track_id", "est_x", "est_y", "raw_x", "raw_y", "observed"]
        )
        writer.writeheader()
        writer.writerows(rows)


def bench_from(stem: str, prefix: str, use_raw: bool) -> dict:
    tracks = defaultdict(list)
    with (OUT_DIR / f"{stem}_{prefix}.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row["observed"] != "1":
                continue
            x = row["raw_x"] if use_raw else row["est_x"]
            y = row["raw_y"] if use_raw else row["est_y"]
            tracks[int(row["track_id"])].append((int(row["frame"]), float(x), float(y)))
    tracks = {t: sorted(pts) for t, pts in tracks.items()}
    by_frame = defaultdict(list)
    for tid, pts in tracks.items():
        for f, x, y in pts:
            by_frame[f].append((tid, x, y))
    stats = defaultdict(lambda: {"n": 0, "top1": 0})
    for tid, pts in tracks.items():
        runs = []
        cur = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            if b[0] - a[0] == 1:
                cur.append(b)
            else:
                if len(cur) >= MIN_RUN:
                    runs.append(cur)
                cur = [b]
        if len(cur) >= MIN_RUN:
            runs.append(cur)
        for run in runs:
            for off in range(4, len(run) - 2, 4):
                left = run[:off][-12:]
                if len(left) < 3:
                    continue
                cut_a = run[off - 1][0]
                for k in GAPS:
                    cut_b = cut_a + k
                    true_pt = next((p for p in run[off:] if p[0] == cut_b), None)
                    if true_pt is None:
                        continue
                    comps = by_frame.get(cut_b, [])
                    if len(comps) < 2:
                        continue
                    pred = fit_predict(left, cut_b)
                    if pred is None:
                        continue
                    scored = sorted(
                        (math.hypot(pred[0] - x2, pred[1] - y2), t2)
                        for t2, x2, y2 in comps
                    )
                    rank = next(i + 1 for i, (_d, t2) in enumerate(scored) if t2 == tid)
                    b = stats[k]
                    b["n"] += 1
                    b["top1"] += rank == 1
    return {
        k: {"n": v["n"], "top1": round(v["top1"] / v["n"], 4) if v["n"] else None}
        for k, v in sorted(stats.items())
    }


def main() -> None:
    results = {}
    for stem in ("identical_balls_trick_000_018",
                 "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"):
        run_export(stem, ConstantAccelerationFactory(), "e8c_ca")
        results[f"{stem}|ca_est"] = bench_from(stem, "e8c_ca", use_raw=False)
        results[f"{stem}|ca_raw"] = bench_from(stem, "e8c_ca", use_raw=True)
        run_export(stem, OptimizedKalmanFilterFactory(), "e8c_vel")
        results[f"{stem}|vel_est"] = bench_from(stem, "e8c_vel", use_raw=False)
        results[f"{stem}|vel_raw"] = bench_from(stem, "e8c_vel", use_raw=True)
        for key in (f"{stem}|ca_est", f"{stem}|ca_raw", f"{stem}|vel_est", f"{stem}|vel_raw"):
            r = results[key]
            print(f"{key}: top1@10={r.get(10, {}).get('top1')} top1@20={r.get(20, {}).get('top1')}")
    (OUT_DIR / "e8c_raw_vs_est.json").write_text(json.dumps(results, indent=2))
    print("wrote data/e8/e8c_raw_vs_est.json")


if __name__ == "__main__":
    main()
