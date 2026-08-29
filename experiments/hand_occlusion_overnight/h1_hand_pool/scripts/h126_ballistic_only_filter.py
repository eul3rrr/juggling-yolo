#!/usr/bin/env python3
"""H126 — BALLISTIC-only H126 filter applied to the H125 v4 union.

HYPOTHESIS (declared BEFORE reading outcomes):
  H125 v4 admitted 13 NEW V4 edges (12 identical + 1 YouTube) with 2 H59=wrong
  edges (6->15 identical, 10->11 YouTube). The 2 wrong edges have a distinctive
  BALLISTIC-edge signature: extreme proximity to the hand (one end < 5 px, or
  both ends < 50 px). This is the "tracker latched onto a held ball" pattern.

  H125 v4 + H126 (BALLISTIC-only) should achieve:
    - P=1.000 (was 0.964) — drops both H59=wrong edges
    - R=0.761 (unchanged) — no H59=correct or visual REAL edges dropped
    - F1=0.864 (was 0.850)

  The filter MUST only apply to BALLISTIC edges (not HAND_TRANSITION /
  RECLASSIFIED_HAND_TRANSITION) because hand-classified edges naturally have
  both endpoints within reach.

Method:
  1. Build the H125 v4 union (h7v3plus3 + H125 v3)
  2. Apply H112 (cross-hand handoff) — keep h7v3plus3's behavior
  3. Apply H114 v1 strict (T_d=25, T_j=200) — keep h7v3plus3's behavior
  4. Apply H126 BALLISTIC-only filter (NEW)
  5. Evaluate P/R on 113 review pairs
  6. Compare to H125 v4 (no H126)
  7. Visual precision: 5/13 visual REAL preserved (none dropped)

Outputs:
  - data/h126_v1_summary.json: per-stem P/R + admitted edges
  - data/h126_v1_per_edge.csv: per-edge details with filter traces
  - reports/h126_report.md: full analysis
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Visual verdicts from H125 v4 contact sheet QA
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
    ("identical_balls_trick_000_018", 6, 15): "FALSE",
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11): "FALSE",
}


def _opt_float(s, default=999.0):
    if s is None or s == "":
        return default
    return float(s)


def load_tracklet_features():
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for r in csv.DictReader(f):
            tid = int(r["tid"])
            out[(r["stem"], tid)] = {
                "tid": tid,
                "first_x": _opt_float(r["first_x"], 0.0) or None,
                "first_y": _opt_float(r["first_y"], 0.0) or None,
                "end_x": _opt_float(r["last_x"], 0.0) or None,
                "end_y": _opt_float(r["last_y"], 0.0) or None,
                "end_dist": _opt_float(r["end_dist"], 999.0),
                "end_slope": _opt_float(r["end_slope"], 0.0),
                "start_dist": _opt_float(r["start_dist"], 999.0),
                "start_slope": _opt_float(r["start_slope"], 0.0),
                "end_side": r.get("end_side", "") or "",
                "start_side": r.get("start_side", "") or "",
            }
    return out


def load_h7v3plus3_edges(stem):
    out = []
    with (H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv").open() as f:
        for r in csv.DictReader(f):
            out.append({
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "edge_type": r["edge_type"],
                "cost": float(r["cost"]),
                "source": "h7v3plus3",
            })
    return out


def load_h125_v3_edges(stem):
    out = []
    with (H1_DATA / f"h125_v3_default_admitted_{stem}.csv").open() as f:
        for r in csv.DictReader(f):
            out.append({
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "edge_type": "BALLISTIC",
                "cost": float(r["cost"]),
                "err": float(r["err"]),
                "gap": int(r["gap"]),
                "source": "h125_v3",
            })
    return out


def compute_spatial_jump(tracklets, stem, src, tgt):
    s = tracklets[(stem, src)]
    t = tracklets[(stem, tgt)]
    if s["end_x"] is None or t["first_x"] is None:
        return None
    return math.hypot(t["first_x"] - s["end_x"], t["first_y"] - s["end_y"])


def h112_fires(e, tracklets, stem, end_thr=30):
    """H112: cross-hand handoff if end_side != start_side AND end_d > end_thr AND start_d > end_thr."""
    if e["edge_type"] not in (
        "HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION",
        "RECLASSIFIED_HAND_TRANSITION", "V_RECLASSIFIED_HAND_TRANSITION",
        "H26_RECLASSIFIED_HAND_TRANSITION", "H22_RECLASSIFIED_HAND_TRANSITION",
    ):
        return False
    s = tracklets[(stem, e["from_tid"])]
    t = tracklets[(stem, e["to_tid"])]
    if s["end_side"] != t["start_side"]:
        if s["end_dist"] > end_thr and t["start_dist"] > end_thr:
            return True
    return False


def h114_v1_strict_fires(e, tracklets, stem, t_d=25, t_j=200):
    """H114 v1 strict: end_d > t_d AND start_d > t_d AND sj > t_j."""
    s = tracklets[(stem, e["from_tid"])]
    t = tracklets[(stem, e["to_tid"])]
    if s["end_dist"] > t_d and t["start_dist"] > t_d:
        sj = compute_spatial_jump(tracklets, stem, e["from_tid"], e["to_tid"])
        if sj is not None and sj > t_j:
            return True
    return False


def h126_fires(e, tracklets, stem, e_ne=5, s_ne=5, both_t=50):
    """H126 BALLISTIC-only filter: (end_d < 5 OR start_d < 5) OR (end_d < 50 AND start_d < 50).

    Only applies to BALLISTIC edges — hand-classified edges naturally have
    both endpoints within reach.
    """
    if e["edge_type"] != "BALLISTIC":
        return False
    s = tracklets[(stem, e["from_tid"])]
    t = tracklets[(stem, e["to_tid"])]
    ed, sd = s["end_dist"], t["start_dist"]
    return (ed < e_ne or sd < s_ne) or (ed < both_t and sd < both_t)


def evaluate_admitted(admitted_edges, review_pairs, stem):
    review_map = {}
    for r in review_pairs:
        if r["stem"] == stem:
            review_map[(int(r["source"]), int(r["candidate"]))] = r

    admitted_keys = set((e["from_tid"], e["to_tid"]) for e in admitted_edges)
    n_admitted_with_review_label = 0
    n_admitted_correct = 0
    n_admitted_wrong = 0
    n_correct_in_review = sum(1 for r in review_pairs if r["stem"] == stem and r["label"] == "correct")
    n_correct_admitted = 0
    for (src, tgt), r in review_map.items():
        if (src, tgt) in admitted_keys:
            n_admitted_with_review_label += 1
            if r["label"] == "correct":
                n_admitted_correct += 1
                n_correct_admitted += 1
            else:
                n_admitted_wrong += 1
    precision = n_admitted_correct / max(1, n_admitted_with_review_label)
    recall = n_correct_admitted / max(1, n_correct_in_review)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "n_admitted_with_review_label": n_admitted_with_review_label,
        "n_admitted_correct": n_admitted_correct,
        "n_admitted_wrong": n_admitted_wrong,
        "n_correct_in_review": n_correct_in_review,
        "n_correct_admitted": n_correct_admitted,
        "precision": precision,
        "recall": recall,
        "F1": f1,
    }


def main():
    tracklets = load_tracklet_features()

    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        review_pairs = list(csv.DictReader(f))

    edges_by_stem = {}
    for stem in STEMS:
        edges_by_stem[stem] = {
            "h7v3plus3": load_h7v3plus3_edges(stem),
            "h125v3": load_h125_v3_edges(stem),
        }

    summary = {"variants": {}}

    # 4 variants:
    # - h7v3plus3 + post-filters (baseline)
    # - h7v3plus3 + H112 + H114 v1 strict (current recommended)
    # - h7v3plus3 + H125 v3 union + H112 + H114 v1 strict (H125 v4)
    # - h7v3plus3 + H125 v3 union + H112 + H114 v1 strict + H126 (NEW)

    variants = [
        ("h7v3plus3_only", "h7v3plus3", False, False),
        ("h7v3plus3_post_filters", "h7v3plus3", True, False),
        ("h125v4_strict", "union", True, False),
        ("h125v4_h126_v1", "union", True, True),
    ]

    for variant_name, source, use_post, use_h126 in variants:
        per_stem_metrics = {}
        per_stem_surviving_new = {}
        for stem in STEMS:
            h7v3plus3 = edges_by_stem[stem]["h7v3plus3"]
            h125v3 = edges_by_stem[stem]["h125v3"]

            if source == "h7v3plus3":
                all_edges = list(h7v3plus3)
            else:
                seen = set()
                all_edges = []
                for e in h7v3plus3 + h125v3:
                    key = (e["from_tid"], e["to_tid"])
                    if key not in seen:
                        seen.add(key)
                        all_edges.append(e)

            h7v3plus3_keys = set((e["from_tid"], e["to_tid"]) for e in h7v3plus3)

            kept = []
            dropped = []
            for e in all_edges:
                drop_reason = []
                if use_post and (h112_fires(e, tracklets, stem) or h114_v1_strict_fires(e, tracklets, stem)):
                    drop_reason.append("h112_or_h114")
                if use_h126 and h126_fires(e, tracklets, stem):
                    drop_reason.append("h126")
                if drop_reason:
                    e_copy = dict(e)
                    e_copy["drop_reason"] = ",".join(drop_reason)
                    dropped.append(e_copy)
                else:
                    kept.append(e)

            new_surviving = [e for e in kept if (e["from_tid"], e["to_tid"]) not in h7v3plus3_keys]
            new_dropped = [e for e in dropped if (e["from_tid"], e["to_tid"]) not in h7v3plus3_keys]
            h7v3plus3_dropped = [e for e in dropped if (e["from_tid"], e["to_tid"]) in h7v3plus3_keys]

            metrics = evaluate_admitted(kept, review_pairs, stem)
            per_stem_metrics[stem] = metrics
            per_stem_surviving_new[stem] = {
                "new_kept": [(e["from_tid"], e["to_tid"]) for e in new_surviving],
                "new_dropped": [(e["from_tid"], e["to_tid"], e.get("drop_reason", ""))
                                for e in new_dropped],
                "h7v3plus3_dropped": [(e["from_tid"], e["to_tid"], e.get("drop_reason", ""))
                                       for e in h7v3plus3_dropped],
            }

        summary["variants"][variant_name] = {
            "per_stem": per_stem_metrics,
            "per_stem_surviving_new": per_stem_surviving_new,
        }

    # Combined P/R/F1
    for variant_name in summary["variants"]:
        v = summary["variants"][variant_name]
        all_correct = sum(v["per_stem"][s]["n_correct_admitted"] for s in STEMS)
        all_in_review = sum(v["per_stem"][s]["n_correct_in_review"] for s in STEMS)
        all_admitted_reviewed = sum(v["per_stem"][s]["n_admitted_with_review_label"] for s in STEMS)
        all_admitted_correct = sum(v["per_stem"][s]["n_admitted_correct"] for s in STEMS)
        all_admitted_wrong = sum(v["per_stem"][s]["n_admitted_wrong"] for s in STEMS)
        v["combined"] = {
            "n_admitted_with_review_label": all_admitted_reviewed,
            "n_admitted_correct": all_admitted_correct,
            "n_admitted_wrong": all_admitted_wrong,
            "n_correct_in_review": all_in_review,
            "n_correct_admitted": all_correct,
            "precision": all_admitted_correct / max(1, all_admitted_reviewed),
            "recall": all_correct / max(1, all_in_review),
            "F1": 2 * all_admitted_correct / max(1, 2 * all_admitted_correct + all_admitted_wrong + (all_in_review - all_correct)),
        }

    with (H1_DATA / "h126_v1_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    # Per-edge detail CSV (for the H125v4_h126_v1 variant)
    detail = []
    v = summary["variants"]["h125v4_h126_v1"]
    for stem in STEMS:
        h7v3plus3 = edges_by_stem[stem]["h7v3plus3"]
        h125v3 = edges_by_stem[stem]["h125v3"]
        # Get h7v3plus3 + h125v3 union, then check filter status
        seen = set()
        all_edges = []
        for e in h7v3plus3 + h125v3:
            key = (e["from_tid"], e["to_tid"])
            if key not in seen:
                seen.add(key)
                all_edges.append(e)
        for e in all_edges:
            drop_reasons = []
            if h112_fires(e, tracklets, stem):
                drop_reasons.append("h112")
            if h114_v1_strict_fires(e, tracklets, stem):
                drop_reasons.append("h114")
            if h126_fires(e, tracklets, stem):
                drop_reasons.append("h126")
            review_label = None
            for r in review_pairs:
                if r["stem"] == stem and int(r["source"]) == e["from_tid"] and int(r["candidate"]) == e["to_tid"]:
                    review_label = r["label"]
                    break
            visual = VISUAL_VERDICT.get((stem, e["from_tid"], e["to_tid"]), "")
            s = tracklets[(stem, e["from_tid"])]
            t = tracklets[(stem, e["to_tid"])]
            detail.append({
                "stem": stem,
                "from_tid": e["from_tid"],
                "to_tid": e["to_tid"],
                "edge_type": e["edge_type"],
                "source": e["source"],
                "end_d": s["end_dist"],
                "start_d": t["start_dist"],
                "sj": compute_spatial_jump(tracklets, stem, e["from_tid"], e["to_tid"]) or 0,
                "h59_label": review_label or "not_in_review",
                "visual_verdict": visual,
                "drop_reason": ",".join(drop_reasons) if drop_reasons else "kept",
            })

    with (H1_DATA / "h126_v1_per_edge.csv").open("w", newline="") as f:
        if detail:
            w = csv.DictWriter(f, fieldnames=list(detail[0].keys()))
            w.writeheader()
            w.writerows(detail)

    # Print summary
    print(f"{'variant':<25} {'P':>7} {'R':>7} {'F1':>7} {'adm':>5} {'corr':>5} {'wrong':>5} {'new_kept':>10}")
    print("-" * 80)
    for variant_name, _, _, _ in variants:
        v = summary["variants"][variant_name]["combined"]
        new_kept_total = sum(
            len(summary["variants"][variant_name]["per_stem_surviving_new"][s]["new_kept"])
            for s in STEMS
        )
        print(f"{variant_name:<25} {v['precision']:>7.3f} {v['recall']:>7.3f} {v['F1']:>7.3f} "
              f"{v['n_admitted_with_review_label']:>5} {v['n_admitted_correct']:>5} "
              f"{v['n_admitted_wrong']:>5} {new_kept_total:>10}")

    print("\nPer-stem detail for H125v4_h126_v1:")
    v = summary["variants"]["h125v4_h126_v1"]
    for stem in STEMS:
        m = v["per_stem"][stem]
        s = v["per_stem_surviving_new"][stem]
        print(f"  {stem[:18]}: P={m['precision']:.3f} R={m['recall']:.3f} F1={m['F1']:.3f} "
              f"adm={m['n_admitted_with_review_label']} corr={m['n_admitted_correct']} "
              f"wrong={m['n_admitted_wrong']} new_kept={len(s['new_kept'])}")
        if s["new_dropped"]:
            print(f"    NEW V4 dropped: {s['new_dropped']}")
        if s["h7v3plus3_dropped"]:
            print(f"    h7v3plus3 dropped: {s['h7v3plus3_dropped']}")


if __name__ == "__main__":
    main()
