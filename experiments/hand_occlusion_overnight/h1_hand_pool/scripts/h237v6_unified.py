#!/usr/bin/env python3
"""H237 v6 - unified chain representation based on H7v2 chains
with H7v2 reclassification metadata + H10 v8 chain quality.

Differences from H237 v5:
- v5 used H7 chains (union-find with H2 BALLISTIC edges) +
  H10 v5 quality.
- v6 uses H7v2 chains (reclassified BALLISTIC edges as
  HAND_TRANSITION) + H10 v8 quality.
- v6 adds explicit `n_reclassified_edges` and
  `pct_reclassified` per chain (informative for downstream
  consumers wanting to distinguish "mostly hand-edge" vs
  "mostly ballistic" chains).

Output: data/h237v6_unified_chains_<stem>.csv and a JSON summary.
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


def load_h7v2_chains(stem: str) -> list[dict]:
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


def load_h7v2_admitted_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


def load_h10v8(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / f"h10v8_chain_quality_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = {
                "h10_v8_quality": float(r["quality_v8"]),
                "h10_v8_rank": -1,  # computed below
                "h3_score": r["h3_score"],
                "h8_score": float(r["h8_score"]),
                "h9_score": float(r["h9_score"]),
                "h8v8_score": float(r["h8v8_score"]),
                "n_hand_edges": int(r["n_hand_edges"]),
                "n_air_edges": int(r["n_air_edges"]),
                "n_h3_confirmed": int(r["n_h3_confirmed"]),
            }
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H237 v6) ===")
        chains = load_h7v2_chains(stem)
        edges = load_h7v2_admitted_edges(stem)
        h10v8 = load_h10v8(stem)

        # Compute h10v8 ranks
        sorted_h10v8 = sorted(h10v8.items(), key=lambda x: -x[1]["h10_v8_quality"])
        for rank, (cid, info) in enumerate(sorted_h10v8):
            info["h10_v8_rank"] = rank

        # Build chain -> edges map
        by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}
        chain_edges = defaultdict(list)
        for c in chains:
            for i in range(len(c["tids"]) - 1):
                a, b = c["tids"][i], c["tids"][i + 1]
                e = by_pair.get((a, b))
                if e:
                    chain_edges[c["chain_id"]].append(e)

        out_rows = []
        for c in chains:
            cid = c["chain_id"]
            ces = chain_edges.get(cid, [])
            n_reclassified = sum(1 for e in ces
                                 if e["edge_type"] == "RECLASSIFIED_HAND_TRANSITION")
            n_hand_total = sum(1 for e in ces if "HAND" in e["edge_type"])
            n_ballistic = sum(1 for e in ces if e["edge_type"] == "BALLISTIC")
            n_ambiguous = sum(1 for e in ces
                              if e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION")
            pct_reclassified = (100 * n_reclassified / n_hand_total
                                 if n_hand_total > 0 else 0.0)
            q = h10v8.get(cid, {})
            out_rows.append({
                "chain_id": cid,
                "n_tracklets": c["n_tracklets"],
                "first_frame": c["first_frame"],
                "last_frame": c["last_frame"],
                "tids": ",".join(str(t) for t in c["tids"]),
                "n_hand_edges": n_hand_total,
                "n_reclassified_edges": n_reclassified,
                "n_ballistic_edges": n_ballistic,
                "n_ambiguous_hand_edges": n_ambiguous,
                "pct_reclassified": f"{pct_reclassified:.1f}",
                "n_h3_confirmed": q.get("n_h3_confirmed", 0),
                "h3_score": q.get("h3_score", ""),
                "h8_score": f"{q.get('h8_score', 0):.3f}",
                "h9_score": f"{q.get('h9_score', 0):.3f}",
                "h8v8_score": f"{q.get('h8v8_score', 0):.3f}",
                "h10_v8_quality": f"{q.get('h10_v8_quality', 0):.4f}",
                "h10_v8_rank": q.get("h10_v8_rank", -1),
            })

        # Sort by chain_id
        out_rows.sort(key=lambda r: r["chain_id"])

        # Write CSV
        out_path = H1_DATA / f"h237v6_unified_chains_{stem}.csv"
        with out_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        print(f"  wrote: {out_path.name}")

        # Compute summary stats
        all_chains = out_rows
        multi_chains = [c for c in all_chains if c["n_tracklets"] > 1]
        n_pure_ballistic = sum(1 for c in all_chains
                                if c["n_ballistic_edges"] > 0
                                and c["n_hand_edges"] == 0)
        n_pure_reclassified = sum(1 for c in all_chains
                                   if c["n_reclassified_edges"] > 0
                                   and c["n_ballistic_edges"] == 0
                                   and c["n_ambiguous_hand_edges"] == 0
                                   and c["n_hand_edges"] - c["n_reclassified_edges"] == 0)
        print(f"  total chains: {len(all_chains)}, multi: {len(multi_chains)}")
        print(f"  pure-ballistic chains: {n_pure_ballistic}")
        print(f"  pure-reclassified chains: {n_pure_reclassified}")
        print(f"  top 5 chains by h10 v8 quality:")
        top5 = sorted(multi_chains, key=lambda r: -float(r["h10_v8_quality"]))[:5]
        for r in top5:
            print(f"    chain {r['chain_id']} (n_tids={r['n_tracklets']}, "
                  f"n_hand={r['n_hand_edges']}, n_reclass={r['n_reclassified_edges']}, "
                  f"n_ballistic={r['n_ballistic_edges']}): q={r['h10_v8_quality']}")

        summary["videos"][stem] = {
            "n_chains": len(all_chains),
            "n_multi_chains": len(multi_chains),
            "n_pure_ballistic_chains": n_pure_ballistic,
            "n_pure_reclassified_chains": n_pure_reclassified,
            "top5_by_h10v8": [
                {"chain_id": r["chain_id"], "n_tracklets": r["n_tracklets"],
                 "h10_v8_quality": float(r["h10_v8_quality"])}
                for r in top5
            ],
        }

    out_json = H1_DATA / "h237v6_unified_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
