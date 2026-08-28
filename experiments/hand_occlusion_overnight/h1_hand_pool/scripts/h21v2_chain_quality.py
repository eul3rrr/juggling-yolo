#!/usr/bin/env python3
"""H21 v2: H10 v9 chain quality on H21 h7v3plus chains (with H20-KEPT REAL edges).

HYPOTHESIS:
  H21 added 4 visually-confirmed REAL H20-KEPT edges as new
  HAND_TRANSITION edges and re-ran min-cost flow. The resulting
  h7v3plus chains should have:
  1. Better coverage (more multi-tracklet chains)
  2. Better H10 v9 quality (especially for the merged chains)
  3. Better H11 v7 identity propagation (more catch+throw events)

  This script measures the H10 v9 chain quality on the h7v3plus chains
  to test hypothesis 1 + 2.

APPROACH:
  Same as H10 v9 but uses h7v3plus chains/edges instead of h7v3pure.
  The 3 admitted H21-KEPT edges should:
  1. Merge 3 pairs of chains (6->15: chain 4 + 11 = 5,6,15; 54->57:
     chain 30 + 33 = 51,52,54,57; 56->58: chain 32 + 34 = 56,58)
  2. Add hand-edges that improve h3_score for the affected chains
  3. The YouTube 20->21 was rejected by capacity (16->21 has t21
     already), so no YouTube chain change
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

WEIGHTS_PER_VIDEO = {
    "identical_balls_trick_000_018": {
        "h3": 0.30, "h8": 0.30, "h9": 0.40, "h8v8": 0.0
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        "h3": 0.25, "h8": 0.20, "h9": 0.30, "h8v8": 0.25
    },
}


def load_chains(stem: str, prefix: str = "h7v3plus") -> list[dict]:
    out = []
    with (H1_DATA / f"{prefix}_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_edges(stem: str, prefix: str = "h7v3plus") -> list[dict]:
    out = []
    with (H1_DATA / f"{prefix}_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def load_h3_confirmed_links(stem: str) -> set:
    path = H1_DATA / "hand_links_v4_v4d_throw7_full_with_h3.csv"
    if not path.exists():
        return set()
    with path.open() as fh:
        first_line = fh.readline().strip()
    if "video" not in first_line or "from_tid" not in first_line:
        return set()
    with path.open() as fh:
        rdr = csv.DictReader(fh)
        confirmed = set()
        for r in rdr:
            if r["stem"] == stem and r.get("h3_confirmed", "False") == "True":
                confirmed.add((int(r["from_tid"]), int(r["to_tid"])))
    return confirmed


def load_h8_v5_violations(stem: str):
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
                continue
    return out


def compute_arc_g_score(gs: list[float], expected_g: float = 0.5,
                        tolerance: float = 0.3) -> float:
    if not gs:
        return 0.5
    n_clean = sum(1 for g in gs if abs(g - expected_g) <= tolerance)
    return n_clean / len(gs)


def compute_h9_for_chains(stem: str, chains: list[dict]) -> dict:
    tracklets = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            tracklets[int(r["tid"])] = {
                "n_pts": int(r["n_pts"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
            }
    out = {}
    for c in chains:
        if not c["tids"]:
            continue
        tids = c["tids"]
        observed = sum(tracklets[t]["n_pts"] for t in tids)
        span = c["last_frame"] - c["first_frame"]
        if span == 0:
            coverage = 1.0
        else:
            coverage = min(1.0, observed / span)
        gaps = []
        for i in range(len(tids) - 1):
            a, b = tids[i], tids[i + 1]
            if a in tracklets and b in tracklets:
                gap = tracklets[b]["first_frame"] - tracklets[a]["last_frame"]
                if gap >= 5:
                    gaps.append(gap)
        out[c["chain_id"]] = {
            "chain_id": c["chain_id"],
            "n_tracklets": c["n_tracklets"],
            "n_gaps": len(gaps),
            "total_gap_frames": sum(gaps),
            "observed_frames": observed,
            "span_frames": span,
            "coverage": coverage,
        }
    return out


def main():
    summary = {"videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        weights = WEIGHTS_PER_VIDEO[stem]
        # Compare h7v3pure (v9) vs h7v3plus (v10 = H21 v2)
        h7v3pure_chains = load_chains(stem, "h7v3pure")
        h7v3plus_chains = load_chains(stem, "h7v3plus")
        h7v3pure_edges = load_edges(stem, "h7v3pure")
        h7v3plus_edges = load_edges(stem, "h7v3plus")
        print(f"  h7v3pure: {len(h7v3pure_chains)} chains, {len(h7v3pure_edges)} edges")
        print(f"  h7v3plus: {len(h7v3plus_chains)} chains, {len(h7v3plus_edges)} edges")
        print(f"  net chain change: {len(h7v3plus_chains) - len(h7v3pure_chains):+d}")
        print(f"  net edge change:  {len(h7v3plus_edges) - len(h7v3pure_edges):+d}")

        h3_confirmed_links = load_h3_confirmed_links(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_v5_violations(stem)
        h8v8_stats = load_h8v8_per_arc_g(stem)
        h9_cov = compute_h9_for_chains(stem, h7v3plus_chains)

        # Build chain -> edges map for h7v3plus
        chain_edges = defaultdict(list)
        for c in h7v3plus_chains:
            tids = c["tids"]
            for i in range(len(tids) - 1):
                a, b = tids[i], tids[i + 1]
                for e in h7v3plus_edges:
                    if e["from_tid"] == a and e["to_tid"] == b:
                        chain_edges[c["chain_id"]].append(e)
                        break

        # Compute per-chain quality (same logic as H10v9)
        results = []
        for c in h7v3plus_chains:
            cid = c["chain_id"]
            tids = c["tids"]
            edges = chain_edges[cid]
            # Treat H21_RECLASSIFIED as a hand-edge (same as V_RECLASSIFIED)
            n_hand = sum(1 for e in edges if "HAND" in e["edge_type"])
            n_v_reclass = sum(1 for e in edges if e["edge_type"] in (
                "V_RECLASSIFIED_HAND_TRANSITION", "H21_RECLASSIFIED_HAND_TRANSITION"))
            n_air = sum(1 for e in edges if e["edge_type"] == "BALLISTIC")
            # h3 eligibility: H21 edges are H20-KEPT e6c_not_in_h7v2, V-shape only
            # We treat H21 same as V_RECLASSIFIED: NOT eligible for h3
            n_h3_eligible = sum(1 for e in edges
                                if e["edge_type"] in ("HAND_TRANSITION",
                                                       "RECLASSIFIED_HAND_TRANSITION",
                                                       "AMBIGUOUS_HAND_TRANSITION"))
            n_h3 = sum(1 for e in edges
                       if e["edge_type"] in ("HAND_TRANSITION",
                                              "RECLASSIFIED_HAND_TRANSITION",
                                              "AMBIGUOUS_HAND_TRANSITION")
                       and (e["from_tid"], e["to_tid"]) in h3_confirmed_links)
            if n_h3_eligible > 0:
                h3 = n_h3 / n_h3_eligible
            else:
                h3 = None
            n_viol = sum(1 for e in edges
                         if e["edge_type"] == "BALLISTIC"
                         and (e["from_tid"], e["to_tid"]) in h8_v5_viol)
            n_unk = sum(1 for e in edges
                        if e["edge_type"] == "BALLISTIC"
                        and (e["from_tid"], e["to_tid"]) in h8_v5_unknown)
            if n_air > 0:
                h8 = (n_air - n_viol - 0.5 * n_unk) / n_air
            else:
                h8 = 1.0
            h9 = h9_cov.get(cid, {}).get("coverage", 0.0)
            if tids:
                arc_scores = [compute_arc_g_score(h8v8_stats.get(t, []))
                              for t in tids]
                h8v8 = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
            else:
                h8v8 = 0.5
            w = weights
            if h3 is None:
                s = w["h8"] + w["h9"] + w["h8v8"]
                w8_eff = w["h8"] + w["h3"] * w["h8"] / s
                w9_eff = w["h9"] + w["h3"] * w["h9"] / s
                w8v8_eff = w["h8v8"] + w["h3"] * w["h8v8"] / s
            else:
                w8_eff, w9_eff, w8v8_eff = w["h8"], w["h9"], w["h8v8"]
            q = (w["h3"] * (h3 or 0) + w8_eff * h8 + w9_eff * h9 + w8v8_eff * h8v8)
            results.append({
                "chain_id": cid,
                "n_tracklets": c["n_tracklets"],
                "n_hand_edges": n_hand,
                "n_v_reclass_edges": n_v_reclass,
                "n_air_edges": n_air,
                "n_h3_confirmed": n_h3,
                "h3_score": h3,
                "h8_score": h8,
                "h9_score": h9,
                "h8v8_score": h8v8,
                "quality_v10": q,
            })

        results.sort(key=lambda r: -r["quality_v10"])
        print(f"  Top 3 chains by v10 quality:")
        for r in results[:3]:
            print(f"    chain {r['chain_id']}: n_tids={r['n_tracklets']}, "
                  f"n_hand={r['n_hand_edges']}, n_v_reclass={r['n_v_reclass_edges']}, "
                  f"n_air={r['n_air_edges']}, h8={r['h8_score']:.2f}, h9={r['h9_score']:.2f}, "
                  f"h8v8={r['h8v8_score']:.2f}, q={r['quality_v10']:.3f}")

        mean_v10 = sum(r["quality_v10"] for r in results) / len(results)
        n_air_zero = sum(1 for r in results if r["n_air_edges"] == 0)
        n_h8_one = sum(1 for r in results if r["h8_score"] == 1.0)
        print(f"  mean v10: {mean_v10:.4f}")
        print(f"  chains with n_air=0: {n_air_zero}/{len(results)}")
        print(f"  chains with h8=1.0: {n_h8_one}/{len(results)}")

        # Compare with h7v3pure v9 quality (read existing summary)
        try:
            v9_summary = json.load(open(H1_DATA / "h10v9_chain_quality_summary.json"))
            v9_mean = v9_summary["videos"][stem]["mean_v9"]
            v9_top = max(v9_summary["videos"][stem]["results"],
                         key=lambda r: r["quality_v9"])
            print(f"  vs h7v3pure v9 mean: {v9_mean:.4f} (delta {mean_v10 - v9_mean:+.4f})")
            print(f"  vs h7v3pure v9 top:  chain {v9_top['chain_id']} q={v9_top['quality_v9']:.3f}")
        except FileNotFoundError:
            pass

        summary["videos"][stem] = {
            "n_chains": len(results),
            "results": results,
            "mean_v10": mean_v10,
            "weights": weights,
        }

    out_path = H1_DATA / "h21v2_chain_quality_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h21v2_chain_quality_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "n_hand_edges", "n_v_reclass_edges",
                "n_air_edges", "n_h3_confirmed", "h3_score", "h8_score",
                "h9_score", "h8v8_score", "quality_v10",
            ])
            w.writeheader()
            for r in v["results"]:
                w.writerow({k: r[k] for k in w.fieldnames})


if __name__ == "__main__":
    main()
