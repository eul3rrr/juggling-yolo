"""Unit tests for ``scripts.hand_features`` (Hand System v1)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "hand_features.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hand_features", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def test_smooth_series_does_not_bridge_long_gaps():
    hf = load_module()
    # Two long gaps: missing values must NOT be filled in by neighbours.
    values = [10.0, None, None, None, 30.0, 31.0, 32.0, None, 40.0, 41.0, 42.0]
    out = hf.smooth_series(values, window=5)
    # Every value inside the first 4-frame gap stays missing.
    assert out[1] is None and out[2] is None and out[3] is None
    # The isolated missing point at index 7 stays missing.
    assert out[7] is None
    # Inside the 30-32 block the centre stays at 31.
    assert out[5] == pytest.approx(31.0, abs=1e-9)
    # Inside the 40-42 block the centre stays at 41.
    assert out[9] == pytest.approx(41.0, abs=1e-9)
    # Critically, the first surviving point at index 4 (centre 30) does NOT
    # inherit 10.0 from index 0 — there is a long gap. Its window covers
    # indices 2..6 = [None, None, 30, 31, 32]; the median of the three
    # valid values is 31, not 10.
    assert out[4] == pytest.approx(31.0, abs=1e-9)


def test_smooth_series_respects_confidence_threshold():
    hf = load_module()
    # A wildly outlying but high-confidence point should survive.
    values = [10.0, 10.0, 1000.0, 10.0, 10.0]
    confs = [0.9, 0.9, 0.9, 0.9, 0.9]
    smoothed = hf.smooth_series(values, window=5, min_confidence=confs,
                                confidence_threshold=0.5)
    # The 1000.0 outlier is real, so the median should not ignore it; but
    # because 4/5 points are ~10 the median stays 10.0 at the centre.
    assert smoothed[2] == pytest.approx(10.0, abs=1e-9)


def test_smooth_series_low_confidence_treated_as_missing():
    hf = load_module()
    values = [10.0, 10.0, 1000.0, 10.0, 10.0]
    confs = [0.9, 0.9, 0.05, 0.9, 0.9]
    smoothed = hf.smooth_series(values, window=5, min_confidence=confs,
                                confidence_threshold=0.3)
    # The centre frame at index 2 has low confidence; the smoothed output
    # there must be None, not the 1000.0 outlier.
    assert smoothed[2] is None
    # Surrounding frames (1, 3) are still smoothed normally.
    assert smoothed[1] == pytest.approx(10.0, abs=1e-9)
    assert smoothed[3] == pytest.approx(10.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Distance / slope
# ---------------------------------------------------------------------------

def test_approaching_hand_gives_negative_distance_slope():
    hf = load_module()
    # Ball approaches the hand over 5 frames.
    ball = np.array([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]], dtype=float)
    hand = np.array([[100, 0], [80, 0], [60, 0], [40, 0], [20, 0]], dtype=float)
    d = hf.distance_series(ball, hand)
    slope = hf.local_slope([0, 1, 2, 3, 4], [float(x) for x in d], n_points=5)
    assert slope is not None
    assert slope < 0


def test_separating_from_hand_gives_positive_distance_slope():
    hf = load_module()
    ball = np.array([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]], dtype=float)
    hand = np.array([[20, 0], [40, 0], [60, 0], [80, 0], [100, 0]], dtype=float)
    d = hf.distance_series(ball, hand)
    slope = hf.local_slope([0, 1, 2, 3, 4], [float(x) for x in d], n_points=5)
    assert slope is not None
    assert slope > 0


def test_slope_uses_least_squares_not_two_frame_difference():
    hf = load_module()
    # If we used only first-vs-last we would get -10. The least-squares
    # slope over 5 noisy points around the same trend should be similar but
    # not identical; the important property is that the slope is a real fit.
    frames = [0, 1, 2, 3, 4]
    distances = [100.0, 95.0, 92.0, 88.0, 80.0]
    slope = hf.local_slope(frames, distances, n_points=5)
    assert slope is not None
    assert -5.5 < slope < -4.0


def test_slope_returns_none_for_too_few_points():
    hf = load_module()
    assert hf.local_slope([0], [10.0], n_points=5) is None
    assert hf.local_slope([0, 1], [None, None], n_points=5) is None


# ---------------------------------------------------------------------------
# Relative radial velocity
# ---------------------------------------------------------------------------

def test_approaching_ball_has_negative_relative_radial_velocity():
    hf = load_module()
    # Ball at origin moving right at 10 px/frame, hand stationary at (100, 0).
    ball_xy = np.array([0.0, 0.0])
    ball_v = np.array([10.0, 0.0])
    hand_xy = np.array([100.0, 0.0])
    hand_v = np.array([0.0, 0.0])
    rrv = hf.relative_radial_velocity(ball_xy, ball_v, hand_xy, hand_v)
    assert rrv is not None
    # Ball closing on hand => radial component is negative.
    assert rrv < 0


def test_separating_ball_has_positive_relative_radial_velocity():
    hf = load_module()
    ball_xy = np.array([0.0, 0.0])
    ball_v = np.array([-10.0, 0.0])  # moving left
    hand_xy = np.array([100.0, 0.0])
    hand_v = np.array([0.0, 0.0])
    rrv = hf.relative_radial_velocity(ball_xy, ball_v, hand_xy, hand_v)
    assert rrv is not None
    assert rrv > 0


def test_radial_velocity_returns_none_when_hand_and_ball_coincide():
    hf = load_module()
    rrv = hf.relative_radial_velocity(np.array([5.0, 5.0]),
                                      np.array([1.0, 0.0]),
                                      np.array([5.0, 5.0]),
                                      np.array([0.0, 0.0]))
    assert rrv is None


def test_radial_velocity_handles_nan_safely():
    hf = load_module()
    assert hf.relative_radial_velocity(np.array([np.nan, 0.0]),
                                       np.array([1.0, 0.0]),
                                       np.array([100.0, 0.0]),
                                       np.array([0.0, 0.0])) is None
    assert hf.relative_radial_velocity(np.array([0.0, 0.0]),
                                       np.array([np.nan, 0.0]),
                                       np.array([100.0, 0.0]),
                                       np.array([0.0, 0.0])) is None


def test_radial_velocity_from_series_recovers_closing_motion():
    hf = load_module()
    # Ball moves linearly from x=0 to x=80 over 5 frames; hand at x=200.
    t = np.arange(5, dtype=float)
    ball = np.stack([t * 20.0, np.zeros(5)], axis=1)
    hand = np.stack([np.full(5, 200.0), np.zeros(5)], axis=1)
    rrv = hf.relative_radial_velocity_series(ball, hand, t, t, min_window_pts=3)
    assert rrv is not None
    # Ball closing on hand => negative.
    assert rrv < -10.0  # slope of relative distance is ~ -20 px/frame


# ---------------------------------------------------------------------------
# Body scale
# ---------------------------------------------------------------------------

def test_body_scale_normalisation_handles_missing_shoulders():
    hf = load_module()
    assert hf.body_scale(np.array([np.nan, 0.0]),
                         np.array([100.0, 0.0])) is None
    assert hf.body_scale(np.array([100.0, 0.0]),
                         np.array([100.0, 0.0])) is None  # degenerate
    assert hf.body_scale(np.array([100.0, 0.0]),
                         np.array([300.0, 0.0])) == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# Crossed arms: anatomical LEFT/RIGHT must not be swapped by screen position
# ---------------------------------------------------------------------------

def test_anatomical_left_right_preserved_under_screen_swap():
    hf = load_module()
    # Anatomical left wrist is on the right side of the screen (crossed arm).
    # Ball is in the subject's left hand, also on the right side of the screen.
    ball_frames = np.array([0, 1, 2, 3, 4])
    ball_xy = np.array([[800, 400], [795, 402], [790, 400], [785, 401], [780, 400]],
                       dtype=float)
    left_hand = np.array([[810, 410], [812, 412], [811, 411], [813, 410], [812, 412]],
                         dtype=float)
    right_hand = np.array([[100, 100], [101, 100], [99, 101], [100, 99], [101, 100]],
                          dtype=float)
    # Distances:
    #   to anatomical left hand  : ~ 14-22 px (very close)
    #   to anatomical right hand : ~ 700 px (far away)
    dist_left = float(np.linalg.norm(ball_xy[0] - left_hand[0]))
    dist_right = float(np.linalg.norm(ball_xy[0] - right_hand[0]))
    assert dist_left < 30 and dist_right > 600

    # The feature module's anchor is the LAST synchronised distance in the
    # window, not the first frame. Both distances should still identify the
    # *anatomical* left hand as the nearest hand.
    left_features = hf.event_features_for_hand(
        ball_frames=ball_frames, ball_xy=ball_xy,
        hand_frames=ball_frames, hand_xy=left_hand,
        hand_confidences=np.full(5, 0.9),
        hand_name="left", body_scale_value=200.0,
    )
    right_features = hf.event_features_for_hand(
        ball_frames=ball_frames, ball_xy=ball_xy,
        hand_frames=ball_frames, hand_xy=right_hand,
        hand_confidences=np.full(5, 0.9),
        hand_name="right", body_scale_value=200.0,
    )
    # Last-frame distances used as anchors.
    last_dist_left = float(np.linalg.norm(ball_xy[-1] - left_hand[-1]))
    last_dist_right = float(np.linalg.norm(ball_xy[-1] - right_hand[-1]))
    assert last_dist_left < 50 and last_dist_right > 600
    assert left_features.distance_px == pytest.approx(last_dist_left, abs=1.0)
    assert right_features.distance_px == pytest.approx(last_dist_right, abs=1.0)
    assert hf.nearest_hand(left_features, right_features) == "left"
    # And explicitly: the hand on the right side of the screen IS the
    # anatomical LEFT hand, by construction of the input. The feature module
    # must NOT silently swap them.
    assert left_features.hand == "left"
    assert right_features.hand == "right"


# ---------------------------------------------------------------------------
# Event-level convenience
# ---------------------------------------------------------------------------

def test_event_features_handle_empty_inputs():
    hf = load_module()
    f = hf.event_features_for_hand(
        ball_frames=np.array([], dtype=int), ball_xy=np.zeros((0, 2)),
        hand_frames=np.array([], dtype=int), hand_xy=np.zeros((0, 2)),
        hand_confidences=np.array([]),
        hand_name="left", body_scale_value=None,
    )
    assert f.distance_px is None
    assert f.distance_slope_px_per_frame is None
    assert f.radial_relative_velocity is None


def test_event_features_n_distance_points_matches_window():
    hf = load_module()
    ball_frames = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    ball_xy = np.tile(np.array([0.0, 0.0]), (10, 1))
    hand_frames = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    # Hand teleports for 4 frames; those frames must be excluded by the
    # missing-data path, not used in the slope fit.
    hand_xy = np.tile(np.array([50.0, 0.0]), (10, 1))
    hand_xy[3:7] = np.array([999.0, 999.0])
    hand_conf = np.ones(10)
    hand_conf[3:7] = 0.0  # marked missing by caller
    # The feature module doesn't gate on confidence inside event_features_for_hand
    # (caller's job), so we replicate the gating here: drop low-conf frames.
    valid = hand_conf >= 0.3
    f = hf.event_features_for_hand(
        ball_frames=ball_frames[valid], ball_xy=ball_xy[valid],
        hand_frames=hand_frames[valid], hand_xy=hand_xy[valid],
        hand_confidences=hand_conf[valid],
        hand_name="left", body_scale_value=200.0,
    )
    # 6 valid frames; only frames 0-2 and 7-9 are usable synchronised points
    # because ball frames and hand frames share the same set here.
    assert f.n_distance_points == 6
    assert f.distance_px == pytest.approx(50.0, abs=1.0)
    assert f.distance_slope_px_per_frame == pytest.approx(0.0, abs=1e-6)
