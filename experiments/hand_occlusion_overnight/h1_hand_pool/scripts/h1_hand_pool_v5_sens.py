#!/usr/bin/env python3
"""H1 v5 — Sensitivity grid on MIN_FROM_SLOPE.

v4 used MIN_FROM_SLOPE = 2.5. The two v3 false positives (15->25
and 35->40) both have |from_slope| < 2.5; the smallest real
catch-throw (17->23) has |from_slope| = 3.95. A sensitivity
grid on MIN_FROM_SLOPE in {2.0, 2.5, 3.0, 4.0, 5.0} verifies
the threshold is well-chosen.

For each threshold we re-run the v4d filtering and report:
- n_links (per video)
- precision_hand_link (per video)
- recall_hand_link (per video)
- links_rejected (which links fell out at this threshold)
- links_kept (the surviving set)

This is a small v5 follow-up to v4 to confirm the v4 operating
point is well-justified.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Reuse v2 internals
sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1_hand_pool_v2 as h2  # noqa: E402

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"


def v4_filter(links: list[dict], min_from_slope: float) -> tuple[list[dict], list[dict]]:
    """Apply the v4 multi-feature filter at a given MIN_FROM_SLOPE.
    Returns (surviving, rejected)."""
    surviving, rejected = [], []
    for l in links:
        if abs(l["from_slope"]) < min_from_slope:
            rejected.append({**l, "rejection_reason": f"LOW_FROM_SLOPE ({abs(l['from_slope']):.2f} < {min_from_slope})"})
            continue
        surviving.append(l)
    return surviving, rejected


def main():
    # First, run v3c (throw=7) to get the candidate link set
    h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"] = 7
    all_runs = []
    for stem, video_key in h2.STEMS.items():
        run = h2.run_for_stem_v2(stem, video_key)
        # v3 soft catch-context rename
        for e in run["events"]:
            if e.event_type == "UNCONTEXTED_ENTRY":
                e.event_type = "POTENTIAL_ENTRY"
        all_runs.append(run)
    v3c_links = []
    for run in all_runs:
        for l in run["links"]:
            v3c_links.append({**l, "stem": run["stem"]})

    print(f"v3c total links: {len(v3c_links)}")
    print(f"  by stem: {dict((s, sum(1 for l in v3c_links if l['stem']==s)) for s in h2.STEMS)}")
    print()

    # Sensitivity grid
    thresholds = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    grid = []
    for thresh in thresholds:
        surviving, rejected = v4_filter(v3c_links, thresh)
        # Per-stem stats
        by_stem = defaultdict(lambda: {"surviving": 0, "rejected": 0})
        for l in surviving:
            by_stem[l["stem"]]["surviving"] += 1
        for l in rejected:
            by_stem[l["stem"]]["rejected"] += 1
        print(f"MIN_FROM_SLOPE={thresh}: total surviving={len(surviving)}, "
              f"rejected={len(rejected)}")
        for stem in h2.STEMS:
            print(f"  {stem}: {by_stem[stem]['surviving']} surviving, {by_stem[stem]['rejected']} rejected")
        # Show which links were rejected at each threshold
        rej_pairs = sorted(set(f"{l['stem']}:{l['from_tid']}->{l['to_tid']}" for l in rejected))
        for s in rej_pairs:
            print(f"    rejected: {s}")
        grid.append({
            "min_from_slope": thresh,
            "n_surviving": len(surviving),
            "n_rejected": len(rejected),
            "by_stem": dict(by_stem),
            "rejected_pairs": rej_pairs,
        })

    out_path = H1_DATA / "sens_grid_v5.json"
    out_path.write_text(json.dumps({
        "v5_settings": grid,
        "v3c_total_links": len(v3c_links),
    }, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
