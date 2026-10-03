#!/usr/bin/env python3
"""E9c: hand-aware tracklet state classification.

Classification per tracklet (using median nearest-wrist distance):
- AIRBORNE  : >=10% of dt==1 windows match a gravity mode.
- HELD      : fails ballistic test BUT median hand distance < 110 px
              (ball at/near hand: static held stubs and carried balls).
- BACKGROUND: fails ballistic test, far from hands, low displacement.
- SWEEP     : fails ballistic test, far from hands, moving (arm/object FPs).

Only BACKGROUND and SWEEP are demoted. Report label-safety and re-run global
assignment with the filtered pool.
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
GFRAC_MIN = 0.10


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


def median_hand_dist(pts, wrists):
    dists = []
    for f, x, y in pts[:: max(1, len(pts) // 12)]:
        nd = nearest_hand_dist(wrists, f, x, y)
        if nd is not None:
            dists.append(nd[0])
    return float(np.median(dists)) if dists else None


def classify(pts, g_modes, wrists):
    gf = gravity_frac(pts, g_modes)
    disp = float(np.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2]))
    hd = median_hand_dist(pts, wrists)
    if gf is not None and gf >= GFRAC_MIN:
        return "AIRBORNE", gf, hd
    if hd is not None and hd < NEAR_HAND:
        return "HELD", gf, hd
    if disp < 15.0:
        return "BACKGROUND", gf, hd
    return "SWEEP", gf, hd


def main() -> None:
    report = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        wrists = load_wrists(stem)
        from e3c_regime_timeline import collect_windows
        wins = collect_windows(tracks)
        accels = np.array([w[3] for w in wins])
        slow = accels[(accels > -0.2) & (accels < 0.9)]
        normal = accels[accels >= 0.9]
        g_modes = [float(np.median(x)) for x in (slow, normal) if len(x)]

        states = {}
        for tid, pts in tracks.items():
            states[tid] = classify(pts, g_modes, wrists)
        n_state = defaultdict(int)
        for s, *_ in states.values():
            n_state[s] += 1
        demoted = {t for t, (s, *_ ) in states.items() if s in ("BACKGROUND", "SWEEP")}
        print(f"[{stem}] states: {dict(n_state)} demoted={sorted(demoted)}")

        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            pairs = [
                (int(r["source_tracklet"]), int(r["candidate_tracklet"]), r["label"])
                for r in csv.DictReader(fh) if r["video"] == video_key
            ]
        hits = defaultdict(int)
        for sid, cid, label in pairs:
            for tid in (sid, cid):
                if tid in demoted:
                    hits[label] += 1
        print(f"[{stem}] demote hits: {dict(hits)}")

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
        print(f"[{stem}] hand-aware filtered global: links={len(links)} tp={tp} fp={fp}")

        report[stem] = {
            "state_counts": dict(n_state),
            "demoted": sorted(demoted),
            "demote_label_hits": dict(hits),
            "links": len(links),
            "labeled_tp": tp,
            "labeled_fp": fp,
            "states": {t: s for t, (s, _g, _h) in states.items()},
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e9c_hand_aware.json").write_text(json.dumps(report, indent=2))
    print("wrote data/e9c_hand_aware.json")


if __name__ == "__main__":
    main()
