"""Shared segment-aware preprocessing primitives for detection and tracking."""
from collections import defaultdict, deque
from pathlib import Path
import cv2
import numpy as np
from .segments import segment_frame_bounds


def selected_frame_ranges(fps, frame_count, segments):
    ranges = []
    for segment in segments:
        start, end = segment_frame_bounds(segment, fps, frame_count)
        if end > start:
            ranges.append((start, end))
    return ranges


def iter_selected_frames(video, fps, frame_count, segments):
    """Yield (absolute source frame, decoded image) only for selected ranges."""
    capture = cv2.VideoCapture(str(Path(video)))
    if not capture.isOpened():
        raise RuntimeError(f'Could not open input video: {video}')
    try:
        for start, end in selected_frame_ranges(fps, frame_count, segments):
            capture.set(cv2.CAP_PROP_POS_FRAMES, start)
            frame_index = start
            while frame_index < end:
                ok, image = capture.read()
                if not ok:
                    raise RuntimeError(f'Could not decode source frame {frame_index}')
                yield frame_index, image
                frame_index += 1
    finally:
        capture.release()


def batched_frames(frames, batch_size):
    """Bounded-memory batches of absolute frame IDs and corresponding images."""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    indices, images = [], []
    for frame_index, image in frames:
        indices.append(frame_index)
        images.append(image)
        if len(images) == batch_size:
            yield indices, images
            indices, images = [], []
    if images:
        yield indices, images


def infer_frame_batches(model, frames, batch_size, predict_kwargs):
    """Yield model results paired with the absolute frame IDs in input order."""
    for indices, images in batched_frames(frames, batch_size):
        results = list(model.predict(source=images, **predict_kwargs))
        if len(results) != len(indices):
            raise RuntimeError(f'YOLO returned {len(results)} results for {len(indices)} frames')
        yield from zip(indices, results, strict=True)


def _row_for_track(track, frame, fps, current_detections):
    if getattr(track, 'is_initializing', False) or getattr(track, 'id', None) is None:
        return None
    estimate = np.asarray(track.estimate)
    if estimate.shape != (1, 2) or not np.isfinite(estimate).all():
        return None
    detection = getattr(track, 'last_detection', None)
    if detection is None:
        return None
    scores = np.asarray(getattr(detection, 'scores', [0])).reshape(-1)
    if len(scores) != 1 or not np.isfinite(scores[0]):
        return None
    x, y = (float(v) for v in estimate[0])
    return {
        'frame': frame, 'time_seconds': f'{frame / fps:.6f}',
        'track_id': int(track.id), 'confidence': f'{float(scores[0]):.6f}',
        'center_x': f'{x:.3f}', 'center_y': f'{y:.3f}',
        'observed': int(any(detection is d for d in current_detections)),
    }


def track_selected_detections(detections, fps, frame_count, segments, tracker_factory, convert_detections=lambda rows: rows):
    """Track each selected segment independently and remap IDs globally.

    ``tracker_factory`` receives no arguments; this makes reset behavior easy
    to test and keeps Norfair construction in the caller.
    """
    next_id = 1
    for segment_start, segment_end in selected_frame_ranges(fps, frame_count, segments):
        tracker = tracker_factory()
        id_map = {}
        for frame in range(segment_start, segment_end):
            current = convert_detections(detections.get(frame, []))
            tracks = tracker.update(current)
            for track in tracks:
                old_id = getattr(track, 'id', None)
                if old_id is None:
                    continue
                if old_id not in id_map:
                    id_map[old_id] = next_id
                    next_id += 1
                row = _row_for_track(track, frame, fps, current)
                if row is not None:
                    row['track_id'] = id_map[old_id]
                    yield row
