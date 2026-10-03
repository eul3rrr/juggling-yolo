from pathlib import Path
import math
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tracking.assignment import solve_paths
from src.tracking.ball_count import estimate_ball_count, resolve_ball_counts
from src.tracking.ballistics import constant_profile
from src.tracking.links import (
    SegmentContext, build_links, describe_tracklet, is_clutter, px_per_metre,
)
from src.tracking.pipeline import track_video
from src.tracking.states import AIRBORNE, HELD, HIDDEN, classify_points
from src.tracking.tracklets import SegmentSpan, Tracklet, load_observed_tracklets

G = 2.0
FPS = 60.0
LEFT, RIGHT = (300.0, 500.0), (500.0, 500.0)
FAR = (5000.0, 5000.0)


def flight(start_frame, p0, p1, frames):
    """Free flight from p0 to p1 taking ``frames`` frames (end point included)."""
    vx = (p1[0] - p0[0]) / frames
    vy = (p1[1] - p0[1]) / frames - 0.5 * G * frames
    return [(start_frame + t, p0[0] + vx * t, p0[1] + vy * t + 0.5 * G * t * t)
            for t in range(frames + 1)]


def carry(start_frame, p0, p1, frames):
    return [(start_frame + t, p0[0] + (p1[0] - p0[0]) * t / frames,
             p0[1] + (p1[1] - p0[1]) * t / frames) for t in range(frames + 1)]


def tracklet(track_id, *pieces):
    points = sorted({p[0]: p for piece in pieces for p in piece}.values())
    return Tracklet(track_id, tuple(points))


def hands(span, left=LEFT, right=RIGHT, scale=200.0):
    return {f: {"left": left, "right": right, "body_scale": scale,
                "left_confidence": 1.0, "right_confidence": 1.0}
            for f in range(span.start, span.end)}


def context(span, hands_by_frame):
    return SegmentContext(span, FPS, constant_profile(G), px_per_metre(G, FPS), hands_by_frame, 200.0)


def solve(tracklets, span, hands_by_frame, n_balls):
    ctx = context(span, hands_by_frame)
    infos = [describe_tracklet(t, ctx) for t in tracklets]
    return solve_paths(infos, build_links(infos, ctx), n_balls, ctx), infos


def test_points_are_airborne_in_flight_and_held_while_carried():
    span = SegmentSpan(0, 0, 90)
    t = tracklet(1, flight(0, (500, 480), (300, 480), 30),
                 carry(30, (300, 480), (320, 520), 20),
                 flight(50, (320, 520), (500, 480), 30))
    states = classify_points(t, hands(span), constant_profile(G), 200.0)
    by_frame = {p[0]: s for p, s in zip(t.points, states)}
    assert by_frame[15].state == AIRBORNE and by_frame[65].state == AIRBORNE
    assert by_frame[40].state == HELD and by_frame[40].hand == "LEFT"


def test_flight_link_bridges_a_gap_constant_velocity_cannot():
    span = SegmentSpan(0, 0, 51)
    arc = flight(0, (300, 480), (500, 480), 50)
    a, b = tracklet(1, arc[:10]), tracklet(2, arc[40:])
    (fa, xa, ya), (fb, xb, yb) = a.points[-2:]
    elapsed = b.first_frame - fb
    straight_error = math.hypot(xb + (xb - xa) * elapsed - b.points[0][1],
                                yb + (yb - ya) * elapsed - b.points[0][2])
    assert straight_error > 500

    solution, _ = solve([a, b], span, hands(span, FAR, FAR), 1)
    assert solution.paths == ((1, 2),)
    link = solution.links[0][0]
    assert link.kind == "flight" and link.gap_frames == 30 and link.fit_rmse_px < 1e-6


