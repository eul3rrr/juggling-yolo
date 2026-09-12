"""Reusable split and held-out detector/tracker benchmark logic."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import random
from statistics import mean, median

from scripts.review_track_events import generate_events
from src.annotation.mining import unresolved_boundary_frames, unresolved_event_near_segment_edge
from src.annotation.segments import segment_for_frame


def detector_arms(baseline_model: str, finetuned_model: Path) -> dict[str, dict]:
    """Return the deliberately asymmetric class filters for the two checkpoints."""
    return {
        "baseline": {"model": str(baseline_model), "classes": [32]},
        "finetuned": {"model": str(finetuned_model), "classes": [0]},
    }


def attach_segment_metadata(records: list[dict]) -> list[dict]:
    """Recover legacy saved items' segment from their immutable source metadata."""
    enriched = []
    for record in records:
        row = deepcopy(record)
        if not isinstance(row.get("segment"), dict):
            timestamp = float(row["timestamp"])
            segment = next((candidate for candidate in row["source"]["segments"]
                            if float(candidate["start"]) <= timestamp < float(candidate["end"])), None)
            if segment is None:
                raise ValueError(f"Frame {row.get('frame')} is outside source LosslessCut segments")
            row["segment"] = deepcopy(segment)
        enriched.append(row)
    return enriched


def _segment_key(record: dict) -> tuple:
    segment = record.get("segment")
    if not isinstance(segment, dict):
        raise ValueError("Every exported annotation needs LosslessCut segment metadata")
    return (int(segment["index"]),)


def split_records_by_segment(records: list[dict], val_fraction: float = 0.18,
                             seed: int | None = None) -> list[dict]:
    """Assign complete segments to a deterministic count-balanced train/val split."""
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between zero and one")
    if not records:
        return []
    groups = Counter(_segment_key(record) for record in records)
    if len(groups) < 2:
        raise ValueError("At least two annotated segments are required for a leakage-safe split")
    # Subset-sum over segment image counts.  Values store lexicographically stable keys.
    choices: dict[int, tuple[tuple, ...]] = {0: ()}
    group_keys = sorted(groups)
    if seed is not None:
        random.Random(seed).shuffle(group_keys)
    for key in group_keys:
        count = groups[key]
        additions = {total + count: selected + (key,) for total, selected in choices.items()}
        for total, selected in additions.items():
            choices.setdefault(total, selected)
    target = len(records) * val_fraction
    valid = ((total, selected) for total, selected in choices.items() if 0 < total < len(records))
    _, val_keys = min(valid, key=lambda pair: (abs(pair[0] - target), pair[0], pair[1]))
    val_set = set(val_keys)
    result = []
    for record in records:
        row = deepcopy(record)
        row["split"] = "val" if _segment_key(record) in val_set else "train"
        result.append(row)
    return result


def build_hard_events(model_arm: str, tracks: dict, fps: float, frame_count: int, segments: list) -> list[dict]:
    """Build END/orphan events with the exact annotation-mining edge exclusion."""
    events = []
    for segment in segments:
        segment_tracks = {}
        for track_id, track in tracks.items():
            observed = track.observed
            if observed and any(segment_for_frame(row.frame, fps, [segment]) is not None for row in observed):
                segment_tracks[track_id] = track
        for event in generate_events(segment_tracks, {}, fps, frame_count,
                                     include_existing_stitches=False,
                                     include_orphan_starts=True):
            if event.kind not in ("end", "orphan_start"):
                continue
            if unresolved_event_near_segment_edge(event.primary_end_frame, fps, frame_count, [segment]):
                continue
            events.append({
                "model_arm": model_arm,
                "event_key": event.event_key,
                "event_kind": "track_end" if event.kind == "end" else "orphan_start",
                "track_id": event.primary.track_id,
                "event_frame": event.primary_end_frame,
                "segment": segment.as_dict(),
                "center_x": event.primary_end_x,
                "center_y": event.primary_end_y,
            })
    return sorted(events, key=lambda row: (row["event_frame"], row["event_kind"], row["track_id"]))


def build_union_frames(baseline_events: list[dict], finetuned_events: list[dict],
                       fps: float, frame_count: int) -> list[dict]:
    """Union both independently generated hard-frame neighborhoods."""
    by_frame: dict[int, list[dict]] = {}
    for event in [*baseline_events, *finetuned_events]:
        for frame in unresolved_boundary_frames(event["event_frame"], fps, frame_count):
            provenance = {key: event[key] for key in
                          ("model_arm", "event_key", "event_kind", "event_frame")}
            if provenance not in by_frame.setdefault(frame, []):
                by_frame[frame].append(provenance)
    return [{"frame": frame, "provenance": sorted(provenance, key=lambda row: tuple(row.values()))}
            for frame, provenance in sorted(by_frame.items())]


