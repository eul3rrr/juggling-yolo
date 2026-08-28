#!/usr/bin/env python3
"""H12 v7 - per-frame juggling pattern inference on H7v2 chains
with H10 v8 quality.

H12 v2 was the best event-log-based pattern classifier, but it
suffered on YouTube because H10 v5 over-counted chains (n_total=5
in 601/898 frames). H7v2 fixes the over-counting at its source by
reclassifying 25/27 BALLISTIC edges as HAND_TRANSITION. After
H7v2, YouTube chains are mostly reclassified (chain 0 has 6 hand
edges, 0 BALLISTIC edges).

H12 v7 hypothesis: re-running the v2 pattern inference on H7v2
chains with H10 v8 quality should give:
  * identical: minimal change (H7v2 reclassifies 13/37 edges
    but most chains have similar structure)
  * YouTube: substantial improvement. The 100% MIXED_3+_UNCONFIRMED
    on YouTube in v2 was caused by H10 v5 over-counting; v7
    should split into actual patterns.
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

K_EVENTS = 4
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0
RECENT_EVENT_FRAMES = 30
MIN_EVENTS_FOR_PATTERN = 3
HAND_REACH_PX = 108


def load_h7v2_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v2_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h7v2_admitted_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            def _f(s):
                if not s:
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
                "end_dist": _f(r["end_dist"]),
                "start_dist": _f(r["start_dist"]),
                "end_side": r["end_side"] or None,
                "start_side": r["start_side"] or None,
            }
    return out


def load_h10v8_quality(stem: str) -> dict[int, float]:
    out = {}
    with (H1_DATA / f"h10v8_chain_quality_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = float(r["quality_v8"])
    return out


def load_wrist_at_frame(stem: str) -> dict[int, dict]:
    """Load wrist positions per frame."""
    out = {}
    path = (WORKTREE / "detections" /
            f"{stem}_yolo26s-pose.csv")
    with path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            e = out.setdefault(f, {"left": None, "right": None})
            for side in ("left", "right"):
                x = r.get(f"{side}_wrist_x")
                y = r.get(f"{side}_wrist_y")
                c = r.get(f"{side}_wrist_confidence")
                if x and y and c and float(c) > 0.3:
                    e[side] = (float(x), float(y))
    return out


def parse_hand_from_metadata(metadata: str) -> str | None:
    m = re.search(r"hand=(\w+)", metadata)
    if m:
        return m.group(1)
    m = re.search(r"side=(\w+)", metadata)
    if m:
        return m.group(1)
    return None


def build_catch_throw_timeline(stem: str) -> list[dict]:
    """Build the CATCH/THROW timeline from h7v2 hand-edges only
    (HAND_TRANSITION, AMBIGUOUS_HAND_TRANSITION, RECLASSIFIED_HAND_TRANSITION).
    Returns list of {chain_id, event, tid, prev_tid, event_frame, hand, ...}.
    """
    chains = load_h7v2_chains(stem)
    edges = load_h7v2_admitted_edges(stem)
    tfs = load_tracklet_features(stem)
    h10v8_q = load_h10v8_quality(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    events = []
    for c in chains:
        cid = c["chain_id"]
        quality = h10v8_q.get(cid, 0.0)
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            if "HAND" not in e["edge_type"]:
                continue
            hand = None
            # Reclassified edges store the hand in the reclassify_reason
            # (e.g. "src_catch_dist=106.2_slope=-23.59_side=left")
            reason = e.get("reclassify_reason", "") or ""
            m = re.search(r"side=(\w+)", reason)
            if m:
                hand = m.group(1)
            if not hand:
                hand = parse_hand_from_metadata(e["metadata"]) or "unknown"
            # CATCH = arrival at the hand: this is when the
            # source tracklet ends (it's the catch moment).
            # The catch frame is the source's last_frame, which
            # is the same as the hand-edge's from_frame.
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            # CATCH = the source's last_frame (ball arrives at hand)
            events.append({
                "chain_id": cid,
                "event": "CATCH",
                "tid": to_tid,
                "prev_tid": from_tid,
                "event_frame": from_t["last_frame"],
                "prev_last_frame": from_t["last_frame"],
                "curr_first_frame": to_t["first_frame"],
                "gap_frames": to_t["first_frame"] - from_t["last_frame"],
                "hand": hand,
                "h3_confirmed": False,  # not relevant for v7 timeline
                "ambiguous": (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
                "chain_quality": quality,
                "edge_type": e["edge_type"],
            })
            # THROW = the target's first_frame (ball leaves hand)
            events.append({
                "chain_id": cid,
                "event": "THROW",
                "tid": to_tid,
                "prev_tid": from_tid,
                "event_frame": to_t["first_frame"],
                "prev_last_frame": from_t["last_frame"],
                "curr_first_frame": to_t["first_frame"],
                "gap_frames": to_t["first_frame"] - from_t["last_frame"],
                "hand": hand,
                "h3_confirmed": False,
                "ambiguous": (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
                "chain_quality": quality,
                "edge_type": e["edge_type"],
            })
    events.sort(key=lambda e: e["event_frame"])
    return events


def build_per_frame_census(stem: str) -> dict[int, dict]:
    """Build per-frame census from h7v2 chains.

    For each chain:
      - For each tracklet in the chain, the tracklet's points
        are "in air" (n_in_air += 1 for that frame).
      - For each hand-edge, the source's last_frame is "in hand"
        on the hand's side. (If the source's end_dist <= 108,
        the ball was at the hand when the catch happened.)
      - For the target's first_frame, the ball starts in the hand
        (just after catch). Track as "in hand" briefly.
    """
    chains = load_h7v2_chains(stem)
    tfs = load_tracklet_features(stem)
    edges = load_h7v2_admitted_edges(stem)
    h10v8_q = load_h10v8_quality(stem)
    wrists = load_wrist_at_frame(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    # Per-frame count accumulators
    in_air: dict[int, set[int]] = defaultdict(set)  # frame -> set of chain_ids
    in_hand_l: dict[int, set[int]] = defaultdict(set)
    in_hand_r: dict[int, set[int]] = defaultdict(set)
    chain_at_frame: dict[int, set[int]] = defaultdict(set)
    chain_qualities: dict[int, float] = h10v8_q

    for c in chains:
        cid = c["chain_id"]
        quality = chain_qualities.get(cid, 0.0)
        # Mark tracklet points as "in air" for this chain
        for tid in c["tids"]:
            if tid not in tfs:
                continue
            t = tfs[tid]
            for f in range(t["first_frame"], t["last_frame"] + 1):
                in_air[f].add(cid)
                chain_at_frame[f].add(cid)

        # Mark catch/throw moments
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            hand = parse_hand_from_metadata(e["metadata"])
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            # CATCH frame = from_t.last_frame
            catch_frame = from_t["last_frame"]
            # THROW frame = to_t.first_frame (or up to 3 frames after)
            throw_frame = to_t["first_frame"]
            # Ball is "in hand" at catch_frame and at throw_frame
            # (or 2 frames around throw if there's a brief hold).
            if hand == "left":
                for f in [catch_frame, throw_frame]:
                    in_hand_l[f].add(cid)
                    chain_at_frame[f].add(cid)
            elif hand == "right":
                for f in [catch_frame, throw_frame]:
                    in_hand_r[f].add(cid)
                    chain_at_frame[f].add(cid)
            else:
                # unknown hand: don't add to hand counts but
                # still count the chain
                for f in [catch_frame, throw_frame]:
                    chain_at_frame[f].add(cid)
            # Also mark the gap frames as in-hand if short (<= 5 frames)
            gap = to_t["first_frame"] - from_t["last_frame"]
            if 0 < gap <= 5 and hand in ("left", "right"):
                for f in range(catch_frame, throw_frame + 1):
                    if hand == "left":
                        in_hand_l[f].add(cid)
                    else:
                        in_hand_r[f].add(cid)
                    chain_at_frame[f].add(cid)

    # Build per-frame row
    out = {}
    all_frames = set(in_air.keys()) | set(in_hand_l.keys()) | \
                 set(in_hand_r.keys())
    for f in sorted(all_frames):
        n_air = len(in_air[f])
        n_l = len(in_hand_l[f])
        n_r = len(in_hand_r[f])
        # Total = unique chains active at this frame
        all_chains = set()
        all_chains |= in_air[f]
        all_chains |= in_hand_l[f]
        all_chains |= in_hand_r[f]
        n_total = len(all_chains)
        # avg_quality across active chains
        if all_chains:
            avg_q = sum(chain_qualities.get(c, 0.0) for c in all_chains) / n_total
        else:
            avg_q = 0.0
        out[f] = {
            "frame": f,
            "n_in_air": n_air,
            "n_in_hand_left": n_l,
            "n_in_hand_right": n_r,
            "n_total_balls": n_total,
            "avg_chain_quality": round(avg_q, 3),
        }
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
    return {
        "same_hand_run": same_hand_run,
        "unique_hands": unique_hands,
        "alternation_score": alternation_score,
        "n_events": n,
    }


def catch_rate(events_window: list[dict]) -> float:
    catches = [e for e in events_window if e["event"] == "CATCH"]
    if len(catches) < 2:
        return 0.0
    duration = float(int(catches[-1]["event_frame"]) -
                      int(catches[0]["event_frame"]))
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
    unique_hands = metrics["unique_hands"]

    if n < MIN_EVENTS_FOR_PATTERN:
        if n_in_hand_left == 1 and n_in_hand_right == 1:
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate
        if n_in_hand_left >= 2 or n_in_hand_right >= 2:
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.5, same_run, alt, rate

    cascade_like = (same_run <= CASCADE_MAX_SAME_HAND_RUN
                    and alt >= 0.5
                    and rate >= CASCADE_MIN_CATCH_RATE)
    fountain_like = (same_run >= n - 1 and alt < 0.3)

    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality, same_run, alt, rate
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality, same_run, alt, rate
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    return "MIXED_3+", avg_quality, same_run, alt, rate


def classify_pattern_v7(census_row: dict, events_window: list[dict],
                         recent_events: list[dict]) -> tuple:
    n_total = census_row["n_total_balls"]
    n_air = census_row["n_in_air"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    q = census_row["avg_chain_quality"]
    conf = max(q, 0.0)

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
        return classify_3ball(events_window, q, n_h_l, n_h_r)
    return "UNKNOWN", conf, 0, 0.0, 0.0


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
                    "start_frame": start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current,
                    "n_frames": r["frame"] - start,
                    "avg_confidence": round(sum(confs) / len(confs), 3),
                })
            current = r["pattern"]
            start = r["frame"]
            confs = [r["confidence"]]
        else:
            confs.append(r["confidence"])
    if current is not None:
        phases.append({
            "start_frame": start,
            "end_frame": results[-1]["frame"],
            "pattern": current,
            "n_frames": results[-1]["frame"] - start + 1,
            "avg_confidence": round(sum(confs) / len(confs), 3),
        })
    return phases


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H12 v7: H7v2 chains + H10 v8 quality) ===")
        census = build_per_frame_census(stem)
        events = build_catch_throw_timeline(stem)
        print(f"  census frames: {len(census)}")
        print(f"  events (CATCH+THROW): {len(events)}")
        n_catch = sum(1 for e in events if e["event"] == "CATCH")
        n_throw = sum(1 for e in events if e["event"] == "THROW")
        print(f"    CATCH: {n_catch}, THROW: {n_throw}")

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
            pattern, conf, same_run, alt, rate = classify_pattern_v7(
                c, events_window, recent)
            metrics = hand_alternation_metric(events_window)
            results.append({
                "frame": f,
                "n_in_air": c["n_in_air"],
                "n_in_hand_left": c["n_in_hand_left"],
                "n_in_hand_right": c["n_in_hand_right"],
                "n_total": c["n_total_balls"],
                "avg_quality": c["avg_chain_quality"],
                "pattern": pattern,
                "confidence": round(conf, 3),
                "n_window_events": len(events_window),
                "n_recent_events": len(recent),
                "same_hand_run": same_run,
                "unique_hands": metrics["unique_hands"],
                "alternation_score": round(alt, 3),
                "catch_rate_hz": round(rate, 2),
            })
            pattern_counts[pattern] += 1
            n_total_buckets[c["n_total_balls"]] += 1

        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        print(f"  n_total_balls distribution:")
        for n, c in sorted(n_total_buckets.items()):
            print(f"    n_total={n}: {c}/{n_total_frames} = {100*c/n_total_frames:.1f}%")
        print(f"  Pattern distribution:")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")

        phases = detect_phase_boundaries(results)
        sub_phases = [p for p in phases if p["n_frames"] >= 20]
        print(f"  Substantial phases (n_frames >= 20): {len(sub_phases)}")
        for p in sub_phases:
            print(f"    f={p['start_frame']}-{p['end_frame']} {p['pattern']} "
                  f"n={p['n_frames']} conf={p['avg_confidence']}")

        out_csv = H1_DATA / f"pattern_inference_v7_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_csv.name}")
        out_phases = H1_DATA / f"pattern_phases_v7_{stem}.csv"
        with out_phases.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(phases[0].keys()))
            w.writeheader()
            w.writerows(phases)
        print(f"  wrote: {out_phases.name}")
        # Also write the events timeline
        out_events = H1_DATA / f"catch_throw_timeline_v7_{stem}.csv"
        with out_events.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
            w.writeheader()
            w.writerows(events)
        print(f"  wrote: {out_events.name}")

        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "v7_pattern_counts": dict(pattern_counts),
            "v7_pct_patterns": {p: round(100 * n / n_total_frames, 1)
                                  for p, n in pattern_counts.items()},
            "n_total_balls_distribution": dict(n_total_buckets),
            "n_substantial_phases": len(sub_phases),
            "sub_phases": sub_phases,
            "n_events": len(events),
        }
    out = H1_DATA / "h12_v7_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
