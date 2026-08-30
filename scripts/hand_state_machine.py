#!/usr/bin/env python3
"""FIFO-only hand pending-identity association; no airborne logic."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from hand_events import HandEvent


@dataclass(frozen=True)
class PendingSource:
    source_track_id: int
    entry_frame: int
    eligible_hands: frozenset[str]
    preferred_hand: str | None
    ambiguous: bool
    event: HandEvent


@dataclass(frozen=True)
class HandAssociation:
    source_track_id: int
    target_track_id: int
    source_end_frame: int
    target_start_frame: int
    gap_frames: int
    hold_seconds: float
    association_type: str
    resolved_hand: str
    hand_ambiguous: bool
    source_eligible_hand_set: str
    target_eligible_hand_set: str
    source_preferred_hand: str
    target_preferred_hand: str
    source_ambiguous: bool
    target_ambiguous: bool
    match_rule: str


@dataclass(frozen=True)
class TraceRow:
    frame: int
    event_type: str
    track_id: int
    action: str
    resolved_hand: str
    matched_source_track_id: str
    pending_before: str
    pending_after: str


@dataclass(frozen=True)
class UnmatchedEvent:
    event: HandEvent
    reason: str


@dataclass(frozen=True)
class MatchResult:
    associations: list[HandAssociation]
    unmatched: list[UnmatchedEvent]
    trace: list[TraceRow]


def load_hand_events(path: Path) -> list[HandEvent]:
    """Load the already-classified logical hand-events CSV unchanged."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        return [HandEvent(
            int(r["track_id"]), r["boundary_type"], int(r["boundary_frame"]),
            r["event_type"], r["boundary_x"], r["boundary_y"], r["eligible_hand_set"],
            r["preferred_hand"] or None, r["ambiguous"] == "1", r["hand_evidence"] == "1",
            r["evidence_reason"], r["video_start_boundary"] == "1", r["video_end_boundary"] == "1",
            r["proximity_band"], r["motion"], r["endpoint_distance_px"],
            r["endpoint_distance_normalized"], r["recent_min_distance_px"],
            r["recent_min_distance_normalized"], r["post_contact"] == "1") for r in rows]


def _hands(value: str) -> frozenset[str]:
    return frozenset(x.strip() for x in value.strip("{}").split(",") if x.strip())


def _pending_text(pending: list[PendingSource]) -> str:
    return ";".join(f"T{p.source_track_id}:{{{','.join(sorted(p.eligible_hands))}}}" for p in pending)


def _exit_hands(event: HandEvent) -> frozenset[str]:
    if event.preferred_hand:
        return frozenset((event.preferred_hand,))
    return _hands(event.eligible_hand_set)


def _resolved_hand(source: PendingSource, target: HandEvent, common: frozenset[str]) -> tuple[str, bool, str]:
    if len(common) == 1:
        hand = next(iter(common))
        if source.ambiguous:
            return hand, False, "FIFO_AMBIGUOUS_SOURCE_RESOLVED"
        if target.ambiguous:
            return hand, False, "FIFO_AMBIGUOUS_EXIT_RESOLVED"
        return hand, False, "FIFO"
    if len(common) > 1:
        return "{" + ",".join(sorted(common)) + "}", True, "FIFO_AMBIGUOUS"
    return "", False, "FIFO"


