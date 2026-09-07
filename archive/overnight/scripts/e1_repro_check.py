#!/usr/bin/env python3
"""Reproduce shipped stitch candidates from legacy (pre-a77cc5d) CSVs."""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LEGACY = BASE / "data" / "legacy_csv"
SHIPPED = Path(__file__).resolve().parents[3] / "detections"

STEMS = {
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}


def load(path: Path):
    tracks = defaultdict(list)
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        has_observed = "observed" in (reader.fieldnames or [])
        for row in reader:
            if has_observed and row["observed"] != "1":
                continue
            tracks[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {tid: sorted(pts) for tid, pts in tracks.items()}


def stitch(tracks, max_gap=10):
    out = []
    for sid in sorted(tracks):
        sp = tracks[sid]
        if len(sp) < 2:
            continue
        (f1, x1, y1), (f2, x2, y2) = sp[-2], sp[-1]
        dt = f2 - f1
        if dt <= 0:
            continue
        vx, vy = (x2 - x1) / dt, (y2 - y1) / dt
        row_cands = []
        for cid in sorted(tracks):
            if cid == sid:
                continue
            cp = tracks[cid]
            if not cp:
                continue
            sf = cp[0][0]
            if sf <= f2:
                continue
            gap = sf - f2 - 1
            if gap > max_gap:
                continue
            elapsed = sf - f2
            px, py = x2 + vx * elapsed, y2 + vy * elapsed
            err = math.hypot(px - cp[0][1], py - cp[0][2])
            row_cands.append((sid, cid, gap, err))
        row_cands.sort(key=lambda r: (r[3], r[1]))
        for rank, r in enumerate(row_cands, 1):
            out.append((*r, rank))
    return out


def main() -> None:
    for stem in sorted(STEMS):
        mine = stitch(load(LEGACY / f"{stem}.csv"))
        shipped = []
        with (SHIPPED / f"{stem}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
            for row in csv.DictReader(fh):
                shipped.append((
                    int(row["source_tracklet"]), int(row["candidate_tracklet"]),
                    int(row["gap_frames"]), float(row["prediction_error"]),
                    int(row["candidate_rank"]),
                ))
        print(f"{stem}: reproduced={len(mine)} shipped={len(shipped)}")
        mine_set = {(s, c): (g, e, r) for s, c, g, e, r in mine}
        exact = 0
        max_derr = 0.0
        for s, c, g, e, r in shipped:
            got = mine_set.get((s, c))
            if got is None:
                print(f"  MISSING src={s} cand={c}")
                continue
            g2, e2, r2 = got
            derr = abs(e2 - e)
            max_derr = max(max_derr, derr)
            if g2 == g and r2 == r and derr < 1e-3:
                exact += 1
        print(f"  exact matches: {exact}/{len(shipped)}  max |derr|={max_derr:.6f}")


if __name__ == "__main__":
    sys.exit(main())
