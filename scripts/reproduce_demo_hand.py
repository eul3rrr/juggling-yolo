#!/usr/bin/env python3
"""Reproduce the frozen demo CSVs without inference, video, or algorithm changes.

See docs/HAND_REPRODUCTION.md: the historical augmented pose fixture is NOT
interchangeable with the wrist-only yolo26s-pose.csv shipped in detections/.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import hand_boundaries as hb
import hand_events as he
import hand_state_machine as sm

ROOT = Path(__file__).resolve().parents[1]
STEM = "identical_balls_trick_000_018"
TRACKLETS = ROOT / "detections/demo" / f"{STEM}_yolo26l_classes-32_norfair_dt50_hc5.csv"
HANDS = ROOT / "tests/fixtures/demo_hand" / f"{STEM}_yolo26s-pose-hands.csv"
# Exact historical serialization rate (not rounded 59.94 or 60000/1001).
FPS = 59.94005994
FRAME_MIN, FRAME_MAX = 2, 1078


def reproduce(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty; existing artifacts are never overwritten")
    output_dir.mkdir(parents=True, exist_ok=True)
    tracklets = hb.load_observed_tracklets(TRACKLETS)
    hands = hb.ha._load_hands_by_frame(HANDS, hb.CONFIG.confidence_threshold)
    boundaries_path = output_dir / f"{STEM}_hand_boundary_assessments.csv"
    hb.write_csv(hb.assess_all(tracklets, hands), boundaries_path)
    events_path = output_dir / f"{STEM}_hand_events.csv"
    he.write_events(he.load_logical_events(boundaries_path, FRAME_MIN, FRAME_MAX), events_path)
    result = sm.match_hand_events(sm.load_hand_events(events_path), FPS)
    sm.write_associations(result.associations, output_dir / f"{STEM}_hand_associations.csv")
    sm.write_trace(result.trace, output_dir / f"{STEM}_hand_state_trace.csv")
    sm.write_unmatched(result.unmatched, output_dir / f"{STEM}_unmatched_hand_events.csv")
    for suffix in ("hand_events", "hand_associations", "hand_state_trace"):
        name = f"{STEM}_{suffix}.csv"
        if (output_dir / name).read_bytes() != (ROOT / "detections/demo" / name).read_bytes():
            raise RuntimeError(f"Frozen demo mismatch: {name}; no differences are accepted")
        print(f"BYTE-EXACT {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    reproduce(args.output_dir)


if __name__ == "__main__":
    main()
