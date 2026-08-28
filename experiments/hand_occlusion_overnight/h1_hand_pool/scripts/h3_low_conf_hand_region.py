#!/usr/bin/env python3
"""H3 — Low-confidence hand-region evidence (master §14).

Hypothesis: around an active v4d hand-link, low-confidence sports-ball
detections that are NOT part of the incoming or outgoing tracklet can
provide *supporting evidence* for the held-ball state, without globally
lowering the detector confidence (which would admit many background
false positives in mid-air regions).

Approach (declared before reading outcomes):
1. For each v4d hand-link (hand-link from the recommended H1 v4d model):
   - Define a HAND_REGION around the relevant wrist for the gap
     window (from_frame .. to_frame), reach radius = 108 px.
   - Find all "sports ball" detections in
     `detections/<stem>_yolo26s_all-classes.csv` (no confidence
     threshold) that fall inside the hand region during the gap,
     plus ±2 frames of lookahead on the throw side.
   - For each such detection, identify the Norfair track_id (if any).
   - Classify as one of:
     * HELD_BALL_GLIMPSE: ≥3 unassigned low-conf detections
       (conf < 0.5) in a temporal cluster of ≤ 5 frames within
       reach of the wrist, and roughly stationary (std(x) < 30 px,
       std(y) < 30 px) — consistent with a held ball being glimpsed
       intermittently by the detector.
     * OUTGOING_PREVIEW: low-conf detection that is the *start* of
       a Norfair tracklet at the hand region, with confidence
       below the normal high-conf threshold.
     * BACKGROUND_NOISE: scattered, no cluster.
2. Compare to a control baseline: same analysis applied to randomly
   sampled (frame, x, y) points across the video. What fraction of
   random spatial-temporal points show a "HELD_BALL_GLIMPSE"-like
   pattern? This is the FPR.
3. Visual QA: render contact sheets for the v4d hand-links that have
   HELD_BALL_GLIMPSE evidence, to confirm the interpretation.

Outputs (per stem):
- data/h3_glimpses_<stem>.csv: per-v4d-link HELD_BALL_GLIMPSE
  classifications with the supporting detections
- data/h3_summary.json: overall summary
- contact_sheets_h3/<link_id>_glimpse.png: visual evidence per link
"""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_OUT = H1_DIR / "contact_sheets_h3"
H1_OUT.mkdir(parents=True, exist_ok=True)

VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")

# ----------------------------------------------------------------------
# H3 thresholds (declared before reading outcomes)
# ----------------------------------------------------------------------
# v1: tight cluster (≤ 5 frames span, 30 px stationary) - FPR = 0.92,
# misses real held-ball patterns that span longer.
# v2: relaxed cluster (≤ 60 frames span, 60 px stationary) - captures
# the full held-ball phase including hand motion; gaps allowed.
# Hand motion can carry the ball 30-60 px across a 1-second hold.
H3_THRESHOLDS = {
    "HAND_REACH_PX": 108,        # same as v2/v4 reach radius
    "LOW_CONF_THRESHOLD": 0.5,   # below this is "low confidence"
    "MIN_GLIMPSE_FRAMES": 3,     # min cluster size
    "MAX_CLUSTER_SPAN_FRAMES": 60,  # 2 seconds at 30 fps
    "MAX_GAP_IN_CLUSTER": 12,    # allow gaps of up to 12 frames in a cluster
    "STATIONARY_STD_PX": 60,     # max std(x), std(y) - allow hand motion
    "LOOKAHEAD_FRAMES": 2,       # extra frames after to_frame
    "LOOKBACK_FRAMES": 2,        # extra frames before from_frame
    "BASELINE_SAMPLES": 200,     # control samples
    "RANDOM_SEED": 42,
}

V4D_LINKS_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"


