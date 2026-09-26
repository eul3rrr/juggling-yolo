"""Deterministic visual evidence per stitch event, written to disk for review.

Every image the model sees is also the image the human reviewer sees; both are
regenerated from the same manifest so a rerun cannot silently disagree with what
was judged.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

SOURCE_COLOR = (0, 255, 0)        # BGR green
CANDIDATE_COLORS = [(255, 255, 0), (255, 0, 255), (0, 165, 255), (255, 120, 0)]
CONTEXT_WIDTH = 1008


@dataclass(frozen=True)
class EvidenceConfig:
    crop_w: int = 440
    crop_h: int = 340
    crop_out_w: int = 620
    ring_radius: int = 48
    pre_offsets: tuple[int, ...] = (-30, -15, -5, 0)
    lost_offset: int = 3
    candidate_offsets: tuple[int, ...] = (0, 6, 18)
    context_width: int = CONTEXT_WIDTH
    jpeg_quality: int = 84
    trail_points: int = 20

    def as_dict(self) -> dict:
        data = asdict(self)
        for key in ("pre_offsets", "candidate_offsets"):
            data[key] = list(data[key])
        return data


def candidate_letters(count: int) -> list[str]:
    if count > 26:
        raise ValueError("at most 26 candidates are addressable by letter")
    return [chr(ord("A") + i) for i in range(count)]


class FrameReader:
    """Seek-based frame reader with an unbounded per-run cache (events are small)."""

    def __init__(self, video: Path):
        self.video = Path(video)
        self._capture = None
        self._cache: dict[int, np.ndarray] = {}
        probe = cv2.VideoCapture(str(self.video))
        if not probe.isOpened():
            raise RuntimeError(f"Could not open video: {self.video}")
        self.fps = float(probe.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(probe.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
        probe.release()

    def __call__(self, frame: int) -> np.ndarray:
        if frame < 0 or frame >= self.frame_count:
            raise ValueError(f"Frame {frame} outside 0..{self.frame_count - 1}")
        if frame not in self._cache:
            if self._capture is None:
                self._capture = cv2.VideoCapture(str(self.video))
                if not self._capture.isOpened():
                    raise RuntimeError(f"Could not open video: {self.video}")
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = self._capture.read()
            if not ok:
                raise RuntimeError(f"Could not decode frame {frame}")
            self._cache[frame] = image
        return self._cache[frame]

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


def _crop_origin(x: float, y: float, width: int, height: int, crop_w: int, crop_h: int) -> tuple[int, int]:
    return (int(np.clip(x - crop_w / 2, 0, max(0, width - crop_w))),
            int(np.clip(y - crop_h / 2, 0, max(0, height - crop_h))))


def render_crop(image: np.ndarray, x: float, y: float, color: tuple[int, int, int],
                label: str, config: EvidenceConfig) -> np.ndarray:
    """A ball-centred crop with a ring, crosshair ticks and a one-line info bar."""
    height, width = image.shape[:2]
    x0, y0 = _crop_origin(x, y, width, height, config.crop_w, config.crop_h)
    crop = image[y0:y0 + config.crop_h, x0:x0 + config.crop_w].copy()
    cx, cy = int(x - x0), int(y - y0)
    r = config.ring_radius
    cv2.circle(crop, (cx, cy), r, color, 2, cv2.LINE_AA)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        a = (cx + dx * (r + 2), cy + dy * (r + 2)) if dx else (cx, cy + dy * (r + 2))
        b = (cx + dx * (r + 14), cy + dy * (r + 14)) if dx else (cx, cy + dy * (r + 14))
        cv2.line(crop, a, b, color, 2, cv2.LINE_AA)
    bar = np.zeros((28, config.crop_w, 3), np.uint8)
    cv2.putText(bar, label[:64], (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    stacked = np.vstack([bar, crop])
    return cv2.resize(stacked, (config.crop_out_w, int(round(stacked.shape[0] * config.crop_out_w / stacked.shape[1]))))


def render_context(image: np.ndarray, marks: list[dict], trails: list[dict], config: EvidenceConfig) -> np.ndarray:
    """Wide frame with rings, labels and observed trails for spatial context."""
    canvas = image.copy()
    for trail in trails:
        points = trail["points"]
        if len(points) < 2:
            continue
        pts = np.array([[int(round(p[0])), int(round(p[1]))] for p in points], np.int32)
        cv2.polylines(canvas, [pts], False, trail["color"], 2, cv2.LINE_AA)
        cv2.circle(canvas, tuple(pts[-1]), 4, trail["color"], -1, cv2.LINE_AA)
    for mark in marks:
        x, y = int(round(mark["x"])), int(round(mark["y"]))
        cv2.circle(canvas, (x, y), 36, mark["color"], 3, cv2.LINE_AA)
        cv2.putText(canvas, mark["text"], (x + 40, y - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.95,
                    mark["color"], 2, cv2.LINE_AA)
    scale = config.context_width / canvas.shape[1]
    return cv2.resize(canvas, (config.context_width, int(round(canvas.shape[0] * scale))))


def _nearest_observed(track, frame: int):
    observed = track.observed
    return min(observed, key=lambda o: abs(o.frame - frame))


def _encode(path: Path, image: np.ndarray, config: EvidenceConfig) -> None:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality])
    if not ok:
        raise ValueError(f"JPEG encoding failed for {path}")
    path.write_bytes(buffer.tobytes())


def _event_fingerprint(event: dict, fps: float) -> dict:
    return dict(
        source=dict(track_id=event["source"]["track_id"], last_frame=event["source"]["last_frame"]),
        candidates=[dict(track_id=c["track_id"], first_frame=c["first_frame"]) for c in event["candidates"]],
    )


def build_event_evidence(event: dict, tracks: dict, reader: FrameReader, out_dir: Path,
                         config: EvidenceConfig, prompt_version: str) -> dict:
    """Write every evidence image for one event plus its manifest.

    Rerun-safe: an existing manifest with the same config, prompt version and
    event fingerprint is reused unless the caller removed it.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = event["fps"]
    source = event["source"]
    source_track = tracks[source["track_id"]]
    letters = candidate_letters(len(event["candidates"]))
    images: list[dict] = []

    def add(image: np.ndarray, role: str, role_index: int, label: str, track_id: int, frame: int,
            letter: str | None = None, requested_offset: int | None = None) -> None:
        name = f"{len(images) + 1:02d}_{role}_{track_id}_{frame}.jpg"
        _encode(out_dir / name, image, config)
        images.append(dict(file=name, role=role, role_index=role_index, letter=letter, label=label,
                           track_id=track_id, frame=frame, seconds=frame / fps,
                           requested_offset_frames=requested_offset))

    # Pre-loss crops follow the ball's own observed frames.  A sparse track can map
    # several requested offsets onto the same observed frame; duplicates are dropped
    # so the model is never shown the identical image twice.
    pre_frames: list[tuple[int, int]] = []
    seen_frames: set[int] = set()
    for offset in config.pre_offsets:
        frame = int(np.clip(source["last_frame"] + offset, 0, reader.frame_count - 1))
        observed = _nearest_observed(source_track, frame)
        if observed.frame in seen_frames:
            continue
        seen_frames.add(observed.frame)
        pre_frames.append((offset, observed.frame))

    for index, (offset, observed_frame) in enumerate(pre_frames, 1):
        observed = _nearest_observed(source_track, observed_frame)
        add(render_crop(reader(observed.frame), observed.center_x, observed.center_y, SOURCE_COLOR,
                        f"END T{source['track_id']} pre-loss {index}/{len(pre_frames)}", config),
            "source_pre", index, f"END tracklet T{source['track_id']} before it is lost", source["track_id"],
            observed.frame, requested_offset=offset)

    lost_frame = int(np.clip(source["last_frame"] + config.lost_offset, 0, reader.frame_count - 1))
    add(render_crop(reader(lost_frame), source["last_x"], source["last_y"], SOURCE_COLOR,
                    f"END T{source['track_id']} LOST (no detection)", config),
        "source_lost", 1, f"END tracklet T{source['track_id']} at/after its last detection (ball gone or hidden)",
        source["track_id"], lost_frame, requested_offset=config.lost_offset)

    for position, (candidate, letter) in enumerate(zip(event["candidates"], letters)):
        color = CANDIDATE_COLORS[position % len(CANDIDATE_COLORS)]
        candidate_track = tracks[candidate["track_id"]]
        for index, offset in enumerate(config.candidate_offsets, 1):
            frame = int(np.clip(candidate["first_frame"] + offset, 0, reader.frame_count - 1))
            observed = _nearest_observed(candidate_track, frame)
            add(render_crop(reader(observed.frame), observed.center_x, observed.center_y, color,
                            f"CAND-{letter} T{candidate['track_id']} +{offset}f", config),
                "candidate", index, f"candidate {letter}: tracklet T{candidate['track_id']} right after it starts",
                candidate["track_id"], observed.frame, letter=letter, requested_offset=offset)

    trails: list[dict] = [dict(points=[[o.center_x, o.center_y] for o in source_track.observed[-config.trail_points:]],
                               color=SOURCE_COLOR)]
    marks: list[dict] = [dict(x=source["last_x"], y=source["last_y"], color=SOURCE_COLOR,
                              text=f"END T{source['track_id']}")]
    for position, (candidate, letter) in enumerate(zip(event["candidates"], letters)):
        color = CANDIDATE_COLORS[position % len(CANDIDATE_COLORS)]
        candidate_track = tracks[candidate["track_id"]]
        trails.append(dict(points=[[o.center_x, o.center_y] for o in candidate_track.observed[:3]], color=color))
        marks.append(dict(x=candidate["first_x"], y=candidate["first_y"], color=color,
                          text=f"{letter} T{candidate['track_id']}"))
    context_frame = int(np.clip(source["last_frame"] + config.lost_offset, 0, reader.frame_count - 1))
    add(render_context(reader(context_frame), marks, trails, config), "context", 1,
        "full frame at the moment of loss: END ball and candidate starts are ringed, trails show recent observed motion",
        source["track_id"], context_frame, requested_offset=config.lost_offset)

    manifest = dict(
        event_key=event["event_key"],
        prompt_version=prompt_version,
        fingerprint=_event_fingerprint(event, fps),
        config=config.as_dict(),
        video=dict(path=str(reader.video), fps=reader.fps, frame_count=reader.frame_count,
                   width=reader.width, height=reader.height),
        segment_index=event["segment_index"],
        window_frames=event["window_frames"],
        top_k=event["top_k"],
        source=source,
        candidates=[dict(candidate, letter=letter) for candidate, letter in zip(event["candidates"], letters)],
        cv_rank1=event["cv_rank1"],
        context_marks=marks,
        images=images,
        images_per_role={role: sum(1 for image in images if image["role"] == role)
                         for role in ("source_pre", "source_lost", "candidate", "context")},
    )
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def manifest_is_current(manifest: dict, event: dict, config: EvidenceConfig, prompt_version: str,
                        out_dir: Path) -> bool:
    """True when an existing manifest already describes this event and config."""
    if manifest.get("prompt_version") != prompt_version:
        return False
    if manifest.get("config") != config.as_dict():
        return False
    if manifest.get("fingerprint") != _event_fingerprint(event, event["fps"]):
        return False
    if sum(1 for _ in Path(out_dir).glob("*.jpg")) != len(manifest.get("images", [])):
        return False
    return True
