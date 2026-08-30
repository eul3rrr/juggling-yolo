#!/usr/bin/env python3
"""Interactive track-lifecycle / missing-stitch reviewer.

Generates one review event per observed track END on the canonical
identical_balls run, plus optional orphan-start events for tracks that
begin with no plausible predecessor. For each event the tool renders a
short H.264 review clip with overlays (frame number, trail of the
primary ending track, all currently active Norfair IDs, predicted vs
observed markers, YOLO detections, and the nearby new track candidates
with numeric selection keys).

A small local HTTP server serves the rendered clips and a plain
HTML/JS UI with full keyboard control. Labels are saved after each
reviewed item so quit/resume is safe.

Run:

    ./.venv/bin/python scripts/review_track_events.py serve \\
        --video videos/identical_balls_trick_000_018.mp4 \\
        --tracklets detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5.csv \\
        --detections detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32.csv \\
        --stitches detections/detector_seg_comparison/identical_balls_trick_000_018_yolo26l_classes-32_norfair_dt50_hc5_stitches.csv

The tool reuses clip manifests and labels on re-run; only missing
clips are re-rendered. Paths in committed code are repo-relative.
"""

from __future__ import annotations

import argparse
import csv
import http.server
import io
import json
import math
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
REVIEW_RENDER_VERSION = 4
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2  # noqa: E402


# ---------- paths / constants ----------

TRACKLET_FIELDS = (
    "frame", "time_seconds", "track_id", "confidence",
    "center_x", "center_y", "observed",
)
DETECTION_FIELDS = (
    "video", "frame", "time_seconds", "class_id", "class_name",
    "confidence", "x1", "y1", "x2", "y2", "center_x", "center_y",
    "width", "height",
)
CANDIDATE_FIELDS = (
    "source_tracklet", "candidate_tracklet", "gap_frames",
    "prediction_error", "source_end_frame", "candidate_start_frame",
    "candidate_rank",
)
LABEL_FIELDS = (
    "video", "event_index", "event_key", "primary_track_id", "primary_end_frame",
    "primary_end_x", "primary_end_y",
    "event_type", "hand", "relation_direction", "continuation_status",
    "selected_related_track_id", "selected_related_frame",
    "selected_continuation_track_id", "selected_continuation_start_frame",
    "nearby_candidate_track_ids",
    "existing_rank1_stitch_track_id",
    "review_clip_path", "notes",
)
MANIFEST_FIELDS = (
    "event_index", "event_key", "kind", "relation_direction", "boundary",
    "primary_track_id", "primary_first_frame", "primary_last_frame",
    "primary_end_frame", "primary_end_x", "primary_end_y",
    "nearby_candidate_track_ids",
    "nearby_starts_first_frames",
    "review_clip_path", "review_clip_first_frame", "review_clip_last_frame",
)

EVENT_TYPES = {
    "h": "HAND-MEDIATED BREAK",
    "a": "AIRBORNE BREAK",
    "n": "NORFAIR ASSOCIATION FAILURE",
    "x": "ID SWITCH / WRONG MERGE",
    "e": "TRUE END",
    "f": "FALSE-POSITIVE TRACK",
    "u": "UNCLEAR / AMBIGUOUS",
    "s": "SKIP",
}
HAND_LABELS = {"l": "left", "r": "right", "u": "unknown"}


# ---------- helpers ----------

