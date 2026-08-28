#!/usr/bin/env python3
"""H34 — H22 + H26 combined chain set (h7v3plus3).

HYPOTHESIS:
  H22 produced h7v3veto (YouTube 20→21 veto) with +0.0034 chain
  quality improvement on YouTube.
  H26 produced h7v3plus2 (identical 7→10, 59→61 H24-KEPT edges)
  with +0.0061 chain quality improvement on identical.

  These two improvements are on different videos and don't
  conflict. Combining them should give the union of both
  improvements, producing the h7v3plus3 chain set as the new
  recommended operating point.

  Note: H22 was a "narrow scope PASS" because the YouTube
  improvement is small. H26 was a "PASS (incremental)" for
  identical. H34 is the final combination.

APPROACH (declared before reading outcomes):
  - Take h7v3pure chains as base (h7v2 + h15v2 = H7v2 + V-shape
    reclassification)
  - Add H22's 1 YouTube veto: replace existing 16→21 with 20→21
  - Add H26's 2 identical H24-KEPT edges: 7→10 (V_SHALLOW, L)
    and 59→61 (V_DEEP, R)
  - Run min-cost flow with the augmented edge set
  - Walk new chains
  - Compute H10 v10 chain quality (v6b per-video weights)
  - Compare to h7v3plus2 (H26) and h7v3veto (H22) baselines

EXPECTED:
  - identical: same as h7v3plus2 (no H22 change for identical)
    Mean q 0.8105
  - YouTube: same as h7v3veto (no H26 change for YouTube)
    Mean q 0.6852 → 0.6886 (per H22 v2)
  - h7v3plus3 should equal the union: identical n_chains=42,
    YouTube n_chains=16 (vs h7v3plus2's 15)
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

# H22 veto: replace 16→21 with 20→21 (YouTube only)
H22_VETO_REPLACE = {
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        "remove": (16, 21),
        "add": (20, 21, {
            "edge_type": "H22_RECLASSIFIED_HAND_TRANSITION",
            "metadata": "h22_vshape=V_DEEP_min_d=5.3",
            "cost": 1.0,
            "reclassify_reason": "",
            "v_reclassify_reason": "",
            "h22_reason": "veto: H20-KEPT min_d=5.3 overrides existing 16->21 (target start_dist=35.3)",
        }),
    },
}

# H26 added edges: 7→10 and 59→61 (identical only)
H26_ADD = {
    "identical_balls_trick_000_018": [
        (7, 10, {
            "edge_type": "H26_RECLASSIFIED_HAND_TRANSITION",
            "metadata": "h26_vshape=V_SHALLOW_h24=REAL_min_d=57.35",
            "reclassify_reason": "",
            "v_reclassify_reason": "",
            "h26_reason": "H24 visually-confirmed REAL H20-KEPT-not-in-h7v2 (R->L hand-off)",
            "which_hand": "left",
            "cost": 1.0,
        }),
        (59, 61, {
            "edge_type": "H26_RECLASSIFIED_HAND_TRANSITION",
            "metadata": "h26_vshape=V_DEEP_h24=REAL_min_d=18.94",
            "reclassify_reason": "",
            "v_reclassify_reason": "",
            "h26_reason": "H24 visually-confirmed REAL H20-KEPT-not-in-h7v2 (R->L hand-off, V_DEEP)",
            "which_hand": "right",
            "cost": 1.0,
        }),
    ],
}


def load_h7v3plus2_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus2_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


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


def build_h7v3plus3(stem: str) -> list[dict]:
    """Build h7v3plus3 edges by combining h7v3plus2 with H22 veto
    (YouTube only) and H26 additions (identical only)."""
    edges = load_h7v3plus2_edges(stem)
    # H22 veto: for YouTube, remove 16→21 and add 20→21
    if stem in H22_VETO_REPLACE:
        spec = H22_VETO_REPLACE[stem]
        # Remove the existing 16→21 edge if present
        rm_from, rm_to = spec["remove"]
        edges = [e for e in edges
                 if not (e["from_tid"] == rm_from and e["to_tid"] == rm_to)]
        # Add the H22 20→21 edge
        add_from, add_to, add_meta = spec["add"]
        edges.append({"from_tid": add_from, "to_tid": add_to, **add_meta})
    return edges


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        # Load h7v3plus2 edges and apply H22 veto where applicable
        edges = build_h7v3plus3(stem)

        # Save the h7v3plus3 edges
        out_csv = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            cols = ["from_tid", "to_tid", "edge_type", "metadata", "cost",
                    "reclassify_reason", "v_reclassify_reason", "h22_reason",
                    "h26_reason"]
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(edges)
        print(f"  wrote {out_csv.name} ({len(edges)} edges)")

        # Edge type counts
        from collections import Counter
        et_counts = Counter(e["edge_type"] for e in edges)

        summary["videos"][stem] = {
            "n_edges": len(edges),
            "edge_type_counts": dict(et_counts),
        }

    out_json = H1_DATA / "h34_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}")
    print("\n=== H34 SUMMARY ===")
    print(json.dumps(summary, indent=2))

    print("\n=== Note ===")
    print("h7v3plus3 is a simple combination of h7v3plus2 (H26) + H22 veto.")
    print("  identical: same as h7v3plus2 (no H22 change for identical)")
    print("  YouTube: h7v3plus2 with 16->21 removed and 20->21 added")
    print("  Expected: identical mean q 0.8105, YouTube mean q 0.6886")
    print("  Expected n_chains: identical 42, YouTube 16 (vs h7v3plus2's 15)")
    print("\nA full min-cost flow re-run is needed to get final chain counts")
    print("and H10 v10 quality. This script just emits the augmented edge set.")


if __name__ == "__main__":
    main()
