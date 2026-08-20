from pathlib import Path
import csv
import importlib.util
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "analyze_stitch_features.py"


def load_script():
    spec = importlib.util.spec_from_file_location("analyze_stitch_features", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_trajectory_fit_error_is_low_for_matching_linear_quadratic_fragments() -> None:
    module = load_script()
    points = [(frame, 4 + 2 * frame, 3 + 1.5 * frame + 0.25 * frame * frame) for frame in range(12)]
    error = module.fit_trajectory_error(points[:6], points[6:], 5)
    assert error == pytest.approx(0.0, abs=1e-9)


def test_trajectory_fit_ignores_norfair_predictions_and_requires_observed_endpoints() -> None:
    module = load_script()
    source = [(0, 0.0, 0.0, 1), (1, 100.0, 100.0, 0), (2, 4.0, 6.0, 1)]
    candidate = [(3, 6.0, 9.0, 1), (4, 200.0, 200.0, 0), (5, 10.0, 15.0, 1)]
    assert module.fit_trajectory_error(source, candidate, 3) == pytest.approx(0.0, abs=1e-9)


def test_observed_velocity_uses_only_observed_points() -> None:
    module = load_script()
    points = [(0, 0.0, 0.0, 1), (1, 100.0, 100.0, 0), (3, 6.0, 9.0, 1)]
    assert module.observed_velocity(points) == pytest.approx((2.0, 3.0))


def test_ambiguity_features_compare_rank_one_with_best_alternative() -> None:
    module = load_script()
    candidates = [
        {"candidate_tracklet": "10", "candidate_rank": "1", "prediction_error": "20"},
        {"candidate_tracklet": "11", "candidate_rank": "2", "prediction_error": "35"},
        {"candidate_tracklet": "12", "candidate_rank": "3", "prediction_error": "80"},
    ]
    features = module.ambiguity_features(candidates, "10", {10: 4.0, 11: 9.0, 12: 20.0})
    assert features["alternative_candidate_count"] == 2
    assert features["best_alternative_candidate"] == 11
    assert features["prediction_margin"] == pytest.approx(15.0)
    assert features["trajectory_fit_margin"] == pytest.approx(5.0)
    assert features["prediction_ratio"] == pytest.approx(20 / 35)
    assert features["trajectory_fit_ratio"] == pytest.approx(4 / 9)


def test_hand_features_use_confident_wrists_and_report_unavailable_when_missing() -> None:
    module = load_script()
    candidate = {
        "source_end_frame": "2", "candidate_start_frame": "5", "gap_frames": "2",
        "predicted_x": "2", "predicted_y": "2", "end_velocity_x": "0", "end_velocity_y": "0",
        "candidate_start_x": "5", "candidate_start_y": "5",
    }
    pose = {
        2: [{"left_x": 2.0, "left_y": 2.0, "left_conf": 0.9, "right_x": None, "right_y": None, "right_conf": None}],
        3: [{"left_x": 3.0, "left_y": 3.0, "left_conf": 0.05, "right_x": None, "right_y": None, "right_conf": None}],
        4: [{"left_x": 4.0, "left_y": 4.0, "left_conf": 0.9, "right_x": None, "right_y": None, "right_conf": None}],
        5: [{"left_x": 5.0, "left_y": 5.0, "left_conf": 0.9, "right_x": None, "right_y": None, "right_conf": None}],
    }
    features = module.hand_features(candidate, (2.0, 2.0), pose, 0.3)
    assert features["nearest_hand"] == "left"
    assert float(features["nearest_hand_distance"]) == pytest.approx(0.0)
    assert float(features["source_end_hand_distance"]) == pytest.approx(0.0)
    assert float(features["candidate_start_hand_distance"]) == pytest.approx(0.0)

    missing = module.hand_features(candidate, (2.0, 2.0), {}, 0.3)
    assert missing["nearest_hand"] == "unavailable"
    assert missing["nearest_hand_distance"] == ""


def test_pose_overlay_default_is_under_ignored_outputs_directory() -> None:
    module = load_script()
    path = module.pose_overlay_default(
        module.PROJECT_ROOT / "videos" / "example.mp4", module.PROJECT_ROOT / "outputs"
    )
    assert path == module.PROJECT_ROOT / "outputs" / "pose_overlay" / "example_yolo26s-pose_overlay.mp4"
