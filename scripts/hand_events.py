#!/usr/bin/env python3
"""Convert authoritative boundary assessments into unpaired hand events."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HandEvent:
    track_id: int
    boundary_type: str
    boundary_frame: int
    event_type: str
    boundary_x: str
    boundary_y: str
    eligible_hand_set: str
    preferred_hand: str | None
    ambiguous: bool
    hand_evidence: bool
    evidence_reason: str
    video_start_boundary: bool
    video_end_boundary: bool
    proximity_band: str
    motion: str
    endpoint_distance_px: str
    endpoint_distance_normalized: str
    recent_min_distance_px: str
    recent_min_distance_normalized: str
    post_contact: bool


def _logical_group(rows: list[dict[str, str]]) -> dict[tuple[str, int, int], dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, int, int], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = (row["boundary_type"], int(row["track_id"]), int(row["boundary_frame"]))
        grouped.setdefault(key, {})[row["hand"]] = row
    return grouped


def _truth(value: str | None) -> bool:
    return value == "1"


def _event_from_rows(key, side_rows, frame_min: int, frame_max: int) -> HandEvent:
    boundary_type, track_id, frame = key
    rows = list(side_rows.values())
    evidence = any(_truth(row.get("hand_evidence")) for row in rows)
    ambiguous = any(_truth(row.get("ambiguous")) for row in rows)
    eligible = next((row.get("eligible_hand_set", "") for row in rows if row.get("eligible_hand_set") is not None), "")
    preferred = next((row.get("preferred_hand", "") for row in rows if row.get("preferred_hand")), "") or None
    event_type = ("HAND_ENTRY" if boundary_type == "END" else "HAND_EXIT") if evidence else ("NON_HAND_END" if boundary_type == "END" else "NON_HAND_START")
    # Preferred-side metrics are intentionally blank for ambiguous events.
    preferred_row = None if ambiguous else next((row for row in rows if row.get("hand") == preferred), None)
    if preferred_row is None and not ambiguous:
        preferred_row = next((row for row in rows if _truth(row.get("hand_evidence"))), None)
    if ambiguous:
        reasons = "; ".join(f"{row['hand']}: {row.get('evidence_reason', '')}" for row in rows)
    else:
        reasons = (preferred_row or rows[0]).get("evidence_reason", "")
    def field(name):
        return (preferred_row or {}).get(name, "")
    return HandEvent(
        track_id=track_id, boundary_type=boundary_type, boundary_frame=frame,
        event_type=event_type, boundary_x=rows[0].get("boundary_x", ""), boundary_y=rows[0].get("boundary_y", ""),
        eligible_hand_set=eligible, preferred_hand=preferred, ambiguous=ambiguous,
        hand_evidence=evidence, evidence_reason=reasons,
        video_start_boundary=frame == frame_min, video_end_boundary=frame == frame_max,
        proximity_band=field("proximity_band"), motion=field("motion"),
        endpoint_distance_px=field("endpoint_distance_px"), endpoint_distance_normalized=field("endpoint_distance_normalized"),
        recent_min_distance_px=field("recent_min_distance_px"), recent_min_distance_normalized=field("recent_min_distance_normalized"),
        post_contact=_truth(field("post_contact")),
    )


def load_logical_events(path: Path, frame_min: int, frame_max: int) -> list[HandEvent]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    grouped = _logical_group(rows)
    return [_event_from_rows(key, grouped[key], frame_min, frame_max) for key in sorted(grouped, key=lambda k: (k[2], k[1], k[0]))]


def write_events(events: list[HandEvent], path: Path) -> None:
    fields = ["track_id", "boundary_type", "boundary_frame", "event_type", "boundary_x", "boundary_y",
              "eligible_hand_set", "preferred_hand", "ambiguous", "hand_evidence", "evidence_reason",
              "video_start_boundary", "video_end_boundary", "proximity_band", "motion",
              "endpoint_distance_px", "endpoint_distance_normalized", "recent_min_distance_px",
              "recent_min_distance_normalized", "post_contact"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for e in events:
            w.writerow({"track_id": e.track_id, "boundary_type": e.boundary_type, "boundary_frame": e.boundary_frame,
                        "event_type": e.event_type, "boundary_x": e.boundary_x, "boundary_y": e.boundary_y,
                        "eligible_hand_set": e.eligible_hand_set, "preferred_hand": e.preferred_hand or "",
                        "ambiguous": int(e.ambiguous), "hand_evidence": int(e.hand_evidence),
                        "evidence_reason": e.evidence_reason, "video_start_boundary": int(e.video_start_boundary),
                        "video_end_boundary": int(e.video_end_boundary), "proximity_band": e.proximity_band,
                        "motion": e.motion, "endpoint_distance_px": e.endpoint_distance_px,
                        "endpoint_distance_normalized": e.endpoint_distance_normalized,
                        "recent_min_distance_px": e.recent_min_distance_px,
                        "recent_min_distance_normalized": e.recent_min_distance_normalized,
                        "post_contact": int(e.post_contact)})


def _hand_label(event: HandEvent) -> str:
    if event.ambiguous:
        return f"{event.eligible_hand_set} AMBIGUOUS"
    return event.preferred_hand or event.eligible_hand_set or "-"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--assessments", type=Path, required=True)
    p.add_argument("--frame-min", type=int, required=True)
    p.add_argument("--frame-max", type=int, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    args = p.parse_args()
    events = load_logical_events(args.assessments, args.frame_min, args.frame_max)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_events(events, args.output_csv)
    for e in events:
        print(f"{e.boundary_frame:4d}  {e.event_type:<15} T{e.track_id:<2} {_hand_label(e)}")
    print(f"counts: HAND_ENTRY={sum(e.event_type == 'HAND_ENTRY' for e in events)} HAND_EXIT={sum(e.event_type == 'HAND_EXIT' for e in events)} NON_HAND_END={sum(e.event_type == 'NON_HAND_END' for e in events)} NON_HAND_START={sum(e.event_type == 'NON_HAND_START' for e in events)} ambiguous={sum(e.ambiguous for e in events)}")
    print("human transition diagnostic:")
    for src, end, dst, start, hand in [(3,149,4,152,"RIGHT"),(4,217,6,224,"RIGHT"),(1,219,5,223,"LEFT"),(5,841,10,845,"LEFT"),(2,882,11,885,"LEFT"),(6,950,13,953,"LEFT"),(10,1074,14,1077,"RIGHT")]:
        se = next(e for e in events if e.track_id == src and e.boundary_type == "END" and e.boundary_frame == end)
        te = next(e for e in events if e.track_id == dst and e.boundary_type == "START" and e.boundary_frame == start)
        print(f"{src} END {end} -> {dst} START {start} expected {hand}: {se.event_type}/{_hand_label(se)} -> {te.event_type}/{_hand_label(te)}")


if __name__ == "__main__":
    main()
