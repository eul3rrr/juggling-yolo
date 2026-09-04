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


def test_live_store_assigns_singleton_hid_without_stitch():
    engine = load("engine")
    store = engine.LiveTrackletStore(fps=30)
    for frame in range(5):
        store.observe(frame, [{"track_id": 7, "x": 100 + frame, "y": 80, "observed": True}], {})
    assert store.display_hids.hid_for(7) == 1
    assert len(store.tracklets[7].observed_history) == 5
    assert store.tracklets[7].start_event is not None


def test_live_store_ignores_predicted_rows_for_history():
    engine = load("engine")
    store = engine.LiveTrackletStore(fps=30)
    store.observe(0, [{"track_id": 2, "x": 10, "y": 10, "observed": True}], {})
    store.observe(1, [{"track_id": 2, "x": 11, "y": 10, "observed": False}], {})
    assert [p.frame for p in store.tracklets[2].observed_history] == [0]


def test_pending_payload_uses_hand_and_historical_bridge_coordinates():
    engine = load("engine")
    store = engine.LiveTrackletStore(fps=30)
    source = engine.HandEvent(3, "END", 10, "HAND_ENTRY", "10", "20", "{LEFT}", "LEFT", False, True, "very_near", False, False, "VERY_NEAR", "NEUTRAL", "10", "0.1", "10", "0.1", False)
    target = engine.HandEvent(8, "START", 15, "HAND_EXIT", "30", "40", "{LEFT}", "LEFT", False, True, "very_near", False, False, "VERY_NEAR", "SEPARATING", "10", "0.1", "10", "0.1", False)
    store.tracklets[3] = engine.LiveTracklet(3, [engine.Point(1, 1, 2)], observed_history=[engine.Point(10, 11, 12)])
    store.tracklets[8] = engine.LiveTracklet(8, [engine.Point(15, 3, 4)], observed_history=[engine.Point(15, 30, 40)])
    store.display_hids.hid_for(3)
    store._insert_event(source)
    assert store.pending(12)[0]["hand"] == "LEFT"
    store._insert_event(target)
    assert store.associations[0].source_track_id == 3
    assert store.bridges[0]["source_x"] == 11
    assert store.bridges[0]["target_y"] == 40


def test_frame_protocol_keeps_detections_hands_and_thresholds_explicit():
    protocol = load("protocol")
    payload = protocol.serialize_frame_state(protocol.FrameState(
        1, 640, 480, detections=[{"x1": 1, "y1": 2, "x2": 5, "y2": 6, "confidence": .9}],
        hands={"LEFT": {"x": 20, "y": 30, "confidence": .8, "body_scale": 100}},
        proximity={"LEFT": {"very_near_radius": 35, "possible_radius": 70}},
        pending=[{"hand": "LEFT", "hid": 1, "track_id": 3, "position": None}],
        runtime={"thresholds": {"very_near": .35, "possible": .7}},
    ))
    data = json.loads(payload)
    assert data["detections"][0]["confidence"] == .9
    assert data["hands"]["LEFT"]["body_scale"] == 100
    assert data["pending"][0]["hand"] == "LEFT"


def test_webcam_frame_state_payload_is_drawable_without_camera_access(monkeypatch):
    session = load("session")
    import numpy as np
    app = session.create_app()
    app.state.config = {"source": "webcam", "model": "yolo26l.pt", "device": "0"}
    app.state.inference_device = "0"
    source = type("Source", (), {"info": type("Info", (), {"fps": 30.0})()})()
    monkeypatch.setattr(session, "_infer_tracks", lambda _app, _frame: {
        "tracks": [{"track_id": 4, "x": 50.0, "y": 60.0, "confidence": .8, "observed": True}],
        "detections": [{"x1": 40.0, "y1": 50.0, "x2": 60.0, "y2": 70.0, "confidence": .8}],
        "hands": {"LEFT": {"x": 100.0, "y": 110.0, "confidence": .9, "body_scale": 100.0}},
        "terminated": set(),
    })
    state = session._frame_state(app, source, np.zeros((120, 160, 3), dtype=np.uint8), 0, 0.0)
    assert state.tracks[0]["hid"] == 1
    assert state.tracks[0]["observed_trail"][0]["frame"] == 0
    assert state.detections[0]["confidence"] == .8
    assert state.hands["LEFT"]["body_scale"] == 100.0
    assert state.proximity["LEFT"]["very_near_radius"] == 35.0
