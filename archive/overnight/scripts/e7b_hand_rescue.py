#!/usr/bin/env python3
"""E7b: hand-event acceptance rule vs calibrated error gates.

Rule under test: when the source ends with a steep hand-approach (catch
signature) AND the candidate starts near the same hand receding (throw
signature), accept the stitch EVEN IF the ballistic error exceeds the
calibrated gate -- identity is unobservable across a hand contact, so the
permutation is legitimate.

Reports how many gate-rejected correct pairs this recovers and how many
gate-rejected wrong pairs it would wrongly admit, vs the same counts for
plain gate acceptance.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

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
CATCH_SLOPE = -1.0      # px/f decreasing = catch signature
THROW_SLOPE = 0.5       # px/f increasing = throw signature
NEAR_HAND = 90.0        # px
SAME_SIDE = True


def slope_at(tracks, tid, from_end, wrists):
    pts = tracks.get(tid, [])
    window = pts[-5:] if from_end else pts[:5]
    dists = []
    for f, x, y in window:
        nd = nearest_hand_dist(wrists, f, x, y)
        if nd is not None:
            dists.append((f, nd[0]))
    if len(dists) < 3:
        return None, None
    fs = np.array([d[0] for d in dists], dtype=float)
    ds = np.array([d[1] for d in dists], dtype=float)
    if fs.max() == fs.min():
        return None, None
    return float(np.polyfit(fs, ds, 1)[0]), float(ds[-1] if from_end else ds[0])


def main() -> None:
    summary = {}
    for stem, video_key in STEMS.items():
        tracks = observed_masked_legacy(stem)
        cal = calibrate_per_video(tracks)
        wrists = load_wrists(stem)

        with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
            pairs = [
                (int(r["source_tracklet"]), int(r["candidate_tracklet"]), r["label"])
                for r in csv.DictReader(fh) if r["video"] == video_key
            ]

        counts = {
            "gate_accept_correct": 0, "gate_accept_wrong": 0,
            "gate_reject_correct": 0, "gate_reject_wrong": 0,
            "hand_rescued_correct": 0, "hand_rescued_wrong": 0,
        }
        rescued_detail = []
        for sid, cid, label in pairs:
            sp, cp = tracks.get(sid, []), tracks.get(cid, [])
            if not sp or not cp:
                continue
            qb = bal8_predict(sp, cp[0][0])
            if qb is None:
                continue
            err = math.hypot(qb[0] - cp[0][1], qb[1] - cp[0][2])
            gap = cp[0][0] - sp[-1][0] - 1
            accepted = err <= gate_for(cal, gap)
            if accepted:
                counts[f"gate_accept_{label}"] += 1
                continue
            counts[f"gate_reject_{label}"] += 1
            # hand-event rescue test
            src_slope, src_dist = slope_at(tracks, sid, True, wrists)
            cand_slope, cand_dist = slope_at(tracks, cid, False, wrists)
            if src_slope is None or cand_slope is None:
                continue
            catch_sig = src_slope <= CATCH_SLOPE and src_dist is not None and src_dist <= NEAR_HAND
            throw_sig = cand_slope >= THROW_SLOPE and cand_dist is not None and cand_dist <= NEAR_HAND
            if catch_sig and throw_sig:
                counts[f"hand_rescued_{label}"] += 1
                rescued_detail.append({
                    "pair": [sid, cid], "label": label, "err": round(err, 1),
                    "gap": gap,
                    "src_slope": round(src_slope, 2) if src_slope is not None else None,
                    "cand_slope": round(cand_slope, 2) if cand_slope is not None else None,
                    "src_dist": round(src_dist, 1) if src_dist is not None else None,
                    "cand_dist": round(cand_dist, 1) if cand_dist is not None else None,
                })
        print(f"[{stem}] {counts}")
        print(f"  rescued: {json.dumps(rescued_detail[:10])}")
        summary[stem] = {"counts": counts, "rescued": rescued_detail}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e7b_hand_rescue.json").write_text(json.dumps(summary, indent=2))
    lines = ["# E7b: hand-event rescue of gate-rejected stitches", ""]
    tot = {k: sum(s["counts"][k] for s in summary.values()) for k in next(iter(summary.values()))["counts"]}
    lines.append(f"Totals: {tot}")
    prec_gate = tot["gate_accept_correct"] / max(1, tot["gate_accept_correct"] + tot["gate_accept_wrong"])
    prec_hand = (tot["gate_accept_correct"] + tot["hand_rescued_correct"]) / max(
        1,
        tot["gate_accept_correct"] + tot["gate_accept_wrong"]
        + tot["hand_rescued_correct"] + tot["hand_rescued_wrong"],
    )
    lines.append(f"precision gate-only: {prec_gate:.3f}; with hand-rescue: {prec_hand:.3f}")
    lines.append(f"recall gate-only: {tot['gate_accept_correct']}/71; with rescue: "
                 f"{tot['gate_accept_correct'] + tot['hand_rescued_correct']}/71")
    (REPORT_DIR / "e7b_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
