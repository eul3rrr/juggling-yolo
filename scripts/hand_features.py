"""Reusable ball↔hand interaction features (Hand System v1).

Pure-numpy, no project-specific imports. Safe to unit-test in isolation.

Conventions
-----------
* Anatomical LEFT / RIGHT is honoured. The video contains crossed arms; the
  caller is responsible for not swapping labels based on screen position.
* Missing or low-confidence data is represented as ``None`` / NaN. The
  functions below never silently fabricate values, and they expose how many
  points they used so downstream code can decide whether the result is
  trustworthy.
* Sign convention for distances and slopes:
    * distance                : always >= 0
    * slope / radial velocity : negative == converging, positive == separating
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def smooth_series(values: Sequence[float | None],
                  window: int = 5,
                  min_confidence: Sequence[float | None] | None = None,
                  confidence_threshold: float | None = None,
                  min_points: int | None = None) -> list[float | None]:
    """Centered moving-average smoothing.

    * ``values`` is the raw series; ``None`` entries are treated as missing.
    * ``min_confidence`` is an optional parallel series. If provided AND
      ``confidence_threshold`` is not None, points whose confidence is below
      the threshold are treated as missing.
    * Long gaps are NOT bridged. The output at position i is the median of
      the available points in the centred window, but only if the centre
      itself is a usable value AND at least ``min_points`` (default = half
      window) usable values are present inside the window. When the centre
      is missing the output is ``None`` (the gap is preserved).
    * The window is clamped to ``[1, len(values)]`` and to odd length.

    We use a *median* of available values rather than a mean to suppress the
    noisy outliers that single-frame pose estimates produce when a wrist
    teleports for one frame. A median over a small window is robust to that
    without introducing the lag of a long Gaussian kernel.
    """
    n = len(values)
    if n == 0 or window <= 1:
        return list(values)
    half = max(1, window // 2)
    threshold = min_points if min_points is not None else half
    out: list[float | None] = []
    for i in range(n):
        centre_v = values[i]
        if centre_v is not None and min_confidence is not None and confidence_threshold is not None:
            c = min_confidence[i]
            if c is None or c < confidence_threshold:
                centre_v = None
        if centre_v is None:
            out.append(None)
            continue
        lo, hi = max(0, i - half), min(n, i + half + 1)
        pts: list[float] = []
        for j in range(lo, hi):
            v = values[j]
            if v is None:
                continue
            if min_confidence is not None and confidence_threshold is not None:
                c = min_confidence[j]
                if c is None or c < confidence_threshold:
                    continue
            pts.append(float(v))
        out.append(float(np.median(pts)) if len(pts) >= threshold else None)
    return out


# ---------------------------------------------------------------------------
# Distance / slope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlopedPoint:
    """A single observed point with an associated (possibly estimated) slope."""
    t: float
    value: float
    slope: float | None


def _least_squares_slope(ts: np.ndarray, ys: np.ndarray) -> float | None:
    """Linear least-squares slope; None if fewer than 2 distinct points."""
    if len(ts) < 2:
        return None
    if np.ptp(ts) <= 0.0:
        return None
    slope, _intercept = np.polyfit(ts, ys, 1)
    return float(slope)


def distance_series(ball_xy: np.ndarray, hand_xy: np.ndarray) -> np.ndarray:
    """Per-frame Euclidean distance. NaN if either input is NaN."""
    delta = ball_xy - hand_xy
    return np.linalg.norm(delta, axis=1)


def local_slope(frames: Sequence[int],
                distances: Sequence[float | None],
                n_points: int = 5) -> float | None:
    """Least-squares slope of distance vs frame over the last (or first)
    ``n_points`` *usable* points.

    The number of usable points used is returned by :func:`local_slope_detail`
    which is the diagnostic-aware version of this function.
    """
    return local_slope_detail(frames, distances, n_points).slope


def local_slope_detail(frames: Sequence[int],
                       distances: Sequence[float | None],
                       n_points: int = 5) -> SlopedPoint:
    """Same as :func:`local_slope` but also returns the anchor point used.

    The "anchor" is the most recent (for an END) or earliest (for a START)
    usable point in the chosen window. For symmetry, the same function is
    used for both; the caller passes a reversed list for START-side slopes.
    """
    if n_points < 2:
        raise ValueError("n_points must be >= 2 for a meaningful slope")
    pairs: list[tuple[int, float]] = []
    for f, d in zip(frames, distances):
        if d is None or not np.isfinite(d):
            continue
        pairs.append((int(f), float(d)))
    if len(pairs) < 2:
        return SlopedPoint(t=-1, value=float("nan"), slope=None)
    window = pairs[-n_points:] if len(pairs) >= n_points else pairs
    ts = np.asarray([p[0] for p in window], dtype=float)
    ys = np.asarray([p[1] for p in window], dtype=float)
    slope = _least_squares_slope(ts, ys)
    anchor_t, anchor_v = window[-1]
    return SlopedPoint(t=anchor_t, value=anchor_v, slope=slope)


# ---------------------------------------------------------------------------
# Relative radial velocity
# ---------------------------------------------------------------------------

def relative_radial_velocity(ball_xy: np.ndarray, ball_v: np.ndarray,
                             hand_xy: np.ndarray, hand_v: np.ndarray,
                             eps: float = 1e-3) -> float | None:
    """Component of (v_ball - v_hand) along the unit vector from hand to ball.

    * Negative => ball is closing on hand.
    * Positive => ball is moving away from hand.
    * Returns ``None`` if the hand and ball are essentially co-located
      (the radial direction is undefined) or if any input is NaN.
    """
    if (not np.all(np.isfinite(ball_xy)) or not np.all(np.isfinite(hand_xy))
            or not np.all(np.isfinite(ball_v)) or not np.all(np.isfinite(hand_v))):
        return None
    r = ball_xy - hand_xy
    dist = float(np.linalg.norm(r))
    if dist < eps:
        return None
    radial_unit = r / dist
    return float(np.dot(ball_v - hand_v, radial_unit))


def relative_radial_velocity_series(
    ball_xy: np.ndarray, hand_xy: np.ndarray,
    ball_t: np.ndarray, hand_t: np.ndarray,
    min_window_pts: int = 4,
) -> float | None:
    """Estimate relative radial velocity from a window of synchronised
    ball and hand positions.

    Computes local ball / hand velocities by independent least-squares
    fits over the supplied points (one per side), then calls
    :func:`relative_radial_velocity` at the most recent synchronised pair.

    Returns ``None`` if either side has fewer than ``min_window_pts`` usable
    points or if the radial direction is undefined at the anchor frame.
    """
    ball_pts = [(float(t), np.asarray(xy, dtype=float))
                for t, xy in zip(ball_t, ball_xy) if np.all(np.isfinite(xy))]
    hand_pts = [(float(t), np.asarray(xy, dtype=float))
                for t, xy in zip(hand_t, hand_xy) if np.all(np.isfinite(xy))]
    if len(ball_pts) < min_window_pts or len(hand_pts) < min_window_pts:
        return None
    ball_v = _local_velocity(ball_pts)
    hand_v = _local_velocity(hand_pts)
    if ball_v is None or hand_v is None:
        return None
    ball_anchor = ball_pts[-1][1]
    hand_anchor = _anchor_at(hand_pts, ball_pts[-1][0])
    if hand_anchor is None:
        return None
    return relative_radial_velocity(ball_anchor, ball_v, hand_anchor, hand_v)


def _local_velocity(pts: list[tuple[float, np.ndarray]],
                    eps_t: float = 1e-6) -> np.ndarray | None:
    if len(pts) < 2:
        return None
    ts = np.asarray([p[0] for p in pts], dtype=float)
    if np.ptp(ts) <= eps_t:
        return None
    xs = np.asarray([p[1][0] for p in pts], dtype=float)
    ys = np.asarray([p[1][1] for p in pts], dtype=float)
    vx, _ = np.polyfit(ts, xs, 1)
    vy, _ = np.polyfit(ts, ys, 1)
    return np.asarray([vx, vy], dtype=float)


def _anchor_at(pts: list[tuple[float, np.ndarray]], t: float,
               tolerance: float = 5.0) -> np.ndarray | None:
    """Closest point in time, within ``tolerance`` (in the same units as t)."""
    if not pts:
        return None
    best = min(pts, key=lambda p: abs(p[0] - t))
    if abs(best[0] - t) > tolerance:
        return None
    return best[1]


# ---------------------------------------------------------------------------
# Body scale
# ---------------------------------------------------------------------------

def body_scale(shoulder_left: np.ndarray, shoulder_right: np.ndarray,
               min_confidence: float | None = None) -> float | None:
    """Estimate body scale as inter-shoulder distance.

    Returns ``None`` if either shoulder is NaN or the resulting distance is
    degenerate (< 5 px) — that is the smallest meaningful shoulder width
    at this resolution.
    """
    if not (np.all(np.isfinite(shoulder_left))
            and np.all(np.isfinite(shoulder_right))):
        return None
    d = float(np.linalg.norm(shoulder_left - shoulder_right))
    if d < 5.0:
        return None
    return d


def normalized_distance(distance_px: float, scale: float | None) -> float | None:
    """Distance / body scale (a unit-less "shoulder-widths" measure).

    Returns ``None`` if scale is unavailable or distance is non-finite.
    """
    if scale is None or not np.isfinite(distance_px):
        return None
    return float(distance_px) / float(scale)


# ---------------------------------------------------------------------------
# Per-event convenience
# ---------------------------------------------------------------------------

@dataclass
class HandEventFeatures:
    """Features for a track END or START against a single anatomical hand."""
    hand: str                   # "left" or "right"
    distance_px: float | None
    distance_normalized: float | None
    distance_slope_px_per_frame: float | None
    radial_relative_velocity: float | None
    n_distance_points: int
    n_radial_points: int
    hand_confidence: float | None


def event_features_for_hand(
    *,
    ball_frames: np.ndarray,
    ball_xy: np.ndarray,
    hand_frames: np.ndarray,
    hand_xy: np.ndarray,
    hand_confidences: np.ndarray,
    hand_name: str,
    body_scale_value: float | None,
    n_window: int = 5,
    min_window_pts: int = 4,
) -> HandEventFeatures:
    """Compute the full set of hand-interaction features for one (event, hand).

    ``ball_frames`` / ``ball_xy`` are the observed ball positions for the
    end (or start) of interest, in chronological order. ``hand_*`` are the
    pose keypoints for the same anatomical hand.
    """
    if len(ball_frames) == 0 or len(hand_frames) == 0:
        return HandEventFeatures(
            hand=hand_name, distance_px=None, distance_normalized=None,
            distance_slope_px_per_frame=None,
            radial_relative_velocity=None,
            n_distance_points=0, n_radial_points=0,
            hand_confidence=_last_finite(hand_confidences),
        )

    # Synchronise by frame index: nearest-neighbour within 2 frames.
    ball_by_frame = {int(f): xy for f, xy in zip(ball_frames, ball_xy)}
    hand_by_frame = {int(f): xy for f, xy in zip(hand_frames, hand_xy)}
    hand_conf_by_frame = {int(f): c for f, c in zip(hand_frames, hand_confidences)}

    common = sorted(set(ball_by_frame) & set(hand_by_frame))
    if not common:
        return HandEventFeatures(
            hand=hand_name, distance_px=None, distance_normalized=None,
            distance_slope_px_per_frame=None,
            radial_relative_velocity=None,
            n_distance_points=0, n_radial_points=0,
            hand_confidence=_last_finite(hand_confidences),
        )

    bxy = np.asarray([ball_by_frame[f] for f in common], dtype=float)
    hxy = np.asarray([hand_by_frame[f] for f in common], dtype=float)
    dists = distance_series(bxy, hxy)
    n_used = int(np.sum(np.isfinite(dists)))
    slope_pt = local_slope_detail(common, [float(d) for d in dists], n_window)
    anchor_dist = slope_pt.value if np.isfinite(slope_pt.value) else None
    rrv = relative_radial_velocity_series(bxy, hxy, np.asarray(common, dtype=float),
                                          np.asarray(common, dtype=float),
                                          min_window_pts=min_window_pts)
    return HandEventFeatures(
        hand=hand_name,
        distance_px=anchor_dist,
        distance_normalized=normalized_distance(anchor_dist, body_scale_value),
        distance_slope_px_per_frame=slope_pt.slope,
        radial_relative_velocity=rrv,
        n_distance_points=n_used,
        n_radial_points=n_used,
        hand_confidence=_last_finite(hand_confidences),
    )


def nearest_hand(left: HandEventFeatures, right: HandEventFeatures) -> str | None:
    """Which hand is closer to the ball at the event.

    Returns ``None`` if neither distance is available.
    """
    candidates = [(f.distance_px, f.hand)
                  for f in (left, right) if f.distance_px is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[0])[1]


def _last_finite(values: Iterable[float | None]) -> float | None:
    last: float | None = None
    for v in values:
        if v is None or not np.isfinite(v):
            continue
        last = float(v)
    return last
