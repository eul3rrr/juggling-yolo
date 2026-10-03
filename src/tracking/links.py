"""Candidate links between tracklets: flight, near, hand, or hidden.

Costs are in "observed frames at 60 fps": using a tracklet earns one unit per
observed 1/60 s, so a link is worth taking when it costs less than the
observations it lets an identity keep.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import hand_boundaries as hb

from src.tracking.ballistics import AccelProfile, Point, fit_flight
from src.tracking.states import (
    HELD, PointState, StateConfig, classify_points, flight_head, flight_tail, link_frame,
)
from src.tracking.tracklets import SegmentSpan, Tracklet, wrist_distance, body_scale, HANDS

GRAVITY_M_PER_S2 = 9.81


@dataclass(frozen=True)
class LinkCostConfig:
    reward_per_second: float = 60.0      # value of keeping one second of observations

    # flight: one free-flight arc joins the two tracklets
    flight_max_gap_seconds: float = 1.0
    flight_max_rmse_m: float = 0.025
    flight_base: float = 0.5
    flight_rmse_weight_per_m: float = 200.0
    flight_gap_weight_per_second: float = 2.0

    # near: the detector lost the ball for a moment and it reappears where a
    # straight continuation puts it (flying or carried, no hand needed)
    near_max_gap_seconds: float = 0.2
    near_max_error_m: float = 0.15
    near_base: float = 1.0
    near_error_weight_per_m: float = 60.0
    near_gap_weight_per_second: float = 10.0

    # hand: ends entering a hand, restarts leaving the same hand
    hand_max_hold_seconds: float = 3.0
    hand_base: float = 2.0
    hand_distance_weight: float = 4.0    # per shoulder width, summed over both ends
    hand_missing_distance: float = 0.7
    hand_hold_weight_per_second2: float = 6.0

    # hidden: no flight and no shared hand explains the gap
    hidden_max_gap_seconds: float = 4.0
    hidden_base: float = 10.0
    hidden_hand_evidence_bonus: float = 2.0   # per end that does show a hand
    hidden_gap_weight_per_second2: float = 4.0
    hidden_distance_weight_per_m: float = 8.0

    # a flight arc extended past the tracklet counts as hand evidence when it
    # comes this close to a wrist within this long
    arc_contact_max_normalized: float = 0.35
    arc_contact_max_raw_px: float = 60.0
    arc_contact_max_seconds: float = 0.35

    # an identity first or last seen away from a segment edge. With a hand at
    # that end the ball was simply resting in it, unseen, which is cheap.
    birth_cost: float = 15.0
    death_cost: float = 15.0
    birth_from_hand_cost: float = 4.0
    death_in_hand_cost: float = 4.0
    edge_margin_seconds: float = 0.25

    # stationary, never near a hand: background clutter, not a ball in play
    clutter_max_extent_m: float = 0.03
    clutter_min_seconds: float = 0.1


@dataclass(frozen=True)
class SegmentContext:
    span: SegmentSpan
    fps: float
    profile: AccelProfile     # local vertical acceleration, px/frame^2
    px_per_m: float           # from the real-time (reference) acceleration
    hands_by_frame: dict
    body_scale: float | None  # median shoulder width in px


@dataclass(frozen=True)
class Boundary:
    hand_evidence: bool
    hands: tuple[str, ...]
    hand: str                      # preferred hand, or the only eligible one, or ""
    distance_normalized: float | None
    source: str = ""               # wrist / carried / arc: what showed the hand


@dataclass(frozen=True)
class TrackletInfo:
    tracklet: Tracklet
    states: tuple[PointState, ...]
    tail: tuple[Point, ...]
    head: tuple[Point, ...]
    start: Boundary
    end: Boundary


@dataclass(frozen=True)
class Link:
    source: int
    target: int
    kind: str                  # flight / near / hand / hidden
    cost: float
    gap_frames: int
    hand: str = ""
    fit_rmse_px: float | None = None


def px_per_metre(accel_y: float, fps: float) -> float:
    """Image scale at the balls' depth, from how fast they fall."""
    return accel_y * fps * fps / GRAVITY_M_PER_S2


def _normalized(distance: float, frame: int, ctx: SegmentContext) -> float | None:
    scale = body_scale(ctx.hands_by_frame, frame) or ctx.body_scale
    return distance / scale if scale else None


