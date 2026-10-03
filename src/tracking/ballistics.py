"""Free-flight model: x is linear in time, y is a parabola with a known acceleration.

Time is in frames and distance in pixels, so the vertical acceleration is in
px/frame^2 and positive (image y grows downward).
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Sequence

import numpy as np

Point = tuple[int, float, float]  # frame, x, y


@dataclass(frozen=True)
class FlightFit:
    frame0: int
    x0: float
    vx: float
    y0: float
    vy: float
    accel_y: float
    rmse: float
    n_points: int

    def predict(self, frame: int) -> tuple[float, float]:
        t = frame - self.frame0
        return (self.x0 + self.vx * t,
                self.y0 + self.vy * t + 0.5 * self.accel_y * t * t)


def _linear_fit(t: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Least-squares ``values = a + b*t``; one sample gives zero slope."""
    if len(t) == 1 or float(np.ptp(t)) == 0.0:
        return float(values.mean()), 0.0
    slope, intercept = np.polyfit(t, values, 1)
    return float(intercept), float(slope)


def fit_flight(points: Sequence[Point], accel_y: float) -> FlightFit:
    """Fit one flight arc through ``points`` with the vertical acceleration fixed.

    Fixing the acceleration leaves only position and velocity free, which is
    what makes a handful of points enough to extrapolate across a long gap.
    """
    if not points:
        raise ValueError("fit_flight requires at least one point")
    frame0 = points[0][0]
    t = np.array([p[0] - frame0 for p in points], dtype=float)
    x = np.array([p[1] for p in points], dtype=float)
    y = np.array([p[2] for p in points], dtype=float)
    x0, vx = _linear_fit(t, x)
    y0, vy = _linear_fit(t, y - 0.5 * accel_y * t * t)
    rx = x - (x0 + vx * t)
    ry = y - (y0 + vy * t + 0.5 * accel_y * t * t)
    rmse = float(np.sqrt(np.mean(rx * rx + ry * ry)))
    return FlightFit(frame0, x0, vx, y0, vy, accel_y, rmse, len(points))


def joint_flight_fit(tail: Sequence[Point], head: Sequence[Point], accel_y: float) -> FlightFit:
    """One arc through the end of a tracklet and the start of a later one."""
    return fit_flight([*tail, *head], accel_y)


def free_accel_fit(points: Sequence[Point]) -> tuple[float, float] | None:
    """Fit y with a free quadratic term; return (accel_y, rmse) or None."""
    if len(points) < 4:
        return None
    frame0 = points[0][0]
    t = np.array([p[0] - frame0 for p in points], dtype=float)
    x = np.array([p[1] for p in points], dtype=float)
    y = np.array([p[2] for p in points], dtype=float)
    if float(np.ptp(t)) == 0.0:
        return None
    x0, vx = _linear_fit(t, x)
    half_accel, vy, y0 = np.polyfit(t, y, 2)
    rx = x - (x0 + vx * t)
    ry = y - (y0 + vy * t + half_accel * t * t)
    return float(2.0 * half_accel), float(np.sqrt(np.mean(rx * rx + ry * ry)))


