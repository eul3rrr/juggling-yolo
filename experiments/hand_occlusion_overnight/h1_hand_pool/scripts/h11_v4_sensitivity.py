#!/usr/bin/env python3
"""H11 v4 sensitivity - sweep SPATIAL_RADIUS and
VELOCITY_COHERENCE thresholds.

For each (SPATIAL_RADIUS, VELOCITY_COHERENCE) cell:
  - n_v4_candidates
  - n_CONFIDENT-merge (cs chain q >= 0.7)
  - n_velocity-coherent

A good operating point is one with few candidates and at
least 1 velocity-coherent (suggesting a real merge).
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

sys.path.insert(0, str(H1_DIR / "scripts"))
from h11_v4_merge_spatial import (
    load_h237v5_chains, load_h237_edges, load_tracklet_features,
    load_norfair_points, load_wrist_positions, initial_velocity,
    final_velocity, parse_hand_metadata, find_closest_wrist,
    QUALITY_CONFIDENT, QUALITY_TRUSTABLE, TEMPORAL_RADIUS,
)

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
}

# Spatial radius values: tighter (50) to looser (108 = reach radius)
SPATIAL_VALUES = [50, 60, 80, 100, 108]
# Velocity coherence threshold (px/frame * sqrt(2))
VELOCITY_VALUES = [3.0, 5.0, 7.0, 10.0]


def detect_v4_with_thresholds(chains, tracklets, edges,
                                norfair_points, wrist_frames,
                                spatial_radius, velocity_coherence):
    out = []
    chain_starts = []
    for c in chains:
        if c["n_tracklets"] == 0:
            continue
        first_tid = c["tids"][0]
        tf = tracklets.get(first_tid)
        if tf is None:
            continue
        vx0, vy0 = initial_velocity(norfair_points, first_tid)
        chain_starts.append({
            "chain_id": c["chain_id"],
            "first_tid": first_tid,
            "first_frame": tf["first_frame"],
            "first_x": tf["first_x"],
            "first_y": tf["first_y"],
            "quality": c["h10_v5_quality"],
            "init_vx": vx0,
            "init_vy": vy0,
        })
    events = []
    for c in chains:
        if c["h10_v5_quality"] < QUALITY_TRUSTABLE:
            continue
        tids = c["tids"]
        for i in range(len(tids) - 1):
            prev_tid = tids[i]
            tid = tids[i + 1]
            edge = edges.get((prev_tid, tid))
            if edge is None:
                continue
            etype = edge["edge_type"]
            if etype not in ("HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION"):
                continue
            md = parse_hand_metadata(edge["metadata"])
            prev_tf = tracklets.get(prev_tid, {})
            curr_tf = tracklets.get(tid, {})
            if "first_frame" not in prev_tf or "first_frame" not in curr_tf:
                continue
            prev_last = prev_tf["last_frame"]
            curr_first = curr_tf["first_frame"]
            event_frame = (prev_last + curr_first) // 2
            fvx, fvy = final_velocity(norfair_points, prev_tid)
            events.append({
                "chain_id": c["chain_id"],
                "event_frame": event_frame,
                "hand": md.get("hand", "?"),
                "prev_tid": prev_tid,
                "tid": tid,
                "final_vx": fvx,
                "final_vy": fvy,
            })
    for cs in chain_starts:
        for e in events:
            if e["chain_id"] == cs["chain_id"]:
                continue
            df = e["event_frame"] - cs["first_frame"]
            if abs(df) > TEMPORAL_RADIUS:
                continue
            w = find_closest_wrist(wrist_frames, e["event_frame"], max_diff=3)
            if w is None:
                continue
            hand = e["hand"]
            if hand not in ("left", "right"):
                continue
            wrist_x, wrist_y, _ = w[hand]
            dx = cs["first_x"] - wrist_x
            dy = cs["first_y"] - wrist_y
            spatial_dist = math.sqrt(dx * dx + dy * dy)
            if spatial_dist > spatial_radius:
                continue
            vdx = cs["init_vx"] - e["final_vx"]
            vdy = cs["init_vy"] - e["final_vy"]
            vel_diff = math.sqrt(vdx * vdx + vdy * vdy)
            coherent = vel_diff < velocity_coherence * math.sqrt(2)
            out.append({
                "cs_quality": cs["quality"],
                "spatial_dist": spatial_dist,
                "vel_diff": vel_diff,
                "coherent": coherent,
            })
    return out


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        chains = load_h237v5_chains(stem)
        edges = load_h237_edges(stem)
        tracklets = load_tracklet_features(stem)
        norfair_points = load_norfair_points(stem)
        wrist_frames = load_wrist_positions(stem)

        grid = []
        for spatial in SPATIAL_VALUES:
            for velocity in VELOCITY_VALUES:
                out = detect_v4_with_thresholds(
                    chains, tracklets, edges,
                    norfair_points, wrist_frames,
                    spatial, velocity)
                n_total = len(out)
                n_confident = sum(1 for m in out
                                  if m["cs_quality"] >= QUALITY_CONFIDENT)
                n_coherent = sum(1 for m in out if m["coherent"])
                grid.append({
                    "spatial_radius": spatial,
                    "velocity_coherence": velocity,
                    "n_total": n_total,
                    "n_confident": n_confident,
                    "n_coherent": n_coherent,
                })
        # Print
        print(f"{'spatial':>8} {'vel':>5} {'n_tot':>5} {'n_conf':>6} {'n_coh':>5}")
        for r in grid:
            print(f"{r['spatial_radius']:8d} {r['velocity_coherence']:5.1f} "
                  f"{r['n_total']:5d} {r['n_confident']:6d} {r['n_coherent']:5d}")
        out_path = H1_DATA / "h11_v4_sensitivity.json"
        out_path.write_text(json.dumps(grid, indent=2))
        print(f"\nSaved: {out_path.name}")
        summary["videos"][stem] = {"grid": grid}

    out = H1_DATA / "h11_v4_sensitivity_summary.json"
    out.write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