def _stored(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_stored(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _safe(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value))


def _video_meta(video: Path) -> tuple[float, int, int, int]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if fps <= 0 or frames <= 0:
        raise RuntimeError(f"Bad video metadata: fps={fps} frames={frames}")
    return fps, frames, width, height


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _tailscale_ipv4() -> str | None:
    binary = shutil.which("tailscale")
    if not binary:
        return None
    try:
        out = subprocess.check_output(
            [binary, "ip", "-4"], timeout=2.0, text=True
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("100.") and re.match(r"^100\.\d+\.\d+\.\d+$", line):
            return line
    return None


# ---------- data loading ----------

@dataclass
class TrackObservation:
    frame: int
    center_x: float
    center_y: float
    confidence: float
    observed: int

    @property
    def is_observed(self) -> bool:
        return self.observed == 1


@dataclass
class Track:
    track_id: int
    observations: list[TrackObservation] = field(default_factory=list)

    @property
    def observed(self) -> list[TrackObservation]:
        return [o for o in self.observations if o.is_observed]

    @property
    def first_observed(self) -> TrackObservation | None:
        o = self.observed
        return min(o, key=lambda r: r.frame) if o else None

    @property
    def last_observed(self) -> TrackObservation | None:
        o = self.observed
        return max(o, key=lambda r: r.frame) if o else None

    @property
    def all_sorted(self) -> list[TrackObservation]:
        return sorted(self.observations, key=lambda r: r.frame)


def load_tracklets(path: Path) -> dict[int, Track]:
    if not path.is_file():
        raise FileNotFoundError(f"Tracklet CSV not found: {path}")
    tracks: dict[int, Track] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in TRACKLET_FIELDS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Tracklet CSV missing fields: {missing}")
        for row in reader:
            tid = int(row["track_id"])
            obs = TrackObservation(
                frame=int(row["frame"]),
                center_x=float(row["center_x"]),
                center_y=float(row["center_y"]),
                confidence=float(row["confidence"]),
                observed=int(row.get("observed", "1")),
            )
            tracks.setdefault(tid, Track(track_id=tid)).observations.append(obs)
    for track in tracks.values():
        track.observations.sort(key=lambda r: r.frame)
    return tracks


def load_detections(path: Path) -> dict[int, list[dict]]:
    if not path.is_file():
        return {}
    by_frame: dict[int, list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            by_frame[int(row["frame"])].append({
                "confidence": float(row["confidence"]),
                "center_x": float(row["center_x"]),
                "center_y": float(row["center_y"]),
                "x1": float(row["x1"]),
                "y1": float(row["y1"]),
                "x2": float(row["x2"]),
                "y2": float(row["y2"]),
            })
    return by_frame


def load_stitches(path: Path) -> dict[tuple[int, int], dict]:
    if path is None or not path.is_file():
        return {}
    out: dict[tuple[int, int], dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["source_tracklet"]), int(row["candidate_tracklet"]))
            existing = out.get(key, {})
            rank = int(row.get("candidate_rank", "99"))
            existing_rank = existing.get("candidate_rank", 99)
            if rank < existing_rank:
                out[key] = row
    return out


# ---------- event generation ----------

@dataclass
class ReviewEvent:
    event_index: int
    kind: str  # "end" | "orphan_start" | "existing_stitch"
    primary: Track
    primary_end_frame: int  # for "end"/"existing_stitch": last observed; for "orphan_start": first observed
    primary_end_x: float
    primary_end_y: float
    nearby_starts: list[Track]  # numbered candidates [1..N]
    existing_rank1_stitch: tuple[int, int] | None  # (source, candidate)
    review_clip_first: int
    review_clip_last: int
    boundary: bool = False

    @property
    def event_key(self) -> str:
        if self.kind == "existing_stitch" and self.existing_rank1_stitch:
            return (f"existing_stitch:{self.primary.track_id}:"
                    f"{self.primary_end_frame}:{self.existing_rank1_stitch[1]}")
        return f"{self.kind}:{self.primary.track_id}:{self.primary_end_frame}"

    @property
    def relation_direction(self) -> str:
        return "predecessor" if self.kind == "orphan_start" else "successor"


def generate_events(
    tracks: dict[int, Track],
    stitches: dict[tuple[int, int], dict],
    fps: float,
    frame_count: int,
    review_window_seconds: float = 1.0,
    orphan_lookback_seconds: float = 4.5,
    boundary_seconds: float = 0.5,
    include_existing_stitches: bool = False,
    include_orphan_starts: bool = True,
) -> list[ReviewEvent]:
    """Generate review events for every track end and orphan start.

    review_window_seconds is the generous forward-look used to discover
    candidate continuation tracks. boundary_seconds is the grace period
    around the video start/end at which a track start/end is marked
    as a boundary event (deprioritized but not discarded).
    """
    events: list[ReviewEvent] = []
    boundary_frames = max(1, int(round(boundary_seconds * fps)))
    review_window_frames = max(1, int(round(review_window_seconds * fps)))
    orphan_lookback_frames = max(1, int(round(orphan_lookback_seconds * fps)))

    # 1. END events (one per observed-end track)
    end_tracks: list[Track] = []
    for tid in sorted(tracks):
        track = tracks[tid]
        if track.last_observed is None:
            continue
        last_obs = track.last_observed
        end_tracks.append(track)
        nearby = _nearby_starts(tracks, last_obs.frame, review_window_frames,
                                exclude={tid})
        events.append(ReviewEvent(
            event_index=-1,
            kind="end",
            primary=track,
            primary_end_frame=last_obs.frame,
            primary_end_x=last_obs.center_x,
            primary_end_y=last_obs.center_y,
            nearby_starts=nearby,
            existing_rank1_stitch=_rank1_stitch_for_source(stitches, tid),
            review_clip_first=_clip_first(last_obs.frame, fps),
            review_clip_last=_clip_last(last_obs.frame, nearby, fps, frame_count),
            boundary=(last_obs.frame >= frame_count - boundary_frames),
        ))

    # 2. EXISTING-STITCH events (one per unique source track that the
    # current stitcher actually proposed something for). Skips when the
    # source end-event already covers it.
    if include_existing_stitches:
        seen_sources: set[int] = set()
        for (src, _cand), row in stitches.items():
            if src in seen_sources or src not in tracks:
                continue
            seen_sources.add(src)
            track = tracks[src]
            last_obs = track.last_observed
            if last_obs is None:
                continue
            # Only add a separate event when the rank-1 stitch lands
            # well AFTER the track's observed end (so we are looking
            # at the gap the stitcher decided matters).
            cand_tid = int(row["candidate_tracklet"])
            cand = tracks.get(cand_tid)
            if cand is None or cand.first_observed is None:
                continue
            cand_first = cand.first_observed.frame
            gap = cand_first - last_obs.frame
            if gap < 5:  # too tight — already covered by END event
                continue
            nearby = _nearby_starts(tracks, last_obs.frame, review_window_frames,
                                    exclude={src, cand_tid})
            events.append(ReviewEvent(
                event_index=-1,
                kind="existing_stitch",
                primary=track,
                primary_end_frame=last_obs.frame,
                primary_end_x=last_obs.center_x,
                primary_end_y=last_obs.center_y,
                nearby_starts=[cand] + nearby,
                existing_rank1_stitch=(src, cand_tid),
                review_clip_first=_clip_first(last_obs.frame, fps),
                review_clip_last=_clip_last(last_obs.frame, [cand] + nearby, fps, frame_count),
            ))

    # 3. ORPHAN-START events (one per track whose first observed frame
    # has no plausible predecessor track). These are the missing-stitch
    # cases that the current stitcher does NOT cover.
    if include_orphan_starts:
        for tid in sorted(tracks):
            track = tracks[tid]
            first = track.first_observed
            if first is None:
                continue
            # Skip starts inside the review-window after any other track's
            # observed end - those are already covered by END events.
            has_predecessor = False
            for other in tracks.values():
                if other.track_id == tid:
                    continue
                ol = other.last_observed
                if ol is None:
                    continue
                if 0 < first.frame - ol.frame <= review_window_frames:
                    has_predecessor = True
                    break
            if has_predecessor:
                continue
            # Genuinely orphan: show earlier possible predecessors, not even
            # later starts. This is a human-review window, not a stitch gate.
            nearby = _nearby_ends_before(tracks, first.frame,
                                         orphan_lookback_frames,
                                         exclude={tid})
            events.append(ReviewEvent(
                event_index=-1,
                kind="orphan_start",
                primary=track,
                primary_end_frame=first.frame,
                primary_end_x=first.center_x,
                primary_end_y=first.center_y,
                nearby_starts=nearby,
                existing_rank1_stitch=None,
                review_clip_first=_clip_first(first.frame, fps),
                review_clip_last=_clip_last(first.frame, nearby, fps, frame_count),
                boundary=(first.frame <= boundary_frames),
            ))

    events.sort(key=_event_sort_key)
    for i, ev in enumerate(events):
        ev.event_index = i
    return events


def _event_sort_key(ev: ReviewEvent) -> tuple[int, int]:
    """Boundary events go to the end; otherwise sort by frame."""
    return (1 if ev.boundary else 0, ev.primary_end_frame)


def _nearby_starts(tracks: dict[int, Track], after_frame: int,
                    window_frames: int, exclude: set[int]) -> list[Track]:
    starts: list[tuple[int, Track]] = []
    for tid, track in tracks.items():
        if tid in exclude:
            continue
        first = track.first_observed
        if first is None:
            continue
        if after_frame < first.frame <= after_frame + window_frames:
            starts.append((first.frame, track))
    starts.sort(key=lambda r: (r[0], r[1].track_id))
    return [t for _, t in starts]


def _nearby_ends_before(tracks: dict[int, Track], before_frame: int,
                        window_frames: int, exclude: set[int]) -> list[Track]:
    endings: list[tuple[int, Track]] = []
    for tid, track in tracks.items():
        if tid in exclude:
            continue
        last = track.last_observed
        if last is None:
            continue
        if 0 < before_frame - last.frame <= window_frames:
            endings.append((last.frame, track))
    # Most recent predecessor first: [1] is the closest earlier ending.
    endings.sort(key=lambda r: (-r[0], r[1].track_id))
    return [t for _, t in endings]


def _rank1_stitch_for_source(stitches: dict[tuple[int, int], dict],
                              source: int) -> tuple[int, int] | None:
    candidates = [(src, cand) for (src, cand) in stitches if src == source]
    if not candidates:
        return None
    candidates.sort(key=lambda k: int(stitches[k].get("candidate_rank", "99")))
    return candidates[0]


def _clip_first(end_frame: int, fps: float) -> int:
    return max(0, end_frame - max(1, int(round(1.0 * fps))))


def _clip_last(end_frame: int, nearby: Iterable[Track], fps: float,
               frame_count: int) -> int:
    latest = end_frame + max(1, int(round(1.0 * fps)))
    for track in nearby:
        first = track.first_observed
        if first is not None:
            latest = max(latest, first.frame + max(1, int(round(0.5 * fps))))
    return min(frame_count - 1, latest)


# ---------- clip rendering ----------

def _point(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def _text(frame, text: str, origin: tuple[int, int],
          color: tuple[int, int, int], scale: float = 0.55,
          thickness: int = 1, shadow: int = 3) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale,
                (0, 0, 0), shadow, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, thickness, cv2.LINE_AA)


def _boxed_text(frame, text: str, anchor: tuple[int, int],
                color: tuple[int, int, int], scale: float = 0.55) -> None:
    """Draw readable text spatially attached to a track point."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, 1)
    x = max(2, min(anchor[0], frame.shape[1] - text_width - 8))
    y = max(text_height + baseline + 2,
            min(anchor[1], frame.shape[0] - 4))
    pad = 4
    cv2.rectangle(
        frame,
        (x - pad, y - text_height - baseline - pad),
        (x + text_width + pad, y + baseline + pad),
        (12, 12, 12), -1,
    )
    cv2.rectangle(
        frame,
        (x - pad, y - text_height - baseline - pad),
        (x + text_width + pad, y + baseline + pad),
        color, 1, cv2.LINE_AA,
    )
    cv2.putText(frame, text, (x, y), font, scale, color, 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), font, scale, (255, 255, 255), 1, cv2.LINE_AA)


def _dashed_line(frame, a: tuple[int, int], b: tuple[int, int],
                 color: tuple[int, int, int], thickness: int = 2) -> None:
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length <= 0:
        return
    for start in range(0, int(length), 10):
        end = min(start + 5, length)
        p1 = (round(a[0] + (b[0] - a[0]) * start / length),
              round(a[1] + (b[1] - a[1]) * start / length))
        p2 = (round(a[0] + (b[0] - a[0]) * end / length),
              round(a[1] + (b[1] - a[1]) * end / length))
        cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)


def _draw_track(frame, track: Track, frame_index: int,
                color: tuple[int, int, int], thickness: int,
                radius: int) -> TrackObservation | None:
    """Draw history and return a current row only when active this frame."""
    rows = [o for o in track.all_sorted if o.frame <= frame_index][-30:]
    for first, second in zip(rows, rows[1:]):
        a = _point(first.center_x, first.center_y)
        b = _point(second.center_x, second.center_y)
        if first.is_observed and second.is_observed:
            cv2.line(frame, a, b, color, thickness, cv2.LINE_AA)
        else:
            _dashed_line(frame, a, b, color, max(1, thickness - 1))
    current = next((o for o in rows if o.frame == frame_index), None)
    if current is not None:
        pt = _point(current.center_x, current.center_y)
        if current.is_observed:
            cv2.circle(frame, pt, radius, color, -1, cv2.LINE_AA)
        else:
            cv2.circle(frame, pt, radius, color, 2, cv2.LINE_AA)
    return current


# ---------------------------------------------------------------------------
# Hand overlay (v1B)
# ---------------------------------------------------------------------------

# Late import so the reviewer module is importable without hand_features
# (which has no other heavy deps) being present. ``hand_overlay`` itself
# loads ``hand_features`` by file path, so this works in the venv even
# when ``scripts/`` is not on sys.path.
def _import_hand_overlay():
    import importlib.util as _il
    from pathlib import Path as _P
    _spec = _il.spec_from_file_location(
        "hand_overlay", _P(__file__).resolve().parent / "hand_overlay.py")
    assert _spec is not None and _spec.loader is not None
    _mod = _il.module_from_spec(_spec)
    # Register in sys.modules so that @dataclass inside hand_overlay
    # (e.g. HandMetrics) can be introspected at instantiation time.
    # Without this, Python 3.14's dataclasses._is_type raises
    # AttributeError: 'NoneType' object has no attribute '__dict__'
    # when it does sys.modules.get(cls.__module__).
    sys.modules.setdefault("hand_overlay", _mod)
    _spec.loader.exec_module(_mod)
    return _mod


_HAND_LEFT_COLOR = (90, 200, 255)   # cyan-ish, distinct from candidates
_HAND_RIGHT_COLOR = (255, 200, 90)  # amber
_HAND_ARM_COLOR = (160, 160, 160)
_HAND_CONNECTOR_COLOR = (255, 255, 255)

# Trend-evidence colors. Visually distinct but semantically neutral:
# a CLOSING source and a SEPARATING successor are both expected, so
# neither is styled as "good" or "bad". INSUFFICIENT keeps the
# cautionary amber and italic styling.
_TREND_CLOSING_COLOR = _HAND_LEFT_COLOR    # cyan
_TREND_SEPARATING_COLOR = _HAND_RIGHT_COLOR  # amber
_TREND_STABLE_COLOR = (200, 200, 200)
_TREND_INSUFFICIENT_COLOR = (210, 150, 60)  # cautionary amber


def _trend_color_for_label(trend_label: str) -> tuple[int, int, int]:
    if trend_label == "CLOSING":
        return _TREND_CLOSING_COLOR
    if trend_label == "SEPARATING":
        return _TREND_SEPARATING_COLOR
    if trend_label == "STABLE":
        return _TREND_STABLE_COLOR
    if trend_label.startswith("INSUFFICIENT"):
        return _TREND_INSUFFICIENT_COLOR
    return (220, 220, 220)


def _draw_hand_skeleton(frame, person) -> None:
    """Draw shoulder→elbow→wrist lines + L/R wrist markers.

    Skips keypoints that are missing rather than interpolating.
    """
    pairs = [
        (person.left_shoulder, person.left_elbow, person.left_wrist, "L",
         _HAND_LEFT_COLOR, person.left_shoulder_conf, person.left_elbow_conf,
         person.left_wrist_conf),
        (person.right_shoulder, person.right_elbow, person.right_wrist, "R",
         _HAND_RIGHT_COLOR, person.right_shoulder_conf, person.right_elbow_conf,
         person.right_wrist_conf),
    ]
    for shoulder, elbow, wrist, label, color, c_shoulder, c_elbow, c_wrist in pairs:
        # Arm segments. We only draw segments whose two endpoints are
        # both present.  This means a brief single-frame drop in any
        # keypoint does NOT visually interpolate across the gap.
        if (shoulder is not None and elbow is not None
                and c_shoulder is not None and c_elbow is not None):
            cv2.line(frame, _point(*shoulder), _point(*elbow),
                     _HAND_ARM_COLOR, 1, cv2.LINE_AA)
        if (elbow is not None and wrist is not None
                and c_elbow is not None and c_wrist is not None):
            cv2.line(frame, _point(*elbow), _point(*wrist),
                     color, 2, cv2.LINE_AA)
        if wrist is not None and c_wrist is not None:
            pt = _point(*wrist)
            cv2.circle(frame, pt, 6, color, 2, cv2.LINE_AA)
            cv2.putText(frame, label, (pt[0] + 8, pt[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def _draw_ball_to_hand_connector(frame, ball_xy, hand_xy, color
                                 ) -> None:
    """Subtle dashed line from the ball to the relevant hand."""
    if ball_xy is None or hand_xy is None:
        return
    _dashed_line(frame, _point(*ball_xy), _point(*hand_xy), color, 1)


def _format_metric(value) -> str:
    """Mirror of :func:`hand_overlay.format_hand_metric` for use in
    bake-on text overlays (the server already exposes structured values
    to the browser, but a quick in-frame text readout is also useful)."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(f):
        return "—"
    return f"{f:+.1f}"


def _format_distance(value) -> str:
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(f):
        return "—"
    return f"{f:.1f} px"


def _draw_event_hand_panel(frame, event, frame_index, hand_features) -> None:
    """Draw a compact panel in the bottom-right showing hand features.

    Trend-evidence styling is semantically neutral: cyan for CLOSING,
    amber for SEPARATING, gray for STABLE, cautionary amber for
    INSUFFICIENT. The raw numeric slope is always rendered so the
    human can see the actual measurement even when n_points is too
    small for a reliable trend class.
    """
    if hand_features is None:
        return
    width = frame.shape[1]
    panel_x = width - 360
    panel_y = max(70, frame.shape[0] - 130)
    # Translucent backdrop
    overlay = frame.copy()
    cv2.rectangle(overlay, (panel_x - 8, panel_y - 8),
                  (width - 8, frame.shape[0] - 8), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    _text(frame, "HAND FEATURES (v1A)", (panel_x, panel_y + 14),
          (255, 255, 255), 0.42)
    src = hand_features.get("source", {})
    src_nearest = src.get("nearest") or "?"
    src_color = (_HAND_LEFT_COLOR if src_nearest == "left"
                 else _HAND_RIGHT_COLOR if src_nearest == "right"
                 else (200, 200, 200))
    src_metrics = (src.get(src_nearest) if src_nearest in ("left", "right")
                   else None) or {}
    src_label = str(src_metrics.get("trend_label", "—"))
    _text(frame,
          f"PRIMARY -> {src_nearest.upper() if src_nearest != '?' else '?'}",
          (panel_x, panel_y + 32), src_color, 0.42)
    _text(frame,
          f"dist {_format_distance(src_metrics.get('distance_px'))}"
          f"   n={src_metrics.get('n_points', 0)}",
          (panel_x, panel_y + 50), (220, 220, 220), 0.36)
    _text(frame,
          f"d' {_format_metric(src_metrics.get('distance_slope_px_per_frame'))}"
          f"   {_format_metric(src_metrics.get('radial_relative_velocity'))} rad",
          (panel_x, panel_y + 66), _trend_color_for_label(src_label), 0.36)
    _text(frame, f"trend: {src_label}", (panel_x, panel_y + 82),
          _trend_color_for_label(src_label), 0.36)
    for idx, cand in enumerate(hand_features.get("candidates", []), start=1):
        cands_nearest = cand.get("nearest") or "?"
        cands_color = (_HAND_LEFT_COLOR if cands_nearest == "left"
                       else _HAND_RIGHT_COLOR if cands_nearest == "right"
                       else (200, 200, 200))
        cand_metrics = (cand.get(cands_nearest) if cands_nearest in ("left", "right")
                        else None) or {}
        cand_label = str(cand_metrics.get("trend_label", "—"))
        label = f"[{cand.get('index', idx)}] ID {cand.get('track_id')} <- {cands_nearest.upper() if cands_nearest != '?' else '?'}"
        _text(frame, label, (panel_x, panel_y + 100 + (idx - 1) * 32),
              cands_color, 0.38)
        sub = (f"d' {_format_metric(cand_metrics.get('distance_slope_px_per_frame'))}"
               f"   {_format_metric(cand_metrics.get('radial_relative_velocity'))} rad"
               f"   n={cand_metrics.get('n_points', 0)}")
        _text(frame, sub, (panel_x, panel_y + 112 + (idx - 1) * 32),
              _trend_color_for_label(cand_label), 0.32)
        _text(frame, f"trend: {cand_label}",
              (panel_x, panel_y + 124 + (idx - 1) * 32),
              _trend_color_for_label(cand_label), 0.32)


def render_clip(
    video: Path,
    output: Path,
    tracks: dict[int, Track],
    detections_by_frame: dict[int, list[dict]],
    event: ReviewEvent,
    start_frame: int,
    end_frame: int,
    fps: float,
    width: int,
    height: int,
    hands_by_frame: dict | None = None,
    hand_features: dict | None = None,
) -> None:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video}")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp = output.with_suffix(".tmp.mp4")
    writer = cv2.VideoWriter(str(tmp), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release(); writer.release()
        raise RuntimeError(f"Could not create clip: {output}")

    candidate_colors = _candidate_colors(len(event.nearby_starts))

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        for frame_index in range(start_frame, end_frame + 1):
            ok, frame = cap.read()
            if not ok:
                break
            # YOLO detections in this frame (small white dots)
            for det in detections_by_frame.get(frame_index, []):
                cv2.rectangle(
                    frame,
                    (round(det["x1"]), round(det["y1"])),
                    (round(det["x2"]), round(det["y2"])),
                    (180, 180, 180), 1, cv2.LINE_AA,
                )
            emphasized = {event.primary.track_id, *(t.track_id for t in event.nearby_starts)}
            for track_id, context_track in tracks.items():
                if track_id in emphasized:
                    continue
                current = _draw_track(frame, context_track, frame_index,
                                      (135, 135, 135), 1, 4)
                if current is not None:
                    pt = _point(current.center_x, current.center_y)
                    _text(frame, f"ID {track_id}", (pt[0] + 5, pt[1] - 5),
                          (170, 170, 170), 0.36, 1, 2)

            primary_current = _draw_track(frame, event.primary, frame_index,
                                          (255, 80, 40), 4, 7)
            if primary_current is not None:
                primary_pt = _point(primary_current.center_x, primary_current.center_y)
                primary_word = "NEW PRIMARY" if event.kind == "orphan_start" else "PRIMARY"
                _boxed_text(frame, f"{primary_word} ID {event.primary.track_id}",
                            (primary_pt[0] + 10, primary_pt[1] - 10),
                            (255, 80, 40), 0.58)
            # NEARBY CANDIDATE trails + persistent spatial labels
            for idx, cand in enumerate(event.nearby_starts, start=1):
                color = candidate_colors[idx - 1]
                candidate_current = _draw_track(frame, cand, frame_index, color, 4, 7)
                first = cand.first_observed
                if first is not None and first.frame == frame_index:
                    pt = _point(first.center_x, first.center_y)
                    cv2.drawMarker(frame, pt, color, cv2.MARKER_STAR, 22, 3)
                if candidate_current is not None:
                    candidate_pt = _point(candidate_current.center_x, candidate_current.center_y)
                    prefix = "predecessor " if event.kind == "orphan_start" else ""
                    _boxed_text(frame, f"{prefix}[{idx}] ID {cand.track_id}",
                                (candidate_pt[0] + 10,
                                 candidate_pt[1] - 10 - (idx - 1) * 22),
                                color, 0.55)
            # Hand overlay (v1B). Drawn BEFORE the header bar so the
            # header always wins z-order.
            if hands_by_frame is not None:
                persons = hands_by_frame.get(frame_index, [])
                if persons:
                    _draw_hand_skeleton(frame, persons[0])
                    if hand_features is not None:
                        src = hand_features.get("source", {})
                        anchor_xy = None
                        primary_current = next(
                            (o for o in event.primary.all_sorted
                             if o.frame == frame_index), None)
                        if primary_current is not None:
                            anchor_xy = (primary_current.center_x,
                                         primary_current.center_y)
                        nearest = src.get("nearest")
                        if nearest and anchor_xy is not None:
                            hand_xy = None
                            for person in persons:
                                hand_xy = (person.left_wrist if nearest == "left"
                                           else person.right_wrist)
                                if hand_xy is not None:
                                    break
                            color = (_HAND_LEFT_COLOR if nearest == "left"
                                     else _HAND_RIGHT_COLOR)
                            _draw_ball_to_hand_connector(
                                frame, anchor_xy, hand_xy, color)
            # Header bar
            legend_height = 31 + 22 * len(event.nearby_starts)
            cv2.rectangle(frame, (0, 0), (width, max(56, legend_height)), (20, 20, 20), -1)
            kind_label = {"end": "TRACK END",
                          "orphan_start": "ORPHAN START",
                          "existing_stitch": "EXISTING STITCH"}[event.kind]
            stitch_str = (""
                          if event.existing_rank1_stitch is None
                          else f"  RANK1 {event.existing_rank1_stitch[0]}->{event.existing_rank1_stitch[1]}")
            _text(frame,
                  f"{kind_label}  PRIMARY id={event.primary.track_id}  "
                  f"FRAME={frame_index}  candidates={len(event.nearby_starts)}"
                  f"{stitch_str}",
                  (10, 22), (255, 255, 255), 0.55)
            primary_legend = ("NEW PRIMARY" if event.kind == "orphan_start" else "PRIMARY")
            _text(frame, f"{primary_legend}: ID {event.primary.track_id}",
                  (10, 44), (255, 80, 40), 0.48)
            for idx, cand in enumerate(event.nearby_starts, start=1):
                endpoint = cand.last_observed if event.kind == "orphan_start" else cand.first_observed
                endpoint_frame = endpoint.frame if endpoint is not None else "?"
                relation_word = "predecessor" if event.kind == "orphan_start" else "future"
                _text(frame, f"{relation_word} [{idx}] ID {cand.track_id} @ frame {endpoint_frame}",
                      (180, 44 + (idx - 1) * 22), candidate_colors[idx - 1], 0.45)
            _text(frame, "OBSERVED: solid/filled   PREDICTED: dashed/hollow",
                  (width - 430, 22), (220, 220, 220), 0.40)
            if hand_features is not None:
                _draw_event_hand_panel(frame, event, frame_index,
                                       hand_features)
            writer.write(frame)
    finally:
        cap.release(); writer.release()
    # Re-encode to H.264 yuv420p with ffmpeg for browser compatibility.
    if _ffmpeg_available():
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(tmp),
                "-c:v", "libx264", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ], check=True, timeout=120)
            tmp.unlink(missing_ok=True)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
            print(f"  ffmpeg reencode failed for {output.name}: {err}; "
                  f"keeping mp4v.", file=sys.stderr)
    shutil.move(str(tmp), str(output))


# ---------- label persistence ----------

def _read_labels(path: Path) -> dict[int, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[int, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                idx = int(row.get("event_index", "-1"))
            except ValueError:
                continue
            out[idx] = row
    return out


def _labels_by_event_key(path: Path,
                         events: list[ReviewEvent]) -> dict[str, dict[str, str]]:
    """Load labels by stable identity; migrate old structural rows safely."""
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("event_key", "")
        if key:
            result[key] = row
            continue
        matches = [ev for ev in events
                   if str(ev.primary.track_id) == row.get("primary_track_id", "")
                   and str(ev.primary_end_frame) == row.get("primary_end_frame", "")]
        if len(matches) == 1:
            result[matches[0].event_key] = row
        elif row.get("event_type"):
            print("WARNING: labeled legacy row could not be matched uniquely: "
                  f"track={row.get('primary_track_id')} "
                  f"frame={row.get('primary_end_frame')}", file=sys.stderr)
    return result


def write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in LABEL_FIELDS} for row in rows)


# ---------- prepare ----------

def _candidate_colors(n: int) -> list[tuple[int, int, int]]:
    palette = [
        (220, 60, 220),   # magenta
        (60, 220, 220),   # yellow
        (60, 220, 60),    # green
        (220, 130, 60),   # teal-ish
        (60, 60, 220),    # red
        (200, 200, 60),   # cyan
        (130, 60, 220),   # violet
        (60, 180, 220),   # orange
        (220, 60, 130),   # pink
    ]
    return [palette[i % len(palette)] for i in range(n)]


def _related_frame(event: ReviewEvent, track: Track) -> int | None:
    endpoint = track.last_observed if event.kind == "orphan_start" else track.first_observed
    return endpoint.frame if endpoint is not None else None


def prepare(
    video: Path,
    tracklets_csv: Path,
    detections_csv: Path,
    stitches_csv: Path | None,
    output_dir: Path,
    labels_csv: Path,
    review_window_seconds: float = 1.0,
    orphan_lookback_seconds: float = 4.5,
    boundary_seconds: float = 0.5,
    pre_seconds: float = 1.0,
    post_seconds: float = 2.0,
    hands_csv: Path | None = None,
) -> tuple[Path, int, int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tracks = load_tracklets(tracklets_csv)
    detections_by_frame = load_detections(detections_csv)
    stitches = load_stitches(stitches_csv) if stitches_csv else {}
    fps, frames, width, height = _video_meta(video)

    events = generate_events(
        tracks, stitches, fps, frames,
        review_window_seconds=review_window_seconds,
        orphan_lookback_seconds=orphan_lookback_seconds,
        boundary_seconds=boundary_seconds,
    )
    print(f"Generated {len(events)} review events from {len(tracks)} tracks")

    # Hand overlay (v1B). Loaded once, used for both the bake-on overlay
    # and the per-event feature dict that the browser renders.
    hands_by_frame: dict | None = None
    hand_features_by_event: dict[int, dict | None] = {}
    if hands_csv is not None:
        hand_overlay_mod = _import_hand_overlay()
        hands_by_frame = hand_overlay_mod.load_hands_by_frame(hands_csv)
        if not hands_by_frame:
            print(f"WARNING: --hands {hands_csv} produced no hand rows; "
                  f"rendering without hand overlay.")
            hands_by_frame = None
        else:
            print(f"Loaded {sum(len(v) for v in hands_by_frame.values())} "
                  f"hand rows from {hands_csv}")
            for ev in events:
                try:
                    hand_features_by_event[ev.event_index] = (
                        hand_overlay_mod.event_hand_features(ev, hands_by_frame))
                except Exception as exc:  # noqa: BLE001
                    # We never want a hand-overlay bug to break clip
                    # rendering; the overlay is supplementary.
                    print(f"WARNING: hand features for event "
                          f"{ev.event_key} failed: {exc!r}", file=sys.stderr)
                    hand_features_by_event[ev.event_index] = None

    manifest_rows: list[dict[str, str]] = []
    label_rows: list[dict[str, str]] = []
    existing_labels = _labels_by_event_key(labels_csv, events)
    n_end = sum(1 for e in events if e.kind == "end")
    n_orphan = sum(1 for e in events if e.kind == "orphan_start")
    n_existing = sum(1 for e in events if e.kind == "existing_stitch")

    rendered = 0
    reused = 0
    for ev in events:
        suffix = ""
        if ev.kind == "end":
            suffix = f"end-id{ev.primary.track_id}-at-{ev.primary_end_frame}"
        elif ev.kind == "orphan_start":
            suffix = f"orphan-start-id{ev.primary.track_id}-at-{ev.primary_end_frame}"
        else:
            suffix = f"existing-id{ev.primary.track_id}"
        filename = f"v{REVIEW_RENDER_VERSION}_{ev.event_index:05d}_{_safe(suffix)}.mp4"
        clip_path = output_dir / filename
        related_frames = []
        for related in ev.nearby_starts:
            endpoint = (related.last_observed if ev.kind == "orphan_start"
                        else related.first_observed)
            if endpoint is not None:
                related_frames.append(endpoint.frame)
        anchor_frames = [ev.primary_end_frame, *related_frames]
        first = max(0, min(anchor_frames) - max(1, int(round(pre_seconds * fps))))
        last = min(frames - 1,
                   max(anchor_frames) + max(1, int(round(post_seconds * fps))))
        if not clip_path.is_file() or clip_path.stat().st_size < 1000:
            render_clip(
                video, clip_path, tracks, detections_by_frame,
                ev, first, last, fps, width, height,
                hands_by_frame=hands_by_frame,
                hand_features=hand_features_by_event.get(ev.event_index),
            )
            rendered += 1
        else:
            reused += 1
        manifest_rows.append({
            "event_index": str(ev.event_index),
            "event_key": ev.event_key,
            "kind": ev.kind,
            "relation_direction": ev.relation_direction,
            "boundary": "1" if ev.boundary else "0",
            "primary_track_id": str(ev.primary.track_id),
            "primary_first_frame": str(ev.primary.first_observed.frame
                                       if ev.primary.first_observed else ""),
            "primary_last_frame": str(ev.primary.last_observed.frame
                                      if ev.primary.last_observed else ""),
            "primary_end_frame": str(ev.primary_end_frame),
            "primary_end_x": f"{ev.primary_end_x:.2f}",
            "primary_end_y": f"{ev.primary_end_y:.2f}",
            "nearby_candidate_track_ids": ",".join(str(c.track_id) for c in ev.nearby_starts),
            "nearby_starts_first_frames": ",".join(
                str(frame) for c in ev.nearby_starts
                if (frame := _related_frame(ev, c)) is not None),
            "review_clip_path": _stored(clip_path),
            "review_clip_first_frame": str(first),
            "review_clip_last_frame": str(last),
        })

        existing = existing_labels.get(ev.event_key, {})
        label_rows.append({
            "video": _stored(video),
            "event_index": str(ev.event_index),
            "event_key": ev.event_key,
            "primary_track_id": str(ev.primary.track_id),
            "primary_end_frame": str(ev.primary_end_frame),
            "primary_end_x": f"{ev.primary_end_x:.2f}",
            "primary_end_y": f"{ev.primary_end_y:.2f}",
            "event_type": existing.get("event_type", ""),
            "hand": existing.get("hand", ""),
            "relation_direction": ev.relation_direction,
            "continuation_status": (existing.get("continuation_status", "")
                                    or _infer_cont_status(
                                        existing.get("event_type", ""),
                                        existing.get("hand", ""),
                                        existing.get("selected_continuation_track_id", ""))),
            "selected_related_track_id": (existing.get("selected_related_track_id", "")
                                           or (existing.get("selected_continuation_track_id", "")
                                               if ev.relation_direction == "successor" else "")),
            "selected_related_frame": (existing.get("selected_related_frame", "")
                                        or (existing.get("selected_continuation_start_frame", "")
                                            if ev.relation_direction == "successor" else "")),
            "selected_continuation_track_id": existing.get("selected_continuation_track_id", ""),
            "selected_continuation_start_frame": existing.get("selected_continuation_start_frame", ""),
            "nearby_candidate_track_ids": ",".join(str(c.track_id) for c in ev.nearby_starts),
            "existing_rank1_stitch_track_id": (
                "" if ev.existing_rank1_stitch is None
                else str(ev.existing_rank1_stitch[1])),
            "review_clip_path": _stored(clip_path),
            "notes": existing.get("notes", ""),
        })

    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for r in manifest_rows:
            writer.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})
    write_labels(labels_csv, label_rows)
    print(f"Prepared {len(events)} events "
          f"(rendered {rendered}, reused {reused}). "
          f"end={n_end} orphan_start={n_orphan} existing_stitch={n_existing}")
    return labels_csv, n_end, n_orphan, n_existing


