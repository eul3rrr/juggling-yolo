from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FrameState:
    frame_id: int
    source_width: int
    source_height: int
    source_fps: float = 0.0
    processing_fps: float = 0.0
    latency_ms: float = 0.0
    detections: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[dict[str, Any]] = field(default_factory=list)
    hands: dict[str, Any] = field(default_factory=dict)
    proximity: dict[str, Any] = field(default_factory=dict)
    pending: list[dict[str, Any]] = field(default_factory=list)
    associations_recent: list[dict[str, Any]] = field(default_factory=list)
    events_recent: list[dict[str, Any]] = field(default_factory=list)
    bridges_recent: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    type: str = "frame"
    version: int = 1


def serialize_frame_state(state: FrameState) -> str:
    """Explicit versioned JSON serialization; never expose dataclasses directly."""
    return json.dumps(asdict(state), separators=(",", ":"), allow_nan=False)


def empty_state(error: str, width: int = 0, height: int = 0) -> FrameState:
    return FrameState(0, width, height, error=error)
