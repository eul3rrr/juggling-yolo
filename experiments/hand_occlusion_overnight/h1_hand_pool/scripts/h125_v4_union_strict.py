#!/usr/bin/env python3
"""H125 v4 — Union of h7v3plus3 + H125 v3 BALLISTIC, with H112 + H114 v1 strict
post-filters applied to the union.

Hypothesis (declared BEFORE reading outcomes):
  - H125 v3 admits 18 NEW BALLISTIC edges (rank-1 capacity-conflicts that
    h7v3plus3 excluded).
  - All 18 NEW edges trigger H114 v1 strict (T_d=40, T_j=250) because
    the E6c `accepted=1` filter was a geometric pre-filter.
  - H125 v4 tests whether the stricter T_d=25, T_j=200 threshold
    (H115 v3 default) is more discriminating. Some NEW edges that
    triggered the loose H114 default (40, 250) might pass the strict
    (25, 200) — they're real catch-throws, not artifacts.

Three sub-experiments:
  v1: h7v3plus3 + H125 v3 union, then apply H112 (cross-hand + end>30 + start>30)
  v2: h7v3plus3 + H125 v3 union, then apply H112 + H114 v1 strict (T_d=40, T_j=250)
  v3: h7v3plus3 + H125 v3 union, then apply H112 + H114 v1 strict (T_d=25, T_j=200)
  v4: h7v3plus3 + H125 v3 union, then apply H112 + H114 v1 strict (T_d=20, T_j=150)

Each sub-experiment:
  - Reports the 113-pair P/R
  - Reports which NEW V4 edges (those in union but not in h7v3plus3) survive
  - Reports which h7v3plus3 BALLISTIC edges are dropped by H112+H114 strict

EXPECTED OUTCOME:
  - v1 (just H112): admits most NEW edges, drops H7v3plus3's 22→27 FP
  - v2 (H112 + loose H114): drops all 18 NEW edges (H125 report claim)
  - v3 (H112 + strict H114): may admit 1-3 NEW edges that pass strict
  - The 2 H59 mislabels (12→17, 16→21) should be in the union but should
    fail the strict filter (they were visually confirmed TRACKER_FRAGMENTATION)
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def _opt_float(s, default=0.0):
    """Convert to float, returning default on empty/None."""
    if s is None or s == "":
        return default
    return float(s)


def load_tracklet_features():
    """Load per-tracklet end_d, start_d, end_side, start_side."""
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for r in csv.DictReader(f):
            tid = int(r["tid"])
            out[(r["stem"], tid)] = {
                "tid": tid,
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "first_x": _opt_float(r["first_x"]),
                "first_y": _opt_float(r["first_y"]),
                "end_x": _opt_float(r["last_x"]),
                "end_y": _opt_float(r["last_y"]),
                "end_side": r["end_side"] or "",
                "end_dist": _opt_float(r["end_dist"], 999.0),  # large if missing
                "end_slope": _opt_float(r["end_slope"]),
                "start_side": r["start_side"] or "",
                "start_dist": _opt_float(r["start_dist"], 999.0),
                "start_slope": _opt_float(r["start_slope"]),
            }
    return out


def load_h7v3plus3_edges(stem):
    """Load h7v3plus3 admitted edges."""
    out = []
    path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
    with path.open() as f:
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
    """Load H125 v3 admitted edges (full_e6c_no_h7v2, BALLISTIC only)."""
    out = []
    path = H1_DATA / f"h125_v3_default_admitted_{stem}.csv"
    with path.open() as f:
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
    """Compute Euclidean spatial jump using H114 v1 method:
    hypot(tgt.first_x - src.last_x, tgt.first_y - src.last_y)
    This is the feat-based spatial jump used by H114/H115/H117.
    Per H121, feat_jump >= raw_jump (tracklet_features is truncated 2-5
    frames before raw last frame), so this is a CONSERVATIVE upper bound
    on the spatial jump.
    """
    s = tracklets[(stem, src)]
    t = tracklets[(stem, tgt)]
    return math.hypot(t["first_x"] - s["end_x"], t["first_y"] - s["end_y"])


def compute_spatial_jump_v2(tracklets, stem, src, tgt):
    """Same as compute_spatial_jump — alias kept for clarity."""
    return compute_spatial_jump(tracklets, stem, src, tgt)


def apply_h112(e, tracklets, stem, end_thr=30):
    """H112: reject cross-hand handoff if end_d > 30 AND start_d > 30.
    Returns True if edge should be DROPPED."""
    if e["edge_type"] not in ("HAND_TRANSITION", "AMBIGUOUS_HAND_TRANSITION",
                             "RECLASSIFIED_HAND_TRANSITION", "V_RECLASSIFIED_HAND_TRANSITION",
                             "H26_RECLASSIFIED_HAND_TRANSITION", "H22_RECLASSIFIED_HAND_TRANSITION"):
        return False  # H112 only applies to hand-classified edges
    s = tracklets[(stem, e["from_tid"])]
    t = tracklets[(stem, e["to_tid"])]
    if s["end_side"] != t["start_side"]:  # cross-hand
        if s["end_dist"] > end_thr and t["start_dist"] > end_thr:
            return True
    return False


def apply_h114_v1_strict(e, tracklets, stem, t_d=25, t_j=200):
    """H114 v1 strict: reject if (end_d > t_d AND start_d > t_d) AND spatial_jump > t_j.
    Returns True if edge should be DROPPED."""
    s = tracklets[(stem, e["from_tid"])]
    t = tracklets[(stem, e["to_tid"])]
    if s["end_dist"] > t_d and t["start_dist"] > t_d:
        jump = compute_spatial_jump_v2(tracklets, stem, e["from_tid"], e["to_tid"])
        if jump > t_j:
            return True
    return False


def evaluate_admitted(admitted_edges, review_pairs, stem):
    """Compute P/R on the 113 review pairs for a given stem."""
    review_map = {}
    for r in review_pairs:
        if r['stem'] == stem:
            review_map[(int(r['source']), int(r['candidate']))] = r

    admitted_keys = set((e['from_tid'], e['to_tid']) for e in admitted_edges)
    n_admitted_with_label = 0
    n_admitted_correct = 0
    n_admitted_wrong = 0
    n_correct_in_review = sum(1 for r in review_pairs if r['stem'] == stem and r['label'] == 'correct')
    n_correct_admitted = 0
    for (src, tgt), r in review_map.items():
        if (src, tgt) in admitted_keys:
            n_admitted_with_label += 1
            if r['label'] == 'correct':
                n_admitted_correct += 1
                n_correct_admitted += 1
            else:
                n_admitted_wrong += 1

    precision = n_admitted_correct / max(1, n_admitted_with_label)
    recall = n_correct_admitted / max(1, n_correct_in_review)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    return {
        "n_admitted_with_review_label": n_admitted_with_label,
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

    # Load review pairs
    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        review_pairs = list(csv.DictReader(f))

    # Load edges
    edges_by_stem = {}
    for stem in STEMS:
        h7v3plus3 = load_h7v3plus3_edges(stem)
        h125v3 = load_h125_v3_edges(stem)
        edges_by_stem[stem] = {"h7v3plus3": h7v3plus3, "h125v3": h125v3}

    summary = {"variants": {}}

    # Variant definitions
    variants = [
        ("union", lambda e, t, s: False),  # No filter
        ("union_h112", lambda e, t, s: apply_h112(e, t, s, 30)),  # H112 only
        ("union_h112_h114_40_250", lambda e, t, s: apply_h112(e, t, s, 30) or apply_h114_v1_strict(e, t, s, 40, 250)),  # H112 + H114 default
        ("union_h112_h114_25_200", lambda e, t, s: apply_h112(e, t, s, 30) or apply_h114_v1_strict(e, t, s, 25, 200)),  # H112 + H114 strict
        ("union_h112_h114_20_150", lambda e, t, s: apply_h112(e, t, s, 30) or apply_h114_v1_strict(e, t, s, 20, 150)),  # H112 + H114 stricter
        ("h7v3plus3_only_h112_h114_25_200", lambda e, t, s: apply_h112(e, t, s, 30) or apply_h114_v1_strict(e, t, s, 25, 200)),  # h7v3plus3 only + strict
    ]

    for variant_name, filter_fn in variants:
        per_stem_metrics = {}
        per_stem_surviving_new = {}
        for stem in STEMS:
            h7v3plus3 = edges_by_stem[stem]["h7v3plus3"]
            h125v3 = edges_by_stem[stem]["h125v3"]

            if variant_name == "h7v3plus3_only_h112_h114_25_200":
                # Only h7v3plus3
                all_edges = list(h7v3plus3)
            else:
                # Union: h7v3plus3 + H125 v3
                seen = set()
                all_edges = []
                for e in h7v3plus3 + h125v3:
                    key = (e["from_tid"], e["to_tid"])
                    if key not in seen:
                        seen.add(key)
                        all_edges.append(e)

            # Apply filter
            kept = []
            dropped = []
            for e in all_edges:
                if filter_fn(e, tracklets, stem):
                    dropped.append(e)
                else:
                    kept.append(e)

            # NEW edges: in union but not in h7v3plus3
            h7v3plus3_keys = set((e["from_tid"], e["to_tid"]) for e in h7v3plus3)
            new_surviving = [e for e in kept if (e["from_tid"], e["to_tid"]) not in h7v3plus3_keys]
            new_dropped = [e for e in dropped if (e["from_tid"], e["to_tid"]) not in h7v3plus3_keys]

            metrics = evaluate_admitted(kept, review_pairs, stem)
            per_stem_metrics[stem] = metrics
            per_stem_surviving_new[stem] = {
                "new_kept": [(e["from_tid"], e["to_tid"]) for e in new_surviving],
                "new_dropped": [(e["from_tid"], e["to_tid"]) for e in new_dropped],
                "h7v3plus3_dropped": [(e["from_tid"], e["to_tid"]) for e in dropped
                                       if (e["from_tid"], e["to_tid"]) in h7v3plus3_keys],
            }
        summary["variants"][variant_name] = {
            "per_stem": per_stem_metrics,
            "per_stem_surviving_new": per_stem_surviving_new,
        }

    # Combined P/R/F1 across both videos
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

    with (H1_DATA / "h125_v4_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    # Print concise results
    print(f"{'variant':<35} {'P':>7} {'R':>7} {'F1':>7} {'adm':>5} {'corr':>5} {'wrong':>5} {'new_surv':>10}")
    for variant_name, _ in variants:
        v = summary["variants"][variant_name]["combined"]
        ns = sum(len(v2["new_kept"]) for s in STEMS for v2 in [summary["variants"][variant_name]["per_stem_surviving_new"][s]])
        print(f"{variant_name:<35} {v['precision']:>7.3f} {v['recall']:>7.3f} {v['F1']:>7.3f} {v['n_admitted_with_review_label']:>5} {v['n_admitted_correct']:>5} {v['n_admitted_wrong']:>5} {ns:>10}")

    print("\nPer-stem detail for each variant:")
    for variant_name, _ in variants:
        print(f"\n  {variant_name}:")
        for stem in STEMS:
            m = summary["variants"][variant_name]["per_stem"][stem]
            s = summary["variants"][variant_name]["per_stem_surviving_new"][stem]
            print(f"    {stem[-20:]}: P={m['precision']:.3f} R={m['recall']:.3f} F1={m['F1']:.3f} "
                  f"adm={m['n_admitted_with_review_label']} corr={m['n_admitted_correct']} wrong={m['n_admitted_wrong']} "
                  f"new_kept={len(s['new_kept'])} new_dropped={len(s['new_dropped'])} h7v3+_dropped={len(s['h7v3plus3_dropped'])}")
            if s["new_kept"]:
                print(f"      NEW V4 SURVIVING edges: {s['new_kept']}")
            if s["h7v3plus3_dropped"]:
                print(f"      H7v3plus3 edges DROPPED by strict: {s['h7v3plus3_dropped']}")


if __name__ == "__main__":
    main()
