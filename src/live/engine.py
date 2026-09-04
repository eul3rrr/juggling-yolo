from __future__ import annotations

import csv
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
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


@dataclass
class LiveTracklet:
    track_id: int
    first_observed_points: list[Point] = field(default_factory=list)
    observed_history: list[Point] = field(default_factory=list)
    recent_observed_points: deque[Point] = field(default_factory=lambda: deque(maxlen=30))
    last_observed_frame: int | None = None
    closed: bool = False
    start_event: Any = None
    end_event: Any = None

    @property
    def observed_points(self) -> list[Point]:
        return list(self.observed_history)


class LiveTrackletStore:
    """Observed-only lifecycle state and frozen hand-event/FIFO integration."""
    def __init__(self, fps: float):
        self.fps = fps
        self.tracklets: dict[int, LiveTracklet] = {}
        self.hands_by_frame: dict[int, dict] = {}
        self.known_events: list[Any] = []
        self.associations: list[Any] = []
        self.bridges: list[dict[str, Any]] = []
        self.display_hids = DisplayHIDMap()

    def observe(self, frame: int, observations: list[dict], hands: dict[str, dict]) -> None:
        self.hands_by_frame[frame] = {
            side.lower(): (value.get("x"), value.get("y")) if value and value.get("x") is not None else None
            for side, value in hands.items()
        }
        self.hands_by_frame[frame]["body_scale"] = next(
            (value.get("body_scale") for value in hands.values() if value and value.get("body_scale") is not None), None
        )
        self.hands_by_frame[frame]["left_confidence"] = (hands.get("LEFT") or {}).get("confidence")
        self.hands_by_frame[frame]["right_confidence"] = (hands.get("RIGHT") or {}).get("confidence")
        for row in observations:
            if not row.get("observed"):
                continue
            tid = int(row["track_id"])
            state = self.tracklets.setdefault(tid, LiveTracklet(tid))
            point = Point(frame, float(row["x"]), float(row["y"]))
            state.observed_history.append(point)
            if len(state.first_observed_points) < 5:
                state.first_observed_points.append(point)
            state.recent_observed_points.append(point)
            state.last_observed_frame = frame
            self.display_hids.hid_for(tid)
            if state.start_event is None and len(state.first_observed_points) >= 5:
                state.start_event = self._classify(tid, "START", state.first_observed_points)
                self._insert_event(state.start_event)

    def close_terminated(self, terminated_ids: set[int], frame: int) -> None:
        for tid in sorted(terminated_ids):
            state = self.tracklets.get(tid)
            if state is None or state.closed or not state.first_observed_points:
                continue
            if state.start_event is None:
                state.start_event = self._classify(tid, "START", state.first_observed_points)
                self._insert_event(state.start_event)
            state.end_event = self._classify(tid, "END", state.first_observed_points)
            self._insert_event(state.end_event)
            state.closed = True

    def _classify(self, tid: int, boundary_type: str, points: list[Point]):
        import hand_boundaries
        window = points[:5] if boundary_type == "START" else points[-5:]
        bp = [hand_boundaries.BoundaryPoint(p.frame, p.x, p.y) for p in window]
        assessment = hand_boundaries.assess_boundary(tid, boundary_type, bp, self.hands_by_frame)
        evidence = bool(assessment.eligible_hands)
        preferred = assessment.preferred_hand
        event_type = (("HAND_ENTRY" if boundary_type == "END" else "HAND_EXIT") if evidence
                      else ("NON_HAND_END" if boundary_type == "END" else "NON_HAND_START"))
        preferred_result = None if assessment.ambiguous else assessment.hand_results.get(preferred.lower() if preferred else "")
        return HandEvent(
            tid, boundary_type, assessment.boundary_frame, event_type,
            str(assessment.boundary_x), str(assessment.boundary_y),
            "{" + ",".join(assessment.eligible_hands) + "}", preferred,
            assessment.ambiguous, evidence,
            "; ".join(f"{side}: {result.reason}" for side, result in assessment.hand_results.items()),
            assessment.boundary_frame == 0, False,
            preferred_result.proximity if preferred_result else "",
            preferred_result.motion if preferred_result else "",
            str(preferred_result.endpoint_distance_px) if preferred_result and preferred_result.endpoint_distance_px is not None else "",
            str(preferred_result.endpoint_distance_normalized) if preferred_result and preferred_result.endpoint_distance_normalized is not None else "",
            str(preferred_result.recent_min_distance_px) if preferred_result and preferred_result.recent_min_distance_px is not None else "",
            str(preferred_result.recent_min_distance_normalized) if preferred_result and preferred_result.recent_min_distance_normalized is not None else "",
            preferred_result.post_contact if preferred_result else False,
        )

    def _insert_event(self, event) -> None:
        self.known_events = [e for e in self.known_events if not (e.track_id == event.track_id and e.boundary_type == event.boundary_type)]
        self.known_events.append(event)
        self.known_events.sort(key=lambda e: (e.boundary_frame, 0 if e.event_type == "HAND_EXIT" else 1, e.track_id))
        result = hsm.match_hand_events(self.known_events, self.fps)
        self.associations = result.associations
        self._refresh_bridges()

    def _refresh_bridges(self) -> None:
        bridges = []
        for association in self.associations:
            source = self.tracklets.get(association.source_track_id)
            target = self.tracklets.get(association.target_track_id)
            if not source or not target or not source.first_observed_points or not target.first_observed_points:
                continue
            a, z = source.observed_history[-1], target.observed_history[0]
            bridges.append({"source_track_id": association.source_track_id, "target_track_id": association.target_track_id,
                            "source_end_frame": association.source_end_frame, "target_start_frame": association.target_start_frame,
                            "source_x": a.x, "source_y": a.y, "target_x": z.x, "target_y": z.y,
                            "hand": association.resolved_hand})
        self.bridges = bridges

    def pending(self, frame: int) -> list[dict[str, Any]]:
        matched = {a.source_track_id for a in self.associations}
        items = []
        for event in self.known_events:
            if event.event_type != "HAND_ENTRY" or event.track_id in matched or event.boundary_frame > frame:
                continue
            if frame - event.boundary_frame <= 5 * self.fps:
                hand = event.preferred_hand or (event.eligible_hand_set.strip("{}") or "AMB")
                items.append({"track_id": event.track_id, "hid": self.display_hids.hid_for(event.track_id),
                              "hand": hand, "age_seconds": round((frame - event.boundary_frame) / max(self.fps, 1), 2),
                              "position": None})
        return items


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
