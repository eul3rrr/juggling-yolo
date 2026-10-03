"""Run the identity stage segment by segment."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Sequence

from src.tracking.assignment import Solution, solve_paths
from src.tracking.ball_count import estimate_ball_count, resolve_ball_counts, simultaneous_histogram
from src.tracking.ballistics import AccelProfile, flight_samples, reference_accel
from src.tracking.links import (
    LinkCostConfig, SegmentContext, TrackletInfo, build_links, describe_tracklet,
    is_clutter, px_per_metre,
)
from src.tracking.states import StateConfig, TimelineRow, build_timeline
from src.tracking.tracklets import SegmentSpan, Tracklet, group_by_segment, median_body_scale


@dataclass(frozen=True)
class SegmentResult:
    span: SegmentSpan
    accel_y: float | None
    accel_source: str            # segment / body_scale / video / none
    n_balls: int
    n_balls_source: str          # estimated / video_mode / override
    count_histogram: dict[int, int]
    infos: dict[int, TrackletInfo]
    clutter: tuple[int, ...]
    solution: Solution | None
    timeline: tuple[TimelineRow, ...]


def _segment_accels(samples: dict[int, list[tuple[int, float]]], spans: Sequence[SegmentSpan],
                    hands_by_frame: dict) -> dict[int, tuple[float | None, str, float | None]]:
    """Gravity per segment, falling back to body scale and then the whole video.

    Gravity in pixels tracks the performer's size in frame, so a segment with
    too little flight borrows the video's gravity-to-shoulder-width ratio.
    """
    scales = {s.index: median_body_scale(hands_by_frame, s) for s in spans}
    own = {s.index: reference_accel([a for _, a in samples[s.index]]) for s in spans}
    ratios = [own[i] / scales[i] for i in own if own[i] is not None and scales[i]]
    ratio = median(ratios) if ratios else None
    video = reference_accel([a for ss in samples.values() for _, a in ss])
    out = {}
    for span in spans:
        i = span.index
        if own[i] is not None:
            out[i] = (own[i], "segment", scales[i])
        elif ratio is not None and scales[i]:
            out[i] = (ratio * scales[i], "body_scale", scales[i])
        elif video is not None:
            out[i] = (video, "video", scales[i])
        else:
            out[i] = (None, "none", scales[i])
    return out


def track_video(tracklets: dict[int, Tracklet], spans: Sequence[SegmentSpan], fps: float,
                hands_by_frame: dict, balls: int | None = None,
                balls_per_segment: dict[int, int] | None = None,
                cfg: LinkCostConfig = LinkCostConfig(),
                state_cfg: StateConfig = StateConfig()) -> list[SegmentResult]:
    grouped = group_by_segment(tracklets, spans)
    samples = {s.index: flight_samples([t.points for t in grouped[s.index]]) for s in spans}
    accels = _segment_accels(samples, spans, hands_by_frame)
    contexts: dict[int, SegmentContext] = {}
    clutter: dict[int, tuple[int, ...]] = {}
    estimates: dict[int, int] = {}
    histograms: dict[int, dict[int, int]] = {}
    for span in spans:
        accel, _, scale = accels[span.index]
        if accel is None:
            continue
        profile = AccelProfile(samples[span.index], accel, radius_frames=round(0.5 * fps))
        ctx = SegmentContext(span, fps, profile, px_per_metre(accel, fps), hands_by_frame, scale)
        contexts[span.index] = ctx
        clutter[span.index] = tuple(t.track_id for t in grouped[span.index]
                                    if is_clutter(t, ctx, cfg, state_cfg))
        in_play = [t for t in grouped[span.index] if t.track_id not in clutter[span.index]]
        estimates[span.index] = estimate_ball_count(in_play, span, fps)
        histograms[span.index] = simultaneous_histogram(in_play, span)
    counts = resolve_ball_counts(estimates, balls, balls_per_segment)

    results = []
    for span in spans:
        accel, accel_source, _ = accels[span.index]
        ctx = contexts.get(span.index)
        if ctx is None:
            results.append(SegmentResult(span, None, accel_source, 0, "none", {}, {}, (), None, ()))
            continue
        n_balls, n_source = counts[span.index]
        in_play = [t for t in grouped[span.index] if t.track_id not in clutter[span.index]]
        infos = {t.track_id: describe_tracklet(t, ctx, cfg, state_cfg) for t in in_play}
        described = list(infos.values())
        solution = solve_paths(described, build_links(described, ctx, cfg), n_balls, ctx, cfg)
        timeline: list[TimelineRow] = []
        for ball_id, (path, links) in enumerate(zip(solution.paths, solution.links), start=1):
            timeline += build_timeline(ball_id, [infos[tid] for tid in path], links, span,
                                       hands_by_frame, ctx.profile)
        results.append(SegmentResult(span, accel, accel_source, n_balls, n_source,
                                     histograms[span.index], infos, clutter[span.index],
                                     solution, tuple(timeline)))
    return results
