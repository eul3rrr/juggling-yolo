from pathlib import Path
import inspect


def test_detector_arm_classes_are_explicit():
    from src.annotation.benchmark import detector_arms

    arms = detector_arms("yolo26l.pt", Path("best.pt"))
    assert arms["baseline"]["classes"] == [32]
    assert arms["finetuned"]["classes"] == [0]


def test_missing_top_level_segment_is_recovered_from_authoritative_source_metadata():
    from src.annotation.benchmark import attach_segment_metadata

    records = [{
        "timestamp": 5.0,
        "source": {"segments": [
            {"index": 0, "start": 0.0, "end": 4.0},
            {"index": 1, "start": 4.0, "end": 8.0},
        ]},
    }]
    enriched = attach_segment_metadata(records)
    assert enriched[0]["segment"]["index"] == 1


def test_segment_split_is_deterministic_balanced_and_has_no_leakage():
    from src.annotation.benchmark import split_records_by_segment

    records = [
        {"id": f"f{segment}-{index}", "segment": {"index": segment}}
        for segment, count in enumerate((20, 18, 17, 15, 12, 10, 8))
        for index in range(count)
    ]
    first = split_records_by_segment(records, val_fraction=0.2)
    second = split_records_by_segment(records, val_fraction=0.2)
    assert first == second
    by_segment = {}
    for row in first:
        by_segment.setdefault(row["segment"]["index"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in by_segment.values())
    val_count = sum(row["split"] == "val" for row in first)
    assert 15 <= val_count <= 25


def _track(track_id, frames):
    from scripts.review_track_events import Track, TrackObservation

    track = Track(track_id=track_id)
    track.observations = [TrackObservation(frame, frame, frame, 0.9, 1) for frame in frames]
    return track


def test_hard_events_reuse_end_orphan_and_segment_edge_semantics():
    from src.annotation.benchmark import build_hard_events
    from src.annotation.segments import Segment

    tracks = {
        1: _track(1, range(20, 31)),
        2: _track(2, range(70, 76)),
        3: _track(3, range(1, 3)),
    }
    events = build_hard_events("baseline", tracks, 10.0, 100, [Segment(0, 0, 10)])
    assert {event["event_kind"] for event in events} == {"track_end", "orphan_start"}
    assert all(event["event_frame"] not in {1, 2} for event in events)
    assert all("ordinary" not in event["event_kind"] for event in events)


def test_union_frames_deduplicate_and_preserve_both_arm_provenance():
    from src.annotation.benchmark import build_union_frames, classify_provenance

    baseline = [{"model_arm": "baseline", "event_key": "end:1:20", "event_kind": "track_end", "event_frame": 20}]
    finetuned = [{"model_arm": "finetuned", "event_key": "orphan_start:2:24", "event_kind": "orphan_start", "event_frame": 24}]
    frames = build_union_frames(baseline, finetuned, fps=60, frame_count=100)
    numbers = [row["frame"] for row in frames]
    assert numbers == sorted(set(numbers))
    assert 20 in numbers and 24 in numbers
    overlap = next(row for row in frames if row["frame"] == 20)
    assert classify_provenance(overlap["provenance"]) == "both"
    assert {entry["model_arm"] for entry in overlap["provenance"]} == {"baseline", "finetuned"}


def test_summary_uses_one_shared_selected_duration():
    from src.annotation.benchmark import summarize_arm

    tracks = {1: _track(1, [1, 2]), 2: _track(2, [5, 6, 7, 8, 9, 10])}
    events = [
        {"event_kind": "track_end"},
        {"event_kind": "track_end"},
        {"event_kind": "orphan_start"},
    ]
    summary = summarize_arm(
        detections=[{"frame": 1}, {"frame": 1}, {"frame": 2}],
        tracks=tracks,
        events=events,
        selected_duration_seconds=120.0,
    )
    assert summary["selected_duration_seconds"] == 120.0
    assert summary["total_detections"] == 3
    assert summary["frames_with_detections"] == 2
    assert summary["total_tracklets"] == 2
    assert summary["median_observed_tracklet_length"] == 4
    assert summary["track_end_events"] == 2
    assert summary["orphan_start_events"] == 1
    assert summary["unresolved_events_per_minute"] == 1.5


def test_viewer_payload_uses_same_raw_frame_for_both_panels():
    from src.annotation.benchmark import viewer_frame_payload

    rows = {
        "baseline": {12: [{"frame": 12, "confidence": 0.8}]},
        "finetuned": {12: [{"frame": 12, "confidence": 0.9}]},
    }
    payload = viewer_frame_payload(12, rows)
    assert payload["frame"] == 12
    assert payload["panels"]["baseline"]["frame"] == 12
    assert payload["panels"]["finetuned"]["frame"] == 12


def test_benchmark_builder_does_not_require_pose_or_hand_artifacts():
    from src.annotation import benchmark

    signature = inspect.signature(benchmark.build_benchmark)
    assert "pose" not in signature.parameters
    assert "hands" not in signature.parameters
