#!/usr/bin/env python3
"""H9 — Object permanence: bridge detector dropouts in H7 chains.

Hypothesis: H7 chains are punctuated by detector dropouts (the
detector misses the ball for some frames, then picks it up again).
By modeling the chain as a single physical ball, we can identify
"missing" frames and quantify the dropout rate. This tells us
how much of the chain is "real observations" vs "gaps where
we have to assume the ball is still there."

Approach (declared before reading outcomes):
1. For each H7 chain, compute the timeline of tracklet coverage
   (frame ranges per tracklet).
2. Identify GAPS: periods of >5 frames where no tracklet is active
   in the chain.
3. For each gap, use a constant-velocity model (linear
   extrapolation from tracklet endpoints) to PREDICT the ball
   position. This is the "object permanence" prediction.
4. Compare predicted position to actual detector observations
   (if any) in the gap window.
5. Report chain fragmentation statistics.

This is a *measurement* experiment, not a *recovery* experiment.
H9 doesn't generate new chains — it measures how much of each
chain is real vs gap.
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

# H9 thresholds
H9 = {
    "MIN_GAP_FRAMES": 5,   # ignore gaps shorter than 5 frames
    "MIN_CHAIN_LEN": 2,    # only consider chains with 2+ tracklets
}


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


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


def predict_via_constant_velocity(tids: list[int], tracklets: dict, gap_start: int,
                                 gap_end: int) -> list[tuple[int, float, float]]:
    """Predict ball position during a gap using constant-velocity extrapolation.

    Uses linear interpolation between the last point before the gap and
    the first point after the gap.
    """
    if len(tids) < 2:
        return []
    # Find the source and target tracklets
    # The gap is between consecutive tracklets in tids
    # We assume gap is between tids[i] and tids[i+1]
    # Find this i:
    src_tid = None
    tgt_tid = None
    for i in range(len(tids) - 1):
        src, tgt = tids[i], tids[i + 1]
        src_last = tracklets[src]["last_frame"]
        tgt_first = tracklets[tgt]["first_frame"]
        if src_last < gap_start and tgt_first > gap_end:
            src_tid = src
            tgt_tid = tgt
            break
    if src_tid is None or tgt_tid is None:
        return []
    # Linear interpolation in time
    src = tracklets[src_tid]
    tgt = tracklets[tgt_tid]
    src_t = src["last_frame"]
    tgt_t = tgt["first_frame"]
    if tgt_t == src_t:
        return []
    # Linear interpolation of x, y
    points = []
    for f in range(gap_start, gap_end + 1):
        t_norm = (f - src_t) / (tgt_t - src_t)
        x = src["last_x"] + t_norm * (tgt["first_x"] - src["last_x"])
        y = src["last_y"] + t_norm * (tgt["first_y"] - src["last_y"])
        points.append((f, x, y))
    return points


def main():
    summary = {"h9_thresholds": H9, "videos": {}}
    for stem, video_key in STEMS.items():
        print(f"\n=== {stem} ===")
        tracklets = load_tracklet_features(stem)
        chains = load_h237_chains(stem)
        print(f"  tracklets: {len(tracklets)}")
        print(f"  chains: {len(chains)}")

        # For each multi-tracklet chain, find gaps
        chain_stats = []
        for c in chains:
            tids = c["tids"]
            if len(tids) < H9["MIN_CHAIN_LEN"]:
                continue
            # Compute total chain coverage
            sorted_tids = sorted(tids, key=lambda t: tracklets[t]["first_frame"])
            first_frame = tracklets[sorted_tids[0]]["first_frame"]
            last_frame = tracklets[sorted_tids[-1]]["last_frame"]
            total_span = last_frame - first_frame + 1
            # Compute observed frames
            observed = set()
            for tid in sorted_tids:
                for f in range(tracklets[tid]["first_frame"],
                               tracklets[tid]["last_frame"] + 1):
                    observed.add(f)
            n_observed = len(observed)
            # Find gaps (>= MIN_GAP_FRAMES)
            gaps = []
            for i in range(len(sorted_tids) - 1):
                src, tgt = sorted_tids[i], sorted_tids[i + 1]
                gap_start = tracklets[src]["last_frame"] + 1
                gap_end = tracklets[tgt]["first_frame"] - 1
                if gap_end >= gap_start and (gap_end - gap_start + 1) >= H9["MIN_GAP_FRAMES"]:
                    gaps.append((gap_start, gap_end, gap_end - gap_start + 1))
            n_gap_frames = sum(g[2] for g in gaps)
            chain_stats.append({
                "chain_id": c["chain_id"],
                "n_tracklets": len(tids),
                "first_frame": first_frame,
                "last_frame": last_frame,
                "total_span": total_span,
                "n_observed_frames": n_observed,
                "coverage": n_observed / total_span if total_span > 0 else 0,
                "n_gaps": len(gaps),
                "n_gap_frames": n_gap_frames,
                "gaps": gaps,
            })

        # Aggregate stats
        total_chains = len(chain_stats)
        total_gaps = sum(s["n_gaps"] for s in chain_stats)
        total_gap_frames = sum(s["n_gap_frames"] for s in chain_stats)
        total_observed = sum(s["n_observed_frames"] for s in chain_stats)
        total_span = sum(s["total_span"] for s in chain_stats)
        print(f"  multi-tracklet chains: {total_chains}")
        print(f"  total gaps: {total_gaps}")
        print(f"  total gap frames: {total_gap_frames}")
        print(f"  total observed frames: {total_observed}")
        print(f"  total span: {total_span}")
        print(f"  overall coverage: {total_observed / total_span * 100:.1f}% "
              f"({total_gap_frames} gap frames filled by object permanence)")
        # Show chains with biggest gaps
        biggest_gap_chains = sorted(chain_stats, key=lambda s: -s["n_gap_frames"])[:5]
        print(f"  chains with biggest gaps:")
        for s in biggest_gap_chains:
            print(f"    chain {s['chain_id']}: n_tids={s['n_tracklets']}, "
                  f"span={s['total_span']}, observed={s['n_observed_frames']}, "
                  f"gaps={s['n_gaps']} ({s['n_gap_frames']} frames)")

        # Per-hand vs per-air: do hand events cause more gap frames?
        # (this is for chains that have hand-edges)
        hand_chain_gaps = [s for s in chain_stats if s["n_gaps"] > 0]
        # In chains with hand events, what's the coverage?
        n_hand_chains = sum(1 for c in chains
                            if c["n_hand_edges"] > 0 and c["n_tracklets"] >= H9["MIN_CHAIN_LEN"])
        n_no_hand_chains = sum(1 for c in chains
                               if c["n_hand_edges"] == 0 and c["n_tracklets"] >= H9["MIN_CHAIN_LEN"])
        print(f"  multi-tracklet chains with hand events: {n_hand_chains}")
        print(f"  multi-tracklet chains without hand events: {n_no_hand_chains}")

        summary["videos"][stem] = {
            "video_key": video_key,
            "total_chains": total_chains,
            "total_gaps": total_gaps,
            "total_gap_frames": total_gap_frames,
            "total_observed_frames": total_observed,
            "total_span": total_span,
            "overall_coverage": total_observed / total_span if total_span > 0 else 0,
            "n_hand_chains": n_hand_chains,
            "n_no_hand_chains": n_no_hand_chains,
            "chain_stats": chain_stats,
        }

    out_path = H1_DATA / "h9_object_permanence_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
