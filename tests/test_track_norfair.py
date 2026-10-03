from pathlib import Path
import csv
import importlib.util
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "track_norfair.py"


def load_script():
    spec = importlib.util.spec_from_file_location("track_norfair", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_direct_execution_help_uses_project_environment() -> None:
    completed = subprocess.run(
        [str(SCRIPT), "--help"], cwd=SCRIPT.parent, check=True, capture_output=True, text=True
    )
    assert "Track existing YOLO center-point detections" in completed.stdout
    assert "--distance-threshold" in completed.stdout
    assert "--hit-counter-max" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr


def test_detection_rows_group_and_convert_to_one_point() -> None:
    module = load_script()
    rows = [
        module.DetectionRow(2, 0.75, 10.5, 20.25),
        module.DetectionRow(2, 0.25, 30.0, 40.0),
    ]
    converted = module.to_norfair_detections(rows)
    assert [d.points.tolist() for d in converted] == [[[10.5, 20.25]], [[30.0, 40.0]]]
    assert [d.scores.tolist() for d in converted] == [[0.75], [0.25]]


def test_output_csv_contract(tmp_path: Path) -> None:
    module = load_script()
    input_csv = tmp_path / "detections.csv"
    input_csv.write_text(
        "frame,confidence,center_x,center_y\n"
        "0,0.8,12,13\n"
        "2,0.4,20,21\n",
        encoding="utf-8",
    )
    grouped = module.load_detections(input_csv)
    output = tmp_path / "tracks.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=module.CSV_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "frame": 0,
                "time_seconds": "0.000000",
                "track_id": 1,
                "confidence": "0.800000",
                "center_x": "12.000",
                "center_y": "13.000",
                "observed": 1,
            }
        )
    with output.open(newline="", encoding="utf-8") as file:
        assert next(csv.reader(file)) == module.CSV_FIELDS
    assert list(grouped) == [0, 2]


def test_track_rows_marks_only_currently_matched_detection_as_observed() -> None:
    module = load_script()

    class Track:
        is_initializing = False
        id = 7
        estimate = [[12.0, 13.0]]

        def __init__(self, last_detection):
            self.last_detection = last_detection

    class Detection:
        scores = [0.8]

    current_detection = Detection()
    predicted_track = Track(Detection())
    observed_track = Track(current_detection)

    predicted_row, _ = next(module._track_rows([predicted_track], 4, 30.0, [current_detection]))
    observed_row, _ = next(module._track_rows([observed_track], 4, 30.0, [current_detection]))
    assert predicted_row["observed"] == 0
    assert observed_row["observed"] == 1
