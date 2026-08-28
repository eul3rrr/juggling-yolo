#!/usr/bin/env python3
"""H125 v2 — H7 min-cost flow on the FULL E6c candidate set.

Hypothesis: the H7 input is currently filtered to 33+25=58 edges (the
highest-quality subset). The 20 NOT_IN_CHAIN + correct review pairs
(17/20 = 85% in identical) are NOT in this filtered input. If we run
the same H7 min-cost flow on the full 85+28=113 E6c candidate set,
the additional capacity-rejected edges from the larger pool may
*block* the new ones (because they compete for the same targets).

But: the E6c-accepted column (27+26=53) marks a curated subset. We
should run H7 on:
  (a) the full 113 E6c candidate set (all rows, accepted=0/1)
  (b) only the 53 E6c-accepted rows
  (c) the original 58 H7 input (baseline)

This isolates the question: does E6c-accepted filtering improve or
hurt the H7 outcome?

Hypothesis (declared before reading outcomes):
  - Running on (a) the full 113 edges will produce more capacity-rejected
    edges and likely LOWER precision (because more wrong edges are now
    in the input).
  - Running on (b) the 53 E6c-accepted is the same input as H7 (we should
    verify that).
  - The key insight: the 20 NOT_IN_CHAIN + correct edges are NOT in the
    E6c-accepted set (only 3/20), so even the (b) variant will miss
    them.

EXPECTED OUTCOME:
  - (a) on full 113: precision will DROP because wrong edges now compete
    for capacity. Recall may go UP if the correct edges are picked.
  - (b) on 53 E6c-accepted: same as H7 (control).
  - The fundamental question: is there a CASCADE rule that admits the
    20 missing-correct edges WITHOUT admitting the 17-19 missing-wrong
    edges? The 17 missing-wrong edges include 14 that are top-1 wrong
    for their source (i.e., they are geometrically plausible wrongs).
"""

from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"

# H7 thresholds (declared from physical geometry)
H7 = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
    "AIR_ERR_SCALE": 0.05,
    "AIR_GAP_SCALE": 0.1,
    "NO_SUCCESSOR_COST": 0.0,
}

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_tracklet_features(stem):
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for r in csv.DictReader(f):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
            }
    return out


def load_e6c_candidates(stem, only_accepted=False):
    """Load E6c candidates. If only_accepted, filter to accepted=1."""
    out = []
    with (DETECTIONS / f"{stem}_norfair_dt50_hc5_accepted_stitches.csv").open() as f:
        for r in csv.DictReader(f):
            if only_accepted and r['accepted'] != '1':
                continue
            out.append({
                "from_tid": int(r["source_tracklet"]),
                "to_tid": int(r["candidate_tracklet"]),
                "edge_type": "BALLISTIC",
                "err": float(r["trajectory_fit_error"]),
                "e6c_accepted": r['accepted'] == '1',
            })
    return out


def load_h7v2_edges(stem):
    """Load h7v2 admitted edges as HAND_TRANSITION / AMBIGUOUS_HAND_TRANSITION."""
    out = []
    with (H1_DATA / f"h7v2_admitted_edges_{stem}.csv").open() as f:
        for r in csv.DictReader(f):
            et = r["edge_type"]
            # Default metadata fields
            err = 0.0
            meta = r.get("metadata", "")
            if et == "RECLASSIFIED_HAND_TRANSITION" or et == "V_RECLASSIFIED_HAND_TRANSITION":
                # extract err from metadata
                m = meta
                if "err=" in m:
                    try:
                        err = float(m.split("err=")[1].split(",")[0].split(";")[0])
                    except (ValueError, IndexError):
                        err = 0.0
            out.append({
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "edge_type": et,
                "err": err,
            })
    return out


def edge_cost(e, src_last_frame, tgt_first_frame):
    et = e["edge_type"]
    if et in ("HAND_TRANSITION", "RECLASSIFIED_HAND_TRANSITION",
              "V_RECLASSIFIED_HAND_TRANSITION", "H26_RECLASSIFIED_HAND_TRANSITION"):
        return H7["HAND_EDGE_COST"]
    if et == "AMBIGUOUS_HAND_TRANSITION":
        return H7["AMBIGUOUS_HAND_EDGE_COST"]
    if et == "BALLISTIC":
        gap = max(0, tgt_first_frame - src_last_frame)
        return (H7["AIR_EDGE_BASE_COST"]
                + H7["AIR_ERR_SCALE"] * e["err"]
                + H7["AIR_GAP_SCALE"] * gap)
    return 5.0


def h7_min_cost_flow(edges, tracklets):
    """Greedy iterative min-cost flow (same as h7_min_cost_flow.py)."""
    edges_with_cost = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        if src not in tracklets or tgt not in tracklets:
            continue
        cost = edge_cost(e, tracklets[src]["last_frame"], tracklets[tgt]["first_frame"])
        edges_with_cost.append({**e, "cost": cost})

    edges_with_cost.sort(key=lambda e: e["cost"])

    succ: dict = {}
    pred: dict = {}
    admitted = []

    def would_cycle(src, tgt):
        cur = src
        seen = set()
        while cur in succ and cur not in seen:
            seen.add(cur)
            cur = succ[cur]
            if cur == tgt:
                return True
        return False

    for e in edges_with_cost:
        src, tgt = e["from_tid"], e["to_tid"]
        if src in succ:
            continue
        if tgt in pred:
            continue
        if would_cycle(src, tgt):
            continue
        succ[src] = tgt
        pred[tgt] = src
        admitted.append(e)

    stats = {
        "n_edges_in": len(edges_with_cost),
        "n_admitted": len(admitted),
        "n_rejected_capacity": len(edges_with_cost) - len(admitted),
    }
    return succ, admitted, stats


