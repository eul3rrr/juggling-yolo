"""Smoke tests for the new comparison + visualization scripts.

These tests do not exercise YOLO or Norfair.  They only verify that the
new scripts:
  * load their dependencies
  * parse the CSV columns they expect
  * produce the expected summary keys when given tiny synthetic inputs
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(module_name: str, script: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "scripts" / script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_compare_arms_summary_keys(tmp_path: Path) -> None:
    compare_arms = _load("compare_arms_test", "compare_arms.py")
    det_a = tmp_path / "det_a.csv"
    det_b = tmp_path / "det_b.csv"
    det_a.write_text(
        "video,frame,time_seconds,class_id,class_name,confidence,x1,y1,x2,y2,center_x,center_y,width,height\n"
        "x.mp4,0,0.0,32,sports ball,0.5,0,0,10,10,5,5,10,10\n"
        "x.mp4,0,0.0,32,sports ball,0.6,20,20,30,30,25,25,10,10\n",
        encoding="utf-8",
    )
    det_b.write_text(
        "video,frame,time_seconds,class_id,class_name,confidence,x1,y1,x2,y2,center_x,center_y,width,height\n"
        "x.mp4,0,0.0,32,sports ball,0.4,0,0,10,10,5,5,10,10\n"
        "x.mp4,0,0.0,32,sports ball,0.7,20,20,30,30,25,25,10,10\n"
        "x.mp4,0,0.0,32,sports ball,0.3,40,40,50,50,45,45,10,10\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "summary.json"
    out_csv = tmp_path / "summary.csv"
    arm_spec = (
        f"a:{det_a} arm_a arm_a 10 "
        f"b:{det_b} arm_b arm_b 10"
    )
    # The argparse takes --arms with multiple specs.  Easier to drive the
    # functions directly.
    csv_paths = {
        "a": {"detections": det_a},
        "b": {"detections": det_b},
    }
    arms: dict = {}
    for key, paths in csv_paths.items():
        rows = compare_arms._read_csv(paths["detections"], compare_arms.MINIMAL_FIELDS)
        arms[key] = {
            "video_name": key,
            "detection": compare_arms.detection_summary(rows, 10),
        }
    diff = compare_arms.framewise_diff(
        compare_arms._read_csv(csv_paths["a"]["detections"], compare_arms.MINIMAL_FIELDS),
        compare_arms._read_csv(csv_paths["b"]["detections"], compare_arms.MINIMAL_FIELDS),
    )
    assert diff["frames_compared"] == 1
    assert diff["abs_frame_count_difference_distribution"][1] == 1
    assert arms["a"]["detection"]["total_detections"] == 2
    assert arms["b"]["detection"]["total_detections"] == 3


def test_segment_script_smoke() -> None:
    """The script should at least import and the MAIN guard should not run
    at import time (otherwise smoke import of detect_video.py would also
    fail in the test process).
    """
    compare_arms = _load("segment_video_test", "segment_video.py")
    # If the module loaded, the constant set is present.
    assert "video" in compare_arms.MINIMAL_CSV_FIELDS
    assert "polygon_points" in compare_arms.INSTANCE_CSV_FIELDS
    assert "mask_centroid_valid" in compare_arms.INSTANCE_CSV_FIELDS
