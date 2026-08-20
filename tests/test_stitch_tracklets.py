from pathlib import Path
import csv
import importlib.util
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "stitch_tracklets.py"


def load_script():
    spec = importlib.util.spec_from_file_location("stitch_tracklets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def point(module, frame, x, y):
    return module.TrackletPoint(frame, x, y)


def test_constant_velocity_candidates_are_ranked_per_source() -> None:
    module = load_script()
    tracklets = {
        1: [point(module, 0, 0, 0), point(module, 2, 4, 0)],
        2: [point(module, 4, 8, 0)],
        3: [point(module, 4, 7, 0)],
        4: [point(module, 20, 40, 0)],
    }

    candidates = module.stitch_tracklets(tracklets, max_gap_frames=2)

    assert [(candidate.candidate_tracklet, candidate.candidate_rank) for candidate in candidates] == [
        (2, 1),
        (3, 2),
    ]
    assert candidates[0].gap_frames == 1
    assert candidates[0].predicted_x == 8
    assert candidates[0].prediction_error == 0
    assert candidates[1].prediction_error == 1


def test_candidates_use_only_tracklets_starting_within_gap() -> None:
    module = load_script()
    tracklets = {
        1: [point(module, 5, 10, 10), point(module, 6, 12, 12)],
        2: [point(module, 8, 16, 16)],
        3: [point(module, 9, 18, 18)],
        4: [point(module, 7, 14, 14)],
    }

    candidates = module.stitch_tracklets(tracklets, max_gap_frames=1)

    assert [(candidate.source_tracklet, candidate.candidate_tracklet) for candidate in candidates] == [(1, 2), (1, 4)]
    assert module.stitch_tracklets(tracklets, max_gap_frames=0)[0].candidate_tracklet == 4


def test_interpolate_bridge_point_moves_linearly_through_gap() -> None:
    module = load_script()
    candidate = module.StitchCandidate(28, 29, 2, 20, 0, 30, 10, 1, 10, 15, 2, 0, 1)

    assert module.interpolate_bridge_point(candidate, 10) == (10, 0)
    assert module.interpolate_bridge_point(candidate, 12) == (18, 4)
    assert module.interpolate_bridge_point(candidate, 15) == (30, 10)
    assert module.interpolate_bridge_point(candidate, 20) == (30, 10)


def test_interpolate_bridge_point_handles_adjacent_endpoints() -> None:
    module = load_script()
    candidate = module.StitchCandidate(1, 2, 0, 8, 4, 8, 4, 0, 3, 4, 5, 0, 1)

    assert module.interpolate_bridge_point(candidate, 3) == (3, 4)
    assert module.interpolate_bridge_point(candidate, 4) == (8, 4)


def test_load_tracklets_requires_norfair_columns(tmp_path: Path) -> None:
    module = load_script()
    path = tmp_path / "tracklets.csv"
    path.write_text("frame,track_id,center_x,center_y\n0,1,2,3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="time_seconds, confidence"):
        module.load_tracklets(path)


def test_output_csv_has_required_fields_and_rank_order(tmp_path: Path) -> None:
    module = load_script()
    path = tmp_path / "stitches.csv"
    candidates = module.stitch_tracklets(
        {
            1: [point(module, 0, 0, 0), point(module, 1, 1, 0)],
            2: [point(module, 2, 2, 0)],
        }
    )
    module.write_candidates(path, candidates)

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        assert set(module.OUTPUT_FIELDS).issubset(reader.fieldnames or [])
        assert next(reader)["candidate_rank"] == "1"


def test_cli_rejects_negative_gap() -> None:
    completed = subprocess.run(
        [str(SCRIPT), "video.mp4", "tracklets.csv", "--max-gap-frames", "-1"],
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "nonnegative" in completed.stderr
