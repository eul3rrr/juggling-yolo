from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tracking.ballistics import (
    AccelProfile, constant_profile, estimate_accel_y, fit_flight, flight_samples, reference_accel,
)

G = 2.0


def arc(start_frame, frames, x0=100.0, y0=500.0, vx=3.0, vy=-40.0, accel=G):
    return [(start_frame + t, x0 + vx * t, y0 + vy * t + 0.5 * accel * t * t) for t in range(frames)]


def test_fit_flight_recovers_the_arc_and_predicts_far_ahead():
    points = arc(10, 8)
    fit = fit_flight(points, G)
    assert fit.rmse < 1e-6
    truth = arc(10, 41)[-1]
    x, y = fit.predict(truth[0])
    assert math.hypot(x - truth[1], y - truth[2]) < 1e-6


def test_constant_velocity_misses_what_the_arc_predicts():
    points = arc(0, 10)
    truth = arc(0, 41)[-1]
    (f0, x0, y0), (f1, x1, y1) = points[-2:]
    elapsed = truth[0] - f1
    straight = (x1 + (x1 - x0) * elapsed, y1 + (y1 - y0) * elapsed)
    assert math.hypot(straight[0] - truth[1], straight[1] - truth[2]) > 500
    assert math.hypot(*(a - b for a, b in zip(fit_flight(points, G).predict(truth[0]), truth[1:]))) < 1e-6


def test_one_or_two_points_fall_back_to_a_straight_line():
    assert fit_flight([(5, 1.0, 2.0)], 0.0).predict(9) == (1.0, 2.0)
    x, y = fit_flight([(5, 0.0, 0.0), (6, 2.0, 1.0)], 0.0).predict(8)
    assert abs(x - 6.0) < 1e-9 and abs(y - 3.0) < 1e-9


def test_estimate_accel_ignores_carried_balls():
    flights = [arc(100 * i, 30) for i in range(4)]
    carried = [[(1000 + t, 300.0 + 0.5 * t, 400.0) for t in range(200)]]
    assert abs(estimate_accel_y(flights + carried) - G) < 1e-6


def test_reference_accel_prefers_real_time_over_a_larger_slow_motion_cluster():
    values = [0.125] * 200 + [2.0] * 40
    assert reference_accel(values) == 2.0


def test_profile_follows_slow_motion_inside_one_segment():
    real = [arc(0, 30)]
    slow = [arc(200 + 150 * i, 120, vy=-7.5, vx=0.75, accel=G / 16) for i in range(3)]
    samples = flight_samples(real + slow)
    profile = AccelProfile(samples, reference_accel([a for _, a in samples]), radius_frames=30)
    assert abs(profile.reference - G) < 1e-6
    assert abs(profile.at(15) - G) < 1e-6
    assert abs(profile.at(260) - G / 16) < 1e-6
    assert abs(profile.speed(260) - 0.25) < 1e-6
    assert profile.window(260) > profile.window(15)


def test_constant_profile_has_one_speed():
    profile = constant_profile(G)
    assert profile.at(0) == profile.at(10_000) == G
    assert profile.speed(123) == 1.0
    assert profile.window(0) == 7