def test_flight_arc_beats_the_straight_line_successor():
    span = SegmentSpan(0, 0, 60)
    arc = flight(0, (300, 480), (500, 480), 50)
    source = tracklet(1, arc[:10])
    true_next = tracklet(2, arc[20:31])
    (f0, x0, y0), (f1, x1, y1) = source.points[-2:]
    decoy_start = (x1 + (x1 - x0) * (20 - f1), y1 + (y1 - y0) * (20 - f1))
    decoy = tracklet(3, flight(20, decoy_start, (decoy_start[0] + 40, decoy_start[1]), 10))

    ctx = context(span, hands(span, FAR, FAR))
    infos = [describe_tracklet(t, ctx) for t in (source, true_next, decoy)]
    links = {(l.source, l.target): l for l in build_links(infos, ctx)}
    assert links[(1, 2)].kind == "flight" and links[(1, 2)].fit_rmse_px < 1e-6
    assert links[(1, 2)].cost < links[(1, 3)].cost
    solution = solve_paths(infos, list(links.values()), 2, ctx)
    assert (1, 2) in solution.paths


def test_two_sources_cannot_both_take_one_target():
    span = SegmentSpan(0, 0, 120)
    h = hands(span)
    first = tracklet(1, flight(0, (500, 480), (300, 480), 30), carry(30, (300, 480), (310, 500), 8))
    second = tracklet(2, flight(4, (500, 470), (300, 490), 30), carry(34, (300, 490), (310, 510), 8))
    target = tracklet(3, carry(60, (310, 500), (300, 480), 6), flight(66, (300, 480), (500, 480), 53))
    solution, _ = solve([first, second, target], span, h, 2)
    assert len(solution.paths) == 2
    assert sum(3 in path for path in solution.paths) == 1
    assert sorted(len(path) for path in solution.paths) == [1, 2]


def test_segments_are_solved_separately():
    spans = [SegmentSpan(0, 0, 51), SegmentSpan(1, 51, 102)]
    arc = flight(0, (300, 480), (500, 480), 50)
    later = [(f + 51, x, y) for f, x, y in arc]
    tracklets = {1: tracklet(1, arc[:30]), 2: tracklet(2, later[5:])}
    h = {**hands(spans[0], FAR, FAR), **hands(spans[1], FAR, FAR)}
    results = track_video(tracklets, spans, FPS, h, balls=1)
    assert [r.solution.paths for r in results] == [((1,),), ((2,),)]
    assert all(not links for r in results for links in r.solution.links)


def test_ball_count_is_a_ceiling_and_a_stray_detection_is_dropped():
    span = SegmentSpan(0, 0, 61)
    h = hands(span, FAR, FAR)
    balls = [tracklet(i + 1, flight(0, (100 + 200 * i, 480), (200 + 200 * i, 480), 60)) for i in range(3)]
    stray = tracklet(9, [(30 + t, 900.0 + t, 100.0) for t in range(4)])
    solution, _ = solve([*balls, stray], span, h, 4)
    assert solution.paths == ((1,), (2,), (3,))
    assert solution.unused == (9,)


def test_catch_out_of_sight_is_joined_by_a_hidden_link():
    span = SegmentSpan(0, 0, 131)
    h = hands(span)
    resting = tracklet(1, carry(0, (500, 480), (500.5, 480.5), 130))
    # thrown up and back, lost in mid-air far from either wrist
    lost = tracklet(2, flight(0, (300, 480), (400, 100), 30))
    # a ball later leaves the left hand: the only ball unaccounted for
    back = tracklet(3, carry(70, (310, 500), (300, 480), 6), flight(76, (300, 480), (500, 480), 54))
    result = track_video({t.track_id: t for t in (resting, lost, back)}, [span], FPS, h, balls=2)[0]
    assert sorted(result.solution.paths) == [(1,), (2, 3)]
    link = [links for links in result.solution.links if links][0][0]
    assert link.kind == "hidden"
    ball = next(i for i, path in enumerate(result.solution.paths, start=1) if path == (2, 3))
    gap = [row for row in result.timeline if row.ball_id == ball and 31 <= row.frame <= 69]
    assert len(gap) == 39 and {row.state for row in gap} == {HIDDEN}
    assert all(row.x is None for row in gap)


