#!/usr/bin/env python3
"""H11 v2 - export identity-merge candidates as a CSV for
downstream review.
"""
from __future__ import annotations

import csv
import json
import importlib.util
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

sys.path.insert(0, str(H1_DIR / "scripts"))
from h11_v2_census_pattern import (
    load_h237v5_chains, load_h237_edges, load_tracklet_features,
    extract_catch_throw_timeline, detect_identity_merges,
    QUALITY_CONFIDENT, QUALITY_TRUSTABLE,
)

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def main():
    for stem in STEMS:
        chains = load_h237v5_chains(stem)
        edges = load_h237_edges(stem)
        tracklets = load_tracklet_features(stem)
        events = extract_catch_throw_timeline(chains, edges, tracklets)
        merges = detect_identity_merges(chains, tracklets, events)
        if not merges:
            continue
        out_path = H1_DATA / f"merge_candidates_{stem}.csv"
        with out_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(merges[0].keys()))
            w.writeheader()
            w.writerows(merges)
        print(f"  wrote: {out_path.name} ({len(merges)} candidates)")


if __name__ == "__main__":
    main()
