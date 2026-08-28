#!/usr/bin/env python3
"""H16 — H3 stationary-cluster corroboration for V-reclassified edges.

H11 v7 found that 2/4 identical V-reclassified edges (23->25, 39->47)
are HAND-BORNE, not clean catch+throws. The 1 YouTube V-reclassified
(27->28) is a false positive. H15v2's V-shape check is position-only
and can't distinguish these cases.

H16 hypothesis: a stricter V-shape check that requires
H3 stationary-cluster evidence of a held ball at the V-apex
hand during the gap should reject the hand-borne cases
(23->25, 39->47) and the false positive (27->28), while
keeping the 2 clean catch+throws (30->33, 51->52).

The H3 criterion: >= 3 low-confidence detections in a 30-px
radius over >= 5 frames within the gap window. Restricted to
the V-apex hand (left or right, from h14_min_d).

H16 thresholds (inherited from H3 v3, declared from physical
geometry, NOT from manual labels):
- LOW_CONF_MAX = 0.5 (criterion uses all dets conf < 0.5)
- CLUSTER_RADIUS_PX = 30
- CLUSTER_MIN_FRAMES = 5
- CLUSTER_MIN_DETS = 3
- GAP_PAD_FRAMES = 5 (search window = gap + 5 frames each side)
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DET_DIR = WORKTREE / "detections"

# H3 v3 thresholds (from experiments/hand_occlusion_overnight/STATE.md H3 v3)
LOW_CONF_MAX = 0.5
CLUSTER_RADIUS_PX = 30.0
CLUSTER_MIN_FRAMES = 5
CLUSTER_MIN_DETS = 3
GAP_PAD_FRAMES = 5

# Reach radius (from H1 v2 / v4d, declared from physical geometry)
REACH_RADIUS_PX = 108.0


def load_v_reclassified(stem: str) -> list[dict]:
    with (H1_DATA / f"h7v3pure_v_reclassified_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


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
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
            }
    return out


def load_low_conf_dets(stem: str, exclude_tids: set = None) -> list[dict]:
    """Load low-conf sports-ball detections (not tracklet-level).

    exclude_tids: tracklets to exclude (e.g., the source/target of
    the edge being checked). A "real" held-ball cluster should
    consist of detector firings that are NOT part of any known
    tracklet.
    """
    out = []
    candidates = [
        DET_DIR / f"{stem}_yolo26s_botsort.csv",
        DET_DIR / f"{stem}_norfair_dt50_hc5.csv",
    ]
    for p in candidates:
        if not p.exists():
            continue
        with p.open() as fh:
            for r in csv.DictReader(fh):
                if "confidence" in r:
                    try:
                        conf = float(r["confidence"])
                    except (ValueError, TypeError):
                        continue
                    if conf < LOW_CONF_MAX:
                        out.append({
                            "frame": int(r["frame"]),
                            "x": float(r["center_x"]),
                            "y": float(r["center_y"]),
                            "conf": conf,
                            "track_id": int(r.get("track_id", -1)) if r.get("track_id", "") else -1,
                        })
                # Also include tracklet-level dets (no confidence column)
                elif "track_id" in r and "confidence" not in r:
                    # Norfair: assume conf=1.0 for tracklet-level
                    pass
        if out:
            break
    if exclude_tids:
        out = [d for d in out if d["track_id"] not in exclude_tids]
    return out


def load_wrist_positions(stem: str) -> dict:
    """Return {frame: {left: (x, y), right: (x, y)}}."""
    out = {}
    path = DET_DIR / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                out[fr] = {
                    "left": (float(r["left_wrist_x"]), float(r["left_wrist_y"])),
                    "right": (float(r["right_wrist_x"]), float(r["right_wrist_y"])),
                }
            except (ValueError, KeyError):
                continue
    return out


def find_h3_cluster(low_conf_dets: list[dict],
                    target_xy: tuple[float, float],
                    gap_start: int, gap_end: int) -> dict:
    """For each frame in [gap_start - GAP_PAD, gap_end + GAP_PAD],
    count low-conf dets within CLUSTER_RADIUS_PX of target_xy.
    Return a summary dict.

    A real held ball should have multiple low-conf dets in the
    same small region across multiple frames (the detector
    intermittently fires on the held ball).
    """
    n_total = 0
    frames_with_dets = set()
    dets = []
    for d in low_conf_dets:
        if d["frame"] < gap_start - GAP_PAD_FRAMES:
            continue
        if d["frame"] > gap_end + GAP_PAD_FRAMES:
            continue
        dx = d["x"] - target_xy[0]
        dy = d["y"] - target_xy[1]
        if (dx * dx + dy * dy) ** 0.5 <= CLUSTER_RADIUS_PX:
            n_total += 1
            frames_with_dets.add(d["frame"])
            dets.append(d)
    n_frames = len(frames_with_dets)
    return {
        "n_total_dets": n_total,
        "n_unique_frames": n_frames,
        "n_unique_tids": len(set(d.get("track_id", -1) for d in dets)),
        "frames": sorted(frames_with_dets),
    }


def main():
    stems = [
        "identical_balls_trick_000_018",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
    ]
    summary = {"videos": {}, "thresholds": {
        "LOW_CONF_MAX": LOW_CONF_MAX,
        "CLUSTER_RADIUS_PX": CLUSTER_RADIUS_PX,
        "CLUSTER_MIN_FRAMES": CLUSTER_MIN_FRAMES,
        "CLUSTER_MIN_DETS": CLUSTER_MIN_DETS,
        "GAP_PAD_FRAMES": GAP_PAD_FRAMES,
    }}
    for stem in stems:
        print(f"\n=== {stem} ===")
        vrecs = load_v_reclassified(stem)
        tracklets = load_tracklet_features(stem)
        low_conf = load_low_conf_dets(stem)
        wrists = load_wrist_positions(stem)
        print(f"  loaded {len(vrecs)} V-reclassified edges, "
              f"{len(low_conf)} low-conf dets, {len(wrists)} wrist frames")

        results = []
        for vrec in vrecs:
            src, tgt = int(vrec["from_tid"]), int(vrec["to_tid"])
            hand = vrec["h14_hand"]
            min_d = float(vrec["h14_min_d"])
            v_class = vrec["h14_class"]
            t_src = tracklets.get(src, {})
            t_tgt = tracklets.get(tgt, {})
            gap_start = t_src.get("last_frame", 0)
            gap_end = t_tgt.get("first_frame", gap_start + 1)
            # Exclude source + target tracklets from H3 cluster check
            # (their own low-conf dets are not "independent evidence")
            edge_low_conf = load_low_conf_dets(stem, exclude_tids={src, tgt})
            # V-apex hand position: average wrist position over the gap window
            wrist_xs, wrist_ys = [], []
            for fr in range(gap_start, gap_end + 1):
                if fr in wrists and hand in wrists[fr]:
                    wx, wy = wrists[fr][hand]
                    wrist_xs.append(wx)
                    wrist_ys.append(wy)
            if not wrist_xs:
                # Use closest available wrist
                for fr in sorted(wrists.keys(), key=lambda f: abs(f - gap_start))[:5]:
                    if hand in wrists[fr]:
                        wrist_xs.append(wrists[fr][hand][0])
                        wrist_ys.append(wrists[fr][hand][1])
            if not wrist_xs:
                target_xy = (0, 0)
            else:
                target_xy = (sum(wrist_xs) / len(wrist_xs),
                              sum(wrist_ys) / len(wrist_ys))

            cluster = find_h3_cluster(edge_low_conf, target_xy, gap_start, gap_end)
            is_h3_confirmed = (
                cluster["n_unique_frames"] >= CLUSTER_MIN_FRAMES
                and cluster["n_total_dets"] >= CLUSTER_MIN_DETS
            )
            results.append({
                "edge": f"{src}->{tgt}",
                "v_class": v_class,
                "v_min_d": min_d,
                "hand": hand,
                "gap_start": gap_start,
                "gap_end": gap_end,
                "target_hand_xy": list(target_xy),
                "n_total_dets_in_cluster": cluster["n_total_dets"],
                "n_unique_frames_in_cluster": cluster["n_unique_frames"],
                "h3_confirmed": is_h3_confirmed,
            })
            print(f"  {src}->{tgt} (V={v_class}, min_d={min_d:.1f}, {hand}): "
                  f"target=({target_xy[0]:.0f},{target_xy[1]:.0f}) "
                  f"n_dets={cluster['n_total_dets']} n_frames={cluster['n_unique_frames']} "
                  f"h3={'YES' if is_h3_confirmed else 'no'}")

        # Summary
        n_total = len(results)
        n_h3_confirmed = sum(1 for r in results if r["h3_confirmed"])
        print(f"\n  Summary: {n_h3_confirmed}/{n_total} V-reclassified edges have h3 cluster confirmation")
        summary["videos"][stem] = {
            "n_v_reclassified": n_total,
            "n_h3_confirmed": n_h3_confirmed,
            "results": results,
        }

    out = H1_DATA / "h16_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
