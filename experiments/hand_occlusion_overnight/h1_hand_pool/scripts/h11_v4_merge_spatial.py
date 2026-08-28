#!/usr/bin/env python3
"""H11 v4 - identity-merge candidates with spatial proximity.

The H11 v2 merge algorithm (detect_identity_merges in
h11_v2_census_pattern.py) only used temporal proximity
(chain_start within 30 frames of an event). It flagged
chain 36 <-> chain 30 as a merge candidate, but visual QA
showed they're 73 pixels apart at f=890 (two different
balls, not a missed merge).

H11 v4 adds:
1. Spatial proximity: the chain_start's first ball position
   must be within SPATIAL_RADIUS pixels of the wrist
   position at the event frame.
2. Velocity coherence: the chain_start's initial velocity
   (first 3 frames) should be consistent with the velocity
   direction of the previous tracklet's last frames.
3. Higher merge confidence when both criteria are met.

The SPATIAL_RADIUS threshold is declared from physical
geometry: a ball at the hand has end_dist <= 108 pixels
(master §5, "reach radius"). For a missed merge to be
plausible, the chain_start's first position must be within
that radius. We use 80 pixels to be conservative.

We compare H11 v2 (temporal-only) vs H11 v4 (temporal +
spatial) on:
- number of merge candidates
- how many are CONFIDENT-merge (both chains q >= 0.7)
- visual QA spot check on the new top candidate
"""
from __future__ import annotations

import csv
import json
import math
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

# Thresholds (declared from physical geometry, not from manual labels).
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4
TEMPORAL_RADIUS = 30  # frames
SPATIAL_RADIUS = 80  # pixels (conservative; reach is 108)
VELOCITY_COHERENCE = 5.0  # px/frame tolerance


def load_h237v5_chains(stem: str) -> list[dict]:
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


