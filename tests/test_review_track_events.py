from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_track_events.py"
spec = importlib.util.spec_from_file_location("review_track_events", MODULE_PATH)
assert spec and spec.loader
review = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = review
spec.loader.exec_module(review)


def track(track_id: int, frames: list[tuple[int, int]]) -> object:
    return review.Track(track_id, [
        review.TrackObservation(frame=f, center_x=float(f), center_y=float(f),
                                confidence=1.0, observed=observed)
        for f, observed in frames
    ])


def test_event_keys_and_orphan_predecessors_are_directional():
    tracks = {
        1: track(1, [(10, 1), (20, 1)]),
        2: track(2, [(130, 1), (140, 1)]),
    }
    events = review.generate_events(
        tracks, {}, fps=60.0, frame_count=200,
        review_window_seconds=1.0, orphan_lookback_seconds=2.0,
    )
    orphan = next(e for e in events if e.kind == "orphan_start" and e.primary.track_id == 2)
    assert orphan.event_key == "orphan_start:2:130"
    assert orphan.relation_direction == "predecessor"
    assert [t.track_id for t in orphan.nearby_starts] == [1]
    assert not any(e.kind == "existing_stitch" for e in events)


def test_draw_track_has_no_current_marker_after_end():
    t = track(1, [(1, 1), (2, 0)])
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert review._draw_track(frame, t, 2, (255, 0, 0), 2, 5).observed == 0
    assert review._draw_track(frame, t, 3, (255, 0, 0), 2, 5) is None


def test_label_migration_uses_stable_unique_structure(tmp_path: Path):
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review.LABEL_FIELDS)
        writer.writeheader()
        writer.writerow({
            "event_index": "99", "primary_track_id": "3",
            "primary_end_frame": "149", "event_type": "h",
            "hand": "right", "selected_continuation_track_id": "4",
            "selected_continuation_start_frame": "152",
        })
    ev = review.ReviewEvent(
        -1, "end", track(3, [(149, 1)]), 149, 0.0, 0.0, [], None,
        0, 0,
    )
    migrated = review._labels_by_event_key(labels, [ev])
    assert migrated["end:3:149"]["event_type"] == "h"
    assert migrated["end:3:149"]["hand"] == "right"


def test_manifest_version_detection(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("review_clip_path\noutputs/track_event_review/v2_old.mp4\n")
    assert review._manifest_needs_refresh(manifest)
    manifest.write_text(f"review_clip_path\noutputs/track_event_review/v{review.REVIEW_RENDER_VERSION}_ok.mp4\n")
    assert not review._manifest_needs_refresh(manifest)
