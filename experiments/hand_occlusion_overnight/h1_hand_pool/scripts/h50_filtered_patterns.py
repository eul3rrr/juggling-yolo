#!/usr/bin/env python3
"""H50: H12 v8 per-frame pattern inference on FILTERED event log.

HYPOTHESIS:
  H47/H48 showed the 10-frame flight-time filter drops 3/48 events on
  identical (all identity switches) and 0/50 on YouTube. H49 measured
  the K=4-only impact as an UPPER BOUND (45.2% identical frames
  re-classified, 15.9% YouTube), but acknowledged that the K=4-only
  classifier does NOT apply H12 v8's full pipeline (census + chain
  quality + n_total balls).

  H50 IMPLEMENTS the proper measurement: re-run H12 v8's full pipeline
  (per-frame census + K=4 events + chain quality + n_total) with the
  filtered event log, and report the actual pattern distribution change
  vs the unfiltered H12 v8 baseline.

  This closes the H49 negative result and provides a final, validated
  H12 v8 + 10-frame filter operating point.

METHOD:
  1. Load H12 v8's full pattern pipeline (chains, census, events, quality).
  2. Re-build the catch/throw timeline with the 10-frame flight-time
     filter applied (drop THROW+CATCH pairs where the THROW's flight
     time to the next CATCH in the same chain is < 10 frames).
  3. Run the per-frame pattern inference on the filtered timeline.
  4. Compare the pattern distribution to the H12 v8 baseline.
  5. Render contact sheets for substantial phase changes.

THRESHOLDS (declared from prior findings, not tuned to labels):
  - MIN_FLIGHT_TIME = 10 frames (H45/H48 finding: 10 is in a flat region)
  - K_EVENTS = 4 (H12 v8 default)
  - CASCADE_MAX_SAME_HAND_RUN = 1
  - CASCADE_MIN_CATCH_RATE = 1.0
  - RECENT_EVENT_FRAMES = 30
  - MIN_EVENTS_FOR_PATTERN = 3
  - HAND_REACH_PX = 108
"""
from __future__ import annotations

import csv
import json
import re
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

# H12 v8 thresholds (from h12_v8_h7v3pure_patterns.py)
K_EVENTS = 4
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0
RECENT_EVENT_FRAMES = 30
MIN_EVENTS_FOR_PATTERN = 3
HAND_REACH_PX = 108

# H50 threshold (H45/H48 finding)
MIN_FLIGHT_TIME = 10  # frames; H45: < 10 = identity switch


# ---------------------------------------------------------------------------
# Reused from H12 v8 (verbatim, since the pipeline is what we're testing)
# ---------------------------------------------------------------------------

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


def load_h7v3pure_admitted_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
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


