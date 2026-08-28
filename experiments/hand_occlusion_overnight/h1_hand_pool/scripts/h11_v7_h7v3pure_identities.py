#!/usr/bin/env python3
"""H11 v7 — tracklet-level identity propagation on h7v3pure chains
with H10 v9 quality.

H11 v6 (be70399..14de483 cycle) propagated identities on H7v2 chains
with H10 v8 quality. H15v2 introduced a new edge type
V_RECLASSIFIED_HAND_TRANSITION (4 on identical, 1 on YouTube) and
H10 v9 uses per-video weights with V_RECLASSIFIED excluded from
the h3-eligible set.

H11 v7 hypothesis: re-running the v6 identity propagation on
h7v3pure chains + h10v9 quality should give the same chain
structure (chains are unchanged from h7v2) but with V_RECLASSIFIED
edges now correctly classified as catch/throw events.

The key change vs v6:
- Load h7v3pure_chains_*.csv (same chains as h7v2)
- Load h7v3pure_admitted_edges_*.csv (with V_RECLASSIFIED type)
- Load h10v9_chain_quality_*.csv quality_v9 (replacing v8)
- Treat V_RECLASSIFIED as a hand-edge for catch/throw event
  extraction (so the 4 new identical V-shape catch-throws are
  included in the event log)

This is a clean consumer experiment: the chain construction
pipeline is h7v2 + h15v2 (h7v3pure), and the chain quality is
H10 v9. H11 v7 just propagates identities through this updated
representation.
"""
from __future__ import annotations

import csv
import json
import re
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
MIN_HAND_EDGES_FOR_EVENTS = 1

# Hand-edge types include V_RECLASSIFIED in v7
HAND_EDGE_TYPES = {
    "HAND_TRANSITION",
    "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION",
    "V_RECLASSIFIED_HAND_TRANSITION",
}


def load_h7v3pure_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h7v3pure_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def load_h10v9(stem: str) -> dict[int, float]:
    out = {}
    with (H1_DATA / f"h10v9_chain_quality_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = float(r["quality_v9"])
    return out


def load_h3_confirmed(stem: str) -> set:
    """Returns {(from_tid, to_tid): True} for h3-confirmed hand-links."""
    confirmed = set()
    path = H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv"
    if not path.exists():
        return confirmed
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] == stem and r.get("h3_confirmed") == "True":
                confirmed.add((int(r["from_tid"]), int(r["to_tid"])))
    return confirmed


def load_tracklet_features(stem: str) -> dict:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
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


def parse_hand_from_edge(edge: dict) -> str:
    """Parse hand from edge metadata or reclassify_reason."""
    md = edge.get("metadata", "") or ""
    m = re.search(r"hand=(\w+)", md)
    if m:
        return m.group(1)
    reason = edge.get("reclassify_reason", "") or ""
    m = re.search(r"side=(\w+)", reason)
    if m:
        return m.group(1)
    # v7: V_RECLASSIFIED edges put hand in v_reclassify_reason
    v_reason = edge.get("v_reclassify_reason", "") or ""
    m = re.search(r"hand=(\w+)", v_reason)
    if m:
        return m.group(1)
    return "unknown"


def parse_tok_age(metadata: str) -> str:
    m = re.search(r"tok_age=(\d+)", metadata or "")
    return m.group(1) if m else "?"


def classify_chain(quality: float) -> str:
    if quality >= QUALITY_CONFIDENT:
        return "CONFIDENT"
    elif quality >= QUALITY_TRUSTABLE:
        return "UNCERTAIN"
    return "LOW"


def propagate_identities(chains: list[dict], edges: list[dict],
                          tracklets: dict, h10v9_q: dict) -> list[dict]:
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        quality = h10v9_q.get(cid, 0.0)
        classification = classify_chain(quality)
        ball_id = f"chain{cid}_ball0"

        for i, tid in enumerate(tids):
            this_ball_id = ball_id
            this_ambiguous = False
            this_hand_event = None
            this_hand = ""
            this_h3 = False
            this_tok_age = ""
            this_v_reclassified = False

            if i > 0:
                prev_tid = tids[i - 1]
                edge = by_pair.get((prev_tid, tid))
                if edge is None:
                    this_ball_id = f"chain{cid}_broken_at_{i}"
                    this_ambiguous = True
                else:
                    etype = edge["edge_type"]
                    this_hand = parse_hand_from_edge(edge)
                    this_tok_age = parse_tok_age(edge["metadata"])
                    this_h3 = (prev_tid, tid) in h3_confirmed_global
                    if etype in HAND_EDGE_TYPES:
                        this_ball_id = ball_id
                        if etype == "AMBIGUOUS_HAND_TRANSITION":
                            this_ambiguous = True
                        if etype == "V_RECLASSIFIED_HAND_TRANSITION":
                            this_v_reclassified = True
                        this_hand_event = "CATCH_AND_THROW"
                    else:
                        # BALLISTIC edge
                        this_ball_id = ball_id
                        this_hand_event = "BALLISTIC_CONTINUATION"
            else:
                this_hand_event = "CHAIN_START"

            tf = tracklets.get(tid, {})
            out.append({
                "chain_id": cid,
                "tid": tid,
                "ball_id": this_ball_id,
                "identity_ambiguous": this_ambiguous,
                "hand_event": this_hand_event,
                "hand": this_hand,
                "tok_age": this_tok_age,
                "h3_confirmed": this_h3,
                "v_reclassified": this_v_reclassified,
                "first_frame": tf.get("first_frame", ""),
                "last_frame": tf.get("last_frame", ""),
                "n_pts": tf.get("n_pts", ""),
                "chain_quality": quality,
                "chain_classification": classification,
            })
    return out


