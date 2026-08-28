#!/usr/bin/env python3
"""H47: H12 v8 with 10-frame flight-time filter (H45 v8 filter).

HYPOTHESIS:
  H45 found that the H12 v8 hand-event "flight times" include
  both real catch-throws (>= 30 frame flight times on identical)
  and identity switches / tracker fragmentations (< 10 frame
  flight times on identical, or >= 58 frame on YouTube).

  A simple 10-frame flight-time filter would drop the identity
  switches on identical, leaving a cleaner event log. The
  filtered event log should produce a better H12 v8 pattern
  classification.

  This is the H45 v8 filter applied to H12 v8. It validates
  H45's most actionable finding (the 10-frame filter) as a
  downstream consumer of H12 v8.

METHOD:
  1. Load H12 v8's catch/throw event log (chain_events_h35_*.csv).
  2. For each (CATCH, THROW) pair on the same tracklet within
     the same chain, compute the flight time (THROW event_frame
     to next CATCH event_frame in same chain).
  3. Tag each event with the "flight time" of the source flight
     (i.e., the time from the event's THROW to the next CATCH).
  4. Drop any event whose source flight time < 10 frames.
  5. Re-run H12 v8's per-frame pattern inference on the
     filtered events.
  6. Compare pattern distribution to H12 v8 baseline.

  THRESHOLD: 10 frames, declared from H45's finding that
  identical's < 10-frame "flights" (1, 3, 5 frames) are
  ALL identity switches.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H12 v8 thresholds (from h12_v8_h7v3pure_patterns.py)
K_EVENTS = 4
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0
RECENT_EVENT_FRAMES = 30
MIN_EVENTS_FOR_PATTERN = 3

# H47 threshold
MIN_FLIGHT_TIME = 10  # frames; H45 finding: < 10 = identity switch


def load_events(stem: str) -> list[dict]:
    events = []
    with (H1_DATA / f"chain_events_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["event_frame"] = int(r["event_frame"])
            r["chain_id"] = int(r["chain_id"])
            r["tid"] = int(r["tid"])
            events.append(r)
    return events


def compute_flight_times(events: list[dict]) -> dict[int, int]:
    """For each event, compute the flight time to the next
    CATCH in the same chain (with different tid).

    Returns: dict mapping event index -> flight_time
    """
    by_chain = defaultdict(list)
    for i, e in enumerate(events):
        by_chain[e["chain_id"]].append(i)
    flight_times = {}
    for cid, indices in by_chain.items():
        # Sort by event_frame
        chain_events = sorted(indices, key=lambda i: events[i]["event_frame"])
        for j, idx in enumerate(chain_events):
            e = events[idx]
            if e["event"] != "THROW":
                continue
            # Find next CATCH in same chain
            for k in range(j + 1, len(chain_events)):
                next_e = events[chain_events[k]]
                if next_e["event"] == "CATCH" and next_e["tid"] != e["tid"]:
                    flight_times[idx] = next_e["event_frame"] - e["event_frame"]
                    break
    return flight_times


def filter_events(events: list[dict], flight_times: dict[int, int],
                  min_ft: int) -> list[dict]:
    """Drop events whose source flight time < min_ft.

    For CATCH events, the source flight is the flight time of
    the previous THROW in the same chain. For THROW events, the
    source flight is the flight time of THIS throw (to the next
    catch).

    Strategy: drop a (CATCH, THROW) pair if the THROW's flight
    time is < min_ft.
    """
    out = []
    # Group events by chain in time order
    by_chain = defaultdict(list)
    for i, e in enumerate(events):
        by_chain[e["chain_id"]].append(i)
    dropped_pairs = 0
    for cid, indices in by_chain.items():
        chain_events = sorted(indices, key=lambda i: events[i]["event_frame"])
        for j, idx in enumerate(chain_events):
            e = events[idx]
            ft = flight_times.get(idx)
            if e["event"] == "THROW" and ft is not None and ft < min_ft:
                # Drop this THROW and the corresponding CATCH
                dropped_pairs += 1
                # The CATCH is the previous event in the chain
                if j > 0 and events[chain_events[j - 1]]["event"] == "CATCH":
                    continue  # skip CATCH too
                out.append(e)
            else:
                out.append(e)
    return out


def main() -> None:
    summary = {"videos": {}, "config": {"MIN_FLIGHT_TIME": MIN_FLIGHT_TIME}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        events = load_events(stem)
        flight_times = compute_flight_times(events)
        # Stats on flight times
        fts = list(flight_times.values())
        n_short = sum(1 for ft in fts if ft < MIN_FLIGHT_TIME)
        print(f"  Total events: {len(events)}")
        print(f"  Total flights with computed time: {len(fts)}")
        print(f"  Flights < {MIN_FLIGHT_TIME} frames: {n_short}")
        if fts:
            print(f"  Flight time mean={statistics.mean(fts):.1f}, "
                  f"median={statistics.median(fts):.1f}, "
                  f"min={min(fts)}, max={max(fts)}")

        # Filter
        filtered = filter_events(events, flight_times, MIN_FLIGHT_TIME)
        n_dropped = len(events) - len(filtered)
        print(f"  Dropped {n_dropped} events ({100*n_dropped/len(events):.1f}%)")

        # Re-run pattern inference
        # We implement a simplified version: per-frame pattern
        # from K=4 sliding window of recent events.
        pattern_dist = compute_pattern_distribution(filtered)
        print(f"  Pattern distribution (filtered):")
        for pat, n in sorted(pattern_dist.items(), key=lambda x: -x[1]):
            print(f"    {pat}: {n} frames ({100*n/sum(pattern_dist.values()):.1f}%)")

        # Compare to H12 v8 baseline
        baseline_dist = load_h12v8_pattern_dist(stem)
        if baseline_dist:
            print(f"  Pattern distribution (H12 v8 baseline):")
            for pat, n in sorted(baseline_dist.items(), key=lambda x: -x[1]):
                print(f"    {pat}: {n} frames ({100*n/sum(baseline_dist.values()):.1f}%)")

        summary["videos"][stem] = {
            "n_events_total": len(events),
            "n_flights_with_time": len(fts),
            "n_short_flights": n_short,
            "n_events_dropped": n_dropped,
            "flight_time_min": min(fts) if fts else None,
            "flight_time_max": max(fts) if fts else None,
            "flight_time_median": statistics.median(fts) if fts else None,
            "pattern_dist_filtered": pattern_dist,
            "pattern_dist_baseline": baseline_dist,
        }

    out_summary = H1_DATA / "h47_flight_time_filter_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out_summary}")


def compute_pattern_distribution(events: list[dict]) -> dict[str, int]:
    """Simplified H12 v8 pattern distribution on filtered events.

    For each frame that has any event, determine the pattern
    based on the K=4 most recent events.
    """
    # Find frame range
    if not events:
        return {}
    fmin = min(e["event_frame"] for e in events)
    fmax = max(e["event_frame"] for e in events)
    # Sort events by frame
    sorted_events = sorted(events, key=lambda e: e["event_frame"])
    pattern_dist = defaultdict(int)
    for f in range(fmin, fmax + 1):
        # K=4 most recent events before this frame
        recent = [e for e in sorted_events
                  if e["event_frame"] < f][-K_EVENTS:]
        if len(recent) < MIN_EVENTS_FOR_PATTERN:
            pattern_dist["UNKNOWN"] += 1
            continue
        # Hand alternation metric
        hands = [e["hand"] for e in recent if e["event"] == "THROW"]
        unique_hands = len(set(hands))
        # Catch rate
        n_catches = sum(1 for e in recent if e["event"] == "CATCH")
        n_throws = sum(1 for e in recent if e["event"] == "THROW")
        catch_rate = n_catches / max(1, n_throws)
        # Decide pattern
        if unique_hands == 1:
            pattern = "FOUNTAIN_3+"
        elif unique_hands == 2 and catch_rate >= CASCADE_MIN_CATCH_RATE:
            pattern = "CASCADE_3+"
        elif unique_hands == 2:
            pattern = "MIXED_3+"
        else:
            pattern = "UNKNOWN"
        pattern_dist[pattern] += 1
    return dict(pattern_dist)


def load_h12v8_pattern_dist(stem: str) -> dict[str, int] | None:
    """Load H12 v8's per-frame pattern distribution if available."""
    p = H1_DATA / f"pattern_inference_h35_{stem}.csv"
    if not p.exists():
        return None
    dist = defaultdict(int)
    with p.open() as fh:
        for r in csv.DictReader(fh):
            dist[r.get("pattern", "UNKNOWN")] += 1
    return dict(dist)


if __name__ == "__main__":
    main()
