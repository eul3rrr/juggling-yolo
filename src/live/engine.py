from __future__ import annotations

import csv
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import hand_association as ha
from hand_events import HandEvent
import hand_state_machine as hsm


@dataclass(frozen=True)
class Point:
    frame: int
    x: float
    y: float


@dataclass(frozen=True)
class TestEvent:
    track_id: int
    event_type: str
    boundary_frame: int
    eligible_hand_set: str
    preferred_hand: str | None = None
    ambiguous: bool = False


class DisplayHIDMap:
    def __init__(self):
        self._track_to_hid: dict[int, int] = {}
        self._next = 1

    def hid_for(self, track_id: int) -> int:
        if track_id not in self._track_to_hid:
            self._track_to_hid[track_id] = self._next
            self._next += 1
        return self._track_to_hid[track_id]

    def apply_associations(self, associations: list[tuple[int, int]]) -> dict[int, int]:
        for source, target in associations:
            hid = self._track_to_hid.get(source)
            if hid is None:
                hid = self.hid_for(source)
            self._track_to_hid[target] = hid
        return dict(self._track_to_hid)

    @property
    def mapping(self):
        return dict(self._track_to_hid)


def pending_overlay_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pending identity is attached to a wrist; never manufacture a ball coordinate."""
    return [{**item, "position": None, "wrist_side": item.get("hand", "AMB")} for item in items]


class LiveReasoningAdapter:
    """Small event-time adapter shared by replay and live inference.

    Track lifecycle is authoritative: START uses the first five observed points;
    END uses the last five and is emitted only when close_track is called.
    """
    def __init__(self, fps: float, hands_by_frame: dict[int, dict] | None = None):
        self.fps = fps
        self.hands_by_frame = hands_by_frame or {}
        self.track_points: dict[int, list[Point]] = defaultdict(list)
        self.known_events: list[Any] = []
        self.associations = []
        self.recompute_count = 0
        self.display_hids = DisplayHIDMap()
        self._started: set[int] = set()
        self._closed: set[int] = set()

    def observe_track(self, track_id: int, frame: int, x: float, y: float) -> str:
        points = self.track_points[track_id]
        points.append(Point(frame, x, y))
        if track_id not in self._started:
            self._started.add(track_id)
            return "START_PROVISIONAL"
        return "START_PROVISIONAL" if len(points) < 5 else "START_READY"

    def close_track(self, track_id: int, discovered_at: int | None = None):
        if track_id in self._closed:
            return next(e for e in self.known_events if getattr(e, "track_id", -1) == track_id and e.boundary_type == "END")
        points = self.track_points[track_id]
        if not points:
            raise ValueError("cannot close an empty track")
        assessment = None
        if self.hands_by_frame:
            import hand_boundaries
            bp = [hand_boundaries.BoundaryPoint(p.frame, p.x, p.y) for p in points]
            assessment = hand_boundaries.assess_boundary(track_id, "END", bp, self.hands_by_frame)
        event = self._event_from_assessment(assessment, track_id, "END", points[-1]) if assessment else TestEvent(track_id, "HAND_ENTRY", points[-1].frame, "{}")
        event = _with_discovery(event, discovered_at)
        self.add_test_event(event)
        self._closed.add(track_id)
        return event

    def _event_from_assessment(self, a, track_id, kind, point):
        eligible = "{" + ",".join(a.eligible_hands) + "}"
        evidence = bool(a.eligible_hands)
        return HandEvent(track_id, kind, a.boundary_frame,
                         "HAND_ENTRY" if kind == "END" and evidence else "NON_HAND_END",
                         f"{a.boundary_x}", f"{a.boundary_y}", eligible,
                         a.preferred_hand, a.ambiguous, evidence, "; ".join(r.reason for r in a.hand_results.values()),
                         False, False, "", "", "", "", "", "", any(r.post_contact for r in a.hand_results.values()))

    def add_test_event(self, event):
        self.known_events.append(event)
        self.known_events.sort(key=lambda e: (e.boundary_frame, getattr(e, "track_id", 0)))
        self.recompute_count += 1
        return self.known_events

    def recompute(self):
        events = [e for e in self.known_events if isinstance(e, HandEvent)]
        if events:
            result = hsm.match_hand_events(events, self.fps)
            self.associations = result.associations
        return self.associations


def _with_discovery(event, discovered_at):
    if discovered_at is None:
        return event
    return type("DiscoveredEvent", (), {**getattr(event, "__dict__", {}), "discovered_at": discovered_at, "boundary_type": getattr(event, "boundary_type", "END")})()


def canonical_parity(events_path: Path, associations_path: Path) -> dict[str, Any]:
    with events_path.open(newline="", encoding="utf-8") as f:
        events = hsm.load_hand_events(events_path)
    result = hsm.match_hand_events(events, fps=59.94)
    with associations_path.open(newline="", encoding="utf-8") as f:
        authoritative = [(int(r["source_track_id"]), int(r["target_track_id"])) for r in csv.DictReader(f)]
    actual = [(a.source_track_id, a.target_track_id) for a in result.associations]
    return {"accepted": actual, "authoritative": authoritative, "match": actual == authoritative}


def load_canonical_rows(tracklets_path: Path) -> dict[int, list[Point]]:
    out = defaultdict(list)
    with tracklets_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed", "1") == "1":
                out[int(row["track_id"])].append(Point(int(row["frame"]), float(row["center_x"]), float(row["center_y"])))
    return out