def load_h237_edges(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            key = (int(r["from_tid"]), int(r["to_tid"]))
            out[key] = {
                "edge_type": r["edge_type"],
                "metadata": r["metadata"],
            }
    return out


def load_tracklet_features(stem: str) -> dict:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            tid = int(r["tid"])
            out[tid] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


def load_norfair_points(stem: str) -> dict:
    """Returns {tid: [(frame, x, y), ...]} sorted by frame."""
    out = defaultdict(list)
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if "track_id" not in r:
                continue
            tid = int(r["track_id"])
            out[tid].append((int(r["frame"]), float(r["center_x"]),
                             float(r["center_y"])))
    for tid in out:
        out[tid].sort()
    return out


def parse_hand_metadata(metadata: str) -> dict:
    if not metadata:
        return {}
    out = {}
    for part in metadata.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def load_wrist_positions(stem: str) -> dict:
    """Returns {frame: {"left": (x, y, conf), "right": (x, y, conf)}}."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                out[fr] = {
                    "left": (float(r["left_wrist_x"]),
                             float(r["left_wrist_y"]),
                             float(r.get("left_wrist_confidence", 0))),
                    "right": (float(r["right_wrist_x"]),
                              float(r["right_wrist_y"]),
                              float(r.get("right_wrist_confidence", 0))),
                }
            except (ValueError, KeyError):
                continue
    return out


def find_closest_wrist(wrist_frames: dict, frame: int, max_diff: int = 5):
    if not wrist_frames or frame in wrist_frames:
        return wrist_frames.get(frame)
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def initial_velocity(norfair_points: dict, tid: int) -> tuple:
    """Returns initial velocity (vx, vy) in px/frame from
    the first 3 detections of tid. Returns (0, 0) if
    insufficient data."""
    pts = norfair_points.get(tid, [])
    if len(pts) < 3:
        return (0.0, 0.0)
    f0, x0, y0 = pts[0]
    f2, x2, y2 = pts[2]
    if f2 == f0:
        return (0.0, 0.0)
    return ((x2 - x0) / (f2 - f0), (y2 - y0) / (f2 - f0))


def final_velocity(norfair_points: dict, tid: int) -> tuple:
    """Returns final velocity (vx, vy) in px/frame from
    the last 3 detections of tid. Returns (0, 0) if
    insufficient data."""
    pts = norfair_points.get(tid, [])
    if len(pts) < 3:
        return (0.0, 0.0)
    f0, x0, y0 = pts[-3]
    f2, x2, y2 = pts[-1]
    if f2 == f0:
        return (0.0, 0.0)
    return ((x2 - x0) / (f2 - f0), (y2 - y0) / (f2 - f0))


def detect_identity_merges_v4(chains: list[dict], tracklets: dict,
                                edges: dict, norfair_points: dict,
                                wrist_frames: dict) -> list[dict]:
    """H11 v4 merge algorithm. Adds spatial proximity
    (chain_start's first position within 80px of the wrist
    at the event frame) and velocity coherence (initial
    velocity of new chain consistent with final velocity
    of the previous tracklet)."""
    out = []

    # Per-chain metadata
    chain_starts = []
    for c in chains:
        if c["n_tracklets"] == 0:
            continue
        first_tid = c["tids"][0]
        tf = tracklets.get(first_tid)
        if tf is None:
            continue
        # Get initial velocity from norfair data
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

    # Per-event metadata: from h237_unified_edges
    # Build events list
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
            # Final velocity of prev_tid
            fvx, fvy = final_velocity(norfair_points, prev_tid)
            events.append({
                "chain_id": c["chain_id"],
                "event_frame": event_frame,
                "hand": md.get("hand", "?"),
                "prev_tid": prev_tid,
                "tid": tid,
                "final_vx": fvx,
                "final_vy": fvy,
                "h3_confirmed": (
                    "True" in edge["metadata"] or "False" not in edge["metadata"]),
            })

    for cs in chain_starts:
        for e in events:
            if e["chain_id"] == cs["chain_id"]:
                continue
            df = e["event_frame"] - cs["first_frame"]
            if abs(df) > TEMPORAL_RADIUS:
                continue
            # Spatial proximity: find wrist at event_frame
            w = find_closest_wrist(wrist_frames, e["event_frame"], max_diff=3)
            if w is None:
                continue
            hand = e["hand"]
            if hand not in ("left", "right"):
                continue
            wrist_x, wrist_y, _ = w[hand]
            # Distance from chain_start's first position to wrist at event
            dx = cs["first_x"] - wrist_x
            dy = cs["first_y"] - wrist_y
            spatial_dist = math.sqrt(dx * dx + dy * dy)
            if spatial_dist > SPATIAL_RADIUS:
                continue
            # Velocity coherence
            vdx = cs["init_vx"] - e["final_vx"]
            vdy = cs["init_vy"] - e["final_vy"]
            vel_diff = math.sqrt(vdx * vdx + vdy * vdy)
            coherent = vel_diff < VELOCITY_COHERENCE * math.sqrt(2)
            out.append({
                "candidate_merge": f"chain{cs['chain_id']}->chain{e['chain_id']}",
                "cs_chain_id": cs["chain_id"],
                "cs_first_tid": cs["first_tid"],
                "cs_first_frame": cs["first_frame"],
                "cs_quality": cs["quality"],
                "event_chain_id": e["chain_id"],
                "event_tid": e["tid"],
                "event_frame": e["event_frame"],
                "frame_diff": df,
                "hand": e["hand"],
                "h3_confirmed": e["h3_confirmed"],
                "spatial_dist_px": round(spatial_dist, 1),
                "vel_diff_px_per_frame": round(vel_diff, 2),
                "velocity_coherent": coherent,
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

        merges_v4 = detect_identity_merges_v4(
            chains, tracklets, edges, norfair_points, wrist_frames)

        n_confident = sum(1 for m in merges_v4
                          if m["cs_quality"] >= QUALITY_CONFIDENT)
        n_coherent = sum(1 for m in merges_v4 if m["velocity_coherent"])
        print(f"  merge candidates: {len(merges_v4)}")
        print(f"  of which CONFIDENT-merge (cs chain q >= 0.7): {n_confident}")
        print(f"  of which velocity-coherent: {n_coherent}")

        # Write CSV
        if merges_v4:
            out = H1_DATA / f"merge_candidates_v4_{stem}.csv"
            with out.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(merges_v4[0].keys()))
                w.writeheader()
                w.writerows(merges_v4)
            print(f"  wrote: {out.name}")

        # Compare with v2
        v2_path = H1_DATA / f"merge_candidates_{stem}.csv"
        n_v2 = 0
        if v2_path.exists():
            with v2_path.open() as fh:
                n_v2 = sum(1 for _ in csv.DictReader(fh))
        print(f"  v2 had {n_v2} candidates, v4 has {len(merges_v4)}")
        print(f"  reduction: {n_v2 - len(merges_v4)} "
              f"({100*(n_v2-len(merges_v4))/max(1,n_v2):.1f}%)")

        summary["videos"][stem] = {
            "n_v2_candidates": n_v2,
            "n_v4_candidates": len(merges_v4),
            "n_v4_confident": n_confident,
            "n_v4_velocity_coherent": n_coherent,
        }

    out = H1_DATA / "h11_v4_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
