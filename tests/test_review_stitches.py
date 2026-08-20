from pathlib import Path
import csv
import importlib.util
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "review_stitches.py"


def load_script():
    spec = importlib.util.spec_from_file_location("review_stitches", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate_row(source=28, target=29):
    return {
        "source_tracklet": source, "candidate_tracklet": target, "gap_frames": 2,
        "prediction_error": 1.5, "source_end_frame": 10, "candidate_start_frame": 13,
        "predicted_x": 16, "predicted_y": 0, "candidate_start_x": 20,
        "candidate_start_y": 4, "end_velocity_x": 2, "end_velocity_y": 0,
        "candidate_rank": 1,
    }


def test_candidate_parser_reads_required_fields(tmp_path: Path) -> None:
    module = load_script()
    path = tmp_path / "candidates.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=module.CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerow(candidate_row())
    candidates = module.load_candidates(path)
    assert candidates[0].source_tracklet == 28
    assert candidates[0].candidate_start_frame == 13
    assert candidates[0].prediction_error == 1.5


def test_clip_bounds_convert_seconds_and_clamp() -> None:
    module = load_script()
    assert module.clip_bounds(3, 20, 30, 24) == (0, 23)
    assert module.clip_bounds(50, 52, 30, 100, 1, 1) == (20, 82)


def test_interpolation_is_linear_and_clamped() -> None:
    module = load_script()
    candidate = module.Candidate(**candidate_row())
    assert module.interpolate_bridge_point(candidate, 0) == (10, 0)
    assert module.interpolate_bridge_point(candidate, 11) == pytest.approx((40 / 3, 4 / 3))
    assert module.interpolate_bridge_point(candidate, 13) == (20, 4)
    assert module.interpolate_bridge_point(candidate, 100) == (20, 4)


def test_prepare_initializes_and_preserves_combined_labels(tmp_path: Path, monkeypatch) -> None:
    module = load_script()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    tracklets = tmp_path / "tracklets.csv"
    tracklets.write_text(
        "frame,time_seconds,track_id,confidence,center_x,center_y\n"
        "9,0,28,1,0,0\n10,0,28,1,2,0\n13,0,29,1,20,4\n", encoding="utf-8"
    )
    stitches = tmp_path / "stitches.csv"
    with stitches.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=module.CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerow(candidate_row())
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "video,source_tracklet,candidate_tracklet,gap_frames,prediction_error,label\n"
        "other.mp4,1,2,1,0.5,w\n", encoding="utf-8"
    )

    class FakeCapture:
        def __init__(self, _path): self.opened = True
        def isOpened(self): return self.opened
        def get(self, prop):
            return {module.cv2.CAP_PROP_FPS: 30, module.cv2.CAP_PROP_FRAME_COUNT: 30,
                    module.cv2.CAP_PROP_FRAME_WIDTH: 64, module.cv2.CAP_PROP_FRAME_HEIGHT: 48}[prop]
        def release(self): pass

    monkeypatch.setattr(module.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(module, "render_clip", lambda *args: args[1].write_bytes(b"clip"))
    output = tmp_path / "review"
    module.prepare(video, tracklets, stitches, output, labels)
    with labels.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 2
    current = next(row for row in rows if row["source_tracklet"] == "28")
    assert current["label"] == ""
    assert current["clip_path"]
    current["label"] = "c"
    module.write_labels(labels, rows)
    module.prepare(video, tracklets, stitches, output, labels)
    with labels.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert next(row for row in rows if row["source_tracklet"] == "28")["label"] == "correct"
    assert len(rows) == 2
