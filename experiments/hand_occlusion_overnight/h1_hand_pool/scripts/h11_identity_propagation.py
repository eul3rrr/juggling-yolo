#!/usr/bin/env python3
"""H11 - tracklet-level identity propagation across H7 chains.

Hypothesis: given a high-quality H10 v5 chain, the entire chain
represents ONE physical ball identity. Walking through the chain:

  - Each tracklet inherits its predecessor's physical ball ID.
  - A HAND_TRANSITION (hand-edge) inside the chain is a CATCH
    on the same physical ball (the ball enters the hand then
    re-emerges as the next tracklet).
  - An AMBIGUOUS_HAND_TRANSITION is also a CATCH on the same
    physical ball IF the pool had only 1 token; otherwise the
    identity is mixed (FIFO picks one arbitrarily, but
    identity_ambiguous=True is the right thing to record).
  - A BALLISTIC edge is mid-air; same physical ball ID.
  - The first tracklet of a chain is the "entry" (no
    predecessor, can't validate from this side).

For chain-as-a-whole, the chain's physical ball identity is:
  - if quality >= 0.7: CONFIDENT (the chain is one ball)
  - if 0.4 <= quality < 0.7: UNCERTAIN (may be a single ball
    with some noise, or may contain an identity switch)
  - if quality < 0.4: LOW (likely contains an identity switch
    or is a false-ballistic chain)

For chains with N_HAND_EDGES >= 1 AND quality >= 0.5, we can
extract CATCH/THROW events with structural semantics:
  - CATCH at (from_tid, to_frame_of_catch)  (hand-edge: the
    ball entered the hand between the two tracklets)
  - THROW at (to_tid, from_frame_of_throw)  (hand-edge: the
    ball left the hand between the two tracklets)
  - Each CATCH/THROW has a hand attribution (left/right) and
    a confidence flag (h3_confirmed)

We export:
  - tracklet_identity_<stem>.csv: per-tracklet ball_id, chain_id, quality
  - chain_events_<stem>.csv: per-chain CATCH/THROW events
  - h11_summary.json: aggregate counts and chain classifications
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

# Quality thresholds (declared from physical geometry, not from labels).
# The high threshold picks chains that H10 v5 confidently identifies as
# single physical balls. The low threshold picks chains where we shouldn't
# trust identity at all.
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4
# For catch/throw extraction, we want at least 1 hand-edge in the chain.
MIN_HAND_EDGES_FOR_EVENTS = 1


def load_h237v5_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            r["n_tracklets"] = int(r["n_tracklets"])
            r["n_hand_edges"] = int(r["n_hand_edges"])
            r["n_air_edges"] = int(r["n_air_edges"])
            r["n_h3_confirmed"] = int(r["n_h3_confirmed"])
            r["h10_v3_quality"] = float(r["h10_v3_quality"])
            r["h10_v5_quality"] = float(r["h10_v5_quality"])
            r["h10_v3_rank"] = int(r["h10_v3_rank"])
            r["h10_v5_rank"] = int(r["h10_v5_rank"])
            r["h10_quality_delta"] = float(r["h10_quality_delta"])
            r["chain_id"] = int(r["chain_id"])
            out.append(r)
    return out


def load_h237_edges(stem: str) -> dict:
    """Returns {(from_tid, to_tid): edge_dict}."""
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


def parse_hand_metadata(metadata: str) -> dict:
    """Parse 'tok_age=20,hand=left' style metadata into a dict."""
    if not metadata:
        return {}
    out = {}
    for part in metadata.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def load_tracklet_features(stem: str) -> dict:
    """Returns {tid: feature_dict}."""
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


def classify_chain(quality: float) -> str:
    if quality >= QUALITY_CONFIDENT:
        return "CONFIDENT"
    elif quality >= QUALITY_TRUSTABLE:
        return "UNCERTAIN"
    else:
        return "LOW"


def propagate_identities(chains: list[dict], edges: dict,
                         tracklets: dict) -> list[dict]:
    """For each chain, assign a physical ball ID to each tracklet
    and emit per-tracklet identity records.

    Ball ID assignment:
      - First tracklet of chain: starts a new physical ball ID
      - Mid-chain tracklet: inherits predecessor's ball ID
      - Hand-edge (HAND_TRANSITION or AMBIGUOUS_HAND_TRANSITION):
        if pool had 1 token, the next tracklet is the SAME ball
        (catch-throw of the same ball). If pool was ambiguous
        (>1 token), mark identity_ambiguous=True.
      - Ballistic edge: same physical ball ID
    """
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        quality = chain["h10_v5_quality"]
        classification = classify_chain(quality)
        ball_id = f"chain{cid}_ball0"

        for i, tid in enumerate(tids):
            # Default: inherit from predecessor (or this chain's ball)
            this_ball_id = ball_id
            this_ambiguous = False
            this_hand_event = None

            if i > 0:
                prev_tid = tids[i - 1]
                edge = edges.get((prev_tid, tid))
                if edge is None:
                    # Should not happen for a valid chain; flag as broken
                    this_ball_id = f"chain{cid}_broken_at_{i}"
                    this_ambiguous = True
                else:
                    etype = edge["edge_type"]
                    md = parse_hand_metadata(edge["metadata"])
                    if etype in ("HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION"):
                        # Catch-throw: same physical ball, but mark
                        # the transition with the hand
                        this_ball_id = ball_id  # same ball
                        if etype == "AMBIGUOUS_HAND_TRANSITION":
                            this_ambiguous = True
                        this_hand_event = {
                            "prev_tid": prev_tid,
                            "tid": tid,
                            "kind": "CATCH_AND_THROW" if i > 0 else "CATCH",
                            "hand": md.get("hand", "?"),
                            "tok_age": md.get("tok_age", "?"),
                            "h3_confirmed": edge["h3_confirmed"],
                        }
                    else:
                        # BALLISTIC: same physical ball, no hand event
                        this_ball_id = ball_id
            else:
                # First tracklet of chain: this is the "entry" of
                # a physical ball. We don't know which physical ball
                # it is (could be the first ball the juggler picks
                # up, or a re-entry from a held phase we missed).
                this_hand_event = {
                    "prev_tid": None,
                    "tid": tid,
                    "kind": "CHAIN_START",
                    "hand": "n/a",
                    "tok_age": "n/a",
                    "h3_confirmed": False,
                }

            tf = tracklets.get(tid, {})
            out.append({
                "chain_id": cid,
                "tid": tid,
                "ball_id": this_ball_id,
                "identity_ambiguous": this_ambiguous,
                "hand_event": this_hand_event["kind"] if this_hand_event else "",
                "hand": this_hand_event.get("hand", "") if this_hand_event else "",
                "h3_confirmed": this_hand_event.get("h3_confirmed", False) if this_hand_event else False,
                "first_frame": tf.get("first_frame", ""),
                "last_frame": tf.get("last_frame", ""),
                "n_pts": tf.get("n_pts", ""),
                "chain_quality": quality,
                "chain_classification": classification,
            })
    return out


def extract_chain_events(chains: list[dict], edges: dict) -> list[dict]:
    """For each chain with at least 1 hand-edge, extract CATCH and
    THROW events with structural semantics.

    A HAND_TRANSITION from tracklet A to tracklet B represents:
      - CATCH at B's first frame (the ball was caught there)
      - THROW at A's last frame (the ball was thrown from there)
    Or, more precisely:
      - CATCH: the moment the ball arrived at the hand (between
        A's last observation and B's first observation)
      - THROW: the moment the ball left the hand (between
        A's last observation and B's first observation)

    We use A's last_frame as the catch/throw moment (where the
    ball was when it entered/left the hand).
    """
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        quality = chain["h10_v5_quality"]
        classification = classify_chain(quality)
        if chain["n_hand_edges"] < MIN_HAND_EDGES_FOR_EVENTS:
            continue
        if quality < QUALITY_TRUSTABLE:
            # Don't emit events from chains we don't trust
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

            # Emit a CATCH event (ball arrived at the hand)
            out.append({
                "chain_id": cid,
                "event": "CATCH",
                "tid": tid,
                "prev_tid": prev_tid,
                "frame": i,  # placeholder, filled below
                "hand": md.get("hand", "?"),
                "tok_age": md.get("tok_age", "?"),
                "h3_confirmed": edge["h3_confirmed"],
                "ambiguous": etype == "AMBIGUOUS_HAND_TRANSITION",
                "chain_quality": quality,
                "chain_classification": classification,
                "edge_type": etype,
            })
            # Emit a THROW event (ball left the hand)
            out.append({
                "chain_id": cid,
                "event": "THROW",
                "tid": tid,
                "prev_tid": prev_tid,
                "frame": i,  # placeholder
                "hand": md.get("hand", "?"),
                "tok_age": md.get("tok_age", "?"),
                "h3_confirmed": edge["h3_confirmed"],
                "ambiguous": etype == "AMBIGUOUS_HAND_TRANSITION",
                "chain_quality": quality,
                "chain_classification": classification,
                "edge_type": etype,
            })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        chains = load_h237v5_chains(stem)
        edges = load_h237_edges(stem)
        tracklets = load_tracklet_features(stem)

        # 1. Per-tracklet identity records
        identities = propagate_identities(chains, edges, tracklets)
        # 2. Per-chain catch/throw events
        events = extract_chain_events(chains, edges)

        # 3. Aggregate stats
        by_class = defaultdict(int)
        for r in identities:
            by_class[r["chain_classification"]] += 1
        n_confident_chains = sum(1 for c in chains
                                 if c["h10_v5_quality"] >= QUALITY_CONFIDENT)
        n_uncertain_chains = sum(1 for c in chains
                                 if QUALITY_TRUSTABLE <= c["h10_v5_quality"] < QUALITY_CONFIDENT)
        n_low_chains = sum(1 for c in chains
                           if c["h10_v5_quality"] < QUALITY_TRUSTABLE)
        n_multi_confident = sum(1 for c in chains
                                if c["h10_v5_quality"] >= QUALITY_CONFIDENT
                                and c["n_tracklets"] >= 2)
        n_catches = sum(1 for e in events if e["event"] == "CATCH")
        n_throws = sum(1 for e in events if e["event"] == "THROW")
        n_h3_confirmed_events = sum(1 for e in events if e["h3_confirmed"])
        n_ambiguous_events = sum(1 for e in events if e["ambiguous"])

        print(f"  chains: total={len(chains)}, "
              f"CONFIDENT={n_confident_chains}, "
              f"UNCERTAIN={n_uncertain_chains}, "
              f"LOW={n_low_chains}")
        print(f"  multi-tracklet CONFIDENT chains: {n_multi_confident}")
        print(f"  CATCH events: {n_catches}, THROW events: {n_throws}")
        print(f"  h3_confirmed events: {n_h3_confirmed_events}")
        print(f"  ambiguous events: {n_ambiguous_events}")

        # Write CSVs
        out_id = H1_DATA / f"tracklet_identity_{stem}.csv"
        with out_id.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(identities[0].keys()))
            w.writeheader()
            w.writerows(identities)
        print(f"  wrote: {out_id.name} ({len(identities)} tracklets)")

        if events:
            out_ev = H1_DATA / f"chain_events_{stem}.csv"
            with out_ev.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
                w.writeheader()
                w.writerows(events)
            print(f"  wrote: {out_ev.name} ({len(events)} events)")
        else:
            print(f"  (no catch/throw events emitted)")

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_confident_chains": n_confident_chains,
            "n_uncertain_chains": n_uncertain_chains,
            "n_low_chains": n_low_chains,
            "n_multi_confident": n_multi_confident,
            "n_catches": n_catches,
            "n_throws": n_throws,
            "n_h3_confirmed_events": n_h3_confirmed_events,
            "n_ambiguous_events": n_ambiguous_events,
            "n_tracklets_with_identity": len(identities),
            "quality_thresholds": {
                "CONFIDENT": QUALITY_CONFIDENT,
                "TRUSTABLE": QUALITY_TRUSTABLE,
            },
        }

    out = H1_DATA / "h11_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
