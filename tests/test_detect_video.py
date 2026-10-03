from pathlib import Path
import subprocess


def test_direct_execution_uses_project_environment() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "scripts" / "detect_video.py"

    completed = subprocess.run(
        [str(script), "--help"],
        cwd=script.parent,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Run YOLO detection" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr
