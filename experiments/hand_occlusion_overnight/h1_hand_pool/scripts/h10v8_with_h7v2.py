#!/usr/bin/env python3
"""H10 v8 — H7v2 (reclassified) chains + H10 v6b (per-video adaptive weights).

The H7v2 chain structure has reclassified BALLISTIC edges as HAND_TRANSITION
when both endpoints pass through a hand region with a catch/throw signature.
This means the per-chain n_air_edges and per-edge H8 violations are
different. We re-run H10 v6b scoring on the H7v2 chains to see if the
YouTube over-counting is fixed at the source.

Hypothesis: H7v2 + H10 v6b should give:
  * identical: minimal change (H7v2 reclassifies only 13 of 37 edges,
    and most chains have similar structure)
  * YouTube: substantial improvement. The chains that were over-counted
    (chains 0, 3, 7, 8, 9, 10) should now have n_air_edges = 0, so
    h8_score = 1.0 (not 0.0). This removes the h8 penalty and
    fixes the over-counting artifact.
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


def load_h7v2_chains(stem: str) -> list[dict]:
    """Load H7v2 chains CSV."""
    out = []
    with (H1_DATA / f"h7v2_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h7v2_edges(stem: str) -> list[dict]:
    """Load H7v2 admitted edges."""
    out = []
    with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


def load_h3_confirmed(stem: str) -> set[tuple]:
    """Load H3 confirmed hand-link times. v3 was (from_tid, to_tid) but
    we also have h3_confirmed: bool per hand_link. Use h3 confirmed
    to set the chain's n_h3_confirmed.

    Simpler approach: load the unified chains CSV's h10_v5_quality,
    but recompute from scratch. For h3, we need to know which hand-links
    are h3_confirmed. The unified chains CSV doesn't expose this directly.
    Use h237_unified_chains_<stem>.csv to get n_h3_confirmed and chain edges.
    """
    out = {}
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            cid = int(r["chain_id"])
            out[cid] = {
                "n_h3_confirmed": int(r["n_h3_confirmed"]),
                "n_hand_edges": int(r["n_hand_edges"]),
                "n_air_edges": int(r["n_air_edges"]),
            }
    return out


def load_h3_confirmed_links(stem: str) -> set:
    """Load the actual h3-confirmed (from_tid, to_tid) pairs."""
    with (H1_DATA / f"hand_links_v4_v4d_throw7_full_with_h3.csv").open() as fh:
        first_line = fh.readline().strip()
    print(f"  hand_links_v4_v4d_throw7_full_with_h3.csv header: {first_line[:100]}")
    if "video" in first_line and "from_tid" in first_line:
        with (H1_DATA / f"hand_links_v4_v4d_throw7_full_with_h3.csv").open() as fh:
            rdr = csv.DictReader(fh)
            confirmed = set()
            for r in rdr:
                if r["stem"] == stem and r.get("h3_confirmed", "False") == "True":
                    confirmed.add((int(r["from_tid"]), int(r["to_tid"])))
            return confirmed
    return set()


def load_h8_violations_v5(stem: str):
    """v5 has 3 statuses: OK, VIOLATING, INSUFFICIENT_DATA."""
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
    """Returns {tid: [g1, g2, ...]} for each tracklet with arcs (from
    the h8_v8_extrema_arcs_<stem>.csv per-edge output)."""
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
    """Score a tracklet's per-arc gravity consistency. Mean of
    (1 if |g-expected|<=tol else 0). No arcs → 0.5 (unknown)."""
    if not gs:
        return 0.5
    n_clean = sum(1 for g in gs if abs(g - expected_g) <= tolerance)
    return n_clean / len(gs)


def load_h9_coverage(stem: str) -> dict:
    """Load H9 chain coverage.

    H9 was computed on H7 v1 chains, not H7v2. We need to recompute
    H9 coverage for H7v2 chains. For now, use H9's existing chain
    coverage (treating H7v2 chain_id by matching first_frame / last_frame).
    """
    with (H1_DATA / "h9_object_permanence_summary.json").open() as fh:
        s = json.load(fh)
    out = {}
    for cs in s["videos"][stem]["chain_stats"]:
        cid = int(cs["chain_id"])
        out[cid] = cs
    return out


def compute_h9_for_h7v2_chains(stem: str) -> dict:
    """Recompute H9 chain coverage for H7v2 chains.

    H9 measures chain coverage = (observed frames) / (span frames).
    For H7v2 chains, we have different chain_id assignments (because
    the chain structure is different). We can use the H7v2 chain's
    tracklets to compute the same coverage metric.

    For simplicity, we use the H7v2 chain's tids to compute:
      - observed_frames = sum of n_pts per tracklet
      - span_frames = last_frame - first_frame
      - coverage = observed / span
    """
    chains = load_h7v2_chains(stem)
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
            "first_frame": c["first_frame"],
            "last_frame": c["last_frame"],
            "n_gaps": len(gaps),
            "total_gap_frames": sum(gaps),
            "observed_frames": observed,
            "span_frames": span,
            "coverage": coverage,
        }
    return out


def compute_quality(h3, h8, h9, weights):
    w3, w8, w9, w8v8 = weights["h3"], weights["h8"], weights["h9"], weights["h8v8"]
    # We don't have h8v8 contribution here; use 4-dim version with h8v8=0.5 default
    if h3 is None:
        s = w8 + w9 + w8v8
        w8 = w8 + w3 * w8 / s
        w9 = w9 + w3 * w9 / s
        w8v8 = w8v8 + w3 * w8v8 / s
    return w3 * (h3 or 0) + w8 * h8 + w9 * h9 + w8v8 * 0.5  # h8v8 placeholder


def main():
    summary = {"videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        weights = WEIGHTS_PER_VIDEO[stem]
        h7v2_chains = load_h7v2_chains(stem)
        h7v2_edges = load_h7v2_edges(stem)
        h3_confirmed_links = load_h3_confirmed_links(stem)
        h8_v5_viol, h8_v5_unknown = load_h8_violations_v5(stem)
        h8v8_stats = load_h8v8_per_arc_g(stem)
        h9_cov = compute_h9_for_h7v2_chains(stem)

        print(f"  h7v2 chains: {len(h7v2_chains)}")
        print(f"  h7v2 edges: {len(h7v2_edges)}")
        print(f"  h3 confirmed: {len(h3_confirmed_links)}")

        # Build chain -> edges map
        chain_edges = defaultdict(list)
        for c in h7v2_chains:
            tids = c["tids"]
            for i in range(len(tids) - 1):
                a, b = tids[i], tids[i + 1]
                for e in h7v2_edges:
                    if e["from_tid"] == a and e["to_tid"] == b:
                        chain_edges[c["chain_id"]].append(e)
                        break

        # Compute per-chain quality
        results = []
        for c in h7v2_chains:
            cid = c["chain_id"]
            tids = c["tids"]
            edges = chain_edges[cid]
            # Count hand vs air edges
            n_hand = sum(1 for e in edges if "HAND" in e["edge_type"])
            n_air = sum(1 for e in edges if e["edge_type"] == "BALLISTIC")
            n_h3 = sum(1 for e in edges
                       if (e["from_tid"], e["to_tid"]) in h3_confirmed_links)
            # h3 score
            if n_hand > 0:
                h3 = n_h3 / n_hand
            else:
                h3 = None
            # h8 score (graduated: VIOLATING=0, UNKNOWN=0.5, OK=1)
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
            # h9 score
            h9 = h9_cov.get(cid, {}).get("coverage", 0.0)
            # h8v8 score: per-tracklet mean of arc-g score
            if tids:
                arc_scores = [compute_arc_g_score(h8v8_stats.get(t, []))
                              for t in tids]
                h8v8 = sum(arc_scores) / len(arc_scores) if arc_scores else 0.5
            else:
                h8v8 = 0.5
            # Composite quality (v6b weights + h8v8)
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
                "n_air_edges": n_air,
                "n_h3_confirmed": n_h3,
                "n_air_in_chain": n_air,
                "n_air_violating": n_viol,
                "n_air_unknown": n_unk,
                "h3_score": h3,
                "h8_score": h8,
                "h9_score": h9,
                "h8v8_score": h8v8,
                "quality_v8": q,
            })

        results.sort(key=lambda r: -r["quality_v8"])
        print(f"  Top 3 chains by v8 quality:")
        for r in results[:3]:
            print(f"    chain {r['chain_id']}: n_tids={r['n_tracklets']}, "
                  f"n_hand={r['n_hand_edges']}, n_air={r['n_air_edges']}, "
                  f"h8={r['h8_score']:.2f}, h9={r['h9_score']:.2f}, "
                  f"h8v8={r['h8v8_score']:.2f}, q={r['quality_v8']:.3f}")

        mean_v8 = sum(r["quality_v8"] for r in results) / len(results)
        n_air_zero = sum(1 for r in results if r["n_air_edges"] == 0)
        n_h8_one = sum(1 for r in results if r["h8_score"] == 1.0)
        print(f"  mean v8: {mean_v8:.4f}")
        print(f"  chains with n_air=0: {n_air_zero}/{len(results)}")
        print(f"  chains with h8=1.0: {n_h8_one}/{len(results)}")

        summary["videos"][stem] = {
            "n_chains": len(results),
            "results": results,
            "mean_v8": mean_v8,
            "weights": weights,
        }

    out_path = H1_DATA / "h10v8_chain_quality_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")

    # Also write per-video CSVs
    for stem in STEMS:
        v = summary["videos"][stem]
        with (H1_DATA / f"h10v8_chain_quality_{stem}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "chain_id", "n_tracklets", "n_hand_edges", "n_air_edges",
                "n_h3_confirmed", "n_air_in_chain", "n_air_violating",
                "n_air_unknown", "h3_score", "h8_score", "h9_score",
                "h8v8_score", "quality_v8",
            ])
            w.writeheader()
            for r in v["results"]:
                w.writerow({k: r[k] for k in w.fieldnames})


if __name__ == "__main__":
    main()
