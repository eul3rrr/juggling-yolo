#!/usr/bin/env python3
"""H10 v7 - length-dependent weight for h8v8.

H10 v6b uses per-video adaptive weights. This requires
knowing which video is being analyzed. H10 v7 generalizes
this to a single formula that works for both videos:

  w8v8 = min(0.30, mean(n_tracklet_pts) / 200)

Rationale: long tracklets have more arcs and the parabolic
fit is more reliable, so h8v8 should be weighted more.
Short tracklets have fewer arcs and the parabolic fit is
unreliable, so h8v8 should be weighted less.

Identical: median tracklet ~5 frames -> w8v8 ~ 0.025
  (close to 0, similar to v5 behavior)
YouTube: median tracklet ~70 frames -> w8v8 ~ 0.30
  (close to v6b YouTube weight)

This is a one-formula-fits-all approach. Should preserve
v5 behavior on identical and v6b behavior on YouTube.
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

# Length-dependent weight
W8V8_MAX = 0.30
LENGTH_DIVISOR = 200  # frames

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


def load_tracklet_lengths(stem: str) -> dict:
    """Returns {tid: n_pts} for each tracklet."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        seen = set()
        for r in csv.DictReader(fh):
            tid = int(r["track_id"])
            if tid in seen:
                continue
            seen.add(tid)
            # Count points
            out[tid] = sum(1 for r2 in csv.DictReader(open(path))
                            if int(r2["track_id"]) == tid)
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


def per_chain_quality_v7(stem: str, h8_violations: set, h8_unknowns: set,
                          h9_cov: dict, h8v8_per_arc_g: dict,
                          tracklet_lengths: dict) -> list[dict]:
    """Compute per-chain quality using v7 length-dependent weight."""
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
        tids = c["tids"]
        arc_scores = [compute_arc_g_score(h8v8_per_arc_g.get(tid, []))
                       for tid in tids]
        h8v8_s = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
        # Length-dependent weight
        lengths = [tracklet_lengths.get(tid, 0) for tid in tids]
        mean_length = sum(lengths) / len(lengths) if lengths else 0
        w8v8 = min(W8V8_MAX, mean_length / LENGTH_DIVISOR)
        # Quality v7 (renormalized to sum to 1)
        w3, w8, w9 = 0.30, 0.30, 0.40
        if h3 is None:
            s = w8 + w9 + w8v8
            w8_ = w8 / s
            w9_ = w9 / s
            w8v8_ = w8v8 / s
            q = w8_ * h8 + w9_ * h9 + w8v8_ * h8v8_s
        else:
            s = w3 + w8 + w9 + w8v8
            w3_ = w3 / s
            w8_ = w8 / s
            w9_ = w9 / s
            w8v8_ = w8v8 / s
            q = w3_ * h3 + w8_ * h8 + w9_ * h9 + w8v8_ * h8v8_s
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
            "mean_tracklet_length": round(mean_length, 1),
            "w8v8_length_dep": round(w8v8, 4),
            "quality_v7": round(q, 4),
        })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H10 v7 length-dependent weight) ===")
        h9_cov = load_h9_coverage(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        h8v8_per_arc_g = load_h8v8_per_arc_g(stem)
        tracklet_lengths = load_tracklet_lengths(stem)
        # Stats
        all_lengths = list(tracklet_lengths.values())
        print(f"  Tracklet length stats: n={len(all_lengths)}, "
              f"min={min(all_lengths)}, max={max(all_lengths)}, "
              f"mean={sum(all_lengths)/len(all_lengths):.1f}, "
              f"median={statistics.median(all_lengths)}")
        results = per_chain_quality_v7(
            stem, h8_v5_viol, h8_v5_unknown, h9_cov, h8v8_per_arc_g,
            tracklet_lengths)
        results.sort(key=lambda r: -r["quality_v7"])
        # Compare to v5 ranking
        with (H1_DATA / "h10v5_chain_quality_summary.json").open() as fh:
            v5_data = json.load(fh)
        v5_ranked = v5_data["videos"][stem]["v5_results"]
        v5_rank = {r["chain_id"]: i for i, r in enumerate(v5_ranked)}
        # Report
        print(f"  Top 10 chains by v7 quality:")
        for r in results[:10]:
            v5_r = v5_rank[r["chain_id"]]
            print(f"    chain {r['chain_id']:>3}: v5_rank={v5_r:>2}, "
                  f"v7={r['quality_v7']:.3f} "
                  f"(w8v8={r['w8v8_length_dep']:.3f} from "
                  f"len={r['mean_tracklet_length']:.0f})")
        # Aggregate
        n_improved = sum(1 for r in results
                          if results.index(r) < v5_rank[r["chain_id"]])
        n_worsened = sum(1 for r in results
                          if results.index(r) > v5_rank[r["chain_id"]])
        n_unchanged = sum(1 for r in results
                          if results.index(r) == v5_rank[r["chain_id"]])
        avg_v5 = sum(r["quality"] for r in v5_ranked) / len(v5_ranked)
        avg_v7 = sum(r["quality_v7"] for r in results) / len(results)
        print(f"  rank: improved={n_improved}, unchanged={n_unchanged}, "
              f"worsened={n_worsened}")
        print(f"  mean quality: v5={avg_v5:.3f}, v7={avg_v7:.3f} "
              f"(delta={avg_v7-avg_v5:+.3f})")
        out_csv = H1_DATA / f"h10v7_chain_quality_{stem}.csv"
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
            "mean_v7": round(avg_v7, 4),
            "mean_tracklet_length": round(sum(all_lengths)/len(all_lengths), 1),
        }
    out = H1_DATA / "h10v7_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