def _arc_contact(points: Sequence[Point], forward: bool, ctx: SegmentContext,
                 cfg: LinkCostConfig) -> Boundary | None:
    """Extend a flight arc beyond the tracklet until it reaches a wrist.

    A ball is usually lost a few frames before the catch (the hand covers it)
    and found a few frames after the throw, so the arc, not the last detection,
    says which hand it went to or came from.
    """
    if len(points) < 3:
        return None
    edge = points[-1][0] if forward else points[0][0]
    fit = fit_flight(points, ctx.profile.at(edge))
    reach = round(cfg.arc_contact_max_seconds * ctx.fps / max(ctx.profile.speed(edge), 0.05))
    for step in range(1, reach + 1):
        frame = edge + step if forward else edge - step
        if not ctx.span.start <= frame < ctx.span.end:
            break
        x, y = fit.predict(frame)
        best: tuple[float, str, float | None] | None = None
        for hand in HANDS:
            distance = wrist_distance(ctx.hands_by_frame, (frame, x, y), hand)
            if distance is None:
                continue
            normalized = _normalized(distance, frame, ctx)
            close = (normalized <= cfg.arc_contact_max_normalized) if normalized is not None else (
                distance <= cfg.arc_contact_max_raw_px)
            if close and (best is None or distance < best[0]):
                best = (distance, hand, normalized)
        if best:
            return Boundary(True, (best[1],), best[1], best[2], "arc")
    return None


def _carried_hand(states_from_edge: Sequence[PointState]) -> str:
    """Hand named most often in the held run at this end of a tracklet, or ""."""
    names: list[str] = []
    for state in states_from_edge:
        if state.state != HELD:
            break
        if state.hand:
            names.append(state.hand)
    return max(HANDS, key=names.count) if names else ""


def _boundary(tracklet: Tracklet, kind: str, states: Sequence[PointState],
              flight: Sequence[Point], ctx: SegmentContext, cfg: LinkCostConfig) -> Boundary:
    """Which hand a tracklet starts from or ends in, from three kinds of evidence.

    The canonical boundary classifier comes first. Failing that, the ball being
    carried at that end counts, then a flight arc that reaches a wrist.
    """
    points = [hb.BoundaryPoint(*p) for p in tracklet.points]
    assessment = hb.assess_boundary(tracklet.track_id, kind, points, ctx.hands_by_frame)
    hands = assessment.eligible_hands
    if hands:
        hand = assessment.preferred_hand or (hands[0] if len(hands) == 1 else "")
        distances = [assessment.hand_results[h].endpoint_distance_normalized for h in hands]
        distances = [d for d in distances if d is not None]
        return Boundary(True, hands, hand, min(distances) if distances else None, "wrist")
    carried = _carried_hand(states if kind == "START" else states[::-1])
    if carried:
        point = tracklet.points[0 if kind == "START" else -1]
        distance = wrist_distance(ctx.hands_by_frame, point, carried)
        normalized = None if distance is None else _normalized(distance, point[0], ctx)
        return Boundary(True, (carried,), carried, normalized, "carried")
    contact = _arc_contact(flight, kind == "END", ctx, cfg)
    return contact or Boundary(False, (), "", None)


def describe_tracklet(tracklet: Tracklet, ctx: SegmentContext,
                      cfg: LinkCostConfig = LinkCostConfig(),
                      state_cfg: StateConfig = StateConfig()) -> TrackletInfo:
    states = classify_points(tracklet, ctx.hands_by_frame, ctx.profile, ctx.body_scale, state_cfg)
    tail = flight_tail(tracklet, states, ctx.profile.window(tracklet.last_frame) + 3)
    head = flight_head(tracklet, states, ctx.profile.window(tracklet.first_frame) + 3)
    return TrackletInfo(
        tracklet, states, tail, head,
        _boundary(tracklet, "START", states, head, ctx, cfg),
        _boundary(tracklet, "END", states, tail, ctx, cfg),
    )


def is_clutter(tracklet: Tracklet, ctx: SegmentContext, cfg: LinkCostConfig = LinkCostConfig(),
               state_cfg: StateConfig = StateConfig()) -> bool:
    """A tracklet that never moves and is never within reach of a wrist.

    A ball resting in a hand also sits still, so stillness alone is not enough;
    without any wrist data nothing is called clutter.
    """
    if tracklet.n_observed < cfg.clutter_min_seconds * ctx.fps:
        return False
    xs = [p[1] for p in tracklet.points]
    ys = [p[2] for p in tracklet.points]
    if max(max(xs) - min(xs), max(ys) - min(ys)) > cfg.clutter_max_extent_m * ctx.px_per_m:
        return False
    seen_wrist = False
    for point in tracklet.points:
        scale = body_scale(ctx.hands_by_frame, point[0]) or ctx.body_scale
        for hand in HANDS:
            distance = wrist_distance(ctx.hands_by_frame, point, hand)
            if distance is None:
                continue
            seen_wrist = True
            if (distance / scale <= state_cfg.held_max_normalized) if scale else (
                    distance <= state_cfg.held_max_raw_px):
                return False
    return seen_wrist


def _real_seconds(a: TrackletInfo, b: TrackletInfo, gap: int, ctx: SegmentContext) -> float:
    """Gap length in real time; slow motion stretches it in frames."""
    return gap / ctx.fps * ctx.profile.speed(link_frame(a, b))


