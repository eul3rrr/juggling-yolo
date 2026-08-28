#!/usr/bin/env python3
"""H11 v2 - per-frame ball census and pattern extraction.

Builds on h11_identity_propagation.py by adding:

1. Per-frame census: at any frame, how many physical balls are
   in the air vs held by each hand? (based on chain membership
   and the hand-edge transitions)

2. Catch/throw timeline: extract the absolute frame of each
   CATCH/THROW event (currently they all have frame=0; this
   populates them properly with the to_tid's first_frame and
   from_tid's last_frame)

3. Juggling pattern analysis: with the ball census, infer
   whether the juggler is in a 3-ball cascade, 2-ball, 1-ball,
   or 0-ball moment. The cascade is the standard pattern
   (3 balls, alternating hands, each ball is in the air for
   ~2 throws).

4. Identity merging: when two chains BOTH have a chain_start
   near the same hand at the same time, they may be the same
   physical ball (the second chain's first tracklet is a
   "continuation" of a missed hand-edge). Flag such candidates
   for downstream review.
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

QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4


def load_h237v5_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            r["n_tracklets"] = int(r["n_tracklets"])
            r["n_hand_edges"] = int(r["n_hand_edges"])
            r["n_air_edges"] = int(r["n_air_edges"])
            r["n_h3_confirmed"] = int(r["n_h3_confirmed"])
            r["h10_v5_quality"] = float(r["h10_v5_quality"])
            r["chain_id"] = int(r["chain_id"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            out.append(r)
    return out


def load_h237_edges(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            key = (int(r["from_tid"]), int(r["to_tid"]))
            out[key] = {
                "edge_type": r["edge_type"],
                "cost": float(r["cost"]),
                "h3_confirmed": r["h3_confirmed"] in ("True", "true", "1"),
                "metadata": r["metadata"],
            }
    return out


def load_tracklet_features(stem: str) -> dict:
    out = {}
    path = H1_DATA / "tracklet_features.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            tid = int(r["tid"])
            out[tid] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


def parse_hand_metadata(metadata: str) -> dict:
    if not metadata:
        return {}
    out = {}
    for part in metadata.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def extract_catch_throw_timeline(chains: list[dict], edges: dict,
                                  tracklets: dict) -> list[dict]:
    """Extract catch/throw events with absolute frame numbers.

    A hand-edge from_tid -> to_tid represents a transition at
    the hand. The "catch" is the moment the ball arrived at
    the hand, somewhere between from_tid's last observation and
    to_tid's first observation. We use the midpoint of that gap
    as the catch/throw moment.

    For AMBIGUOUS_HAND_TRANSITION, we still emit the event but
    mark identity_ambiguous=True.
    """
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        quality = chain["h10_v5_quality"]
        if quality < QUALITY_TRUSTABLE:
            continue
        for i in range(len(tids) - 1):
            prev_tid = tids[i]
            tid = tids[i + 1]
            edge = edges.get((prev_tid, tid))
            if edge is None:
                continue
            etype = edge["edge_type"]
            if etype not in ("HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION"):
                continue
            md = parse_hand_metadata(edge["metadata"])
            prev_tf = tracklets.get(prev_tid, {})
            curr_tf = tracklets.get(tid, {})
            if "first_frame" not in prev_tf or "first_frame" not in curr_tf:
                continue
            prev_last = prev_tf["last_frame"]
            curr_first = curr_tf["first_frame"]
            event_frame = (prev_last + curr_first) // 2
            gap_frames = curr_first - prev_last

            for event in ("CATCH", "THROW"):
                out.append({
                    "chain_id": cid,
                    "event": event,
                    "tid": tid,
                    "prev_tid": prev_tid,
                    "event_frame": event_frame,
                    "prev_last_frame": prev_last,
                    "curr_first_frame": curr_first,
                    "gap_frames": gap_frames,
                    "hand": md.get("hand", "?"),
                    "tok_age": md.get("tok_age", "?"),
                    "h3_confirmed": edge["h3_confirmed"],
                    "ambiguous": etype == "AMBIGUOUS_HAND_TRANSITION",
                    "chain_quality": quality,
                    "edge_type": etype,
                })
    return out


def compute_per_frame_census(chains: list[dict], tracklets: dict,
                             events: list[dict]) -> dict:
    """For each frame, compute:
    - n_in_air: number of balls in the air
    - n_in_hand_left, n_in_hand_right: balls held in each hand
    - n_total: total balls in the juggling census
    - balls_in_hand: list of (chain_id, ball_id, hand)
    - balls_in_air: list of (chain_id, ball_id)
    - quality_avg: average H10 v5 quality of chains that have a tracklet at this frame
    """
    # Build per-frame occupancy
    # Each chain has tracklets; we treat each chain as one physical ball
    # (regardless of quality). For "high-quality" census, we filter
    # to chains with quality >= QUALITY_TRUSTABLE.
    air_by_frame = defaultdict(list)  # frame -> list of (chain_id, ball_id)
    in_hand_by_frame = defaultdict(list)  # frame -> list of (chain_id, ball_id, hand)
    quality_by_frame = defaultdict(list)

    for chain in chains:
        cid = chain["chain_id"]
        quality = chain["h10_v5_quality"]
        tids = chain["tids"]
        ball_id = f"chain{cid}_ball0"

        # For each tracklet, look up its frame range and check if
        # it's at a hand (via hand-edge) or in the air
        # We model: if tracklet has a hand-edge TO it, it's the
        # FIRST tracklet after the hand (just released). If it has
        # a hand-edge FROM it, it's the LAST tracklet before the
        # hand (just caught). Otherwise it's mid-air.

        # Find hand events involving this chain
        chain_events = [e for e in events if e["chain_id"] == cid]
        # Build a map: tid -> list of (event, hand) on that tid
        events_by_tid = defaultdict(list)
        for e in chain_events:
            events_by_tid[e["tid"]].append(e)
            events_by_tid[e["prev_tid"]].append(e)

        for i, tid in enumerate(tids):
            tf = tracklets.get(tid)
            if tf is None:
                continue
            f_first = tf["first_frame"]
            f_last = tf["last_frame"]
            hand_events = events_by_tid.get(tid, [])

            # Decide: at the first frame, is this at a hand or in air?
            # If the previous tracklet has a HAND-edge to this tracklet
            # (i.e. we have a catch event for this tid), then this tid
            # starts in the hand (after the catch). If this tracklet
            # has a HAND-edge from it (i.e. catch event for next tid),
            # then it ends in the hand (before the catch).
            is_after_catch = any(e["event"] == "CATCH" and e["tid"] == tid
                                 for e in hand_events)
            is_before_catch = any(e["event"] == "CATCH" and e["prev_tid"] == tid
                                  for e in hand_events)
            is_after_throw = any(e["event"] == "THROW" and e["tid"] == tid
                                 for e in hand_events)
            is_before_throw = any(e["event"] == "THROW" and e["prev_tid"] == tid
                                  for e in hand_events)
            # Find the hand if available
            hand = None
            for e in hand_events:
                hand = e["hand"]
                break

            for f in range(f_first, f_last + 1):
                # Determine the state at this frame
                # First frame after catch: in hand (until next throw or end)
                # Frame before catch: in hand (since previous throw)
                # First frame after throw: in air
                # Frame before throw: in hand
                # Other frames: in air
                in_hand = (is_after_catch and f == f_first) or \
                          (is_before_catch and f == f_last) or \
                          (is_before_throw and f == f_last)
                in_air = not in_hand

                if in_air:
                    air_by_frame[f].append((cid, ball_id))
                else:
                    in_hand_by_frame[f].append((cid, ball_id, hand))
                quality_by_frame[f].append(quality)

    # Find frame range
    all_frames = set(air_by_frame.keys()) | set(in_hand_by_frame.keys())
    if not all_frames:
        return {}
    fmin, fmax = min(all_frames), max(all_frames)

    census = {}
    for f in range(fmin, fmax + 1):
        n_air = len(air_by_frame.get(f, []))
        in_hand = in_hand_by_frame.get(f, [])
        n_hand_left = sum(1 for _, _, h in in_hand if h == "left")
        n_hand_right = sum(1 for _, _, h in in_hand if h == "right")
        n_hand = len(in_hand)
        n_total = n_air + n_hand
        q_avg = (sum(quality_by_frame.get(f, [])) /
                 max(1, len(quality_by_frame.get(f, []))))
        census[f] = {
            "n_in_air": n_air,
            "n_in_hand_left": n_hand_left,
            "n_in_hand_right": n_hand_right,
            "n_total_balls": n_total,
            "balls_in_hand": [f"c{c[0]}" for c in in_hand],
            "balls_in_air": [f"c{c[0]}" for c in air_by_frame.get(f, [])],
            "avg_chain_quality": q_avg,
        }
    return census


def detect_identity_merges(chains: list[dict], tracklets: dict,
                            events: list[dict]) -> list[dict]:
    """For each chain_start (first tracklet of a chain), check if
    it happens near a hand event in another chain at the same time.
    If so, the two chains may be the same physical ball and the
    second chain's first tracklet is a "continuation" of a missed
    hand-edge.

    This is a HYPOTHESIS GENERATOR, not a definitive merge.
    """
    out = []
    # For each chain, find chain_starts
    chain_starts = []
    for c in chains:
        if c["n_tracklets"] == 0:
            continue
        first_tid = c["tids"][0]
        tf = tracklets.get(first_tid)
        if tf is None:
            continue
        chain_starts.append({
            "chain_id": c["chain_id"],
            "first_tid": first_tid,
            "first_frame": tf["first_frame"],
            "first_x": tf["first_x"],
            "first_y": tf["first_y"],
            "quality": c["h10_v5_quality"],
        })

    # For each (chain_start, other_chain_event), check proximity
    for cs in chain_starts:
        for e in events:
            # Skip events in the same chain
            if e["chain_id"] == cs["chain_id"]:
                continue
            # Check temporal proximity (within 30 frames)
            df = e["event_frame"] - cs["first_frame"]
            if abs(df) > 30:
                continue
            # Check spatial proximity (need ball position at cs's first frame
            # and at e's event frame)
            # cs already has first_x, first_y
            # e's position: from prev_tid's last position (for catch/throw)
            # We'd need prev_tid's last position; for now use heuristic
            out.append({
                "candidate_merge": f"chain{cs['chain_id']}->chain{e['chain_id']}",
                "cs_chain_id": cs["chain_id"],
                "cs_first_tid": cs["first_tid"],
                "cs_first_frame": cs["first_frame"],
                "cs_quality": cs["quality"],
                "event_chain_id": e["chain_id"],
                "event": e["event"],
                "event_tid": e["tid"],
                "event_frame": e["event_frame"],
                "frame_diff": df,
                "hand": e["hand"],
                "h3_confirmed": e["h3_confirmed"],
            })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        chains = load_h237v5_chains(stem)
        edges = load_h237_edges(stem)
        tracklets = load_tracklet_features(stem)

        # 1. Per-frame census
        events = extract_catch_throw_timeline(chains, edges, tracklets)
        census = compute_per_frame_census(chains, tracklets, events)

        # Census summary
        n0 = n1 = n2 = n3 = n4 = n_total = n_at_3 = 0
        if census:
            frame_counts = [c["n_total_balls"] for c in census.values()]
            n0 = sum(1 for c in census.values() if c["n_total_balls"] == 0)
            n1 = sum(1 for c in census.values() if c["n_total_balls"] == 1)
            n2 = sum(1 for c in census.values() if c["n_total_balls"] == 2)
            n3 = sum(1 for c in census.values() if c["n_total_balls"] == 3)
            n4 = sum(1 for c in census.values() if c["n_total_balls"] >= 4)
            n_total = len(census)
            n_at_3 = (n3 + n4)  # any time at 3+ balls = cascade
            print(f"  census frames: {n_total}, "
                  f"0={n0}/{n_total}={100*n0/n_total:.1f}%, "
                  f"1={n1}/{n_total}={100*n1/n_total:.1f}%, "
                  f"2={n2}/{n_total}={100*n2/n_total:.1f}%, "
                  f"3={n3}/{n_total}={100*n3/n_total:.1f}%, "
                  f"4+={n4}/{n_total}={100*n4/n_total:.1f}%")
            print(f"  cascade time (3+ balls): {100*n_at_3/n_total:.1f}%")

        # Write census CSV
        if census:
            with (H1_DATA / f"per_frame_census_{stem}.csv").open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["frame", "n_in_air", "n_in_hand_left",
                            "n_in_hand_right", "n_total_balls",
                            "balls_in_hand", "balls_in_air",
                            "avg_chain_quality"])
                for f in sorted(census.keys()):
                    c = census[f]
                    w.writerow([
                        f, c["n_in_air"], c["n_in_hand_left"],
                        c["n_in_hand_right"], c["n_total_balls"],
                        "|".join(c["balls_in_hand"]),
                        "|".join(c["balls_in_air"]),
                        f"{c['avg_chain_quality']:.3f}",
                    ])
            print(f"  wrote: per_frame_census_{stem}.csv")

        # 2. Catch/throw timeline
        if events:
            with (H1_DATA / f"catch_throw_timeline_{stem}.csv").open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
                w.writeheader()
                w.writerows(events)
            print(f"  wrote: catch_throw_timeline_{stem}.csv ({len(events)} events)")

        # 3. Identity-merge candidates
        merges = detect_identity_merges(chains, tracklets, events)
        # Filter to merges where both chains are CONFIDENT (>= 0.7)
        confident_merges = [m for m in merges
                            if m["cs_quality"] >= QUALITY_CONFIDENT]
        print(f"  identity merge candidates: {len(merges)}, "
              f"of which CONFIDENT-merge: {len(confident_merges)}")
        if confident_merges:
            print(f"  top 5 CONFIDENT-merge candidates:")
            for m in confident_merges[:5]:
                print(f"    {m['candidate_merge']}: {m['frame_diff']:+d}f, "
                      f"hand={m['hand']}, h3={m['h3_confirmed']}")

        summary["videos"][stem] = {
            "n_events": len(events),
            "n_census_frames": len(census),
            "census": {
                "pct_0": 100 * n0 / max(1, n_total) if census else 0,
                "pct_1": 100 * n1 / max(1, n_total) if census else 0,
                "pct_2": 100 * n2 / max(1, n_total) if census else 0,
                "pct_3": 100 * n3 / max(1, n_total) if census else 0,
                "pct_4+": 100 * n4 / max(1, n_total) if census else 0,
                "pct_cascade": 100 * n_at_3 / max(1, n_total) if census else 0,
            },
            "n_merge_candidates": len(merges),
            "n_confident_merge_candidates": len(confident_merges),
        }

    out = H1_DATA / "h11_v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
