#!/usr/bin/env python3
"""H11 sensitivity — sweep QUALITY_CONFIDENT and QUALITY_TRUSTABLE
thresholds to see if the H11 chain classification (CONFIDENT,
UNCERTAIN, LOW) is robust to threshold perturbations.

For each (CONFIDENT, TRUSTABLE) cell:
  - n_chains at each classification
  - n_catch_throw_events emitted
  - identity merge candidates (CONFIDENT-merge count)
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
}

# Confident thresholds to sweep.
CONFIDENT_VALUES = [0.5, 0.6, 0.7, 0.8, 0.9]
# Trustable thresholds to sweep.
TRUSTABLE_VALUES = [0.3, 0.4, 0.5]


def main():
    stem = "identical_balls_trick_000_018"
    chains = list(csv.DictReader(
        (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open()))
    edges = list(csv.DictReader(
        (H1_DATA / f"h237_unified_edges_{stem}.csv").open()))

    grid = []
    for confident in CONFIDENT_VALUES:
        for trustable in TRUSTABLE_VALUES:
            if trustable >= confident:
                continue
            n_confident = sum(1 for c in chains
                              if float(c["h10_v5_quality"]) >= confident)
            n_uncertain = sum(1 for c in chains
                              if trustable <= float(c["h10_v5_quality"]) < confident)
            n_low = sum(1 for c in chains
                        if float(c["h10_v5_quality"]) < trustable)
            # n_events: count hand-edges in chains with q >= trustable
            chain_ids_trustable = set(
                int(c["chain_id"]) for c in chains
                if float(c["h10_v5_quality"]) >= trustable)
            chain_tids = {}
            for c in chains:
                chain_tids[int(c["chain_id"])] = set(
                    int(t) for t in c["tids"].split(",") if t)
            n_events = 0
            for e in edges:
                et = e["edge_type"]
                if et not in ("HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION"):
                    continue
                # Find which chain this edge belongs to
                from_t = int(e["from_tid"])
                to_t = int(e["to_tid"])
                for cid, tids in chain_tids.items():
                    if from_t in tids and to_t in tids and cid in chain_ids_trustable:
                        n_events += 1
                        break
            grid.append({
                "confident": confident,
                "trustable": trustable,
                "n_confident": n_confident,
                "n_uncertain": n_uncertain,
                "n_low": n_low,
                "n_hand_events": n_events,
            })
    # Print
    print("=== H11 sensitivity grid ===")
    print(f"{'conf':>6} {'trust':>6} {'n_conf':>6} {'n_unc':>6} {'n_low':>6} {'n_ev':>5}")
    for r in grid:
        print(f"{r['confident']:6.2f} {r['trustable']:6.2f} "
              f"{r['n_confident']:6d} {r['n_uncertain']:6d} "
              f"{r['n_low']:6d} {r['n_hand_events']:5d}")
    out = H1_DATA / "h11_sensitivity.json"
    out.write_text(json.dumps(grid, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
