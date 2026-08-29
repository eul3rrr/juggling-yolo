"""Unit tests for ``scripts.hand_overlay`` (Hand System v1B reviewer helpers)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = PROJECT_ROOT / "scripts" / "hand_overlay.py"


def load_overlay():
    spec = importlib.util.spec_from_file_location("hand_overlay", OVERLAY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def test_format_hand_metric_handles_none_and_nan():
    ho = load_overlay()
    assert ho.format_hand_metric(None) == "—"
    assert ho.format_hand_metric(float("nan")) == "—"
    assert ho.format_hand_metric(float("inf")) == "—"


def test_format_hand_metric_signed_has_explicit_sign():
    ho = load_overlay()
    assert ho.format_hand_metric(13.3) == "+13.3"
    assert ho.format_hand_metric(-13.3) == "-13.3"
    assert ho.format_hand_metric(0.0) == "+0.0"


def test_format_hand_metric_unsigned_omits_plus():
    ho = load_overlay()
    assert ho.format_hand_metric(42.7, signed=False) == "42.7"


def test_format_hand_metric_decimals_respected():
    ho = load_overlay()
    assert ho.format_hand_metric(1.23456, decimals=2) == "+1.23"
    assert ho.format_hand_metric(-1.2, decimals=0) == "-1"


def test_trend_labels_match_sign_convention():
    ho = load_overlay()
    assert ho._trend_label(None) == "—"
    assert ho._trend_label(-5.0) == "CLOSING"
    assert ho._trend_label(+5.0) == "SEPARATING"
    assert ho._trend_label(0.1) == "STABLE"
    assert ho._trend_label(-0.1) == "STABLE"


# ---------------------------------------------------------------------------
# Hand-metric dataclass
# ---------------------------------------------------------------------------

def test_hand_metrics_as_dict_is_json_serialisable():
    ho = load_overlay()
    import json
    m = ho.HandMetrics(hand="left", distance_px=12.3,
                       distance_normalized=0.07,
                       distance_slope_px_per_frame=-3.4,
                       radial_relative_velocity=-3.1, n_points=5,
                       hand_confidence=0.92, trend_label="CLOSING")
    json.dumps(m.as_dict())


# ---------------------------------------------------------------------------
# Nearest hand and missing data
# ---------------------------------------------------------------------------

def test_nearest_hand_picks_closer_hand():
    ho = load_overlay()
    left = ho.HandMetrics(hand="left", distance_px=12.0, distance_normalized=None,
                          distance_slope_px_per_frame=None,
                          radial_relative_velocity=None, n_points=5,
                          hand_confidence=0.9, trend_label="—")
    right = ho.HandMetrics(hand="right", distance_px=200.0, distance_normalized=None,
                           distance_slope_px_per_frame=None,
                           radial_relative_velocity=None, n_points=5,
                           hand_confidence=0.9, trend_label="—")
    assert ho.nearest_hand({"left": left, "right": right}) == "left"


def test_nearest_hand_returns_none_when_both_missing():
    ho = load_overlay()
    left = ho.HandMetrics(hand="left", distance_px=None, distance_normalized=None,
                          distance_slope_px_per_frame=None,
                          radial_relative_velocity=None, n_points=0,
                          hand_confidence=None, trend_label="—")
    right = ho.HandMetrics(hand="right", distance_px=None, distance_normalized=None,
                           distance_slope_px_per_frame=None,
                           radial_relative_velocity=None, n_points=0,
                           hand_confidence=None, trend_label="—")
    assert ho.nearest_hand({"left": left, "right": right}) is None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def test_load_hands_by_frame_handles_missing_file(tmp_path: Path):
    ho = load_overlay()
    hands = ho.load_hands_by_frame(tmp_path / "nope.csv")
    assert hands == {}


def test_load_hands_by_frame_skips_low_confidence(tmp_path: Path):
    ho = load_overlay()
    p = tmp_path / "hands.csv"
    p.write_text(
        "frame,person_index,left_wrist_x,left_wrist_y,left_wrist_confidence,"
        "left_wrist_x_smooth,left_wrist_y_smooth,"
        "right_wrist_x,right_wrist_y,right_wrist_confidence,"
        "right_wrist_x_smooth,right_wrist_y_smooth,"
        "left_elbow_x,left_elbow_y,left_elbow_confidence,"
        "left_elbow_x_smooth,left_elbow_y_smooth,"
        "right_elbow_x,right_elbow_y,right_elbow_confidence,"
        "right_elbow_x_smooth,right_elbow_y_smooth,"
        "left_shoulder_x,left_shoulder_y,left_shoulder_confidence,"
        "left_shoulder_x_smooth,left_shoulder_y_smooth,"
        "right_shoulder_x,right_shoulder_y,right_shoulder_confidence,"
        "right_shoulder_x_smooth,right_shoulder_y_smooth,body_scale_shoulder_px\n"
        "0,0,100,200,0.9,100,200,300,400,0.9,300,400,110,210,0.9,110,210,"
        "310,410,0.9,310,410,90,190,0.9,90,190,290,390,0.9,290,390,150\n"
        "1,0,110,200,0.05,,,310,400,0.9,310,400,110,210,0.9,110,210,"
        "310,410,0.9,310,410,90,190,0.9,90,190,290,390,0.9,290,390,150\n"
    )
    hands = ho.load_hands_by_frame(p)
    assert 0 in hands and 1 in hands
    # frame 0: both wrists valid
    assert hands[0][0].left_wrist == (100.0, 200.0)
    assert hands[0][0].right_wrist == (300.0, 400.0)
    # frame 1: left wrist raw is low confidence; smoothed is empty too.
    # The reviewer should treat it as missing.
    assert hands[1][0].left_wrist is None
    assert hands[1][0].right_wrist == (310.0, 400.0)


# ---------------------------------------------------------------------------
# event_hand_features
# ---------------------------------------------------------------------------

def _make_event(primary_obs, candidates, kind="end"):
    """Tiny stand-in for a review_event that only exposes the attributes
    the overlay module reads."""
    import types
    primary = types.SimpleNamespace(
        all_sorted=[types.SimpleNamespace(frame=f, center_x=x, center_y=y,
                                         is_observed=True) for (f, x, y) in primary_obs],
    )
    cand_objs = []
    for idx, cand_obs in enumerate(candidates):
        cand_objs.append(types.SimpleNamespace(
            track_id=10 + idx,
            all_sorted=[types.SimpleNamespace(frame=f, center_x=x, center_y=y,
                                             is_observed=True) for (f, x, y) in cand_obs],
        ))
    ev = types.SimpleNamespace(
        primary=primary, nearby_starts=cand_objs, kind=kind,
    )
    return ev


def test_event_hand_features_returns_underdetermined_when_no_ball_points():
    ho = load_overlay()
    ev = _make_event([], [], kind="end")
    out = ho.event_hand_features(ev, hands={})
    assert out["source"]["nearest"] is None
    assert out["source"]["left"]["trend_label"] == "—"
    assert out["source"]["right"]["trend_label"] == "—"
    assert out["candidates"] == []


def test_event_hand_features_end_event_picks_correct_sides():
    ho = load_overlay()
    # Primary last 3 points at (200, 200) - (210, 200) - (220, 200):
    # approaching a hand at (300, 200). Right hand is far.
    primary_obs = [(0, 100, 200), (1, 200, 200), (2, 210, 200), (3, 220, 200)]
    # Candidate first 2 points at (400, 200) - (500, 200):
    # separating from a hand at (300, 200). Left hand is far.
    cand_obs = [(3, 400, 200), (4, 500, 200)]
    ev = _make_event(primary_obs, [cand_obs], kind="end")
    # Build a tiny hand map: left wrist at (50, 50), right wrist at (300, 200)
    # for frames 0..4.
    import types
    hands = {}
    for fr in range(0, 5):
        rows = []
        for side, xy in [("left", (50, 50)), ("right", (300, 200))]:
            x_key = f"{side}_wrist_x_smooth"
            y_key = f"{side}_wrist_y_smooth"
            conf_key = f"{side}_wrist_confidence"
            row_dict = {x_key: xy[0], y_key: xy[1], conf_key: 0.99}
            # Pad other required columns to empty so loader's _xy returns None.
            for k in ("left_wrist", "right_wrist", "left_elbow", "right_elbow",
                      "left_shoulder", "right_shoulder"):
                for suffix in ("_x", "_y", "_confidence",
                               "_x_smooth", "_y_smooth"):
                    row_dict.setdefault(f"{k}{suffix}", "")
            row_dict["frame"] = fr
            row_dict["person_index"] = 0
            row_dict["body_scale_shoulder_px"] = ""
            rows.append(row_dict)
        hands[fr] = [ho.PersonHandRow(
            frame=fr, person_index=0,
            left_wrist=(50.0, 50.0), left_wrist_conf=0.99,
            right_wrist=(300.0, 200.0), right_wrist_conf=0.99,
            left_elbow=None, left_elbow_conf=None,
            right_elbow=None, right_elbow_conf=None,
            left_shoulder=None, left_shoulder_conf=None,
            right_shoulder=None, right_shoulder_conf=None,
            body_scale=None,
        )]
    out = ho.event_hand_features(ev, hands=hands)
    # Source nearest hand: right (300, 200) is 80 px from (220, 200);
    # left is ~245 px away.
    assert out["source"]["nearest"] == "right"
    src_right = out["source"]["right"]
    # Closing as the ball moves from 100 -> 220 (toward 300).
    assert src_right["trend_label"] == "CLOSING"
    # Candidate nearest hand: right is far (300-400=100, 300-500=200).
    # left is 50, 450 — closer is left at frame 3 (50 px) but
    # frame 4 the ball is at (500, 200) and the left hand is at (50, 50)
    # so left=~450, right=~200. Nearest is right.
    assert out["candidates"][0]["nearest"] == "right"
    cand_right = out["candidates"][0]["right"]
    # Ball is moving 400 -> 500, hand at 300. Separating.
    assert cand_right["trend_label"] == "SEPARATING"


# ---------------------------------------------------------------------------
# End-to-end with hand_features: numbers must match
# ---------------------------------------------------------------------------

def test_event_hand_features_match_v1a_diagnostic_on_simple_track():
    """The reviewer and the v1A diagnostic must agree on the same numbers
    for the same hand CSV + same Track observations. This guards against
    accidental re-implementations of the math in hand_overlay."""
    ho = load_overlay()
    import hand_features
    primary_obs = [(0, 100.0, 200.0), (1, 200.0, 200.0), (2, 300.0, 200.0)]
    # Right hand stationary at (500, 200) for all 3 frames.
    hands = {}
    for fr in (0, 1, 2):
        hands[fr] = [ho.PersonHandRow(
            frame=fr, person_index=0,
            left_wrist=None, left_wrist_conf=None,
            right_wrist=(500.0, 200.0), right_wrist_conf=0.99,
            left_elbow=None, left_elbow_conf=None,
            right_elbow=None, right_elbow_conf=None,
            left_shoulder=None, left_shoulder_conf=None,
            right_shoulder=None, right_shoulder_conf=None,
            body_scale=None,
        )]
    ev = _make_event(primary_obs, [], kind="end")
    out = ho.event_hand_features(ev, hands=hands)
    right = out["source"]["right"]
    # Anchored to the LAST point (300, 200), hand at (500, 200) -> 200 px.
    assert right["distance_px"] == pytest.approx(200.0, abs=1e-6)
    # Ball is moving 100 -> 200 -> 300, hand is fixed at 500.
    # Distance: 400, 300, 200. Slope is -100 px/frame.
    assert right["distance_slope_px_per_frame"] == pytest.approx(-100.0, abs=1e-6)
    # Radial relative velocity: ball velocity (100, 0), hand (0, 0).
    # r = ball - hand = (-200, 0); r_hat = (-1, 0) (unit vector hand->ball).
    # dot((100,0), (-1,0)) = -100. Sign convention: negative = closing.
    assert right["radial_relative_velocity"] == pytest.approx(-100.0, abs=1e-6)
    # Same numbers from the v1A module directly:
    bf = __import__("numpy").asarray([0, 1, 2], dtype=int)
    bxy = __import__("numpy").asarray([[100.0, 200.0], [200.0, 200.0],
                                       [300.0, 200.0]])
    hxy = __import__("numpy").asarray([[500.0, 200.0]] * 3)
    feats = hand_features.event_features_for_hand(
        ball_frames=bf, ball_xy=bxy, hand_frames=bf, hand_xy=hxy,
        hand_confidences=__import__("numpy").array([0.99, 0.99, 0.99]),
        hand_name="right", body_scale_value=None, n_window=3, min_window_pts=2,
    )
    assert feats.distance_px == pytest.approx(right["distance_px"], abs=1e-6)
    assert feats.distance_slope_px_per_frame == pytest.approx(
        right["distance_slope_px_per_frame"], abs=1e-6)
    assert feats.radial_relative_velocity == pytest.approx(
        right["radial_relative_velocity"], abs=1e-6)