def extract_chain_events(chains: list[dict], edges: list[dict],
                          h10v9_q: dict) -> list[dict]:
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        quality = h10v9_q.get(cid, 0.0)
        classification = classify_chain(quality)
        n_hand = sum(1 for i in range(len(tids) - 1)
                      if by_pair.get((tids[i], tids[i + 1]))
                      and by_pair[(tids[i], tids[i + 1])]["edge_type"] in HAND_EDGE_TYPES)
        if n_hand < MIN_HAND_EDGES_FOR_EVENTS:
            continue
        if quality < QUALITY_TRUSTABLE:
            continue

        for i in range(len(tids) - 1):
            prev_tid = tids[i]
            tid = tids[i + 1]
            edge = by_pair.get((prev_tid, tid))
            if not edge or edge["edge_type"] not in HAND_EDGE_TYPES:
                continue
            etype = edge["edge_type"]
            is_ambiguous = (etype == "AMBIGUOUS_HAND_TRANSITION")
            is_reclassified = (etype == "RECLASSIFIED_HAND_TRANSITION")
            is_v_reclassified = (etype == "V_RECLASSIFIED_HAND_TRANSITION")
            this_hand = parse_hand_from_edge(edge)
            this_tok_age = parse_tok_age(edge["metadata"])
            h3 = (prev_tid, tid) in h3_confirmed_global
            for ev in ("CATCH", "THROW"):
                out.append({
                    "chain_id": cid,
                    "event": ev,
                    "tid": tid,
                    "prev_tid": prev_tid,
                    "hand": this_hand,
                    "tok_age": this_tok_age,
                    "h3_confirmed": h3,
                    "ambiguous": is_ambiguous,
                    "reclassified": is_reclassified,
                    "v_reclassified": is_v_reclassified,
                    "chain_quality": quality,
                    "chain_classification": classification,
                    "edge_type": etype,
                })
    return out


h3_confirmed_global = set()


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H11 v7) ===")
        global h3_confirmed_global
        h3_confirmed_global = load_h3_confirmed(stem)
        chains = load_h7v3pure_chains(stem)
        edges = load_h7v3pure_edges(stem)
        tracklets = load_tracklet_features(stem)
        h10v9_q = load_h10v9(stem)

        # 1. Per-tracklet identity records
        identities = propagate_identities(chains, edges, tracklets, h10v9_q)
        # 2. Per-chain catch/throw events
        events = extract_chain_events(chains, edges, h10v9_q)

        n_confident_chains = sum(1 for c in chains
                                 if h10v9_q.get(c["chain_id"], 0.0) >= QUALITY_CONFIDENT)
        n_uncertain_chains = sum(1 for c in chains
                                 if QUALITY_TRUSTABLE <= h10v9_q.get(c["chain_id"], 0.0) < QUALITY_CONFIDENT)
        n_low_chains = sum(1 for c in chains
                           if h10v9_q.get(c["chain_id"], 0.0) < QUALITY_TRUSTABLE)
        n_multi_confident = sum(1 for c in chains
                                if h10v9_q.get(c["chain_id"], 0.0) >= QUALITY_CONFIDENT
                                and c["n_tracklets"] >= 2)
        n_catches = sum(1 for e in events if e["event"] == "CATCH")
        n_throws = sum(1 for e in events if e["event"] == "THROW")
        n_h3_confirmed_events = sum(1 for e in events if e["h3_confirmed"])
        n_reclassified_events = sum(1 for e in events if e["reclassified"])
        n_v_reclassified_events = sum(1 for e in events if e["v_reclassified"])
        n_ambiguous_events = sum(1 for e in events if e["ambiguous"])

        print(f"  chains: total={len(chains)}, "
              f"CONFIDENT={n_confident_chains}, "
              f"UNCERTAIN={n_uncertain_chains}, "
              f"LOW={n_low_chains}")
        print(f"  multi-tracklet CONFIDENT chains: {n_multi_confident}")
        print(f"  CATCH events: {n_catches}, THROW events: {n_throws}")
        print(f"  h3_confirmed events: {n_h3_confirmed_events}")
        print(f"  reclassified events: {n_reclassified_events}")
        print(f"  v_reclassified events: {n_v_reclassified_events}")
        print(f"  ambiguous events: {n_ambiguous_events}")

        # Write CSVs
        out_id = H1_DATA / f"tracklet_identity_v7_{stem}.csv"
        with out_id.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(identities[0].keys()))
            w.writeheader()
            w.writerows(identities)
        print(f"  wrote: {out_id.name} ({len(identities)} tracklets)")

        if events:
            out_ev = H1_DATA / f"chain_events_v7_{stem}.csv"
            with out_ev.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
                w.writeheader()
                w.writerows(events)
            print(f"  wrote: {out_ev.name} ({len(events)} events)")

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_confident_chains": n_confident_chains,
            "n_uncertain_chains": n_uncertain_chains,
            "n_low_chains": n_low_chains,
            "n_multi_confident": n_multi_confident,
            "n_catches": n_catches,
            "n_throws": n_throws,
            "n_h3_confirmed_events": n_h3_confirmed_events,
            "n_reclassified_events": n_reclassified_events,
            "n_v_reclassified_events": n_v_reclassified_events,
            "n_ambiguous_events": n_ambiguous_events,
            "n_tracklets_with_identity": len(identities),
        }

    out = H1_DATA / "h11_v7_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
