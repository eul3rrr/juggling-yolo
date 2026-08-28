#!/usr/bin/env python3
"""H49: measure 10-frame filter's impact on per-frame H12 v8 pattern.

HYPOTHESIS:
  H47 applied the 10-frame filter to H12 v8's event log and
  found it drops 3/48 events on identical. H48 confirmed
  THR=10 is in a flat region of the sensitivity grid.

  Question: what is the actual downstream impact on H12 v8's
  per-frame pattern classification? Which specific frames
  change pattern after the filter?

METHOD:
  1. Load H12 v8's per-frame pattern labels
     (pattern_inference_h35_*.csv).
  2. Load H12 v8's event log (chain_events_h35_*.csv).
  3. Identify the (chain_id, tid) pairs whose flight time
     is < 10 frames.
  4. Find the per-frame K=4 sliding window context for each
     dropped pair: what was the window before/after the drop?
  5. Re-classify those frames using H12 v8's pattern logic
     (simplified: K=4 events, hand alternation metric).
  6. Compare the re-classified frames' patterns to the
     original H12 v8 labels.
  7. Report the count of frames whose pattern changes.

  This is a measurement of filter impact, not a re-run of
  H12 v8's full pipeline.
"""
from __future__ import annotations

import csv
import json
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

K_EVENTS = 4
MIN_EVENTS_FOR_PATTERN = 3
MIN_FLIGHT_TIME = 10


def load_events(stem: str) -> list[dict]:
    events = []
    with (H1_DATA / f"chain_events_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["event_frame"] = int(r["event_frame"])
            r["chain_id"] = int(r["chain_id"])
            r["tid"] = int(r["tid"])
            events.append(r)
    return events


def load_pattern(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            rows.append(r)
    return rows


def compute_flight_times(events: list[dict]) -> dict[tuple, int]:
    """Map (chain_id, src_tid) -> flight_time to next CATCH."""
    by_chain = defaultdict(list)
    for e in events:
        by_chain[e["chain_id"]].append(e)
    flights = {}
    for cid, evs in by_chain.items():
        evs = sorted(evs, key=lambda e: e["event_frame"])
        for j, e in enumerate(evs):
            if e["event"] != "THROW":
                continue
            for k in range(j + 1, len(evs)):
                next_e = evs[k]
                if next_e["event"] == "CATCH" and next_e["tid"] != e["tid"]:
                    flights[(cid, e["tid"])] = (
                        next_e["event_frame"] - e["event_frame"]
                    )
                    break
    return flights


def identify_dropped_tids(events: list[dict], flights: dict, min_ft: int):
    """Identify (chain_id, tid) pairs whose flight time < min_ft.
    Returns a set of (chain_id, tid) keys to drop."""
    dropped = set()
    for (cid, src_tid), ft in flights.items():
        if ft < min_ft:
            dropped.add((cid, src_tid))
            # Also drop the tgt_tid in the same flight
            for e in events:
                if e["chain_id"] == cid and e["tid"] == src_tid and e["event"] == "THROW":
                    for e2 in events:
                        if (e2["chain_id"] == cid and e2["event"] == "CATCH"
                                and e2["tid"] != src_tid
                                and e2["event_frame"] > e["event_frame"]):
                            dropped.add((cid, e2["tid"]))
                            break
                    break
    return dropped


def classify_window(events_window: list[dict]) -> str:
    """Classify a K=4 sliding window of events.
    Simplified H12 v8 logic: CASCADE_3+ if hand-alternation
    on THROW events, FOUNTAIN_3+ if same-hand.
    """
    if len(events_window) < MIN_EVENTS_FOR_PATTERN:
        return "UNKNOWN"
    hands = [e["hand"] for e in events_window if e["event"] == "THROW"]
    unique_hands = len(set(hands))
    n_catches = sum(1 for e in events_window if e["event"] == "CATCH")
    n_throws = sum(1 for e in events_window if e["event"] == "THROW")
    catch_rate = n_catches / max(1, n_throws)
    if unique_hands <= 1:
        return "FOUNTAIN_3+"
    if unique_hands == 2 and catch_rate >= 1.0:
        return "CASCADE_3+"
    return "MIXED_3+"


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        events = load_events(stem)
        patterns = load_pattern(stem)
        flights = compute_flight_times(events)
        # Identify dropped (chain_id, tid) pairs
        dropped = identify_dropped_tids(events, flights, MIN_FLIGHT_TIME)
        print(f"  Total events: {len(events)}")
        print(f"  Total flights: {len(flights)}")
        print(f"  Dropped (chain_id, tid) pairs: {len(dropped)}")
        # Filter events
        filtered_events = [e for e in events
                           if (e["chain_id"], e["tid"]) not in dropped]
        print(f"  Filtered events: {len(filtered_events)} "
              f"(dropped {len(events) - len(filtered_events)})")
        # Sort by event_frame
        filtered_events.sort(key=lambda e: e["event_frame"])
        # For each frame, compute K=4 window classification
        # (with and without filter) and compare
        # Note: H12 v8 baseline uses (n_in_air, n_in_hand_left, n_in_hand_right)
        # census, not just K=4 events. We approximate with K=4 events.
        # For each frame in patterns, find the K=4 most recent events
        # (before this frame).
        changes = []
        n_total = 0
        n_unchanged = 0
        n_changed = 0
        for p in patterns:
            f = p["frame"]
            n_total += 1
            # Original K=4 window from H12 v8 events
            recent_orig = [e for e in events if e["event_frame"] < f][-K_EVENTS:]
            # Filtered K=4 window
            recent_filt = [e for e in filtered_events
                           if e["event_frame"] < f][-K_EVENTS:]
            # Classify
            pat_orig = classify_window(recent_orig)
            pat_filt = classify_window(recent_filt)
            if pat_orig != pat_filt:
                n_changed += 1
                if len(changes) < 10:  # log first 10
                    changes.append({
                        "frame": f,
                        "orig_pattern": pat_orig,
                        "filt_pattern": pat_filt,
                        "h12v8_pattern": p["pattern"],
                        "h12v8_confidence": float(p.get("confidence", 0)),
                    })
            else:
                n_unchanged += 1
        pct_changed = 100 * n_changed / max(1, n_total)
        print(f"  Frames re-classified by filter: {n_changed}/{n_total} "
              f"({pct_changed:.2f}%)")
        print(f"  Sample changes (first 10):")
        for c in changes:
            print(f"    f={c['frame']}: {c['orig_pattern']} -> {c['filt_pattern']} "
                  f"(H12 v8: {c['h12v8_pattern']} conf={c['h12v8_confidence']:.2f})")
        summary["videos"][stem] = {
            "n_events": len(events),
            "n_events_dropped": len(events) - len(filtered_events),
            "n_dropped_pairs": len(dropped),
            "n_frames_total": n_total,
            "n_frames_changed": n_changed,
            "pct_frames_changed": round(pct_changed, 3),
            "n_sample_changes": len(changes),
            "sample_changes": changes,
        }
    out = H1_DATA / "h49_filter_impact_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
