#!/usr/bin/env python3
"""H34 — H10 v10 chain quality on H7v3plus3 chains (H22+H26 combined)."""
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

# Per-video weights (from H10 v6b)
WEIGHTS_PER_VIDEO = {
    "identical_balls_trick_000_018": {
        "h3": 0.30, "h8": 0.30, "h9": 0.40, "h8v8": 0.0
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        "h3": 0.25, "h8": 0.20, "h9": 0.30, "h8v8": 0.25
    },
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
            except (ValueError, KeyError):
                r["cost"] = None
            out.append(r)
    return out


def load_h3_confirmed(stem: str) -> set:
    path = H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv"
    confirmed = set()
    if not path.exists():
        return confirmed
    with path.open() as fh:
        rdr = csv.DictReader(fh)
        for r in rdr:
            if r["stem"] == stem and r.get("h3_confirmed", "False") == "True":
                confirmed.add((int(r["from_tid"]), int(r["to_tid"])))
    return confirmed


def load_h8_violations(stem: str):
    with (H1_DATA / "h8_v5_parabolic_summary.json").open() as fh:
        s = json.load(fh)
    violations = set()
    unknowns = set()
    for r in s["videos"][stem]["results"]:
        if r["edge_type"] != "BALLISTIC":
            continue
        if r["physics_status"] == "VIOLATING":
            violations.add((r["from_tid"], r["to_tid"]))
        elif r["physics_status"] == "INSUFFICIENT_DATA":
            unknowns.add((r["from_tid"], r["to_tid"]))
    return violations, unknowns


def load_h8v8_per_arc_g(stem: str) -> dict[int, list[float]]:
    out = defaultdict(list)
    path = H1_DATA / f"h8_v8_extrema_arcs_{stem}.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                src_g = float(r["src_g"])
                tgt_g = float(r["tgt_g"])
                if 0.0 < src_g < 2.0:
                    out[int(r["src_tid"])].append(src_g)
                if 0.0 < tgt_g < 2.0:
                    out[int(r["tgt_tid"])].append(tgt_g)
            except (KeyError, ValueError):
                pass
    return out


def compute_chain_quality(chain: dict, edges: list[dict],
                          h3_confirmed: set, h8_violations: set,
                          h8_unknowns: set, h8v8_arcs: dict[int, list[float]],
                          weights: dict) -> dict:
    """Compute H10 v10 quality for one chain."""
    cids = set(chain["tids"])
    chain_edges = [e for e in edges if e["from_tid"] in cids and e["to_tid"] in cids]
    n_total = len(chain_edges)

    n_hand = sum(1 for e in chain_edges if e["edge_type"] in (
        "HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
        "V_RECLASSIFIED_HAND_TRANSITION", "H26_RECLASSIFIED_HAND_TRANSITION",
        "H22_RECLASSIFIED_HAND_TRANSITION"))
    n_v_reclass = sum(1 for e in chain_edges if e["edge_type"] == "V_RECLASSIFIED_HAND_TRANSITION")
    n_h26 = sum(1 for e in chain_edges if e["edge_type"] == "H26_RECLASSIFIED_HAND_TRANSITION")
    n_air = sum(1 for e in chain_edges if e["edge_type"] == "BALLISTIC")
    n_h3 = sum(1 for e in chain_edges if (e["from_tid"], e["to_tid"]) in h3_confirmed)

    # H3 score: fraction of hand-edges with H3 confirmation
    # If n_hand == 0, h3 is None (no edges to confirm)
    h3 = (n_h3 / n_hand) if n_hand > 0 else None

    # H8 score: fraction of BALLISTIC edges without physics violation
    # If n_air == 0, h8 = 1.0 (no air edges = no violations)
    air_violating = sum(1 for e in chain_edges
                        if e["edge_type"] == "BALLISTIC"
                        and (e["from_tid"], e["to_tid"]) in h8_violations)
    air_unknown = sum(1 for e in chain_edges
                      if e["edge_type"] == "BALLISTIC"
                      and (e["from_tid"], e["to_tid"]) in h8_unknowns)
    h8 = 1.0 - (air_violating / n_air) if n_air > 0 else 1.0

    # H9 score: a chain has 1.0 if it has at least one tid
    h9 = 1.0 if chain["n_tracklets"] > 0 else 0.0

    # H8v8 score: per-arc gravity consistency
    chain_arcs = []
    for tid in chain["tids"]:
        chain_arcs.extend(h8v8_arcs.get(tid, []))
    if chain_arcs:
        clean = sum(1 for g in chain_arcs if 0.2 <= g <= 0.8)
        h8v8 = clean / len(chain_arcs)
    else:
        h8v8 = 0.5  # no arcs = neutral

    # Composite quality v10 (per-video weights)
    # The H10 v6b formula excludes h3 if n_hand == 0 (h3=None)
    # and uses h8v8 with weight 0 for identical (per H10 v6b)
    w = weights
    q_components = []
    if h3 is not None and w["h3"] > 0:
        q_components.append(w["h3"] * h3)
    if w["h8"] > 0:
        q_components.append(w["h8"] * h8)
    if w["h9"] > 0:
        q_components.append(w["h9"] * h9)
    if w["h8v8"] > 0:
        q_components.append(w["h8v8"] * h8v8)
    total_w = sum(w.values())
    q = sum(q_components) / total_w if total_w > 0 else 0.0

    return {
        "chain_id": chain["chain_id"],
        "n_tracklets": chain["n_tracklets"],
        "n_hand_edges": n_hand,
        "n_v_reclass_edges": n_v_reclass,
        "n_h26_edges": n_h26,
        "n_air_edges": n_air,
        "n_h3_confirmed": n_h3,
        "n_air_in_chain": n_air,
        "n_air_violating": air_violating,
        "n_air_unknown": air_unknown,
        "h3_score": round(h3, 4) if h3 is not None else "",
        "h8_score": round(h8, 4),
        "h9_score": round(h9, 4),
        "h8v8_score": round(h8v8, 4),
        "quality_v10": round(q, 4),
    }


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        chains = load_chains(stem)
        edges = load_edges(stem)
        h3_confirmed = load_h3_confirmed(stem)
        h8_violations, h8_unknowns = load_h8_violations(stem)
        h8v8_arcs = load_h8v8_per_arc_g(stem)
        weights = WEIGHTS_PER_VIDEO[stem]

        results = []
        for c in chains:
            r = compute_chain_quality(c, edges, h3_confirmed, h8_violations,
                                      h8_unknowns, h8v8_arcs, weights)
            results.append(r)

        results.sort(key=lambda r: -r["quality_v10"])

        mean_q = sum(r["quality_v10"] for r in results) / len(results)
        print(f"  {stem}: n_chains={len(chains)} mean_v10={mean_q:.4f}")

        # Save per-chain CSV
        out_csv = H1_DATA / f"h10v10_h7v3plus3_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            cols = list(results[0].keys())
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(results)
        print(f"  wrote {out_csv.name}")

        summary["videos"][stem] = {
            "n_chains": len(chains),
            "mean_quality_v10": round(mean_q, 4),
        }

    out_json = H1_DATA / "h34_h10v10_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}")
    print("\n=== H34 H10 v10 CHAIN QUALITY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
