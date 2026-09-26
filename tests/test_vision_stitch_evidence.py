from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.review_track_events import Track, TrackObservation  # noqa: E402
from src.annotation.segments import Segment  # noqa: E402
from src.vision_stitch.candidates import build_events  # noqa: E402
from src.vision_stitch.evidence import (EvidenceConfig, FrameReader,  # noqa: E402
                                        build_event_evidence, candidate_letters,
                                        manifest_is_current, render_crop)
from src.vision_stitch.prompt import build_request  # noqa: E402

FPS = 60.0
FRAMES = 150


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("clip") / "synthetic.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (640, 360))
    assert writer.isOpened(), "OpenCV could not open a VideoWriter"
    for index in range(FRAMES):
        frame = np.zeros((360, 640, 3), np.uint8)
        cv2.circle(frame, (60 + (index * 3) % 500, 80 + (index * 2) % 200), 12, (255, 255, 255), -1)
        cv2.putText(frame, str(index), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 0), 2)
        writer.write(frame)
    writer.release()
    return path


def make_track(track_id, points):
    return Track(track_id=track_id, observations=[
        TrackObservation(frame=frame, center_x=x, center_y=y, confidence=0.9, observed=1)
        for frame, x, y in points])


def make_event(*, source_points=None, candidate_specs=None, window=60):
    """Source track is dense and ends at frame 44; candidates start 34 and 46 frames later."""
    source_points = source_points or [(frame, 100.0 + frame, 100.0 + frame * 0.5) for frame in range(5, 45)]
    candidate_specs = candidate_specs or [(78, 130.0, 120.0), (90, 200.0, 150.0)]
    tracks = {1: make_track(1, source_points)}
    for offset, (first, x, y) in enumerate(candidate_specs, start=2):
        tracks[offset] = make_track(offset, [(first + step * 2, x + step * 3, y - step) for step in range(6)])
    events, _ = build_events(tracks, [Segment(index=0, start=0.0, end=FRAMES / FPS)], FPS, FRAMES,
                             window_frames=window, top_k=3)
    return tracks, events[0]


def test_candidate_letters():
    assert candidate_letters(3) == ["A", "B", "C"]
    with pytest.raises(ValueError):
        candidate_letters(27)


def test_frame_reader_reports_metadata_and_clips(clip):
    reader = FrameReader(clip)
    assert reader.frame_count == FRAMES
    assert reader.fps == pytest.approx(FPS, abs=0.5)
    assert (reader.width, reader.height) == (640, 360)
    assert reader(0).shape == (360, 640, 3)
    with pytest.raises(ValueError):
        reader(FRAMES)
    reader.release()


def test_render_crop_marks_the_ball_and_resizes(clip):
    image = FrameReader(clip)(10)
    config = EvidenceConfig()
    crop = render_crop(image, 300.0, 180.0, (0, 255, 0), "T1 test", config)
    assert crop.shape[1] == config.crop_out_w
    assert crop.shape[0] > config.crop_h                       # info bar adds height
    # the ring is drawn in green somewhere in the crop body
    body = crop[28:, :, :]
    assert (body[:, :, 1] > 200).any()


def test_build_event_evidence_writes_the_full_image_set(clip, tmp_path):
    tracks, event = make_event()
    reader = FrameReader(clip)
    try:
        out_dir = tmp_path / "end_1_44"
        manifest = build_event_evidence(event, tracks, reader, out_dir, EvidenceConfig(), "v1")
        roles = [image["role"] for image in manifest["images"]]
        pre, lost, candidate, context = (manifest["images_per_role"][key]
                                         for key in ("source_pre", "source_lost", "candidate", "context"))
        assert pre == 4                                        # dense source track: no offsets collapse
        assert manifest["images_per_role"] == {"source_pre": 4, "source_lost": 1, "candidate": 6, "context": 1}
        assert roles[:pre] == ["source_pre"] * pre
        assert roles[pre] == "source_lost"
        assert roles[pre + 1:pre + 1 + candidate] == ["candidate"] * candidate
        assert roles[-1] == "context" and context == 1
        assert len(manifest["images"]) == pre + lost + candidate + context == 12
        assert sum(1 for _ in out_dir.glob("*.jpg")) == 12
        for image in manifest["images"]:
            payload = (out_dir / image["file"]).read_bytes()
            assert payload[:2] == b"\xff\xd8"                     # JPEG magic
            decoded = cv2.imread(str(out_dir / image["file"]))
            assert decoded is not None and decoded.size > 0
        assert all(image["seconds"] == pytest.approx(image["frame"] / FPS) for image in manifest["images"])
        assert [c["letter"] for c in manifest["candidates"]] == ["A", "B"]
        assert manifest["cv_rank1"]["track_id"] == manifest["candidates"][0]["track_id"]
        assert manifest["prompt_version"] == "v1"
    finally:
        reader.release()


