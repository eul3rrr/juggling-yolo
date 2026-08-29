#!/usr/bin/env python3
"""H126 — Post-H125v4 auxiliary filters: search for a (T_d, T_j, single_end_far)
combination that drops the 2 H59=wrong edges (6->15 identical, 10->11 YouTube)
without dropping any of the 5 visual REAL NEW V4 edges (4->7, 14->19, 53->58,
66->69, 44->53) and without losing useful NEW V4 recall.

HYPOTHESIS (declared BEFORE reading outcomes):
  The 2 H59=wrong H125 v4 admitted edges (6->15, 10->11 YT) have characteristic
  signatures NOT captured by H114 v1 strict (T_d, T_j):
    - 6->15 identical: end_d=47, start_d=15, sj=101 (low sj, low start_d)
    - 10->11 YouTube: end_d=2.2, start_d=120, sj=175 (very low end_d)
  These look like "tracker latched onto a held ball" — one endpoint is at the
  hand, the other is at a random location, but the spatial jump is moderate
  because the held ball is at the hand and the other is in mid-air nearby.

  A single-end-far filter (one end_d < FAR_NEAR, other end_d > FAR_FAR)
  should catch this pattern.

  Test on the 13 H125 v4 NEW admitted edges:
    - 5 visual REAL (must NOT be dropped): 4->7, 14->19, 53->58, 66->69, 44->53
    - 5 visual FALSE (good to drop): 9->12, 25->27, 54->57, 63->65, 73->75
    - 2 H59=wrong (must drop for precision): 6->15, 10->11 YT

  Goal: find (FAR_NEAR, FAR_FAR) that drops 6->15 and 10->11 YT
        without dropping 4->7, 14->19, 53->58, 66->69, 44->53.

  Also explore: combined H114 v1 strict + single-end-far.
  Also test: H59 review as "ground truth" AND visual QA as alternative ground truth.

Expected outcome:
  - Some (FAR_NEAR, FAR_FAR) combination catches both wrong edges
  - The 5 visual REAL edges all have BOTH ends within reach (none have min_d < 20)
  - Therefore: the operating point is achievable

Method:
  1. Load H125 v4 NEW admitted edges from h125_v4_summary.json
  2. For each (FAR_NEAR, FAR_FAR) combination, compute which edges are dropped
  3. Compare to ground truth (H59 review + visual QA)
  4. Report the optimal operating point
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

# Visual verdicts from H125 v4 contact sheet QA (H125_v4_report.md, table)
VISUAL_VERDICT = {
    ("identical_balls_trick_000_018", 4, 7): "REAL",
    ("identical_balls_trick_000_018", 9, 12): "FALSE",
    ("identical_balls_trick_000_018", 10, 11): "FALSE",
    ("identical_balls_trick_000_018", 14, 19): "REAL",
    ("identical_balls_trick_000_018", 25, 27): "FALSE",
    ("identical_balls_trick_000_018", 53, 58): "REAL",
    ("identical_balls_trick_000_018", 66, 69): "REAL",
    ("identical_balls_trick_000_018", 44, 53): "REAL",
    ("identical_balls_trick_000_018", 54, 57): "FALSE",
    ("identical_balls_trick_000_018", 63, 65): "FALSE",
    ("identical_balls_trick_000_018", 73, 75): "FALSE",
    ("identical_balls_trick_000_018", 6, 15): "FALSE",  # H59=wrong
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11): "FALSE",  # H59=wrong
}


def load_tracklet_features():
    tf = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for r in csv.DictReader(f):
            key = (r["stem"], int(r["tid"]))
            tf[key] = {
                "first_x": float(r["first_x"]) if r["first_x"] else None,
                "first_y": float(r["first_y"]) if r["first_y"] else None,
                "last_x": float(r["last_x"]) if r["last_x"] else None,
                "last_y": float(r["last_y"]) if r["last_y"] else None,
                "end_dist": float(r["end_dist"]) if r["end_dist"] else 999.0,
                "start_dist": float(r["start_dist"]) if r["start_dist"] else 999.0,
                "end_side": r.get("end_side", "") or "",
                "start_side": r.get("start_side", "") or "",
            }
    return tf


def load_h125_v4_new_edges():
    """Return list of (stem, src, tgt) for the 13 NEW V4 surviving edges."""
    return [
        ("identical_balls_trick_000_018", 25, 27),
        ("identical_balls_trick_000_018", 9, 12),
        ("identical_balls_trick_000_018", 66, 69),
        ("identical_balls_trick_000_018", 53, 58),
        ("identical_balls_trick_000_018", 54, 57),
        ("identical_balls_trick_000_018", 10, 11),
        ("identical_balls_trick_000_018", 44, 53),
        ("identical_balls_trick_000_018", 14, 19),
        ("identical_balls_trick_000_018", 6, 15),
        ("identical_balls_trick_000_018", 4, 7),
        ("identical_balls_trick_000_018", 63, 65),
        ("identical_balls_trick_000_018", 73, 75),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11),
    ]


def load_h59_review():
    review = {}
    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        for r in csv.DictReader(f):
            review[(r["stem"], int(r["source"]), int(r["candidate"]))] = r["label"]
    return review


def spatial_jump(src_last_xy, tgt_first_xy):
    if src_last_xy is None or tgt_first_xy is None:
        return None
    return math.hypot(tgt_first_xy[0] - src_last_xy[0], tgt_first_xy[1] - src_last_xy[1])


def h114_v1_strict_fires(s, t, T_d, T_j):
    """H114 v1 strict: fires if end_d > T_d AND start_d > T_d AND sj > T_j."""
    if s["last_x"] is None or t["first_x"] is None:
        return False
    ed, sd = s["end_dist"], t["start_dist"]
    sj = spatial_jump((s["last_x"], s["last_y"]), (t["first_x"], t["first_y"]))
    return ed > T_d and sd > T_d and sj > T_j


def single_end_far_fires(s, t, FAR_NEAR, FAR_FAR):
    """Single-end-far: fires if min(end_d, start_d) < FAR_NEAR AND max(end_d, start_d) > FAR_FAR.

    Pattern: one end is at the hand (low dist), other is far away.
    This is the "tracker latched onto a held ball" pattern.
    """
    ed, sd = s["end_dist"], t["start_dist"]
    return min(ed, sd) < FAR_NEAR and max(ed, sd) > FAR_FAR


def gap_far_fires(s, t, GAP_THRESHOLD):
    """H125 v3 high-err filter: fires if err > GAP_THRESHOLD (proxy for V-shape depth)."""
    # We don't have err in tracklet_features; just return False
    return False


def main():
    tf = load_tracklet_features()
    new_edges = load_h125_v4_new_edges()
    review = load_h59_review()

    # Annotate each edge with metadata
    annotated = []
    for stem, src, tgt in new_edges:
        s = tf.get((stem, src), {})
        t = tf.get((stem, tgt), {})
        if s.get("last_x") is None or t.get("first_x") is None:
            print(f"  missing features for {stem} {src}->{tgt}")
            continue
        ed, sd = s["end_dist"], t["start_dist"]
        sj = spatial_jump((s["last_x"], s["last_y"]), (t["first_x"], t["first_y"]))
        h59 = review.get((stem, src, tgt), "not_in_review")
        visual = VISUAL_VERDICT.get((stem, src, tgt), "?")

        annotated.append({
            "stem": stem, "src": src, "tgt": tgt,
            "end_d": ed, "start_d": sd, "sj": sj,
            "h59": h59, "visual": visual,
            "min_d": min(ed, sd), "max_d": max(ed, sd),
        })

    # 2. Sweep H114 v1 strict thresholds on the 13 NEW V4 edges
    print("=" * 70)
    print("H114 v1 strict threshold sweep on 13 H125 v4 NEW V4 edges")
    print("=" * 70)
    print(f"{'T_d':>4} {'T_j':>5} | {'fires':>6} {'drops_REAL':>10} {'drops_FALSE':>11} {'drops_WRONG':>11}")
    print("-" * 70)
    for T_d in [15, 20, 25, 30, 40]:
        for T_j in [80, 100, 150, 180, 200, 250]:
            fires_count = 0
            drops_real = 0
            drops_false = 0
            drops_wrong = 0
            for e in annotated:
                s = tf.get((e["stem"], e["src"]), {})
                t = tf.get((e["stem"], e["tgt"]), {})
                if h114_v1_strict_fires(s, t, T_d, T_j):
                    fires_count += 1
                    if e["visual"] == "REAL":
                        drops_real += 1
                    elif e["visual"] == "FALSE" and e["h59"] == "correct":
                        drops_false += 1
                    elif e["h59"] == "wrong":
                        drops_wrong += 1
            print(f"{T_d:>4} {T_j:>5} | {fires_count:>6} {drops_real:>10} {drops_false:>11} {drops_wrong:>11}")

    # 3. Sweep single-end-far thresholds
    print()
    print("=" * 70)
    print("Single-end-far threshold sweep on 13 H125 v4 NEW V4 edges")
    print("=" * 70)
    print(f"{'FAR_NEAR':>8} {'FAR_FAR':>7} | {'fires':>6} {'drops_REAL':>10} {'drops_FALSE':>11} {'drops_WRONG':>11}")
    print("-" * 70)
    for FAR_NEAR in [5, 10, 15, 20, 25, 30]:
        for FAR_FAR in [60, 80, 100, 120]:
            fires_count = 0
            drops_real = 0
            drops_false = 0
            drops_wrong = 0
            for e in annotated:
                s = tf.get((e["stem"], e["src"]), {})
                t = tf.get((e["stem"], e["tgt"]), {})
                if single_end_far_fires(s, t, FAR_NEAR, FAR_FAR):
                    fires_count += 1
                    if e["visual"] == "REAL":
                        drops_real += 1
                    elif e["visual"] == "FALSE" and e["h59"] == "correct":
                        drops_false += 1
                    elif e["h59"] == "wrong":
                        drops_wrong += 1
            print(f"{FAR_NEAR:>8} {FAR_FAR:>7} | {fires_count:>6} {drops_real:>10} {drops_false:>11} {drops_wrong:>11}")

    # 4. Sweep combined H114 v1 strict + single-end-far
    print()
    print("=" * 70)
    print("Combined filter: H114 v1 strict (25, 200) OR single-end-far")
    print("=" * 70)
    print(f"{'FAR_NEAR':>8} {'FAR_FAR':>7} | {'fires':>6} {'drops_REAL':>10} {'drops_FALSE':>11} {'drops_WRONG':>11}")
    print("-" * 70)
    T_d, T_j = 25, 200
    for FAR_NEAR in [5, 10, 15, 20, 25, 30]:
        for FAR_FAR in [60, 80, 100, 120]:
            fires_count = 0
            drops_real = 0
            drops_false = 0
            drops_wrong = 0
            for e in annotated:
                s = tf.get((e["stem"], e["src"]), {})
                t = tf.get((e["stem"], e["tgt"]), {})
                fires = (h114_v1_strict_fires(s, t, T_d, T_j)
                         or single_end_far_fires(s, t, FAR_NEAR, FAR_FAR))
                if fires:
                    fires_count += 1
                    if e["visual"] == "REAL":
                        drops_real += 1
                    elif e["visual"] == "FALSE" and e["h59"] == "correct":
                        drops_false += 1
                    elif e["h59"] == "wrong":
                        drops_wrong += 1
            print(f"{FAR_NEAR:>8} {FAR_FAR:>7} | {fires_count:>6} {drops_real:>10} {drops_false:>11} {drops_wrong:>11}")

    # 5. Show the per-edge annotation table
    print()
    print("=" * 70)
    print("Per-edge annotation table (for reference)")
    print("=" * 70)
    print(f"{'edge':<55} {'H59':<8} {'visual':<8} {'end_d':>7} {'start_d':>8} {'min_d':>6} {'max_d':>6} {'sj':>7}")
    for e in annotated:
        print(f"{e['stem'][:18]} {e['src']}->{e['tgt']:<3} {e['h59']:<8} {e['visual']:<8} "
              f"{e['end_d']:>7.1f} {e['start_d']:>8.1f} {e['min_d']:>6.1f} {e['max_d']:>6.1f} {e['sj']:>7.1f}")


if __name__ == "__main__":
    main()
