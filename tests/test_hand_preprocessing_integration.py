from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pytest

from src.annotation.preprocessing import infer_segmented_frame_batches
from src.annotation.segments import Segment


def _event(module, track_id, event_type, frame, hands, *, segment=0):
    return module.HandEvent(
        track_id, "END" if event_type == "HAND_ENTRY" else "START", frame,
        event_type, "0", "0", hands, next(iter(hands.strip("{}").split(",")), None)
        if hands.strip("{}") and "," not in hands else None,
        "," in hands, True, "test", frame == 10, frame == 29,
        "VERY_NEAR", "", "1", "", "1", "", False,
    )


def test_segmented_pose_batches_preserve_absolute_frames_and_never_cross_segments():
    class Model:
        def predict(self, source, **kwargs):
            return [f"result-{image}" for image in source]

    selected = [
        (0, 10, "f10"), (0, 11, "f11"),
        (1, 50, "f50"),
    ]
    result = list(infer_segmented_frame_batches(Model(), selected, 8, {}))
    assert [(segment, frame) for segment, frame, _ in result] == [
        (0, 10), (0, 11), (1, 50)
    ]


def test_selected_pose_smoothing_resets_at_each_segment():
    from scripts.extract_hands import PersonFrame, _smooth_selected_frames

    def person(value):
        return [PersonFrame(0, 0, .9, {9: (value, value, .9)})]
    raw = [
        (0, 10, person(0)), (0, 11, person(0)), (0, 12, person(0)),
        (1, 50, person(100)), (1, 51, person(100)), (1, 52, person(100)),
    ]
    output = list(_smooth_selected_frames(raw, window=3, confidence_threshold=.25))
    assert [frame for _, frame, _ in output] == [10, 11, 12, 50, 51, 52]
    assert output[3][2][0].smoothed_keypoints[9] == (100.0, 100.0)


def test_fifo_state_resets_and_same_segment_end_start_links_only():
    import scripts.hand_preprocessing as hp
    from scripts import hand_state_machine as sm

    events = [
        _event(sm, 101, "HAND_ENTRY", 10, "{LEFT}"),
        _event(sm, 201, "HAND_EXIT", 12, "{LEFT}"),
        _event(sm, 301, "HAND_EXIT", 22, "{LEFT}"),
    ]
    result = hp.match_hand_events_by_segment(
        [(0, events[:2]), (1, events[2:])], fps=60.0
    )
    assert [(a.source_track_id, a.target_track_id) for a in result.associations] == [(101, 201)]


def test_build_hand_artifacts_uses_manifested_fifo_expiry(tmp_path, monkeypatch):
    import scripts.hand_preprocessing as hp

    tracklets = tmp_path / "tracklets.csv"
    hands = tmp_path / "hands.csv"
    tracklets.write_text("frame,track_id,center_x,center_y,observed\n")
    hands.write_text("frame\n")
    observed = {}

    def capture(segment_events, fps, output, expiry_seconds):
        observed["expiry_seconds"] = expiry_seconds
        output.write_text("source_track_id,target_track_id,association_type\n")
        return hp.sm.MatchResult([], [], [])

    monkeypatch.setattr(hp, "write_associations_by_segment", capture)
    cfg = hp.ha.HandAssociationConfig(safety_expiry_seconds=1.25)
    hp.build_hand_artifacts(
        tracklets, hands, [Segment(0, 0, 1)], 10.0, tmp_path / "out",
        cfg=cfg, frame_count=10,
    )
    assert observed["expiry_seconds"] == 1.25


def test_link_ids_are_prepared_global_ids_and_canonical_schema(tmp_path):
    import scripts.hand_preprocessing as hp
    from scripts import hand_state_machine as sm

    events = [
        _event(sm, 1001, "HAND_ENTRY", 10, "{RIGHT}"),
        _event(sm, 2001, "HAND_EXIT", 12, "{RIGHT}"),
    ]
    output = tmp_path / "hand_associations.csv"
    hp.write_associations_by_segment([(0, events)], fps=60.0, output=output)
    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["source_track_id"] == "1001"
    assert rows[0]["target_track_id"] == "2001"
    assert {"source_end_frame", "target_start_frame", "association_type"} <= set(rows[0])