# ---------- server ----------

INDEX_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Track-Lifecycle Reviewer</title>
<style>
  :root {
    --bg: #0e1116; --panel: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
    --good: #3fb950; --warn: #d29922; --bad: #f85149;
    --pending: #d29922;
  }
  html, body { margin:0; padding:0; background:var(--bg); color:var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 16px; }
  header { display:flex; align-items:baseline; justify-content:space-between; padding:8px 0 12px; border-bottom:1px solid var(--border); }
  h1 { margin: 0; font-size: 18px; }
  .event-meta { font-size: 13px; color: var(--muted); }
  .progress { font-size: 13px; color: var(--muted); }
  .stage { background: var(--panel); border:1px solid var(--border);
    border-radius: 8px; padding: 12px; margin-top: 12px; }
  video { width: 100%; background: #000; border-radius: 6px; }
  .controls { display:grid; grid-template-columns: repeat(2, 1fr);
    gap:8px 16px; margin-top:12px; font-size:13px; }
  .ctrl-group { background:#0d1117; border:1px solid var(--border);
    padding:8px 10px; border-radius: 6px; }
  .ctrl-group h3 { margin:0 0 4px; font-size: 12px; color: var(--muted);
    text-transform: uppercase; letter-spacing: .05em; }
  kbd { background:#21262d; border:1px solid var(--border); border-bottom-width:2px;
    padding: 1px 6px; border-radius: 4px; font-family: ui-monospace, monospace;
    font-size: 12px; color: var(--text); }
  .saved { color: var(--good); font-size: 13px; }
  .pending { color: var(--warn); font-size: 13px; }
  textarea { width: 100%; background: #0d1117; color: var(--text);
    border:1px solid var(--border); border-radius: 4px; padding: 6px;
    font-family: inherit; box-sizing: border-box; }
  .statusbar { display:flex; gap: 16px; flex-wrap: wrap; align-items: center;
    font-size: 13px; color: var(--muted); }
  .statusbar .pill { background:#0d1117; border:1px solid var(--border);
    padding: 2px 8px; border-radius: 10px; color: var(--text); }
  .statusbar .pill.pending { border-color: var(--pending); color: var(--pending); }
  .statusbar .pill.saved { border-color: var(--good); color: var(--good); }
  button { background:#21262d; color:var(--text); border:1px solid var(--border);
    border-radius: 4px; padding: 4px 10px; cursor:pointer; font-size: 13px; }
  button:hover { background:#30363d; }
  .legend { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .pending-panel { background:#1a1f2b; border:1px solid var(--pending);
    border-radius: 6px; padding: 10px 12px; margin-top: 10px;
    font-size: 13px; color: var(--pending); display:none; }
  .pending-panel.active { display:block; }
  .pending-panel h3 { margin:0 0 6px; font-size: 12px; color: var(--pending);
    text-transform: uppercase; letter-spacing: .05em; }
  .pending-panel .cand-map { font-family: ui-monospace, monospace; font-size: 12px;
    color: var(--text); white-space: pre-wrap; line-height: 1.5; }
  .saved-readout { background:#0d1117; border:1px solid var(--border);
    border-radius: 6px; padding: 10px 12px; margin-top: 10px;
    font-size: 13px; color: var(--good); display:none; }
  .saved-readout.active { display:block; }
  .saved-readout h3 { margin:0 0 6px; font-size: 12px; color: var(--good);
    text-transform: uppercase; letter-spacing: .05em; }
  .statusbar .pill.boundary { background:#3a2400; border-color: var(--warn);
    color: var(--warn); font-weight: 600; }
  .boundary-banner { background:#3a2400; border:1px solid var(--warn);
    color: var(--warn); border-radius: 6px; padding: 10px 12px;
    margin-top: 10px; font-size: 13px; }
  .boundary-banner kbd { background:#21262d; border:1px solid var(--warn);
    color: var(--warn); }
  .hand-panel { background:#0d1117; border:1px solid var(--border);
    border-radius: 6px; padding: 10px 12px; margin-top: 10px; font-size: 13px; }
  .hand-panel h3 { margin:0 0 6px; font-size: 12px; color: var(--accent);
    text-transform: uppercase; letter-spacing: .05em; }
  .hand-panel .hand-source, .hand-panel .hand-candidates { margin: 4px 0; }
  .hand-panel .hand-row { display: grid;
    grid-template-columns: 200px 80px 110px 110px 80px;
    gap: 6px 10px; align-items: baseline; font-family: ui-monospace, monospace;
    font-size: 12px; padding: 2px 0; }
  .hand-panel .hand-row.header { color: var(--muted); font-size: 11px;
    text-transform: uppercase; letter-spacing: .05em; }
  /* CLOSING / SEPARATING are visually distinct but semantically
     neutral — neither should imply "good" or "bad" because a CLOSING
     source and a SEPARATING successor are both expected. INSUFFICIENT
     keeps the cautionary amber and italic styling. */
  .hand-panel .hand-row .closing { color: #5ac8ff; }
  .hand-panel .hand-row .separating { color: #ffc85a; }
  .hand-panel .hand-row .stable { color: #c8c8c8; }
  .hand-panel .hand-row .insufficient { color: var(--warn); font-style: italic; }
  .hand-panel .hand-legend { color: var(--muted); font-size: 11px;
    margin-top: 6px; line-height: 1.4; }
  .hand-panel .hand-legend code { color: var(--text); background:#21262d;
    padding: 1px 4px; border-radius: 3px; }
</style>
</head><body>
<div class="wrap">
  <header>
    <div>
      <h1>Track-Lifecycle Reviewer</h1>
      <div class="event-meta" id="event-meta">loading...</div>
    </div>
    <div class="progress" id="progress"></div>
  </header>

  <div class="stage">
    <video id="clip" autoplay muted loop playsinline></video>
    <div class="statusbar" style="margin-top:8px;">
      <span class="pill" id="kind-pill">kind: -</span>
      <span class="pill" id="primary-pill">primary: -</span>
      <span class="pill" id="stitch-pill">stitcher: -</span>
      <span class="pill" id="mode-pill">mode: viewing</span>
      <span class="pill" id="saved-pill">label: blank</span>
      <span class="pill boundary" id="boundary-pill" style="display:none;">BOUNDARY</span>
    </div>
    <div class="boundary-banner" id="boundary-banner" style="display:none;">
      <strong>BOUNDARY EVENT</strong> &mdash; this event is at the start or
      end of the source video. The visible clip window may not show enough
      context to classify it as a normal track failure. Consider pressing
      <kbd>e</kbd> (true end) for events already present at frame 0, or
      use <kbd>u</kbd> (unclear) if the visible window is too short.
    </div>
    <div class="pending-panel" id="pending-panel">
      <h3>Pending classification (not yet saved)</h3>
      <div id="pending-event-type">event type: -</div>
      <div id="pending-hand">hand: -</div>
      <div id="pending-continuation">continuation: -</div>
      <div class="cand-map" id="cand-map"></div>
    </div>
    <div class="saved-readout" id="saved-readout">
      <h3>Saved label</h3>
      <div id="saved-content"></div>
    </div>
    <div class="hand-panel" id="hand-panel" style="display:none;">
      <h3>Hand features (v1A)</h3>
      <div id="hand-source"></div>
      <div class="hand-candidates" id="hand-candidates"></div>
      <div class="hand-legend">
        L = anatomical left wrist, R = anatomical right wrist
        (anatomical, not screen position). d' is the least-squares
        slope of ball-to-hand distance over the last/first observed
        ball points. Negative = CLOSING, positive = SEPARATING, near
        zero = STABLE. <code>radial</code> is the radial component of
        (v_ball &minus; v_hand) along the unit hand-to-ball vector.
        Trend classes require <code>n_points &gt;= 3</code>; with fewer
        points the row is marked <code>INSUFFICIENT (n=N)</code> and
        the raw numeric slope is still shown for diagnostics. CLOSING
        vs SEPARATING styling is visually distinct but
        semantically neutral &mdash; neither implies good or bad.
        Missing values are <code>—</code>, never zero.
      </div>
    </div>
  </div>

  <div class="stage">
    <div class="controls">
      <div class="ctrl-group">
        <h3>Playback (viewing)</h3>
        <kbd>space</kbd> pause / play &nbsp;
        <kbd>r</kbd> restart &nbsp;
        <kbd>&larr;</kbd> / <kbd>&rarr;</kbd> seek 1 s &nbsp;
        <kbd>-</kbd> / <kbd>=</kbd> slower / faster
        <br>
        <label for="speed-select">Speed:</label>
        <select id="speed-select" aria-label="Playback speed">
          <option value="0.25">0.25x</option>
          <option value="0.5">0.5x</option>
          <option value="0.75">0.75x</option>
          <option value="1" selected>1.0x</option>
          <option value="1.5">1.5x</option>
          <option value="2">2.0x</option>
        </select>
        <span id="speed-display">Speed: 1.0x</span>
      </div>
      <div class="ctrl-group">
        <h3>Event type (viewing)</h3>
        <kbd>h</kbd> hand-mediated &nbsp;
        <kbd>a</kbd> airborne break &nbsp;
        <kbd>n</kbd> norfair fail &nbsp;
        <kbd>x</kbd> id switch &nbsp;
        <kbd>e</kbd> true end &nbsp;
        <kbd>f</kbd> false-positive track &nbsp;
        <kbd>u</kbd> unclear &nbsp;
        <kbd>s</kbd> skip
      </div>
      <div class="ctrl-group">
        <h3>Hand (after h)</h3>
        <kbd>l</kbd> left &nbsp;
        <kbd>r</kbd> right &nbsp;
        <kbd>u</kbd> unknown
      </div>
      <div class="ctrl-group">
        <h3>Continuation (after h / a / n / x)</h3>
        <kbd>1</kbd>..<kbd>9</kbd> pick numbered nearby id &nbsp;
        <kbd>0</kbd> no continuation &nbsp;
        <kbd>?</kbd> ambiguous continuation
      </div>
      <div class="ctrl-group">
        <h3>Cancel / Navigation</h3>
        <kbd>Esc</kbd> cancel pending &nbsp;
        <kbd>p</kbd> previous event &nbsp;
        <kbd>]</kbd> next event &nbsp;
        <kbd>q</kbd> quit safely
        <br>
        <button id="next-btn">next (])</button>
        <button id="prev-btn">previous (p)</button>
        <button id="quit-btn">quit (q)</button>
      </div>
    </div>
  </div>

  <div class="stage">
    <h3 style="margin: 0 0 8px; font-size: 13px; color: var(--muted);
      text-transform: uppercase; letter-spacing: .05em;">Notes</h3>
    <textarea id="notes" rows="3" placeholder="free-form notes (optional)"></textarea>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const clip = $('clip');

// Explicit browser-side review state machine.
// mode: "viewing" | "choosing_hand" | "choosing_continuation"
// pendingEventType: single-letter event type code or null
// pendingHand: "left" | "right" | "unknown" | null
const state = {
  index: 0, total: 0, saved: 0,
  mode: 'viewing',
  pendingEventType: null,
  pendingHand: null,
  playbackRate: 1.0,
};
let currentEvent = null;
const PLAYBACK_RATES = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0];

const EVENT_TYPE_LABELS = {
  h: 'HAND-MEDIATED',
  a: 'AIRBORNE BREAK',
  n: 'NORFAIR ASSOCIATION FAILURE',
  x: 'ID SWITCH / WRONG MERGE',
  e: 'TRUE END',
  f: 'FALSE-POSITIVE TRACK',
  u: 'UNCLEAR / AMBIGUOUS',
  s: 'SKIP',
};
const REQUIRES_HAND = new Set(['h']);
const REQUIRES_CONTINUATION = new Set(['h', 'a', 'n', 'x']);

function resetPending() {
  state.mode = 'viewing';
  state.pendingEventType = null;
  state.pendingHand = null;
  renderPending();
}

async function fetchState() {
  const r = await fetch('/api/state');
  const s = await r.json();
  state.index = s.index; state.total = s.total; state.saved = s.saved;
  return s;
}

async function fetchEvent(i) {
  const r = await fetch('/api/event?index=' + i);
  if (!r.ok) return null;
  return await r.json();
}

async function postLabel(payload) {
  const response = await fetch('/api/label', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  return await response.json();
}

async function setIndex(i) {
  const ev = await fetchEvent(i);
  if (!ev) return;
  currentEvent = ev;
  resetPending();
  clip.src = '/clip?path=' + encodeURIComponent(ev.review_clip_path);
  clip.playbackRate = state.playbackRate;
  clip.loop = true;
  clip.play().catch(() => {});
  $('event-meta').textContent =
    `EVENT ${ev.event_index + 1}/${state.total}   ` +
    `${ev.kind_label}   PRIMARY id=${ev.primary_track_id} ` +
    `@ frame ${ev.primary_end_frame}`;
  $('progress').textContent = `${state.saved}/${state.total} saved`;
  $('kind-pill').textContent = `kind: ${ev.kind_label}`;
  $('primary-pill').textContent =
    `primary id=${ev.primary_track_id} @ ${ev.primary_end_frame}`;
  $('stitch-pill').textContent = ev.existing_rank1_stitch_track_id
    ? `stitcher: rank1 ${ev.existing_rank1_stitch_source}->${ev.existing_rank1_stitch_track_id}`
    : 'stitcher: NONE';
  $('saved-pill').textContent = ev.saved_label
    ? `label: ${EVENT_TYPE_LABELS[ev.saved_label] || ev.saved_label}`
    : 'label: blank';
  const bp = $('boundary-pill');
  const bb = $('boundary-banner');
  if (ev.boundary) {
    bp.style.display = 'inline-block';
    bb.style.display = 'block';
  } else {
    bp.style.display = 'none';
    bb.style.display = 'none';
  }
  $('notes').value = ev.saved_notes || '';
  // Saved readout
  const sr = $('saved-readout'); const sc = $('saved-content');
  if (ev.saved_label) {
    const lines = [];
    lines.push(EVENT_TYPE_LABELS[ev.saved_label] || ev.saved_label);
    if (ev.saved_hand) lines.push(`hand: ${ev.saved_hand}`);
    if (ev.saved_continuation_choice) lines.push(ev.saved_continuation_choice);
    sc.innerHTML = lines.map(l => `<div>${l}</div>`).join('');
    sr.classList.add('active');
  } else {
    sr.classList.remove('active');
  }
  document.title = `Reviewer ${ev.event_index + 1}/${state.total}`;
  renderPending();
  renderHandPanel(ev);
}

function fmtSigned(value) {
  if (value === null || value === undefined) return '—';
  const f = Number(value);
  if (!Number.isFinite(f)) return '—';
  return (f >= 0 ? '+' : '') + f.toFixed(1);
}
function fmtUnsigned(value, suffix) {
  if (value === null || value === undefined) return '—';
  const f = Number(value);
  if (!Number.isFinite(f)) return '—';
  return f.toFixed(1) + (suffix || '');
}
function trendClass(slope, nPoints) {
  // Semantically neutral: cyan for CLOSING, amber for SEPARATING, gray
  // for STABLE. The combined INSUFFICIENT/CLOSING/SEPARATING/label
  // decision lives in trendLabel() so the colour class can never
  // disagree with the label.
  if (slope === null || slope === undefined) return '';
  const f = Number(slope);
  if (!Number.isFinite(f)) return '';
  if (nPoints !== undefined && Number(nPoints) < 3) return 'insufficient';
  if (f < -0.5) return 'closing';
  if (f > 0.5) return 'separating';
  return 'stable';
}
function trendLabel(slope, nPoints) {
  if (slope === null || slope === undefined) return '—';
  const f = Number(slope);
  if (!Number.isFinite(f)) return '—';
  if (nPoints !== undefined && Number(nPoints) < 3) {
    return `INSUFFICIENT (n=${Number(nPoints)})`;
  }
  if (f < -0.5) return 'CLOSING';
  if (f > 0.5) return 'SEPARATING';
  return 'STABLE';
}

function renderHandPanel(ev) {
  const panel = $('hand-panel');
  if (!ev.hand_features) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  const src = ev.hand_features.source || {};
  const srcNearest = src.nearest || '?';
  const srcMetrics = (srcNearest === 'left' || srcNearest === 'right')
    ? (src[srcNearest] || {}) : {};
  const nPts = srcMetrics.n_points || 0;
  const srcRow = (kind) => {
    const cls = trendClass(srcMetrics.distance_slope_px_per_frame, nPts);
    const label = trendLabel(srcMetrics.distance_slope_px_per_frame, nPts);
    const arrow = srcNearest === 'left' ? '→ L' : srcNearest === 'right' ? '→ R' : '→ ?';
    return `<div class="hand-row ${cls}">
      <span><b>PRIMARY</b> id=${ev.primary_track_id} ${arrow}</span>
      <span>${fmtUnsigned(srcMetrics.distance_px, ' px')}</span>
      <span>d' ${fmtSigned(srcMetrics.distance_slope_px_per_frame)}</span>
      <span>radial ${fmtSigned(srcMetrics.radial_relative_velocity)}</span>
      <span>${label} (n=${nPts})</span>
    </div>`;
  };
  $('hand-source').innerHTML = `
    <div class="hand-row header">
      <span>PRIMARY → nearest hand</span>
      <span>distance</span>
      <span>slope d'</span>
      <span>radial v</span>
      <span>trend (n)</span>
    </div>
    ${srcRow('primary')}`;

  const cands = ev.hand_features.candidates || [];
  let candHTML = '';
  if (cands.length) {
    candHTML += `<div class="hand-row header" style="margin-top:8px;">
      <span>${ev.kind === 'orphan_start' ? 'predecessor candidates' : 'successor candidates'}</span>
      <span>distance</span>
      <span>slope d'</span>
      <span>radial v</span>
      <span>trend (n)</span>
    </div>`;
    for (const c of cands) {
      const cn = c.nearest || '?';
      const cm = (cn === 'left' || cn === 'right') ? (c[cn] || {}) : {};
      const cn_pts = cm.n_points || 0;
      const cls = trendClass(cm.distance_slope_px_per_frame, cn_pts);
      const label = trendLabel(cm.distance_slope_px_per_frame, cn_pts);
      const arrow = cn === 'left' ? '← L' : cn === 'right' ? '← R' : '← ?';
      candHTML += `<div class="hand-row ${cls}">
        <span><b>[${c.index}]</b> ID ${c.track_id} ${arrow}</span>
        <span>${fmtUnsigned(cm.distance_px, ' px')}</span>
        <span>d' ${fmtSigned(cm.distance_slope_px_per_frame)}</span>
        <span>radial ${fmtSigned(cm.radial_relative_velocity)}</span>
        <span>${label} (n=${cn_pts})</span>
      </div>`;
    }
  } else {
    candHTML = `<div class="hand-row"><span>(no candidates)</span></div>`;
  }
  $('hand-candidates').innerHTML = candHTML;
}

function renderPending() {
  $('mode-pill').textContent = `mode: ${state.mode}`;
  const pp = $('pending-panel');
  const ev = currentEvent;
  const nearby = ev ? ev.nearby_candidate_track_ids : [];
  const starts = ev ? ev.nearby_starts_first_frames : [];
  if (state.mode === 'viewing' && !state.pendingEventType) {
    pp.classList.remove('active');
    return;
  }
  pp.classList.add('active');
  $('pending-event-type').textContent = state.pendingEventType
    ? `event type: ${EVENT_TYPE_LABELS[state.pendingEventType]}`
    : 'event type: - (choose an event type to begin)';
  const needsHand = state.pendingEventType && REQUIRES_HAND.has(state.pendingEventType);
  $('pending-hand').textContent = needsHand
    ? (state.pendingHand
        ? `hand: ${state.pendingHand}`
        : 'hand: waiting — press L / R / U')
    : 'hand: not applicable';
  const needsCont = state.pendingEventType
    && REQUIRES_CONTINUATION.has(state.pendingEventType)
    && (needsHand ? state.pendingHand !== null : true);
  const relationWord = currentEvent?.relation_direction === 'predecessor'
    ? 'predecessor' : 'continuation';
  $('pending-continuation').textContent = needsCont
    ? `${relationWord}: waiting — press 1..9 / 0 / ?`
    : (state.pendingEventType === 'e' || state.pendingEventType === 'f'
        ? 'continuation: not applicable (event type ends here)'
        : 'continuation: not required for this event type');
  // Candidate map
  if (needsCont && nearby.length) {
    const lines = nearby.map((id, i) =>
      `  ${i + 1} -> ID ${id} @ frame ${starts[i] ?? '?'}`);
    lines.unshift(currentEvent?.relation_direction === 'predecessor'
      ? 'possible predecessors:' : 'future candidates:');
    $('cand-map').textContent = lines.join('\\n');
  } else {
    $('cand-map').textContent = '';
  }
}

function updatePlaybackRate(rate) {
  const clamped = Math.max(PLAYBACK_RATES[0],
                          Math.min(PLAYBACK_RATES[PLAYBACK_RATES.length - 1], rate));
  const nearest = PLAYBACK_RATES.reduce((best, candidate) =>
    Math.abs(candidate - clamped) < Math.abs(best - clamped) ? candidate : best);
  state.playbackRate = nearest;
  clip.playbackRate = state.playbackRate;
  const selector = $('speed-select');
  if (selector) selector.value = String(state.playbackRate);
  const display = $('speed-display');
  if (display) display.textContent = `Speed: ${state.playbackRate}x`;
}

function adjustPlaybackRate(direction) {
  const currentIndex = PLAYBACK_RATES.indexOf(state.playbackRate);
  const index = currentIndex < 0 ? PLAYBACK_RATES.indexOf(1.0) : currentIndex;
  const nextIndex = direction === 'slower' ? index - 1 : index + 1;
  updatePlaybackRate(PLAYBACK_RATES[Math.max(0, Math.min(PLAYBACK_RATES.length - 1, nextIndex))]);
}

async function saveAndAdvance(payload) {
  if (!currentEvent) return;
  const result = await postLabel({
    event_index: currentEvent.event_index,
    ...payload,
    notes: $('notes').value,
  });
  resetPending();
  await fetchState();
  state.index = Number.isInteger(result.next_index) ? result.next_index : state.index;
  await setIndex(state.index);
}

async function commitSelection(contStatus, contTrackId, contStartFrame) {
  if (!currentEvent || !state.pendingEventType) return;
  // For event types that do NOT require continuation, the user still
  // gets to choose one (per task spec) but we don't block on it.
  const payload = {
    event_type: state.pendingEventType,
    hand: state.pendingHand || '',
    continuation_status: contStatus,
    selected_related_track_id: contTrackId || '',
    selected_related_frame: contStartFrame || '',
    selected_continuation_track_id: contTrackId || '',
    selected_continuation_start_frame: contStartFrame || '',
  };
  await saveAndAdvance(payload);
}

async function commitDirect(eventType) {
  // Used for e/f/u which don't require continuation.
  if (!currentEvent) return;
  const payload = {
    event_type: eventType,
    hand: '',
    continuation_status: 'not_applicable',
    selected_continuation_track_id: '',
    selected_continuation_start_frame: '',
  };
  await saveAndAdvance(payload);
}

async function loadCurrent() {
  const s = await fetchState();
  await setIndex(s.index);
}

document.addEventListener('keydown', async (e) => {
  if (e.target && e.target.tagName === 'TEXTAREA') return;
  if (e.target && e.target.tagName === 'INPUT') return;
  const key = e.key;

  // Playback speed is independent of review classification state.
  if (key === '-' || key === '=') {
    e.preventDefault();
    adjustPlaybackRate(key === '-' ? 'slower' : 'faster');
    return;
  }

  // Mode-routing key handling. Each mode only responds to its keys.
  if (state.mode === 'choosing_hand') {
    // Hand selection mode: l/r/u complete the hand; Escape cancels.
    if (key === 'Escape' || key === 'Esc') {
      e.preventDefault();
      resetPending();
      return;
    }
    if (key === 'l' || key === 'r' || key === 'u') {
      e.preventDefault();
      state.pendingHand = ({l: 'left', r: 'right', u: 'unknown'})[key];
      state.mode = 'choosing_continuation';
      renderPending();
      return;
    }
    // Otherwise ignore.
    return;
  }

  if (state.mode === 'choosing_continuation') {
    // Continuation selection mode: 1..9 / 0 / ? complete the record;
    // Escape cancels.
    if (key === 'Escape' || key === 'Esc') {
      e.preventDefault();
      resetPending();
      return;
    }
    const ev = currentEvent;
    if (!ev) return;
    if (/^[1-9]$/.test(key)) {
      e.preventDefault();
      const idx = parseInt(key, 10) - 1;
      const tids = ev.nearby_candidate_track_ids || [];
      const starts = ev.nearby_starts_first_frames || [];
      if (idx >= 0 && idx < tids.length) {
        await commitSelection('selected', String(tids[idx]), String(starts[idx] ?? ''));
      } else {
        // Out of range: treat as ambiguous for safety.
        await commitSelection('ambiguous', '', '');
      }
      return;
    }
    if (key === '0') {
      e.preventDefault();
      await commitSelection('none', '', '');
      return;
    }
    if (key === '?') {
      e.preventDefault();
      await commitSelection('ambiguous', '', '');
      return;
    }
    // Other keys ignored while choosing continuation.
    return;
  }

  // state.mode === 'viewing'
  // Playback shortcuts (viewing mode only — they don't apply once we
  // start a multi-step classification).
  if (key === ' ') {
    e.preventDefault();
    if (clip.paused) clip.play(); else clip.pause();
    return;
  }
  if (key === 'r' || key === 'R') {
    clip.currentTime = 0;
    return;
  }
  if (key === 'ArrowLeft') {
    clip.currentTime = Math.max(0, clip.currentTime - 1);
    return;
  }
  if (key === 'ArrowRight') {
    clip.currentTime = Math.min(clip.duration || 0, clip.currentTime + 1);
    return;
  }

  // Skip (advances without saving)
  if (key === 's' || key === 'S') {
    e.preventDefault();
    await fetch('/api/next', {method: 'POST'});
    await loadCurrent();
    return;
  }

  // Navigation
  if (key === 'p' || key === 'P') {
    e.preventDefault();
    await fetch('/api/prev', {method: 'POST'});
    await loadCurrent();
    return;
  }
  if (key === ']') {
    e.preventDefault();
    await fetch('/api/next', {method: 'POST'});
    await loadCurrent();
    return;
  }
  if (key === 'q' || key === 'Q') {
    e.preventDefault();
    await fetch('/api/quit', {method: 'POST'});
    return;
  }

  // Event type selection (viewing mode only).
  // e and f save immediately (no continuation, no hand).
  if (key === 'e') { e.preventDefault(); await commitDirect('e'); return; }
  if (key === 'f') { e.preventDefault(); await commitDirect('f'); return; }
  // u: from viewing mode, save as unclear with continuation=none.
  if (key === 'u') { e.preventDefault(); await commitDirect('u'); return; }
  // h / a / n / x: enter multi-step classification.
  if (key === 'h' || key === 'a' || key === 'n' || key === 'x') {
    e.preventDefault();
    state.pendingEventType = key;
    state.mode = REQUIRES_HAND.has(key) ? 'choosing_hand' : 'choosing_continuation';
    renderPending();
    return;
  }
});

const nextButton = $('next-btn');
if (nextButton) nextButton.addEventListener('click', async () => {
 await fetch('/api/next', {method: 'POST'}); await loadCurrent();
});
const prevButton = $('prev-btn');
if (prevButton) prevButton.addEventListener('click', async () => {
 await fetch('/api/prev', {method: 'POST'}); await loadCurrent();
});
const quitButton = $('quit-btn');
if (quitButton) quitButton.addEventListener('click', async () => {
 await fetch('/api/quit', {method: 'POST'});
});

const speedSelect = $('speed-select');
if (speedSelect) speedSelect.addEventListener('change', () => {
  updatePlaybackRate(parseFloat(speedSelect.value));
});

(async () => { await loadCurrent(); })();
</script>
</body></html>
"""


def _infer_cont_status(event_type: str, hand: str, track_id: str) -> str:
    """Backward-compat: if a CSV row pre-dates the continuation_status
    field, infer what its value would be."""
    if event_type in ("e", "f"):
        return "not_applicable"
    if track_id:
        return "selected"
    return "none"


def _format_cont_choice(event_type: str, hand: str, cont_status: str,
                         track_id: str, start_frame: str) -> str:
    """Human-readable summary of the saved continuation choice."""
    if not event_type:
        return ""
    if cont_status == "not_applicable" or event_type in ("e", "f"):
        return "no continuation applicable"
    if cont_status == "selected":
        return (f"continuation → ID {track_id} @ frame {start_frame}" if track_id
                else "continuation selected but ID missing")
    if cont_status == "ambiguous":
        return "continuation ambiguous"
    if cont_status == "none":
        return "no continuation chosen"
    return ""


def _validate_continuation(idx: int, payload: dict,
                           events: list[dict]) -> tuple[str, str, str]:
    """Validate the continuation fields against the event's manifest.

    Returns (continuation_status, track_id, start_frame) to persist.
    continuation_status is always one of {selected, none, ambiguous,
    not_applicable}. When 'selected', the supplied track_id and start
    frame must match the manifest's nearby candidates.
    """
    raw_status = (payload.get("continuation_status", "") or "").strip()
    raw_track = (payload.get("selected_related_track_id", "")
                 or payload.get("selected_continuation_track_id", "") or "").strip()
    raw_frame = (payload.get("selected_related_frame", "")
                 or payload.get("selected_continuation_start_frame", "") or "").strip()
    event_type = (payload.get("event_type", "") or "").strip()
    if event_type in ("e", "f"):
        return ("not_applicable", "", "")
    allowed = {"selected", "none", "ambiguous", "not_applicable"}
    status = raw_status if raw_status in allowed else "none"
    if status != "selected":
        return (status, "", "")
    if not (0 <= idx < len(events)):
        return ("none", "", "")
    nearby_str = events[idx].get("nearby_candidate_track_ids", "") or ""
    nearby = [int(x) for x in nearby_str.split(",") if x]
    starts_str = events[idx].get("nearby_starts_first_frames", "") or ""
    starts = [int(x) for x in starts_str.split(",") if x]
    if not raw_track:
        return ("none", "", "")
    try:
        track_id = int(raw_track)
    except ValueError:
        return ("none", "", "")
    if track_id not in nearby:
        return ("none", "", "")
    try:
        start_frame = int(raw_frame)
    except ValueError:
        start_frame = starts[nearby.index(track_id)] if nearby else 0
    expected_start = starts[nearby.index(track_id)] if nearby else 0
    if expected_start and start_frame != expected_start:
        start_frame = expected_start
    return ("selected", str(track_id), str(start_frame))


class _State:
    def __init__(self, events_path: Path, labels_path: Path,
                 clip_root: Path, port: int, host: str, url: str,
                 tracks: dict | None = None,
                 hands_by_frame: dict | None = None):
        self.events_path = events_path
        self.labels_path = labels_path
        self.clip_root = clip_root.resolve()
        self.port = port
        self.host = host
        self.url = url
        self.events: list[dict] = []
        self.labels: dict[int, dict[str, str]] = {}
        self.index: int = 0
        self._lock = threading.Lock()
        self._tracks = tracks
        self._hands_by_frame = hands_by_frame
        self._hand_overlay_mod = (_import_hand_overlay()
                                  if hands_by_frame is not None else None)
        self._reload()
        # Skip already-saved labels so resume picks the first unsaved row.
        for i in range(len(self.events)):
            if not self.labels.get(i, {}).get("event_type"):
                self.index = i
                break
        else:
            self.index = max(0, len(self.events) - 1)

    def _reload(self):
        if self.events_path.is_file():
            with self.events_path.open(newline="", encoding="utf-8") as f:
                self.events = list(csv.DictReader(f))
        else:
            self.events = []
        self.labels = _read_labels(self.labels_path)

    def to_public_event(self, i: int) -> dict | None:
        with self._lock:
            self._reload()
            if not (0 <= i < len(self.events)):
                return None
            row = self.events[i]
            label_row = self.labels.get(i, {})
            nearby = [int(x) for x in row.get("nearby_candidate_track_ids", "").split(",") if x]
            starts = [int(x) for x in row.get("nearby_starts_first_frames", "").split(",") if x]
            rank1_dst = row.get("existing_rank1_stitch_track_id", "")
            existing = label_row.get("event_type", "")
            hand = label_row.get("hand", "")
            relation = row.get("relation_direction", "successor")
            saved_track = (label_row.get("selected_related_track_id", "")
                           or label_row.get("selected_continuation_track_id", ""))
            saved_frame = (label_row.get("selected_related_frame", "")
                           or label_row.get("selected_continuation_start_frame", ""))
            cont_status = label_row.get("continuation_status", "") or _infer_cont_status(
                existing, hand, saved_track)
            notes = label_row.get("notes", "")
            cont_choice = _format_cont_choice(
                existing, hand, cont_status,
                saved_track, saved_frame)
            if relation == "predecessor":
                cont_choice = cont_choice.replace("continuation", "predecessor")
            kind_label = {"end": "TRACK END",
                          "orphan_start": "ORPHAN START",
                          "existing_stitch": "EXISTING STITCH"}.get(row.get("kind", ""), row.get("kind", ""))
            boundary = row.get("boundary", "0") == "1"
            hand_features: dict | None = None
            if (self._tracks is not None
                    and self._hands_by_frame is not None
                    and self._hand_overlay_mod is not None):
                hand_features = self._build_hand_features(
                    row, self._tracks, self._hands_by_frame,
                    self._hand_overlay_mod)
        return {
            "event_index": i,
            "event_key": row.get("event_key", ""),
            "kind": row.get("kind", ""),
            "kind_label": kind_label,
            "relation_direction": relation,
            "boundary": boundary,
            "primary_track_id": int(row.get("primary_track_id", "0")),
            "primary_end_frame": int(row.get("primary_end_frame", "0") or 0),
            "nearby_candidate_track_ids": nearby,
            "nearby_starts_first_frames": starts,
            "existing_rank1_stitch_track_id": rank1_dst,
            "existing_rank1_stitch_source": (row.get("primary_track_id", "") if rank1_dst else ""),
            "review_clip_path": row.get("review_clip_path", ""),
            "saved_label": existing,
            "saved_hand": hand,
            "saved_continuation_status": cont_status,
            "saved_continuation_choice": cont_choice,
            "saved_notes": notes,
            "hand_features": hand_features,
        }

    @staticmethod
    def _build_hand_features(row, tracks, hands, hand_overlay_mod) -> dict | None:
        """Build the per-event hand-features dict for the browser."""
        try:
            primary_id = int(row.get("primary_track_id", "0") or 0)
        except ValueError:
            return None
        primary_track = tracks.get(primary_id)
        if primary_track is None:
            return None
        nearby_ids = [int(x) for x in row.get("nearby_candidate_track_ids", "").split(",") if x]
        candidate_tracks = [tracks.get(tid) for tid in nearby_ids]
        candidate_tracks = [c for c in candidate_tracks if c is not None]
        # Build a ReviewEvent-shaped object the hand_overlay module
        # understands. The fields it reads are: primary, nearby_starts, kind.
        synthetic = type("R", (), {})()
        synthetic.primary = primary_track
        synthetic.nearby_starts = candidate_tracks
        synthetic.kind = row.get("kind", "end")
        return hand_overlay_mod.event_hand_features(synthetic, hands)

    def save_label(self, payload: dict) -> int:
        idx = int(payload["event_index"])
        with self._lock:
            self._reload()
            if not (0 <= idx < len(self.events)):
                return self.index
            event_type = payload.get("event_type", "") or ""
            hand = payload.get("hand", "") or ""
            cont_status, track_id, start_frame = _validate_continuation(
                idx, payload, self.events)
            label_row = self.labels.get(idx, {})
            label_row["event_type"] = event_type
            label_row["hand"] = hand
            label_row["continuation_status"] = cont_status
            relation = self.events[idx].get("relation_direction", "successor")
            label_row["event_key"] = self.events[idx].get("event_key", "")
            label_row["relation_direction"] = relation
            label_row["selected_related_track_id"] = track_id
            label_row["selected_related_frame"] = start_frame
            label_row["selected_continuation_track_id"] = track_id if relation == "successor" else ""
            label_row["selected_continuation_start_frame"] = start_frame if relation == "successor" else ""
            label_row["notes"] = payload.get("notes", "") or ""
            self.labels[idx] = label_row
            # Persist as a single CSV with one row per event_index, joined
            # to event structural fields from the manifest.
            self.labels_path.parent.mkdir(parents=True, exist_ok=True)
            with self.labels_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
                writer.writeheader()
                for i, ev in enumerate(self.events):
                    base = {
                        "video": ev.get("video", ""),
                        "event_index": str(i),
                        "event_key": ev.get("event_key", ""),
                        "primary_track_id": ev.get("primary_track_id", ""),
                        "primary_end_frame": ev.get("primary_end_frame", ""),
                        "primary_end_x": ev.get("primary_end_x", ""),
                        "primary_end_y": ev.get("primary_end_y", ""),
                        "nearby_candidate_track_ids": ev.get("nearby_candidate_track_ids", ""),
                        "relation_direction": ev.get("relation_direction", "successor"),
                        "existing_rank1_stitch_track_id": ev.get("existing_rank1_stitch_track_id", ""),
                        "review_clip_path": ev.get("review_clip_path", ""),
                    }
                    lr = self.labels.get(i, {})
                    base.update({k: lr.get(k, "") for k in (
                        "event_type", "hand", "relation_direction", "continuation_status",
                        "selected_related_track_id", "selected_related_frame",
                        "selected_continuation_track_id",
                        "selected_continuation_start_frame",
                        "notes",
                    )})
                    row: dict[str, str] = {k: str(base.get(k, "")) for k in LABEL_FIELDS}
                    writer.writerow(row)  # type: ignore[arg-type]
            self.index = self.next_unfinished_after(idx, reload=False)
            return self.index

    def next_unfinished_after(self, completed_index: int,
                              reload: bool = True) -> int:
        if reload:
            self._reload()
        count = len(self.events)
        for offset in range(1, count + 1):
            candidate = (completed_index + offset) % count
            if not self.labels.get(candidate, {}).get("event_type"):
                return candidate
        return completed_index

    def next_unsaved(self) -> int:
        with self._lock:
            self._reload()
            for i in range(len(self.events)):
                if not self.labels.get(i, {}).get("event_type"):
                    return i
            return max(0, len(self.events) - 1)

    def next_index(self) -> int:
        with self._lock:
            i = min(self.index + 1, max(0, len(self.events) - 1))
            self.index = i
        return i

    def prev_index(self) -> int:
        with self._lock:
            i = max(self.index - 1, 0)
            self.index = i
        return i


class ReviewerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "TrackReviewer/1.0"
    state: _State = None  # type: ignore

    def log_message(self, format: str, *args) -> None:  # silence stderr noise
        return

    def _json(self, obj, status: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe_path(self, value: str) -> Path | None:
        path = _resolve_stored(value).resolve()
        root = self.state.clip_root.resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if not path.is_file():
            return None
        return path

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = INDEX_HTML.encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/clip?"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            value = q.get("path", [""])[0]
            path = self._safe_path(value)
            if path is None:
                self.send_response(404); self.end_headers(); return
            file_size = path.stat().st_size
            range_header = self.headers.get("Range", "")
            start, end = 0, file_size - 1
            status = 200
            if range_header:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
                if not match:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers(); return
                start_text, end_text = match.groups()
                if not start_text and not end_text:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers(); return
                if start_text:
                    start = int(start_text)
                    end = int(end_text) if end_text else file_size - 1
                else:
                    suffix = int(end_text)
                    start = max(0, file_size - suffix)
                    end = file_size - 1
                if start >= file_size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers(); return
                end = min(end, file_size - 1)
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            with path.open("rb") as media:
                media.seek(start)
                remaining = length
                while remaining:
                    chunk = media.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            return
        if self.path.startswith("/api/state"):
            saved = sum(1 for i in range(len(self.state.events))
                        if self.state.labels.get(i, {}).get("event_type"))
            self._json({
                "index": self.state.index,
                "total": len(self.state.events),
                "saved": saved,
            })
            return
        if self.path.startswith("/api/event?"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            i = int(q.get("index", [self.state.index])[0])
            ev = self.state.to_public_event(i)
            if ev is None:
                self._json({"error": "not found"}, 404); return
            self._json(ev)
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._json({"error": "bad json"}, 400); return
        if self.path == "/api/label":
            if "event_index" not in payload:
                self._json({"error": "event_index required"}, 400); return
            next_index = self.state.save_label(payload)
            self._json({"ok": True, "next_index": next_index})
            return
        if self.path == "/api/next":
            i = self.state.next_unsaved()
            # Fallback: linear advance
            if self.state.index < len(self.state.events) - 1:
                i = self.state.index + 1
            self.state.index = i
            self._json({"index": i})
            return
        if self.path == "/api/prev":
            i = self.state.prev_index()
            self._json({"index": i})
            return
        if self.path == "/api/quit":
            # Shutdown from a background thread
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            self._json({"ok": True})
            return
        self.send_response(404); self.end_headers()


def _bind_port(start: int = 43127, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not bind any port in [{start}, {start + attempts})")


def _manifest_needs_refresh(path: Path) -> bool:
    """Return true when clips were rendered by an older overlay version."""
    if not path.is_file():
        return True
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return True
    version_marker = f"v{REVIEW_RENDER_VERSION}_"
    return any(version_marker not in row.get("review_clip_path", "") for row in rows)


def serve(args) -> int:
    labels_csv = args.labels_csv.resolve()
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "manifest.csv"
    if not labels_csv.exists() or args.rebuild or _manifest_needs_refresh(manifest_path):
        if args.rebuild:
            for p in output_dir.glob("*.mp4"):
                p.unlink()
        prepare(
            args.video.resolve(),
            args.tracklets.resolve(),
            args.detections.resolve(),
            args.stitches.resolve() if args.stitches else None,
            output_dir,
            labels_csv,
            review_window_seconds=args.review_window,
            orphan_lookback_seconds=args.orphan_lookback,
            boundary_seconds=args.boundary,
            pre_seconds=args.pre_seconds,
            post_seconds=args.post_seconds,
            hands_csv=args.hands,
        )
    elif labels_csv.exists():
        # Re-prepare only if the labels CSV has fewer rows than the
        # manifest (events have been added since last prepare).
        events_path = manifest_path
        if events_path.is_file():
            with events_path.open(newline="", encoding="utf-8") as f:
                n_events = sum(1 for _ in csv.DictReader(f))
            with labels_csv.open(newline="", encoding="utf-8") as f:
                n_labels = sum(1 for _ in csv.DictReader(f))
            if n_labels < n_events:
                print(f"Labels CSV has {n_labels} rows but {n_events} events; "
                      "re-preparing.")
                prepare(
                    args.video.resolve(),
                    args.tracklets.resolve(),
                    args.detections.resolve(),
                    args.stitches.resolve() if args.stitches else None,
                    output_dir,
                    labels_csv,
                    review_window_seconds=args.review_window,
                    orphan_lookback_seconds=args.orphan_lookback,
                    boundary_seconds=args.boundary,
                    pre_seconds=args.pre_seconds,
                    post_seconds=args.post_seconds,
                    hands_csv=args.hands,
                )

    tailscale_ip = _tailscale_ipv4()
    port = _bind_port(args.start_port, args.port_attempts)
    if args.bind:
        host = args.bind
    elif tailscale_ip:
        host = tailscale_ip
    else:
        host = "127.0.0.1"

    # Load tracks + hands for the live hand-features endpoint. These are
    # used only by /api/event when --hands is provided. Track loading is
    # cheap; hand loading is cheap too. Doing it here means the
    # reviewer can serve the v1B features without re-rendering clips.
    server_tracks = None
    server_hands = None
    if args.hands is not None:
        server_tracks = load_tracklets(args.tracklets.resolve())
        hand_overlay_mod = _import_hand_overlay()
        server_hands = hand_overlay_mod.load_hands_by_frame(args.hands)
        if not server_hands:
            print(f"WARNING: --hands {args.hands} produced no hand rows; "
                  f"live hand-features disabled.")
            server_hands = None

    state = _State(
        events_path=output_dir / "manifest.csv",
        labels_path=labels_csv,
        clip_root=output_dir,
        port=port,
        host=host,
        url=f"http://{host}:{port}",
        tracks=server_tracks,
        hands_by_frame=server_hands,
    )

    class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    ReviewerHandler.state = state
    httpd = _ThreadingHTTPServer((host, port), ReviewerHandler)
    print("=============================================================")
    print(f"Reviewer running ({len(state.events)} events).")
    print()
    if host == tailscale_ip and tailscale_ip:
        print(f"Open on your laptop:")
        print(f"  http://{tailscale_ip}:{port}")
    elif host == "127.0.0.1":
        print(f"No tailscale detected; binding to localhost only.")
        print(f"On your laptop run (use any free laptop-side port; we picked "
              f"remote-side port {port}):")
        print(f"  ssh -N -L 43127:127.0.0.1:{port} {os.environ.get('USER', 'user')}@{socket.gethostname()}")
        print(f"Then open:")
        print(f"  http://127.0.0.1:43127")
    else:
        print(f"Bound to {host}. Open:")
        print(f"  http://{host}:{port}")
    print()
    print(f"Labels CSV: {labels_csv}")
    print(f"Review clips: {output_dir}")
    print(f"Press q in the browser (or Ctrl-C here) to quit safely.")
    print("=============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--video", type=Path, required=True)
    common.add_argument("--tracklets", type=Path, required=True)
    common.add_argument("--detections", type=Path, required=True)
    common.add_argument("--stitches", type=Path, default=None)
    common.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "track_event_review")
    common.add_argument("--labels-csv", type=Path,
                        default=PROJECT_ROOT / "detections" / "track_event_review_labels.csv")
    common.add_argument("--review-window", type=float, default=1.0)
    common.add_argument("--orphan-lookback", type=float, default=4.5,
                        help="Backward review window for orphan predecessors (default: 4.5 s; review only).")
    common.add_argument("--boundary", type=float, default=0.5)
    common.add_argument("--pre-seconds", type=float, default=1.0)
    common.add_argument("--post-seconds", type=float, default=2.0)
    common.add_argument("--rebuild", action="store_true")
    common.add_argument("--hands", type=Path, default=None,
                        help="Optional per-frame hand CSV produced by "
                             "scripts/extract_hands.py. When provided, the "
                             "reviewer overlays anatomical left/right hands and "
                             "exposes the v1A hand features in the UI. The "
                             "reviewer remains fully functional without this "
                             "argument.")

    prep = sub.add_parser("prepare", parents=[common], help="Generate events + clips only")
    serve_p = sub.add_parser("serve", parents=[common], help="Generate (if needed) and serve")
    serve_p.add_argument("--start-port", type=int, default=43127)
    serve_p.add_argument("--port-attempts", type=int, default=20)
    serve_p.add_argument("--bind",
                        help="Override bind address (default: Tailscale IP if "
                        "available, else 127.0.0.1).")
    serve_p.add_argument("--no-open", action="store_true",
                        help="Skip auto-opening a browser tab (no-op when not Tailscale).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        labels_csv, n_end, n_orphan, n_existing = prepare(
            args.video.resolve(),
            args.tracklets.resolve(),
            args.detections.resolve(),
            args.stitches.resolve() if args.stitches else None,
            args.output_dir.resolve(),
            args.labels_csv.resolve(),
            review_window_seconds=args.review_window,
            orphan_lookback_seconds=args.orphan_lookback,
            boundary_seconds=args.boundary,
            pre_seconds=args.pre_seconds,
            post_seconds=args.post_seconds,
            hands_csv=args.hands,
        )
        print(f"Wrote {labels_csv}")
        print(f"Counts: end={n_end} orphan_start={n_orphan} existing_stitch={n_existing}")
        return 0
    if args.command == "serve":
        return serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())