def test_sparse_source_track_never_repeats_the_same_frame(clip, tmp_path):
    tracks, event = make_event(source_points=[(40, 100.0, 100.0), (42, 104.0, 102.0), (44, 108.0, 104.0)])
    reader = FrameReader(clip)
    try:
        manifest = build_event_evidence(event, tracks, reader, tmp_path / "sparse", EvidenceConfig(), "v1")
        pre = [image for image in manifest["images"] if image["role"] == "source_pre"]
        assert len({image["frame"] for image in pre}) == len(pre)      # no duplicate images
        assert manifest["images_per_role"]["source_pre"] == 2          # frames 40 and 44 survive
    finally:
        reader.release()


def test_offsets_are_clamped_near_the_start_of_the_video(clip, tmp_path):
    tracks, event = make_event(source_points=[(1, 50.0, 50.0), (2, 52.0, 51.0)], candidate_specs=[])
    event["candidates"] = []
    reader = FrameReader(clip)
    try:
        manifest = build_event_evidence(event, tracks, reader, tmp_path / "clamped", EvidenceConfig(), "v1")
        frames = [image["frame"] for image in manifest["images"]]
        assert min(frames) >= 0 and max(frames) < FRAMES
        assert all((tmp_path / "clamped" / image["file"]).is_file() for image in manifest["images"])
    finally:
        reader.release()


def test_manifest_is_current_detects_drift(clip, tmp_path):
    tracks, event = make_event()
    reader = FrameReader(clip)
    try:
        out_dir = tmp_path / "current"
        config = EvidenceConfig()
        manifest = build_event_evidence(event, tracks, reader, out_dir, config, "v1")
        assert manifest_is_current(manifest, event, config, "v1", out_dir)
        assert not manifest_is_current(manifest, event, config, "v2", out_dir)          # prompt changed
        assert not manifest_is_current(manifest, event, EvidenceConfig(crop_out_w=500), "v1", out_dir)
        (out_dir / manifest["images"][0]["file"]).unlink()                              # evidence lost
        assert not manifest_is_current(manifest, event, config, "v1", out_dir)
    finally:
        reader.release()


def test_prompt_carries_every_timestamp_and_the_candidate_list(clip, tmp_path):
    tracks, event = make_event()
    reader = FrameReader(clip)
    try:
        out_dir = tmp_path / "prompt"
        manifest = build_event_evidence(event, tracks, reader, out_dir, EvidenceConfig(), "v1")
        content = build_request(manifest, out_dir)
        kinds = [part["type"] for part in content]
        assert kinds.count("image_url") == len(manifest["images"])
        assert kinds[0] == "text" and kinds[-1] == "text"
        text = "\n".join(part["text"] for part in content if part["type"] == "text")
        for image in manifest["images"]:
            assert f"t={image['seconds']:.2f}s" in text
            assert f"frame {image['frame']}" in text
        assert "A = tracklet T" in text and "B = tracklet T" in text
        for candidate in manifest["candidates"]:
            assert f"{candidate['letter']} = tracklet T{candidate['track_id']}" in text
        assert all(part["image_url"]["url"].startswith("data:image/jpeg;base64,")
                   for part in content if part["type"] == "image_url")
    finally:
        reader.release()
