#!/usr/bin/env python3
"""E6e: physical self-consistency of chains.

A chain claiming two observations at the same frame is physically impossible
(one ball cannot be in two places). Counts same-frame violations per linking
configuration and reports the worst offenders. Also measures how many chains
survive violation-free.
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

BASE = Path(__file__).resolve().parents[1]
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}
MAX_GAP = 30


def build_links(tracks, cal, max_gap=MAX_GAP, gate_scale=1.0):
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
            if gap > max_gap:
                continue
            qb = bal8_predict(sp, cp[0][0])
            err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
            if err_b is None or err_b >= gate_for(cal, gap) * gate_scale:
                continue
            cand_rows.append({"sid": sid, "cid": cid, "gap": gap, "bal8": err_b})
    all_ids = sorted(tracks)
    n_t = len(all_ids)
    idx = {t: i for i, t in enumerate(all_ids)}
    cost = np.full((n_t, 2 * n_t), 1e9)
    cost[:, n_t:] = 1.0
    for r in cand_rows:
        rel = r["bal8"] / gate_for(cal, r["gap"])
        si, ci = idx[r["sid"]], idx[r["cid"]]
        if cost[si, ci] > rel:
            cost[si, ci] = rel
    ri, ci = linear_sum_assignment(cost)
    return {(all_ids[a], all_ids[b]) for a, b in zip(ri, ci) if b < n_t and cost[a, b] < 1e9}


def chains_of(links):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s, c in sorted(links):
        rs, rc = find(s), find(c)
        if rs != rc:
            parent[rs] = rc
    groups = defaultdict(list)
    for t in parent:
        groups[find(t)].append(t)
    return groups


def violations(groups, tracks):
    """Same-frame collisions within chains."""
    bad = []
    for root, members in groups.items():
        if len(members) < 2:
            continue
        frames_seen = defaultdict(list)
        for m in members:
            for f, x, y in tracks[m]:
                frames_seen[f].append(m)
        collisions = {f: ts for f, ts in frames_seen.items() if len(ts) > 1}
        if collisions:
            bad.append({
                "chain": sorted(members),
                "n_collision_frames": len(collisions),
                "example_frame": min(collisions),
                "example_tracks": collisions[min(collisions)],
            })
    return bad


def main() -> None:
    report = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        cal = calibrate_per_video(tracks)
        entry = {}
        for scale in (0.8, 1.0, 1.3):
            links = build_links(tracks, cal, gate_scale=scale)
            groups = chains_of(links)
            bad = violations(groups, tracks)
            labeled_tp = labeled_fp = 0
            with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
                for row in csv.DictReader(fh):
                    if row["video"] != video_key:
                        continue
                    pair = (int(row["source_tracklet"]), int(row["candidate_tracklet"]))
                    if pair in links:
                        if row["label"] == "correct":
                            labeled_tp += 1
                        elif row["label"] == "wrong":
                            labeled_fp += 1
            entry[f"scale{scale}"] = {
                "links": len(links),
                "chains": len(groups),
                "violating_chains": len(bad),
                "labeled_tp": labeled_tp,
                "labeled_fp": labeled_fp,
                "worst": sorted(bad, key=lambda b: -b["n_collision_frames"])[:5],
            }
            print(f"[{stem}] gate_scale={scale}: links={len(links)} chains={len(groups)} "
                  f"violating={len(bad)} tp={labeled_tp} fp={labeled_fp}")
        report[stem] = entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e6e_consistency.json").write_text(json.dumps(report, indent=2))
    print("wrote data/e6e_consistency.json")


if __name__ == "__main__":
    main()
