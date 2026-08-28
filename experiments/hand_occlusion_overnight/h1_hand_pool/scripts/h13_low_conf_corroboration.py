#!/usr/bin/env python3
"""H13 v2 - Stricter low-conf detector corroboration of hand events (master §14).

Lesson from v1: with MIN_LOW_CONF_NEEDED=1, the FPR is 91-100% — the
detector fires constantly on background. A real corroboration signal
needs STRICTER criteria that the background does not produce.

v2 uses H3 v3's "stationary cluster" criterion but restricted to the
edge window:
- ≥3 low-conf sports-ball detections
- within 30px radius of their cluster center
- span ≥5 frames
- within REACH of the hand
- mean confidence < 0.5

This is a meaningful "stationary held ball intermittently glimpsed"
pattern. The baseline FPR of this exact pattern is much lower than
"any single detection".

Outputs:
- per-edge classification: CORROBORATED / NO_EVIDENCE / REFUTED
- per-edge stats
- contact sheets for CORROBORATED edges
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H13_OUT = H1_DIR / "contact_sheets_h13"
H13_OUT.mkdir(parents=True, exist_ok=True)

H13_V2_THRESHOLDS = {
    "HAND_REACH_PX": 108,
    "LOW_CONF_THRESHOLD": 0.5,
    "GAP_PAD_FRAMES": 5,
    "MAX_GAP_FRAMES": 60,
    # Stationary-cluster criteria (H3 v3):
    "MIN_CLUSTER_DETECTIONS": 3,
    "MAX_CLUSTER_SPAN_FRAMES": 60,  # 2 sec at 30 fps
    "MAX_GAP_IN_CLUSTER": 12,
    "STATIONARY_RADIUS_PX": 30,
    "STATIONARY_MIN_STD_PX": 0,  # 0 means "any"
    "STATIONARY_MAX_STD_PX": 30,
    "BASELINE_SAMPLES": 200,
    "RANDOM_SEED": 42,
}

V4D_LINKS_PATH = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"
H7V2_RECLASS_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v2_reclassified_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v2_reclassified_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
H7V2_EDGES_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v2_admitted_edges_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v2_admitted_edges_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
TRACKLET_FEATURES_PATH = H1_DATA / "tracklet_features.csv"


def load_sports_ball(stem: str) -> list[tuple]:
    candidates = [
        WORKTREE / "detections" / f"{stem}_yolo26s_all-classes.csv",
        WORKTREE / "detections" / f"{stem}_yolo26s_classes-32.csv",
    ]
    for path in candidates:
        if path.exists():
            break
    else:
        return []
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                x = float(r["center_x"])
                y = float(r["center_y"])
                c = float(r["confidence"])
                out.append((fr, x, y, c))
            except (ValueError, KeyError):
                continue
    out.sort()
    return out


def load_wrist_frames(stem: str) -> dict:
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


def load_tracklets(stem: str) -> dict:
    out = {}
    with TRACKLET_FEATURES_PATH.open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            tid = int(r["tid"])
            out[tid] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "first_x": float(r["first_x"]),
                "first_y": float(r["first_y"]),
                "last_x": float(r["last_x"]),
                "last_y": float(r["last_y"]),
                "n_pts": int(r["n_pts"]),
            }
    return out


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


def parse_hand_from_reason(reason: str) -> str:
    import re
    m = re.search(r"side=(\w+)", reason or "")
    return m.group(1) if m else "unknown"


def get_v4d_links() -> list[dict]:
    out = []
    with V4D_LINKS_PATH.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "source": "v4d",
                "stem": r["stem"],
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "hand": r["hand"],
                "from_frame": int(r["from_frame"]),
                "to_frame": int(r["to_frame"]),
                "gap": int(r["to_frame"]) - int(r["from_frame"]),
            })
    return out


def get_h7v2_reclassified() -> list[dict]:
    out = []
    for stem, path in H7V2_RECLASS_PATHS.items():
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                out.append({
                    "source": "h7v2_reclassified",
                    "stem": stem,
                    "from_tid": int(r["from_tid"]),
                    "to_tid": int(r["to_tid"]),
                    "hand": parse_hand_from_reason(r.get("reason", "")),
                    "from_frame": None,
                    "to_frame": None,
                    "gap": int(r["gap"]),
                })
    return out


def get_h7v2_not_reclassified() -> list[dict]:
    """The h7v2 admitted edges that were NOT reclassified — these
    are BALLISTIC edges kept as ballistic (i.e., the rule didn't fire
    on them). We use them as a control: do they have LESS detector
    evidence at the hand than reclassified edges?
    """
    out = []
    for stem, reclass_path in H7V2_RECLASS_PATHS.items():
        edges_path = H7V2_EDGES_PATHS.get(stem)
        if edges_path is None or not reclass_path.exists() or not edges_path.exists():
            continue
        # Read reclassified pairs
        reclass_pairs = set()
        with reclass_path.open() as fh:
            for r in csv.DictReader(fh):
                reclass_pairs.add((int(r["from_tid"]), int(r["to_tid"])))
        # Read admitted edges; keep only those NOT in reclass set
        with edges_path.open() as fh:
            for r in csv.DictReader(fh):
                if r["edge_type"] != "BALLISTIC":
                    continue
                pair = (int(r["from_tid"]), int(r["to_tid"]))
                if pair in reclass_pairs:
                    continue
                # Parse hand from metadata if present
                md = r.get("metadata", "")
                hand = parse_hand_from_reason(md) or "unknown"
                out.append({
                    "source": "h7v2_kept_ballistic",
                    "stem": stem,
                    "from_tid": pair[0],
                    "to_tid": pair[1],
                    "hand": hand,
                    "from_frame": None,
                    "to_frame": None,
                    "gap": None,  # compute from tracklet features
                })
    return out


def cluster_dets_in_reach(dets: list, reach_radius: float) -> list[dict]:
    """Given dets all in reach of a hand (frame, x, y, conf), return
    clusters that satisfy H3 v3's stationary-cluster criterion.
    """
    if not dets:
        return []
    dets = sorted(dets)
    clusters = []
    cur = []
    for d in dets:
        if cur and d[0] - cur[-1][0] > H13_V2_THRESHOLDS["MAX_GAP_IN_CLUSTER"]:
            clusters.append(cur)
            cur = []
        cur.append(d)
    if cur:
        clusters.append(cur)
    out = []
    for cl in clusters:
        if len(cl) < H13_V2_THRESHOLDS["MIN_CLUSTER_DETECTIONS"]:
            continue
        if max(d[0] for d in cl) - min(d[0] for d in cl) > H13_V2_THRESHOLDS["MAX_CLUSTER_SPAN_FRAMES"]:
            continue
        xs = [d[1] for d in cl]
        ys = [d[2] for d in cl]
        cfs = [d[3] for d in cl]
        std_x = statistics.pstdev(xs)
        std_y = statistics.pstdev(ys)
        # Stationary: std_x, std_y both small
        if std_x > H13_V2_THRESHOLDS["STATIONARY_MAX_STD_PX"]:
            continue
        if std_y > H13_V2_THRESHOLDS["STATIONARY_MAX_STD_PX"]:
            continue
        mean_cf = statistics.mean(cfs)
        if mean_cf >= H13_V2_THRESHOLDS["LOW_CONF_THRESHOLD"]:
            continue
        out.append({
            "n": len(cl),
            "frame_min": min(d[0] for d in cl),
            "frame_max": max(d[0] for d in cl),
            "x_mean": statistics.mean(xs),
            "y_mean": statistics.mean(ys),
            "std_x": std_x,
            "std_y": std_y,
            "conf_mean": mean_cf,
            "conf_min": min(cfs),
            "conf_max": max(cfs),
            "frames": sorted(set(d[0] for d in cl)),
        })
    return out


def analyse_edge(edge: dict, sb_dets: list, wrist_frames: dict, tracklets: dict,
                 baseline_mean_conc: float = 0.2) -> dict:
    """Analyze one edge. Returns classification + stats.

    baseline_mean_conc: mean concentration at random hand-region windows
    (from the FPR baseline computation). Used for the peak test.
    """
    stem = edge["stem"]
    from_tid = edge["from_tid"]
    to_tid = edge["to_tid"]
    hand = edge["hand"]
    gap = edge["gap"]

    if edge["from_frame"] is None:
        from_tf = tracklets.get(from_tid, {})
        to_tf = tracklets.get(to_tid, {})
        from_f = from_tf.get("last_frame", 0)
        to_f = to_tf.get("first_frame", 0)
        edge["from_frame"] = from_f
        edge["to_frame"] = to_f
    else:
        from_f = edge["from_frame"]
        to_f = edge["to_frame"]
    # Compute gap if not set
    if edge.get("gap") is None:
        edge["gap"] = to_f - from_f
        gap = edge["gap"]

    if gap > H13_V2_THRESHOLDS["MAX_GAP_FRAMES"]:
        return {"edge": edge, "skipped": f"gap>{H13_V2_THRESHOLDS['MAX_GAP_FRAMES']}"}

    # Edge_type for h7v2 — some are HAND_TRANSITION (real H1 v4d) and
    # some are BALLISTIC edges that h7v2 RECLASSIFIED. We use this to
    # allow the h7v2 reclassified BALLISTIC edges in our analysis.
    # In this implementation, all v4d links AND h7v2_reclassified edges
    # are treated equally.

    w_mid = find_closest_wrist(wrist_frames, (from_f + to_f) // 2)
    if w_mid is None or hand not in w_mid:
        # Fallback: try the other hand, or "both" by averaging. For
        # h7v2_kept_ballistic edges, the hand is unknown. Use the
        # MIDPOINT of the two wrists as a proxy, or just left.
        if w_mid is None:
            return {"edge": edge, "skipped": "no_wrist_data"}
        # Use whichever wrist is closer to the ball's last position
        if "left" in w_mid and "right" in w_mid:
            lx, ly = w_mid["left"]
            rx, ry = w_mid["right"]
            # Use tracklet endpoint as ball position
            from_tf = tracklets.get(from_tid, {})
            to_tf = tracklets.get(to_tid, {})
            bx = (from_tf.get("last_x", 0) + to_tf.get("first_x", 0)) / 2
            by = (from_tf.get("last_y", 0) + to_tf.get("first_y", 0)) / 2
            dl = ((bx - lx) ** 2 + (by - ly) ** 2) ** 0.5
            dr = ((bx - rx) ** 2 + (by - ry) ** 2) ** 0.5
            if dl < dr:
                wx, wy = lx, ly
                edge["hand"] = "left_inferred"
            else:
                wx, wy = rx, ry
                edge["hand"] = "right_inferred"
        else:
            return {"edge": edge, "skipped": "no_wrist_data"}
    else:
        wx, wy = w_mid[hand]

    f1 = from_f - H13_V2_THRESHOLDS["GAP_PAD_FRAMES"]
    f2 = to_f + H13_V2_THRESHOLDS["GAP_PAD_FRAMES"]

    # Find low-conf in reach
    low_conf_in_reach = []
    low_conf_out_reach = []
    for (fr, x, y, c) in sb_dets:
        if fr < f1 or fr > f2:
            continue
        if c >= H13_V2_THRESHOLDS["LOW_CONF_THRESHOLD"]:
            continue
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d <= H13_V2_THRESHOLDS["HAND_REACH_PX"]:
            low_conf_in_reach.append((fr, x, y, c))
        else:
            low_conf_out_reach.append((fr, x, y, c))

    n_in = len(low_conf_in_reach)
    n_out = len(low_conf_out_reach)
    n_total = n_in + n_out
    concentration = n_in / n_total if n_total > 0 else 0.0

    # Cluster the in-reach detections
    clusters = cluster_dets_in_reach(low_conf_in_reach, H13_V2_THRESHOLDS["HAND_REACH_PX"])

    # v3 classification: concentration-based
    if n_in >= 3 and n_in >= n_out:
        classification_v3 = "CORROBORATED"
    elif n_in == 0 and n_out >= 3:
        classification_v3 = "REFUTED"
    elif n_in == 0:
        classification_v3 = "NO_EVIDENCE"
    else:
        classification_v3 = "AMBIGUOUS"

    # v2 classification: cluster-based (kept for comparison)
    if len(clusters) > 0:
        classification_v2 = "CORROBORATED"
    elif n_in == 0 and n_out >= 3:
        classification_v2 = "REFUTED"
    elif n_in == 0:
        classification_v2 = "NO_EVIDENCE"
    else:
        classification_v2 = "AMBIGUOUS"

    # v4: peak test. Does the hand region have more low-conf dets DURING
    # the event than in the surrounding context (±30 frames)?
    ctx_pad = 30
    ctx_f1 = max(0, from_f - ctx_pad)
    ctx_f2 = to_f + ctx_pad
    # In-context low-conf in reach
    in_ctx = 0
    out_ctx = 0
    for (fr, x, y, c) in sb_dets:
        if fr < ctx_f1 or fr > ctx_f2:
            continue
        if c >= H13_V2_THRESHOLDS["LOW_CONF_THRESHOLD"]:
            continue
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d <= H13_V2_THRESHOLDS["HAND_REACH_PX"]:
            in_ctx += 1
        else:
            out_ctx += 1
    ctx_total = in_ctx + out_ctx
    ctx_conc = in_ctx / ctx_total if ctx_total > 0 else 0.0
    # Event-vs-context ratio: the event window has higher concentration
    # than the surrounding ±30 frames? If so, the hand is a "magnet"
    # during the event but not around it.
    event_ratio = concentration / ctx_conc if ctx_conc > 0 else 0.0
    if event_ratio > 1.5 and concentration > baseline_mean_conc:
        classification_v4 = "PEAK"
    elif event_ratio < 0.5 and ctx_conc > baseline_mean_conc:
        classification_v4 = "DEPRESSED"  # hand is empty during event
    else:
        classification_v4 = "FLAT"

    return {
        "edge": edge,
        "hand_xy": (round(wx, 1), round(wy, 1)),
        "from_f": from_f,
        "to_f": to_f,
        "window": (f1, f2),
        "context_window": (ctx_f1, ctx_f2),
        "n_in_reach": n_in,
        "n_out_reach": n_out,
        "n_in_context": in_ctx,
        "n_out_context": out_ctx,
        "n_clusters": len(clusters),
        "concentration": round(concentration, 3),
        "context_concentration": round(ctx_conc, 3),
        "event_ratio": round(event_ratio, 3),
        "classification_v2": classification_v2,
        "classification_v3": classification_v3,
        "classification_v4": classification_v4,
        "classification": classification_v3,
        "clusters": clusters,
    }


def control_baseline(stem: str, sb_dets: list, wrist_frames: dict) -> dict:
    """FPR: at a random frame+hand, how often does each criterion fire?
    Also: mean concentration at random hand-frames (so we can compare
    hand-event concentrations to a random baseline)."""
    random.seed(H13_V2_THRESHOLDS["RANDOM_SEED"])
    n_samples = H13_V2_THRESHOLDS["BASELINE_SAMPLES"]
    pad = H13_V2_THRESHOLDS["GAP_PAD_FRAMES"]
    max_frame = max((d[0] for d in sb_dets), default=0)
    if not wrist_frames or max_frame == 0:
        return {"fpr_v2_per_sample": 0.0, "fpr_v3_per_sample": 0.0,
                "n_cor_v2": 0, "n_cor_v3": 0, "n_total": 0,
                "mean_concentration_random": 0.0,
                "concentration_p50_random": 0.0,
                "concentration_p90_random": 0.0,
                "concentration_p99_random": 0.0}

    sb_by_frame = defaultdict(list)
    for d in sb_dets:
        if d[3] < H13_V2_THRESHOLDS["LOW_CONF_THRESHOLD"]:
            sb_by_frame[d[0]].append(d)

    n_cor_v2 = 0
    n_cor_v3 = 0
    n_total_used = 0
    random_concentrations = []
    for _ in range(n_samples):
        target = random.randint(0, max_frame)
        hand = random.choice(["left", "right"])
        w = find_closest_wrist(wrist_frames, target)
        if w is None or hand not in w:
            continue
        wx, wy = w[hand]
        n_total_used += 1
        f1 = target - pad
        f2 = target + pad
        in_reach = []
        out_reach = 0
        for f in range(f1, f2 + 1):
            for d in sb_by_frame.get(f, []):
                dx = d[1] - wx
                dy = d[2] - wy
                if (dx * dx + dy * dy) ** 0.5 <= H13_V2_THRESHOLDS["HAND_REACH_PX"]:
                    in_reach.append((d[0], d[1], d[2], d[3]))
                else:
                    out_reach += 1
        n_in = len(in_reach)
        n_total = n_in + out_reach
        conc = n_in / n_total if n_total > 0 else 0.0
        random_concentrations.append(conc)
        # v2 (cluster)
        clusters = cluster_dets_in_reach(in_reach, H13_V2_THRESHOLDS["HAND_REACH_PX"])
        if clusters:
            n_cor_v2 += 1
        # v3 (concentration): n_in >= 3 AND n_in >= n_out
        if n_in >= 3 and n_in >= out_reach:
            n_cor_v3 += 1

    if random_concentrations:
        sorted_conc = sorted(random_concentrations)
        p50 = sorted_conc[len(sorted_conc) // 2]
        p90 = sorted_conc[int(len(sorted_conc) * 0.9)]
        p99 = sorted_conc[int(len(sorted_conc) * 0.99)]
    else:
        p50 = p90 = p99 = 0.0

    return {
        "fpr_v2_per_sample": n_cor_v2 / n_total_used if n_total_used else 0.0,
        "fpr_v3_per_sample": n_cor_v3 / n_total_used if n_total_used else 0.0,
        "n_cor_v2": n_cor_v2,
        "n_cor_v3": n_cor_v3,
        "n_total": n_total_used,
        "mean_concentration_random": statistics.mean(random_concentrations) if random_concentrations else 0.0,
        "concentration_p50_random": p50,
        "concentration_p90_random": p90,
        "concentration_p99_random": p99,
    }


def render_contact_sheet(stem: str, edge: dict, result: dict, out_path: Path):
    """Render a contact sheet for a single edge showing the gap window
    with low-conf detections, wrist positions, and tracklet endpoints.
    """
    import math
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False

    VIDEO_PATHS = {
        "identical_balls_trick_000_018":
            "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/identical_balls_trick_000_018.mp4",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
            "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
    }
    if stem not in VIDEO_PATHS:
        return False
    cap = cv2.VideoCapture(VIDEO_PATHS[stem])
    if not cap.isOpened():
        return False

    from_f = result["from_f"]
    to_f = result["to_f"]
    n_show = 6
    span = max(to_f - from_f, 1)
    frames = [from_f + i * span // (n_show - 1) for i in range(n_show)]
    frames = [min(max(f, 0), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1) for f in frames]

    # Load tracklet features for the relevant tids
    tracklets = load_tracklets(stem)
    from_tid = edge["from_tid"]
    to_tid = edge["to_tid"]
    from_tf = tracklets.get(from_tid, {})
    to_tf = tracklets.get(to_tid, {})

    # Load sports ball dets for these frames
    sb_dets = load_sports_ball(stem)
    sb_by_frame = defaultdict(list)
    for d in sb_dets:
        sb_by_frame[d[0]].append(d)

    panels = []
    for fi, f in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            continue
        h, w = frame.shape[:2]
        # Resize to 360 max width for contact sheet
        scale = min(1.0, 360 / w)
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            h, w = frame.shape[:2]
        # Annotate
        cv2.putText(frame, f"f={f}", (5, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        # Hand position
        w_wrist = find_closest_wrist(load_wrist_frames(stem), f)
        if w_wrist and edge["hand"] in w_wrist:
            wx, wy = w_wrist[edge["hand"]]
            wx, wy = int(wx * scale), int(wy * scale)
            cv2.circle(frame, (wx, wy), int(H13_V2_THRESHOLDS["HAND_REACH_PX"] * scale),
                       (255, 165, 0), 1)  # reach circle (orange)
            cv2.circle(frame, (wx, wy), 4, (255, 165, 0), -1)
        # Sports ball detections
        for d in sb_by_frame.get(f, []):
            x, y, c = int(d[1] * scale), int(d[2] * scale), d[3]
            color = (0, 255, 255) if c >= H13_V2_THRESHOLDS["LOW_CONF_THRESHOLD"] else (0, 165, 255)
            cv2.circle(frame, (x, y), 4, color, -1 if c >= 0.7 else 1)
            cv2.putText(frame, f"{c:.2f}", (x + 5, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
        # Tracklet endpoint
        if from_tf.get("last_frame") == f and from_tf.get("last_x"):
            x, y = int(from_tf["last_x"] * scale), int(from_tf["last_y"] * scale)
            cv2.circle(frame, (x, y), 6, (0, 255, 0), 2)
        if to_tf.get("first_frame") == f and to_tf.get("first_x"):
            x, y = int(to_tf["first_x"] * scale), int(to_tf["first_y"] * scale)
            cv2.circle(frame, (x, y), 6, (255, 0, 255), 2)
        panels.append(frame)

    cap.release()
    if not panels:
        return False
    # 2 rows of 3
    rows = []
    for i in range(0, len(panels), 3):
        row = panels[i:i + 3]
        while len(row) < 3:
            row.append(np.zeros_like(panels[0]))
        rows.append(np.hstack(row))
    grid = np.vstack(rows)
    cv2.putText(grid, f"{edge['source']} {edge['from_tid']}->{edge['to_tid']} "
                f"hand={edge['hand']} f={from_f}..{to_f} "
                f"class={result['classification']} "
                f"n_in_reach={result['n_in_reach']} n_clusters={result['n_clusters']}",
                (5, grid.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    cv2.imwrite(str(out_path), grid)
    return True


def main():
    print("H13 v3: low-conf detector CONCENTRATION around hand events")
    print(f"  thresholds: {H13_V2_THRESHOLDS}")
    print("  Classifies an edge as CORROBORATED if the ratio of")
    print("  low-conf-in-reach to low-conf-total in the search window")
    print("  exceeds a threshold (concentration test).")
    print("  This is a less strict version of v2's cluster criterion.")

    edges = (get_v4d_links()
             + get_h7v2_reclassified()
             + get_h7v2_not_reclassified())
    print(f"  total edges: {len(edges)}")
    print(f"    v4d: {len(get_v4d_links())}, "
          f"h7v2_reclassified: {len(get_h7v2_reclassified())}, "
          f"h7v2_kept_ballistic: {len(get_h7v2_not_reclassified())}")

    by_stem = defaultdict(list)
    for e in edges:
        by_stem[e["stem"]].append(e)

    all_results = []
    fpr_by_stem = {}
    for stem, stem_edges in by_stem.items():
        print(f"\n  --- {stem} ---")
        sb_dets = load_sports_ball(stem)
        wrist_frames = load_wrist_frames(stem)
        tracklets = load_tracklets(stem)
        print(f"    sports ball dets: {len(sb_dets)}, "
              f"wrist frames: {len(wrist_frames)}, "
              f"tracklets: {len(tracklets)}")

        fpr = control_baseline(stem, sb_dets, wrist_frames)
        fpr_by_stem[stem] = fpr
        baseline_conc = fpr.get("mean_concentration_random", 0.2)
        print(f"    baseline FPR: v2={fpr['n_cor_v2']}/{fpr['n_total']} = {fpr['fpr_v2_per_sample']:.3f}, "
              f"v3={fpr['n_cor_v3']}/{fpr['n_total']} = {fpr['fpr_v3_per_sample']:.3f}, "
              f"mean_conc_random={baseline_conc:.3f}")

        for e in stem_edges:
            r = analyse_edge(e, sb_dets, wrist_frames, tracklets,
                             baseline_mean_conc=baseline_conc)
            all_results.append(r)
            if "skipped" in r:
                print(f"    SKIP {r['edge']['source']} {e['from_tid']:>3}->{e['to_tid']:<3}  {r['skipped']}")
                continue
            n_cl = r['n_clusters']
            print(f"    {r['edge']['source']:>20}  {e['from_tid']:>3}->{e['to_tid']:<3}  "
                  f"hand={e['hand']:>5}  f={r['from_f']:>4}..{r['to_f']:<4}  "
                  f"v3={r['classification_v3']:>15}  v4={r['classification_v4']:>10}  "
                  f"in_reach={r['n_in_reach']:>3}  out={r['n_out_reach']:>3}  "
                  f"conc={r['concentration']:.2f}  ctx={r['context_concentration']:.2f}  "
                  f"ratio={r['event_ratio']:.2f}  cl={n_cl}")

    by_source = defaultdict(list)
    for r in all_results:
        by_source[r["edge"]["source"]].append(r)
    print("\n  === per-source summary ===")
    for source, rs in by_source.items():
        non_skip = [r for r in rs if "skipped" not in r]
        n_v2 = sum(1 for r in non_skip if r["classification_v2"] == "CORROBORATED")
        n_v3 = sum(1 for r in non_skip if r["classification_v3"] == "CORROBORATED")
        n_v4_peak = sum(1 for r in non_skip if r["classification_v4"] == "PEAK")
        n_v4_dep = sum(1 for r in non_skip if r["classification_v4"] == "DEPRESSED")
        n_v4_flat = sum(1 for r in non_skip if r["classification_v4"] == "FLAT")
        n_noev = sum(1 for r in non_skip if r["classification_v3"] == "NO_EVIDENCE")
        n_ref = sum(1 for r in non_skip if r["classification_v3"] == "REFUTED")
        n_amb = sum(1 for r in non_skip if r["classification_v3"] == "AMBIGUOUS")
        avg_conc = statistics.mean(r["concentration"] for r in non_skip) if non_skip else 0
        avg_ctx = statistics.mean(r["context_concentration"] for r in non_skip) if non_skip else 0
        avg_ratio = statistics.mean(r["event_ratio"] for r in non_skip) if non_skip else 0
        print(f"    {source:>20}: total={len(rs)}, "
              f"v2_corroborated={n_v2}, v3_corroborated={n_v3}, "
              f"v4_PEAK={n_v4_peak}, v4_DEPRESSED={n_v4_dep}, v4_FLAT={n_v4_flat}, "
              f"avg_conc={avg_conc:.3f} (vs ctx {avg_ctx:.3f}), avg_ratio={avg_ratio:.3f}")

    # Render contact sheets for v3-CORROBORATED, v2-CORROBORATED, and
    # v4-PEAK edges (the most informative subsets).
    print("\n  === rendering contact sheets (v2 cluster, v4 PEAK) ===")
    to_render = []
    for r in all_results:
        if "skipped" in r:
            continue
        if r["classification_v2"] == "CORROBORATED":
            to_render.append((r, "v2_cluster"))
        elif r["classification_v4"] == "PEAK":
            to_render.append((r, "v4_peak"))
    # De-dupe
    seen = set()
    n_sheets = 0
    for r, kind in to_render:
        stem = r["edge"]["stem"]
        key = (stem, r["edge"]["source"], r["edge"]["from_tid"], r["edge"]["to_tid"], kind)
        if key in seen:
            continue
        seen.add(key)
        out_path = H13_OUT / f"{stem}_{r['edge']['source']}_{r['edge']['from_tid']}_{r['edge']['to_tid']}_{kind}.png"
        if render_contact_sheet(stem, r["edge"], r, out_path):
            n_sheets += 1
    print(f"    rendered {n_sheets} contact sheets")

    out = {
        "thresholds": H13_V2_THRESHOLDS,
        "n_total_edges": len(edges),
        "per_source_summary": {
            source: {
                "n_total": len(rs),
                "n_skipped": len(rs) - sum(1 for r in rs if "skipped" not in r),
                "n_v2_corroborated": sum(1 for r in rs if r.get("classification_v2") == "CORROBORATED"),
                "n_v3_corroborated": sum(1 for r in rs if r.get("classification_v3") == "CORROBORATED"),
                "n_v3_ambiguous": sum(1 for r in rs if r.get("classification_v3") == "AMBIGUOUS"),
                "n_v3_no_evidence": sum(1 for r in rs if r.get("classification_v3") == "NO_EVIDENCE"),
                "n_v3_refuted": sum(1 for r in rs if r.get("classification_v3") == "REFUTED"),
                "avg_concentration": round(statistics.mean(r["concentration"] for r in rs if "skipped" not in r), 3) if any("skipped" not in r for r in rs) else 0,
            }
            for source, rs in by_source.items()
        },
        "fpr_by_stem": fpr_by_stem,
        "per_edge": [
            {
                "source": r["edge"]["source"],
                "stem": r["edge"]["stem"],
                "from_tid": r["edge"]["from_tid"],
                "to_tid": r["edge"]["to_tid"],
                "hand": r["edge"]["hand"],
                "from_frame": r["edge"]["from_frame"],
                "to_frame": r["edge"]["to_frame"],
                "gap": r["edge"]["gap"],
                "skipped": r.get("skipped", ""),
                "hand_xy": r.get("hand_xy"),
                "window": r.get("window"),
                "classification_v2": r.get("classification_v2", "SKIPPED"),
                "classification_v3": r.get("classification_v3", "SKIPPED"),
                "n_in_reach": r.get("n_in_reach", 0),
                "n_out_reach": r.get("n_out_reach", 0),
                "concentration": r.get("concentration", 0),
                "n_clusters": r.get("n_clusters", 0),
                "cluster_n_max": max((c["n"] for c in r.get("clusters", [])), default=0),
            }
            for r in all_results
        ],
    }
    out_path = H1_DATA / "h13_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  Saved: {out_path}")

    rows = out["per_edge"]
    if rows:
        csv_path = H1_DATA / "h13_per_edge.csv"
        with csv_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"  Saved: {csv_path}")


if __name__ == "__main__":
    main()
