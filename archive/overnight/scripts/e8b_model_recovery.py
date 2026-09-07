#!/usr/bin/env python3
"""E8b: synthetic-occlusion recovery on E8 motion-model CSVs.

Applies the E4 protocol (cut clean runs, rank true continuation against all
observed points at re-entry) to each E8 variant CSV. Better recovery means the
motion model produces better stitching raw material, independent of labels.
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

BASE = Path(__file__).resolve().parents[1]
E8_DIR = BASE / "data" / "e8"
OUT_DIR = E8_DIR

VARIANTS = ("nofilter", "optvel", "optvel_looseQ", "constacc")
GAPS = (2, 4, 6, 10, 15, 20, 30)
MIN_RUN = 12


def load_observed(path: Path):
    tracks = defaultdict(list)
    n_obs = 0
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed") != "1":
                continue
            n_obs += 1
            tracks[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {t: sorted(pts) for t, pts in tracks.items()}, n_obs


def bench(tracks):
    by_frame = defaultdict(list)
    for tid, pts in tracks.items():
        for f, x, y in pts:
            by_frame[f].append((tid, x, y))
    stats = defaultdict(lambda: {"n": 0, "top1": 0, "top3": 0})
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
                    b["top3"] += rank <= 3
    return {
        k: {
            "n": v["n"],
            "top1": round(v["top1"] / v["n"], 4) if v["n"] else None,
            "top3": round(v["top3"] / v["n"], 4) if v["n"] else None,
        }
        for k, v in sorted(stats.items())
    }


def main() -> None:
    results = {}
    for stem in ("identical_balls_trick_000_018",
                 "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"):
        for variant in VARIANTS:
            tracks, n_obs = load_observed(E8_DIR / f"{stem}_norfair_{variant}.csv")
            res = bench(tracks)
            results[f"{stem}|{variant}"] = {"n_observed_rows": n_obs, "by_gap": res}
            top1_10 = res.get(10, {}).get("top1")
            top1_20 = res.get(20, {}).get("top1")
            print(f"[{stem}] {variant}: obs_rows={n_obs} top1@10={top1_10} top1@20={top1_20}")
    (OUT_DIR / "e8b_recovery.json").write_text(json.dumps(results, indent=2))
    print("wrote data/e8/e8b_recovery.json")


if __name__ == "__main__":
    main()
