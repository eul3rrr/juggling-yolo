"""Deterministic END -> successor candidate generation for vision judging.

Reuses the canonical tracklet loader so the tool sees exactly the observed rows
the rest of the pipeline sees.  Candidates are ranked with the same
constant-velocity prediction the airborne stitcher uses (last two observed
points), which is what the review UI shows next to the model verdict.

Nothing here changes the stitcher or any identity layer.
"""
from __future__ import annotations

from pathlib import Path

from scripts.review_track_events import Track, load_tracklets
from src.annotation.segments import Segment, parse_losslesscut_csv


def track_velocity(track: Track) -> tuple[float, float]:
    """Constant-velocity estimate in px/frame from the last two observed points."""
    observed = track.observed
    if len(observed) < 2:
        return 0.0, 0.0
    a, b = observed[-2], observed[-1]
    span = b.frame - a.frame
    if span <= 0:
        return 0.0, 0.0
    return (b.center_x - a.center_x) / span, (b.center_y - a.center_y) / span

def assign_segment(track: Track, fps: float, segments: list[Segment]) -> int | None:
    """Segment index owning a tracklet, decided by its first observed frame."""
    first = track.first_observed
    if first is None:
        return None
    seconds = first.frame / fps
    for segment in segments:
        if segment.start <= seconds < segment.end:
            return segment.index
    return None


def build_events(tracks: dict[int, Track], segments: list[Segment], fps: float,
                 frame_count: int, window_frames: int = 30, top_k: int = 3) -> tuple[list[dict], dict]:
    """One event per tracklet END that has at least one later candidate start.

    Candidates are tracklets whose first observed frame is strictly after the
    END frame, inside the same LosslessCut segment (per-segment tracking means
    no identity can cross a cut), and within ``window_frames``.  They are ranked
    by constant-velocity prediction error and truncated to ``top_k``.
    """
    if window_frames <= 0:
        raise ValueError("window_frames must be positive")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    by_segment: dict[int, list[Track]] = {}
    for track in tracks.values():
        if track.first_observed is None or track.last_observed is None:
            continue
        index = assign_segment(track, fps, segments)
        if index is None:
            continue
        by_segment.setdefault(index, []).append(track)

    events: list[dict] = []
    total_ends = 0
    for index in sorted(by_segment):
        rows = by_segment[index]
        starts = sorted(((t.first_observed.frame, t) for t in rows if t.first_observed is not None),
                        key=lambda p: (p[0], p[1].track_id))
        ends = sorted(((t.last_observed.frame, t) for t in rows if t.last_observed is not None),
                      key=lambda p: (p[0], p[1].track_id))
        for _, track in ends:
            total_ends += 1
            last = track.last_observed
            assert last is not None
            vx, vy = track_velocity(track)
            candidates = []
            for first_frame, other in starts:
                gap = first_frame - last.frame
                if gap <= 0 or gap > window_frames:
                    continue
                first = other.first_observed
                if first is None:
                    continue
                predicted_x = last.center_x + vx * gap
                predicted_y = last.center_y + vy * gap
                error = ((predicted_x - first.center_x) ** 2 + (predicted_y - first.center_y) ** 2) ** 0.5
                candidates.append(dict(
                    track_id=other.track_id,
                    first_frame=first_frame,
                    first_x=first.center_x,
                    first_y=first.center_y,
                    first_confidence=first.confidence,
                    observed_len=len(other.observed),
                    gap_frames=gap,
                    gap_seconds=gap / fps,
                    predicted_x=predicted_x,
                    predicted_y=predicted_y,
                    prediction_error=error,
                ))
            if not candidates:
                continue
            candidates.sort(key=lambda c: (c["prediction_error"], c["gap_frames"], c["track_id"]))
            candidates = candidates[:top_k]
            for rank, candidate in enumerate(candidates, 1):
                candidate["rank"] = rank
            events.append(dict(
                event_key=f"end:{track.track_id}:{last.frame}",
                segment_index=index,
                window_frames=window_frames,
                top_k=top_k,
                fps=fps,
                frame_count=frame_count,
                video_seconds=frame_count / fps,
                source=dict(
                    track_id=track.track_id,
                    last_frame=last.frame,
                    last_x=last.center_x,
                    last_y=last.center_y,
                    last_seconds=last.frame / fps,
                    last_confidence=last.confidence,
                    observed_len=len(track.observed),
                    velocity_x=vx,
                    velocity_y=vy,
                ),
                candidates=candidates,
                cv_rank1=dict(track_id=candidates[0]["track_id"],
                              prediction_error=candidates[0]["prediction_error"],
                              gap_frames=candidates[0]["gap_frames"]),
            ))
    events.sort(key=lambda e: (e["source"]["last_frame"], e["source"]["track_id"]))
    stats = dict(
        total_ends=total_ends,
        ends_with_candidates=len(events),
        ends_without_candidates=total_ends - len(events),
        segment_count=len(by_segment),
        window_frames=window_frames,
        top_k=top_k,
    )
    return events, stats


def load_inputs(video: Path, tracklets: Path, segments: Path | None, frame_count: int, fps: float) -> tuple[dict, list[Segment]]:
    """Load canonical tracklets and LosslessCut segments for one video."""
    tracks = load_tracklets(Path(tracklets))
    csv_path = Path(segments) if segments else Path(str(video) + ".csv")
    parsed = parse_losslesscut_csv(csv_path, duration=frame_count / fps)
    return tracks, parsed
