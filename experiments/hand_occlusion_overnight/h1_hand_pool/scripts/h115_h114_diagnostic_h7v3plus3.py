#!/usr/bin/env python3
"""H115: H114 v1 diagnostic on h7v3plus3 added edges + wider H20-KEPT pool.

H114 conclusion (from STATE.md): "H114 v1 (T_d=40, T_j=250) is a useful
post-hoc validation tool. The cross-hand vs same-hand distinction is
essential." H114's primary verification was on the 113 manual review
pairs; only 4 edges in h7v3plus3 (the recommended operating point)
were not in the 113 review pairs. H115 closes this gap and also
extends H114 v1 to the wider H20-KEPT candidate pool.

H115 has three sub-experiments:

H115 v1 — H114 v1 diagnostic on the 4 h7v3plus3 added edges.
  Tests whether the post-hoc validation signal (T_d=40, T_j=250) flags
  any of the 4 edges that h7v3pure/h7v2 missed but the recommended
  operating point (h7v3plus3) added. If 0/4 fire, the operating point
  is robust to the H114 v1 filter.

H115 v2 — H114 v1 as a pre-filter for the 115 H20-KEPT candidates.
  Computes per-edge (end_d, start_d, spatial_jump) for all 115 H20-KEPT
  candidates and tests whether H114 v1 (T_d=40, T_j=250) separates
  REAL catch-throws from FALSE positives in the 29 visually-QA'd
  subset. Reports precision/recall on the 29.

H115 v3 — H21-style chain augmentation using H114 v1 as pre-filter.
  Tests the hypothesis: a H21-style augmentation that uses H114 v1
  as a pre-filter (in addition to H20's in-hand + vel-jump + apex
  filters) has higher visual precision than H20 alone. Reports
  per-pool FPR/precision on the 29 visually-QA'd.

Per master §15: thresholds are declared before reading outcomes.
- H115 v1: H114 v1 at (T_d=40, T_j=250) is the recommended diagnostic
- H115 v2/v3: (T_d=40, T_j=250) is the post-hoc validation threshold

Outputs:
- data/h115_per_edge.csv: 4 h7v3plus3 added edges + H114 v1 outputs
- data/h115_h20_kept_per_edge.csv: 115 H20-KEPT + H114 v1 outputs
- data/h115_summary.json: aggregate stats
- contact_sheets_h115/: visual QA on the edges that fire

Note: 4 h7v3plus3-added edges are in the 113 review pairs.
- 7->10 identical (in 113, correct) — H26_RECLASSIFIED_HAND_TRANSITION
- 59->61 identical (NOT in 113) — H26_RECLASSIFIED_HAND_TRANSITION
- 20->21 YouTube (in 113, correct) — H22_RECLASSIFIED_HAND_TRANSITION
- 16->21 YouTube (REMOVED by H22) — NOT_IN_CHAIN
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
H114_PER_EDGE = H1_DATA / "h114_per_edge.csv"
H20_KEPT = H1_DATA / "h20_strict_v_shape_positives_inhand.csv"
H24_QA = H1_DATA / "h24_visual_qa_verdicts.csv"
H28_QA = H1_DATA / "h28_visual_qa_verdicts.csv"
H7V3PURE = "h7v3pure_admitted_edges_{}.csv"
H7V3PLUS2 = "h7v3plus2_admitted_edges_{}.csv"
H7V3PLUS3 = "h7v3plus3_admitted_edges_{}.csv"

VIDEOS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H115 thresholds (declared before reading outcomes)
H114_DIAGNOSTIC_TD = 40.0
H114_DIAGNOSTIC_TJ = 250.0
H115_V2_TD = 40.0
H115_V2_TJ = 250.0


def load_tracklet_features() -> dict:
    """Per (stem, tid) -> dict with end_dist, start_dist, end_side,
    start_side, last_x, last_y, first_x, first_y, last_frame, first_frame.
    """
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


def load_chain_set(variant_template: str) -> set:
    """Return set of (stem, src, tgt) in the named chain set."""
    out = set()
    for stem in VIDEOS:
        path = H1_DATA / variant_template.format(stem)
        if not path.exists():
            continue
        with path.open() as f:
            for row in csv.DictReader(f):
                out.add((stem, int(row["from_tid"]), int(row["to_tid"])))
    return out


def spatial_jump(src: dict, tgt: dict) -> float:
    return math.hypot(tgt["first_x"] - src["last_x"],
                      tgt["first_y"] - src["last_y"])


def rule_v1_fires(src: dict, tgt: dict, td: float, tj: float) -> tuple[bool, float]:
    """Return (fires, spatial_jump) under H114 v1 rule."""
    if src["end_dist"] is None or tgt["start_dist"] is None:
        return False, None
    sj = spatial_jump(src, tgt)
    fires = (sj > tj) and (src["end_dist"] > td) and (tgt["start_dist"] > td)
    return fires, sj


def main():
    tf = load_tracklet_features()
    h7v3pure = load_chain_set(H7V3PURE)
    h7v3plus3 = load_chain_set(H7V3PLUS3)
    h7v3plus2 = load_chain_set(H7V3PLUS2)

    # === H115 v1: H114 v1 diagnostic on h7v3plus3 added edges ===
    added_in_plus3 = h7v3plus3 - h7v3pure
    removed_in_plus3 = h7v3pure - h7v3plus3
    print("=" * 70)
    print("H115 v1: H114 v1 diagnostic on h7v3plus3 added/removed edges")
    print("=" * 70)
    print(f"h7v3pure: {len(h7v3pure)} edges, h7v3plus3: {len(h7v3plus3)} edges")
    print(f"Added in plus3: {sorted(added_in_plus3)}")
    print(f"Removed in plus3: {sorted(removed_in_plus3)}")

    # All chain diff edges (added + removed)
    diff_edges = sorted(added_in_plus3 | removed_in_plus3)
    per_edge_v1 = []
    for stem, src, tgt in diff_edges:
        src_d = tf.get((stem, src))
        tgt_d = tf.get((stem, tgt))
        fires, sj = rule_v1_fires(src_d, tgt_d, H114_DIAGNOSTIC_TD,
                                   H114_DIAGNOSTIC_TJ)
        in_chain = (stem, src, tgt) in h7v3plus3
        in_pure = (stem, src, tgt) in h7v3pure
        in_plus2 = (stem, src, tgt) in h7v3plus2
        status = "ADDED" if in_chain and not in_pure else \
                 "REMOVED" if in_pure and not in_chain else "BOTH"
        print(f"  {status:8} {stem[:25]:25} {src:>3}->{tgt:<3} "
              f"end_d={src_d['end_dist']:6.1f} start_d={tgt_d['start_dist']:6.1f} "
              f"sj={sj:6.1f} fires_H114_v1={fires}")
        per_edge_v1.append({
            "stem": stem,
            "src": src,
            "tgt": tgt,
            "end_d": src_d["end_dist"],
            "start_d": tgt_d["start_dist"],
            "end_side": src_d["end_side"],
            "start_side": tgt_d["start_side"],
            "spatial_jump": sj,
            "in_h7v3plus3": in_chain,
            "in_h7v3plus2": in_plus2,
            "in_h7v3pure": in_pure,
            "status": status,
            "h114_v1_fires_TD40_TJ250": fires,
        })

    # === H115 v2: H114 v1 on the 115 H20-KEPT candidates ===
    print()
    print("=" * 70)
    print("H115 v2: H114 v1 (T_d=40, T_j=250) on 115 H20-KEPT candidates")
    print("=" * 70)
    h20_rows = []
    with H20_KEPT.open() as f:
        for row in csv.DictReader(f):
            if row["h20_keep"] != "True":
                continue
            h20_rows.append(row)
    print(f"Loaded {len(h20_rows)} H20-KEPT candidates")

    # Load H24 / H28 visual QA verdicts
    h24_qa = {}
    with H24_QA.open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["from_tid"]), int(row["to_tid"]))
            h24_qa[key] = row["verdict"]
    h28_qa = {}
    with H28_QA.open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["from_tid"]), int(row["to_tid"]))
            h28_qa[key] = row["vision_verdict"]

    h20_per_edge = []
    fire_count = 0
    for row in h20_rows:
        stem = row["stem"]
        src = int(row["from_tid"])
        tgt = int(row["to_tid"])
        src_d = tf.get((stem, src))
        tgt_d = tf.get((stem, tgt))
        if src_d is None or tgt_d is None:
            continue
        fires, sj = rule_v1_fires(src_d, tgt_d, H115_V2_TD, H115_V2_TJ)
        verdict = h24_qa.get((stem, src, tgt),
                              h28_qa.get((stem, src, tgt), None))
        is_in_chain = (stem, src, tgt) in h7v3plus3
        if fires:
            fire_count += 1
        h20_per_edge.append({
            "stem": stem,
            "src": src,
            "tgt": tgt,
            "vshape": row["vshape"],
            "in_hand_px": row["in_hand_px"],
            "min_hand_dist": row["min_hand_dist"],
            "gap_dist": row["gap_dist"],
            "gap_vel": row["gap_vel"],
            "apex_src_dist": row["apex_src_dist"],
            "h20_keep": row["h20_keep"],
            "end_d": src_d["end_dist"],
            "start_d": tgt_d["start_dist"],
            "end_side": src_d["end_side"],
            "start_side": tgt_d["start_side"],
            "spatial_jump": sj,
            "h114_v1_fires_TD40_TJ250": fires,
            "visual_qa_verdict": verdict,
            "in_h7v3plus3": is_in_chain,
        })

    print(f"Total H20-KEPT candidates with tracklet data: {len(h20_per_edge)}")
    print(f"H114 v1 (T_d=40, T_j=250) fires on: {fire_count} candidates")

    # === Precision/recall on the visually-QA'd subset ===
    qa_subset = [r for r in h20_per_edge if r["visual_qa_verdict"] is not None]
    print(f"\nVisually-QA'd H20-KEPT: {len(qa_subset)}")
    if qa_subset:
        # Verdicts in QA: REAL, PARTIAL, FALSE, UNCLEAR
        # Define "is_TRUE" = REAL or PARTIAL
        def is_true(r):
            return r["visual_qa_verdict"] in ("REAL", "PARTIAL")
        def is_real(r):
            return r["visual_qa_verdict"] == "REAL"
        def is_false(r):
            return r["visual_qa_verdict"] == "FALSE"

        n_real = sum(1 for r in qa_subset if is_real(r))
        n_true = sum(1 for r in qa_subset if is_true(r))
        n_false = sum(1 for r in qa_subset if is_false(r))
        print(f"  REAL: {n_real}")
        print(f"  REAL+PARTIAL: {n_true}")
        print(f"  FALSE: {n_false}")

        # Among H114 v1 KEEPs (not rejected), what is precision?
        kept_by_h114 = [r for r in qa_subset if not r["h114_v1_fires_TD40_TJ250"]]
        rejected_by_h114 = [r for r in qa_subset if r["h114_v1_fires_TD40_TJ250"]]
        n_kept_real = sum(1 for r in kept_by_h114 if is_real(r))
        n_kept_true = sum(1 for r in kept_by_h114 if is_true(r))
        n_kept_false = sum(1 for r in kept_by_h114 if is_false(r))
        n_rej_real = sum(1 for r in rejected_by_h114 if is_real(r))
        n_rej_true = sum(1 for r in rejected_by_h114 if is_true(r))
        n_rej_false = sum(1 for r in rejected_by_h114 if is_false(r))

        print(f"\n  H114 v1 KEPT (not rejected): {len(kept_by_h114)}")
        print(f"    REAL: {n_kept_real}, REAL+PARTIAL: {n_kept_true}, "
              f"FALSE: {n_kept_false}")
        if len(kept_by_h114) > 0:
            print(f"    precision (REAL): {n_kept_real/len(kept_by_h114):.3f}")
            print(f"    precision (REAL+PARTIAL): {n_kept_true/len(kept_by_h114):.3f}")
        print(f"  H114 v1 REJECTED: {len(rejected_by_h114)}")
        print(f"    REAL: {n_rej_real}, REAL+PARTIAL: {n_rej_true}, "
              f"FALSE: {n_rej_false}")
        if len(rejected_by_h114) > 0:
            print(f"    rejection precision (REAL): "
                  f"{n_rej_real/len(rejected_by_h114):.3f}")
            print(f"    rejection precision (REAL+PARTIAL): "
                  f"{n_rej_true/len(rejected_by_h114):.3f}")

    # Save outputs
    out1 = H1_DATA / "h115_per_edge.csv"
    with out1.open("w", newline="") as f:
        if per_edge_v1:
            w = csv.DictWriter(f, fieldnames=list(per_edge_v1[0].keys()))
            w.writeheader()
            w.writerows(per_edge_v1)
    print(f"\nWrote {out1} ({len(per_edge_v1)} rows)")

    out2 = H1_DATA / "h115_h20_kept_per_edge.csv"
    with out2.open("w", newline="") as f:
        if h20_per_edge:
            w = csv.DictWriter(f, fieldnames=list(h20_per_edge[0].keys()))
            w.writeheader()
            w.writerows(h20_per_edge)
    print(f"Wrote {out2} ({len(h20_per_edge)} rows)")

    # Save summary
    summary = {
        "h115_v1": {
            "h7v3plus3_added_edges": [list(e) for e in sorted(added_in_plus3)],
            "h7v3plus3_removed_edges": [list(e) for e in sorted(removed_in_plus3)],
            "n_fires": sum(1 for e in per_edge_v1
                           if e["h114_v1_fires_TD40_TJ250"]),
            "threshold_TD": H114_DIAGNOSTIC_TD,
            "threshold_TJ": H114_DIAGNOSTIC_TJ,
        },
        "h115_v2": {
            "n_h20_kept": len(h20_per_edge),
            "n_fires": fire_count,
            "n_qa": len(qa_subset),
            "n_qa_real": n_real if qa_subset else 0,
            "n_qa_real_or_partial": n_true if qa_subset else 0,
            "n_qa_false": n_false if qa_subset else 0,
            "n_kept_by_h114": len(kept_by_h114) if qa_subset else 0,
            "n_rej_by_h114": len(rejected_by_h114) if qa_subset else 0,
            "precision_kept_real":
                (n_kept_real / len(kept_by_h114)) if kept_by_h114 else 0,
            "precision_kept_real_or_partial":
                (n_kept_true / len(kept_by_h114)) if kept_by_h114 else 0,
            "precision_rej_real":
                (n_rej_real / len(rejected_by_h114)) if rejected_by_h114 else 0,
            "precision_rej_real_or_partial":
                (n_rej_true / len(rejected_by_h114)) if rejected_by_h114 else 0,
        },
    }
    out3 = H1_DATA / "h115_summary.json"
    with out3.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {out3}")


if __name__ == "__main__":
    main()
