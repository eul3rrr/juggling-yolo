#!/usr/bin/env python3
"""H48: sensitivity grid for H12 v8 flight-time filter thresholds.

HYPOTHESIS:
  H47 showed the 10-frame flight-time filter drops 3/48
  events on identical (small but real precision improvement)
  and 0/50 on YouTube (no-op because all flights are >= 58).

  A symmetric YouTube-specific filter would drop tracker-
  fragmented flights. The natural choice is a 50-frame
  upper bound: real 5-ball cascade flights are ~15-25 frames,
  so a 50-frame threshold is a 2x safety margin.

  H48 tests a sensitivity grid of flight-time thresholds
  on both videos and reports the per-threshold impact.

METHOD:
  1. Load H12 v8 event log.
  2. Compute per-flight flight times (THROW to next CATCH).
  3. Sweep MIN_FLIGHT_TIME in {5, 10, 15, 20, 30, 40, 50, 60}.
  4. For each threshold, count dropped events.
  5. Cross-reference with H45 visual-QA labels for the
     3 multi-flight chains (chain 22 identical, chain 29
     identical, chain 9 YouTube).

  THRESHOLDS declared from physical juggler limits:
    - 5f: catches even the shortest real throws
    - 10f: H45 recommended filter (drops ft=1, 3, 5)
    - 30f: drops any "flight" shorter than a typical 3-ball
      cascade ball airtime (1.0s at 30fps)
    - 50f: 5-ball cascade upper bound (2.0s for very high throws)
    - 100f: very permissive (likely all real flights still drop)
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

# H45 visual-QA labels for the 11 flights
H45_LABELS = {
    ("identical_balls_trick_000_018", 22, 40, 41): "REAL",
    ("identical_balls_trick_000_018", 22, 41, 45): "REAL",
    ("identical_balls_trick_000_018", 22, 45, 46): "REAL",
    ("identical_balls_trick_000_018", 22, 37, 40): "IDENTITY_SWITCH",
    ("identical_balls_trick_000_018", 29, 52, 54): "IDENTITY_SWITCH",
    ("identical_balls_trick_000_018", 29, 54, 59): "REAL",
    ("identical_balls_trick_000_018", 12, 23, 25): "IDENTITY_SWITCH",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 9, 22, 26): "TRACKER_FRAGMENTATION",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 9, 26, 31): "TRACKER_FRAGMENTATION",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 9, 31, 35): "TRACKER_FRAGMENTATION",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 9, 35, 38): "TRACKER_FRAGMENTATION",
}

THRESHOLDS = [5, 10, 15, 20, 30, 40, 50, 60]


def load_events(stem: str) -> list[dict]:
    events = []
    with (H1_DATA / f"chain_events_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["event_frame"] = int(r["event_frame"])
            r["chain_id"] = int(r["chain_id"])
            r["tid"] = int(r["tid"])
            events.append(r)
    return events


def compute_flight_times(events: list[dict]) -> list[dict]:
    """For each (chain, source_tid) pair, compute the flight time
    from THROW event_frame to next CATCH event_frame in same chain.

    Returns: list of {chain_id, src_tid, throw_frame, catch_frame,
    flight_time}.
    """
    by_chain = defaultdict(list)
    for e in events:
        by_chain[e["chain_id"]].append(e)
    flights = []
    for cid, evs in by_chain.items():
        evs = sorted(evs, key=lambda e: e["event_frame"])
        for j, e in enumerate(evs):
            if e["event"] != "THROW":
                continue
            for k in range(j + 1, len(evs)):
                next_e = evs[k]
                if next_e["event"] == "CATCH" and next_e["tid"] != e["tid"]:
                    flights.append({
                        "chain_id": cid,
                        "src_tid": e["tid"],
                        "tgt_tid": next_e["tid"],
                        "throw_frame": e["event_frame"],
                        "catch_frame": next_e["event_frame"],
                        "flight_time": next_e["event_frame"] - e["event_frame"],
                    })
                    break
    return flights


def main() -> None:
    print("=== H48: Flight-time filter sensitivity grid ===\n")
    summary = {"videos": {}, "config": {"THRESHOLDS": THRESHOLDS}}
    for stem in STEMS:
        events = load_events(stem)
        flights = compute_flight_times(events)
        # Mark each flight with H45 label if available
        for f in flights:
            label = H45_LABELS.get((stem, f["chain_id"], f["src_tid"], f["tgt_tid"]))
            f["h45_label"] = label or "UNKNOWN"
        # Stats
        fts = [f["flight_time"] for f in flights]
        labeled = [f for f in flights if f["h45_label"] != "UNKNOWN"]
        n_real = sum(1 for f in labeled if f["h45_label"] == "REAL")
        n_id = sum(1 for f in labeled if f["h45_label"] == "IDENTITY_SWITCH")
        n_tf = sum(1 for f in labeled if f["h45_label"] == "TRACKER_FRAGMENTATION")
        print(f"--- {stem} ---")
        print(f"  Total events: {len(events)}")
        print(f"  Total flights: {len(flights)}")
        print(f"  H45-labeled: {len(labeled)} "
              f"(REAL={n_real}, IDENTITY_SWITCH={n_id}, "
              f"TRACKER_FRAGMENTATION={n_tf})")
        if fts:
            print(f"  Flight time: min={min(fts)}, max={max(fts)}, "
                  f"median={statistics.median(fts):.0f}, "
                  f"mean={statistics.mean(fts):.1f}")
        # Per-threshold analysis
        print(f"  Per-threshold:")
        print(f"    {'THR':>4s} | {'dropped':>8s} | "
              f"{'kept REAL':>10s} | {'dropped REAL':>12s} | "
              f"{'kept ID':>8s} | {'dropped ID':>10s} | "
              f"{'kept TF':>8s} | {'dropped TF':>10s}")
        threshold_results = []
        for thr in THRESHOLDS:
            # Drop flights with flight_time < thr
            kept = [f for f in flights if f["flight_time"] >= thr]
            dropped = [f for f in flights if f["flight_time"] < thr]
            # Categorize
            def by_label(fs, label):
                return [f for f in fs if f["h45_label"] == label]
            kept_real = len(by_label(kept, "REAL"))
            dropped_real = len(by_label(dropped, "REAL"))
            kept_id = len(by_label(kept, "IDENTITY_SWITCH"))
            dropped_id = len(by_label(dropped, "IDENTITY_SWITCH"))
            kept_tf = len(by_label(kept, "TRACKER_FRAGMENTATION"))
            dropped_tf = len(by_label(dropped, "TRACKER_FRAGMENTATION"))
            print(f"    {thr:>4d} | {len(dropped):>8d} | "
                  f"{kept_real:>10d} | {dropped_real:>12d} | "
                  f"{kept_id:>8d} | {dropped_id:>10d} | "
                  f"{kept_tf:>8d} | {dropped_tf:>10d}")
            threshold_results.append({
                "threshold": thr,
                "n_dropped": len(dropped),
                "kept_REAL": kept_real,
                "dropped_REAL": dropped_real,
                "kept_IDENTITY_SWITCH": kept_id,
                "dropped_IDENTITY_SWITCH": dropped_id,
                "kept_TRACKER_FRAGMENTATION": kept_tf,
                "dropped_TRACKER_FRAGMENTATION": dropped_tf,
            })
        # Per-event-log impact (events)
        n_events_total = len(events)
        per_thr_events = []
        for thr in THRESHOLDS:
            n_dropped = sum(2 for f in flights if f["flight_time"] < thr)
            per_thr_events.append({
                "threshold": thr,
                "n_events_dropped": n_dropped,
                "pct_dropped": round(100 * n_dropped / n_events_total, 1),
            })
        print(f"  Per-event-log impact (out of {n_events_total} total events):")
        for r in per_thr_events:
            print(f"    thr={r['threshold']:>3d}: "
                  f"drop {r['n_events_dropped']} events ({r['pct_dropped']}%)")
        summary["videos"][stem] = {
            "n_events": n_events_total,
            "n_flights": len(flights),
            "flight_time_min": min(fts) if fts else None,
            "flight_time_max": max(fts) if fts else None,
            "flight_time_median": statistics.median(fts) if fts else None,
            "h45_label_counts": {
                "REAL": n_real, "IDENTITY_SWITCH": n_id,
                "TRACKER_FRAGMENTATION": n_tf,
            },
            "threshold_results": threshold_results,
            "per_thr_events_impact": per_thr_events,
        }
        print()
    out = H1_DATA / "h48_flight_filter_sensitivity.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
