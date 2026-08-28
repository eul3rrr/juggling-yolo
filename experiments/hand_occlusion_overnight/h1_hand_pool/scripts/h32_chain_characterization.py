#!/usr/bin/env python3
"""H32 — per-chain characterization on h7v3plus2 chains.

HYPOTHESIS:
  H12's per-frame CASCADE/FOUNTAIN inference has fundamental
  reliability issues (H20 visual QA, vision tool inconsistencies).
  But the h7v3plus2 chain set (H7v2 + H15v2 + H21 + H26 = 42 identical,
  15 YouTube) is the best-validated chain representation we have.

  H32 hypothesis: at the CHAIN level (not the frame level), hand
  alternation is a robust discriminator between CASCADE (alternates
  hands) and FOUNTAIN (single-hand) juggling patterns. The h7v3plus2
  chains each have an edge_type metadata that encodes which hand was
  used for each catch/throw, so we can build a per-chain hand
  sequence.

  A chain-level CASCADE/FOUNTAIN classification based on hand
  alternation:
    - Has the advantage of using the validated chain set (immune to
      the H17→H20→H31 negative finding chain)
    - Operates at chain granularity (not per-frame), so it's robust
      to per-frame pattern noise
    - Uses the catch/throw event log (H11 v7 family), not the
      unreliable per-frame vx-signal (H12 v4/v5)

APPROACH (declared from physical geometry, not tuned to labels):
  - Per-chain metrics:
    1. n_hand_events: count of HAND_TRANSITION +
       RECLASSIFIED_HAND_TRANSITION + V_RECLASSIFIED_HAND_TRANSITION
       + H26_RECLASSIFIED_HAND_TRANSITION + AMBIGUOUS_HAND_TRANSITION
       edges in the chain
    2. n_ballistic: count of BALLISTIC edges
    3. n_pure_hand: 1 if n_ballistic == 0 else 0
    4. hand_sequence: chronological list of hand strings parsed
       from edge metadata (for HAND_TRANSITION: from
       "tok_age=X,hand=Y"; for RECLASSIFIED_HAND_TRANSITION: from
       reclassify_reason "src_catch_dist=..._side=left/right" or
       "tgt_throw_dist=..._side=left/right"; for
       V_RECLASSIFIED_HAND_TRANSITION: from v_reclassify_reason
       "v_shape_v_X_hand=Y"; for H26_RECLASSIFIED: from which_hand
       field, but it's not in the CSV; we can parse it from
       h26_reason "R->L hand-off" or "L->R hand-off" or from the
       chain_summary h26_added field)
    5. hand_alternation_rate: fraction of consecutive hand-event
       pairs that alternate L<->R
    6. unique_hands: 1, 2, or 0
    7. dominant_hand: 'left', 'right', or 'mixed'
    8. n_catches: same as n_hand_events (each hand-edge = 1 catch)
    9. catch_rate_hz: n_catches / chain_duration_seconds
   10. catch_per_frame: n_catches / (last_frame - first_frame + 1)
   11. pattern_verdict:
         - CASCADE_LIKE: alternation_rate >= 0.5 AND unique_hands == 2
         - FOUNTAIN_LIKE: unique_hands == 1 AND n_catches >= 2
         - MIXED: not CASCADE_LIKE and not FOUNTAIN_LIKE, n_catches >= 3
         - SINGLE_CATCH: n_catches == 1
         - NO_CATCH: n_catches == 0
   12. physical_ball_count_estimate:
         - 1 if chain has exactly 1 tid (singleton)
         - 1 if chain is a 2-tid chain with 1 hand-edge (likely the
           same physical ball caught+thrown)
         - n_catches if CASCADE_LIKE (one ball per catch cycle)
         - min(3, n_catches) otherwise (conservative)

OUTPUTS:
  - data/h32_chain_metrics_identical_balls_trick_000_018.csv
  - data/h32_chain_metrics_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv
  - data/h32_summary.json
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

HAND_EDGE_TYPES = {
    "HAND_TRANSITION",
    "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION",
    "V_RECLASSIFIED_HAND_TRANSITION",
    "H26_RECLASSIFIED_HAND_TRANSITION",
}

# --- parsers ---


def _parse_reclassify_hand(reason: str) -> str | None:
    """Parse RECLASSIFIED_HAND_TRANSITION side from reclassify_reason.

    Format: 'src_catch_dist=X_slope=Y_side=left/right' or
    'tgt_throw_dist=X_slope=Y_side=left/right'
    """
    m = re.search(r"side=(left|right)", reason)
    return m.group(1) if m else None


def _parse_v_hand(v_reason: str) -> str | None:
    """Parse V_RECLASSIFIED_HAND_TRANSITION hand from v_reclassify_reason.

    Format: 'v_shape_v_deep_hand=left' or 'v_shape_v_shallow_hand=right'
    """
    m = re.search(r"hand=(left|right)", v_reason)
    return m.group(1) if m else None


def _parse_h26_hands(h26_reason: str) -> tuple[str, str] | None:
    """Parse H26_RECLASSIFIED_HAND_TRANSITION (catch, throw) hands from h26_reason.

    Format: 'H24 visually-confirmed REAL H20-KEPT-not-in-h7v2 (R->L hand-off)'
    or '(L->R hand-off, V_DEEP)'

    Returns (catch_hand, throw_hand) or None.
    Catch hand = where the ball arrived (source of the edge in H26);
    throw hand = where the ball left (target of the edge in H26).
    """
    m = re.search(r"\(([LR])->([LR]) hand-off", h26_reason)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def _parse_hand_transition_hand(metadata: str) -> str | None:
    """Parse HAND_TRANSITION hand from metadata.

    Format: 'tok_age=X,hand=left/right'
    """
    m = re.search(r"hand=(left|right)", metadata)
    return m.group(1) if m else None


def edge_hand(edge: dict) -> str | None:
    """Return the primary hand of an edge (the catch hand, or the throw hand
    for reclass edges, or None for BALLISTIC)."""
    et = edge["edge_type"]
    if et == "HAND_TRANSITION" or et == "AMBIGUOUS_HAND_TRANSITION":
        return _parse_hand_transition_hand(edge.get("metadata", ""))
    if et == "RECLASSIFIED_HAND_TRANSITION":
        return _parse_reclassify_hand(edge.get("reclassify_reason", ""))
    if et == "V_RECLASSIFIED_HAND_TRANSITION":
        return _parse_v_hand(edge.get("v_reclassify_reason", ""))
    if et == "H26_RECLASSIFIED_HAND_TRANSITION":
        h = _parse_h26_hands(edge.get("h26_reason", ""))
        return h[0] if h else None
    return None


def edge_hands(edge: dict) -> tuple[str, str] | None:
    """Return the (catch_hand, throw_hand) tuple for a hand-edge, or None."""
    et = edge["edge_type"]
    if et == "HAND_TRANSITION" or et == "AMBIGUOUS_HAND_TRANSITION":
        h = _parse_hand_transition_hand(edge.get("metadata", ""))
        return (h, h) if h else None
    if et == "RECLASSIFIED_HAND_TRANSITION":
        h = _parse_reclassify_hand(edge.get("reclassify_reason", ""))
        return (h, h) if h else None
    if et == "V_RECLASSIFIED_HAND_TRANSITION":
        h = _parse_v_hand(edge.get("v_reclassify_reason", ""))
        return (h, h) if h else None
    if et == "H26_RECLASSIFIED_HAND_TRANSITION":
        return _parse_h26_hands(edge.get("h26_reason", ""))
    return None


def edge_frame(edge: dict) -> int | None:
    """Best-effort frame for a hand-edge. We don't have direct frame in the
    admitted edges CSV; use the source tid's last_frame as an approximation
    (the catch or throw happens at or near the source's last frame)."""
    return None  # set later from tracklet features


# --- loaders ---


def load_h7v3plus2_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus2_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h7v3plus2_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            try:
                r["cost"] = float(r["cost"])
            except (ValueError, KeyError):
                r["cost"] = None
            out.append(r)
    return out


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["tid"] = int(r["tid"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["n_pts"] = int(r["n_pts"])
            out[r["tid"]] = r
    return out


def load_h10v10(stem: str) -> dict[int, dict]:
    """Return chain_id -> {quality, classification, ...}."""
    out = {}
    path = H1_DATA / f"h10v10_chain_quality_{stem}.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            cid = int(r["chain_id"])
            try:
                q = float(r["quality_v10"])
            except (ValueError, KeyError):
                q = None
            out[cid] = {
                "quality": q,
                "n_hand_edges": int(r.get("n_hand_edges", 0)),
                "n_air_edges": int(r.get("n_air_edges", 0)),
                "n_h3_confirmed": int(r.get("n_h3_confirmed", 0)),
            }
    return out


# --- per-chain metrics ---


def per_chain_metrics(chain: dict, edges: list[dict], tid_meta: dict,
                      h10v10: dict[int, dict]) -> dict:
    """Compute per-chain hand-alternation + ball-count metrics."""
    cids = set(chain["tids"])
    chain_edges = [e for e in edges if e["from_tid"] in cids and e["to_tid"] in cids]
    chain_edges.sort(key=lambda e: (
        tid_meta[e["from_tid"]]["last_frame"],
        tid_meta[e["to_tid"]]["first_frame"],
    ))

    # For each hand-edge, produce a list of (frame, hand, kind) entries.
    # A HAND_TRANSITION / V_RECLASSIFIED / RECLASSIFIED contributes 1
    # entry (the hand involved). An H26 hand-off contributes 2 entries
    # (catch hand + throw hand) since it explicitly transits between
    # hands.
    hand_events: list[tuple[int, str, str, str]] = []  # (frame, hand, kind, edge_id)
    for e in chain_edges:
        if e["edge_type"] not in HAND_EDGE_TYPES:
            continue
        src_meta = tid_meta.get(e["from_tid"])
        frame = src_meta["last_frame"] if src_meta else -1
        hands = edge_hands(e)
        if hands is None:
            continue
        c_hand, t_hand = hands
        edge_id = f"{e['from_tid']}->{e['to_tid']}"
        if c_hand == t_hand:
            hand_events.append((frame, c_hand, e["edge_type"], edge_id))
        else:
            # Hand-off: record BOTH hands
            hand_events.append((frame, c_hand, e["edge_type"] + "/CATCH", edge_id))
            hand_events.append((frame, t_hand, e["edge_type"] + "/THROW", edge_id))

    hand_events.sort()
    hands = [h for _, h, _, _ in hand_events]

    n_catches = len(hand_events)
    chain_dur_frames = max(1, chain["last_frame"] - chain["first_frame"] + 1)
    chain_dur_seconds = chain_dur_frames / 30.0
    catch_rate_hz = n_catches / chain_dur_seconds if chain_dur_seconds > 0 else 0.0
    catch_per_frame = n_catches / chain_dur_frames

    unique_hands = len(set(hands)) if hands else 0

    # Hand alternation rate: fraction of consecutive hand-event pairs
    # that alternate L<->R. For SINGLE_CATCH chains, alt_rate is 0.
    if len(hands) >= 2:
        n_alt = sum(1 for a, b in zip(hands, hands[1:]) if a != b)
        alt_rate = n_alt / (len(hands) - 1)
    else:
        alt_rate = 0.0

    # Dominant hand
    if hands:
        cnt = Counter(hands)
        dom, dom_count = cnt.most_common(1)[0]
        dom_frac = dom_count / len(hands)
        dominant_hand = dom if dom_frac >= 0.7 else "mixed"
    else:
        dominant_hand = "none"

    # Edge type counts
    et_counts = Counter(e["edge_type"] for e in chain_edges)
    n_ballistic = et_counts.get("BALLISTIC", 0)
    n_pure_hand = 1 if n_ballistic == 0 and n_catches > 0 else 0

    # Pattern verdict
    if n_catches == 0:
        pattern = "NO_CATCH"
    elif n_catches == 1:
        pattern = "SINGLE_CATCH"
    elif unique_hands == 1:
        pattern = "FOUNTAIN_LIKE"
    elif alt_rate >= 0.5 and unique_hands == 2:
        pattern = "CASCADE_LIKE"
    elif alt_rate < 0.5 and unique_hands == 2:
        pattern = "MIXED"
    else:
        pattern = "UNKNOWN"

    # Physical ball count estimate
    if chain["n_tracklets"] == 1:
        ball_estimate = 1
    elif chain["n_tracklets"] == 2 and n_catches == 1:
        ball_estimate = 1
    elif pattern == "CASCADE_LIKE":
        # A 3-ball cascade: each hand catches once per cycle, so
        # n_catches / 2 cycles is a rough cycle count.
        # Conservative: 3 balls if n_catches >= 4 (more than 1 cycle)
        ball_estimate = 3 if n_catches >= 4 else 2
    elif pattern == "FOUNTAIN_LIKE":
        # A 2-ball fountain: 1 hand catches twice per cycle
        ball_estimate = 2 if n_catches >= 3 else 1
    else:
        # Conservative: assume 1 ball unless chain is long
        ball_estimate = 1 if chain["n_tracklets"] <= 2 else 2

    h10 = h10v10.get(chain["chain_id"], {})

    return {
        "chain_id": chain["chain_id"],
        "n_tracklets": chain["n_tracklets"],
        "first_frame": chain["first_frame"],
        "last_frame": chain["last_frame"],
        "duration_frames": chain_dur_frames,
        "duration_seconds": round(chain_dur_seconds, 2),
        "n_hand_events": n_catches,
        "n_ballistic": n_ballistic,
        "n_pure_hand": n_pure_hand,
        "hand_sequence": "->".join(hands) if hands else "",
        "n_hand_edges_total": sum(et_counts.get(t, 0) for t in HAND_EDGE_TYPES),
        "unique_hands": unique_hands,
        "dominant_hand": dominant_hand,
        "alternation_rate": round(alt_rate, 3),
        "catch_rate_hz": round(catch_rate_hz, 3),
        "catch_per_frame": round(catch_per_frame, 4),
        "pattern_verdict": pattern,
        "physical_ball_estimate": ball_estimate,
        "h10v10_quality": h10.get("quality"),
        "tids": ",".join(str(t) for t in chain["tids"]),
    }


# --- main ---


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        chains = load_h7v3plus2_chains(stem)
        edges = load_h7v3plus2_edges(stem)
        tid_meta = load_tracklet_features(stem)
        h10v10 = load_h10v10(stem)
        print(f"[{stem}] chains={len(chains)} edges={len(edges)} "
              f"tids={len(tid_meta)}")

        per_chain = []
        for c in chains:
            m = per_chain_metrics(c, edges, tid_meta, h10v10)
            per_chain.append(m)

        # Aggregate stats
        n_multi = sum(1 for m in per_chain if m["n_tracklets"] > 1)
        n_with_catches = sum(1 for m in per_chain if m["n_hand_events"] > 0)
        pattern_counts = Counter(m["pattern_verdict"] for m in per_chain)
        ball_estimate_total = sum(m["physical_ball_estimate"]
                                  for m in per_chain)
        h10q = [m["h10v10_quality"] for m in per_chain
                if m["h10v10_quality"] is not None]
        h10q_mean = sum(h10q) / len(h10q) if h10q else None

        # Long-chain (multi-tid) summary
        multi = [m for m in per_chain if m["n_tracklets"] > 1]
        multi_pattern_counts = Counter(m["pattern_verdict"] for m in multi)
        multi_mean_alt = (sum(m["alternation_rate"] for m in multi) / len(multi)
                          if multi else 0.0)
        multi_mean_catch_rate = (sum(m["catch_rate_hz"] for m in multi) / len(multi)
                                 if multi else 0.0)

        # Save per-chain CSV
        out_csv = H1_DATA / f"h32_chain_metrics_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            cols = list(per_chain[0].keys())
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(per_chain)
        print(f"  wrote {out_csv.name}")

        summary["videos"][stem] = {
            "n_chains": len(per_chain),
            "n_multi_tracklet_chains": n_multi,
            "n_chains_with_catches": n_with_catches,
            "pattern_counts": dict(pattern_counts),
            "multi_tracklet_pattern_counts": dict(multi_pattern_counts),
            "multi_mean_alternation_rate": round(multi_mean_alt, 3),
            "multi_mean_catch_rate_hz": round(multi_mean_catch_rate, 3),
            "ball_estimate_total": ball_estimate_total,
            "h10v10_mean_quality": round(h10q_mean, 4) if h10q_mean else None,
        }

    out_json = H1_DATA / "h32_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}")
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