def flight_samples(runs: Sequence[Sequence[Point]], windows: Sequence[int] = (9, 17, 33),
                   min_sagitta_px: float = 6.0, max_rmse_px: float = 1.5) -> list[tuple[int, float]]:
    """``(centre_frame, accel_y)`` for every window that looks like free flight.

    A window qualifies when it is frame-contiguous, fits a parabola to within
    ``max_rmse_px``, accelerates downward and bends by at least
    ``min_sagitta_px`` over its length. The bend requirement is why several
    window lengths are tried: in slow motion the arc is too flat to measure
    over a short window.
    """
    samples: list[tuple[int, float]] = []
    for run in runs:
        for window in windows:
            for start in range(0, len(run) - window + 1):
                chunk = run[start:start + window]
                if chunk[-1][0] - chunk[0][0] != window - 1:
                    continue
                fit = free_accel_fit(chunk)
                if fit is None:
                    continue
                accel, rmse = fit
                if accel <= 0 or rmse > max_rmse_px:
                    continue
                if 0.5 * accel * (window / 2.0) ** 2 < min_sagitta_px:
                    continue
                samples.append((chunk[window // 2][0], accel))
    return samples


def _clusters(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each sorted value, the index range of values within +-15% of it."""
    return (np.searchsorted(values, values * 0.85, side="left"),
            np.searchsorted(values, values * 1.15, side="right"))


def densest_accel(values: Sequence[float], min_samples: int = 5) -> float | None:
    """Centre of the most populated +-15% cluster of acceleration samples."""
    if len(values) < min_samples:
        return None
    ordered = np.sort(np.asarray(values, dtype=float))
    lower, upper = _clusters(ordered)
    best = int(np.argmax(upper - lower))
    if upper[best] - lower[best] < min_samples:
        return None
    return float(median(ordered[lower[best]:upper[best]].tolist()))


def reference_accel(values: Sequence[float], min_samples: int = 8,
                    min_share: float = 0.05) -> float | None:
    """Real-time gravity: the highest well-supported cluster of samples.

    Slow-motion passages produce a second, lower cluster that can hold more
    samples than the real-time one, so the densest cluster is the wrong choice
    for fixing the image scale.
    """
    if len(values) < min_samples:
        return None
    ordered = np.sort(np.asarray(values, dtype=float))
    lower, upper = _clusters(ordered)
    needed = max(min_samples, min_share * len(ordered))
    counts = upper - lower
    for index in range(len(ordered) - 1, -1, -1):
        if counts[index] >= needed:
            # this is the cluster's upper fringe; move to its fullest point,
            # staying inside it so a bigger, lower cluster cannot take over
            index = lower[index] + int(np.argmax(counts[lower[index]:index + 1]))
            return float(median(ordered[lower[index]:upper[index]].tolist()))
    return None


def estimate_accel_y(runs: Sequence[Sequence[Point]]) -> float | None:
    """Real-time vertical acceleration of free flight over ``runs``, or None."""
    return reference_accel([accel for _, accel in flight_samples(runs)])


class AccelProfile:
    """Vertical acceleration as a function of frame.

    Footage can change playback speed inside one segment; in slow motion the
    apparent gravity drops with the square of the slowdown. The profile takes
    the densest cluster of flight samples near a frame and widens the search
    until enough samples exist, ending at the segment's reference value.
    """

    def __init__(self, samples: Sequence[tuple[int, float]], reference: float,
                 radius_frames: int = 30, sagitta_px: float = 12.0):
        self.reference = reference
        self._frames = np.array([f for f, _ in samples], dtype=int)
        self._values = np.array([a for _, a in samples], dtype=float)
        self._radius = max(1, radius_frames)
        self._sagitta = sagitta_px
        self._cache: dict[int, float] = {}

    def at(self, frame: int) -> float:
        if frame in self._cache:
            return self._cache[frame]
        value = None
        radius = self._radius
        for _ in range(3):
            near = self._values[np.abs(self._frames - frame) <= radius]
            value = densest_accel(near.tolist())
            if value is not None:
                break
            radius *= 2
        self._cache[frame] = self.reference if value is None else value
        return self._cache[frame]

    def speed(self, frame: int) -> float:
        """Playback speed relative to real time (0.25 for 4x slow motion)."""
        return min(1.0, float(np.sqrt(self.at(frame) / self.reference)))

    def window(self, frame: int) -> int:
        """Odd number of points over which a flight arc bends by ``sagitta_px``."""
        points = int(round(2.0 * np.sqrt(2.0 * self._sagitta / self.at(frame))))
        points = min(41, max(5, points))
        return points if points % 2 else points + 1


def constant_profile(accel_y: float) -> AccelProfile:
    return AccelProfile([], accel_y)
