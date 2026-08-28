#!/usr/bin/env python3
"""H10 v5 - H10 chain quality using H8 v5 (parabolic fit) instead of H8 v3.

Compares H10 (v3-based) to H10 v5 (v5-based) on each chain.
Reports:
  - per-chain delta quality
  - chain rank changes (which chains moved up/down)
  - which previously-OK chains become VIOLATING (new catches)
  - which previously-VIOLATING chains become OK (new false negatives)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

WEIGHTS = (0.30, 0.30, 0.40)


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


def load_h8_violations_v3(stem: str) -> set:
    with (H1_DATA / "h8_v3_edge_physics_summary.json").open() as fh:
        s = json.load(fh)
    violations = set()
    for r in s["videos"][stem]["results"]:
        if r["edge_type"] == "BALLISTIC" and r["physics_status"] == "VIOLATING":
            violations.add((r["from_tid"], r["to_tid"]))
    return violations


def load_h8_violations_v5(stem: str):
    """v5 has 3 statuses: OK, VIOLATING, INSUFFICIENT_DATA.
    For H10 scoring, treat INSUFFICIENT_DATA as 'unknown' (not
    violating). The H8 score will be 0.5 for unknown edges.
    Return both the violation set and the unknown set.
    """
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


def compute_quality(h3, h8, h9, weights=WEIGHTS):
    w3, w8, w9 = weights
    if h3 is None:
        s = w8 + w9
        w8 = w8 + w3 * w8 / s
        w9 = w9 + w3 * w9 / s
        return w8 * h8 + w9 * h9
    return w3 * h3 + w8 * h8 + w9 * h9


def per_chain_quality(stem: str, h8_violations: set, h8_unknowns: set,
                      h9_cov: dict) -> list[dict]:
    """Compute per-chain quality using h8 v3 OR v5 (with graduated scoring)."""
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
            # Graduated scoring: OK=1, VIOLATING=0, UNKNOWN=0.5
            h8 = (n_air - n_violating - 0.5 * n_unknown) / n_air
        else:
            h8 = 1.0
        h9 = h9_cov.get(c["chain_id"], {}).get("coverage", 0.0)
        q = compute_quality(h3, h8, h9)
        out.append({
            "chain_id": c["chain_id"],
            "n_tracklets": c["n_tracklets"],
            "n_hand_edges": c["n_hand_edges"],
            "n_air_edges": c["n_air_edges"],
            "n_h3_confirmed": c["n_h3_confirmed"],
            "n_air_in_chain": n_air,
            "n_air_violating": n_violating,
            "n_air_unknown": n_unknown,
            "h3_score": h3, "h8_score": h8, "h9_score": h9,
            "quality": q,
        })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        h9_cov = load_h9_coverage(stem)

        # v3-based
        h8_v3_viol = load_h8_violations_v3(stem)
        h8_v3_unknown = set()  # v3 has no unknown
        v3_results = per_chain_quality(stem, h8_v3_viol, h8_v3_unknown, h9_cov)
        v3_results.sort(key=lambda r: -r["quality"])

        # v5-based
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        v5_results = per_chain_quality(stem, h8_v5_viol, h8_v5_unknown, h9_cov)
        v5_results.sort(key=lambda r: -r["quality"])

        # Compare
        v3_by_id = {r["chain_id"]: (i, r["quality"]) for i, r in enumerate(v3_results)}
        v5_by_id = {r["chain_id"]: (i, r["quality"]) for i, r in enumerate(v5_results)}
        deltas = []
        for cid in v3_by_id:
            if cid in v5_by_id:
                v3_rank, v3_q = v3_by_id[cid]
                v5_rank, v5_q = v5_by_id[cid]
                deltas.append({
                    "chain_id": cid,
                    "v3_quality": v3_q,
                    "v5_quality": v5_q,
                    "v3_rank": v3_rank,
                    "v5_rank": v5_rank,
                    "rank_change": v3_rank - v5_rank,  # positive = improved
                })
        deltas.sort(key=lambda d: -d["rank_change"])
        print(f"  Top 5 chains that IMPROVED rank (v3 -> v5):")
        for d in deltas[:5]:
            print(f"    chain {d['chain_id']}: rank {d['v3_rank']}->{d['v5_rank']}, "
                  f"quality {d['v3_quality']:.3f}->{d['v5_quality']:.3f}")
        print(f"  Top 5 chains that WORSENED rank (v3 -> v5):")
        for d in deltas[-5:]:
            print(f"    chain {d['chain_id']}: rank {d['v3_rank']}->{d['v5_rank']}, "
                  f"quality {d['v3_quality']:.3f}->{d['v5_quality']:.3f}")
        # Aggregate stats
        n_improved = sum(1 for d in deltas if d["rank_change"] > 0)
        n_worsened = sum(1 for d in deltas if d["rank_change"] < 0)
        n_unchanged = sum(1 for d in deltas if d["rank_change"] == 0)
        avg_v3 = sum(d["v3_quality"] for d in deltas) / len(deltas)
        avg_v5 = sum(d["v5_quality"] for d in deltas) / len(deltas)
        print(f"  rank: improved={n_improved}, unchanged={n_unchanged}, worsened={n_worsened}")
        print(f"  mean quality: v3={avg_v3:.3f}, v5={avg_v5:.3f} (delta={avg_v5-avg_v3:+.3f})")

        summary["videos"][stem] = {
            "v3_results": v3_results,
            "v5_results": v5_results,
            "deltas": deltas,
        }

    out_path = H1_DATA / "h10v5_chain_quality_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
