#!/usr/bin/env python3
"""H10 v6 - chain quality with per-arc gravity (4th dimension).

H10 v5 (current recommended) uses 3 dimensions:
  - h3: H3 stationary-cluster confirmation of hand-edges
  - h8: H8 v5 parabolic-fit physics consistency
  - h9: H9 object permanence (chain coverage)

H8 v8 produces per-arc parabolic fits for each tracklet. A
tracklet's "arc-gravity score" is the consistency of its arcs'
gravity with the expected 0.5 px/frame^2:
  - If all arcs have g in [0.3, 0.7], score = 1.0 (clean parabolas)
  - If arcs have widely varying g, score = 0 (noisy)
  - Tracklet with no arcs: score = 0.5 (unknown)

Per-chain h8v8_score = mean of tracklet arc-gravity scores.

H10 v6 formula: quality = 0.25*h3 + 0.20*h8_v5 + 0.30*h9 + 0.25*h8v8

Hypothesis: a tracklet whose arcs all have g ~ 0.5 is more likely
to be a real single ball (not a noise artifact or hand-contaminated).
A chain of such tracklets is more likely a real juggling cycle.

This should:
  - Promote chains whose tracklets are clean parabolic motions
    (chain 23 on identical has 7 clean tracklets).
  - Demote chains with noisy/hand-contaminated tracklets
    (chain 30 has tracklets with mixed g).
  - Be especially useful for YouTube where H8 v5 is unreliable
    on long tracklets.
"""
from __future__ import annotations

import csv
import json
import statistics
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

WEIGHTS_V6 = (0.25, 0.20, 0.30, 0.25)  # h3, h8, h9, h8v8 (default)
WEIGHTS_V5 = (0.30, 0.30, 0.40)  # h3, h8, h9

# Per-arc gravity scoring
EXPECTED_G = 0.5  # quoted gravity
G_TOLERANCE = 0.3  # [0.2, 0.8] considered clean
G_FLOOR = 0.0
G_CEIL = 2.0


def load_h237_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            r["n_tracklets"] = int(r["n_tracklets"])
            r["n_hand_edges"] = int(r["n_hand_edges"])
            r["n_air_edges"] = int(r["n_air_edges"])
            r["n_h3_confirmed"] = int(r["n_h3_confirmed"])
            out.append(r)
    return out


def load_h237_edges(stem: str) -> list[dict]:
    edges = []
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            edges.append({
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "edge_type": r["edge_type"],
            })
    return edges


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


def load_h9_coverage(stem: str) -> dict:
    with (H1_DATA / "h9_object_permanence_summary.json").open() as fh:
        s = json.load(fh)
    return {cs["chain_id"]: cs for cs in s["videos"][stem]["chain_stats"]}


def load_h8v8_per_arc_g(stem: str) -> dict:
    """Returns {tid: [g1, g2, ...]} for each tracklet with arcs."""
    out = defaultdict(list)
    path = H1_DATA / f"h8_v8_extrema_arcs_{stem}.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                src_g = float(r["src_g"])
                tgt_g = float(r["tgt_g"])
                if G_FLOOR < src_g < G_CEIL:
                    out[int(r["src_tid"])].append(src_g)
                if G_FLOOR < tgt_g < G_CEIL:
                    out[int(r["tgt_tid"])].append(tgt_g)
            except (KeyError, ValueError):
                continue
    return out


def compute_arc_g_score(gs: list[float]) -> float:
    """Score a tracklet's per-arc gravity consistency.

    A tracklet with all arcs near expected g=0.5 gets 1.0.
    A tracklet with widely varying g gets 0.0.
    A tracklet with no arcs gets 0.5 (unknown).
    """
    if not gs:
        return 0.5
    # How close are the per-arc gravity values to expected?
    n_clean = sum(1 for g in gs if abs(g - EXPECTED_G) <= G_TOLERANCE)
    return n_clean / len(gs)


def chain_air_edges(chain: dict, all_edges: list[dict]) -> list[tuple]:
    tids = chain["tids"]
    out = []
    for i in range(len(tids) - 1):
        a, b = tids[i], tids[i + 1]
        for e in all_edges:
            if e["from_tid"] == a and e["to_tid"] == b:
                out.append((a, b, e["edge_type"]))
                break
    return out


