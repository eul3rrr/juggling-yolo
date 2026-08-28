#!/usr/bin/env python3
"""H125 v3 — H7 min-cost flow on full E6c with sensitivity grid.

Hypothesis: the cost formula `cost = 2.0 + 0.05*err + 0.1*gap` is the
H7 default. We can choose AIR_ERR_SCALE and AIR_GAP_SCALE from physical
geometry, NOT from the review labels. The review labels are for evaluation
only.

Physical-geometry defaults:
- AIR_ERR_SCALE: per-pixel trajectory fit error. A real ballistic edge
  has err~0-10 (the parabolic model fits the 2D trajectory well). A
  cross-ball artifact has err~30-100. So 0.05 is a reasonable scale.
- AIR_GAP_SCALE: per-frame time gap. A typical juggling throw has gap
  0-30 frames (0-1 sec at 30fps). 0.1 is a reasonable scale.

Sensitivity grid (declared before running):
- AIR_ERR_SCALE ∈ {0.025, 0.05, 0.075, 0.10, 0.15}
- AIR_GAP_SCALE ∈ {0.05, 0.10, 0.15, 0.20}
- (each combination: 5×4 = 20 cells)

Output: per-stem precision/recall at each setting, plus the
EDGE-LEVEL decisions (which edges are admitted) so we can check
sensitivity of the per-edge results.

We use the full_e6c_no_h7v2 variant (no hand-link edges), which has
the cleanest separation: 65 correct + 4 wrong in the default setting.
"""

from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Default H7 thresholds
DEFAULTS = {
    "HAND_EDGE_COST": 1.0,
    "AMBIGUOUS_HAND_EDGE_COST": 1.5,
    "AIR_EDGE_BASE_COST": 2.0,
}


def load_tracklet_features(stem):
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for r in csv.DictReader(f):
            if r["stem"] != stem:
                continue
            out[int(r["tid"])] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
            }
    return out


def load_e6c_candidates(stem):
    out = []
    with (DETECTIONS / f"{stem}_norfair_dt50_hc5_accepted_stitches.csv").open() as f:
        for r in csv.DictReader(f):
            out.append({
                "from_tid": int(r["source_tracklet"]),
                "to_tid": int(r["candidate_tracklet"]),
                "err": float(r["trajectory_fit_error"]),
            })
    return out


def h7_min_cost_flow(edges, tracklets, err_scale, gap_scale):
    edges_with_cost = []
    for e in edges:
        src = e["from_tid"]
        tgt = e["to_tid"]
        if src not in tracklets or tgt not in tracklets:
            continue
        gap = max(0, tracklets[tgt]["first_frame"] - tracklets[src]["last_frame"])
        cost = (DEFAULTS["AIR_EDGE_BASE_COST"]
                + err_scale * e["err"]
                + gap_scale * gap)
        edges_with_cost.append({**e, "cost": cost, "gap": gap})

    edges_with_cost.sort(key=lambda e: e["cost"])

    succ = {}
    pred = {}
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

    return succ, admitted


def evaluate(stem, admitted, review_pairs):
    review_map = {}
    for r in review_pairs:
        if r['stem'] == stem:
            review_map[(int(r['source']), int(r['candidate']))] = r
    admitted_keys = set((e['from_tid'], e['to_tid']) for e in admitted)
    n_correct_in_review = sum(1 for r in review_pairs if r['stem'] == stem and r['label'] == 'correct')
    n_admitted_with_label = 0
    n_admitted_correct = 0
    n_admitted_wrong = 0
    n_correct_admitted = 0
    for (src, tgt), r in review_map.items():
        if (src, tgt) in admitted_keys:
            n_admitted_with_label += 1
            if r['label'] == 'correct':
                n_admitted_correct += 1
                n_correct_admitted += 1
            else:
                n_admitted_wrong += 1
    p = n_admitted_correct / max(1, n_admitted_with_label)
    r_v = n_correct_admitted / max(1, n_correct_in_review)
    return {
        "n_admitted_with_label": n_admitted_with_label,
        "n_correct": n_admitted_correct,
        "n_wrong": n_admitted_wrong,
        "n_correct_in_review": n_correct_in_review,
        "n_correct_admitted": n_correct_admitted,
        "precision": p,
        "recall": r_v,
        "F1": 2 * p * r_v / max(1e-9, p + r_v),
    }


