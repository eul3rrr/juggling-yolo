#!/usr/bin/env python3
"""H35 - re-run H12 pattern inference + H11 identity propagation
on h7v3plus3 chains (H22 + H26 combined).

HYPOTHESIS:
  H22 split the YouTube 7-tid chain (1,9,13,16,21,29,34) into two
  4-tid chains (1,9,13,16) and (20,21,29,34). H11 v7 / H12 v8
  were computed on h7v3pure (the old chain set). We need to
  re-measure on h7v3plus3 to:
  1. See if the chain split changes the per-frame census
  2. See if the new chain 10 (20,21,29,34) has correct identity
  3. See if the pattern inference catches different patterns on
     the 4-tid vs 7-tid chain

EXPECTED:
  - identical: identical to h7v3plus2 (no H22 change)
  - YouTube: chain 0 (1,9,13,16) loses 3 tids (21,29,34),
    new chain 10 (20,21,29,34) gains 3 tids
  - Catch/throw events on YouTube: the 7-tid chain had ~6 events;
    split chains should have ~3+3=6 events total
  - Pattern inference: short chains have weaker catch_rate signal,
    may shift some patterns from CASCADE to MIXED_3+
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

# Constants from H12 v7
K_EVENTS = 4
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0
RECENT_EVENT_FRAMES = 30
MIN_EVENTS_FOR_PATTERN = 3

# H11 v7 thresholds
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4

# Hand-edge types (H11 v7 set)
HAND_EDGE_TYPES = {
    "HAND_TRANSITION",
    "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION",
    "V_RECLASSIFIED_HAND_TRANSITION",
    "H26_RECLASSIFIED_HAND_TRANSITION",
    "H22_RECLASSIFIED_HAND_TRANSITION",  # NEW in H35
}


def load_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus3_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            try:
                r["cost"] = float(r["cost"])
            except (ValueError, KeyError, TypeError):
                r["cost"] = None
            out.append(r)
    return out


def load_quality(stem: str) -> dict[int, float]:
    out = {}
    with (H1_DATA / f"h10v10_h7v3plus3_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = float(r["quality_v10"])
    return out


def load_tracklets(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
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
    md = edge.get("metadata", "") or ""
    m = re.search(r"hand=(\w+)", md)
    if m:
        return m.group(1)
    reason = edge.get("reclassify_reason", "") or ""
    m = re.search(r"side=(\w+)", reason)
    if m:
        return m.group(1)
    v_reason = edge.get("v_reclassify_reason", "") or ""
    m = re.search(r"hand=(\w+)", v_reason)
    if m:
        return m.group(1)
    # H35: H22/H26 edges store hand in h22_reason / h26_reason
    h22_reason = edge.get("h22_reason", "") or ""
    h26_reason = edge.get("h26_reason", "") or ""
    for rsn in (h22_reason, h26_reason):
        m = re.search(r"hand=(\w+)", rsn)
        if m:
            return m.group(1)
        m = re.search(r"which_hand=(\w+)", rsn)
        if m:
            return m.group(1)
    return "unknown"


def classify_chain(quality: float) -> str:
    if quality >= QUALITY_CONFIDENT:
        return "CONFIDENT"
    elif quality >= QUALITY_TRUSTABLE:
        return "UNCERTAIN"
    return "LOW"


def extract_chain_events(chains: list[dict], edges: list[dict],
                          quality: dict, tracklets: dict) -> list[dict]:
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        q = quality.get(cid, 0.0)
        if q < QUALITY_TRUSTABLE:
            continue
        for i in range(len(tids) - 1):
            prev_tid = tids[i]
            tid = tids[i + 1]
            edge = by_pair.get((prev_tid, tid))
            if not edge or edge["edge_type"] not in HAND_EDGE_TYPES:
                continue
            etype = edge["edge_type"]
            from_t = tracklets[prev_tid]
            to_t = tracklets[tid]
            catch_frame = from_t["last_frame"]
            throw_frame = to_t["first_frame"]
            for ev, frame in (("CATCH", catch_frame), ("THROW", throw_frame)):
                out.append({
                    "chain_id": cid,
                    "event": ev,
                    "tid": tid,
                    "prev_tid": prev_tid,
                    "event_frame": frame,
                    "hand": parse_hand_from_edge(edge),
                    "ambiguous": (etype == "AMBIGUOUS_HAND_TRANSITION"),
                    "v_reclassified": (etype == "V_RECLASSIFIED_HAND_TRANSITION"),
                    "h22_reclassified": (etype == "H22_RECLASSIFIED_HAND_TRANSITION"),
                    "h26_reclassified": (etype == "H26_RECLASSIFIED_HAND_TRANSITION"),
                    "chain_quality": q,
                    "chain_classification": classify_chain(q),
                    "edge_type": etype,
                })
    return out


def propagate_identities(chains: list[dict], edges: list[dict],
                          tracklets: dict, quality: dict) -> list[dict]:
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
    out = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        q = quality.get(cid, 0.0)
        classification = classify_chain(q)
        ball_id = f"chain{cid}_ball0"

        for i, tid in enumerate(tids):
            this_ball_id = ball_id
            this_ambiguous = False
            this_hand_event = None
            this_hand = ""
            if i > 0:
                prev_tid = tids[i - 1]
                edge = by_pair.get((prev_tid, tid))
                if edge is None:
                    this_ball_id = f"chain{cid}_broken_at_{i}"
                    this_ambiguous = True
                else:
                    etype = edge["edge_type"]
                    this_hand = parse_hand_from_edge(edge)
                    if etype in HAND_EDGE_TYPES:
                        this_ball_id = ball_id
                        if etype == "AMBIGUOUS_HAND_TRANSITION":
                            this_ambiguous = True
                        this_hand_event = "CATCH_AND_THROW"
                    else:
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
                "first_frame": tf.get("first_frame", ""),
                "last_frame": tf.get("last_frame", ""),
                "n_pts": tf.get("n_pts", ""),
                "chain_quality": q,
                "chain_classification": classification,
            })
    return out


def hand_alternation_metric(events_window: list[dict]) -> dict:
    if not events_window:
        return {"same_hand_run": 0, "unique_hands": 0,
                "alternation_score": 0.0, "n_events": 0}
    hands = [e["hand"] for e in events_window]
    n = len(hands)
    same_hand_run = sum(1 for i in range(1, n) if hands[i] == hands[i - 1])
    unique_hands = len(set(h for h in hands if h and h != "unknown"))
    if n <= 1:
        alternation_score = 0.0
    else:
        alternation_score = 1.0 - (same_hand_run / (n - 1))
    return {"same_hand_run": same_hand_run, "unique_hands": unique_hands,
            "alternation_score": alternation_score, "n_events": n}


def catch_rate(events_window: list[dict]) -> float:
    catches = [e for e in events_window if e["event"] == "CATCH"]
    if len(catches) < 2:
        return 0.0
    duration = int(catches[-1]["event_frame"]) - int(catches[0]["event_frame"])
    if duration <= 0:
        return 0.0
    return len(catches) * 30.0 / duration


def classify_3ball(events_window: list[dict], avg_quality: float,
                    n_in_hand_left: int, n_in_hand_right: int) -> tuple:
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]
    same_run = metrics["same_hand_run"]
    alt = metrics["alternation_score"]

    if n < MIN_EVENTS_FOR_PATTERN:
        if n_in_hand_left >= 1 or n_in_hand_right >= 1:
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.5

    cascade_like = (same_run <= CASCADE_MAX_SAME_HAND_RUN
                    and alt >= 0.5
                    and rate >= CASCADE_MIN_CATCH_RATE)
    fountain_like = (same_run >= n - 1 and alt < 0.3)

    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality
        return "FOUNTAIN_3+", avg_quality
    return "MIXED_3+", avg_quality


def classify_pattern_v7(census_row: dict, events_window: list[dict],
                         recent_events: list[dict]) -> tuple:
    n_total = census_row["n_total_balls"]
    n_air = census_row["n_in_air"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    q = census_row["avg_chain_quality"]
    conf = max(q, 0.0)

    if n_total == 0:
        return "NO_BALL", 1.0
    if n_total == 1:
        return "SINGLE_BALL", conf
    if n_total == 2:
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", conf
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", conf
        return "TWO_BALL", conf
    if n_total >= 3:
        return classify_3ball(events_window, q, n_h_l, n_h_r)
    return "UNKNOWN", conf


def build_per_frame_census(stem: str, chains: list[dict], edges: list[dict],
                            tracklets: dict, quality: dict) -> dict:
    in_air = defaultdict(set)
    in_hand_l = defaultdict(set)
    in_hand_r = defaultdict(set)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    for c in chains:
        cid = c["chain_id"]
        for tid in c["tids"]:
            if tid not in tracklets:
                continue
            t = tracklets[tid]
            for f in range(t["first_frame"], t["last_frame"] + 1):
                in_air[f].add(cid)

        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            hand = parse_hand_from_edge(e)
            from_t = tracklets[from_tid]
            to_t = tracklets[to_tid]
            catch_frame = from_t["last_frame"]
            throw_frame = to_t["first_frame"]
            if hand == "left":
                for f in [catch_frame, throw_frame]:
                    in_hand_l[f].add(cid)
            elif hand == "right":
                for f in [catch_frame, throw_frame]:
                    in_hand_r[f].add(cid)
            gap = to_t["first_frame"] - from_t["last_frame"]
            if 0 < gap <= 5 and hand in ("left", "right"):
                for f in range(catch_frame, throw_frame + 1):
                    if hand == "left":
                        in_hand_l[f].add(cid)
                    else:
                        in_hand_r[f].add(cid)

    out = {}
    all_frames = set(in_air.keys()) | set(in_hand_l.keys()) | set(in_hand_r.keys())
    for f in sorted(all_frames):
        n_air = len(in_air[f])
        n_l = len(in_hand_l[f])
        n_r = len(in_hand_r[f])
        all_chains = set()
        all_chains |= in_air[f]
        all_chains |= in_hand_l[f]
        all_chains |= in_hand_r[f]
        n_total = len(all_chains)
        avg_q = (sum(quality.get(c, 0.0) for c in all_chains) / n_total
                 if n_total > 0 else 0.0)
        out[f] = {"frame": f, "n_in_air": n_air,
                  "n_in_hand_left": n_l, "n_in_hand_right": n_r,
                  "n_total_balls": n_total, "avg_chain_quality": round(avg_q, 3)}
    return out


def detect_phase_boundaries(results: list[dict]) -> list[dict]:
    if not results:
        return []
    phases = []
    current = None
    start = None
    confs = []
    for r in results:
        if r["pattern"] != current:
            if current is not None:
                phases.append({
                    "start_frame": start, "end_frame": r["frame"] - 1,
                    "pattern": current, "n_frames": r["frame"] - start,
                    "avg_confidence": round(sum(confs) / len(confs), 3),
                })
            current = r["pattern"]
            start = r["frame"]
            confs = [r["confidence"]]
        else:
            confs.append(r["confidence"])
    if current is not None:
        phases.append({
            "start_frame": start, "end_frame": results[-1]["frame"],
            "pattern": current, "n_frames": results[-1]["frame"] - start + 1,
            "avg_confidence": round(sum(confs) / len(confs), 3),
        })
    return phases


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H35: h7v3plus3 chains + h10v10 quality) ===")
        chains = load_chains(stem)
        edges = load_edges(stem)
        tracklets = load_tracklets(stem)
        quality = load_quality(stem)

        # H11 identity propagation
        identities = propagate_identities(chains, edges, tracklets, quality)
        events = extract_chain_events(chains, edges, quality, tracklets)
        n_conf = sum(1 for c in chains if quality.get(c["chain_id"], 0) >= QUALITY_CONFIDENT)
        n_multi_conf = sum(1 for c in chains
                           if quality.get(c["chain_id"], 0) >= QUALITY_CONFIDENT
                           and c["n_tracklets"] >= 2)
        n_catch = sum(1 for e in events if e["event"] == "CATCH")
        n_throw = sum(1 for e in events if e["event"] == "THROW")
        n_h22_events = sum(1 for e in events if e["h22_reclassified"])
        n_h26_events = sum(1 for e in events if e["h26_reclassified"])
        n_v_events = sum(1 for e in events if e["v_reclassified"])
        print(f"  H11: chains={len(chains)} CONFIDENT={n_conf} multi_CONF={n_multi_conf}")
        print(f"  H11: CATCH={n_catch} THROW={n_throw}")
        print(f"  H11: h22_events={n_h22_events} h26_events={n_h26_events} "
              f"v_reclass_events={n_v_events}")

        # H12 pattern inference (uses h11 events)
        census = build_per_frame_census(stem, chains, edges, tracklets, quality)
        events_by_frame = defaultdict(list)
        for e in events:
            events_by_frame[int(e["event_frame"])].append(e)
        events_sorted = sorted(events, key=lambda e: int(e["event_frame"]))

        results = []
        pattern_counts = defaultdict(int)
        n_total_buckets = defaultdict(int)
        for f, c in sorted(census.items()):
            events_before = [e for e in events_sorted
                              if int(e["event_frame"]) <= f]
            events_window = events_before[-K_EVENTS:]
            recent = []
            for df in range(-RECENT_EVENT_FRAMES, RECENT_EVENT_FRAMES + 1):
                recent.extend(events_by_frame.get(f + df, []))
            pattern, conf = classify_pattern_v7(c, events_window, recent)
            results.append({
                "frame": f,
                "n_in_air": c["n_in_air"],
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total_balls"],
                "avg_quality": c["avg_chain_quality"],
                "pattern": pattern,
                "confidence": round(conf, 3),
            })
            pattern_counts[pattern] += 1
            n_total_buckets[c["n_total_balls"]] += 1

        n_total_frames = len(results)
        print(f"  H12: census_frames={n_total_frames}")
        print(f"  H12: pattern distribution:")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")
        print(f"  H12: n_total distribution:")
        for n, c in sorted(n_total_buckets.items()):
            print(f"    n_total={n}: {c}/{n_total_frames} = {100*c/n_total_frames:.1f}%")

        phases = detect_phase_boundaries(results)
        sub_phases = [p for p in phases if p["n_frames"] >= 20]
        print(f"  H12: substantial phases (n_frames >= 20): {len(sub_phases)}")
        for p in sub_phases:
            print(f"    f={p['start_frame']}-{p['end_frame']} {p['pattern']} "
                  f"n={p['n_frames']} conf={p['avg_confidence']}")

        # Write outputs
        out_id = H1_DATA / f"tracklet_identity_h35_{stem}.csv"
        with out_id.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(identities[0].keys()))
            w.writeheader()
            w.writerows(identities)
        print(f"  wrote: {out_id.name} ({len(identities)} tracklets)")

        if events:
            out_ev = H1_DATA / f"chain_events_h35_{stem}.csv"
            with out_ev.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
                w.writeheader()
                w.writerows(events)
            print(f"  wrote: {out_ev.name} ({len(events)} events)")

        out_pat = H1_DATA / f"pattern_inference_h35_{stem}.csv"
        with out_pat.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_pat.name} ({len(results)} frames)")

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "n_confident_chains": n_conf,
            "n_multi_confident": n_multi_conf,
            "n_catches": n_catch,
            "n_throws": n_throw,
            "n_h22_events": n_h22_events,
            "n_h26_events": n_h26_events,
            "n_v_reclass_events": n_v_events,
            "pattern_distribution": dict(pattern_counts),
            "n_total_distribution": dict(n_total_buckets),
            "n_substantial_phases": len(sub_phases),
        }

    out = H1_DATA / "h35_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