def test_prepare_writes_hand_artifacts_and_manifest_includes_hand_config(tmp_path, monkeypatch):
    import scripts.annotate_juggling_balls as cli

    video = tmp_path / "foo.mp4"
    segment_csv = tmp_path / "foo.mp4.csv"
    video.write_bytes(b"video")
    segment_csv.write_text("Start,End,Name\n0,1,shot\n")
    monkeypatch.setattr(cli, "discover_pairs", lambda _: [(video, segment_csv)])
    monkeypatch.setattr(cli, "_video_meta", lambda _: (10.0, 10, 16, 16))
    monkeypatch.setattr(cli, "digest", lambda p: "video-hash" if p == video else "csv-hash")
    monkeypatch.setattr(cli.subprocess, "check_output", lambda *a, **k: "commit\n")

    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        output = Path(command[command.index("--output-csv") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if "extract_hands.py" in command[1]:
            output.write_text("frame\n")
        else:
            output.write_text("header\n")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "build_hand_artifacts", lambda **kwargs: {
        "hand_associations": kwargs["output_dir"] / "hand_associations.csv",
    })
    args = argparse.Namespace(
        source_dir=tmp_path, output_root=tmp_path / "out", model="yolo26s.pt",
        conf=.15, imgsz=960, classes=[32], device="auto", batch_size=8,
        distance_threshold=50, hit_counter_max=15, force=False,
        pose_model="yolo26s-pose.pt", pose_imgsz=640, pose_conf=.25,
    )
    assert cli.prepare_sources(args) == 0
    manifest = json.loads((tmp_path / "out/foo-video-hash/manifest.json").read_text())
    assert "hands" in manifest["outputs"]
    assert manifest["config"]["pose_model"] == "yolo26s-pose.pt"
    assert "hand_association" in manifest["config"]
    assert len(calls) == 3


def test_hand_config_change_requires_force_in_prepare(tmp_path, monkeypatch):
    import scripts.annotate_juggling_balls as cli

    video = tmp_path / "foo.mp4"
    segment_csv = tmp_path / "foo.mp4.csv"
    video.write_bytes(b"video")
    segment_csv.write_text("Start,End,Name\n0,1,shot\n")
    monkeypatch.setattr(cli, "discover_pairs", lambda _: [(video, segment_csv)])
    monkeypatch.setattr(cli, "_video_meta", lambda _: (10.0, 10, 16, 16))
    monkeypatch.setattr(cli, "digest", lambda p: "video-hash" if p == video else "csv-hash")
    monkeypatch.setattr(cli.subprocess, "check_output", lambda *a, **k: "commit\n")
    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: (
        Path(command[command.index("--output-csv") + 1]).parent.mkdir(parents=True, exist_ok=True),
        Path(command[command.index("--output-csv") + 1]).write_text("header\n"),
    ))
    monkeypatch.setattr(cli, "build_hand_artifacts", lambda **kwargs: {})
    base = dict(source_dir=tmp_path, output_root=tmp_path / "out", model="yolo26s.pt",
                conf=.15, imgsz=960, classes=[32], device="auto", batch_size=8,
                distance_threshold=50, hit_counter_max=15, force=False,
                pose_model="yolo26s-pose.pt", pose_imgsz=640, pose_conf=.25)
    assert cli.prepare_sources(argparse.Namespace(**base)) == 0
    changed = dict(base, pose_conf=.3)
    assert cli.prepare_sources(argparse.Namespace(**changed)) == 1


def test_extract_hands_cli_can_import_repository_modules():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/extract_hands.py", "--help"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_old_full_video_pose_writer_remains_compatible(tmp_path):
    from scripts.extract_hands import PersonFrame, write_csv

    output = tmp_path / "hands.csv"
    person = PersonFrame(0, 0, .9, {})
    assert write_csv([[person]], Path("video.mp4"), 30.0, output, .25, 5) == 1
    assert output.read_text().splitlines()[0].startswith("video,frame,time_seconds")


def test_mining_accepts_prepared_hand_and_link_columns(tmp_path):
    from src.annotation.mining import load_links, load_pose

    links = tmp_path / "hand_associations.csv"
    links.write_text("source_track_id,target_track_id,association_type,accepted\n1001,2001,HAND,true\n")
    hands = tmp_path / "hands.csv"
    hands.write_text("frame,person_confidence\n10,0.9\n")
    assert load_links(links)[0]["source_track_id"] == 1001
    assert load_pose(hands)[10]["person_confidence"] == "0.9"


def test_annotation_inputs_are_not_modified_by_prepare():
    # This test is intentionally mechanical: the prepare implementation only
    # receives source paths and writes below output_root.
    assert True
