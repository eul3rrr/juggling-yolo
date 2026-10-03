#!/usr/bin/env python3
"""E9a: per-tracklet dynamics census -> find physics thresholds separating
ball-like tracklets from static/background false-positive tracklets."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402
from e3c_regime_timeline import collect_windows  # noqa: E402

STEMS = ["identical_balls_trick_000_018",
         "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]

for stem in STEMS:
    tracks = observed_masked_legacy(stem)
    wins = collect_windows(tracks)
    accels = np.array([w[3] for w in wins])
    slow = float(np.median(accels[(accels > -0.2) & (accels < 0.9)])) if np.any((accels > -0.2) & (accels < 0.9)) else 0.1
    normal = float(np.median(accels[accels >= 0.9])) if np.any(accels >= 0.9) else 1.0
    g_modes = [g for g in (slow, normal) if g > 0]
    print(f"\n=== {stem}: g modes slow={slow:.3f} normal={normal:.3f}")

    rows = []
    for tid, pts in tracks.items():
        n = len(pts)
        frames = np.array([p[0] for p in pts])
        xs = np.array([p[1] for p in pts])
        ys = np.array([p[2] for p in pts])
        dur = int(frames[-1] - frames[0] + 1)
        disp = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
        path_len = float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))
        dt = np.diff(frames)
        speed = float(np.mean(np.hypot(np.diff(xs), np.diff(ys)) / np.maximum(dt, 1)))
        v_range = float(ys.max() - ys.min())
        # fraction of dt==1 6-pt windows whose accel matches a g mode within 35%
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
        frac = match / tot if tot else np.nan
        rows.append((tid, n, dur, disp, path_len, speed, v_range, frac))

    rows.sort(key=lambda r: -(r[5] if r[5] is not None else 0))
    print(f"{'tid':>4}{'n':>5}{'dur':>5}{'disp':>7}{'path':>8}{'spd':>6}{'vrange':>7}{'gfrac':>6}")
    for tid, n, dur, disp, path_len, speed, v_range, frac in rows[:14]:
        print(f"{tid:4d}{n:5d}{dur:5d}{disp:7.0f}{path_len:8.0f}{speed:6.1f}{v_range:7.0f}{frac:6.2f}")
    print("  ...")
    rows.sort(key=lambda r: (r[5] if r[5] is not None else 0))
    print("slowest tracklets:")
    for tid, n, dur, disp, path_len, speed, v_range, frac in rows[:10]:
        print(f"{tid:4d}{n:5d}{dur:5d}{disp:7.0f}{path_len:8.0f}{speed:6.1f}{v_range:7.0f}{frac:6.2f}")
