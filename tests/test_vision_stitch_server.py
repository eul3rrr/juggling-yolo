from pathlib import Path
import csv
import json
import sys
import threading
import urllib.error
import urllib.request

import cv2
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.vision_stitch.server import LABEL_FIELDS, LabelStore, build_items, make_server  # noqa: E402


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("clip") / "synthetic.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 60.0, (320, 180))
    for _ in range(60):
        writer.write(np.zeros((180, 320, 3), np.uint8))
    writer.release()
    return path


def write_fixture(root: Path, clip: Path, with_result: bool = True):
    events_root, results_root = root / "events", root / "results"
    directory = events_root / "end_66_100"
    directory.mkdir(parents=True)
    (directory / "01_source_pre_66_98.jpg").write_bytes(b"\xff\xd8fixture")
    (directory / "manifest.json").write_text(json.dumps({
        "event_key": "end:66:100", "prompt_version": "v1", "segment_index": 2,
        "window_frames": 30, "top_k": 2,
        "video": {"path": str(clip), "fps": 60.0, "frame_count": 60, "width": 320, "height": 180},
        "source": {"track_id": 66, "last_frame": 30, "last_x": 10.0, "last_y": 20.0, "last_seconds": 0.5,
                   "last_confidence": 0.9, "observed_len": 12, "velocity_x": 1.0, "velocity_y": 0.0},
        "candidates": [{"letter": "A", "track_id": 70, "first_frame": 34, "first_x": 1.0, "first_y": 1.0,
                        "first_confidence": 0.8, "observed_len": 6, "gap_frames": 4, "gap_seconds": 0.07,
                        "predicted_x": 1.0, "predicted_y": 1.0, "prediction_error": 4.5, "rank": 1}],
        "cv_rank1": {"track_id": 70, "prediction_error": 4.5, "gap_frames": 4},
        "images": [{"file": "01_source_pre_66_98.jpg", "role": "source_pre", "role_index": 1, "letter": None,
                    "label": "END tracklet T66 before it is lost", "track_id": 66, "frame": 30, "seconds": 0.5,
                    "requested_offset_frames": -30}],
    }) + "\n")
    if with_result:
        results_root.mkdir(parents=True, exist_ok=True)
        (results_root / "end_66_100.json").write_text(json.dumps({
            "event_key": "end:66:100", "model": "deepseek/deepseek-v4.1-flash", "prompt_version": "v1",
            "candidate_track_id": 70, "latency_s": 12.0,
            "verdict": {"parse_ok": True, "decision": "stitch", "candidate_letter": "A", "confidence": 0.77,
                        "reason": "motion extrapolates", "error": None},
            "usage": {"cost_usd": 0.002, "prompt_tokens": 2000},
            "raw_text": '{"decision":"stitch","candidate":"A"}', "error": None,
        }) + "\n")
    return events_root, results_root


def test_label_store_preserves_existing_rows_and_updates_in_place(tmp_path):
    path = tmp_path / "labels" / "vision_stitch_review_labels.csv"
    store = LabelStore(path)
    store.save("end:66:100", {"label": "correct", "note": "first pass"})
    store.save("end:67:120", {"label": "wrong", "note": ""})
    reloaded = LabelStore(path)
    first = reloaded.get("end:66:100")
    assert first is not None and first["label"] == "correct"
    reloaded.save("end:66:100", {"label": "unclear", "note": "second look"})
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 2                                     # updated, not duplicated
    assert list(rows[0].keys()) == LABEL_FIELDS
    updated = reloaded.get("end:66:100")
    assert updated is not None and updated["note"] == "second look"
    assert reloaded.counts() == {"correct": 0, "wrong": 1, "unclear": 1}


def test_label_store_rejects_unknown_values(tmp_path):
    store = LabelStore(tmp_path / "labels.csv")
    with pytest.raises(ValueError):
        store.save("end:1:1", {"label": "maybe"})


def test_build_items_merges_manifest_result_and_label(tmp_path, clip):
    events_root, results_root = write_fixture(tmp_path, clip)
    labels = LabelStore(tmp_path / "labels.csv")
    items = build_items(events_root, results_root, labels, clip.name)
    assert len(items) == 1
    item = items[0]
    assert item["slug"] == "end_66_100"
    assert item["model"]["decision"] == "stitch" and item["model"]["candidate_track_id"] == 70
    assert item["cv_rank1"]["track_id"] == 70
    assert item["images"][0]["url"] == "/evidence/end_66_100/01_source_pre_66_98.jpg"
    assert item["window"]["reference_frame"] == 30 and item["window"]["first_frame"] == 0
    assert item["label"] is None


def test_server_serves_items_evidence_frames_and_labels(tmp_path, clip):
    events_root, results_root = write_fixture(tmp_path, clip)
    labels = LabelStore(tmp_path / "labels.csv")
    server = make_server(events_root, results_root, labels, clip, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        payload = json.loads(urllib.request.urlopen(f"{base}/api/items", timeout=10).read())
        assert payload["items"][0]["event_key"] == "end:66:100"

        body = urllib.request.urlopen(f"{base}/evidence?event=end_66_100&file=01_source_pre_66_98.jpg", timeout=10).read()
        assert body.startswith(b"\xff\xd8")

        frame = urllib.request.urlopen(f"{base}/frame?event=end_66_100&frame=30", timeout=15).read()
        assert frame[:2] == b"\xff\xd8"

        request = urllib.request.Request(
            f"{base}/api/label", method="POST",
            data=json.dumps({"event_key": "end:66:100", "label": "correct", "note": "looks right"}).encode(),
            headers={"Content-Type": "application/json"})
        saved = json.loads(urllib.request.urlopen(request, timeout=10).read())
        assert saved["label"]["label"] == "correct"
        assert saved["label"]["model_decision"] == "stitch"
        assert saved["label"]["model_candidate_track_id"] == 70
        assert saved["label_counts"]["correct"] == 1
        persisted = LabelStore(labels.path).get("end:66:100")
        assert persisted is not None and persisted["note"] == "looks right"

        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"{base}/evidence?event=../etc&file=passwd", timeout=10)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
