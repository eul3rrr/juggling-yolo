import csv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation.segments import Segment
from src.annotation.preprocessing import selected_frame_ranges, iter_selected_frames, track_selected_detections, batched_frames, infer_frame_batches


def test_selected_frame_ranges_are_absolute_and_exclude_gaps():
    segments = [Segment(0, 1.0, 2.0), Segment(1, 5.0, 6.0)]
    assert selected_frame_ranges(10, 100, segments) == [(10, 20), (50, 60)]


def test_frame_iterator_never_yields_excluded_frames(tmp_path):
    import cv2
    import numpy as np
    path = tmp_path / 'tiny.mp4'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (8, 8))
    for i in range(70):
        writer.write(np.full((8, 8, 3), i, dtype=np.uint8))
    writer.release()
    frames = list(iter_selected_frames(path, 10, 70, [Segment(0, 1, 2), Segment(1, 5, 6)]))
    assert [frame for frame, _ in frames] == list(range(10, 20)) + list(range(50, 60))


def test_tracker_resets_and_remaps_ids_at_segment_boundary():
    class FakeTrack:
        def __init__(self, ident, x):
            self.id, self.x = ident, x
            self.is_initializing = False
            self.last_detection = object()
            self.estimate = [[x, 10]]
    class FakeTracker:
        next_id = 0
        def __init__(self, **kwargs):
            FakeTracker.next_id += 1
            self.ident = FakeTracker.next_id
        def update(self, detections):
            return [FakeTrack(self.ident, 10)] if detections else []
    rows = {10: [{'center_x': 10, 'center_y': 10, 'confidence': .9}], 11: [{'center_x': 10, 'center_y': 10, 'confidence': .9}]}
    segments = [Segment(0, 1, 1.1), Segment(1, 1.1, 1.2)]
    out = list(track_selected_detections(rows, 10, 20, segments, FakeTracker))
    assert [r['frame'] for r in out] == [10, 11]
    assert out[0]['track_id'] != out[1]['track_id']
    assert [r['frame'] for r in out] == [10, 11]
    assert [r['time_seconds'] for r in out] == ['1.000000', '1.100000']


def test_empty_segments_yield_no_frames():
    assert selected_frame_ranges(30, 100, []) == []

def test_selected_frames_are_batched_and_results_keep_absolute_order():
    frames = [(f, f'image-{f}') for f in [10, 11, 12, 13, 50, 51, 52, 53, 54, 55]]
    batches = list(batched_frames(frames, 4))
    assert [len(indices) for indices, _ in batches] == [4, 4, 2]
    assert [f for indices, _ in batches for f in indices] == [10, 11, 12, 13, 50, 51, 52, 53, 54, 55]
    class Model:
        def __init__(self): self.calls = []
        def predict(self, source, **kwargs):
            self.calls.append(list(source)); return ['result-' + image for image in source]
    model = Model()
    mapped = list(infer_frame_batches(model, frames, 4, {'verbose': False}))
    assert mapped == [(f, f'result-image-{f}') for f in [10, 11, 12, 13, 50, 51, 52, 53, 54, 55]]
    assert [len(call) for call in model.calls] == [4, 4, 2]

def test_result_processing_does_not_plot_without_writer():
    from scripts.detect_video import consume_result
    class Result:
        boxes = None
        names = {}
        def plot(self, **kwargs): raise AssertionError('plot must not be called')
    assert consume_result(Result(), 50, None, object(), Path('foo.mp4'), 10, 16, 16) == 0

def test_folder_prepare_manifest_and_idempotent_skip(tmp_path, monkeypatch):
    import argparse
    import scripts.annotate_juggling_balls as cli
    video = tmp_path / 'foo.mp4'; csv_path = tmp_path / 'foo.mp4.csv'
    video.write_bytes(b'video'); csv_path.write_text('Start,End,Name\n0,1,shot\n')
    monkeypatch.setattr(cli, 'discover_pairs', lambda _: [(video, csv_path)])
    monkeypatch.setattr(cli, '_video_meta', lambda _: (10.0, 10, 16, 16))
    monkeypatch.setattr(cli, 'digest', lambda p: 'video-hash' if str(p).endswith('.mp4') else 'csv-hash')
    monkeypatch.setattr(cli.subprocess, 'check_output', lambda *a, **k: 'commit\n')
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        output = Path(command[command.index('--output-csv') + 1])
        output.write_text('header\n')
    monkeypatch.setattr(cli.subprocess, 'run', fake_run)
    args = argparse.Namespace(source_dir=tmp_path, output_root=tmp_path / 'out', model='yolo26s.pt', conf=.15, imgsz=960, classes=[32], device='auto', batch_size=32, distance_threshold=50, hit_counter_max=15, force=False)
    assert cli.prepare_sources(args) == 0
    manifest = (tmp_path / 'out').joinpath('foo-video-hash/manifest.json')
    assert len(calls) == 2 and manifest.is_file()
    assert __import__('json').loads(manifest.read_text())['config']['batch_size'] == 32
    assert '--batch-size' in calls[0]
    assert cli.prepare_sources(args) == 0
    assert len(calls) == 2