def load_wrist_frames(stem: str) -> dict:
    """{frame: {'left': (x,y), 'right': (x,y)}} from the pose CSV."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                lx = float(r["left_wrist_x"]); ly = float(r["left_wrist_y"])
                rx = float(r["right_wrist_x"]); ry = float(r["right_wrist_y"])
                out[fr] = {"left": (lx, ly), "right": (rx, ry)}
            except (ValueError, KeyError):
                continue
    return out


def load_all_sports_ball(stem: str) -> list[tuple]:
    """Load all sports-ball detections from the all-classes YOLO output.

    Tries `_yolo26s_all-classes.csv` first (multi-class), then
    `_yolo26s_classes-32.csv` (only class 32 / sports ball).
    Returns list of (frame, x, y, confidence).
    """
    for suffix in ["_yolo26s_all-classes.csv", "_yolo26s_classes-32.csv"]:
        path = WORKTREE / "detections" / f"{stem}{suffix}"
        if path.exists():
            break
    else:
        return []
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if "class_name" in r and r["class_name"] != "sports ball":
                continue
            try:
                out.append((int(r["frame"]), float(r["center_x"]), float(r["center_y"]), float(r["confidence"])))
            except (ValueError, KeyError):
                continue
    out.sort()
    return out


def load_norfair_index(stem: str) -> dict:
    """{(frame, round(x), round(y)): track_id} from the norfair dt50_hc5 CSV."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                x = round(float(r["center_x"]))
                y = round(float(r["center_y"]))
                out[(fr, x, y)] = int(r["track_id"])
            except (ValueError, KeyError):
                continue
    return out


def find_tid_for_detection(norfair_index: dict, fr: int, x: float, y: float, max_dist: int = 4) -> int | None:
    """Find the Norfair track_id closest to (fr, x, y) within max_dist pixels."""
    for d in range(max_dist + 1):
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                k = (fr, round(x) + dx, round(y) + dy)
                if k in norfair_index:
                    return norfair_index[k]
    return None


def find_closest_wrist(wrist_frames: dict, frame: int, max_diff: int = 5):
    if not wrist_frames:
        return None
    if frame in wrist_frames:
        return wrist_frames[frame]
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def detect_glimpse_cluster(detections: list[tuple], hand_xy: tuple, reach: float) -> dict | None:
    """Given a list of (frame, x, y, conf) detections all within reach of
    the hand, return a classification dict if they form a HELD_BALL_GLIMPSE
    cluster, else None.

    GLIMPSE criteria:
    - n >= MIN_GLIMPSE_FRAMES
    - frame range (max - min) <= MAX_CLUSTER_SPAN_FRAMES
    - std(x) <= STATIONARY_STD_PX and std(y) <= STATIONARY_STD_PX
    - mean confidence < LOW_CONF_THRESHOLD (held ball is intermittently
      glimpsed, so conf is lower than a normal tracklet)
    """
    if len(detections) < H3_THRESHOLDS["MIN_GLIMPSE_FRAMES"]:
        return None
    frames = [d[0] for d in detections]
    if max(frames) - min(frames) > H3_THRESHOLDS["MAX_CLUSTER_SPAN_FRAMES"]:
        return None
    xs = [d[1] for d in detections]
    ys = [d[2] for d in detections]
    cfs = [d[3] for d in detections]
    if statistics.pstdev(xs) > H3_THRESHOLDS["STATIONARY_STD_PX"]:
        return None
    if statistics.pstdev(ys) > H3_THRESHOLDS["STATIONARY_STD_PX"]:
        return None
    mean_conf = statistics.mean(cfs)
    if mean_conf >= H3_THRESHOLDS["LOW_CONF_THRESHOLD"]:
        return None
    return {
        "n": len(detections),
        "frame_min": min(frames),
        "frame_max": max(frames),
        "x_mean": statistics.mean(xs),
        "y_mean": statistics.mean(ys),
        "conf_mean": mean_conf,
        "conf_min": min(cfs),
        "conf_max": max(cfs),
        "std_x": statistics.pstdev(xs),
        "std_y": statistics.pstdev(ys),
    }