def load_h10v9_quality(stem: str) -> dict[int, float]:
    out = {}
    with (H1_DATA / f"h10v9_chain_quality_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = float(r["quality_v9"])
    return out


def load_wrist_at_frame(stem: str) -> dict[int, dict]:
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


# ---------------------------------------------------------------------------
# H50 event log: build + filter
# ---------------------------------------------------------------------------

def build_catch_throw_timeline(stem: str) -> list[dict]:
    """Build the CATCH/THROW timeline from h7v3pure hand-edges only."""
    chains = load_h7v3pure_chains(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    tfs = load_tracklet_features(stem)
    h10v9_q = load_h10v9_quality(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    events = []
    for c in chains:
        cid = c["chain_id"]
        quality = h10v9_q.get(cid, 0.0)
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            if "HAND" not in e["edge_type"]:
                continue
            hand = None
            reason = e.get("reclassify_reason", "") or ""
            m = re.search(r"side=(\w+)", reason)
            if m:
                hand = m.group(1)
            if not hand:
                hand = parse_hand_from_metadata(e["metadata"]) or "unknown"
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
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
                "h3_confirmed": False,
                "ambiguous": (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
                "chain_quality": quality,
                "edge_type": e["edge_type"],
            })
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


def compute_flight_times(events: list[dict]) -> dict[int, int]:
    """For each event, compute the flight time from THIS throw to the
    NEXT CATCH in the same chain (with different tid)."""
    by_chain = defaultdict(list)
    for i, e in enumerate(events):
        by_chain[e["chain_id"]].append(i)
    flight_times = {}
    for cid, indices in by_chain.items():
        chain_events = sorted(indices, key=lambda i: events[i]["event_frame"])
        for j, idx in enumerate(chain_events):
            e = events[idx]
            if e["event"] != "THROW":
                continue
            for k in range(j + 1, len(chain_events)):
                next_e = events[chain_events[k]]
                if next_e["event"] == "CATCH" and next_e["tid"] != e["tid"]:
                    flight_times[idx] = next_e["event_frame"] - e["event_frame"]
                    break
    return flight_times


def filter_events_by_flight_time(events: list[dict],
                                  flight_times: dict[int, int],
                                  min_ft: int) -> tuple[list[dict], list[dict]]:
    """Drop (CATCH, THROW) pairs where the THROW's flight time < min_ft.

    Returns (filtered_events, dropped_events_with_reasons).
    """
    by_chain = defaultdict(list)
    for i, e in enumerate(events):
        by_chain[e["chain_id"]].append(i)

    keep_indices = set(range(len(events)))
    dropped = []

    for cid, indices in by_chain.items():
        chain_events = sorted(indices, key=lambda i: events[i]["event_frame"])
        for j, idx in enumerate(chain_events):
            e = events[idx]
            ft = flight_times.get(idx)
            if e["event"] == "THROW" and ft is not None and ft < min_ft:
                # Find the matching CATCH (previous event in same chain)
                catch_idx = None
                if j > 0 and events[chain_events[j - 1]]["event"] == "CATCH":
                    catch_idx = chain_events[j - 1]
                # Drop the THROW
                keep_indices.discard(idx)
                dropped.append({
                    "chain_id": cid,
                    "tid": e["tid"],
                    "event": "THROW",
                    "event_frame": e["event_frame"],
                    "hand": e["hand"],
                    "flight_time": ft,
                    "reason": f"flight_time<{min_ft}",
                })
                # Drop the matching CATCH too
                if catch_idx is not None:
                    keep_indices.discard(catch_idx)
                    dropped.append({
                        "chain_id": cid,
                        "tid": events[catch_idx]["tid"],
                        "event": "CATCH",
                        "event_frame": events[catch_idx]["event_frame"],
                        "hand": events[catch_idx]["hand"],
                        "flight_time": ft,
                        "reason": f"paired_with_dropped_throw_ft<{min_ft}",
                    })

    out = [e for i, e in enumerate(events) if i in keep_indices]
    out.sort(key=lambda e: e["event_frame"])
    return out, dropped


# ---------------------------------------------------------------------------
# Per-frame census (same as H12 v8)
# ---------------------------------------------------------------------------

def build_per_frame_census(stem: str) -> dict[int, dict]:
    chains = load_h7v3pure_chains(stem)
    tfs = load_tracklet_features(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    h10v9_q = load_h10v9_quality(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    in_air: dict[int, set[int]] = defaultdict(set)
    in_hand_l: dict[int, set[int]] = defaultdict(set)
    in_hand_r: dict[int, set[int]] = defaultdict(set)
    chain_at_frame: dict[int, set[int]] = defaultdict(set)
    chain_qualities: dict[int, float] = h10v9_q

    for c in chains:
        cid = c["chain_id"]
        for tid in c["tids"]:
            if tid not in tfs:
                continue
            t = tfs[tid]
            for f in range(t["first_frame"], t["last_frame"] + 1):
                in_air[f].add(cid)
                chain_at_frame[f].add(cid)

        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            hand = parse_hand_from_metadata(e["metadata"])
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            catch_frame = from_t["last_frame"]
            throw_frame = to_t["first_frame"]
            if hand == "left":
                for f in [catch_frame, throw_frame]:
                    in_hand_l[f].add(cid)
                    chain_at_frame[f].add(cid)
            elif hand == "right":
                for f in [catch_frame, throw_frame]:
                    in_hand_r[f].add(cid)
                    chain_at_frame[f].add(cid)
            else:
                for f in [catch_frame, throw_frame]:
                    chain_at_frame[f].add(cid)
            gap = to_t["first_frame"] - from_t["last_frame"]
            if 0 < gap <= 5 and hand in ("left", "right"):
                for f in range(catch_frame, throw_frame + 1):
                    if hand == "left":
                        in_hand_l[f].add(cid)
                    else:
                        in_hand_r[f].add(cid)
                    chain_at_frame[f].add(cid)

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


# ---------------------------------------------------------------------------
# Pattern classification (same as H12 v8)
# ---------------------------------------------------------------------------

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


def classify_pattern(census_row: dict, events_window: list[dict]) -> tuple:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pattern_inference(stem: str, events: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Run H12 v8's full per-frame pattern inference on the given events."""
    census = build_per_frame_census(stem)
    events_sorted = sorted(events, key=lambda e: e["event_frame"])
    events_by_frame = defaultdict(list)
    for e in events_sorted:
        events_by_frame[int(e["event_frame"])].append(e)

    results = []
    pattern_counts = defaultdict(int)
    n_total_buckets = defaultdict(int)
    for f, c in sorted(census.items()):
        events_before = [e for e in events_sorted
                         if int(e["event_frame"]) <= f]
        events_window = events_before[-K_EVENTS:]
        pattern, conf, same_run, alt, rate = classify_pattern(c, events_window)
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
            "same_hand_run": same_run,
            "unique_hands": metrics["unique_hands"],
            "alternation_score": round(alt, 3),
            "catch_rate_hz": round(rate, 2),
        })
        pattern_counts[pattern] += 1
        n_total_buckets[c["n_total_balls"]] += 1

    phases = detect_phase_boundaries(results)
    return results, phases, {
        "n_total_frames": len(results),
        "pattern_counts": dict(pattern_counts),
        "pattern_pcts": {p: round(100 * n / len(results), 1)
                          for p, n in pattern_counts.items()},
        "n_total_balls_dist": dict(n_total_buckets),
        "n_substantial_phases": sum(1 for p in phases if p["n_frames"] >= 20),
        "sub_phases": [p for p in phases if p["n_frames"] >= 20],
    }


def load_h12v8_baseline(stem: str) -> tuple[list[dict], list[dict], dict]:
    """Load H12 v8's per-frame pattern inference (h7v3plus3 variant)."""
    p = H1_DATA / f"pattern_inference_h35_{stem}.csv"
    if not p.exists():
        return [], [], {}
    rows = []
    with p.open() as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    pat_counts = defaultdict(int)
    for r in rows:
        pat_counts[r.get("pattern", "UNKNOWN")] += 1
    return rows, [], {
        "n_total_frames": len(rows),
        "pattern_counts": dict(pat_counts),
        "pattern_pcts": {p: round(100 * n / max(1, len(rows)), 1)
                          for p, n in pat_counts.items()},
    }


def main() -> None:
    summary = {
        "config": {
            "MIN_FLIGHT_TIME": MIN_FLIGHT_TIME,
            "K_EVENTS": K_EVENTS,
            "CASCADE_MAX_SAME_HAND_RUN": CASCADE_MAX_SAME_HAND_RUN,
            "CASCADE_MIN_CATCH_RATE": CASCADE_MIN_CATCH_RATE,
            "RECENT_EVENT_FRAMES": RECENT_EVENT_FRAMES,
            "MIN_EVENTS_FOR_PATTERN": MIN_EVENTS_FOR_PATTERN,
        },
        "videos": {},
    }
    for stem in STEMS:
        print(f"\n=== {stem} (H50: H12 v8 with 10-frame filter) ===")

        # Build unfiltered events (H12 v8 baseline)
        events_unf = build_catch_throw_timeline(stem)
        # Build filtered events
        flight_times = compute_flight_times(events_unf)
        fts = list(flight_times.values())
        n_short = sum(1 for ft in fts if ft < MIN_FLIGHT_TIME)
        events_filt, dropped = filter_events_by_flight_time(
            events_unf, flight_times, MIN_FLIGHT_TIME)
        print(f"  Unfiltered events: {len(events_unf)} "
              f"(CATCH={sum(1 for e in events_unf if e['event']=='CATCH')}, "
              f"THROW={sum(1 for e in events_unf if e['event']=='THROW')})")
        print(f"  Filtered events:   {len(events_filt)} "
              f"(CATCH={sum(1 for e in events_filt if e['event']=='CATCH')}, "
              f"THROW={sum(1 for e in events_filt if e['event']=='THROW')})")
        print(f"  Dropped events:    {len(dropped)}")
        if fts:
            print(f"  Flight times: {n_short}/{len(fts)} below {MIN_FLIGHT_TIME} frames; "
                  f"median={statistics.median(fts):.0f}, "
                  f"min={min(fts)}, max={max(fts)}")

        # Run pattern inference on UNFILTERED events (apples-to-apples baseline)
        results_u, phases_u, stats_u = run_pattern_inference(stem, events_unf)
        # Run pattern inference on FILTERED events (H50 main result)
        results_f, phases_f, stats_f = run_pattern_inference(stem, events_filt)

        print(f"  Pattern distribution (H12 v8 unfiltered / H50 filtered):")
        all_pats = set(stats_u["pattern_counts"]) | set(stats_f["pattern_counts"])
        for pat in sorted(all_pats, key=lambda p: -stats_f["pattern_counts"].get(p, 0)):
            u = stats_u["pattern_pcts"].get(pat, 0.0)
            f_pct = stats_f["pattern_pcts"].get(pat, 0.0)
            d = round(f_pct - u, 1)
            arrow = " <--" if abs(d) > 0.1 else ""
            print(f"    {pat}: {u:5.1f}% -> {f_pct:5.1f}%  ({d:+5.1f}%){arrow}")

        # Per-frame diff (filtered vs unfiltered, same pipeline)
        u_by_frame = {int(r["frame"]): r for r in results_u}
        f_by_frame = {int(r["frame"]): r for r in results_f}
        common = sorted(set(u_by_frame) & set(f_by_frame))
        diff_count = 0
        diff_examples = []
        for f in common:
            if u_by_frame[f]["pattern"] != f_by_frame[f]["pattern"]:
                diff_count += 1
                if len(diff_examples) < 10:
                    diff_examples.append({
                        "frame": f,
                        "unfiltered": u_by_frame[f]["pattern"],
                        "filtered": f_by_frame[f]["pattern"],
                        "unfiltered_conf": u_by_frame[f].get("confidence"),
                        "filtered_conf": f_by_frame[f].get("confidence"),
                    })
        pct_diff = round(100 * diff_count / max(1, len(common)), 1)
        print(f"  Per-frame pattern diff (H50 filtered vs H12 v8 unfiltered): "
              f"{diff_count}/{len(common)} ({pct_diff}%)")
        if diff_examples:
            print(f"  First 5 diff examples:")
            for ex in diff_examples[:5]:
                print(f"    f={ex['frame']}: {ex['unfiltered']} -> {ex['filtered']} "
                      f"(conf {ex['unfiltered_conf']} -> {ex['filtered_conf']})")

        # Substantial phases
        sub_phases_f = [p for p in phases_f if p["n_frames"] >= 20]
        sub_phases_u = [p for p in phases_u if p["n_frames"] >= 20]
        print(f"  Substantial phases (n_frames >= 20):")
        print(f"    H12 v8 unfiltered: {len(sub_phases_u)}")
        print(f"    H50 filtered:      {len(sub_phases_f)}")

        # Per-pattern delta
        delta = {}
        for pat in all_pats:
            f_pct = stats_f["pattern_pcts"].get(pat, 0.0)
            u_pct = stats_u["pattern_pcts"].get(pat, 0.0)
            delta[pat] = round(f_pct - u_pct, 1)
        significant_deltas = {p: d for p, d in delta.items() if abs(d) > 0.1}

        # Save outputs
        out_csv_u = H1_DATA / f"pattern_inference_h50_unfiltered_{stem}.csv"
        with out_csv_u.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results_u[0].keys()))
            w.writeheader()
            w.writerows(results_u)
        print(f"  Wrote: {out_csv_u.name}")
        out_csv_f = H1_DATA / f"pattern_inference_h50_{stem}.csv"
        with out_csv_f.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results_f[0].keys()))
            w.writeheader()
            w.writerows(results_f)
        print(f"  Wrote: {out_csv_f.name}")
        out_phases_f = H1_DATA / f"pattern_phases_h50_{stem}.csv"
        with out_phases_f.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(phases_f[0].keys()))
            w.writeheader()
            w.writerows(phases_f)
        print(f"  Wrote: {out_phases_f.name}")
        out_events_f = H1_DATA / f"catch_throw_timeline_h50_{stem}.csv"
        with out_events_f.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(events_filt[0].keys()))
            w.writeheader()
            w.writerows(events_filt)
        print(f"  Wrote: {out_events_f.name}")
        out_dropped = H1_DATA / f"h50_dropped_events_{stem}.csv"
        with out_dropped.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dropped[0].keys()) if dropped else [
                "chain_id", "tid", "event", "event_frame", "hand", "flight_time", "reason"])
            w.writeheader()
            w.writerows(dropped)
        print(f"  Wrote: {out_dropped.name}")

        summary["videos"][stem] = {
            "n_events_unfiltered": len(events_unf),
            "n_events_filtered": len(events_filt),
            "n_events_dropped": len(dropped),
            "n_flights_with_time": len(fts),
            "n_short_flights": n_short,
            "flight_time_min": min(fts) if fts else None,
            "flight_time_max": max(fts) if fts else None,
            "flight_time_median": statistics.median(fts) if fts else None,
            "h50_pattern_pcts": stats_f["pattern_pcts"],
            "h50_pattern_counts": stats_f["pattern_counts"],
            "h12v8_unfiltered_pattern_pcts": stats_u["pattern_pcts"],
            "h12v8_unfiltered_pattern_counts": stats_u["pattern_counts"],
            "pattern_delta_pct": delta,
            "significant_pattern_deltas": significant_deltas,
            "n_per_frame_diff": diff_count,
            "pct_per_frame_diff": pct_diff,
            "diff_examples": diff_examples,
            "h50_substantial_phases": sub_phases_f,
            "h12v8_unfiltered_substantial_phases": sub_phases_u,
        }

    out_summary = H1_DATA / "h50_filtered_patterns_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_summary}")


if __name__ == "__main__":
    main()
