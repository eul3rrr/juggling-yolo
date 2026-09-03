from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "src" / "live" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"live_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_protocol_serializes_explicit_readable_shape():
    protocol = load("protocol")
    payload = protocol.FrameState(frame_id=3, source_width=10, source_height=20)
    encoded = protocol.serialize_frame_state(payload)
    assert json.loads(encoded)["type"] == "frame"
    assert json.loads(encoded)["frame_id"] == 3
    assert "tracks" in json.loads(encoded)


def test_display_hids_follow_association_components():
    engine = load("engine")
    mapping = engine.DisplayHIDMap()
    assert mapping.apply_associations([(3, 4), (1, 5), (4, 6)]) == {3: 1, 4: 1, 1: 2, 5: 2, 6: 1}
    assert mapping.hid_for(8) == 3


def test_live_start_uses_first_five_points_and_provisional_then_final():
    engine = load("engine")
    adapter = engine.LiveReasoningAdapter(fps=60)
    for frame in range(4):
        state = adapter.observe_track(7, frame, 100 + frame, 100)
    assert state == "START_PROVISIONAL"
    assert adapter.track_points[7][-1].frame == 3
    adapter.observe_track(7, 4, 104, 100)
    assert len(adapter.track_points[7][:5]) == 5


def test_delayed_end_keeps_final_observed_boundary():
    engine = load("engine")
    adapter = engine.LiveReasoningAdapter(fps=30)
    for frame in (10, 11, 12):
        adapter.observe_track(2, frame, frame, 4)
    event = adapter.close_track(2, discovered_at=20)
    assert event.boundary_frame == 12
    assert event.boundary_frame < event.discovered_at


def test_late_event_recomputes_in_authoritative_boundary_order():
    engine = load("engine")
    adapter = engine.LiveReasoningAdapter(fps=30)
    adapter.add_test_event(engine.TestEvent(9, "HAND_ENTRY", 20, "{LEFT}"))
    adapter.add_test_event(engine.TestEvent(8, "HAND_EXIT", 10, "{LEFT}"))
    assert adapter.known_events[0].boundary_frame == 10
    assert adapter.recompute_count == 2


def test_pending_identity_has_no_fake_coordinate():
    engine = load("engine")
    pending = engine.pending_overlay_items([{"track_id": 3, "hid": 2, "hand": "LEFT", "age_seconds": 0.18}])
    assert pending[0]["position"] is None
    assert pending[0]["wrist_side"] == "LEFT"


def test_canonical_frozen_associations_are_regression_expectations():
    engine = load("engine")
    root = ROOT / "detections" / "detector_seg_comparison"
    result = engine.canonical_parity(
        root / "identical_balls_trick_000_018_hand_events.csv",
        root / "identical_balls_trick_000_018_hand_associations.csv",
    )
    assert result["accepted"] == [(3, 4), (1, 5), (4, 6), (5, 10), (2, 11), (6, 13)]
    assert (10, 14) not in result["accepted"]


def test_video_source_graceful_missing_camera():
    sources = load("sources")
    source = sources.OpenCVSource(kind="webcam", camera_index=9999)
    with pytest.raises(sources.SourceOpenError):
        source.open()


def test_fastapi_app_smoke():
    appmod = load("session")
    assert appmod.create_app().title == "Juggling Tracker Live"
