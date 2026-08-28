#!/usr/bin/env python3
"""H237 v5 - enrich the H2+H3+H7 unified chains with H10 v5 quality.

For each chain in the H237 unified representation, add:
- h10_v3_quality (from h10_chain_quality_summary.json)
- h10_v5_quality (from h10v5_chain_quality_summary.json)
- h10_v3_rank
- h10_v5_rank
- h10_quality_delta (v5 - v3)

Output: data/h237v5_unified_chains_<stem>.csv and a JSON summary.

This makes the v5 quality directly available in the chain
representation for downstream consumers.
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


def load_h10_v3(stem: str) -> dict[str, dict]:
    with (H1_DATA / "h10_chain_quality_summary.json").open() as fh:
        s = json.load(fh)
    return {r["chain_id"]: r for r in s["videos"][stem]["chain_results"]}


def load_h10_v5(stem: str) -> dict[str, dict]:
    with (H1_DATA / "h10v5_chain_quality_summary.json").open() as fh:
        s = json.load(fh)
    # v5 has v3_results AND v5_results inside the videos dict
    return {r["chain_id"]: r for r in s["videos"][stem]["v5_results"]}


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        h10_v3 = load_h10_v3(stem)
        h10_v5 = load_h10_v5(stem)

        # Compute ranks for v3 and v5
        v3_sorted = sorted(h10_v3.values(), key=lambda r: -r["quality"])
        v3_rank = {r["chain_id"]: i for i, r in enumerate(v3_sorted)}
        v5_sorted = sorted(h10_v5.values(), key=lambda r: -r["quality"])
        v5_rank = {r["chain_id"]: i for i, r in enumerate(v5_sorted)}

        # Read existing h237 chains and enrich
        in_path = H1_DATA / f"h237_unified_chains_{stem}.csv"
        out_path = H1_DATA / f"h237v5_unified_chains_{stem}.csv"
        with in_path.open() as fh:
            reader = csv.DictReader(fh)
            base_fields = list(reader.fieldnames or [])
            fieldnames = base_fields + [
                "h10_v3_quality", "h10_v5_quality", "h10_v3_rank", "h10_v5_rank",
                "h10_quality_delta",
            ]
            out_rows = []
            for r in reader:
                cid = r["chain_id"]
                v3 = h10_v3.get(cid, {})
                v5 = h10_v5.get(cid, {})
                v3_q = v3.get("quality", 0.0)
                v5_q = v5.get("quality", 0.0)
                out_rows.append({
                    **r,
                    "h10_v3_quality": f"{v3_q:.4f}",
                    "h10_v5_quality": f"{v5_q:.4f}",
                    "h10_v3_rank": v3_rank.get(cid, -1),
                    "h10_v5_rank": v5_rank.get(cid, -1),
                    "h10_quality_delta": f"{v5_q - v3_q:+.4f}",
                })
        with out_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"  wrote: {out_path}")
        # Show top 5 and bottom 3 by v5 quality
        print(f"  Top 5 chains by v5 quality:")
        for r in v5_sorted[:5]:
            cid = r["chain_id"]
            n_tids = int(next(rr["n_tracklets"] for rr in out_rows if rr["chain_id"] == cid))
            print(f"    chain {cid} (n_tids={n_tids}): v3_q={h10_v3[cid]['quality']:.3f} -> v5_q={r['quality']:.3f} (rank {v5_rank[cid]})")
        print(f"  Bottom 3 chains by v5 quality:")
        for r in v5_sorted[-3:]:
            cid = r["chain_id"]
            print(f"    chain {cid}: v3_q={h10_v3[cid]['quality']:.3f} -> v5_q={r['quality']:.3f} (rank {v5_rank[cid]})")

        summary["videos"][stem] = {
            "n_chains": len(out_rows),
            "v3_top3": [(r["chain_id"], r["quality"]) for r in v3_sorted[:3]],
            "v5_top3": [(r["chain_id"], r["quality"]) for r in v5_sorted[:3]],
        }

    out_json = H1_DATA / "h237v5_unified_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
