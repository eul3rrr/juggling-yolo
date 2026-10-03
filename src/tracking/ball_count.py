"""Estimate how many balls a segment has from simultaneous tracklets."""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from src.tracking.tracklets import SegmentSpan, Tracklet


def simultaneous_histogram(tracklets: Sequence[Tracklet], span: SegmentSpan) -> dict[int, int]:
    """``{count: frames}`` of observed tracklets per frame over the span."""
    per_frame: Counter[int] = Counter()
    for tracklet in tracklets:
        for frame, _, _ in tracklet.points:
            per_frame[frame] += 1
    histogram = Counter(per_frame.get(frame, 0) for frame in range(span.start, span.end))
    return dict(sorted(histogram.items()))


def estimate_ball_count(tracklets: Sequence[Tracklet], span: SegmentSpan, fps: float,
                        min_seconds: float = 0.15, min_fraction: float = 0.02) -> int:
    """Largest number of balls seen at once for long enough to be believed.

    A count must hold for at least ``min_seconds`` and ``min_fraction`` of the
    segment, so a brief false positive does not raise it. Balls resting in a
    hand are often undetected, so this tends to be low rather than high.
    """
    histogram = simultaneous_histogram(tracklets, span)
    needed = max(min_seconds * fps, min_fraction * (span.end - span.start))
    best = 0
    for count in sorted(histogram):
        frames_at_least = sum(n for c, n in histogram.items() if c >= count)
        if count > 0 and frames_at_least >= needed:
            best = count
    return best


def resolve_ball_counts(estimates: dict[int, int], override: int | None = None,
                        per_segment: dict[int, int] | None = None) -> dict[int, tuple[int, str]]:
    """Pick the count per segment and say where it came from.

    Unless overridden, a segment gets at least the video's most common estimate.
    The solver treats the count as a ceiling (a spare identity may stay empty),
    while a count that is too low forces a real ball to be dropped or merged,
    so the estimate is deliberately biased upward.
    """
    usable = [n for n in estimates.values() if n > 0]
    video_mode = max(Counter(usable).items(), key=lambda kv: (kv[1], kv[0]))[0] if usable else 0
    resolved: dict[int, tuple[int, str]] = {}
    for index, estimate in estimates.items():
        if per_segment and index in per_segment:
            resolved[index] = (per_segment[index], "override")
        elif override is not None:
            resolved[index] = (override, "override")
        elif estimate >= video_mode:
            resolved[index] = (estimate, "estimated")
        else:
            resolved[index] = (video_mode, "video_mode")
    return resolved
