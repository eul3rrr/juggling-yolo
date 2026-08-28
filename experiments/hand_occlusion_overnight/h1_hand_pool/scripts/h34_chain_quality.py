#!/usr/bin/env python3
"""H34 — H10 v10 chain quality on H7v3plus3 chains (H22+H26 combined).

Faithful port of h10v10_with_h26.py to h7v3plus3 chains. Includes:
- h3-redistribution rule when h3 is None
- h9 = coverage (observed_frames / span_frames)
- h8v8 = mean per-tid arc_score using h8_v8_extrema_arcs
- n_h3_eligible excludes V_RECLASSIFIED and H22_RECLASSIFIED
  (matches h10v10_with_h26.py)
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
            r["tid"] = int(r["tid"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["n_pts"] = int(r["n_pts"])
            out[r["tid"]] = r
    return out


def load_h3_confirmed(stem: str) -> set:
    confirmed = set()
    path = H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv"
    if not path.exists():
        return confirmed
    with path.open() as fh:
        for r in csv.DictReader(fh):
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


def compute_arc_g_score(gs, expected_g=0.5, tolerance=0.3) -> float:
    if not gs:
        return 0.5
    n_clean = sum(1 for g in gs if abs(g - expected_g) <= tolerance)
    return n_clean / len(gs)


def compute_h9(stem: str, chains: list[dict], tracklets: dict[int, dict]) -> dict:
    """Coverage = observed_frames / span_frames (matches h10v10_with_h26)."""
    out = {}
    for c in chains:
        tids = c["tids"]
        if not tids:
            continue
        observed = sum(tracklets[t]["n_pts"] for t in tids
                       if t in tracklets)
        span = c["last_frame"] - c["first_frame"]
        coverage = min(1.0, observed / span) if span > 0 else 1.0
        out[c["chain_id"]] = coverage
    return out


def compute_chain_quality(chain: dict, edges_in_chain: list[dict],
                          h3_confirmed: set, h8_violations: set,
                          h8_unknowns: set, h8v8_stats: dict,
                          coverage: float, weights: dict) -> dict:
    """Compute H10 v10 quality for one chain.

    Faithful to h10v10_with_h26.py:
    - n_h3_eligible = HAND + RECLASSIFIED + AMBIGUOUS + H26
      (excludes V_RECLASSIFIED and H22_RECLASSIFIED)
    - h3 = n_h3 / n_h3_eligible if n_h3_eligible > 0 else None
    - h8 = (n_air - n_viol - 0.5*n_unk) / n_air if n_air > 0 else 1.0
    - h8v8 = mean of per-tid arc_g scores
    - h3-redistribution rule when h3 is None
    """
    n_total = len(edges_in_chain)
    n_hand = sum(1 for e in edges_in_chain if "HAND" in e["edge_type"])
    n_v_reclass = sum(1 for e in edges_in_chain
                      if e["edge_type"] == "V_RECLASSIFIED_HAND_TRANSITION")
    n_h26 = sum(1 for e in edges_in_chain
                if e["edge_type"] == "H26_RECLASSIFIED_HAND_TRANSITION")
    n_h22 = sum(1 for e in edges_in_chain
                if e["edge_type"] == "H22_RECLASSIFIED_HAND_TRANSITION")
    n_air = sum(1 for e in edges_in_chain if e["edge_type"] == "BALLISTIC")
    n_h3_eligible = sum(1 for e in edges_in_chain
                        if e["edge_type"] in (
                            "HAND_TRANSITION",
                            "RECLASSIFIED_HAND_TRANSITION",
                            "AMBIGUOUS_HAND_TRANSITION",
                            "H26_RECLASSIFIED_HAND_TRANSITION",
                        ))
    n_h3 = sum(1 for e in edges_in_chain
               if e["edge_type"] in (
                   "HAND_TRANSITION",
                   "RECLASSIFIED_HAND_TRANSITION",
                   "AMBIGUOUS_HAND_TRANSITION",
                   "H26_RECLASSIFIED_HAND_TRANSITION",
               )
               and (e["from_tid"], e["to_tid"]) in h3_confirmed)
    h3 = (n_h3 / n_h3_eligible) if n_h3_eligible > 0 else None

    n_viol = sum(1 for e in edges_in_chain
                 if e["edge_type"] == "BALLISTIC"
                 and (e["from_tid"], e["to_tid"]) in h8_violations)
    n_unk = sum(1 for e in edges_in_chain
                if e["edge_type"] == "BALLISTIC"
                and (e["from_tid"], e["to_tid"]) in h8_unknowns)
    h8 = ((n_air - n_viol - 0.5 * n_unk) / n_air) if n_air > 0 else 1.0

    h9 = coverage

    arc_scores = [compute_arc_g_score(h8v8_stats.get(t, []))
                  for t in chain["tids"]]
    h8v8 = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5

    w = weights
    if h3 is None:
        s = w["h8"] + w["h9"] + w["h8v8"]
        if s > 0:
            w8_eff = w["h8"] + w["h3"] * w["h8"] / s
            w9_eff = w["h9"] + w["h3"] * w["h9"] / s
            w8v8_eff = w["h8v8"] + w["h3"] * w["h8v8"] / s
        else:
            w8_eff, w9_eff, w8v8_eff = 0.0, 0.0, 0.0
    else:
        w8_eff, w9_eff, w8v8_eff = w["h8"], w["h9"], w["h8v8"]
    q = (w["h3"] * (h3 or 0) + w8_eff * h8 + w9_eff * h9 + w8v8_eff * h8v8)

    return {
        "chain_id": chain["chain_id"],
        "n_tracklets": chain["n_tracklets"],
        "n_hand_edges": n_hand,
        "n_v_reclass_edges": n_v_reclass,
        "n_h26_edges": n_h26,
        "n_h22_edges": n_h22,
        "n_air_edges": n_air,
        "n_h3_confirmed": n_h3,
        "n_air_in_chain": n_air,
        "n_air_violating": n_viol,
        "n_air_unknown": n_unk,
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
        tracklets = load_tracklets(stem)
        h3_confirmed = load_h3_confirmed(stem)
        h8_violations, h8_unknowns = load_h8_violations(stem)
        h8v8_stats = load_h8v8_per_arc_g(stem)
        coverage_map = compute_h9(stem, chains, tracklets)
        weights = WEIGHTS_PER_VIDEO[stem]

        # Build chain -> edges map (only consecutive edges within chain)
        chain_edges = defaultdict(list)
        for c in chains:
            tids = c["tids"]
            for i in range(len(tids) - 1):
                a, b = tids[i], tids[i + 1]
                for e in edges:
                    if e["from_tid"] == a and e["to_tid"] == b:
                        chain_edges[c["chain_id"]].append(e)
                        break

        results = []
        for c in chains:
            cid = c["chain_id"]
            r = compute_chain_quality(
                c, chain_edges[cid], h3_confirmed, h8_violations,
                h8_unknowns, h8v8_stats, coverage_map[cid], weights,
            )
            results.append(r)

        results.sort(key=lambda r: -r["quality_v10"])

        mean_q = sum(r["quality_v10"] for r in results) / len(results)
        print(f"  {stem}: n_chains={len(chains)} mean_v10={mean_q:.4f}")

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
