"""Keep the public demo snapshot and its documentation internally consistent.

These checks protect published artifacts; decision-generation tests separately
exercise the hand pipeline. They do not treat the snapshot as ground truth.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_inputs_and_media_match_manifest():
    manifest = json.loads((ROOT / "docs/demo-manifest.json").read_text())
    for entry in manifest["files"]:
        data = (ROOT / entry["path"]).read_bytes()
        assert len(data) == entry["bytes"], entry["path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]


def test_readme_has_three_gif_to_mp4_links():
    readme = (ROOT / "README.md").read_text()
    links = re.findall(r"\[!\[([^\]]+)\]\(([^)]+\.gif)\)\]\(([^)]+\.mp4)\)", readme)
    assert len(links) == 3
    expected = ["demo-local-tracking", "demo-hand-stitching", "demo-reconstructed-identity"]
    for (_, image, video), stem in zip(links, expected):
        assert image == f"docs/assets/{stem}.gif"
        assert video == f"docs/assets/{stem}.mp4"
        assert (ROOT / image).is_file()
        assert (ROOT / video).is_file()


def test_current_documentation_relative_links_resolve():
    docs = [ROOT / "README.md", ROOT / "scripts/README.md", ROOT / "archive/README.md"]
    docs += list((ROOT / "docs").glob("*.md"))
    for path in docs:
        text = path.read_text()
        assert sum(line.startswith("```") for line in text.splitlines()) % 2 == 0, path
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link or link.startswith("#"):
                continue
            target = link.split("#", 1)[0]
            assert (path.parent / target).exists(), (path, link)
    assert "$$" not in (ROOT / "README.md").read_text()


def test_snapshot_counts_are_artifact_counts():
    base = ROOT / "detections/demo"
    with (base / "identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv").open() as f:
        tracks = {int(row["track_id"]) for row in csv.DictReader(f)}
    with (base / "identical_balls_trick_000_018_hand_associations.csv").open() as f:
        links = list(csv.DictReader(f))
    assert len(tracks) == 14
    assert len(links) == 6


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe needed for media metadata")
def test_previews_have_matching_timing_dimensions_and_size():
    metadata = []
    for stem in ("local-tracking", "hand-stitching", "reconstructed-identity"):
        path = ROOT / f"docs/assets/demo-{stem}.gif"
        result = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=width,height,nb_frames,avg_frame_rate,duration", "-of", "json", str(path),
        ], text=True))
        stream = result["streams"][0]
        metadata.append(stream)
        assert stream["width"] == 560 and stream["height"] == 316
        assert stream["nb_frames"] == "40"
        assert stream["avg_frame_rate"] == "10/1"
        assert float(stream["duration"]) == 4.0
        assert path.stat().st_size < 5_000_000
        assert b"NETSCAPE2.0\x03\x01\x00\x00\x00" in path.read_bytes()
    assert all(item == metadata[0] for item in metadata)
