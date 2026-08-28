#!/usr/bin/env python3
"""H36 - per-frame hand-occupancy state machine on h7v3plus3 chains.

HYPOTHESIS:
  The h7v3plus3 chain set is a validated list of "real hand events".
  Each chain has HAND_TRANSITION edges (catch/throw), AMBIGUOUS_HAND
  edges, RECLASSIFIED/V_RECLASSIFIED edges, and BALLISTIC edges
  (no hand event). We can walk the chains chronologically and
  maintain a (L, R, A) state where L = balls in left hand,
  R = balls in right hand, A = balls in air, L+R+A = total_n_balls.

  This produces a per-frame timeline that:
  - Validates the chain set for physical consistency
    (no over-capacity, no negative ball counts)
  - Provides a clean consumer-facing artifact: a single CSV
    answering "at frame f, how many balls are in left/right/air?"
  - Detects identity switches (ball 0 in left at f=100, ball 0
    in right at f=200) that suggest multi-ball merges

EXPECTED:
  - identical: 3-ball cascade pattern, mostly 1 ball per hand + 1 in air
  - YouTube: 5-ball pattern, 2 per hand + 1 in air (cascade) or
    1 per hand + 3 in air (fountain) or other variations
  - Some frames have "impossible states" (over-capacity, negative)
    that should be reported as diagnostic signals

ALGORITHM:
  - Sort all hand-events (catch/throw) by event_frame
  - For each event, update (L, R, A) based on edge type and hand
  - Emit per-frame state timeline
  - Detect capacity violations and identity conflicts
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

# H36 assumption: total_n_balls per video
TOTAL_BALLS = {
    "identical_balls_trick_000_018": 3,  # 3-ball cascade
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 5,  # 5-ball pattern
}

# H36 capacity: each hand can hold 0-3 balls (3-ball hands)
HAND_CAPACITY = 3

# Hand-edge types
HAND_EDGE_TYPES = {
    "HAND_TRANSITION",
    "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION",
    "V_RECLASSIFIED_HAND_TRANSITION",
    "H26_RECLASSIFIED_HAND_TRANSITION",
    "H22_RECLASSIFIED_HAND_TRANSITION",
}

STEMS = list(TOTAL_BALLS.keys())


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
            }
    return out


def parse_hand_from_edge(edge: dict) -> str:
    """Extract hand from edge metadata. Returns 'left', 'right', or 'unknown'."""
    md = edge.get("metadata", "") or ""
    m = re.search(r"hand=(\w+)", md)
    if m:
        return m.group(1)
    for rsn_field in ("reclassify_reason", "v_reclassify_reason",
                       "h22_reason", "h26_reason"):
        rsn = edge.get(rsn_field, "") or ""
        m = re.search(r"hand=(\w+)", rsn)
        if m:
            return m.group(1)
        m = re.search(r"side=(\w+)", rsn)
        if m:
            return m.group(1)
        m = re.search(r"which_hand=(\w+)", rsn)
        if m:
            return m.group(1)
    return "unknown"


def collect_hand_events(chains: list[dict], edges: list[dict],
                          tracklets: dict) -> list[dict]:
    """Walk chains, emit per-hand-edge catch/throw events chronologically."""
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
    events = []
    for chain in chains:
        cid = chain["chain_id"]
        tids = chain["tids"]
        for i in range(len(tids) - 1):
            prev_tid = tids[i]
            tid = tids[i + 1]
            edge = by_pair.get((prev_tid, tid))
            if not edge or edge["edge_type"] not in HAND_EDGE_TYPES:
                continue
            hand = parse_hand_from_edge(edge)
            from_t = tracklets.get(prev_tid, {})
            to_t = tracklets.get(tid, {})
            catch_frame = from_t.get("last_frame")
            throw_frame = to_t.get("first_frame")
            if catch_frame is None or throw_frame is None:
                continue
            events.append({
                "chain_id": cid,
                "edge_type": edge["edge_type"],
                "hand": hand,
                "tid": tid,
                "prev_tid": prev_tid,
                "catch_frame": catch_frame,
                "throw_frame": throw_frame,
                "ambiguous": (edge["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
            })
    events.sort(key=lambda e: e["catch_frame"])
    return events


def simulate_state_machine(events: list[dict], total_balls: int) -> list[dict]:
    """Walk events chronologically, maintain (L, R, A) state.

    For each event:
    - CATCH: at catch_frame, decrement A, increment hand.
      At throw_frame, decrement hand, increment A.
    - AMBIGUOUS: track separately, don't update state.
    """
    state = {"L": 0, "R": 0, "A": total_balls}
    timeline = []
    violations = []

    def emit(f, ev_type, hand, note=""):
        nonlocal state
        cap = state["L"] + state["R"] + state["A"]
        timeline.append({
            "frame": f,
            "L": state["L"],
            "R": state["R"],
            "A": state["A"],
            "event_type": ev_type,
            "hand": hand,
            "conservation": cap,
            "conservation_ok": (cap == total_balls),
            "note": note,
        })

    # Initial state
    timeline.append({
        "frame": -1,
        "L": 0, "R": 0, "A": total_balls,
        "event_type": "INIT",
        "hand": "",
        "conservation": total_balls,
        "conservation_ok": True,
        "note": f"total_balls={total_balls}",
    })

    for ev in events:
        hand = ev["hand"]
        if hand not in ("left", "right"):
            # AMBIGUOUS or unknown hand: don't update state, just record
            timeline.append({
                "frame": ev["catch_frame"],
                "L": state["L"], "R": state["R"], "A": state["A"],
                "event_type": f"AMBIG_{ev['edge_type']}",
                "hand": hand,
                "conservation": state["L"] + state["R"] + state["A"],
                "conservation_ok": (state["L"] + state["R"] + state["A"] == total_balls),
                "note": f"chain={ev['chain_id']} {ev['prev_tid']}->{ev['tid']}",
            })
            continue

        # CATCH: ball at hand, decrement A, increment hand
        catch_frame = ev["catch_frame"]
        hand_key = "L" if hand == "left" else "R"
        if state["A"] <= 0:
            violations.append({"frame": catch_frame, "type": "CATCH_NO_AIR",
                                "hand": hand, "state_before": dict(state)})
        if state[hand_key] >= HAND_CAPACITY:
            violations.append({"frame": catch_frame, "type": "CATCH_OVER_CAP",
                                "hand": hand, "state_before": dict(state)})

        state["A"] = max(0, state["A"] - 1)
        state[hand_key] = min(HAND_CAPACITY, state[hand_key] + 1)
        emit(catch_frame, "CATCH", hand,
             note=f"chain={ev['chain_id']} {ev['prev_tid']}->{ev['tid']}")

        # THROW: ball leaves hand, decrement hand, increment A
        throw_frame = ev["throw_frame"]
        if state[hand_key] <= 0:
            violations.append({"frame": throw_frame, "type": "THROW_EMPTY_HAND",
                                "hand": hand, "state_before": dict(state)})
        if state["A"] >= total_balls:
            violations.append({"frame": throw_frame, "type": "THROW_NO_AIR_SLOT",
                                "hand": hand, "state_before": dict(state)})

        state[hand_key] = max(0, state[hand_key] - 1)
        state["A"] = min(total_balls, state["A"] + 1)
        emit(throw_frame, "THROW", hand,
             note=f"chain={ev['chain_id']} {ev['prev_tid']}->{ev['tid']}")

    return timeline, violations


def detect_identity_conflicts(timeline: list[dict]) -> list[dict]:
    """Look for runs of unusual state patterns.

    A real juggling pattern has bounded state (e.g., 1+1+1 for
    3-ball cascade). Multi-ball merges may produce weird states
    (e.g., 3+0+0, 0+3+0) that look like "all balls in one hand"
    which is physically impossible during juggling.
    """
    conflicts = []
    for t in timeline:
        if t["event_type"] == "INIT":
            continue
        if t["L"] + t["R"] + t["A"] != t.get("L", 0) + t.get("R", 0) + t.get("A", 0):
            continue
        # Check for impossible state: 3+ balls in one hand during active juggling
        if t["L"] >= 3 or t["R"] >= 3:
            conflicts.append({
                "frame": t["frame"],
                "type": "OVER_CAPACITY_HAND",
                "L": t["L"], "R": t["R"], "A": t["A"],
                "event": t["event_type"],
            })
        # Check for conservation violation
        if not t["conservation_ok"]:
            conflicts.append({
                "frame": t["frame"],
                "type": "CONSERVATION_VIOLATION",
                "L": t["L"], "R": t["R"], "A": t["A"],
                "conservation": t["conservation"],
                "event": t["event_type"],
            })
    return conflicts


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H36: per-frame hand-occupancy state machine) ===")
        total = TOTAL_BALLS[stem]
        print(f"  total_balls = {total}")

        chains = load_chains(stem)
        edges = load_edges(stem)
        tracklets = load_tracklets(stem)

        events = collect_hand_events(chains, edges, tracklets)
        print(f"  hand-events: {len(events)}")
        n_amb = sum(1 for e in events if e["ambiguous"])
        n_known = sum(1 for e in events if e["hand"] in ("left", "right"))
        n_unknown = len(events) - n_amb - n_known
        print(f"    ambiguous: {n_amb}, known-hand: {n_known}, "
              f"unknown-hand: {n_unknown}")

        timeline, violations = simulate_state_machine(events, total)
        print(f"  timeline: {len(timeline)} entries")
        print(f"  violations: {len(violations)}")
        v_types = defaultdict(int)
        for v in violations:
            v_types[v["type"]] += 1
        for vt, vn in sorted(v_types.items(), key=lambda x: -x[1]):
            print(f"    {vt}: {vn}")

        conflicts = detect_identity_conflicts(timeline)
        print(f"  identity conflicts (over-capacity / conservation): {len(conflicts)}")

        # Per-state distribution
        state_counts = defaultdict(int)
        for t in timeline:
            if t["event_type"] == "INIT":
                continue
            state_counts[(t["L"], t["R"], t["A"])] += 1
        print(f"  per-state distribution (L, R, A):")
        for (L, R, A), c in sorted(state_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    L={L} R={R} A={A}: {c}")

        # Interpolate to per-frame timeline (HOLD state between events)
        last_state = None
        last_frame = -1
        per_frame = []
        for t in timeline:
            f = t["frame"]
            if f < 0:
                last_state = t
                continue
            # Fill frames between last_frame+1 and f-1 with last_state
            if last_state is not None and f > last_frame + 1:
                for fill_f in range(last_frame + 1, f):
                    per_frame.append({
                        "frame": fill_f,
                        "L": last_state["L"],
                        "R": last_state["R"],
                        "A": last_state["A"],
                        "event_type": "HOLD",
                        "hand": "",
                        "conservation": last_state["L"] + last_state["R"] + last_state["A"],
                        "conservation_ok": (last_state["L"] + last_state["R"]
                                            + last_state["A"] == total),
                        "note": "interpolated",
                    })
            # Now add the actual event frame
            per_frame.append({
                "frame": f,
                "L": t["L"],
                "R": t["R"],
                "A": t["A"],
                "event_type": t["event_type"],
                "hand": t["hand"],
                "conservation": t["L"] + t["R"] + t["A"],
                "conservation_ok": (t["L"] + t["R"] + t["A"] == total),
                "note": t["note"],
            })
            last_state = t
            last_frame = f

        # Per-state distribution on interpolated per-frame timeline
        per_frame_state_counts = defaultdict(int)
        for t in per_frame:
            if t["event_type"] == "INIT":
                continue
            per_frame_state_counts[(t["L"], t["R"], t["A"])] += 1
        n_interp = sum(per_frame_state_counts.values())
        print(f"  interpolated per-frame states: {n_interp}")
        print(f"  per-state distribution (L, R, A) [interpolated]:")
        for (L, R, A), c in sorted(per_frame_state_counts.items(),
                                     key=lambda x: -x[1])[:10]:
            print(f"    L={L} R={R} A={A}: {c} ({100*c/n_interp:.1f}%)")

        # Write outputs
        out_tl = H1_DATA / f"h36_timeline_{stem}.csv"
        with out_tl.open("w", newline="") as fh:
            if timeline:
                w = csv.DictWriter(fh, fieldnames=list(timeline[0].keys()))
                w.writeheader()
                w.writerows(timeline)
        print(f"  wrote: {out_tl.name} ({len(timeline)} entries)")

        out_pf = H1_DATA / f"h36_per_frame_{stem}.csv"
        with out_pf.open("w", newline="") as fh:
            if per_frame:
                w = csv.DictWriter(fh, fieldnames=list(per_frame[0].keys()))
                w.writeheader()
                w.writerows(per_frame)
        print(f"  wrote: {out_pf.name} ({len(per_frame)} frames)")

        out_v = H1_DATA / f"h36_violations_{stem}.csv"
        with out_v.open("w", newline="") as fh:
            if violations:
                w = csv.DictWriter(fh, fieldnames=list(violations[0].keys()))
                w.writeheader()
                w.writerows(violations)
        print(f"  wrote: {out_v.name} ({len(violations)} violations)")

        out_c = H1_DATA / f"h36_conflicts_{stem}.csv"
        with out_c.open("w", newline="") as fh:
            if conflicts:
                w = csv.DictWriter(fh, fieldnames=list(conflicts[0].keys()))
                w.writeheader()
                w.writerows(conflicts)
        print(f"  wrote: {out_c.name} ({len(conflicts)} conflicts)")

        summary["videos"][stem] = {
            "total_balls": total,
            "n_events": len(events),
            "n_ambiguous": n_amb,
            "n_known_hand": n_known,
            "n_unknown_hand": n_unknown,
            "n_timeline_entries": len(timeline),
            "n_per_frame_entries": n_interp,
            "n_violations": len(violations),
            "violation_types": dict(v_types),
            "n_conflicts": len(conflicts),
            "state_distribution": {
                f"L{L} R{R} A{A}": c
                for (L, R, A), c in state_counts.items()
            },
            "per_frame_state_distribution": {
                f"L{L} R{R} A{A}": c
                for (L, R, A), c in per_frame_state_counts.items()
            },
        }

    out = H1_DATA / "h36_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
