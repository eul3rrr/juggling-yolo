"""Per-frame ball state: airborne, held by a hand, or hidden."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.tracking.ballistics import AccelProfile, Point, fit_flight
from src.tracking.tracklets import HANDS, Tracklet, body_scale, wrist, wrist_distance

AIRBORNE = "AIRBORNE"
HELD = "HELD"
HIDDEN = "HIDDEN"


@dataclass(frozen=True)
class StateConfig:
    flight_rmse_px: float = 1.6          # a carried ball misfits its window by ~3.5 px
    held_max_normalized: float = 0.7     # same reach as the POSSIBLE hand band
    held_max_raw_px: float = 130.0
    min_run: int = 3                     # shorter state runs are absorbed


@dataclass(frozen=True)
class PointState:
    state: str   # AIRBORNE or HELD
    hand: str    # LEFT / RIGHT / "" (unknown or not held)


@dataclass(frozen=True)
class TimelineRow:
    frame: int
    ball_id: int
    state: str
    hand: str
    x: float | None
    y: float | None
    position_source: str   # detection / predicted / interpolated / wrist / ""
    track_id: int | None


def _local_flight_rmse(points: Sequence[Point], index: int, accel_y: float, window: int) -> float | None:
    """Best fit among the windows ending at, centred on and starting at ``index``.

    One-sided windows keep the last flight frame before a catch (and the first
    after a throw) from being judged by a window that straddles the hand.
    """
    if len(points) < 3:
        return None
    if len(points) <= window:
        return fit_flight(points, accel_y).rmse
    best: float | None = None
    for low in (index - window + 1, index - window // 2, index):
        high = low + window
        if low < 0 or high > len(points):
            continue
        chunk = points[low:high]
        if chunk[-1][0] - chunk[0][0] > window + 1:
            continue
        rmse = fit_flight(chunk, accel_y).rmse
        best = rmse if best is None else min(best, rmse)
    return best


def _nearest_hand(hands_by_frame: dict, point: Point, fallback_scale: float | None,
                  cfg: StateConfig) -> str | None:
    """Hand within holding reach of the ball, LEFT/RIGHT, or None."""
    scale = body_scale(hands_by_frame, point[0]) or fallback_scale
    best: tuple[float, str] | None = None
    for hand in HANDS:
        distance = wrist_distance(hands_by_frame, point, hand)
        if distance is None:
            continue
        within = (distance / scale <= cfg.held_max_normalized) if scale else (
            distance <= cfg.held_max_raw_px)
        if within and (best is None or distance < best[0]):
            best = (distance, hand)
    return best[1] if best else None


def _absorb_short_runs(labels: list[bool], min_run: int) -> list[bool]:
    """Majority-smooth the labels, then flip runs shorter than ``min_run``
    that sit between two longer runs."""
    half = min_run - 1
    if len(labels) > 2 * half:
        smoothed = list(labels)
        for i in range(half, len(labels) - half):
            window = labels[i - half:i + half + 1]
            smoothed[i] = sum(window) * 2 > len(window)
        labels = smoothed
    runs: list[list] = []
    for value in labels:
        if runs and runs[-1][0] == value:
            runs[-1][1] += 1
        else:
            runs.append([value, 1])
    for i in range(1, len(runs) - 1):
        if runs[i][1] < min_run and runs[i - 1][1] >= min_run and runs[i + 1][1] >= min_run:
            runs[i][0] = runs[i - 1][0]
    return [value for value, count in runs for _ in range(count)]


def classify_points(tracklet: Tracklet, hands_by_frame: dict, profile: AccelProfile,
                    fallback_scale: float | None = None,
                    cfg: StateConfig = StateConfig()) -> tuple[PointState, ...]:
    """Label each observed point as free flight or held.

    A point is airborne when a short window around it follows a parabola with
    the local gravity. Otherwise it is being carried: held by the nearest wrist
    within reach, or held with the hand unknown when no wrist is usable. The
    window is sized so a flight arc bends by the same number of pixels at any
    playback speed, which keeps one residual limit valid in slow motion.
    """
    points = tracklet.points
    ballistic = []
    for index, point in enumerate(points):
        rmse = _local_flight_rmse(points, index, profile.at(point[0]), profile.window(point[0]))
        ballistic.append(rmse is None or rmse <= cfg.flight_rmse_px)
    ballistic = _absorb_short_runs(ballistic, cfg.min_run)
    states = []
    for point, flying in zip(points, ballistic):
        if flying:
            states.append(PointState(AIRBORNE, ""))
        else:
            states.append(PointState(HELD, _nearest_hand(hands_by_frame, point, fallback_scale, cfg) or ""))
    return tuple(states)


def flight_tail(tracklet: Tracklet, states: Sequence[PointState], max_points: int = 10) -> tuple[Point, ...]:
    """Trailing run of airborne points (empty when the tracklet ends held)."""
    count = 0
    for state in reversed(states):
        if state.state != AIRBORNE or count == max_points:
            break
        count += 1
    return tracklet.points[len(tracklet.points) - count:] if count else ()


def flight_head(tracklet: Tracklet, states: Sequence[PointState], max_points: int = 10) -> tuple[Point, ...]:
    """Leading run of airborne points (empty when the tracklet starts held)."""
    count = 0
    for state in states:
        if state.state != AIRBORNE or count == max_points:
            break
        count += 1
    return tracklet.points[:count]


def link_frame(a, b) -> int:
    """Frame at the middle of the gap between two tracklets, for local gravity."""
    return (a.tracklet.last_frame + b.tracklet.first_frame) // 2


def _held_rows(ball_id: int, frames: range, hand: str, hands_by_frame: dict) -> list[TimelineRow]:
    rows = []
    for frame in frames:
        xy = wrist(hands_by_frame, frame, hand) if hand else None
        rows.append(TimelineRow(frame, ball_id, HELD, hand,
                                xy[0] if xy else None, xy[1] if xy else None,
                                "wrist" if xy else "", None))
    return rows


def _tracklet_rows(ball_id: int, tracklet: Tracklet, states: Sequence[PointState],
                   profile: AccelProfile) -> list[TimelineRow]:
    rows: list[TimelineRow] = []
    points = tracklet.points
    for index, (point, state) in enumerate(zip(points, states)):
        rows.append(TimelineRow(point[0], ball_id, state.state, state.hand,
                                point[1], point[2], "detection", tracklet.track_id))
        if index + 1 == len(points) or points[index + 1][0] == point[0] + 1:
            continue
        nxt, nxt_state = points[index + 1], states[index + 1]
        missing = range(point[0] + 1, nxt[0])
        if state.state == AIRBORNE and nxt_state.state == AIRBORNE:
            fit = fit_flight([*points[max(0, index - 4):index + 1], *points[index + 1:index + 6]],
                             profile.at((point[0] + nxt[0]) // 2))
            for frame in missing:
                x, y = fit.predict(frame)
                rows.append(TimelineRow(frame, ball_id, AIRBORNE, "", x, y, "predicted", tracklet.track_id))
        else:
            hand = state.hand if state.state == HELD else nxt_state.hand
            span = nxt[0] - point[0]
            for frame in missing:
                w = (frame - point[0]) / span
                rows.append(TimelineRow(frame, ball_id, HELD, hand,
                                        point[1] + w * (nxt[1] - point[1]),
                                        point[2] + w * (nxt[2] - point[2]),
                                        "interpolated", tracklet.track_id))
    return rows


def build_timeline(ball_id: int, path: Sequence, links: Sequence, span, hands_by_frame: dict,
                   profile: AccelProfile) -> list[TimelineRow]:
    """One row per frame of the segment for a single ball identity.

    ``path`` is the ordered ``TrackletInfo`` list of the identity and ``links``
    the chosen link between each consecutive pair.
    """
    rows: list[TimelineRow] = []
    if not path:
        return rows
    first, last = path[0], path[-1]
    lead = range(span.start, first.tracklet.first_frame)
    if first.start.hand_evidence or first.states[0].state == HELD:
        rows += _held_rows(ball_id, lead, first.start.hand or first.states[0].hand, hands_by_frame)
    else:
        rows += [TimelineRow(f, ball_id, HIDDEN, "", None, None, "", None) for f in lead]
    for index, info in enumerate(path):
        rows += _tracklet_rows(ball_id, info.tracklet, info.states, profile)
        if index + 1 == len(path):
            break
        link, nxt = links[index], path[index + 1]
        gap = range(info.tracklet.last_frame + 1, nxt.tracklet.first_frame)
        if link.kind == "flight":
            fit = fit_flight([*info.tail, *nxt.head], profile.at(link_frame(info, nxt)))
            for frame in gap:
                x, y = fit.predict(frame)
                rows.append(TimelineRow(frame, ball_id, AIRBORNE, "", x, y, "predicted", None))
        elif link.kind == "hand":
            rows += _held_rows(ball_id, gap, link.hand, hands_by_frame)
        else:
            rows += [TimelineRow(f, ball_id, HIDDEN, "", None, None, "", None) for f in gap]
    trail = range(last.tracklet.last_frame + 1, span.end)
    if last.end.hand_evidence or last.states[-1].state == HELD:
        rows += _held_rows(ball_id, trail, last.end.hand or last.states[-1].hand, hands_by_frame)
    else:
        rows += [TimelineRow(f, ball_id, HIDDEN, "", None, None, "", None) for f in trail]
    return rows