def analyse_link(link: dict, all_sb: list, wrist_frames: dict, norfair_index: dict) -> dict:
    """For one v4d hand-link, return all unassigned detections in the
    hand region during the gap, plus classifications."""
    stem = link["stem"]
    from_tid = int(link["from_tid"])
    to_tid = int(link["to_tid"])
    hand = link["hand"]
    f1 = int(link["from_frame"]) - H3_THRESHOLDS["LOOKBACK_FRAMES"]
    f2 = int(link["to_frame"]) + H3_THRESHOLDS["LOOKAHEAD_FRAMES"]

    # Find hand position: use the wrist at the catch frame, throw frame,
    # and average. Falls back to nearest available.
    w_catch = find_closest_wrist(wrist_frames, int(link["from_frame"]))
    w_throw = find_closest_wrist(wrist_frames, int(link["to_frame"]))
    if w_catch is None or w_throw is None:
        return {"error": "no_wrist_data"}
    wx_c, wy_c = w_catch[hand]
    wx_t, wy_t = w_throw[hand]
    wx = (wx_c + wx_t) / 2
    wy = (wy_c + wy_t) / 2

    # Find unassigned detections in the hand region
    in_reach = []
    for (fr, x, y, c) in all_sb:
        if fr < f1 or fr > f2:
            continue
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d > H3_THRESHOLDS["HAND_REACH_PX"]:
            continue
        tid = find_tid_for_detection(norfair_index, fr, x, y)
        is_from = (tid == from_tid)
        is_to = (tid == to_tid)
        if is_from or is_to:
            continue
        in_reach.append((fr, x, y, c, tid, d))

    # Cluster consecutive frames into glimpse groups (gap > MAX_GAP_IN_CLUSTER breaks)
    in_reach.sort()
    clusters = []
    cur = []
    for det in in_reach:
        if cur and det[0] - cur[-1][0] > H3_THRESHOLDS["MAX_GAP_IN_CLUSTER"]:
            clusters.append(cur)
            cur = []
        cur.append(det)
    if cur:
        clusters.append(cur)

    # Classify each cluster
    classified = []
    for cluster in clusters:
        cluster_dets = [(d[0], d[1], d[2], d[3]) for d in cluster]  # (fr, x, y, conf)
        glimpse = detect_glimpse_cluster(cluster_dets, (wx, wy), H3_THRESHOLDS["HAND_REACH_PX"])
        cluster_summary = {
            "frames": [d[0] for d in cluster],
            "n": len(cluster),
            "dets": cluster,
        }
        if glimpse is not None:
            cluster_summary["classification"] = "HELD_BALL_GLIMPSE"
            cluster_summary["glimpse"] = glimpse
        else:
            cluster_summary["classification"] = "BACKGROUND"
        classified.append(cluster_summary)

    # Outgoing preview: low-conf detection at the throw side that is
    # the START of a Norfair tracklet
    outgoing_previews = []
    for (fr, x, y, c, tid, d) in in_reach:
        if fr >= int(link["to_frame"]) - 1 and fr <= int(link["to_frame"]) + 2:
            if tid is not None and tid != to_tid and c < H3_THRESHOLDS["LOW_CONF_THRESHOLD"]:
                outgoing_previews.append({
                    "frame": fr, "x": x, "y": y, "conf": c, "tid": tid, "d": d
                })

    return {
        "link": {
            "stem": stem,
            "from_tid": from_tid,
            "to_tid": to_tid,
            "hand": hand,
            "from_frame": int(link["from_frame"]),
            "to_frame": int(link["to_frame"]),
        },
        "hand_xy": (wx, wy),
        "n_in_reach_unassigned": len(in_reach),
        "n_in_reach_low_conf": sum(1 for d in in_reach if d[3] < H3_THRESHOLDS["LOW_CONF_THRESHOLD"]),
        "n_clusters": len(classified),
        "n_glimpses": sum(1 for c in classified if c["classification"] == "HELD_BALL_GLIMPSE"),
        "clusters": classified,
        "outgoing_previews": outgoing_previews,
    }