def test_hand_link_reports_the_ball_as_held_at_the_wrist():
    span = SegmentSpan(0, 0, 111)
    h = hands(span)
    caught = tracklet(1, flight(0, (500, 480), (300, 480), 30), carry(30, (300, 480), (310, 500), 8))
    thrown = tracklet(2, carry(50, (310, 500), (300, 480), 6), flight(56, (300, 480), (500, 480), 54))
    result = track_video({1: caught, 2: thrown}, [span], FPS, h, balls=1)[0]
    assert result.solution.paths == ((1, 2),)
    assert result.solution.links[0][0].kind == "hand" and result.solution.links[0][0].hand == "LEFT"
    gap = [row for row in result.timeline if 39 <= row.frame <= 49]
    assert {(row.state, row.hand, row.position_source) for row in gap} == {(HELD, "LEFT", "wrist")}
    assert all((row.x, row.y) == LEFT for row in gap)
    assert len(result.timeline) == span.end - span.start


def test_clutter_is_still_and_never_near_a_hand():
    span = SegmentSpan(0, 0, 60)
    h = hands(span)
    ctx = context(span, h)
    background = Tracklet(1, tuple((f, 900.0, 100.0) for f in range(40)))
    resting = Tracklet(2, tuple((f, 510.0, 490.0) for f in range(40)))
    assert is_clutter(background, ctx)
    assert not is_clutter(resting, ctx)
    assert not is_clutter(background, context(span, {}))


def test_ball_count_needs_a_sustained_overlap():
    span = SegmentSpan(0, 0, 200)
    long = [Tracklet(i, tuple((f, 0.0, 0.0) for f in range(200))) for i in (1, 2, 3)]
    blip = Tracklet(4, tuple((f, 0.0, 0.0) for f in range(50, 53)))
    assert estimate_ball_count(long, span, FPS) == 3
    assert estimate_ball_count([*long, blip], span, FPS) == 3


def test_ball_count_resolution_floors_at_the_video_mode_and_honours_overrides():
    estimates = {0: 3, 1: 3, 2: 2, 3: 5}
    assert resolve_ball_counts(estimates) == {
        0: (3, "estimated"), 1: (3, "estimated"), 2: (3, "video_mode"), 3: (5, "estimated")}
    assert resolve_ball_counts(estimates, override=4)[2] == (4, "override")
    assert resolve_ball_counts(estimates, per_segment={2: 2})[2] == (2, "override")


TRACKLETS = ROOT / "detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv"
HANDS = ROOT / "detections/identical_balls_trick_000_018_yolo26s-pose-hands.csv"


@pytest.mark.skipif(not (TRACKLETS.is_file() and HANDS.is_file()), reason="reference clip data not present")
def test_reference_clip_matches_the_human_labelled_handovers():
    sys.path.insert(0, str(ROOT / "scripts"))
    import hand_association as ha

    result = track_video(load_observed_tracklets(TRACKLETS), [SegmentSpan(0, 0, 1079)], 59.94,
                         ha._load_hands_by_frame(HANDS))[0]
    assert (result.n_balls, result.n_balls_source) == (3, "estimated")
    assert set(result.clutter) == {7, 8}
    ball_of = {tid: i for i, path in enumerate(result.solution.paths) for tid in path}
    # six of the seven human-labelled links; 10 -> 14 targets a 2-frame tracklet
    # at the very end of the clip, which is left unassigned
    for source, target in ((3, 4), (4, 6), (1, 5), (5, 10), (2, 11), (6, 13)):
        assert ball_of[source] == ball_of[target]
    assert len(result.solution.paths) == 3
    assert set(result.solution.unused) == {9, 12, 14}
    # the clip drops to slow motion in the middle; gravity must follow it
    slow = result.infos[5]
    assert slow.tracklet.first_frame == 223
    assert sum(s.state == AIRBORNE for s in slow.states) > 300
