#!/usr/bin/env python3
"""H13 v2: Stricter cluster criterion with hand-specificity filter.

Hypothesis: the v2 (H3 stationary-cluster) criterion's false
positives (3/6 v2 CORROBORATED edges are h7v2_kept_ballistic) are
because the cluster is not specific to the relevant hand. The
41->43 case has 2 balls in the right hand that look like one
cluster.

A stricter H13 v2 criterion: the cluster must be at the EXACT
hand used by the edge AND no other hand should have cluster
activity simultaneously AND the cluster's spatial extent must be
tight (std_x, std_y < 15 px, consistent with a held ball).

If H13 v2 fires on real catch-throws but NOT on identity switches,
then H3's stationary-cluster is salvageable with stricter filters.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Reuse functions from h13
import sys
sys.path.insert(0, str(WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "scripts"))
from h13_low_conf_corroboration import (
    H13_V2_THRESHOLDS, V4D_LINKS_PATH, H7V2_RECLASS_PATHS, H7V2_EDGES_PATHS,
    TRACKLET_FEATURES_PATH,
    load_sports_ball, load_wrist_frames, load_tracklets, find_closest_wrist,
    get_v4d_links, get_h7v2_reclassified, get_h7v2_not_reclassified,
    cluster_dets_in_reach,
)

H13_V2_STRICT = {
    "MIN_CLUSTER_DETECTIONS": 3,
    "MAX_CLUSTER_SPAN_FRAMES": 60,
    "MAX_GAP_IN_CLUSTER": 12,
    "STATIONARY_RADIUS_PX": 30,
    "STATIONARY_MAX_STD_PX": 25,   # slightly tighter than H3 v3's 30
    "OTHER_HAND_MAX_LOW_CONF": 2,  # allow a few low-conf dets at the OTHER hand
    "LOW_CONF_THRESHOLD": 0.5,
    "HAND_REACH_PX": 108,
    "GAP_PAD_FRAMES": 5,
    "MAX_GAP_FRAMES": 60,
}

OTHER_HAND = {"left": "right", "right": "left"}


def analyse_edge_strict(edge, sb_dets, wrist_frames, tracklets, baseline_mean_conc=0.2):
    """Like v2 but with hand-specificity filter."""
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
    if edge.get("gap") is None:
        edge["gap"] = to_f - from_f
        gap = edge["gap"]

    if gap > H13_V2_STRICT["MAX_GAP_FRAMES"]:
        return {"edge": edge, "skipped": f"gap>{H13_V2_STRICT['MAX_GAP_FRAMES']}"}

    w_mid = find_closest_wrist(wrist_frames, (from_f + to_f) // 2)
    if w_mid is None or hand not in w_mid:
        if w_mid is None:
            return {"edge": edge, "skipped": "no_wrist_data"}
        if "left" in w_mid and "right" in w_mid:
            lx, ly = w_mid["left"]
            rx, ry = w_mid["right"]
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

    f1 = from_f - H13_V2_STRICT["GAP_PAD_FRAMES"]
    f2 = to_f + H13_V2_STRICT["GAP_PAD_FRAMES"]

    # Cluster in-reach low-conf dets
    low_conf_in_reach = []
    for (fr, x, y, c) in sb_dets:
        if fr < f1 or fr > f2:
            continue
        if c >= H13_V2_STRICT["LOW_CONF_THRESHOLD"]:
            continue
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d <= H13_V2_STRICT["HAND_REACH_PX"]:
            low_conf_in_reach.append((fr, x, y, c))

    # Apply stricter stationary criterion (tighter std)
    clusters = cluster_dets_in_reach_strict(
        low_conf_in_reach,
        H13_V2_STRICT["HAND_REACH_PX"],
        H13_V2_STRICT["STATIONARY_MAX_STD_PX"],
    )

    # Other-hand check: no low-conf dets at the OTHER hand in the window
    other_hand = OTHER_HAND.get(hand.split("_")[0])  # "left_inferred" -> "left"
    other_hand_low_conf = -1
    other_hand_clear = True
    if other_hand and other_hand in w_mid:
        ox, oy = w_mid[other_hand]
        other_hand_low_conf = 0
        for (fr, x, y, c) in sb_dets:
            if fr < f1 or fr > f2:
                continue
            if c >= H13_V2_STRICT["LOW_CONF_THRESHOLD"]:
                continue
            d = ((x - ox) ** 2 + (y - oy) ** 2) ** 0.5
            if d <= H13_V2_STRICT["HAND_REACH_PX"]:
                other_hand_low_conf += 1
        other_hand_clear = (other_hand_low_conf <= H13_V2_STRICT["OTHER_HAND_MAX_LOW_CONF"])

    if len(clusters) > 0 and other_hand_clear:
        classification = "STRICT_CORROBORATED"
    elif len(clusters) > 0 and not other_hand_clear:
        classification = "AMBIGUOUS_OTHER_HAND"  # cluster at hand, but also at other
    else:
        classification = "NOT_CORROBORATED"

    return {
        "edge": edge,
        "hand_xy": (round(wx, 1), round(wy, 1)),
        "from_f": from_f,
        "to_f": to_f,
        "window": (f1, f2),
        "n_in_reach": len(low_conf_in_reach),
        "n_clusters": len(clusters),
        "clusters": clusters,
        "other_hand_low_conf": other_hand_low_conf,
        "other_hand_clear": other_hand_clear,
        "classification": classification,
    }


def cluster_dets_in_reach_strict(dets, reach_radius, max_std):
    """Like cluster_dets_in_reach but with stricter std (15 instead of 30)."""
    if not dets:
        return []
    dets = sorted(dets)
    clusters = []
    cur = []
    for d in dets:
        if cur and d[0] - cur[-1][0] > 12:
            clusters.append(cur)
            cur = []
        cur.append(d)
    if cur:
        clusters.append(cur)
    out = []
    for cl in clusters:
        if len(cl) < 3:
            continue
        if max(d[0] for d in cl) - min(d[0] for d in cl) > 60:
            continue
        xs = [d[1] for d in cl]
        ys = [d[2] for d in cl]
        cfs = [d[3] for d in cl]
        std_x = statistics.pstdev(xs)
        std_y = statistics.pstdev(ys)
        if std_x > max_std:
            continue
        if std_y > max_std:
            continue
        mean_cf = statistics.mean(cfs)
        if mean_cf >= 0.5:
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
        })
    return out


def main():
    print("H13 v2: stricter cluster criterion with hand-specificity filter")
    print(f"  thresholds: {H13_V2_STRICT}")

    edges = (get_v4d_links()
             + get_h7v2_reclassified()
             + get_h7v2_not_reclassified())
    print(f"  total edges: {len(edges)}")

    by_stem = defaultdict(list)
    for e in edges:
        by_stem[e["stem"]].append(e)

    all_results = []
    for stem, stem_edges in by_stem.items():
        print(f"\n  --- {stem} ---")
        sb_dets = load_sports_ball(stem)
        wrist_frames = load_wrist_frames(stem)
        tracklets = load_tracklets(stem)

        for e in stem_edges:
            r = analyse_edge_strict(e, sb_dets, wrist_frames, tracklets)
            all_results.append(r)
            if "skipped" in r:
                continue
            print(f"    {r['edge']['source']:>20}  {e['from_tid']:>3}->{e['to_tid']:<3}  "
                  f"hand={e['hand']:>15}  f={r['from_f']:>4}..{r['to_f']:<4}  "
                  f"class={r['classification']:>30}  "
                  f"in_reach={r['n_in_reach']:>3}  cl={r['n_clusters']}  "
                  f"other_hand_lc={r['other_hand_low_conf']}")

    by_source = defaultdict(list)
    for r in all_results:
        by_source[r["edge"]["source"]].append(r)
    print("\n  === per-source summary (strict v2) ===")
    for source, rs in by_source.items():
        non_skip = [r for r in rs if "skipped" not in r]
        n_cor = sum(1 for r in non_skip if r["classification"] == "STRICT_CORROBORATED")
        n_amb = sum(1 for r in non_skip if r["classification"] == "AMBIGUOUS_OTHER_HAND")
        n_no = sum(1 for r in non_skip if r["classification"] == "NOT_CORROBORATED")
        print(f"    {source:>20}: total={len(rs)}, "
              f"STRICT_CORROBORATED={n_cor}, "
              f"AMBIGUOUS_OTHER_HAND={n_amb}, "
              f"NOT_CORROBORATED={n_no}")

    # Save
    out = {
        "thresholds": H13_V2_STRICT,
        "n_total_edges": len(edges),
        "per_source_summary": {
            source: {
                "n_total": len(rs),
                "n_strict_corroborated": sum(1 for r in rs if r.get("classification") == "STRICT_CORROBORATED"),
                "n_ambiguous_other_hand": sum(1 for r in rs if r.get("classification") == "AMBIGUOUS_OTHER_HAND"),
                "n_not_corroborated": sum(1 for r in rs if r.get("classification") == "NOT_CORROBORATED"),
            }
            for source, rs in by_source.items()
        },
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
                "classification": r.get("classification", "SKIPPED"),
                "n_in_reach": r.get("n_in_reach", 0),
                "n_clusters": r.get("n_clusters", 0),
                "other_hand_low_conf": r.get("other_hand_low_conf", 0),
                "other_hand_clear": r.get("other_hand_clear", True),
            }
            for r in all_results
        ],
    }
    out_path = H1_DATA / "h13v2_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
