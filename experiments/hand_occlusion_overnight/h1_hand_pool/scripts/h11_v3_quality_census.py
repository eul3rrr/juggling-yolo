#!/usr/bin/env python3
"""H11 v3 - quality-filtered census.

The H11 v2 census counts every chain as one physical ball,
regardless of quality. The YouTube video's 4+ ball inflation
is because UNCERTAIN chains (q 0.4-0.6) over-count.

H11 v3 sweeps a quality threshold and reports the census at
each level. This tells us:
  - what threshold yields a "3-ball cascade" for the cascade
    portions of the videos
  - what threshold yields a "1-ball" for the non-cascade
    portions
  - whether the YouTube inflation can be tamed by a higher
    quality threshold
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

# Quality thresholds to sweep.
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def load_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            r["n_tracklets"] = int(r["n_tracklets"])
            r["h10_v5_quality"] = float(r["h10_v5_quality"])
            r["chain_id"] = int(r["chain_id"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            out.append(r)
    return out


def census_at_threshold(chains: list[dict], threshold: float) -> dict:
    """Count, at each frame, how many quality-filtered chains
    are present (i.e. their first_frame <= f <= last_frame)."""
    # Build a per-frame count of QUALITY-FILTERED chains
    chain_at_frame = defaultdict(int)
    for c in chains:
        if c["h10_v5_quality"] >= threshold:
            for f in range(c["first_frame"], c["last_frame"] + 1):
                chain_at_frame[f] += 1
    if not chain_at_frame:
        return {}
    n_total = sum(1 for v in chain_at_frame.values() if v >= 0)
    n0 = sum(1 for v in chain_at_frame.values() if v == 0)
    n1 = sum(1 for v in chain_at_frame.values() if v == 1)
    n2 = sum(1 for v in chain_at_frame.values() if v == 2)
    n3 = sum(1 for v in chain_at_frame.values() if v == 3)
    n4 = sum(1 for v in chain_at_frame.values() if v >= 4)
    fmin, fmax = min(chain_at_frame.keys()), max(chain_at_frame.keys())
    pct_3 = 100 * (n3 + n4) / max(1, n_total)
    return {
        "n_frames": n_total,
        "pct_0": 100 * n0 / max(1, n_total),
        "pct_1": 100 * n1 / max(1, n_total),
        "pct_2": 100 * n2 / max(1, n_total),
        "pct_3": 100 * n3 / max(1, n_total),
        "pct_4+": 100 * n4 / max(1, n_total),
        "pct_cascade": pct_3,
        "fmin": fmin,
        "fmax": fmax,
    }


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        chains = load_chains(stem)
        print(f"  Total chains: {len(chains)}")

        results = []
        for th in THRESHOLDS:
            cens = census_at_threshold(chains, th)
            results.append({"threshold": th, **cens})
            print(f"  q >= {th}: n_kept_chains=?, "
                  f"pct_3={cens['pct_3']:.1f}%, "
                  f"pct_cascade={cens['pct_cascade']:.1f}%")
        n_kept = {}
        for th in THRESHOLDS:
            n_kept[th] = sum(1 for c in chains if c["h10_v5_quality"] >= th)
            # Update the matching entry
            for r in results:
                if r["threshold"] == th:
                    r["n_kept_chains"] = n_kept[th]
                    break
        print(f"  n_kept_chains by threshold:")
        for th in THRESHOLDS:
            print(f"    q >= {th}: {n_kept[th]} chains kept")

        # For each video, find the threshold that best fits:
        #   - identical: peaks at ~50% cascade time
        #   - youtube: stays at high cascade time
        # This is just a measurement, not a tuning.

        summary["videos"][stem] = {"results": results}

    out = H1_DATA / "h11_v3_quality_census.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
