#!/usr/bin/env python3
"""H12 v3 - integrate detector-level signals into H12 v2 event log.

The H12 v2 algorithm is limited by event log density (8 events on identical,
1 on YouTube). Visual QA found that the v3c-rejected link 35->40 on
identical is a real catch-throw that v4d's MIN_FROM_SLOPE=2.5 threshold
incorrectly rejected. The other v3c rejection (15->25 on YouTube) is
correctly rejected.

H12 v3 adds the 35->40 event back to the event log as a
"VISUALLY_CONFIRMED" event and re-runs H12 v2 with the enriched event log.

Hypothesis: adding 1 more event to the early phase of identical will
change the pattern classification in the MIXED_3+ and CASCADE_3+ regions
in the early video (f=0-700), where the algorithm currently sees few
events and labels everything as MIXED.

This is a "label-informed" parameter choice (we visually confirmed the
event is real). It's NOT a v4d threshold change — the v4d threshold is
still 2.5. The 35->40 event is added with a special flag.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from h12_v2_sliding_window import (
    load_census, load_events, hand_alternation_metric, catch_rate,
    K_EVENTS, MIN_EVENTS_FOR_PATTERN, CASCADE_MAX_SAME_HAND_RUN,
    CASCADE_MIN_CATCH_RATE, classify_pattern_v2, detect_phase_boundaries,
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Visually confirmed v4d-rejected event (from H12 v2 visual QA)
# 35->40 on identical, f=522-549, left hand
# This was rejected by v4d (from_slope=2.31 < 2.5) but is a real catch-throw.
ADDED_EVENTS = [
    # (stem, chain_id, event, tid, prev_tid, event_frame, prev_last_frame,
    #  curr_first_frame, gap_frames, hand, tok_age, h3_confirmed, ambiguous,
    #  chain_quality, edge_type, source)
    ("identical_balls_trick_000_018", "23", "CATCH", 40, 35, 535, 522, 549, 27,
     "left", 27, "False", "False", 0.8367, "HAND_TRANSITION", "v3c_rejected_visually_confirmed"),
    ("identical_balls_trick_000_018", "23", "THROW", 40, 35, 535, 522, 549, 27,
     "left", 27, "False", "False", 0.8367, "HAND_TRANSITION", "v3c_rejected_visually_confirmed"),
]


def load_events_v3(stem: str) -> list[dict]:
    """Load v2 events and add the visually-confirmed v3c-rejected events."""
    events = load_events(stem)
    for added in ADDED_EVENTS:
        if added[0] != stem:
            continue
        # Only add CATCH (not THROW) to avoid double-counting
        if added[2] == "CATCH":
            events.append({
                "chain_id": added[1],
                "event": added[2],
                "tid": added[3],
                "prev_tid": added[4],
                "event_frame": added[5],
                "prev_last_frame": added[6],
                "curr_first_frame": added[7],
                "gap_frames": added[8],
                "hand": added[9],
                "tok_age": added[10],
                "h3_confirmed": added[11],
                "ambiguous": added[12],
                "chain_quality": added[13],
                "edge_type": added[14],
                "source": added[15],
            })
    return events


def main():
    summary = {"videos": {}, "added_events": [list(a) for a in ADDED_EVENTS]}
    for stem in ["identical_balls_trick_000_018"]:
        print(f"\n=== {stem} (H12 v3 with enriched event log) ===")
        census = load_census(stem)
        events = load_events_v3(stem)
        print(f"  loaded {len(events)} events (was 16 = 8 catches + 8 throws)")

        events_sorted = sorted(events, key=lambda e: int(e["event_frame"]))
        events_by_frame = defaultdict(list)
        for e in events:
            events_by_frame[int(e["event_frame"])].append(e)

        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        for f, c in sorted(census.items()):
            events_before = [e for e in events_sorted
                              if int(e["event_frame"]) <= f]
            events_window = events_before[-K_EVENTS:]
            recent = []
            for df in range(-30, 31):
                recent.extend(events_by_frame.get(f + df, []))
            pattern, conf, same_run, alt, rate = classify_pattern_v2(
                c, events_window, recent)
            results.append({
                "frame": f,
                "n_in_air": c["n_in_air"],
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total"],
                "avg_quality": c["avg_quality"],
                "pattern": pattern,
                "confidence": round(conf, 3),
                "n_window_events": len(events_window),
                "n_recent_events": len(recent),
                "same_hand_run": same_run,
                "alternation_score": round(alt, 3),
                "catch_rate_hz": round(rate, 2),
            })
            pattern_counts[pattern] += 1

        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        phases = detect_phase_boundaries(results)
        print(f"  Detected {len(phases)} pattern phases")
        for ph in phases:
            if ph["n_frames"] >= 30:
                print(f"    f={ph['start_frame']}-{ph['end_frame']} "
                      f"({ph['n_frames']}f) {ph['pattern']} "
                      f"conf={ph['avg_confidence']:.2f}")

        out = H1_DATA / f"pattern_inference_v3_{stem}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out.name}")

        if phases:
            phase_out = H1_DATA / f"pattern_phases_v3_{stem}.csv"
            with phase_out.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(phases[0].keys()))
                w.writeheader()
                w.writerows(phases)
            print(f"  wrote: {phase_out.name}")

        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "pattern_counts": dict(pattern_counts),
            "pct_patterns": {p: 100 * n / n_total_frames
                              for p, n in pattern_counts.items()},
            "n_phases": len(phases),
        }

    out = H1_DATA / "h12_v3_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
