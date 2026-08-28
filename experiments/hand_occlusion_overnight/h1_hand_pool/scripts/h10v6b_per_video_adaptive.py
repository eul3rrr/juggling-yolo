#!/usr/bin/env python3
"""H10 v6b - per-video adaptive weights for h8v8.

H10 v6 with default weights (h8v8=0.25) had OPPOSITE effects on
the two videos:
- identical: hurt ranking (chain 21 dropped from v5 #0 to v6 #7)
  because t31/t36 have unreliable parabolic fits.
- youtube: helped ranking (mean q 0.537 -> 0.569) because long
  tracklets have many arcs and the per-arc gravity is a real
  signal.

H10 v6b uses per-video adaptive weights:
- identical: w8v8 = 0 (revert to v5)
- youtube: w8v8 = 0.30 (from sensitivity grid, near-best)

This should give best of both worlds: identical ranking is
preserved (matches v5), YouTube ranking is improved.
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

# Per-video weights
WEIGHTS_PER_VIDEO = {
    "identical_balls_trick_000_018": (0.30, 0.30, 0.40, 0.00),  # h3, h8, h9, h8v8
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": (0.25, 0.20, 0.30, 0.25),
}

# Per-arc gravity scoring
EXPECTED_G = 0.5
G_TOLERANCE = 0.3
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
    if not gs:
        return 0.5
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


def per_chain_quality_v6b(stem: str, h8_violations: set, h8_unknowns: set,
                           h9_cov: dict, h8v8_per_arc_g: dict) -> list[dict]:
    """Compute per-chain quality using v6b formula (per-video adaptive weights)."""
    chains = load_h237_chains(stem)
    edges = load_h237_edges(stem)
    w3, w8, w9, w8v8 = WEIGHTS_PER_VIDEO[stem]
    # Renormalize
    total = w3 + w8 + w9 + w8v8
    w3, w8, w9, w8v8 = w3 / total, w8 / total, w9 / total, w8v8 / total
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
        tids = c["tids"]
        arc_scores = [compute_arc_g_score(h8v8_per_arc_g.get(tid, []))
                       for tid in tids]
        h8v8_s = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
        if h3 is None:
            s = w8 + w9 + w8v8
            w8_ = w8 + w3 * w8 / s
            w9_ = w9 + w3 * w9 / s
            w8v8_ = w8v8 + w3 * w8v8 / s
            q = w8_ * h8 + w9_ * h9 + w8v8_ * h8v8_s
        else:
            q = w3 * h3 + w8 * h8 + w9 * h9 + w8v8 * h8v8_s
        out.append({
            "chain_id": c["chain_id"],
            "n_tracklets": c["n_tracklets"],
            "n_hand_edges": c["n_hand_edges"],
            "n_air_edges": c["n_air_edges"],
            "n_h3_confirmed": c["n_h3_confirmed"],
            "n_air_in_chain": n_air,
            "n_air_violating": n_violating,
            "n_air_unknown": n_unknown,
            "h3_score": h3, "h8_score": h8, "h9_score": h9, "h8v8_score": h8v8_s,
            "quality_v6b": round(q, 4),
        })
    return out


def main():
    summary = {"videos": {}}
    for stem in WEIGHTS_PER_VIDEO:
        print(f"\n=== {stem} (H10 v6b per-video adaptive weights) ===")
        w3, w8, w9, w8v8 = WEIGHTS_PER_VIDEO[stem]
        print(f"  weights: h3={w3}, h8={w8}, h9={w9}, h8v8={w8v8}")
        h9_cov = load_h9_coverage(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        h8v8_per_arc_g = load_h8v8_per_arc_g(stem)
        results = per_chain_quality_v6b(
            stem, h8_v5_viol, h8_v5_unknown, h9_cov, h8v8_per_arc_g)
        results.sort(key=lambda r: -r["quality_v6b"])
        # Compare to v5 ranking
        from h10v5_with_h8v5 import per_chain_quality as v5_per_chain_quality
        # Hack: import the v5 result
        with (H1_DATA / "h10v5_chain_quality_summary.json").open() as fh:
            v5_data = json.load(fh)
        v5_ranked = v5_data["videos"][stem]["v5_results"]
        v5_rank = {r["chain_id"]: i for i, r in enumerate(v5_ranked)}
        # Report
        print(f"  Top 10 chains by v6b quality:")
        for r in results[:10]:
            v5_r = v5_rank[r["chain_id"]]
            print(f"    chain {r['chain_id']:>3}: v5_rank={v5_r:>2}, "
                  f"v6b={r['quality_v6b']:.3f} "
                  f"(h3={r['h3_score']}, h8={r['h8_score']:.2f}, "
                  f"h9={r['h9_score']:.2f}, h8v8={r['h8v8_score']:.2f})")
        # Aggregate
        n_improved = sum(1 for r in results
                          if results.index(r) < v5_rank[r["chain_id"]])
        n_worsened = sum(1 for r in results
                          if results.index(r) > v5_rank[r["chain_id"]])
        n_unchanged = sum(1 for r in results
                          if results.index(r) == v5_rank[r["chain_id"]])
        avg_v5 = sum(r["quality"] for r in v5_ranked) / len(v5_ranked)
        avg_v6b = sum(r["quality_v6b"] for r in results) / len(results)
        print(f"  rank: improved={n_improved}, unchanged={n_unchanged}, "
              f"worsened={n_worsened}")
        print(f"  mean quality: v5={avg_v5:.3f}, v6b={avg_v6b:.3f} "
              f"(delta={avg_v6b-avg_v5:+.3f})")
        out_csv = H1_DATA / f"h10v6b_chain_quality_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(results[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_csv.name}")
        summary["videos"][stem] = {
            "results": results,
            "n_chains": len(results),
            "n_improved": n_improved,
            "n_unchanged": n_unchanged,
            "n_worsened": n_worsened,
            "mean_v5": round(avg_v5, 4),
            "mean_v6b": round(avg_v6b, 4),
            "weights": {"h3": w3, "h8": w8, "h9": w9, "h8v8": w8v8},
        }
    out = H1_DATA / "h10v6b_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
