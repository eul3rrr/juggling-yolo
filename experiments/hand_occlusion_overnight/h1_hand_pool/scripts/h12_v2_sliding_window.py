#!/usr/bin/env python3
"""H12 v2 - per-frame juggling pattern inference with sliding-window event history.

H12 v1 classified each frame based on the n_total census and "recent" events
(within 30 frames). The CASCADE_3+ vs FOUNTAIN_3+ distinction was based
purely on the unique hands of those recent events. With only 8 events on
identical and 1 on YouTube, the distinction was weak:
  - identical: 33.8% UNKNOWN, 21.9% CASCADE_3+, 15.3% TWO_BALL,
    13.9% SINGLE_BALL, 11.7% FOUNTAIN_3+, 3.2% NO_BALL
  - youtube: 93.2% CASCADE_3+ (over-counting artifact), 6.8% FOUNTAIN_3+

H12 v2 adds three improvements:

1. Sliding-window event history. For each frame, examine the LAST K
   catch/throw events (not events within ±30 frames). CASCADE patterns
   produce events at a regular cadence with hand-alternation. FOUNTAIN
   patterns produce events with same-hand dominance.

2. Hand-alternation regularity score: consecutive same-hand events.
   CASCADE_3+ should have ~0 same-hand runs, FOUNTAIN_3+ should have
   all same-hand events, MIXED/UNKNOWN in between.

3. Catch rate (events/sec). CASCADE has higher catch rate than FOUNTAIN
   because hands alternate. With only K events in window, the
   catch-rate signal is noisy but helps.

4. Quality-aware confidence floor. v1 dropped everything below q < 0.5
   to UNKNOWN. v2 keeps the classification but propagates the chain
   quality as the pattern confidence, so downstream consumers see
   "CASCADE_3+ with conf 0.42" rather than "UNKNOWN".

5. Phase-boundary detection. Identify when the pattern label changes
   from one block to the next, and emit the transition frames.

Thresholds (declared from physical geometry / existing thresholds):
  - K_EVENTS = 4  (last 4 catch/throw events)
  - CASCADE_MAX_SAME_HAND_RUN = 1  (0 or 1 same-hand event is OK)
  - CASCADE_MIN_CATCH_RATE = 1.0  (events per second; 1.0 = 1 per sec)
  - QUALITY_CONFIDENT = 0.7
  - QUALITY_TRUSTABLE = 0.4
"""
from __future__ import annotations

import csv
import json
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

K_EVENTS = 4
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0  # events per second
RECENT_EVENT_FRAMES = 30  # for v1-style "any event nearby" signal
QUALITY_FLOOR = 0.0  # propagate chain quality as confidence; don't drop to UNKNOWN


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


def hand_alternation_metric(events_window: list[dict]) -> dict:
    """Compute hand-alternation metrics for the events window.

    Returns:
        same_hand_run: count of events that follow a same-hand event
        unique_hands: number of unique hands in the window
        alternation_score: 1.0 = perfect alternation, 0.0 = all same-hand
    """
    if not events_window:
        return {"same_hand_run": 0, "unique_hands": 0,
                "alternation_score": 0.0, "n_events": 0}

    hands = [e["hand"] for e in events_window]
    n = len(hands)
    same_hand_run = sum(1 for i in range(1, n) if hands[i] == hands[i - 1])
    unique_hands = len(set(hands))
    if n <= 1:
        alternation_score = 0.0
    else:
        # alternation = 1.0 - (same_hand_run / (n - 1))
        # n-1 because we have n-1 transitions
        alternation_score = 1.0 - (same_hand_run / (n - 1))
    return {
        "same_hand_run": same_hand_run,
        "unique_hands": unique_hands,
        "alternation_score": alternation_score,
        "n_events": n,
    }


def catch_rate(events_window: list[dict]) -> float:
    """Returns catch rate in events/second.

    Window's first/last event frames define the duration. Use CATCH
    events only (not THROW) to avoid double-counting.
    """
    catches = [e for e in events_window if e["event"] == "CATCH"]
    if len(catches) < 2:
        return 0.0
    duration_frames = float(int(catches[-1]["event_frame"]) -
                            int(catches[0]["event_frame"]))
    if duration_frames <= 0:
        return 0.0
    return len(catches) * 30.0 / duration_frames  # assume 30 fps


MIN_EVENTS_FOR_PATTERN = 3  # need >= 3 events to classify CASCADE vs FOUNTAIN