def _flight_link(a: TrackletInfo, b: TrackletInfo, gap: int, ctx: SegmentContext,
                 cfg: LinkCostConfig) -> Link | None:
    seconds = _real_seconds(a, b, gap, ctx)
    if seconds > cfg.flight_max_gap_seconds:
        return None
    if not a.tail or not b.head or len(a.tail) + len(b.head) < 3:
        return None
    rmse = fit_flight([*a.tail, *b.head], ctx.profile.at(link_frame(a, b))).rmse
    rmse_m = rmse / ctx.px_per_m
    if rmse_m > cfg.flight_max_rmse_m:
        return None
    cost = (cfg.flight_base + cfg.flight_rmse_weight_per_m * rmse_m
            + cfg.flight_gap_weight_per_second * seconds)
    return Link(a.tracklet.track_id, b.tracklet.track_id, "flight", cost, gap, "", rmse)


def _near_link(a: TrackletInfo, b: TrackletInfo, gap: int, ctx: SegmentContext,
               cfg: LinkCostConfig) -> Link | None:
    seconds = _real_seconds(a, b, gap, ctx)
    if seconds > cfg.near_max_gap_seconds:
        return None
    if a.tail and b.head:
        return None  # both ends are flying: the flight arc decides, not a straight line
    points = a.tracklet.points
    end, start = points[-1], b.tracklet.points[0]
    vx = vy = 0.0
    if len(points) >= 2 and end[0] - points[-2][0] <= 3:
        frames = end[0] - points[-2][0]
        vx, vy = (end[1] - points[-2][1]) / frames, (end[2] - points[-2][2]) / frames
    elapsed = start[0] - end[0]
    error_m = math.hypot(end[1] + vx * elapsed - start[1],
                         end[2] + vy * elapsed - start[2]) / ctx.px_per_m
    if error_m > cfg.near_max_error_m:
        return None
    cost = (cfg.near_base + cfg.near_error_weight_per_m * error_m
            + cfg.near_gap_weight_per_second * seconds)
    return Link(a.tracklet.track_id, b.tracklet.track_id, "near", cost, gap)


def _hand_link(a: TrackletInfo, b: TrackletInfo, gap: int, ctx: SegmentContext,
               cfg: LinkCostConfig) -> Link | None:
    if not (a.end.hand_evidence and b.start.hand_evidence):
        return None
    shared = [h for h in a.end.hands if h in b.start.hands]
    seconds = _real_seconds(a, b, gap, ctx)
    if not shared or seconds > cfg.hand_max_hold_seconds:
        return None
    if a.end.hand in shared and b.start.hand in ("", a.end.hand):
        hand = a.end.hand
    elif b.start.hand in shared:
        hand = b.start.hand
    else:
        hand = shared[0]
    distance = sum(cfg.hand_missing_distance if d is None else d
                   for d in (a.end.distance_normalized, b.start.distance_normalized))
    cost = (cfg.hand_base + cfg.hand_distance_weight * distance
            + cfg.hand_hold_weight_per_second2 * seconds * seconds)
    return Link(a.tracklet.track_id, b.tracklet.track_id, "hand", cost, gap, hand)


def _hidden_link(a: TrackletInfo, b: TrackletInfo, gap: int, ctx: SegmentContext,
                 cfg: LinkCostConfig) -> Link | None:
    seconds = _real_seconds(a, b, gap, ctx)
    if seconds > cfg.hidden_max_gap_seconds:
        return None
    end, start = a.tracklet.points[-1], b.tracklet.points[0]
    distance_m = math.hypot(start[1] - end[1], start[2] - end[2]) / ctx.px_per_m
    evidence = int(a.end.hand_evidence) + int(b.start.hand_evidence)
    cost = (cfg.hidden_base - cfg.hidden_hand_evidence_bonus * evidence
            + cfg.hidden_gap_weight_per_second2 * seconds * seconds
            + cfg.hidden_distance_weight_per_m * distance_m)
    hand = b.start.hand if b.start.hand_evidence else ""
    return Link(a.tracklet.track_id, b.tracklet.track_id, "hidden", cost, gap, hand)


def build_links(infos: Sequence[TrackletInfo], ctx: SegmentContext,
                cfg: LinkCostConfig = LinkCostConfig()) -> list[Link]:
    """Cheapest explanation for every ordered pair where the second starts later.

    The hold and hidden penalties grow with the square of the gap. A linear
    penalty could not tell which of two waiting balls leaves a hand first,
    because every pairing would sum to the same total time.
    """
    links: list[Link] = []
    for a in infos:
        for b in infos:
            gap = b.tracklet.first_frame - a.tracklet.last_frame - 1
            if a is b or gap < 0:
                continue
            options = [link for link in (
                _flight_link(a, b, gap, ctx, cfg),
                _near_link(a, b, gap, ctx, cfg),
                _hand_link(a, b, gap, ctx, cfg),
                _hidden_link(a, b, gap, ctx, cfg),
            ) if link is not None]
            if options:
                links.append(min(options, key=lambda link: link.cost))
    return links
