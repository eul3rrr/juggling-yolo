from pathlib import Path
import subprocess

import yaml


def test_direct_tracking_help_uses_project_environment() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "scripts" / "track_video.py"
    completed = subprocess.run(
        [str(script), "--help"], cwd=script.parent, check=True,
        capture_output=True, text=True,
    )
    assert "Run generic YOLO tracking" in completed.stdout
    assert "--tracker-label" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def test_botsort_configs_only_differ_in_reid_flag() -> None:
    project_root = Path(__file__).resolve().parents[1]
    botsort = yaml.safe_load((project_root / "configs/botsort.yaml").read_text())
    reid = yaml.safe_load((project_root / "configs/botsort_reid.yaml").read_text())
    assert botsort["with_reid"] is False
    assert reid["with_reid"] is True
    assert botsort["model"] == reid["model"] == "auto"
    assert {key: value for key, value in botsort.items() if key != "with_reid"} == {
        key: value for key, value in reid.items() if key != "with_reid"
    }


def test_bytetrack_config_is_distinct_tracker() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((project_root / "configs/bytetrack.yaml").read_text())
    assert config["tracker_type"] == "bytetrack"
    assert "with_reid" not in config