def per_chain_quality_v6(stem: str, h8_violations: set, h8_unknowns: set,
                          h9_cov: dict, h8v8_per_arc_g: dict) -> list[dict]:
    """Compute per-chain quality using v6 formula (4 dimensions)."""
    chains = load_h237_chains(stem)
    edges = load_h237_edges(stem)
    out = []
    for c in chains:
        h3 = (c["n_h3_confirmed"] / c["n_hand_edges"]
              if c["n_hand_edges"] > 0 else None)
        chain_edges = chain_air_edges(c, edges)
        n_air = sum(1 for _, _, et in chain_edges if et == "BALLISTIC")
        n_violating = sum(1 for a, b, et in chain_edges
                          if et == "BALLISTIC" and (a, b) in h8_violations)
        n_unknown = sum(1 for a, b, et in chain_edges
                        if et == "BALLISTIC" and (a, b) in h8_unknowns)
        if n_air > 0:
            h8 = (n_air - n_violating - 0.5 * n_unknown) / n_air
        else:
            h8 = 1.0
        h9 = h9_cov.get(c["chain_id"], {}).get("coverage", 0.0)
        # h8v8: per-arc gravity score, averaged across chain's tracklets
        tids = c["tids"]
        arc_scores = [compute_arc_g_score(h8v8_per_arc_g.get(tid, []))
                       for tid in tids]
        h8v8 = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
        # Quality v6 = w3*h3 + w8*h8 + w9*h9 + w8v8*h8v8
        w3, w8, w9, w8v8 = WEIGHTS_V6
        if h3 is None:
            s = w8 + w9 + w8v8
            w8 = w8 + w3 * w8 / s
            w9 = w9 + w3 * w9 / s
            w8v8 = w8v8 + w3 * w8v8 / s
        q_v6 = (w3 * (h3 or 0) + w8 * h8 + w9 * h9 + w8v8 * h8v8
                 if h3 is not None
                 else w8 * h8 + w9 * h9 + w8v8 * h8v8)
        # Quality v5 (3-dim, for comparison)
        w3, w8, w9 = WEIGHTS_V5
        if h3 is None:
            s = w8 + w9
            w8 = w8 + w3 * w8 / s
            w9 = w9 + w3 * w9 / s
            q_v5 = w8 * h8 + w9 * h9
        else:
            q_v5 = w3 * h3 + w8 * h8 + w9 * h9
        out.append({
            "chain_id": c["chain_id"],
            "n_tracklets": c["n_tracklets"],
            "n_hand_edges": c["n_hand_edges"],
            "n_air_edges": c["n_air_edges"],
            "n_h3_confirmed": c["n_h3_confirmed"],
            "n_air_in_chain": n_air,
            "n_air_violating": n_violating,
            "n_air_unknown": n_unknown,
            "h3_score": h3, "h8_score": h8, "h9_score": h9, "h8v8_score": h8v8,
            "quality_v5": round(q_v5, 4),
            "quality_v6": round(q_v6, 4),
        })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        h9_cov = load_h9_coverage(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        h8v8_per_arc_g = load_h8v8_per_arc_g(stem)
        print(f"  Tracklets with v8 arc data: {len(h8v8_per_arc_g)}")
        # Compute per-chain quality
        results = per_chain_quality_v6(
            stem, h8_v5_viol, h8_v5_unknown, h9_cov, h8v8_per_arc_g)
        # Sort by v6 quality
        results.sort(key=lambda r: -r["quality_v6"])
        # Compare to v5 ranking
        v5_ranked = sorted(results, key=lambda r: -r["quality_v5"])
        v5_rank = {r["chain_id"]: i for i, r in enumerate(v5_ranked)}
        # Report
        print(f"  Top 10 chains by v6 quality:")
        for r in results[:10]:
            v5_r = v5_rank[r["chain_id"]]
            print(f"    chain {r['chain_id']:>3}: v5={r['quality_v5']:.3f} "
                  f"v6={r['quality_v6']:.3f} (v5_rank={v5_r}, "
                  f"h3={r['h3_score']}, h8={r['h8_score']:.2f}, "
                  f"h9={r['h9_score']:.2f}, h8v8={r['h8v8_score']:.2f})")
        # Aggregate
        n_improved = sum(1 for r in results
                          if results.index(r) < v5_rank[r["chain_id"]])
        n_worsened = sum(1 for r in results
                          if results.index(r) > v5_rank[r["chain_id"]])
        n_unchanged = sum(1 for r in results
                          if results.index(r) == v5_rank[r["chain_id"]])
        avg_v5 = sum(r["quality_v5"] for r in results) / len(results)
        avg_v6 = sum(r["quality_v6"] for r in results) / len(results)
        print(f"  rank: improved={n_improved}, unchanged={n_unchanged}, "
              f"worsened={n_worsened}")
        print(f"  mean quality: v5={avg_v5:.3f}, v6={avg_v6:.3f} "
              f"(delta={avg_v6-avg_v5:+.3f})")
        # Big movers
        deltas = [(r["chain_id"], v5_rank[r["chain_id"]] - results.index(r),
                    r["quality_v5"], r["quality_v6"]) for r in results]
        deltas.sort(key=lambda x: -x[1])
        print(f"  Top 5 IMPROVED (v5_rank - v6_rank):")
        for cid, d, q5, q6 in deltas[:5]:
            print(f"    chain {cid}: rank delta={d:+d}, v5={q5:.3f} v6={q6:.3f}")
        print(f"  Top 5 WORSENED (v5_rank - v6_rank):")
        for cid, d, q5, q6 in sorted(deltas, key=lambda x: x[1])[:5]:
            print(f"    chain {cid}: rank delta={d:+d}, v5={q5:.3f} v6={q6:.3f}")

        # Persist
        out_csv = H1_DATA / f"h10v6_chain_quality_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(results[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_csv.name}")
        # Sensitivity grid on h8v8 weight
        print(f"  Sensitivity grid (h8v8 weight):")
        sens = []
        for w8v8 in [0.0, 0.10, 0.20, 0.25, 0.30, 0.40, 0.50]:
            # Re-rank with this weight
            w3, w8, w9 = 0.30, 0.30, 0.40
            # Recompute quality
            tmp = []
            for r in results:
                h3 = r["h3_score"]
                h8 = r["h8_score"]
                h9 = r["h9_score"]
                h8v8 = r["h8v8_score"]
                w3_, w8_, w9_, w8v8_ = w3, w8, w9, w8v8
                # Renormalize to sum=1
                total = w3_ + w8_ + w9_ + w8v8_
                w3_ /= total
                w8_ /= total
                w9_ /= total
                w8v8_ /= total
                if h3 is None:
                    s = w8_ + w9_ + w8v8_
                    w8_ = w8_ + w3_ * w8_ / s
                    w9_ = w9_ + w3_ * w9_ / s
                    w8v8_ = w8v8_ + w3_ * w8v8_ / s
                    q = w8_ * h8 + w9_ * h9 + w8v8_ * h8v8
                else:
                    q = w3_ * h3 + w8_ * h8 + w9_ * h9 + w8v8_ * h8v8
                tmp.append((r["chain_id"], q))
            tmp.sort(key=lambda x: -x[1])
            ranks = {cid: i for i, (cid, _) in enumerate(tmp)}
            # Compare to v5 ranks
            n_changed = sum(1 for cid, _ in tmp if v5_rank[cid] != ranks[cid])
            avg_q = sum(q for _, q in tmp) / len(tmp)
            sens.append({"w8v8": w8v8, "mean_q": round(avg_q, 3),
                         "n_changed": n_changed})
            print(f"    w8v8={w8v8:.2f}: mean_q={avg_q:.3f}, "
                  f"n_changed_from_v5={n_changed}/{len(tmp)}")
        summary["videos"][stem] = {
            "results": results,
            "n_chains": len(results),
            "n_improved": n_improved,
            "n_unchanged": n_unchanged,
            "n_worsened": n_worsened,
            "mean_v5": round(avg_v5, 4),
            "mean_v6": round(avg_v6, 4),
            "top_5_by_v6": [
                {"chain_id": r["chain_id"], "v5": r["quality_v5"],
                 "v6": r["quality_v6"]} for r in results[:5]
            ],
            "sensitivity_grid": sens,
        }
    out = H1_DATA / "h10v6_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