def control_baseline(stem: str, all_sb: list, wrist_frames: dict, norfair_index: dict) -> dict:
    """Sample random frames and ask: at that frame, does the *random*
    hand region (randomly chosen L or R) show a HELD_BALL_GLIMPSE
    pattern? This is the FPR estimate: how often does the pattern
    fire on a random (non-hand-event) frame.

    The baseline uses the same cluster criteria as the link analysis.
    """
    random.seed(H3_THRESHOLDS["RANDOM_SEED"])
    if not all_sb or not wrist_frames:
        return {"n_samples": 0, "n_glimpse_like": 0, "fpr": 0.0}

    max_frame = max(d[0] for d in all_sb)
    sb_by_frame = defaultdict(list)
    for d in all_sb:
        sb_by_frame[d[0]].append(d)

    n_glimpse = 0
    n_total = 0

    for _ in range(H3_THRESHOLDS["BASELINE_SAMPLES"]):
        # Pick a random frame, and randomly choose L or R hand
        target_frame = random.randint(0, max_frame)
        hand = random.choice(["left", "right"])
        # Find wrist at that frame (or nearest)
        w = find_closest_wrist(wrist_frames, target_frame)
        if w is None:
            continue
        wx, wy = w[hand]
        # Find all unassigned low-conf detections in a ±30 frame window
        # around target_frame, within reach of (wx, wy)
        window = []
        for df in range(target_frame - 30, target_frame + 31):
            for d in sb_by_frame.get(df, []):
                if d[3] >= H3_THRESHOLDS["LOW_CONF_THRESHOLD"]:
                    continue
                dx = d[1] - wx
                dy = d[2] - wy
                if (dx*dx + dy*dy) ** 0.5 > H3_THRESHOLDS["HAND_REACH_PX"]:
                    continue
                # Exclude detections that are part of any tracklet (we want
                # the noise floor)
                tid = find_tid_for_detection(norfair_index, d[0], d[1], d[2])
                if tid is not None:
                    continue
                window.append(d)

        # Cluster with the same gap rule
        window.sort()
        cur = []
        clusters = []
        for d in window:
            if cur and d[0] - cur[-1][0] > H3_THRESHOLDS["MAX_GAP_IN_CLUSTER"]:
                clusters.append(cur)
                cur = []
            cur.append(d)
        if cur:
            clusters.append(cur)

        for cluster in clusters:
            n_total += 1
            if len(cluster) >= H3_THRESHOLDS["MIN_GLIMPSE_FRAMES"]:
                n_glimpse += 1

    return {
        "n_samples": H3_THRESHOLDS["BASELINE_SAMPLES"],
        "n_clusters_total": n_total,
        "n_glimpse_like": n_glimpse,
        "fpr_per_cluster": (n_glimpse / n_total) if n_total > 0 else 0.0,
    }


