from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.review_track_events import Track, TrackObservation  # noqa: E402
from src.annotation.segments import Segment  # noqa: E402
from src.vision_stitch.candidates import (build_events, track_velocity,  # noqa: E402
                                          assign_segment)

FPS = 60.0


def make_track(track_id: int, points: list[tuple[int, float, float]]) -> Track:
    return Track(track_id=track_id, observations=[
        TrackObservation(frame=frame, center_x=x, center_y=y, confidence=0.9, observed=1)
        for frame, x, y in points])


def segments(*spans: tuple[float, float]) -> list[Segment]:
    return [Segment(index=i, start=start, end=end) for i, (start, end) in enumerate(spans)]


def test_velocity_uses_the_last_two_observed_points():
    track = make_track(1, [(0, 100.0, 100.0), (2, 110.0, 90.0), (4, 120.0, 80.0)])
    vx, vy = track_velocity(track)
    assert vx == pytest.approx(5.0)
    assert vy == pytest.approx(-5.0)


def test_velocity_is_zero_with_a_single_point():
    assert track_velocity(make_track(1, [(0, 10.0, 10.0)])) == (0.0, 0.0)


def test_assign_segment_uses_the_first_observed_frame():
    track = make_track(1, [(120, 10.0, 10.0), (130, 20.0, 20.0)])
    assert assign_segment(track, FPS, segments((0.0, 5.0))) == 0
    assert assign_segment(make_track(2, [(600, 1.0, 1.0)]), FPS, segments((0.0, 5.0))) is None


def test_window_gap_and_ordering():
    source = make_track(1, [(100, 100.0, 100.0), (102, 104.0, 100.0)])
    inside = make_track(2, [(110, 120.0, 100.0)])
    too_far = make_track(3, [(200, 120.0, 100.0)])
    events, stats = build_events({1: source, 2: inside, 3: too_far}, segments((0.0, 10.0)),
                                 FPS, 600, window_frames=30, top_k=3)
    assert len(events) == 1
    event = events[0]
    assert event["event_key"] == "end:1:102"
    assert [c["track_id"] for c in event["candidates"]] == [2]
    assert event["candidates"][0]["gap_frames"] == 8
    assert stats["total_ends"] == 3
    assert stats["ends_with_candidates"] == 1


def test_candidates_never_cross_a_segment_boundary():
    # segment 0 ends at 2.0 s (frame 120); the source ends at frame 115.
    source = make_track(1, [(100, 100.0, 100.0), (115, 130.0, 100.0)])
    after_cut = make_track(2, [(125, 131.0, 100.0)])   # inside segment 1 only
    events, _ = build_events({1: source, 2: after_cut}, segments((0.0, 2.0), (2.0, 6.0)),
                             FPS, 600, window_frames=60, top_k=3)
    assert events == []


def test_ranking_and_top_k_truncation():
    source = make_track(1, [(100, 100.0, 100.0), (102, 110.0, 100.0)])   # +5 px/frame
    # gap is 8 frames, so the constant-velocity prediction at frame 110 is x=150
    near = make_track(2, [(110, 150.0, 100.0)])    # error 0
    mid = make_track(3, [(110, 170.0, 100.0)])     # error 20
    far = make_track(4, [(110, 210.0, 100.0)])     # error 60
    events, _ = build_events({1: source, 2: near, 3: mid, 4: far}, segments((0.0, 10.0)),
                             FPS, 600, window_frames=30, top_k=2)
    candidates = events[0]["candidates"]
    assert [c["track_id"] for c in candidates] == [2, 3]
    assert [c["rank"] for c in candidates] == [1, 2]
    assert candidates[0]["prediction_error"] == pytest.approx(0.0)
    assert events[0]["cv_rank1"]["track_id"] == 2


def test_ties_are_broken_deterministically_by_track_id():
    source = make_track(1, [(100, 100.0, 100.0), (102, 100.0, 100.0)])
    a = make_track(7, [(110, 100.0, 100.0)])
    b = make_track(3, [(110, 100.0, 100.0)])
    events, _ = build_events({1: source, 7: a, 3: b}, segments((0.0, 10.0)), FPS, 600, 30, 3)
    assert [c["track_id"] for c in events[0]["candidates"]] == [3, 7]


def test_tracklets_without_observed_rows_are_ignored():
    empty = Track(track_id=9, observations=[TrackObservation(frame=5, center_x=1.0, center_y=1.0,
                                                             confidence=0.1, observed=0)])
    source = make_track(1, [(100, 10.0, 10.0), (101, 11.0, 10.0)])
    events, stats = build_events({1: source, 9: empty}, segments((0.0, 10.0)), FPS, 600, 30, 3)
    assert stats["total_ends"] == 1
    assert events == []


def test_invalid_parameters_raise():
    source = make_track(1, [(10, 1.0, 1.0), (11, 1.0, 1.0)])
    with pytest.raises(ValueError):
        build_events({1: source}, segments((0.0, 10.0)), FPS, 600, window_frames=0)
    with pytest.raises(ValueError):
        build_events({1: source}, segments((0.0, 10.0)), FPS, 600, top_k=0)
