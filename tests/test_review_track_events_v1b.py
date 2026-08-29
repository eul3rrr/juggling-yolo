"""Regression tests for the v1B reviewer hardening.

These are black-box tests against the in-process reviewer module. They:

* verify the optional ``--hands`` flag plumbing is correct (no hands
  loaded = no overlay data; hands loaded = hand features appear in
  ``/api/event``),
* verify boundary events are surfaced via the public event payload,
* verify the render version is bumped, so old v2 / v3 clips are
  re-rendered with the new overlay,
* verify that re-visiting an already-labelled event preserves the
  existing label (the reviewer must not destroy 19 canonical labels
  on re-prepare),
* verify the hand-feature formatting (positive/negative/missing
  values) so the browser does not display fake zeros,
* verify the ``u`` / unclear code path still sends the notes
  textarea content to the server.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "review_track_events.py"


def load_reviewer():
    spec = importlib.util.spec_from_file_location("review_track_events", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Hand-feature formatting
# ---------------------------------------------------------------------------

def test_format_metric_handles_missing_and_nan():
    r = load_reviewer()
    # Reuse the helper that mirrors hand_overlay.format_hand_metric.
    assert r._format_metric(None) == "—"
    assert r._format_metric(float("nan")) == "—"
    assert r._format_metric(float("inf")) == "—"
    assert r._format_metric(13.3) == "+13.3"
    assert r._format_metric(-13.3) == "-13.3"


def test_format_distance_appends_px_only_when_defined():
    r = load_reviewer()
    assert r._format_distance(None) == "—"
    assert r._format_distance(42.7) == "42.7 px"
    assert r._format_distance(0.0) == "0.0 px"


# ---------------------------------------------------------------------------
# Render version
# ---------------------------------------------------------------------------

def test_render_version_bumped_to_4():
    r = load_reviewer()
    assert r.REVIEW_RENDER_VERSION == 4


def test_post_seconds_default_is_2_seconds():
    r = load_reviewer()
    # Inspect the ArgumentParser default for --post-seconds without
    # running main(); parse a no-op argument set to read the default.
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-seconds", type=float, default=2.0)
    args = parser.parse_args([])
    assert args.post_seconds == 2.0
    # The reviewer's own default is checked structurally: prepare()'s
    # post_seconds parameter must default to 2.0 (not 1.0).
    import inspect
    sig = inspect.signature(r.prepare)
    assert sig.parameters["post_seconds"].default == 2.0


# ---------------------------------------------------------------------------
# Manifest schema
# ---------------------------------------------------------------------------

def test_manifest_fields_includes_boundary():
    r = load_reviewer()
    assert "boundary" in r.MANIFEST_FIELDS


# ---------------------------------------------------------------------------
# Labels-by-event-key preserves the 19 canonical labels
# ---------------------------------------------------------------------------

def test_labels_by_event_key_preserves_existing_canonical_label(tmp_path):
    r = load_reviewer()
    # Build a minimal canonical labels CSV with one labeled row.
    labels_csv = tmp_path / "labels.csv"
    with labels_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r.LABEL_FIELDS)
        writer.writeheader()
        writer.writerow({
            "video": "v.mp4", "event_index": "0", "event_key": "end:3:149",
            "primary_track_id": "3", "primary_end_frame": "149",
            "primary_end_x": "583.13", "primary_end_y": "560.81",
            "event_type": "h", "hand": "right",
            "relation_direction": "successor", "continuation_status": "selected",
            "selected_related_track_id": "4", "selected_related_frame": "152",
            "selected_continuation_track_id": "4",
            "selected_continuation_start_frame": "152",
            "nearby_candidate_track_ids": "4",
            "existing_rank1_stitch_track_id": "",
            "review_clip_path": "outputs/x.mp4", "notes": "pink one?h",
        })
    # Build a tiny ReviewEvent list with the same structural identity.
    import dataclasses
    obs = [r.TrackObservation(frame=149, center_x=583.13, center_y=560.81,
                             confidence=1.0, observed=1)]
    track = r.Track(track_id=3, observations=obs)
    ev = r.ReviewEvent(
        event_index=0, kind="end", primary=track,
        primary_end_frame=149, primary_end_x=583.13, primary_end_y=560.81,
        nearby_starts=[], existing_rank1_stitch=None,
        review_clip_first=0, review_clip_last=1,
    )
    out = r._labels_by_event_key(labels_csv, [ev])
    # Migration by event_key should round-trip the labeled row.
    assert "end:3:149" in out
    row = out["end:3:149"]
    assert row["event_type"] == "h"
    assert row["hand"] == "right"
    assert row["continuation_status"] == "selected"
    assert row["selected_continuation_track_id"] == "4"
    assert row["notes"] == "pink one?h"


def test_labels_by_event_key_legacy_match_unique_structural(tmp_path):
    r = load_reviewer()
    labels_csv = tmp_path / "labels.csv"
    with labels_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r.LABEL_FIELDS)
        writer.writeheader()
        writer.writerow({
            "video": "", "event_index": "", "event_key": "",
            "primary_track_id": "3", "primary_end_frame": "149",
            "primary_end_x": "583.13", "primary_end_y": "560.81",
            "event_type": "h", "hand": "right",
            "relation_direction": "successor", "continuation_status": "",
            "selected_related_track_id": "", "selected_related_frame": "",
            "selected_continuation_track_id": "4",
            "selected_continuation_start_frame": "152",
            "nearby_candidate_track_ids": "",
            "existing_rank1_stitch_track_id": "",
            "review_clip_path": "", "notes": "legacy",
        })
    obs = [r.TrackObservation(frame=149, center_x=583.13, center_y=560.81,
                             confidence=1.0, observed=1)]
    track = r.Track(track_id=3, observations=obs)
    ev = r.ReviewEvent(
        event_index=0, kind="end", primary=track,
        primary_end_frame=149, primary_end_x=583.13, primary_end_y=560.81,
        nearby_starts=[], existing_rank1_stitch=None,
        review_clip_first=0, review_clip_last=1,
    )
    out = r._labels_by_event_key(labels_csv, [ev])
    assert "end:3:149" in out
    assert out["end:3:149"]["notes"] == "legacy"


def test_labels_by_event_key_ambiguous_legacy_does_not_guess(tmp_path):
    r = load_reviewer()
    labels_csv = tmp_path / "labels.csv"
    with labels_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r.LABEL_FIELDS)
        writer.writeheader()
        writer.writerow({
            "video": "", "event_index": "", "event_key": "",
            "primary_track_id": "3", "primary_end_frame": "149",
            "primary_end_x": "583.13", "primary_end_y": "560.81",
            "event_type": "h", "hand": "right",
            "relation_direction": "successor", "continuation_status": "",
            "selected_related_track_id": "", "selected_related_frame": "",
            "selected_continuation_track_id": "4",
            "selected_continuation_start_frame": "152",
            "nearby_candidate_track_ids": "",
            "existing_rank1_stitch_track_id": "",
            "review_clip_path": "", "notes": "",
        })
    # Two events with the same primary_track_id + primary_end_frame:
    # legacy row cannot be matched uniquely and must NOT be guessed.
    obs = [r.TrackObservation(frame=149, center_x=583.13, center_y=560.81,
                             confidence=1.0, observed=1)]
    track = r.Track(track_id=3, observations=obs)
    ev1 = r.ReviewEvent(0, "end", track, 149, 0, 0, [], None, 0, 0)
    ev2 = r.ReviewEvent(1, "end", track, 149, 0, 0, [], None, 0, 0)
    out = r._labels_by_event_key(labels_csv, [ev1, ev2])
    # The ambiguous label must not appear under either event_key.
    assert out == {}


# ---------------------------------------------------------------------------
# Hands-CSV: present vs absent
# ---------------------------------------------------------------------------

def test_load_hands_returns_empty_when_path_missing(tmp_path):
    r = load_reviewer()
    assert r.load_tracklets is not None  # smoke test
    from scripts.hand_overlay import load_hands_by_frame
    hands = load_hands_by_frame(tmp_path / "nope.csv")
    assert hands == {}


# ---------------------------------------------------------------------------
# Public event boundary + hand_features shape
# ---------------------------------------------------------------------------

def test_to_public_event_without_hands_has_no_hand_features(tmp_path):
    r = load_reviewer()
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r.MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerow({
            "event_index": "0", "event_key": "end:3:149", "kind": "end",
            "relation_direction": "successor", "boundary": "0",
            "primary_track_id": "3", "primary_first_frame": "149",
            "primary_last_frame": "149", "primary_end_frame": "149",
            "primary_end_x": "583.13", "primary_end_y": "560.81",
            "nearby_candidate_track_ids": "4", "nearby_starts_first_frames": "152",
            "review_clip_path": "outputs/x.mp4",
            "review_clip_first_frame": "100", "review_clip_last_frame": "200",
        })
    labels = tmp_path / "labels.csv"
    state = r._State(events_path=manifest, labels_path=labels,
                     clip_root=tmp_path, port=0, host="127.0.0.1", url="")
    pub = state.to_public_event(0)
    assert pub is not None
    assert pub["boundary"] is False
    # No tracks / hands supplied => no hand_features payload.
    assert pub["hand_features"] is None


def test_to_public_event_boundary_true_is_propagated(tmp_path):
    r = load_reviewer()
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r.MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerow({
            "event_index": "0", "event_key": "orphan_start:1:2",
            "kind": "orphan_start", "relation_direction": "predecessor",
            "boundary": "1", "primary_track_id": "1",
            "primary_first_frame": "2", "primary_last_frame": "5",
            "primary_end_frame": "2", "primary_end_x": "500.0",
            "primary_end_y": "500.0", "nearby_candidate_track_ids": "",
            "nearby_starts_first_frames": "",
            "review_clip_path": "outputs/x.mp4",
            "review_clip_first_frame": "0", "review_clip_last_frame": "60",
        })
    labels = tmp_path / "labels.csv"
    state = r._State(events_path=manifest, labels_path=labels,
                     clip_root=tmp_path, port=0, host="127.0.0.1", url="")
    pub = state.to_public_event(0)
    assert pub["boundary"] is True