def match_hand_events(events: list[HandEvent], fps: float, expiry_seconds: float = 5.0) -> MatchResult:
    if fps <= 0 or expiry_seconds < 0:
        raise ValueError("fps must be positive and expiry_seconds must be nonnegative")
    expiry_frames = fps * expiry_seconds
    pending: list[PendingSource] = []
    associations: list[HandAssociation] = []
    unmatched: list[UnmatchedEvent] = []
    trace: list[TraceRow] = []
    ordered = sorted((e for e in events if e.event_type in {"HAND_ENTRY", "HAND_EXIT"}),
                     key=lambda e: (e.boundary_frame, 0 if e.event_type == "HAND_EXIT" else 1, e.track_id))
    for event in ordered:
        before = _pending_text(pending)
        stale = [p for p in pending if event.boundary_frame - p.entry_frame > expiry_frames]
        for source in stale:
            pending.remove(source)
            unmatched.append(UnmatchedEvent(source.event, "EXPIRED_PENDING_SOURCE"))
            trace.append(TraceRow(event.boundary_frame, "EXPIRY", source.source_track_id,
                                  "EXPIRED_PENDING_SOURCE", "", "", before, _pending_text(pending)))
            before = _pending_text(pending)
        if event.event_type == "HAND_ENTRY":
            source = PendingSource(event.track_id, event.boundary_frame, _hands(event.eligible_hand_set),
                                   event.preferred_hand, event.ambiguous, event)
            pending.append(source)
            trace.append(TraceRow(event.boundary_frame, event.event_type, event.track_id,
                                  "PENDING_ENTRY", "", "", before, _pending_text(pending)))
            continue
        if event.video_start_boundary:
            unmatched.append(UnmatchedEvent(event, "VIDEO_START_EXIT"))
            trace.append(TraceRow(event.boundary_frame, event.event_type, event.track_id,
                                  "UNMATCHED_VIDEO_START", "", "", before, _pending_text(pending)))
            continue
        exit_hands = _exit_hands(event)
        candidates = [p for p in pending if p.entry_frame < event.boundary_frame
                      and p.eligible_hands & exit_hands]
        if not candidates:
            unmatched.append(UnmatchedEvent(event, "NO_COMPATIBLE_PENDING_SOURCE"))
            trace.append(TraceRow(event.boundary_frame, event.event_type, event.track_id,
                                  "UNMATCHED_NO_COMPATIBLE_SOURCE", "", "", before, _pending_text(pending)))
            continue
        source = candidates[0]
        pending.remove(source)
        common = source.eligible_hands & exit_hands
        hand, ambiguous, rule = _resolved_hand(source, event, common)
        associations.append(HandAssociation(
            source_track_id=source.source_track_id, target_track_id=event.track_id,
            source_end_frame=source.entry_frame, target_start_frame=event.boundary_frame,
            gap_frames=event.boundary_frame - source.entry_frame - 1,
            hold_seconds=(event.boundary_frame - source.entry_frame) / fps,
            association_type="HAND", resolved_hand=hand, hand_ambiguous=ambiguous,
            source_eligible_hand_set=event_set(source.eligible_hands),
            target_eligible_hand_set=event.eligible_hand_set,
            source_preferred_hand=source.preferred_hand or "",
            target_preferred_hand=event.preferred_hand or "",
            source_ambiguous=source.ambiguous, target_ambiguous=event.ambiguous,
            match_rule=rule,
        ))
        trace.append(TraceRow(event.boundary_frame, event.event_type, event.track_id,
                              "MATCHED_FIFO", hand, str(source.source_track_id), before, _pending_text(pending)))
    for source in pending:
        reason = "VIDEO_END_PENDING_ENTRY" if source.event.video_end_boundary else "UNRESOLVED_PENDING_ENTRY"
        unmatched.append(UnmatchedEvent(source.event, reason))
        trace.append(TraceRow(source.entry_frame, "FINALIZATION", source.source_track_id,
                              reason, "", "", _pending_text(pending), _pending_text(pending)))
    return MatchResult(associations, unmatched, trace)


def event_set(hands: frozenset[str]) -> str:
    return "{" + ",".join(sorted(hands)) + "}" if hands else "{}"


def write_associations(rows: list[HandAssociation], path: Path) -> None:
    fields = ["source_track_id", "target_track_id", "source_end_frame", "target_start_frame", "gap_frames", "hold_seconds", "association_type", "resolved_hand", "hand_ambiguous", "source_eligible_hand_set", "target_eligible_hand_set", "source_preferred_hand", "target_preferred_hand", "source_ambiguous", "target_ambiguous", "match_rule"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader()
        for r in rows: w.writerow(r.__dict__)


def write_unmatched(rows: list[UnmatchedEvent], path: Path) -> None:
    fields = ["track_id", "boundary_type", "boundary_frame", "event_type", "eligible_hand_set", "preferred_hand", "ambiguous", "hand_evidence", "video_start_boundary", "video_end_boundary", "reason"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader()
        for x in rows:
            e=x.event; w.writerow({"track_id":e.track_id,"boundary_type":e.boundary_type,"boundary_frame":e.boundary_frame,"event_type":e.event_type,"eligible_hand_set":e.eligible_hand_set,"preferred_hand":e.preferred_hand or "","ambiguous":int(e.ambiguous),"hand_evidence":int(e.hand_evidence),"video_start_boundary":int(e.video_start_boundary),"video_end_boundary":int(e.video_end_boundary),"reason":x.reason})


def write_trace(rows: list[TraceRow], path: Path) -> None:
    fields = ["frame", "event_type", "track_id", "action", "resolved_hand", "matched_source_track_id", "pending_before", "pending_after"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for r in rows: w.writerow(r.__dict__)


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--events",type=Path,required=True); p.add_argument("--fps",type=float,required=True); p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    result=match_hand_events(load_hand_events(a.events),a.fps); a.output_dir.mkdir(parents=True,exist_ok=True)
    write_associations(result.associations,a.output_dir/"identical_balls_trick_000_018_hand_associations.csv")
    write_unmatched(result.unmatched,a.output_dir/"identical_balls_trick_000_018_unmatched_hand_events.csv")
    write_trace(result.trace,a.output_dir/"identical_balls_trick_000_018_hand_state_trace.csv")
    for r in result.associations: print(f"{r.target_start_frame:4d} HAND {r.source_track_id}->{r.target_track_id} {r.resolved_hand}")
    for x in result.unmatched: print(f"{x.event.boundary_frame:4d} {x.event.event_type} T{x.event.track_id} {x.reason}")


if __name__ == "__main__": main()
