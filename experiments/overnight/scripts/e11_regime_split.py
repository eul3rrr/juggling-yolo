#!/usr/bin/env python3
"""E11: regime-split acceptance architecture.

Sources are split by catch signature (steedy wrist-approach slope at source
end + near hand):
- AIR occlusions  : accept rank-1 if bal8 err <= per-video calibrated q90(gap).
- CONTACT occlusions (catch signature): error gates are meaningless (ball
  vanishes into hand); instead accept the best candidate starting from the
  SAME hand within a time window, subject to mutual exclusion (no time-
  overlapping duplicate claims on one hand event).

Evaluated against 113 labels; compared to E6c gate-only baseline.
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
REPORT_DIR = BASE / "reports"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}
MAX_GAP = 30
NEAR_HAND = 110.0
CATCH_SLOPE = -1.0


def src_catch_signature(tracks, sid, wrists):
    pts = tracks.get(sid, [])
    if not pts:
        return False, None
    window = pts[-5:]
    dists = []
    for f, x, y in window:
        nd = nearest_hand_dist(wrists, f, x, y)
        if nd is not None:
            dists.append((f, nd[0]))
    if len(dists) < 3:
        return False, None
    fs = np.array([d[0] for d in dists], dtype=float)
    ds = np.array([d[1] for d in dists], dtype=float)
    if fs.max() == fs.min():
        return False, None
    slope = float(np.polyfit(fs, ds, 1)[0])
    end_dist = dists[-1][1]
    return (slope <= CATCH_SLOPE and end_dist <= NEAR_HAND), slope


def cand_hand(cp, wrists):
    nd = nearest_hand_dist(wrists, cp[0][0], cp[0][1], cp[0][2])
    if nd is None or nd[0] > NEAR_HAND:
        return None
    return nd[1]


def main() -> None:
    master = {}
    pooled = defaultdict(int)
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        wrists = load_wrists(stem)
        cal = calibrate_per_video(tracks)

        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            labels = {
                (int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
                for r in csv.DictReader(fh) if r["video"] == video_key
            }

        # build candidate pool
        cand_rows = []
        for sid in sorted(tracks):
            sp = tracks[sid]
            if len(sp) < 3:
                continue
            end_f = sp[-1][0]
            is_catch, slope = src_catch_signature(tracks, sid, wrists)
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
                if err_b is None:
                    continue
                cand_rows.append({
                    "sid": sid, "cid": cid, "gap": gap, "err": err_b,
                    "norm": err_b / gate_for(cal, gap),
                    "catch_src": is_catch,
                    "hand": cand_hand(cp, wrists),
                    "label": labels.get((sid, cid), ""),
                })

        # AIR path: per-source rank-1 under gate (like E6c rank-1 accepts)
        # CONTACT path: for catch sources, group candidates by hand; arbitrate
        # by normalized cost with time-overlap exclusion.
        accepted = {}
        air_sources = {r["sid"] for r in cand_rows if not r["catch_src"]}
        contact_sources = {r["sid"] for r in cand_rows if r["catch_src"]}

        for sid in air_sources:
            rows = sorted(
                (r for r in cand_rows if r["sid"] == sid and r["err"] <= gate_for(cal, r["gap"])),
                key=lambda r: r["norm"],
            )
            if rows:
                accepted[sid] = rows[0]

        def interval(tid):
            pts = tracks.get(tid, [])
            return (pts[0][0], pts[-1][0]) if pts else (0, -1)

        for sid in contact_sources:
            rows = [r for r in cand_rows if r["sid"] == sid and r["hand"] is not None]
            by_hand = defaultdict(list)
            for r in rows:
                by_hand[r["hand"]].append(r)
            for hand, hrows in by_hand.items():
                hrows.sort(key=lambda r: r["norm"])
                keeper = hrows[0]
                ks, ke = interval(keeper["cid"])
                clash = False
                for other_sid, other in accepted.items():
                    if other_sid == sid or other.get("hand") != hand:
                        continue
                    os_, oe = interval(other["cid"])
                    if os_ <= ke and ks <= oe:
                        clash = True
                        break
                if not clash:
                    accepted[sid] = keeper

        # evaluate
        res = defaultdict(int)
        for sid, r in accepted.items():
            res[f"accept_{r['label'] or 'unlabeled'}"] += 1
        for r in cand_rows:
            key = (r["sid"], r["cid"])
            if r["label"] and key not in accepted:
                res[f"reject_{r['label']}"] += 1
        n_air = len(air_sources & set(accepted))
        n_contact = len(contact_sources & set(accepted))
        print(f"[{stem}] accepted={len(accepted)} (air={n_air}, contact={n_contact}) {dict(res)}")
        for k, v in res.items():
            pooled[k] += v
        master[stem] = {
            "n_accepted": len(accepted),
            "air_accepted": n_air,
            "contact_accepted": n_contact,
            "outcomes": dict(res),
            "accepted_pairs": [
                [sid, r["cid"], r["label"] or "unlabeled",
                 "contact" if r["catch_src"] else "air"]
                for sid, r in sorted(accepted.items())
            ],
        }

    tot = pooled
    correct = tot.get("accept_correct", 0)
    wrong = tot.get("accept_wrong", 0)
    print(f"POOLED: accepted correct={correct} wrong={wrong} "
          f"precision={correct / max(1, correct + wrong):.3f} "
          f"recall={correct}/71")
    master["_pooled"] = dict(tot)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e11_regime_split.json").write_text(json.dumps(master, indent=2))
    print("wrote data/e11_regime_split.json")


if __name__ == "__main__":
    main()