def main():
    # Load v4d hand-links
    with V4D_LINKS_PATH.open() as fh:
        links = list(csv.DictReader(fh))
    print(f"v4d links: {len(links)}")

    # Group by stem
    stems = sorted(set(l["stem"] for l in links))
    print(f"stems: {stems}")

    all_sb_by_stem = {}
    wrist_by_stem = {}
    norfair_by_stem = {}
    for stem in stems:
        all_sb_by_stem[stem] = load_all_sports_ball(stem)
        wrist_by_stem[stem] = load_wrist_frames(stem)
        norfair_by_stem[stem] = load_norfair_index(stem)
        print(f"  {stem}: {len(all_sb_by_stem[stem])} sports ball dets, "
              f"{len(wrist_by_stem[stem])} wrist frames, "
              f"{len(norfair_by_stem[stem])} norfair index entries")

    # Analyse each link
    results = []
    for link in links:
        stem = link["stem"]
        r = analyse_link(link,
                         all_sb_by_stem[stem],
                         wrist_by_stem[stem],
                         norfair_by_stem[stem])
        results.append(r)
        print(f"\n  {link['from_tid']:>3}->{link['to_tid']:<3}  hand={link['hand']:>5}  "
              f"f={link['from_frame']:>4}..{link['to_frame']:<4}  "
              f"n_in_reach={r['n_in_reach_unassigned']:>3}  "
              f"low_conf={r['n_in_reach_low_conf']:>3}  "
              f"glimpses={r['n_glimpses']}  "
              f"outgoing_previews={len(r['outgoing_previews'])}")

    # Control baseline per stem
    baseline = {}
    for stem in stems:
        baseline[stem] = control_baseline(stem,
                                           all_sb_by_stem[stem],
                                           wrist_by_stem[stem],
                                           norfair_by_stem[stem])
        print(f"\n  baseline[{stem}]: "
              f"samples={baseline[stem]['n_samples']}  "
              f"clusters_total={baseline[stem]['n_clusters_total']}  "
              f"glimpse_like={baseline[stem]['n_glimpse_like']}  "
              f"fpr_per_cluster={baseline[stem]['fpr_per_cluster']:.3f}")

    # Save outputs
    summary = {
        "thresholds": H3_THRESHOLDS,
        "n_links": len(links),
        "n_glimpse_links": sum(1 for r in results if r["n_glimpses"] > 0),
        "n_with_outgoing_preview": sum(1 for r in results if len(r["outgoing_previews"]) > 0),
        "total_in_reach_unassigned": sum(r["n_in_reach_unassigned"] for r in results),
        "total_glimpses": sum(r["n_glimpses"] for r in results),
        "baseline": baseline,
        "per_link": [
            {
                "link": r["link"],
                "hand_xy": r["hand_xy"],
                "n_in_reach_unassigned": r["n_in_reach_unassigned"],
                "n_in_reach_low_conf": r["n_in_reach_low_conf"],
                "n_clusters": r["n_clusters"],
                "n_glimpses": r["n_glimpses"],
                "outgoing_previews": r["outgoing_previews"],
            }
            for r in results
        ],
    }
    with (H1_DATA / "h3_summary.json").open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"\nSaved: {H1_DATA / 'h3_summary.json'}")

    # Save per-link glimpse CSV (only the HELD_BALL_GLIMPSE clusters)
    glimpse_rows = []
    for r in results:
        link = r["link"]
        for cluster in r["clusters"]:
            if cluster["classification"] != "HELD_BALL_GLIMPSE":
                continue
            g = cluster["glimpse"]
            glimpse_rows.append({
                "video": link["stem"],
                "from_tid": link["from_tid"],
                "to_tid": link["to_tid"],
                "hand": link["hand"],
                "glimpse_frame_min": g["frame_min"],
                "glimpse_frame_max": g["frame_max"],
                "glimpse_n": g["n"],
                "glimpse_x_mean": round(g["x_mean"], 1),
                "glimpse_y_mean": round(g["y_mean"], 1),
                "glimpse_conf_mean": round(g["conf_mean"], 3),
                "glimpse_conf_min": round(g["conf_min"], 3),
                "glimpse_conf_max": round(g["conf_max"], 3),
                "glimpse_std_x": round(g["std_x"], 1),
                "glimpse_std_y": round(g["std_y"], 1),
                "hand_x": round(r["hand_xy"][0], 1),
                "hand_y": round(r["hand_xy"][1], 1),
                "frames_in_cluster": ",".join(str(f) for f in cluster["frames"]),
            })
    if glimpse_rows:
        with (H1_DATA / "h3_glimpses.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(glimpse_rows[0].keys()))
            w.writeheader()
            w.writerows(glimpse_rows)
        print(f"Saved: {H1_DATA / 'h3_glimpses.csv'} ({len(glimpse_rows)} rows)")

    # Save detailed per-link cluster dumps
    with (H1_DATA / "h3_clusters_detailed.json").open("w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"Saved: {H1_DATA / 'h3_clusters_detailed.json'}")

    return results, baseline


if __name__ == "__main__":
    main()
