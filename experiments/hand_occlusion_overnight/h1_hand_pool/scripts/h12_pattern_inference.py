#!/usr/bin/env python3
"""H12 - per-frame juggling pattern inference.

For each frame, infer the juggling pattern based on:
- n_chains active (from H11 v2 census)
- which hands are active (from H11 v2 census)
- catch/throw events around the frame (from H11 v1 events)
- chain quality average (from H11 v2 census)

Pattern classes:
- NO_BALL: 0 chains (jugger has no ball)
- SINGLE_BALL: 1 chain
- TWO_BALL: 2 chains
- CASCADE_3: 3+ chains, alternating hands, regular intervals
- FOUNTAIN_3: 3+ chains, both balls thrown from same hand
- STATIONARY: 1 chain, low velocity
- UNKNOWN: pattern not classified

For each frame, emit:
- frame
- n_in_air
- n_in_hand
- hand_active (left/right/none)
- pattern
- confidence
- catch_or_throw_recent (last 30 frames)
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Pattern classification thresholds.
MIN_QUALITY_FOR_PATTERN = 0.5  # below this, pattern is UNKNOWN
RECENT_EVENT_FRAMES = 30  # how recent is "recent" for catch/throw


def load_census(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"per_frame_census_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "n_in_air": int(r["n_in_air"]),
                "n_in_hand_left": int(r["n_in_hand_left"]),
                "n_in_hand_right": int(r["n_in_hand_right"]),
                "n_total": int(r["n_total_balls"]),
                "avg_quality": float(r["avg_chain_quality"]),
            }
    return out


def load_events(stem: str) -> list[dict]:
    with (H1_DATA / f"catch_throw_timeline_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


def classify_pattern(census_row: dict, recent_events: list[dict]) -> tuple:
    """Return (pattern, confidence)."""
    n_total = census_row["n_total"]
    n_air = census_row["n_in_air"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    n_hand = n_h_l + n_h_r
    q = census_row["avg_quality"]

    if n_total == 0:
        return "NO_BALL", 1.0
    if q < MIN_QUALITY_FOR_PATTERN:
        return "UNKNOWN", q

    if n_total == 1:
        return "SINGLE_BALL", q

    if n_total == 2:
        # 2-ball: shower, columns, or 1 in each hand
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", q
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", q
        return "TWO_BALL", q

    if n_total >= 3:
        # 3+ ball: cascade (alternating) or fountain (both from same hand)
        if recent_events:
            hands = [e["hand"] for e in recent_events]
            unique_hands = set(hands)
            if len(unique_hands) == 1:
                return "FOUNTAIN_3+", q
            else:
                return "CASCADE_3+", q
        return "CASCADE_3+", q

    return "UNKNOWN", q


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        census = load_census(stem)
        events = load_events(stem)

        # Build per-frame event list
        events_by_frame = defaultdict(list)
        for e in events:
            events_by_frame[int(e["event_frame"])].append(e)

        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        for f, c in sorted(census.items()):
            # Recent events (within RECENT_EVENT_FRAMES)
            recent = []
            for df in range(-RECENT_EVENT_FRAMES, RECENT_EVENT_FRAMES + 1):
                recent.extend(events_by_frame.get(f + df, []))
            pattern, conf = classify_pattern(c, recent)
            results.append({
                "frame": f,
                "n_in_air": c["n_in_air"],
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total"],
                "avg_quality": c["avg_quality"],
                "pattern": pattern,
                "confidence": conf,
                "n_recent_events": len(recent),
            })
            pattern_counts[pattern] += 1

        # Print pattern distribution
        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        # Write CSV
        out = H1_DATA / f"pattern_inference_{stem}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out.name}")

        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "pattern_counts": dict(pattern_counts),
            "pct_patterns": {p: 100 * n / n_total_frames
                              for p, n in pattern_counts.items()},
        }

    out = H1_DATA / "h12_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