def classify_3ball(events_window: list[dict], avg_quality: float,
                    n_in_hand_left: int, n_in_hand_right: int) -> tuple:
    """Classify a 3+ ball frame using the sliding-window event history.

    Returns (pattern, confidence, same_hand_run, alternation_score, catch_rate).

    Decision rules:
    - 0 events in window: cannot disambiguate; use census hand-state as
      a weak signal. If n_in_hand_left=0 and n_in_hand_right=0 (all balls
      in air), cannot decide. Otherwise: 1 in each hand = cascade-like,
      both in one hand = fountain-like. Report as MIXED_3+_UNCONFIRMED.
    - 1-2 events in window: still too few; MIXED_3+ with low confidence.
    - 3+ events in window: use hand-alternation metric and catch rate.
    """
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]
    same_run = metrics["same_hand_run"]
    alt = metrics["alternation_score"]

    if n < MIN_EVENTS_FOR_PATTERN:
        # Use census hand-state as weak fallback signal
        if n_in_hand_left == 1 and n_in_hand_right == 1:
            # alternating at this instant: cascade-like hint
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate
        if n_in_hand_left >= 2 or n_in_hand_right >= 2:
            # both in same hand: fountain-like hint
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.5, same_run, alt, rate

    # CASCADE: low same-hand run, high alternation, high catch rate
    cascade_like = (same_run <= CASCADE_MAX_SAME_HAND_RUN
                    and alt >= 0.5
                    and rate >= CASCADE_MIN_CATCH_RATE)
    # FOUNTAIN: high same-hand run, low alternation, lower catch rate
    fountain_like = (same_run >= n - 1
                     and alt < 0.3)

    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality, same_run, alt, rate
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality, same_run, alt, rate
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate

    # Mixed: same_hand_run in between (e.g., 1 of 3 same)
    return "MIXED_3+", avg_quality, same_run, alt, rate


def classify_pattern_v2(census_row: dict, events_window: list[dict],
                         recent_events: list[dict]) -> tuple:
    """Classify a frame using v2 logic.

    Returns (pattern, confidence, same_hand_run, alternation_score, catch_rate).
    """
    n_total = census_row["n_total"]
    n_air = census_row["n_in_air"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    n_hand = n_h_l + n_h_r
    q = census_row["avg_quality"]
    # v2: confidence is the chain quality, not the v1 binary
    # Floor at QUALITY_FLOOR
    conf = max(q, QUALITY_FLOOR)

    if n_total == 0:
        return "NO_BALL", 1.0, 0, 0.0, 0.0
    if n_total == 1:
        return "SINGLE_BALL", conf, 0, 0.0, 0.0

    if n_total == 2:
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", conf, 0, 0.0, 0.0
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", conf, 0, 0.0, 0.0
        return "TWO_BALL", conf, 0, 0.0, 0.0

    if n_total >= 3:
        pattern, conf3, same_run, alt, rate = classify_3ball(
            events_window, q, n_h_l, n_h_r)
        return pattern, conf3, same_run, alt, rate

    return "UNKNOWN", conf, 0, 0.0, 0.0


def detect_phase_boundaries(results: list[dict]) -> list[dict]:
    """Identify pattern phase transitions in the timeline.

    Returns list of {start_frame, end_frame, pattern, n_frames, avg_confidence}.
    """
    if not results:
        return []
    phases = []
    current_pattern = None
    phase_start = None
    phase_confs = []
    for r in results:
        if r["pattern"] != current_pattern:
            if current_pattern is not None:
                phases.append({
                    "start_frame": phase_start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current_pattern,
                    "n_frames": r["frame"] - phase_start,
                    "avg_confidence": round(sum(phase_confs) / len(phase_confs), 3)
                })
            current_pattern = r["pattern"]
            phase_start = r["frame"]
            phase_confs = [r["confidence"]]
        else:
            phase_confs.append(r["confidence"])
    # final phase
    if current_pattern is not None:
        phases.append({
            "start_frame": phase_start,
            "end_frame": results[-1]["frame"],
            "pattern": current_pattern,
            "n_frames": results[-1]["frame"] - phase_start + 1,
            "avg_confidence": round(sum(phase_confs) / len(phase_confs), 3)
        })
    return phases


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        census = load_census(stem)
        events = load_events(stem)

        # Sort events by event_frame
        events_sorted = sorted(events, key=lambda e: int(e["event_frame"]))

        # Build per-frame event list (for "recent events" ±window)
        events_by_frame = defaultdict(list)
        for e in events:
            events_by_frame[int(e["event_frame"])].append(e)

        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        for f, c in sorted(census.items()):
            # Sliding window: last K_EVENTS events BEFORE/AT this frame
            events_before = [e for e in events_sorted
                              if int(e["event_frame"]) <= f]
            events_window = events_before[-K_EVENTS:]

            # Recent events (v1 style, for comparison)
            recent = []
            for df in range(-RECENT_EVENT_FRAMES, RECENT_EVENT_FRAMES + 1):
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

        # Print pattern distribution
        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        # Phase detection
        phases = detect_phase_boundaries(results)
        print(f"  Detected {len(phases)} pattern phases:")
        for ph in phases:
            if ph["n_frames"] >= 20:  # only show substantial phases
                print(f"    f={ph['start_frame']}-{ph['end_frame']} "
                      f"({ph['n_frames']}f) {ph['pattern']} "
                      f"conf={ph['avg_confidence']:.2f}")

        # Write CSV
        out = H1_DATA / f"pattern_inference_v2_{stem}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out.name}")

        # Phase CSV
        if phases:
            phase_out = H1_DATA / f"pattern_phases_v2_{stem}.csv"
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
            "phases": phases,
        }

    out = H1_DATA / "h12_v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
