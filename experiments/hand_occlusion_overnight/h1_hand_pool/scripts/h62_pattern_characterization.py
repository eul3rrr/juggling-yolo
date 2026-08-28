#!/usr/bin/env python3
"""H62 - characterize the YouTube 5-ball pattern (cascade vs shower).

H58 found 1 YouTube CONFIDENT chain (chain 6) with right-hand-only
events and a 17-frame held phase. The H58 report interpreted this
as a 5-ball SHOWER pattern (same-hand throw+catch).

H60 found that YouTube has more left-hand held phases than right
(opposite of identical). The H60 report interpreted this as a
"different pattern" but didn't characterize it.

H62 systematically examines the YouTube catch/throw event log to
answer: is the YouTube 5-ball pattern a CASCADE (alternating hands)
or a SHOWER (same-hand throw+catch)?

Method:
- For each consecutive (THROW, CATCH) pair on YouTube, classify
  the hand pattern:
  - SAME_HAND: THROW hand == CATCH hand
  - ALT_HAND: THROW hand != CATCH hand
- Compute the ratio: SAME_HAND / total. SHOWER would be ~1.0;
  CASCADE would be ~0.0.
- For reference, also compute the same metric on identical (which
  is known to be 3-ball CASCADE).

Also compute:
- Inter-throw interval (time between consecutive throws): SHOWER
  has shorter intervals (one hand throws, same hand catches, then
  throws again). CASCADE has longer intervals (hand A throws,
  ball goes to hand B, hand A throws again only after B throws).
- Held phase distribution per hand (the H60 hand-asymmetry).

Outputs:
- data/h62_youtube_pattern.csv (per-throw classification)
- data/h62_pattern_summary.json (aggregate stats)
- reports/h62_report.md
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_catch_throw_v8(stem: str) -> list[dict]:
    path = H1_DATA / f"catch_throw_timeline_v8_{stem}.csv"
    with path.open() as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        events = load_catch_throw_v8(stem)
        # Only CATCH events for hand sequence
        catches = [e for e in events if e["event"] == "CATCH" and e["hand"] in ("left", "right")]
        throws = [e for e in events if e["event"] == "THROW" and e["hand"] in ("left", "right")]
        # Sort by event_frame
        catches.sort(key=lambda e: int(e["event_frame"]))
        throws.sort(key=lambda e: int(e["event_frame"]))

        # Hand sequence
        catch_hands = [e["hand"] for e in catches]
        throw_hands = [e["hand"] for e in throws]

        # Transitions
        catch_transitions = 0
        for i in range(1, len(catch_hands)):
            if catch_hands[i] != catch_hands[i - 1]:
                catch_transitions += 1
        catch_alt_rate = catch_transitions / max(1, len(catch_hands) - 1)

        throw_transitions = 0
        for i in range(1, len(throw_hands)):
            if throw_hands[i] != throw_hands[i - 1]:
                throw_transitions += 1
        throw_alt_rate = throw_transitions / max(1, len(throw_hands) - 1)

        # (THROW, CATCH) pair analysis: was the next CATCH on the same hand?
        # For each THROW, find the next CATCH (chronologically)
        pair_classifications = []
        for i, t in enumerate(throws):
            t_frame = int(t["event_frame"])
            t_hand = t["hand"]
            # Find the next CATCH after this THROW
            next_catches = [c for c in catches if int(c["event_frame"]) > t_frame]
            if not next_catches:
                continue
            next_c = min(next_catches, key=lambda c: int(c["event_frame"]))
            same_hand = next_c["hand"] == t_hand
            gap = int(next_c["event_frame"]) - t_frame
            pair_classifications.append({
                "throw_frame": t_frame,
                "throw_hand": t_hand,
                "next_catch_frame": int(next_c["event_frame"]),
                "next_catch_hand": next_c["hand"],
                "same_hand": same_hand,
                "gap_frames": gap,
            })

        n_pairs = len(pair_classifications)
        n_same = sum(1 for p in pair_classifications if p["same_hand"])
        n_alt = n_pairs - n_same
        same_hand_rate = n_same / max(1, n_pairs)

        # Inter-throw intervals
        throw_intervals = []
        for i in range(1, len(throws)):
            interval = int(throws[i]["event_frame"]) - int(throws[i - 1]["event_frame"])
            throw_intervals.append(interval)

        # Held phase by hand
        by_hand_catch = defaultdict(int)
        by_hand_throw = defaultdict(int)
        for e in catches:
            by_hand_catch[e["hand"]] += 1
        for e in throws:
            by_hand_throw[e["hand"]] += 1

        # By q11 (for YouTube only)
        by_q_hand = defaultdict(lambda: {"same": 0, "alt": 0})
        for i, t in enumerate(throws):
            t_cid = int(t["chain_id"])
            t_hand = t["hand"]
            next_catches = [c for c in catches if int(c["event_frame"]) > int(t["event_frame"])]
            if not next_catches:
                continue
            next_c = min(next_catches, key=lambda c: int(c["event_frame"]))
            same_hand = next_c["hand"] == t_hand
            pair_classifications[-1]  # ensure list is not unused
            # Re-look-up q11 from chain_quality field in event
            try:
                q11 = float(t.get("chain_quality", 0))
            except (ValueError, TypeError):
                q11 = 0
            band = "CONF" if q11 >= 0.7 else ("UNC" if q11 >= 0.4 else "LOW")
            by_q_hand[band]["same" if same_hand else "alt"] += 1

        summary["videos"][stem] = {
            "n_catch_events": len(catches),
            "n_throw_events": len(throws),
            "catch_hand_sequence": catch_hands,
            "throw_hand_sequence": throw_hands,
            "catch_alt_rate": round(catch_alt_rate, 3),
            "throw_alt_rate": round(throw_alt_rate, 3),
            "n_throw_catch_pairs": n_pairs,
            "n_same_hand_pairs": n_same,
            "n_alt_hand_pairs": n_alt,
            "same_hand_rate": round(same_hand_rate, 3),
            "pattern_verdict": (
                "CASCADE" if same_hand_rate < 0.3 else
                "SHOWER" if same_hand_rate > 0.7 else
                "MIXED"
            ),
            "throw_intervals": {
                "min": min(throw_intervals) if throw_intervals else 0,
                "max": max(throw_intervals) if throw_intervals else 0,
                "mean": round(statistics.mean(throw_intervals), 2) if throw_intervals else 0,
                "median": round(statistics.median(throw_intervals), 2) if throw_intervals else 0,
            },
            "by_hand_catch": dict(by_hand_catch),
            "by_hand_throw": dict(by_hand_throw),
        }

        print(f"\n=== {stem} ===")
        print(f"  N CATCH events: {len(catches)}, N THROW events: {len(throws)}")
        print(f"  Catch hand sequence: {catch_hands}")
        print(f"  Throw hand sequence: {throw_hands}")
        print(f"  Catch alt rate: {catch_alt_rate:.2f}, Throw alt rate: {throw_alt_rate:.2f}")
        print(f"  THROW->CATCH pair analysis:")
        print(f"    N pairs: {n_pairs}")
        print(f"    Same-hand: {n_same} ({same_hand_rate:.2f})")
        print(f"    Alt-hand:  {n_alt} ({1 - same_hand_rate:.2f})")
        print(f"  Pattern verdict: {summary['videos'][stem]['pattern_verdict']}")
        print(f"  Inter-throw interval: {summary['videos'][stem]['throw_intervals']}")
        print(f"  By hand (catch): {dict(by_hand_catch)}")
        print(f"  By hand (throw): {dict(by_hand_throw)}")

    # Cross-video
    print("\n=== Cross-video pattern verdict ===")
    for stem in STEMS:
        v = summary["videos"][stem]
        print(f"  {stem}: {v['pattern_verdict']} (same-hand rate: {v['same_hand_rate']:.2f})")

    # Write outputs
    (H1_DATA / "h62_pattern_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    # Per-throw CSV (YouTube only since it has the question)
    yt_pairs = []
    yt_events = load_catch_throw_v8(STEMS[1])
    yt_catches = sorted([e for e in yt_events if e["event"] == "CATCH" and e["hand"] in ("left", "right")],
                       key=lambda e: int(e["event_frame"]))
    yt_throws = sorted([e for e in yt_events if e["event"] == "THROW" and e["hand"] in ("left", "right")],
                      key=lambda e: int(e["event_frame"]))
    for t in yt_throws:
        t_frame = int(t["event_frame"])
        t_hand = t["hand"]
        next_catches = [c for c in yt_catches if int(c["event_frame"]) > t_frame]
        if not next_catches:
            continue
        next_c = min(next_catches, key=lambda c: int(c["event_frame"]))
        same_hand = next_c["hand"] == t_hand
        gap = int(next_c["event_frame"]) - t_frame
        try:
            q11 = float(t.get("chain_quality", 0))
        except (ValueError, TypeError):
            q11 = 0
        band = "CONF" if q11 >= 0.7 else ("UNC" if q11 >= 0.4 else "LOW")
        yt_pairs.append({
            "throw_frame": t_frame,
            "throw_hand": t_hand,
            "next_catch_frame": int(next_c["event_frame"]),
            "next_catch_hand": next_c["hand"],
            "same_hand": same_hand,
            "gap_frames": gap,
            "q11": q11,
            "q11_band": band,
            "chain_id": int(t["chain_id"]),
        })
    (H1_DATA / "h62_youtube_pattern.csv").write_text(
        "throw_frame,throw_hand,next_catch_frame,next_catch_hand,"
        "same_hand,gap_frames,q11,q11_band,chain_id\n" +
        "\n".join(
            f"{p['throw_frame']},{p['throw_hand']},{p['next_catch_frame']},"
            f"{p['next_catch_hand']},{p['same_hand']},{p['gap_frames']},"
            f"{p['q11']},{p['q11_band']},{p['chain_id']}"
            for p in yt_pairs
        ) + "\n"
    )
    print(f"\nWrote {H1_DATA / 'h62_pattern_summary.json'}")
    print(f"Wrote {H1_DATA / 'h62_youtube_pattern.csv'}")


if __name__ == "__main__":
    main()
