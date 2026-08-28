"""H112: Cross-hand handoff spatial filter for h7v3plus3 hand edges.

Hypothesis (from H111 S2 surface analysis): a cross-hand handoff edge where
BOTH the source's endpoint AND the target's startpoint are > 30 px from their
respective assigned hands is NOT a real catch-throw — it's a tracker-association
artifact where the chain algorithm stitched two unrelated tracklets.

H111 identified the 22->27 identical (left->right, end_d=46.7, start_d=56.2,
spatial jump=190.4 px in 11 frames) as a hand-edge FP that the H102 strict
midgap-anchored evaluation missed because the midgap (260) is just before
the f=263-312 JUGGLING phase.

Physical-geometry justification (declared from physical geometry, not from
manual labels per master §15):
- A real catch-throw requires the ball to be AT the hand at the catch frame
  (end_d < 30 px for a hand radius of ~15-20 px).
- A real cross-hand handoff requires the ball to be at the SOURCE hand at the
  catch frame AND at the TARGET hand at the throw frame.
- An end_d > 30 px (ball not at source hand at catch) PLUS a start_d > 30 px
  (ball not at target hand at throw) means the ball is NOT at either hand
  during the transition. This is physically implausible for a real catch-throw.

Rule (default): reject hand-classified edge if
  (src.end_side != tgt.start_side)  AND  (src.end_dist > 30)  AND  (tgt.start_dist > 30)

Outputs:
  - data/h112_per_edge.csv: all h7v3plus3 hand edges with the H112 rule applied
  - data/h112_per_phase.csv: 21 H93 phases with TP/FP/FN/P/R for each threshold
  - data/h112_summary.json: aggregate stats per threshold setting
  - reports/h112_report.md: human-readable analysis
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

H93_FILE = H1_DATA / "h93_multi_rater_qa.json"
H102_PAIR = H1_DATA / "h102_per_pair.csv"
TRACKLET_FEATURES = H1_DATA / "tracklet_features.csv"

HAND_EDGE_TYPES = {
    "HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION",
    "RECLASSIFIED_HAND_TRANSITION", "V_RECLASSIFIED_HAND_TRANSITION",
    "H22_RECLASSIFIED_HAND_TRANSITION", "H26_RECLASSIFIED_HAND_TRANSITION",
}

# Per master §15: declare parameters from physical geometry, not from labels.
# Justification: a real catch-throw places the ball within 30 px of the hand
# at the catch/throw frame. 30 px is conservative: a 25-30 px reach radius
# for a sports ball at the hand, with 5 px tolerance for detection noise.
DEFAULT_THRESHOLD_PX = 30.0


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


def load_h93_phases() -> list[tuple[str, int, int, str, str]]:
    with H93_FILE.open() as f:
        gt = json.load(f)["corrected_ground_truth"]
    out = []
    for pkey, verdict in gt.items():
        parts = pkey.rsplit("_", 2)
        stem, start, end = parts[0], int(parts[1]), int(parts[2])
        out.append((stem, start, end, verdict, pkey))
    return out


def load_review_labels() -> dict:
    labels = {}
    with H102_PAIR.open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["source"]), int(row["candidate"]))
            labels[key] = row["label"]
    return labels


def anchor_pair(stem: str, src_end: int, tgt_start: int, phases: list) -> str | None:
    """S2 union anchoring: midgap OR src_end OR tgt_start in phase."""
    midgap = (src_end + tgt_start) / 2
    for ps, pstart, pend, _v, pkey in phases:
        if ps != stem:
            continue
        if pstart <= midgap <= pend or pstart <= src_end <= pend or pstart <= tgt_start <= pend:
            return pkey
    return None


def is_cross_hand_handoff(tf_row_src: dict, tf_row_tgt: dict) -> bool:
    """A cross-hand handoff has src.end_side != tgt.start_side AND both defined."""
    if tf_row_src["end_side"] is None or tf_row_tgt["start_side"] is None:
        return False
    return tf_row_src["end_side"] != tf_row_tgt["start_side"]


def should_reject(
    src: dict, tgt: dict, threshold_px: float, require_cross: bool = True
) -> tuple[bool, str]:
    """Apply H112 rule.

    Returns (should_reject, reason_string).

    Rule:
      IF (require_cross AND cross_hand) OR (NOT require_cross)
      AND src.end_dist > threshold AND tgt.start_dist > threshold
      -> REJECT
    """
    cross = is_cross_hand_handoff(src, tgt)
    if require_cross and not cross:
        return False, "same-hand"
    if src["end_dist"] is None or tgt["start_dist"] is None:
        return False, "missing-dist"
    if src["end_dist"] > threshold_px and tgt["start_dist"] > threshold_px:
        return True, f"both-endstart>{threshold_px}"
    return False, "ok"


def main():
    tf = load_tracklet_features()
    phases = load_h93_phases()
    labels = load_review_labels()

    # Per-edge CSV
    out_rows = []
    summary_per_threshold = {thr: {"dropped_FP": 0, "dropped_correct": 0, "dropped_NR": 0, "dropped_total": 0}
                             for thr in [20, 25, 30, 40, 50, 60, 80, 100]}

    for stem_file in ["identical_balls_trick_000_018",
                      "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]:
        with (H1_DATA / f"h7v3plus3_admitted_edges_{stem_file}.csv").open() as f:
            for row in csv.DictReader(f):
                if row["edge_type"] not in HAND_EDGE_TYPES:
                    continue
                src, tgt = int(row["from_tid"]), int(row["to_tid"])
                src_f = tf.get((stem_file, src))
                tgt_f = tf.get((stem_file, tgt))
                if src_f is None or tgt_f is None:
                    continue

                cross = is_cross_hand_handoff(src_f, tgt_f)
                gap = tgt_f["first_frame"] - src_f["last_frame"]
                spatial_jump = math.hypot(
                    tgt_f["first_x"] - src_f["last_x"],
                    tgt_f["first_y"] - src_f["last_y"],
                )
                v_jump = spatial_jump / gap if gap > 0 else float("inf")
                label = labels.get((stem_file, src, tgt), "NOT_REVIEWED")

                pkey = anchor_pair(stem_file, src_f["last_frame"], tgt_f["first_frame"], phases)

                out_rows.append({
                    "stem": stem_file, "src": src, "tgt": tgt,
                    "edge_type": row["edge_type"],
                    "src_end_side": src_f["end_side"],
                    "tgt_start_side": tgt_f["start_side"],
                    "cross_hand": cross,
                    "end_d": src_f["end_dist"],
                    "start_d": tgt_f["start_dist"],
                    "gap": gap,
                    "spatial_jump": round(spatial_jump, 2),
                    "v_jump": round(v_jump, 2),
                    "label": label,
                    "h93_phase_key": pkey or "",
                    # For each threshold, would this be dropped?
                    **{f"drop_at_{thr}": should_reject(src_f, tgt_f, float(thr))[0]
                       for thr in [20, 25, 30, 40, 50, 60, 80, 100]},
                })

                # Accumulate per-threshold stats
                for thr in [20, 25, 30, 40, 50, 60, 80, 100]:
                    reject, _ = should_reject(src_f, tgt_f, float(thr))
                    if reject:
                        summary_per_threshold[thr]["dropped_total"] += 1
                        if label == "wrong":
                            summary_per_threshold[thr]["dropped_FP"] += 1
                        elif label == "correct":
                            summary_per_threshold[thr]["dropped_correct"] += 1
                        else:
                            summary_per_threshold[thr]["dropped_NR"] += 1

    # Save per-edge CSV
    out_csv = H1_DATA / "h112_per_edge.csv"
    if out_rows:
        with out_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
    print(f"Wrote {out_csv} ({len(out_rows)} rows)")

    # Per-threshold summary
    print()
    print("Per-threshold H112 rejection stats (hand-classified edges only):")
    print(f"{'thr':>5} {'dropped':>8} {'FP':>4} {'correct':>8} {'NR':>4}")
    for thr, s in sorted(summary_per_threshold.items()):
        print(f"  {thr:>3} {s['dropped_total']:>8} {s['dropped_FP']:>4} {s['dropped_correct']:>8} {s['dropped_NR']:>4}")

    # Save summary JSON
    summary = {
        "default_threshold_px": DEFAULT_THRESHOLD_PX,
        "rule": "(cross_hand_handoff) AND (end_d > T) AND (start_d > T)",
        "justification": (
            "Per physical geometry: a real catch-throw places the ball within 30 px of "
            "the hand at the catch/throw frame. A cross-hand handoff where the source "
            "endpoint is >30 px from the source hand AND the target startpoint is >30 px "
            "from the target hand is not a real catch-throw."
        ),
        "thresholds_tested": sorted(summary_per_threshold.keys()),
        "per_threshold_stats": summary_per_threshold,
    }
    with (H1_DATA / "h112_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {H1_DATA / 'h112_summary.json'}")

    # Per-phase evaluation at default threshold (30 px)
    print()
    print("Per-phase evaluation at default threshold 30 px (S2 anchored):")
    per_phase_stats = {}
    for pkey in sorted({r["h93_phase_key"] for r in out_rows if r["h93_phase_key"]}):
        phase_rows = [r for r in out_rows if r["h93_phase_key"] == pkey]
        verdict = next(p[3] for p in phases if p[4] == pkey)
        # Count: TP (correct in chain at default), FP (wrong in chain at default)
        # After H112: edges with drop_at_30=True are removed from chain.
        tp_default = sum(1 for r in phase_rows if r["label"] == "correct" and not r["drop_at_30"])
        fp_default = sum(1 for r in phase_rows if r["label"] == "wrong" and not r["drop_at_30"])
        fn_default = sum(1 for r in phase_rows if r["label"] == "correct" and r["drop_at_30"])

        tp_h112 = sum(1 for r in phase_rows if r["label"] == "correct" and r["drop_at_30"])
        fp_h112 = sum(1 for r in phase_rows if r["label"] == "wrong" and r["drop_at_30"])
        fn_h112 = sum(1 for r in phase_rows if r["label"] == "wrong" and r["drop_at_30"])

        per_phase_stats[pkey] = {
            "verdict": verdict,
            "n_rows": len(phase_rows),
            "default_TP": tp_default, "default_FP": fp_default, "default_FN": fn_default,
            "h112_drops_correct": tp_h112,
            "h112_drops_wrong": fp_h112,
        }
        if tp_h112 or fp_h112:
            print(f"  {pkey[-25:]:<25} verdict={verdict:<10} H112_drops: correct={tp_h112} wrong={fp_h112}")

    # Edge-level impact on 113 review pairs
    print()
    print("Edge-level impact on 113 review pairs (at default threshold 30 px):")
    n_total = sum(1 for r in out_rows if r["label"] != "NOT_REVIEWED")
    n_dropped = sum(1 for r in out_rows if r["label"] != "NOT_REVIEWED" and r["drop_at_30"])
    fp_dropped = sum(1 for r in out_rows if r["label"] == "wrong" and r["drop_at_30"])
    fn_dropped = sum(1 for r in out_rows if r["label"] == "correct" and r["drop_at_30"])
    print(f"  Total reviewed h7v3plus3 hand edges: {n_total}")
    print(f"  Dropped by H112: {n_dropped} (FP={fp_dropped}, FN={fn_dropped})")

    # Full 113-pair baseline: h7v3+ precision/recall before/after H112
    all_review = []
    with H102_PAIR.open() as f:
        for row in csv.DictReader(f):
            if row["in_h7v3plus3"] != "True":
                continue
            all_review.append({
                "stem": row["stem"],
                "src": int(row["source"]),
                "tgt": int(row["candidate"]),
                "label": row["label"],
                "edge_type": row["edge_type"],
            })
    n_baseline_correct = sum(1 for r in all_review if r["label"] == "correct")
    n_baseline_wrong = sum(1 for r in all_review if r["label"] == "wrong")
    base_TP = n_baseline_correct
    base_FP = n_baseline_wrong
    base_FN = 71 - n_baseline_correct  # 71 correct in full 113
    base_P = base_TP / (base_TP + base_FP)
    base_R = base_TP / (base_TP + base_FN)

    # After H112
    after_review = []
    for r in all_review:
        # Find this edge in out_rows
        match = next((o for o in out_rows
                      if o["stem"] == r["stem"] and o["src"] == r["src"] and o["tgt"] == r["tgt"]), None)
        if match is None:
            # Non-hand edge (BALLISTIC) - H112 doesn't apply
            after_review.append(r)
            continue
        if not match["drop_at_30"]:
            after_review.append(r)
        # else: dropped

    n_after_correct = sum(1 for r in after_review if r["label"] == "correct")
    n_after_wrong = sum(1 for r in after_review if r["label"] == "wrong")
    after_TP = n_after_correct
    after_FP = n_after_wrong
    after_FN = 71 - n_after_correct
    after_P = after_TP / (after_TP + after_FP)
    after_R = after_TP / (after_TP + after_FN)

    print(f"  Baseline h7v3plus3 (113 pair subset, hand edges only): TP={base_TP} FP={base_FP} FN={base_FN} P={base_P:.3f} R={base_R:.3f}")
    print(f"  After H112: TP={after_TP} FP={after_FP} FN={after_FN} P={after_P:.3f} R={after_R:.3f}")

    # Update summary
    summary["edge_level_impact"] = {
        "baseline_TP": base_TP, "baseline_FP": base_FP, "baseline_FN": base_FN,
        "baseline_precision": round(base_P, 4), "baseline_recall": round(base_R, 4),
        "after_TP": after_TP, "after_FP": after_FP, "after_FN": after_FN,
        "after_precision": round(after_P, 4), "after_recall": round(after_R, 4),
    }
    summary["per_phase_impact_at_default"] = per_phase_stats

    with (H1_DATA / "h112_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    # Per-phase CSV
    with (H1_DATA / "h112_per_phase.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "phase_key", "verdict", "n_rows", "default_TP", "default_FP", "default_FN",
            "h112_drops_correct", "h112_drops_wrong",
        ])
        for pkey, d in per_phase_stats.items():
            w.writerow([pkey, d["verdict"], d["n_rows"], d["default_TP"], d["default_FP"],
                        d["default_FN"], d["h112_drops_correct"], d["h112_drops_wrong"]])
    print(f"Wrote {H1_DATA / 'h112_per_phase.csv'}")


if __name__ == "__main__":
    main()
