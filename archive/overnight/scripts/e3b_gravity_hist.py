#!/usr/bin/env python3
"""E3b: per-window gravity distribution inside the identical-balls clip."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_shared_gravity import observed_masked_legacy  # noqa: E402

tracks = observed_masked_legacy("identical_balls_trick_000_018")
accels: list[float] = []
for pts in tracks.values():
    if len(pts) < 8:
        continue
    frames = np.array([p[0] for p in pts])
    ys = np.array([p[2] for p in pts])
    for i in range(len(pts) - 7):
        fw = frames[i : i + 8]
        if np.any(np.diff(fw) != 1):
            continue
        tau = fw - fw.mean()
        try:
            coef = np.polyfit(tau, ys[i : i + 8], 2)
        except np.linalg.LinAlgError:
            continue
        accels.append(2.0 * coef[0])

a = np.array(accels)
q = np.percentile(a, [10, 25, 50, 75, 90])
print(f"n={len(a)} q10={q[0]:.3f} q25={q[1]:.3f} med={q[2]:.3f} q75={q[3]:.3f} q90={q[4]:.3f}")
hist, edges = np.histogram(a, bins=24)
for h, e0, e1 in zip(hist, edges[:-1], edges[1:]):
    print(f"  {e0:+.2f}..{e1:+.2f}: {'#' * int(60 * h / max(hist.max(), 1))} {h}")

# split by first vs second half of the clip (slow-mo edit sits in the middle)
mid = 1079 / 2
first_half = []
second_half = []
for tid, pts in tracks.items():
    for f, x, y in pts:
        pass
for pts in tracks.values():
    if len(pts) < 8:
        continue
    frames = np.array([p[0] for p in pts])
    ys = np.array([p[2] for p in pts])
    for i in range(len(pts) - 7):
        fw = frames[i : i + 8]
        if np.any(np.diff(fw) != 1):
            continue
        tau = fw - fw.mean()
        try:
            coef = np.polyfit(tau, ys[i : i + 8], 2)
        except np.linalg.LinAlgError:
            continue
        (first_half if fw.mean() < mid else second_half).append(2.0 * coef[0])
fa = np.array(first_half)
sa = np.array(second_half)
print(f"first half: n={len(fa)} median={np.median(fa):+.3f}")
print(f"second half: n={len(sa)} median={np.median(sa):+.3f}")
