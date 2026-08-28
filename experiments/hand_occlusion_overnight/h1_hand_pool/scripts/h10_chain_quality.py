#!/usr/bin/env python3
"""H10 - Per-chain quality score combining H3, H8, H9.

Hypothesis: a chain's "physical-ball identity confidence" can be measured
by combining multiple signals from prior experiments:
  - H3: fraction of hand edges corroborated by a stationary-cluster
    (held-ball evidence); high = "this hand-edge has visible support"
  - H8: fraction of air edges passing the y-velocity discontinuity
    check; high = "this chain doesn't contain identity switches"
  - H9: chain coverage (observed_frames / total_span); high =
    "this chain is well-observed, not mostly gaps"

Composite quality (declared before reading outcomes):
  quality = 0.30 * h3 + 0.30 * h8 + 0.40 * h9
(Hand and air edges are the two ways chains extend; H3 and H8
constrain those edges. H9 measures observation density, which is
the most direct chain-quality proxy. Weights are not tuned to
labels - they are a reasonable decomposition.)

For chains with no hand edges, h3 = None -> redistributed weight
to (h8, h9) with the same 0.30/0.40 -> 0.43/0.57 split.
For chains with no air edges, h8 = 1.0 (no violations possible).

Report:
  - per-chain quality, sorted descending
  - distribution histogram (high/mid/low)
  - top-3 and bottom-3 chains per video
  - sensitivity grid: vary weights {h3, h8, h9} across a small grid
    and confirm the ranking is stable.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_REPORTS = H1_DIR / "reports"
H1_CS = H1_DIR / "contact_sheets_h10"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


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
    """Returns the list of edges (from_tid, to_tid, edge_type)."""
    edges = []
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            edges.append({
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "edge_type": r["edge_type"],
            })
    return edges


def load_h8_violations(stem: str) -> set:
    """Return set of (from_tid, to_tid) for BALLISTIC edges flagged VIOLATING.

    Hand edges are EXCLUDED (held-then-released naturally has vy discontinuity).
    """
    with (H1_DATA / "h8_v3_edge_physics_summary.json").open() as fh:
        s = json.load(fh)
    violations = set()
    for r in s["videos"][stem]["results"]:
        if (r["edge_type"] == "BALLISTIC"
                and r["physics_status"] == "VIOLATING"):
            violations.add((r["from_tid"], r["to_tid"]))
    return violations


def load_h9_coverage(stem: str) -> dict:
    """Return {chain_id_str: coverage_dict}."""
    with (H1_DATA / "h9_object_permanence_summary.json").open() as fh:
        s = json.load(fh)
    out = {}
    for cs in s["videos"][stem]["chain_stats"]:
        out[cs["chain_id"]] = cs
    return out


def chain_air_edges(chain: dict, all_edges: list[dict]) -> list[tuple]:
    """Return list of (from_tid, to_tid) BALLISTIC edges belonging to this chain.

    A chain is a sequence of tids; an edge (t_i, t_{i+1}) belongs to the chain
    iff both endpoints are in chain['tids'] and the edge is in all_edges.
    """
    tids = chain["tids"]
    tids_set = set(tids)
    chain_edges = []
    # chain edges are consecutive pairs in the chain's tids list
    for i in range(len(tids) - 1):
        a, b = tids[i], tids[i + 1]
        for e in all_edges:
            if e["from_tid"] == a and e["to_tid"] == b:
                chain_edges.append((a, b, e["edge_type"]))
                break
    return chain_edges


def compute_quality(
    h3_score: float | None,
    h8_score: float,
    h9_score: float,
    weights: tuple[float, float, float] = (0.30, 0.30, 0.40),
) -> float:
    """Composite quality with declared weights, in [0, 1].

    If h3 is None (chain has no hand edges), redistribute the
    h3 weight to (h8, h9) in proportion to their original
    weights so the result still sums to 1.0 and lies in [0, 1].
    """
    w3, w8, w9 = weights
    if h3_score is None:
        s = w8 + w9
        w8 = w8 + w3 * w8 / s
        w9 = w9 + w3 * w9 / s
        return w8 * h8_score + w9 * h9_score
    return w3 * h3_score + w8 * h8_score + w9 * h9_score


def per_video(stem: str, weights: tuple[float, float, float]) -> dict:
    chains = load_h237_chains(stem)
    edges = load_h237_edges(stem)
    h8_violations = load_h8_violations(stem)
    h9_cov = load_h9_coverage(stem)
    results = []
    for c in chains:
        # H3: fraction of hand edges with H3 confirmation
        h3 = (c["n_h3_confirmed"] / c["n_hand_edges"]
              if c["n_hand_edges"] > 0 else None)
        # H8: fraction of BALLISTIC edges in this chain that pass physics
        chain_edges = chain_air_edges(c, edges)
        n_air = sum(1 for _, _, et in chain_edges if et == "BALLISTIC")
        n_air_violating = sum(1 for a, b, et in chain_edges
                              if et == "BALLISTIC" and (a, b) in h8_violations)
        if n_air > 0:
            h8 = 1.0 - n_air_violating / n_air
        else:
            h8 = 1.0  # no air edges, no possible violations
        # H9: chain coverage from h9 dict; chain_id is a string in h9
        h9 = h9_cov.get(c["chain_id"], {})
        h9_score = float(h9.get("coverage", 0.0))
        quality = compute_quality(h3, h8, h9_score, weights)
        results.append({
            "chain_id": c["chain_id"],
            "n_tracklets": c["n_tracklets"],
            "n_hand_edges": c["n_hand_edges"],
            "n_air_edges": c["n_air_edges"],
            "n_h3_confirmed": c["n_h3_confirmed"],
            "n_air_in_chain": n_air,
            "n_air_violating": n_air_violating,
            "h3_score": h3,
            "h8_score": h8,
            "h9_score": h9_score,
            "n_observed_frames": h9.get("n_observed_frames", 0),
            "total_span": h9.get("total_span", 0),
            "n_gaps": h9.get("n_gaps", 0),
            "quality": quality,
        })
    results.sort(key=lambda r: -r["quality"])
    n_high = sum(1 for r in results if r["quality"] > 0.7)
    n_mid = sum(1 for r in results if 0.3 <= r["quality"] <= 0.7)
    n_low = sum(1 for r in results if r["quality"] < 0.3)
    return {
        "video_key": STEMS[stem],
        "weights": list(weights),
        "n_chains": len(chains),
        "n_high": n_high, "n_mid": n_mid, "n_low": n_low,
        "chain_results": results,
    }


def sensitivity_grid(stem: str):
    """3x3 weight grid: w3, w8, w9 each in {0.2, 0.3, 0.4}. Sum must = 1.

    For each cell, rank chains by quality. Then for each chain
    measure rank-stability across cells (std of rank / N_chains).
    """
    grid = []
    grid_results = {}
    for w3 in (0.20, 0.30, 0.40):
        for w8 in (0.20, 0.30, 0.40):
            w9 = round(1.0 - w3 - w8, 2)
            if w9 <= 0 or w9 > 0.6:
                continue
            weights = (w3, w8, w9)
            r = per_video(stem, weights)
            grid.append(weights)
            grid_results[weights] = r["chain_results"]
    # Per-chain rank stability
    n_chains = len(grid_results[grid[0]])
    stability = []
    for i, c in enumerate(grid_results[grid[0]]):
        cid = c["chain_id"]
        ranks = []
        for w in grid:
            r = grid_results[w]
            # Find this chain in the sorted (by quality) list
            for rank, rc in enumerate(r):
                if rc["chain_id"] == cid:
                    ranks.append(rank)
                    break
        if ranks:
            mean_r = sum(ranks) / len(ranks)
            std_r = (sum((r - mean_r) ** 2 for r in ranks) / len(ranks)) ** 0.5
        else:
            mean_r, std_r = -1, 0
        stability.append({
            "chain_id": cid,
            "mean_rank": mean_r,
            "std_rank": std_r,
            "min_rank": min(ranks) if ranks else -1,
            "max_rank": max(ranks) if ranks else -1,
        })
    return grid, grid_results, stability


def main():
    summary = {"videos": {}}
    sensitivity = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        r = per_video(stem, (0.30, 0.30, 0.40))
        print(f"  n_chains: {r['n_chains']}")
        print(f"  n_high (>0.7): {r['n_high']}, n_mid (0.3-0.7): {r['n_mid']}, n_low (<0.3): {r['n_low']}")
        print(f"  top 5 chains by quality:")
        for cr in r["chain_results"][:5]:
            h3s = f"{cr['h3_score']:.2f}" if cr["h3_score"] is not None else "n/a"
            print(f"    chain {cr['chain_id']}: n_tids={cr['n_tracklets']}, "
                  f"quality={cr['quality']:.3f}, h3={h3s}, h8={cr['h8_score']:.2f}, "
                  f"h9={cr['h9_score']:.2f}, "
                  f"h={cr['n_hand_edges']}h+{cr['n_air_edges']}a, "
                  f"air_violations={cr['n_air_violating']}")
        print(f"  bottom 3 chains by quality:")
        for cr in r["chain_results"][-3:]:
            h3s = f"{cr['h3_score']:.2f}" if cr["h3_score"] is not None else "n/a"
            print(f"    chain {cr['chain_id']}: n_tids={cr['n_tracklets']}, "
                  f"quality={cr['quality']:.3f}, h3={h3s}, h8={cr['h8_score']:.2f}, "
                  f"h9={cr['h9_score']:.2f}")
        summary["videos"][stem] = r

        # Sensitivity grid
        grid, grid_results, stability = sensitivity_grid(stem)
        print(f"  sensitivity grid: {len(grid)} cells")
        n_stable = sum(1 for s in stability if s["std_rank"] < 2.0)
        print(f"    chains with stable rank (std<2 across {len(grid)} cells): {n_stable}/{len(stability)}")
        # Print most unstable
        stability.sort(key=lambda s: -s["std_rank"])
        for s in stability[:3]:
            print(f"    most unstable: chain {s['chain_id']}: "
                  f"mean_rank={s['mean_rank']:.1f}, std={s['std_rank']:.1f}, "
                  f"min/max={s['min_rank']}/{s['max_rank']}")
        sensitivity["videos"][stem] = {
            "grid_cells": [list(w) for w in grid],
            "n_stable_chains": n_stable,
            "n_total_chains": len(stability),
            "stability": stability,
        }

    out1 = H1_DATA / "h10_chain_quality_summary.json"
    out1.write_text(json.dumps(summary, indent=2, default=str))
    out2 = H1_DATA / "h10_sensitivity_grid.json"
    out2.write_text(json.dumps(sensitivity, indent=2, default=str))
    print(f"\nSaved: {out1}")
    print(f"Saved: {out2}")


if __name__ == "__main__":
    main()
