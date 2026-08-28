#!/usr/bin/env python3
"""H10 v10 — H7v3plus2 (H26) chains + H10 v6b per-video weights.

HYPOTHESIS:
  H26 adds 2 H24 visually-confirmed REAL H20-KEPT edges to the
  h7v3pure chain set. The new chain set (h7v3plus2) has:
    - identical: 43 -> 42 chains (1 chain reduction)
    - 7->10 and 59->61 both admitted with cost=1.0
  H10 v10 should re-measure chain quality on h7v3plus2 and compare
  to h7v3pure (H22 reference) and h7v3plus (H21 reference).
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
            r["cost"] = float(r["cost"])
            out.append(r)
    return out


def load_h3_confirmed_links(stem: str) -> set:
    confirmed = set()
    try:
        with (H1_DATA / f"hand_links_v4_v4d_throw7_full_with_h3.csv").open() as fh:
            rdr = csv.DictReader(fh)
            for r in rdr:
                if r["stem"] == stem and r.get("h3_confirmed", "False") == "True":
                    confirmed.add((int(r["from_tid"]), int(r["to_tid"])))
    except FileNotFoundError:
        pass
    return confirmed


def load_h8_violations_v5(stem: str):
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


def compute_arc_g_score(gs, expected_g=0.5, tolerance=0.3) -> float:
    if not gs:
        return 0.5
    n_clean = sum(1 for g in gs if abs(g - expected_g) <= tolerance)
    return n_clean / len(gs)


def compute_h9(stem: str, chains: list[dict]) -> dict:
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
        coverage = min(1.0, observed / span) if span > 0 else 1.0
        gaps = []
        for i in range(len(tids) - 1):
            a, b = tids[i], tids[i + 1]
            if a in tracklets and b in tracklets:
                gap = tracklets[b]["first_frame"] - tracklets[a]["last_frame"]
                if gap >= 5:
                    gaps.append(gap)
        out[c["chain_id"]] = {
            "chain_id": c["chain_id"],
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
        h7v3plus2_chains = load_h7v3plus2_chains(stem)
        h7v3plus2_edges = load_h7v3plus2_edges(stem)
        h3_confirmed_links = load_h3_confirmed_links(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        h8v8_stats = load_h8v8_per_arc_g(stem)
        h9_cov = compute_h9(stem, h7v3plus2_chains)

        print(f"  h7v3plus2 chains: {len(h7v3plus2_chains)}")
        print(f"  h7v3plus2 edges: {len(h7v3plus2_edges)}")
        print(f"  h3 confirmed: {len(h3_confirmed_links)}")

        # Build chain -> edges map
        chain_edges = defaultdict(list)
        for c in h7v3plus2_chains:
            tids = c["tids"]
            for i in range(len(tids) - 1):
                a, b = tids[i], tids[i + 1]
                for e in h7v3plus2_edges:
                    if e["from_tid"] == a and e["to_tid"] == b:
                        chain_edges[c["chain_id"]].append(e)
                        break

        # Compute per-chain quality
        results = []
        for c in h7v3plus2_chains:
            cid = c["chain_id"]
            tids = c["tids"]
            edges = chain_edges[cid]
            n_hand = sum(1 for e in edges if "HAND" in e["edge_type"])
            n_v_reclass = sum(1 for e in edges if e["edge_type"] == "V_RECLASSIFIED_HAND_TRANSITION")
            n_h26 = sum(1 for e in edges if e["edge_type"] == "H26_RECLASSIFIED_HAND_TRANSITION")
            n_air = sum(1 for e in edges if e["edge_type"] == "BALLISTIC")
            n_h3_eligible = sum(1 for e in edges
                                if e["edge_type"] in ("HAND_TRANSITION",
                                                       "RECLASSIFIED_HAND_TRANSITION",
                                                       "AMBIGUOUS_HAND_TRANSITION",
                                                       "H26_RECLASSIFIED_HAND_TRANSITION"))
            n_h3 = sum(1 for e in edges
                       if e["edge_type"] in ("HAND_TRANSITION",
                                              "RECLASSIFIED_HAND_TRANSITION",
                                              "AMBIGUOUS_HAND_TRANSITION",
                                              "H26_RECLASSIFIED_HAND_TRANSITION")
                       and (e["from_tid"], e["to_tid"]) in h3_confirmed_links)
            h3 = (n_h3 / n_h3_eligible) if n_h3_eligible > 0 else None
            n_viol = sum(1 for e in edges
                         if e["edge_type"] == "BALLISTIC"
                         and (e["from_tid"], e["to_tid"]) in h8_v5_viol)
            n_unk = sum(1 for e in edges
                        if e["edge_type"] == "BALLISTIC"
                        and (e["from_tid"], e["to_tid"]) in h8_v5_unknown)
            h8 = ((n_air - n_viol - 0.5 * n_unk) / n_air) if n_air > 0 else 1.0
            h9 = h9_cov.get(cid, {}).get("coverage", 0.0)
            arc_scores = [compute_arc_g_score(h8v8_stats.get(t, [])) for t in tids]
            h8v8 = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
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
                "n_h26_edges": n_h26,
                "n_air_edges": n_air,
                "n_h3_confirmed": n_h3,
                "n_air_in_chain": n_air,
                "n_air_violating": n_viol,
                "n_air_unknown": n_unk,
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
                  f"n_h26={r['n_h26_edges']}, n_air={r['n_air_edges']}, "
                  f"h8={r['h8_score']:.2f}, h9={r['h9_score']:.2f}, h8v8={r['h8v8_score']:.2f}, "
                  f"q={r['quality_v10']:.3f}")

        mean_v10 = sum(r["quality_v10"] for r in results) / len(results)
        n_air_zero = sum(1 for r in results if r["n_air_edges"] == 0)
        n_h8_one = sum(1 for r in results if r["h8_score"] == 1.0)
        print(f"  mean v10: {mean_v10:.4f}")
        print(f"  chains with n_air=0: {n_air_zero}/{len(results)}")
        print(f"  chains with h8=1.0: {n_h8_one}/{len(results)}")

        # Comparison to v9 (H7v3pure) and v10 (H7v3plus H21)
        v9_path = H1_DATA / f"h10v9_chain_quality_{stem}.csv"
        v9_mean = None
        if v9_path.exists():
            with v9_path.open() as fh:
                rows = list(csv.DictReader(fh))
                if rows:
                    v9_mean = sum(float(r.get("quality_v9", 0)) for r in rows) / len(rows)
        v10_path = H1_DATA / f"h21v2_chain_quality_{stem}.csv"
        v10_mean = None
        if v10_path.exists():
            with v10_path.open() as fh:
                rows = list(csv.DictReader(fh))
                if rows:
                    v10_mean = sum(float(r.get("quality_v10", 0)) for r in rows) / len(rows)
        print(f"  v9 (h7v3pure) mean:  {v9_mean:.4f}" if v9_mean is not None else "  v9 mean: N/A")
        print(f"  v10 (h7v3plus) mean: {v10_mean:.4f}" if v10_mean is not None else "  v10 mean: N/A")
        print(f"  v10 (h7v3plus2) mean: {mean_v10:.4f}")

        summary["videos"][stem] = {
            "n_chains": len(h7v3plus2_chains),
            "n_edges": len(h7v3plus2_edges),
            "mean_quality_v10": mean_v10,
            "mean_quality_v9": v9_mean,
            "mean_quality_h21v2": v10_mean,
            "top3": [
                {"chain_id": r["chain_id"], "n_tracklets": r["n_tracklets"],
                 "quality_v10": r["quality_v10"]}
                for r in results[:3]
            ],
            "results": results,
        }

    out_path = H1_DATA / "h10v10_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Per-video CSV
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h10v10_chain_quality_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "n_hand_edges", "n_v_reclass_edges",
                "n_h26_edges", "n_air_edges", "n_h3_confirmed", "n_air_in_chain",
                "n_air_violating", "n_air_unknown", "h3_score", "h8_score", "h9_score",
                "h8v8_score", "quality_v10"])
            w.writeheader()
            for r in v["results"]:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})


if __name__ == "__main__":
    main()
