#!/usr/bin/env python3
"""H12 v2 sensitivity grid on K_EVENTS and MIN_EVENTS_FOR_PATTERN.

H12 v2 default uses K=4, MIN=3. This script sweeps:
  K_EVENTS in {2, 3, 4, 5, 6}
  MIN_EVENTS_FOR_PATTERN in {2, 3, 4}

Saves pattern distribution per cell. Goal: identify the (K, MIN) cell that
is in a flat region for identical (so threshold choice is well-justified).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Import the v2 classifier by reading its source and re-implementing
# the relevant parts with parameter overrides.
sys.path.insert(0, str(Path(__file__).parent))
from h12_v2_sliding_window import (
    load_census, load_events, hand_alternation_metric, catch_rate,
    K_EVENTS as DEFAULT_K, MIN_EVENTS_FOR_PATTERN as DEFAULT_MIN
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def classify_with_params(events_window, q, n_h_l, n_h_r,
                          min_events, k_events):
    """Reimplementation of classify_3ball with overridden thresholds."""
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]
    same_run = metrics["same_hand_run"]
    alt = metrics["alternation_score"]

    if n < min_events:
        if n_h_l == 1 and n_h_r == 1:
            return "MIXED_3+_UNCONFIRMED", q * 0.6, same_run, alt, rate
        if n_h_l >= 2 or n_h_r >= 2:
            return "MIXED_3+_UNCONFIRMED", q * 0.6, same_run, alt, rate
        return "MIXED_3+_UNCONFIRMED", q * 0.5, same_run, alt, rate

    cascade_like = (same_run <= 1 and alt >= 0.5 and rate >= 1.0)
    fountain_like = (same_run >= n - 1 and alt < 0.3)

    if cascade_like and not fountain_like:
        return "CASCADE_3+", q, same_run, alt, rate
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", q, same_run, alt, rate
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", q, same_run, alt, rate
        return "FOUNTAIN_3+", q, same_run, alt, rate
    return "MIXED_3+", q, same_run, alt, rate


def classify_frame(census_row, events_sorted, k_events, min_events):
    f = census_row["frame"]
    n_total = census_row["n_total"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    q = census_row["avg_quality"]

    if n_total == 0:
        return "NO_BALL", 1.0
    if n_total == 1:
        return "SINGLE_BALL", max(q, 0.0)
    if n_total == 2:
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", max(q, 0.0)
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", max(q, 0.0)
        return "TWO_BALL", max(q, 0.0)
    if n_total >= 3:
        events_before = [e for e in events_sorted
                          if int(e["event_frame"]) <= f]
        events_window = events_before[-k_events:]
        pattern, conf, _, _, _ = classify_with_params(
            events_window, q, n_h_l, n_h_r, min_events, k_events)
        return pattern, conf
    return "UNKNOWN", max(q, 0.0)


def main():
    grid = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        census = load_census(stem)
        events = load_events(stem)
        events_sorted = sorted(events, key=lambda e: int(e["event_frame"]))

        grid["videos"][stem] = {}
        for k in [2, 3, 4, 5, 6]:
            for min_ in [2, 3, 4]:
                counts = defaultdict(int)
                for f, c in sorted(census.items()):
                    cr = {"frame": f, "n_total": c["n_total"],
                          "n_in_hand_left": c["n_in_hand_left"],
                          "n_in_hand_right": c["n_in_hand_right"],
                          "avg_quality": c["avg_quality"]}
                    pat, _ = classify_frame(cr, events_sorted, k, min_)
                    counts[pat] += 1
                n = sum(counts.values())
                key = f"K={k}_MIN={min_}"
                grid["videos"][stem][key] = {
                    "n_total": n,
                    "pct": {p: round(100 * v / n, 2) for p, v in counts.items()},
                    "n_unique": len(counts),
                }
                # print summary
                top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
                top3_str = ", ".join(f"{p}={100*v/n:.1f}%" for p, v in top3)
                print(f"  K={k} MIN={min_}: {top3_str} ({len(counts)} classes)")

    out = H1_DATA / "h12_v2_sensitivity.json"
    out.write_text(json.dumps(grid, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