def classify_multi_provenance(provenance: list[dict], all_arms: dict) -> str:
    """Return a stable category for any subset of arms in a union frame."""
    present = sorted({row["model_arm"] for row in provenance})
    known = set(all_arms)
    if not present or not set(present) <= known:
        raise ValueError(f"Invalid provenance arms: {present}")
    if set(present) == known:
        return "all"
    if len(present) == 1:
        return f"{present[0]}_only"
    return "+".join(present)


def build_union_frames_multi(events_by_arm: dict[str, list[dict]], fps: float,
                             frame_count: int) -> list[dict]:
    """Union unresolved neighborhoods across an arbitrary number of arms."""
    by_frame: dict[int, list[dict]] = {}
    for arm in sorted(events_by_arm):
        for event in events_by_arm[arm]:
            for frame in unresolved_boundary_frames(event["event_frame"], fps, frame_count):
                provenance = {key: event[key] for key in
                              ("model_arm", "event_key", "event_kind", "event_frame")}
                if provenance not in by_frame.setdefault(frame, []):
                    by_frame[frame].append(provenance)
    return [{
        "frame": frame,
        "provenance": sorted(provenance, key=lambda row: tuple(row.values())),
        "selection": classify_multi_provenance(provenance, events_by_arm),
    } for frame, provenance in sorted(by_frame.items())]


def classify_provenance(provenance: list[dict]) -> str:
    arms = {row["model_arm"] for row in provenance}
    if arms == {"baseline", "finetuned"}:
        return "both"
    if arms == {"baseline"}:
        return "baseline_only"
    if arms == {"finetuned"}:
        return "finetuned_only"
    raise ValueError(f"Invalid provenance arms: {sorted(arms)}")


def summarize_arm(detections: list[dict], tracks: dict, events: list[dict],
                  selected_duration_seconds: float) -> dict:
    if selected_duration_seconds <= 0:
        raise ValueError("selected duration must be positive")
    lengths = [len(track.observed) for track in tracks.values() if track.observed]
    kinds = Counter(event["event_kind"] for event in events)
    total_events = kinds["track_end"] + kinds["orphan_start"]
    return {
        "selected_duration_seconds": selected_duration_seconds,
        "total_detections": len(detections),
        "frames_with_detections": len({int(row["frame"]) for row in detections}),
        "total_tracklets": len(lengths),
        "median_observed_tracklet_length": median(lengths) if lengths else 0,
        "mean_observed_tracklet_length": mean(lengths) if lengths else 0,
        "tracklets_shorter_than_3": sum(length < 3 for length in lengths),
        "tracklets_shorter_than_6": sum(length < 6 for length in lengths),
        "tracklets_at_least_15": sum(length >= 15 for length in lengths),
        "track_end_events": kinds["track_end"],
        "orphan_start_events": kinds["orphan_start"],
        "total_unresolved_events": total_events,
        "unresolved_events_per_minute": total_events / (selected_duration_seconds / 60),
    }


def viewer_frame_payload(frame: int, detections_by_arm: dict[str, dict[int, list[dict]]]) -> dict:
    return {
        "frame": frame,
        "raw_frame": f"/frame?frame={frame}",
        "panels": {
            arm: {"frame": frame, "detections": rows.get(frame, [])}
            for arm, rows in detections_by_arm.items()
        },
    }


def build_benchmark(*, tracks_by_arm: dict, detections_by_arm: dict,
                    fps: float, frame_count: int, segments: list,
                    selected_duration_seconds: float) -> dict:
    """Build independent events, their union, and matched-duration summaries."""
    events = {arm: build_hard_events(arm, tracks_by_arm[arm], fps, frame_count, segments)
              for arm in ("baseline", "finetuned")}
    frames = build_union_frames(events["baseline"], events["finetuned"], fps, frame_count)
    for row in frames:
        row["selection"] = classify_provenance(row["provenance"])
    summaries = {
        arm: summarize_arm(
            [row for values in detections_by_arm[arm].values() for row in values],
            tracks_by_arm[arm], events[arm], selected_duration_seconds,
        ) for arm in ("baseline", "finetuned")
    }
    return {"events": events, "frames": frames, "summaries": summaries}
