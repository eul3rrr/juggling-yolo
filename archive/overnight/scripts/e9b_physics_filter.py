#!/usr/bin/env python3
"""E9b: physics-based tracklet filter + effect on global assignment.

Rules:
- STATIC: total displacement < 15 px -> demote (background blobs).
- DYNAMICS: >= 8 consecutive frames but <10% of dt==1 6-pt windows matching
  a gravity mode -> demote (non-ballistic sweeps).

Safety check: which labeled pairs involve demoted tracklets, split by label.
Then re-run the E6c global assignment with filtered tracklets.
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
STATIC_DISP = 15.0
DYNAMICS_MIN_RUN = 8
DYNAMICS_GFRAC = 0.10


def tracklet_stats(pts):
    frames = np.array([p[0] for p in pts])
    xs = np.array([p[1] for p in pts])
    ys = np.array([p[2] for p in pts])
    disp = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
    # longest consecutive run
    longest = cur = 1
    for a, b in zip(frames[:-1], frames[1:]):
        cur = cur + 1 if b - a == 1 else 1
        longest = max(longest, cur)
    return disp, int(longest)


def gravity_frac(pts, g_modes):
    frames = np.array([p[0] for p in pts])
    ys = np.array([p[2] for p in pts])
    match = tot = 0
    for i in range(len(pts) - 5):
        fw = frames[i : i + 6]
        if np.any(np.diff(fw) != 1):
            continue
        tau = fw - fw.mean()
        try:
            a2 = 2 * np.polyfit(tau, ys[i : i + 6], 2)[0]
        except Exception:
            continue
        tot += 1
        if any(abs(a2 - g) <= 0.35 * max(abs(g), 1e-6) for g in g_modes):
            match += 1
    return (match / tot) if tot else None


def gravity_modes(accels):
    a = np.asarray(accels)
    slow = a[(a > -0.2) & (a < 0.9)]
    normal = a[a >= 0.9]
    modes = []
    if len(slow):
        modes.append(float(np.median(slow)))
    if len(normal):
        modes.append(float(np.median(normal)))
    return modes or [0.1, 1.0]


def main() -> None:
    report = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        # gravity modes from all windows
        from e3c_regime_timeline import collect_windows
        wins = collect_windows(tracks)
        g_modes = gravity_modes([w[3] for w in wins])

        demoted = {}
        for tid, pts in tracks.items():
            disp, longest = tracklet_stats(pts)
            reason = None
            if disp < STATIC_DISP:
                reason = "static"
            elif longest >= DYNAMICS_MIN_RUN:
                gf = gravity_frac(pts, g_modes)
                if gf is not None and gf < DYNAMICS_GFRAC:
                    reason = f"dynamics(gfrac={gf:.2f})"
            if reason:
                demoted[tid] = reason

        # label safety check
        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            pairs = [
                (int(r["source_tracklet"]), int(r["candidate_tracklet"]), r["label"])
                for r in csv.DictReader(fh) if r["video"] == video_key
            ]
        demote_hits = defaultdict(list)
        for sid, cid, label in pairs:
            for tid in (sid, cid):
                if tid in demoted:
                    demote_hits[label].append((tid, demoted[tid]))
        print(f"[{stem}] demoted {len(demoted)}/{len(tracks)} tracklets: {demoted}")
        print(f"[{stem}] demote hits on labeled pairs: {dict(demote_hits)}")

        # filtered global assignment
        live = {t: pts for t, pts in tracks.items() if t not in demoted}
        cal = calibrate_per_video(tracks)
        cand_rows = []
        for sid in sorted(live):
            sp = live[sid]
            if len(sp) < 3:
                continue
            end_f = sp[-1][0]
            for cid in sorted(live):
                if cid == sid:
                    continue
                cp = live[cid]
                if not cp or cp[0][0] <= end_f:
                    continue
                gap = cp[0][0] - end_f - 1
                if gap > MAX_GAP:
                    continue
                qb = bal8_predict(sp, cp[0][0])
                err_b = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2]) if qb else None
                if err_b is None or err_b >= gate_for(cal, gap):
                    continue
                cand_rows.append({"sid": sid, "cid": cid, "gap": gap, "bal8": err_b})
        all_ids = sorted(live)
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
        links = {(all_ids[a], all_ids[b]) for a, b in zip(ri, ci) if b < n_t and cost[a, b] < 1e9}
        tp = sum(1 for s, c, l in pairs if (s, c) in links and l == "correct")
        fp = sum(1 for s, c, l in pairs if (s, c) in links and l == "wrong")
        print(f"[{stem}] filtered global: links={len(links)} tp={tp} fp={fp}")
        report[stem] = {
            "n_demoted": len(demoted),
            "demoted": demoted,
            "demote_hits": {k: v for k, v in demote_hits.items()},
            "filtered_links": len(links),
            "labeled_tp": tp,
            "labeled_fp": fp,
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e9b_filter.json").write_text(json.dumps(report, indent=2))
    print("wrote data/e9b_filter.json")


if __name__ == "__main__":
    main()
