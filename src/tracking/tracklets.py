"""Observed tracklets, wrist lookups and per-segment grouping."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Sequence

Point = tuple[int, float, float]  # frame, x, y
HANDS = ("LEFT", "RIGHT")


@dataclass(frozen=True)
class Tracklet:
    track_id: int
    points: tuple[Point, ...]  # observed rows only, sorted by frame

    @property
    def first_frame(self) -> int:
        return self.points[0][0]

    @property
    def last_frame(self) -> int:
        return self.points[-1][0]

    @property
    def n_observed(self) -> int:
        return len(self.points)


@dataclass(frozen=True)
class SegmentSpan:
    """Half-open frame range ``[start, end)`` that tracklets never cross."""
    index: int
    start: int
    end: int


def load_observed_tracklets(path: Path) -> dict[int, Tracklet]:
    """Load a Norfair tracklet CSV, keeping only rows with a real detection.

    Coasting rows (``observed == 0``) are Kalman predictions, so a tracklet ends
    at its last detection. A CSV without the column counts every row as observed.
    """
    rows: dict[int, list[Point]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed", "1") != "1":
                continue
            rows.setdefault(int(row["track_id"]), []).append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    return {tid: Tracklet(tid, tuple(sorted(points))) for tid, points in rows.items()}


def group_by_segment(tracklets: dict[int, Tracklet],
                     spans: Sequence[SegmentSpan]) -> dict[int, list[Tracklet]]:
    """Assign each tracklet to the span holding its first frame; others are left out."""
    grouped: dict[int, list[Tracklet]] = {span.index: [] for span in spans}
    for tracklet in sorted(tracklets.values(), key=lambda t: (t.first_frame, t.track_id)):
        for span in spans:
            if span.start <= tracklet.first_frame < span.end:
                grouped[span.index].append(tracklet)
                break
    return grouped


def wrist(hands_by_frame: dict, frame: int, hand: str) -> tuple[float, float] | None:
    row = hands_by_frame.get(frame)
    return row.get(hand.lower()) if row else None


def body_scale(hands_by_frame: dict, frame: int) -> float | None:
    row = hands_by_frame.get(frame)
    scale = row.get("body_scale") if row else None
    return scale if scale is not None and math.isfinite(scale) and scale >= 5.0 else None


def median_body_scale(hands_by_frame: dict, span: SegmentSpan) -> float | None:
    scales = [s for frame in range(span.start, span.end)
              if (s := body_scale(hands_by_frame, frame)) is not None]
    return float(median(scales)) if scales else None


def wrist_distance(hands_by_frame: dict, point: Point, hand: str) -> float | None:
    """Pixel distance from a ball point to that frame's wrist, if the wrist is usable."""
    xy = wrist(hands_by_frame, point[0], hand)
    if xy is None:
        return None
    return math.hypot(point[1] - xy[0], point[2] - xy[1])
