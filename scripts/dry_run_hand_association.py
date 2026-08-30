"""Hand Association Engine v1 dry-run driver.

Reads:
    tracklets CSV
    hands CSV (per-frame pose)
    total video frames + FPS
    known human-confirmed hand-mediated transitions (for reporting)

Writes:
    events CSV (chronological)
    coverage report (stdout)
    summary (stdout)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import hand_association as ha  # noqa: E402


KNOWN_TRANSITIONS = [
    {"source_id": 3, "target_id": 4, "frame": 149, "hand": "right"},
    {"source_id": 4, "target_id": 6, "frame": 217, "hand": "right"},
    {"source_id": 1, "target_id": 5, "frame": 219, "hand": "left"},
    {"source_id": 5, "target_id": 10, "frame": 841, "hand": "left"},
    {"source_id": 2, "target_id": 11, "frame": 882, "hand": "left"},
    {"source_id": 6, "target_id": 13, "frame": 950, "hand": "left"},
    {"source_id": 10, "target_id": 14, "frame": 1074, "hand": "right"},
]


def remap_known_transitions(mapping: dict[int, int]) -> list[dict]:
    """Translate known transitions from tracklet IDs to chain IDs."""
    out = []
    for tr in KNOWN_TRANSITIONS:
        src = mapping.get(tr["source_id"], tr["source_id"])
        tgt = mapping.get(tr["target_id"], tr["target_id"])
        if src == tgt:
            # No real chain boundary -- the stitcher already merged
            # these tracklets. Skip the transition.
            continue
        out.append({**tr, "source_id": src, "target_id": tgt})
    return out

# Background noise: events around frame 465 and 936 that the v1A
# diagnostic flagged as NOT real hand bridges.
NOISE_WINDOWS = [
    {"label": "noise_465_498", "lo": 465, "hi": 498, "expected": "no_bridge"},
    {"label": "noise_900_960", "lo": 900, "hi": 960, "expected": "no_bridge"},
]


def find_track_for_frame(tracklets, frame):
    for tid, pts in tracklets.items():
        if not pts:
            continue
        if pts[0].frame <= frame <= pts[-1].frame:
            return tid
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracklets", required=True, type=Path)
    p.add_argument("--hands", required=True, type=Path)
    p.add_argument("--video-frames", required=True, type=int)
    p.add_argument("--fps", type=float, default=60.0)
    p.add_argument("--output-events", required=True, type=Path)
    p.add_argument("--output-report", required=True, type=Path)
    p.add_argument("--chain-mapping", type=Path, default=None,
                   help="Optional track_id->chain_id CSV. When provided, "
                        "the engine operates on chain-level identities "
                        "instead of raw tracklet IDs.")
    p.add_argument("--window", type=int, default=10)
    args = p.parse_args()

    tracklets = ha._load_tracklets(args.tracklets)
    hands_by_frame = ha._load_hands_by_frame(args.hands)
    chain_mapping: dict[int, int] = {}
    if args.chain_mapping and args.chain_mapping.is_file():
        chain_mapping = ha._load_chain_mapping(args.chain_mapping)
        identities = ha._load_chains(tracklets, chain_mapping)
        identity_label = "chain"
    else:
        identities = tracklets
        identity_label = "tracklet"
    known = remap_known_transitions(chain_mapping) if chain_mapping \
            else KNOWN_TRANSITIONS
    result = ha.dry_run(identities, hands_by_frame, args.fps)
    coverage = ha.compute_wrist_coverage(
        hands_by_frame, args.video_frames, known,
        args.fps, window=args.window)

    args.output_events.parent.mkdir(parents=True, exist_ok=True)
    ha.write_event_csv(result.events, args.output_events)

    # Per-known-transition check: did the source -> target bridge
    # get proposed? Find the END event for the source, then check
    # for a subsequent hand_exit that names the target. We accept
    # "ambiguous" as a valid bridge verdict for cases where the spec
    # calls for ambiguity (e.g. 2 -> 11), and we report what the
    # engine actually proposed for the human to inspect.
    known_results = []
    for tr in KNOWN_TRANSITIONS:
        src_end = max((pt.frame for pt in tracklets.get(tr["source_id"], [])),
                      default=-1)
        entry = next((e for e in result.events
                     if e["event_type"] == "hand_entry"
                     and e["frame"] == src_end
                     and e["track_id"] == tr["source_id"]),
                    None)
        exit_evt = next((e for e in result.events
                        if e["event_type"] == "hand_exit"
                        and e["track_id"] == tr["target_id"]),
                       None)
        # Did the engine propose a bridge at all?
        proposed_bridge = (entry is not None and exit_evt is not None
                          and exit_evt["source_track_id"] == tr["source_id"])
        # Did it get the hand side right (or accept ambiguity)?
        hand_match = False
        if entry is not None and exit_evt is not None:
            if tr["hand"] == "left":
                hand_match = entry["hand"] in ("left", "ambiguous")
            else:
                hand_match = entry["hand"] in ("right", "ambiguous")
        known_results.append({
            "source_id": tr["source_id"], "target_id": tr["target_id"],
            "frame": tr["frame"], "expected_hand": tr["hand"],
            "entry_hand": entry["hand"] if entry else None,
            "entry_band": entry["band"] if entry else None,
            "exit_hand": exit_evt["hand"] if exit_evt else None,
            "exit_source_track_id": exit_evt["source_track_id"] if exit_evt else None,
            "proposed_bridge": proposed_bridge,
            "hand_match": hand_match,
        })

    # Per-noise-window check: did the engine spuriously admit any
    # track boundary in this window?
    noise_results = []
    for nw in NOISE_WINDOWS:
        spurious = []
        for e in result.events:
            if e["event_type"] == "hand_entry" and nw["lo"] <= e["frame"] <= nw["hi"]:
                spurious.append({"frame": e["frame"], "track_id": e["track_id"],
                                 "hand": e["hand"], "band": e["band"]})
        noise_results.append({
            "label": nw["label"],
            "expected": nw["expected"],
            "spurious_entries": spurious,
            "spurious_count": len(spurious),
        })

    report = {
        "video_frames": args.video_frames,
        "fps": args.fps,
        "n_track_ends": result.n_track_ends,
        "n_track_starts": result.n_track_starts,
        "n_orphan_continuations": result.n_orphan_continuations,
        "counts": result.counts,
        "queue_final": result.queue_final,
        "coverage": {
            "total_frames": coverage.total_frames,
            "left_pct": coverage.left_pct,
            "right_pct": coverage.right_pct,
            "both_pct": coverage.both_pct,
            "neither_pct": coverage.neither_pct,
            "longest_left_outage": coverage.longest_left_outage,
            "longest_right_outage": coverage.longest_right_outage,
            "longest_both_outage": coverage.longest_both_outage,
            "outage_distribution_left": coverage.outage_distribution_left,
            "outage_distribution_right": coverage.outage_distribution_right,
            "outage_distribution_both": coverage.outage_distribution_both,
            "coverage_around_transitions": coverage.coverage_around_transitions,
        },
        "known_results": known_results,
        "noise_results": noise_results,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    with args.output_report.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # Short stdout summary.
    print(f"n_track_ends={result.n_track_ends} n_track_starts={result.n_track_starts} n_orphans={result.n_orphan_continuations}")
    for k in sorted(result.counts.keys()):
        print(f"  {k}: {result.counts[k]}")
    print(f"queue_final: {result.queue_final}")
    print()
    print("Coverage:")
    print(f"  left={coverage.left_pct*100:.1f}% right={coverage.right_pct*100:.1f}% "
          f"both={coverage.both_pct*100:.1f}% neither={coverage.neither_pct*100:.1f}%")
    print(f"  longest outages (frames): L={coverage.longest_left_outage} "
          f"R={coverage.longest_right_outage} B={coverage.longest_both_outage}")
    print()
    print("Known hand transitions:")
    for r in known_results:
        bridge_v = "BRIDGE" if r["proposed_bridge"] else "no_bridge"
        hand_v = "HAND_OK" if r["hand_match"] else "HAND_MISMATCH"
        print(f"  {r['source_id']}->{r['target_id']} @ {r['frame']} expected={r['expected_hand']} "
              f"got_entry={r['entry_hand']} exit={r['exit_hand']} "
              f"[{bridge_v} {hand_v}]")
    print()
    print("Noise windows:")
    for n in noise_results:
        print(f"  {n['label']}: spurious_entries={n['spurious_count']}")
        for s in n["spurious_entries"][:5]:
            print(f"    frame={s['frame']} track={s['track_id']} hand={s['hand']} band={s['band']}")


if __name__ == "__main__":
    main()
