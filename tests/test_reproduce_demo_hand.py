"""Frozen CSV reproduction, not an algorithm-quality benchmark."""
import csv
import hashlib
import pytest

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STEM = "identical_balls_trick_000_018"
sys.path.insert(0, str(ROOT / "scripts"))


def test_cli_refuses_nonempty_output_directory(tmp_path):
    sentinel = tmp_path / "existing.csv"
    sentinel.write_text("do not overwrite")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reproduce_demo_hand.py"),
         "--output-dir", str(tmp_path)], capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "empty" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["existing.csv"]
    assert sentinel.read_text() == "do not overwrite"


@pytest.mark.parametrize("relative,sha256", [
    (f"detections/demo/{STEM}_yolo26l_classes-32_norfair_dt50_hc5.csv",
     "daa7905eac1ec6bc9b96c4c9ea791fbbc4673d0b3a6533b771a39798a066569b"),
    (f"tests/fixtures/demo_hand/{STEM}_yolo26s-pose-hands.csv",
     "5ddb7d426e934f4f7bc288969c8d93a54be582a0a630d0ab54343f5ac5a8f843"),
    (f"detections/{STEM}_yolo26s-pose.csv",
     "0d273faf9bd68c1f9e543405fb902dd05c5d25a26fca66f39c544cf2531211fc"),
])
def test_frozen_input_provenance(relative, sha256):
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == sha256


def test_wrist_only_pose_is_not_the_historical_augmented_pose():
    # This is an explicit limitation, not an accepted approximation or skip.
    import hand_boundaries as hb
    raw = ROOT / f"detections/{STEM}_yolo26s-pose.csv"
    with raw.open(newline="") as f:
        fields = csv.DictReader(f).fieldnames
    assert "left_wrist_x_smooth" not in fields
    assert "body_scale_shoulder_px" not in fields
    hands = hb.ha._load_hands_by_frame(raw, hb.CONFIG.confidence_threshold)
    tracklets = hb.load_observed_tracklets(
        ROOT / f"detections/demo/{STEM}_yolo26l_classes-32_norfair_dt50_hc5.csv")
    assessments = hb.assess_all(tracklets, hands)
    assert assessments and not any(a.eligible_hands for a in assessments)



def test_cli_regenerates_all_three_shipped_csvs_byte_exact(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reproduce_demo_hand.py"),
         "--output-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for suffix in ("hand_events", "hand_associations", "hand_state_trace"):
        name = f"{STEM}_{suffix}.csv"
        assert (tmp_path / name).read_bytes() == (ROOT / "detections/demo" / name).read_bytes(), name
    with (tmp_path / f"{STEM}_hand_associations.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(int(r["source_track_id"]), int(r["target_track_id"])) for r in rows] == [
        (3, 4), (1, 5), (4, 6), (5, 10), (2, 11), (6, 13),
    ]
