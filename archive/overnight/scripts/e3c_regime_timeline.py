#!/usr/bin/env python3
"""E3c: playback-regime timeline from image-space gravity modes.

Windows of fully-observed tracklet points are fit with quadratics; their
implied y-accelerations cluster into modes (slow-motion vs normal speed vs
hand-influenced). This script:

1. classifies each 8-point window into {slow, normal, other};
2. builds a frame-level regime timeline (rolling airborne-window vote);
3. locates regime-boundary frames;
4. reports the estimated playback-factor ratio between modes;
5. cross-references reviewed stitch pairs against boundaries: do gaps that
   span a regime cut fail more often?
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

from e1_ballistic_rescore import SHIPPED  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "data"
STEM = "identical_balls_trick_000_018"
VIDEO_KEY = f"videos/{STEM}.mp4"
WINDOW = 8
SLOW_MAX = 0.9          # px/frame^2; above this -> normal mode
BOUNDARY_VOTE_FRAC = 0.25


def collect_windows(tracks):
    rows = []
    for tid, pts in tracks.items():
        if len(pts) < WINDOW:
            continue
        frames = np.array([p[0] for p in pts])
        ys = np.array([p[2] for p in pts])
        for i in range(len(pts) - WINDOW + 1):
            fw = frames[i : i + WINDOW]
            if np.any(np.diff(fw) != 1):
                continue
            tau = fw - fw.mean()
            try:
                coef = np.polyfit(tau, ys[i : i + WINDOW], 2)
            except np.linalg.LinAlgError:
                continue
            rows.append((int(round(fw.mean())), int(fw[0]), int(fw[-1]), float(2 * coef[0])))
    return rows


def main() -> None:
    tracks = observed_masked_legacy(STEM)
    wins = collect_windows(tracks)
    accels = np.array([w[3] for w in wins])
    slow = accels[(accels > -0.2) & (accels < SLOW_MAX)]
    normal = accels[accels >= SLOW_MAX]
    g_slow = float(np.median(slow))
    g_normal = float(np.median(normal))
    ratio = g_normal / g_slow
    print(f"windows={len(wins)} slow_mode_median={g_slow:.3f} (n={len(slow)}) "
          f"normal_mode_median={g_normal:.3f} (n={len(normal)}) ratio={ratio:.2f} "
          f"playback_factor=sqrt(ratio)={np.sqrt(ratio):.2f}")

    # airborne-class windows only, per midpoint frame
    air = sorted(w for w in wins if 0.0 <= w[3] < 4.0)
    mids = np.array([w[0] for w in air], dtype=int)

    n_frames = 1079
    regime = np.full(n_frames, np.nan)
    for f in range(n_frames):
        lo, hi = f - 12, f + 12
        sel = mids[(mids >= lo) & (mids <= hi)]
        if len(sel) < 4:
            continue
        vals = np.array([w[3] for w in air])[(mids >= lo) & (mids <= hi)]
        frac_normal = float(np.mean(vals >= SLOW_MAX))
        frac_slow = float(np.mean(vals < SLOW_MAX))
        if frac_normal >= BOUNDARY_VOTE_FRAC and frac_normal >= frac_slow:
            regime[f] = 1.0
        elif frac_slow > BOUNDARY_VOTE_FRAC:
            regime[f] = 0.0

    # fill gaps via nearest valid
    valid = np.where(~np.isnan(regime))[0]
    filled = regime.copy()
    for i in range(n_frames):
        if np.isnan(filled[i]):
            j = valid[np.argmin(np.abs(valid - i))]
            filled[i] = regime[j]

    # boundaries = sign flips after smoothing (majority filter width 9)
    sm = np.convolve(filled, np.ones(9) / 9, mode="same")
    binary = sm > 0.5
    bounds = [int(i) for i in range(1, n_frames) if binary[i] != binary[i - 1]]
    print("regime boundaries at frames:", bounds)

    # label the contiguous regimes
    segs = []
    start = 0
    for b in bounds + [n_frames]:
        segs.append((start, b, "normal" if binary[start] else "slow"))
        start = b
    print("segments:", segs)

    # cross-reference stitch pairs
    with (SHIPPED / f"{STEM}_norfair_dt50_hc5_stitches.csv").open(newline="") as fh:
        cands = list(csv.DictReader(fh))
    with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
        labels = {
            (int(r["source_tracklet"]), int(r["candidate_tracklet"])): r["label"]
            for r in csv.DictReader(fh) if r["video"] == VIDEO_KEY
        }

    def seg_of(frame: int) -> str:
        for s, e, name in segs:
            if s <= frame < e:
                return name
        return "?"

    stats = {"cross": {"correct": 0, "wrong": 0}, "same": {"correct": 0, "wrong": 0}}
    detail = []
    for c in cands:
        sid, cid = int(c["source_tracklet"]), int(c["candidate_tracklet"])
        lab = labels.get((sid, cid))
        if lab not in ("correct", "wrong"):
            continue
        s_seg = seg_of(int(c["source_end_frame"]))
        c_seg = seg_of(int(c["candidate_start_frame"]))
        key = "cross" if s_seg != c_seg else "same"
        stats[key][lab] += 1
        detail.append({"src": sid, "cand": cid, "label": lab,
                       "source_seg": s_seg, "candidate_seg": c_seg})

    print("cross-boundary pairs:", stats["cross"])
    print("same-regime pairs:", stats["same"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e3c_regime_timeline.json").write_text(json.dumps({
        "stem": STEM,
        "window": WINDOW,
        "slow_max_threshold": SLOW_MAX,
        "boundary_vote_frac": BOUNDARY_VOTE_FRAC,
        "g_slow_px_f2": round(g_slow, 4),
        "g_normal_px_f2": round(g_normal, 4),
        "ratio": round(ratio, 3),
        "playback_factor": round(float(np.sqrt(ratio)), 3),
        "boundaries": bounds,
        "segments": [{"start": s, "end": e, "regime": n} for s, e, n in segs],
        "pair_stats": stats,
        "pairs": detail,
    }, indent=2))

    # also dump per-frame regime CSV for downstream use
    with (OUT_DIR / "e3c_regime_timeline.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["frame", "regime"])
        writer.writerows(enumerate(binary.astype(int)))
    print(f"wrote {OUT_DIR / 'e3c_regime_timeline.json'} and .csv")


if __name__ == "__main__":
    main()