def walk_chains(succ, all_tids):
    has_pred = set(succ.values())
    roots = sorted(t for t in all_tids if t not in has_pred)
    chains = []
    for r in roots:
        chain = [r]
        cur = r
        while cur in succ:
            nxt = succ[cur]
            if nxt in chain:
                break
            chain.append(nxt)
            cur = nxt
        chains.append(chain)
    return chains


def evaluate_chain(stem, admitted_edges, review_pairs):
    """Compute P/R/F1 vs the 113 review pairs."""
    # Map (stem, src, tgt) -> label
    review_map = {}
    for r in review_pairs:
        if r['stem'] == stem:
            review_map[(int(r['source']), int(r['candidate']))] = r

    # Admitted edge set
    admitted_keys = set((e['from_tid'], e['to_tid']) for e in admitted_edges)

    # P: of admitted edges with a review label, fraction that are correct
    # R: of correct review pairs, fraction that are admitted
    n_admitted_reviewed = 0
    n_admitted_correct = 0
    n_correct_in_review = sum(1 for r in review_pairs if r['stem'] == stem and r['label'] == 'correct')
    n_correct_admitted = 0
    n_admitted_with_label = 0
    n_admitted_wrong = 0
    n_unreviewed_admitted = 0
    for (src, tgt), r in review_map.items():
        if (src, tgt) in admitted_keys:
            n_admitted_with_label += 1
            if r['label'] == 'correct':
                n_admitted_correct += 1
                n_correct_admitted += 1
            else:
                n_admitted_wrong += 1

    # P = correct / reviewed
    precision = n_admitted_correct / max(1, n_admitted_with_label)
    recall = n_correct_admitted / max(1, n_correct_in_review)

    return {
        "n_admitted_with_review_label": n_admitted_with_label,
        "n_admitted_correct": n_admitted_correct,
        "n_admitted_wrong": n_admitted_wrong,
        "n_correct_in_review": n_correct_in_review,
        "n_correct_admitted": n_correct_admitted,
        "precision": precision,
        "recall": recall,
        "F1": 2 * precision * recall / max(1e-9, precision + recall),
    }


def main():
    # Load review pairs
    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        review_pairs = list(csv.DictReader(f))

    summary = {"h7_thresholds": H7, "variants": {}}

    for variant_name, e6c_filter, add_h7v2 in [
        ("full_e6c", False, True),         # all 113 E6c + h7v2 hand-link edges
        ("e6c_accepted_only", True, True),  # 53 E6c-accepted + h7v2 hand-link edges
        ("full_e6c_no_h7v2", False, False),  # all 113 E6c only (no hand-link edges)
        ("e6c_accepted_no_h7v2", True, False),  # 53 E6c-accepted only
    ]:
        print(f'\n=== Variant: {variant_name} ===')
        summary["variants"][variant_name] = {"stems": {}}
        for stem in STEMS:
            tracklets = load_tracklet_features(stem)
            edges = []
            edges.extend(load_e6c_candidates(stem, only_accepted=e6c_filter))
            if add_h7v2:
                edges.extend(load_h7v2_edges(stem))
            print(f'\n  {stem[:30]}: {len(edges)} input edges')
            succ, admitted, stats = h7_min_cost_flow(edges, tracklets)
            chains = walk_chains(succ, sorted(tracklets.keys()))
            n_multi = sum(1 for c in chains if len(c) > 1)
            longest = max(chains, key=len) if chains else []
            eval_metrics = evaluate_chain(stem, admitted, review_pairs)
            print(f'    H7: {len(chains)} chains ({n_multi} multi, longest {len(longest)})')
            print(f'    admitted: {stats["n_admitted"]}/{stats["n_edges_in"]}, capacity-rejected: {stats["n_rejected_capacity"]}')
            print(f'    eval: P={eval_metrics["precision"]:.3f} R={eval_metrics["recall"]:.3f} F1={eval_metrics["F1"]:.3f}')
            print(f'    admitted with label: {eval_metrics["n_admitted_with_review_label"]} (correct: {eval_metrics["n_admitted_correct"]}, wrong: {eval_metrics["n_admitted_wrong"]})')
            print(f'    correct review: {eval_metrics["n_correct_in_review"]} (admitted: {eval_metrics["n_correct_admitted"]})')
            summary["variants"][variant_name]["stems"][stem] = {
                "n_edges_in": stats["n_edges_in"],
                "n_admitted": stats["n_admitted"],
                "n_rejected_capacity": stats["n_rejected_capacity"],
                "n_chains": len(chains),
                "n_chains_multi": n_multi,
                "longest": len(longest),
                "longest_chain": longest,
                "eval": eval_metrics,
                "admitted_edges": admitted,
            }

    # Save summary
    with (H1_DATA / "h125_v2_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Per-variant per-edge CSVs
    for variant_name in summary["variants"]:
        for stem in STEMS:
            v = summary["variants"][variant_name]["stems"][stem]
            with (H1_DATA / f"h125_v2_{variant_name}_admitted_{stem}.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["from_tid", "to_tid", "edge_type", "cost", "e6c_accepted", "err"])
                w.writeheader()
                for e in v["admitted_edges"]:
                    w.writerow({
                        "from_tid": e["from_tid"],
                        "to_tid": e["to_tid"],
                        "edge_type": e["edge_type"],
                        "cost": f"{e['cost']:.3f}",
                        "e6c_accepted": e.get("e6c_accepted", ""),
                        "err": e.get("err", 0.0),
                    })


if __name__ == '__main__':
    main()