def main():
    with (H1_DATA / "h59_per_pair_eval.csv").open() as f:
        review_pairs = list(csv.DictReader(f))

    err_scales = [0.025, 0.05, 0.075, 0.10, 0.15]
    gap_scales = [0.05, 0.10, 0.15, 0.20]

    grid_results = []
    for err_scale in err_scales:
        for gap_scale in gap_scales:
            cell = {
                "err_scale": err_scale,
                "gap_scale": gap_scale,
                "stems": {},
            }
            for stem in STEMS:
                tracklets = load_tracklet_features(stem)
                edges = load_e6c_candidates(stem)
                succ, admitted = h7_min_cost_flow(edges, tracklets, err_scale, gap_scale)
                ev = evaluate(stem, admitted, review_pairs)
                cell["stems"][stem] = {
                    "n_admitted": len(admitted),
                    "n_correct": ev["n_correct"],
                    "n_wrong": ev["n_wrong"],
                    "precision": ev["precision"],
                    "recall": ev["recall"],
                    "F1": ev["F1"],
                    "admitted_keys": [(e['from_tid'], e['to_tid']) for e in admitted],
                }
            grid_results.append(cell)

    # Print summary
    print(f'{"err":>6} {"gap":>6} | {"identical P":>10} {"R":>5} {"F1":>5} | {"youtube P":>10} {"R":>5} {"F1":>5} | combined P/R/F1')
    for cell in grid_results:
        es = cell["err_scale"]
        gs = cell["gap_scale"]
        i = cell["stems"]["identical_balls_trick_000_018"]
        y = cell["stems"]["youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"]
        # Combined
        tot_correct = i['n_correct'] + y['n_correct']
        tot_wrong = i['n_wrong'] + y['n_wrong']
        # Get review totals from the raw counts (need to recompute since we don't store them in cell)
        n_correct_review_total = sum(
            1 for rp in review_pairs if rp['label'] == 'correct'
        )
        tot_review = n_correct_review_total
        tot_adm_correct = sum(
            sum(1 for k in cell["stems"][s]["admitted_keys"] if any(
                rp['stem'] == s and int(rp['source']) == k[0] and int(rp['candidate']) == k[1] and rp['label'] == 'correct'
                for rp in review_pairs))
            for s in STEMS
        )
        tot_with_label = tot_correct + tot_wrong
        c_p = tot_correct / max(1, tot_with_label)
        c_r = tot_correct / max(1, tot_review)
        c_f1 = 2 * c_p * c_r / max(1e-9, c_p + c_r)
        print(f'{es:>6.3f} {gs:>6.2f} | {i["precision"]:>10.3f} {i["recall"]:>5.3f} {i["F1"]:>5.3f} | {y["precision"]:>10.3f} {y["recall"]:>5.3f} {y["F1"]:>5.3f} | {c_p:.3f}/{c_r:.3f}/{c_f1:.3f}')

    # Save
    with (H1_DATA / "h125_v3_grid_summary.json").open("w") as f:
        json.dump(grid_results, f, indent=2, default=str)

    # Save per-edge admitted for default setting
    err_scale, gap_scale = 0.05, 0.10
    for stem in STEMS:
        tracklets = load_tracklet_features(stem)
        edges = load_e6c_candidates(stem)
        succ, admitted = h7_min_cost_flow(edges, tracklets, err_scale, gap_scale)
        with (H1_DATA / f"h125_v3_default_admitted_{stem}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["from_tid", "to_tid", "cost", "err", "gap"])
            w.writeheader()
            for e in admitted:
                w.writerow({
                    "from_tid": e["from_tid"],
                    "to_tid": e["to_tid"],
                    "cost": f"{e['cost']:.3f}",
                    "err": f"{e['err']:.3f}",
                    "gap": e["gap"],
                })
    print('\nSaved: h125_v3_grid_summary.json + h125_v3_default_admitted_*.csv')


if __name__ == '__main__':
    main()
