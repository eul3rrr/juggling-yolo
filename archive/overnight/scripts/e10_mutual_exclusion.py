#!/usr/bin/env python3
"""E10: hand-inventory mutual exclusion for catch->throw stitching.

Idea: after a catch at hand H ending source tracklet S, at most ONE candidate
may start from H within a short window. When multiple candidates share the
same (source, hand) event, the event can only be assigned to one - resolve by
best normalized ballistic cost; others are rejected as duplicates.

Implementation: over the E6c candidate pool (observed-only, calibrated gates,
gap<=30), find groups of candidates sharing source sid AND nearest-hand side
(at candidate start). Within each group of size>1, keep only the min
normalized cost; count label outcomes of kept-vs-dropped.

Also tests the reverse: candidates from DIFFERENT sources arriving at the same
hand within the same time window (competing catches) - report frequency.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402
from e6c_wide_universe_v2 import bal8_predict, calibrate_per_video, gate_for  # noqa: E402
from e7a_hand_events import load_wrists, nearest_hand_dist  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}
MAX_GAP = 30
NEAR_HAND = 110.0


def cand_side(cp, wrists):
    nd = nearest_hand_dist(wrists, cp[0][0], cp[0][1], cp[0][2])
    if nd is None or nd[0] > NEAR_HAND:
        return None
    return nd[1]


def main() -> None:
    master = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        wrists = load_wrists(stem)
        cal = calibrate_per_video(tracks)

        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh) if r["video"] == video_key
            }

        cand_rows = []
        for sid in sorted(tracks):
            sp = tracks[sid]
            if len(sp) < 3:
                continue
            end_f = sp[-1][0]
            for cid in sorted(tracks):
                if cid == sid:
                    continue
                cp = tracks[cid]
                if not cp or cp[0][0] <= end_f:
                    continue
                gap = cp[0][0] - end_f - 1
                if gap > MAX_GAP:
                    continue
                qb = bal8_predict(sp, cp[0][0])
                err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
                if err_b is None or err_b >= gate_for(cal, gap):
                    continue
                cand_rows.append({
                    "sid": sid, "cid": cid, "gap": gap, "err": err_b,
                    "norm": err_b / gate_for(cal, gap),
                    "side": cand_side(cp, wrists),
                    "label": labels.get((sid, cid), ""),
                })

        # group by (source, side) where side is not None; drop only
        # TIME-OVERLAPPING duplicates (sequential hops through a held ball
        # are legitimate: catch -> carry -> throw)
        def interval(tid):
            pts = tracks.get(tid, [])
            return (pts[0][0], pts[-1][0]) if pts else (0, -1)

        groups = defaultdict(list)
        for r in cand_rows:
            if r["side"] is not None:
                groups[(r["sid"], r["side"])].append(r)
        multi = {k: v for k, v in groups.items() if len(v) > 1}
        kept_stats = defaultdict(int)
        dropped_stats = defaultdict(int)
        examples = []
        for (sid, side), rows in sorted(multi.items()):
            rows.sort(key=lambda r: r["norm"])
            keeper = rows[0]
            kept_stats[keeper["label"] or "unlabeled"] += 1
            ks, ke = interval(keeper["cid"])
            for loser in rows[1:]:
                ls, le = interval(loser["cid"])
                overlaps = ls <= ke and ks <= le
                if not overlaps:
                    continue  # sequential hop, keep it
                dropped_stats[loser["label"] or "unlabeled"] += 1
                if keeper["label"] or loser["label"]:
                    examples.append({
                        "event": [sid, side],
                        "keeper": [keeper["cid"], keeper["label"], round(keeper["norm"], 2)],
                        "loser": [loser["cid"], loser["label"], round(loser["norm"], 2)],
                    })
        # how many candidates have no side (mid-air starts)?
        n_side = sum(1 for r in cand_rows if r["side"] is None)
        print(f"[{stem}] candidates={len(cand_rows)} no-side={n_side} "
              f"multi-events={len(multi)}")
        print(f"[{stem}] kept: {dict(kept_stats)} dropped: {dict(dropped_stats)}")
        print(f"[{stem}] examples: {json.dumps(examples[:10])}")
        master[stem] = {
            "n_candidates": len(cand_rows),
            "n_multi_events": len(multi),
            "kept": dict(kept_stats),
            "dropped": dict(dropped_stats),
            "examples": examples[:20],
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e10_mutual_exclusion.json").write_text(json.dumps(master, indent=2))
    print("wrote data/e10_mutual_exclusion.json")


if __name__ == "__main__":
    main()
