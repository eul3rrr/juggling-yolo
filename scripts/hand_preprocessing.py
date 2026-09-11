"""Manifest-oriented hand preprocessing built from the existing hand engines."""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import hand_association as ha
import hand_boundaries as hb
import hand_events as he
import hand_state_machine as sm
from src.annotation.preprocessing import selected_frame_ranges


HAND_ASSOCIATION_VERSION = "v1-segment-fifo-1"


def hand_config_dict(cfg: ha.HandAssociationConfig | None = None) -> dict:
    """Return the exact threshold/configuration payload pinned in a manifest."""
    return dataclasses.asdict(cfg or ha.HandAssociationConfig())


def hand_config_manifest(cfg: ha.HandAssociationConfig | None = None) -> dict:
    return {"version": HAND_ASSOCIATION_VERSION,
            "config": hand_config_dict(cfg)}


def match_hand_events_by_segment(segment_events, fps: float,
                                 expiry_seconds: float = 5.0) -> sm.MatchResult:
    """Run the existing FIFO matcher independently for every segment."""
    associations = []
    unmatched = []
    trace = []
    for _segment_index, events in segment_events:
        result = sm.match_hand_events(events, fps, expiry_seconds)
        associations.extend(result.associations)
        unmatched.extend(result.unmatched)
        trace.extend(result.trace)
    return sm.MatchResult(associations, unmatched, trace)


def write_associations_by_segment(segment_events, fps: float, output: Path,
                                  expiry_seconds: float = 5.0) -> sm.MatchResult:
    result = match_hand_events_by_segment(segment_events, fps, expiry_seconds)
    output.parent.mkdir(parents=True, exist_ok=True)
    sm.write_associations(result.associations, output)
    return result


def build_hand_artifacts(tracklets_path: Path, hands_path: Path, segments,
                         fps: float, output_dir: Path,
                         cfg: ha.HandAssociationConfig | None = None,
                         frame_count: int | None = None) -> dict[str, Path]:
    """Create hands diagnostics and canonical links for selected segments.

    Tracklets are already globally remapped by the existing Norfair pipeline.
    This function never renumbers them and never passes state between segment
    runs.
    """
    cfg = cfg or ha.HandAssociationConfig()
    tracklets = hb.load_observed_tracklets(tracklets_path)
    assessments = []
    segment_events = []
    if frame_count is None:
        frame_count = max(
            (point.frame for points in tracklets.values() for point in points),
            default=0) + 1
    ranges = selected_frame_ranges(fps, frame_count, segments)
    for segment_index, (start, end) in enumerate(ranges):
        selected_tracklets = {
            tid: [point for point in points if start <= point.frame < end]
            for tid, points in tracklets.items()
        }
        selected_tracklets = {
            tid: points for tid, points in selected_tracklets.items() if points
        }
        hands_by_frame = ha._load_hands_by_frame(
            hands_path, cfg.confidence_threshold, segment_index=segment_index)
        segment_assessments = hb.assess_all(selected_tracklets,
                                            hands_by_frame)
        assessments.extend(segment_assessments)
        rows = hb.assessment_rows(segment_assessments)
        segment_events.append((segment_index, he.logical_events_from_rows(
            rows, start, end - 1)))

    output_dir.mkdir(parents=True, exist_ok=True)
    assessments_path = output_dir / "hand_assessments.csv"
    events_path = output_dir / "hand_events.csv"
    associations_path = output_dir / "hand_associations.csv"
    unmatched_path = output_dir / "unmatched_hand_events.csv"
    trace_path = output_dir / "hand_state_trace.csv"
    hb.write_csv(assessments, assessments_path)
    all_events = [event for _, events in segment_events for event in events]
    he.write_events(all_events, events_path)
    result = write_associations_by_segment(
        segment_events, fps, associations_path,
        expiry_seconds=cfg.safety_expiry_seconds,
    )
    sm.write_unmatched(result.unmatched, unmatched_path)
    sm.write_trace(result.trace, trace_path)
    return {
        "hands": hands_path,
        "hand_assessments": assessments_path,
        "hand_events": events_path,
        "hand_associations": associations_path,
        "unmatched_hand_events": unmatched_path,
        "hand_state_trace": trace_path,
    }
