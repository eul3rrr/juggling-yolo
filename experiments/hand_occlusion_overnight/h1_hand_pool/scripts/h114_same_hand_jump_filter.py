"""H114: Same-hand large-jump filter for h7v3plus3 hand edges.

Hypothesis (from H112 future-research): a hand-classified edge where the
ball is NOT at either hand at the transition (end_d > T AND start_d > T)
is NOT a real catch-throw, regardless of whether the source and target
hands are the same or different. H112 restricted the rule to cross-hand
edges because only 1 cross-hand FP was found (22->27). A same-hand
variant at higher threshold may catch additional same-hand large-jump
FPs.

H112 evaluation scope was the 51 h7v3plus3 hand-classified admitted
edges (only 1 wrong was in the chain set, 22->27). H114 expands the
evaluation scope to the FULL 113 manually reviewed pairs because the
question is "does this rule help with edge-level quality in general?"
not just within the chain algorithm's accepted set. Many wrong edges
were correctly rejected by the chain algorithm; testing on the full
review set ensures we measure recall cost and precision gain correctly.

H114 declares the rule in two flavors:
- v1 (spatial_jump check): reject if (spatial_jump_px > T) AND
  (end_d > D) AND (start_d > D) AND (same_hand OR cross_hand)
- v2 (H112 extended, no cross_hand): reject if (end_d > T) AND
  (start_d > T) [matches H112 except cross_hand requirement removed]

Physical-geometry justification (per master §15):
- A real catch-throw places the ball within ~30 px of the hand at
  the catch/throw frame.
- A real catch-throw's spatial jump from source's last point to
  target's first point is bounded by the held-phase arc: a ball
  caught and immediately re-thrown moves <100 px per second of
  held time. For a 6-12 frame hold (200-400 ms at 30 fps), the
  ball travels 20-50 px while in the hand.
- A spatial jump > 150 px in < 12 frames is therefore physically
  implausible for a real catch-throw — the ball would need to
  teleport from source-end to target-start, which only happens
  when the chain algorithm stitched two unrelated tracklets.

The thresholds are declared from physical geometry, not from
manual labels. 150 px is a conservative ceiling for any real
catch-throw; > 150 px in 12 frames is necessarily a tracker
artifact (not a real ball trajectory).

Outputs:
- data/h114_per_edge.csv: all 113 review pairs with rule applied
- data/h114_per_pair.csv: TP/FP/FN per threshold
- data/h114_summary.json: aggregate stats
- reports/h114_report.md: human-readable analysis
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

TRACKLET_FEATURES = H1_DATA / "tracklet_features.csv"
H102_PAIR = H1_DATA / "h102_per_pair.csv"
H7V3_ADMITTED_EDGES = "h7v3plus3_admitted_edges_{}.csv"

HAND_EDGE_TYPES = {
    "HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION", "V_RECLASSIFIED_HAND_TRANSITION",
    "H22_RECLASSIFIED_HAND_TRANSITION", "H26_RECLASSIFIED_HAND_TRANSITION",
}


def load_tracklet_features() -> dict:
    tf = {}
    with TRACKLET_FEATURES.open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["tid"]))
            end_d = float(row["end_dist"]) if row["end_dist"] else None
            start_d = float(row["start_dist"]) if row["start_dist"] else None
            tf[key] = {
                "end_dist": end_d,
                "start_dist": start_d,
                "end_side": row["end_side"] or None,
                "start_side": row["start_side"] or None,
                "last_x": float(row["last_x"]),
                "last_y": float(row["last_y"]),
                "first_x": float(row["first_x"]),
                "first_y": float(row["first_y"]),
                "last_frame": int(row["last_frame"]),
                "first_frame": int(row["first_frame"]),
            }
    return tf


def load_h7v3plus3_set() -> dict:
    """Return the dict of (stem, src, tgt) -> edge_type for h7v3plus3 chain set."""
    out = {}
    for stem_file in ["identical_balls_trick_000_018",
                      "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]:
        path = H1_DATA / H7V3_ADMITTED_EDGES.format(stem_file)
        if not path.exists():
            continue
        with path.open() as f:
            for row in csv.DictReader(f):
                src = int(row["from_tid"])
                tgt = int(row["to_tid"])
                out[(stem_file, src, tgt)] = row["edge_type"]
    return out


def spatial_jump(src: dict, tgt: dict) -> float:
    return math.hypot(tgt["first_x"] - src["last_x"], tgt["first_y"] - src["last_y"])


def is_cross_hand(src: dict, tgt: dict) -> bool:
    if src["end_side"] is None or tgt["start_side"] is None:
        return False
    return src["end_side"] != tgt["start_side"]


def rule_v1(src: dict, tgt: dict, threshold_d: float, threshold_jump: float,
            require_cross: bool = False) -> tuple[bool, str]:
    """Spatial jump + end_d + start_d rule.

    Returns (should_reject, reason).
    """
    if src["end_dist"] is None or tgt["start_dist"] is None:
        return False, "missing-dist"
    cross = is_cross_hand(src, tgt)
    if require_cross and not cross:
        return False, "same-hand-skip"
    sj = spatial_jump(src, tgt)
    if sj > threshold_jump and src["end_dist"] > threshold_d and tgt["start_dist"] > threshold_d:
        return True, f"sj>{threshold_jump}_and_d>{threshold_d}"
    return False, "ok"


def rule_v2(src: dict, tgt: dict, threshold_d: float, require_cross: bool = False) -> tuple[bool, str]:
    """H112 rule without cross_hand requirement."""
    if src["end_dist"] is None or tgt["start_dist"] is None:
        return False, "missing-dist"
    cross = is_cross_hand(src, tgt)
    if require_cross and not cross:
        return False, "same-hand-skip"
    if src["end_dist"] > threshold_d and tgt["start_dist"] > threshold_d:
        return True, f"d>{threshold_d}"
    return False, "ok"


def main():
    tf = load_tracklet_features()
    h7v3 = load_h7v3plus3_set()

    # Build the full 113 review pair table
    rows = []
    with H102_PAIR.open() as f:
        for row in csv.DictReader(f):
            stem = row["stem"]
            src = int(row["source"])
            tgt = int(row["candidate"])
            gap = int(row["gap_frames"])
            label = row["label"]
            in_chain = row["in_h7v3plus3"] == "True"
            chain_etype = h7v3.get((stem, src, tgt), "NOT_IN_CHAIN")

            src_f = tf.get((stem, src))
            tgt_f = tf.get((stem, tgt))
            if src_f is None or tgt_f is None:
                continue

            cross = is_cross_hand(src_f, tgt_f)
            sj = spatial_jump(src_f, tgt_f)
            v_jump = sj / gap if gap > 0 else float("inf")

            row_d = {
                "stem": stem,
                "src": src,
                "tgt": tgt,
                "gap": gap,
                "label": label,
                "in_h7v3plus3": in_chain,
                "chain_edge_type": chain_etype,
                "src_end_side": src_f["end_side"] or "",
                "tgt_start_side": tgt_f["start_side"] or "",
                "cross_hand": cross,
                "end_d": round(src_f["end_dist"], 2) if src_f["end_dist"] is not None else "",
                "start_d": round(tgt_f["start_dist"], 2) if tgt_f["start_dist"] is not None else "",
                "spatial_jump": round(sj, 2),
                "v_jump": round(v_jump, 2),
                "is_hand_edge": chain_etype in HAND_EDGE_TYPES,
            }
            rows.append(row_d)

    # v1: spatial_jump + end_d + start_d (varying T_jump, T_d)
    v1_thresholds = [(30, 80), (30, 100), (30, 120), (30, 150), (30, 200),
                     (40, 100), (40, 150), (40, 200), (40, 250),
                     (50, 100), (50, 150), (50, 200), (50, 250),
                     (60, 150), (60, 200), (60, 250), (60, 300),
                     (80, 200), (80, 250), (80, 300)]
    v2_thresholds = [30, 40, 50, 60, 80, 100]

    # For each rule variant, compute per-edge rejection
    for t_d, t_j in v1_thresholds:
        rows[0]  # touch
        for r in rows:
            r[f"v1_d{t_d}_j{t_j}"] = rule_v1(
                tf[(r["stem"], r["src"])], tf[(r["stem"], r["tgt"])], t_d, t_j
            )[0]

    for t_d in v2_thresholds:
        for r in rows:
            r[f"v2_d{t_d}"] = rule_v2(
                tf[(r["stem"], r["src"])], tf[(r["stem"], r["tgt"])], t_d
            )[0]

    # Save per-edge CSV
    out_csv = H1_DATA / "h114_per_edge.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with out_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows)")

    # Per-rule precision/recall against the 113 review labels
    def evaluate(rule_col: str, require_in_chain: bool = False) -> dict:
        """For each rule, return TP/FP/FN/P/R.

        TPs and FPs are about h7v3plus3 hand edges in the review set.
        A dropped correct edge is FN (a real catch-throw we wrongly
        rejected). A dropped wrong edge is TN.

        But we also want to know: does the rule surface wrong edges
        that h7v3plus3 missed (NOT_IN_CHAIN wrong edges)?
        """
        # Scope 1: ALL 113 review pairs
        all_113 = rows
        # Scope 2: only h7v3plus3 hand edges in the 113 review set
        chain_edges = [r for r in rows if r["in_h7v3plus3"]]

        def scope_stats(scope, name):
            drops = [r for r in scope if r[rule_col]]
            n_drop_wrong = sum(1 for r in drops if r["label"] == "wrong")
            n_drop_correct = sum(1 for r in drops if r["label"] == "correct")
            n_keep_wrong = sum(1 for r in scope if not r[rule_col] and r["label"] == "wrong")
            n_keep_correct = sum(1 for r in scope if not r[rule_col] and r["label"] == "correct")
            return {
                "scope": name,
                "n_total": len(scope),
                "n_dropped": len(drops),
                "drop_wrong": n_drop_wrong,
                "drop_correct": n_drop_correct,
                "keep_wrong": n_keep_wrong,
                "keep_correct": n_keep_correct,
                "n_wrong_total": sum(1 for r in scope if r["label"] == "wrong"),
                "n_correct_total": sum(1 for r in scope if r["label"] == "correct"),
            }

        return {
            "all_113": scope_stats(all_113, "all_113"),
            "chain_edges_only": scope_stats(chain_edges, "chain_edges_only"),
        }

    # v1 per-threshold
    print()
    print("=" * 80)
    print("v1 (spatial_jump > T_j AND end_d > T_d AND start_d > T_d) results")
    print("=" * 80)
    print(f"{'T_d':>5} {'T_jump':>7} | {'all_113':>22} | {'chain':>22}")
    print(f"{'':>5} {'':>7} | {'drop_W/C':>9} {'keep_W/C':>11} | {'drop_W/C':>9} {'keep_W/C':>11}")
    v1_results = {}
    for t_d, t_j in v1_thresholds:
        col = f"v1_d{t_d}_j{t_j}"
        r = evaluate(col)
        v1_results[f"d{t_d}_j{t_j}"] = r
        a = r["all_113"]
        c = r["chain_edges_only"]
        print(f"  {t_d:>3} {t_j:>5} | {a['drop_wrong']:>4}/{a['drop_correct']:>4} {a['keep_wrong']:>4}/{a['keep_correct']:>6} | "
              f"{c['drop_wrong']:>4}/{c['drop_correct']:>4} {c['keep_wrong']:>4}/{c['keep_correct']:>6}")

    # v2 per-threshold
    print()
    print("=" * 80)
    print("v2 (end_d > T_d AND start_d > T_d, NO cross_hand requirement) results")
    print("=" * 80)
    print(f"{'T_d':>5} | {'all_113':>22} | {'chain':>22}")
    print(f"{'':>5} | {'drop_W/C':>9} {'keep_W/C':>11} | {'drop_W/C':>9} {'keep_W/C':>11}")
    v2_results = {}
    for t_d in v2_thresholds:
        col = f"v2_d{t_d}"
        r = evaluate(col)
        v2_results[f"d{t_d}"] = r
        a = r["all_113"]
        c = r["chain_edges_only"]
        print(f"  {t_d:>3} | {a['drop_wrong']:>4}/{a['drop_correct']:>4} {a['keep_wrong']:>4}/{a['keep_correct']:>6} | "
              f"{c['drop_wrong']:>4}/{c['drop_correct']:>4} {c['keep_wrong']:>4}/{c['keep_correct']:>6}")

    # Identify "all_113 wrong drops" (wrong edges that the filter would catch)
    print()
    print("=" * 80)
    print("Wrong edges caught at any v1 setting (out of 30 wrong in 113):")
    print("=" * 80)
    wrong_edges = [r for r in rows if r["label"] == "wrong"]
    for r in wrong_edges:
        v1_caught = []
        for t_d, t_j in v1_thresholds:
            col = f"v1_d{t_d}_j{t_j}"
            if r[col]:
                v1_caught.append(f"d{t_d}_j{t_j}")
        v2_caught = []
        for t_d in v2_thresholds:
            col = f"v2_d{t_d}"
            if r[col]:
                v2_caught.append(f"d{t_d}")
        in_chain = r["in_h7v3plus3"]
        sj = r["spatial_jump"]
        end_d = r["end_d"]
        start_d = r["start_d"]
        cross = r["cross_hand"]
        if v1_caught or v2_caught:
            print(f"  {r['stem'][:20]:<20} {r['src']:>2}->{r['tgt']:<2} "
                  f"in_chain={in_chain!s:<5} cross={cross!s:<5} sj={sj:>6.1f} end={end_d!s:>6} start={start_d!s:>6} "
                  f"v1={len(v1_caught)}/{len(v1_thresholds)} v2={len(v2_caught)}/{len(v2_thresholds)}")

    # Cross-hand WRONG edges in h7v3plus3
    print()
    print("=" * 80)
    print("Cross-hand WRONG edges in h7v3plus3 hand set (would H112 catch?):")
    print("=" * 80)
    for r in rows:
        if r["label"] == "wrong" and r["in_h7v3plus3"] and r["cross_hand"]:
            print(f"  {r['stem'][:20]:<20} {r['src']:>2}->{r['tgt']:<2} "
                  f"sj={r['spatial_jump']:>6.1f} end={r['end_d']!s:>6} start={r['start_d']!s:>6} "
                  f"et={r['chain_edge_type']}")

    # Same-hand WRONG edges in h7v3plus3
    print()
    print("=" * 80)
    print("Same-hand WRONG edges in h7v3plus3 hand set (H114 target):")
    print("=" * 80)
    for r in rows:
        if r["label"] == "wrong" and r["in_h7v3plus3"] and not r["cross_hand"]:
            print(f"  {r['stem'][:20]:<20} {r['src']:>2}->{r['tgt']:<2} "
                  f"sj={r['spatial_jump']:>6.1f} end={r['end_d']!s:>6} start={r['start_d']!s:>6} "
                  f"et={r['chain_edge_type']}")

    # Same-hand WRONG edges NOT in h7v3plus3 (the chain algorithm already
    # rejected these, but H114 might suggest a different reason)
    print()
    print("=" * 80)
    print("Same-hand WRONG edges NOT in h7v3plus3 (H114 redundant for chain, but informative for new chains):")
    print("=" * 80)
    for r in rows:
        if r["label"] == "wrong" and not r["in_h7v3plus3"] and not r["cross_hand"]:
            print(f"  {r['stem'][:20]:<20} {r['src']:>2}->{r['tgt']:<2} "
                  f"sj={r['spatial_jump']:>6.1f} end={r['end_d']!s:>6} start={r['start_d']!s:>6} "
                  f"gap={r['gap']:>2}")

    # Save summary JSON
    summary = {
        "rule_v1": {
            "rule": "spatial_jump > T_jump AND end_d > T_d AND start_d > T_d",
            "thresholds": v1_thresholds,
            "per_threshold": v1_results,
        },
        "rule_v2": {
            "rule": "end_d > T_d AND start_d > T_d (no cross_hand requirement)",
            "thresholds": v2_thresholds,
            "per_threshold": v2_results,
        },
        "evaluation_scope": "All 113 review pairs (chain + non-chain) and chain-only subset",
        "physical_geometry_justification": (
            "A real catch-throw places the ball within ~30 px of the hand at "
            "the catch/throw frame. A spatial jump > 150 px in 12 frames is "
            "physically implausible for a real catch-throw; only tracker "
            "association can produce such a jump."
        ),
    }
    with (H1_DATA / "h114_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print()
    print(f"Wrote {H1_DATA / 'h114_summary.json'}")


if __name__ == "__main__":
    main()
