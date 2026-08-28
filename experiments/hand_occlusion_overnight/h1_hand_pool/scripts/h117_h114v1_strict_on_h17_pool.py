#!/usr/bin/env python3
"""H117: H114 v1 strict (T_d=25, T_j=200) as a candidate flagger on the H17
strict V-shape pool (151 candidates).

HYPOTHESIS:
  H115 v3 found that the H114 v1 strict rule (T_d=25, T_j=200) catches
  2 FALSE + 1 UNCLEAR H20-KEPT candidates without dropping any REAL
  (P_kept_TRUE 0.450 -> 0.529, +7.9 points). H116 confirmed the rule
  has 0% false-positive rate on 9 known-or-newly-QA'd strict fires
  (5/5 newly-QA'd are cross-ball artifacts).

  H117 hypothesis: the H114 v1 strict rule should also be informative
  on the wider H17 V-shape pool (151 strict positives). H17 is the
  ORIGINAL geometric candidate set, less filtered than the H20-KEPT
  subset. If H114 v1 strict catches most of the FALSE in H17, it
  could be used as a pre-filter on future V-shape candidate mining.

METHOD (per master §15, thresholds declared before reading outcomes):
  - Apply H114 v1 strict (T_d=25, T_j=200) to all 151 H17 strict
    positives.
  - Compute precision/recall against the 16 H17 v1 visually-QA'd
    verdicts (5 REAL, 3 PARTIAL, 1 UNCLEAR, 7 FALSE).
  - Run a 6x6 threshold sweep (T_d x T_j) to characterize the
    precision-recall trade-off.
  - Check what fraction of strict fires are in h7v3plus3 (informative
    if 0 — confirms the rule never wrongly flags a real catch-throw).

INPUTS:
  - h17_strict_v_shape_positives.csv: 151 strict V-shape positives
  - tracklet_features.csv: per-tracklet end_dist, start_dist, end_xy,
    start_xy, end_side, start_side
  - h17_v1_qa_verdicts.csv: 16 visually-QA'd verdicts
    (recovered from the H17 v1 report table)

OUTPUTS:
  - data/h117_per_edge.csv: 151 edges with H114 v1 default + strict
    firing status, end_d, start_d, spatial_jump, vshape
  - data/h117_v1_strict_fires.csv: subset that fires H114 v1 strict
  - data/h117_v1_threshold_grid.csv: 6x6 = 36-cell sweep
  - data/h117_v1_summary.json: optimal operating point + per-bin
    counts
  - reports/h117_report.md: written report
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_REPORTS = H1_DIR / "reports"
H1_SCRIPTS = H1_DIR / "scripts"

# H117 declared thresholds (per master §15)
T_D_VALUES = [20, 25, 30, 40, 50, 80]
T_J_VALUES = [100, 150, 200, 250, 300, 400]
DEFAULT_T_D = 25
DEFAULT_T_J = 200

# H17 v1 visually-QA'd verdicts (recovered from h17_report.md, Table)
# Format: (stem, from_tid, to_tid) -> verdict
H17_QA_VERDICTS = {
    ("identical_balls_trick_000_018", 35, 40): "UNCLEAR",  # 1
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 15, 25): "REAL",  # 2
    ("identical_balls_trick_000_018", 6, 15): "REAL",  # 3
    ("identical_balls_trick_000_018", 4, 8): "FALSE",  # 4 (in-hand)
    ("identical_balls_trick_000_018", 35, 38): "FALSE",  # 5 (source high)
    ("identical_balls_trick_000_018", 56, 57): "REAL",  # 6
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11): "FALSE",  # 7 (apex high)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 20, 21): "REAL",  # 8
    ("identical_balls_trick_000_018", 54, 57): "REAL",  # 9
    ("identical_balls_trick_000_018", 66, 68): "FALSE",  # 10 (source held)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 23, 24): "PARTIAL",  # 11
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 1, 10): "FALSE",  # 12 (apex at shoulder)
    ("identical_balls_trick_000_018", 29, 33): "PARTIAL",  # 13
    ("identical_balls_trick_000_018", 13, 15): "PARTIAL",  # 14
    ("identical_balls_trick_000_018", 56, 58): "REAL",  # 15 (long 26-frame gap)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 24, 27): "FALSE",  # 16 (apex at torso)
}

H17_STRICT_PATH = H1_DATA / "h17_strict_v_shape_positives.csv"
TRACKLET_FEATURES_PATH = H1_DATA / "tracklet_features.csv"
H7V3PLUS3_PATHS = {
    "identical_balls_trick_000_018":
        H1_DATA / "h7v3plus3_admitted_edges_identical_balls_trick_000_018.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        H1_DATA / "h7v3plus3_admitted_edges_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv",
}
OUT_PER_EDGE = H1_DATA / "h117_per_edge.csv"
OUT_FIRES = H1_DATA / "h117_v1_strict_fires.csv"
OUT_GRID = H1_DATA / "h117_v1_threshold_grid.csv"
OUT_SUMMARY = H1_DATA / "h117_v1_summary.json"


def load_tracklet_features() -> dict:
    out = {}
    with TRACKLET_FEATURES_PATH.open() as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["tid"]))
            def _f(v):
                try:
                    return float(v) if v != "" else None
                except (ValueError, TypeError):
                    return None
            out[key] = {
                "end_dist": _f(r["end_dist"]),
                "start_dist": _f(r["start_dist"]),
                "last_x": _f(r["last_x"]),
                "last_y": _f(r["last_y"]),
                "first_x": _f(r["first_x"]),
                "first_y": _f(r["first_y"]),
                "end_side": r["end_side"] or None,
                "start_side": r["start_side"] or None,
            }
    return out


def load_h7v3plus3_edges() -> set:
    """Return set of (stem, src, tgt) tuples in h7v3plus3.

    Note: h7v3plus3 CSVs do not have a 'stem' column; the stem is
    encoded in the filename.
    """
    s = set()
    for stem, path in H7V3PLUS3_PATHS.items():
        if not path.exists():
            continue
        with path.open() as f:
            for r in csv.DictReader(f):
                try:
                    s.add((stem, int(r["from_tid"]), int(r["to_tid"])))
                except (KeyError, ValueError):
                    pass
    return s


def spatial_jump(src_last_xy, tgt_first_xy):
    if src_last_xy is None or tgt_first_xy is None:
        return None
    dx = tgt_first_xy[0] - src_last_xy[0]
    dy = tgt_first_xy[1] - src_last_xy[1]
    return math.sqrt(dx * dx + dy * dy)


def main():
    print("=" * 70)
    print("H117: H114 v1 strict on the H17 V-shape pool (151 strict positives)")
    print("=" * 70)
    print()

    tf = load_tracklet_features()
    h7v3plus3 = load_h7v3plus3_edges()
    print(f"Loaded {len(tf)} tracklet features, {len(h7v3plus3)} h7v3plus3 edges")

    # Load H17 strict V-shape positives
    rows = []
    with H17_STRICT_PATH.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    print(f"Loaded {len(rows)} H17 strict V-shape positives")
    print()

    # Per-edge features
    per_edge = []
    for r in rows:
        stem = r["stem"]
        src = int(r["from_tid"])
        tgt = int(r["to_tid"])
        src_f = tf.get((stem, src))
        tgt_f = tf.get((stem, tgt))
        end_d = src_f["end_dist"] if src_f else None
        start_d = tgt_f["start_dist"] if tgt_f else None
        sj = spatial_jump(
            (src_f["last_x"], src_f["last_y"]) if src_f else None,
            (tgt_f["first_x"], tgt_f["first_y"]) if tgt_f else None,
        )
        in_h7v3plus3 = (stem, src, tgt) in h7v3plus3
        qa = H17_QA_VERDICTS.get((stem, src, tgt), "")
        per_edge.append({
            "kind": r["kind"],
            "stem": stem,
            "src": src,
            "tgt": tgt,
            "vshape": r["vshape"],
            "gap": r["gap"],
            "min_hand_dist": r["min_hand_dist"],
            "ratio": r["ratio"],
            "in_h7v2": r["in_h7v2"],
            "end_d": "" if end_d is None else f"{end_d:.2f}",
            "start_d": "" if start_d is None else f"{start_d:.2f}",
            "spatial_jump": "" if sj is None else f"{sj:.2f}",
            "end_side": src_f["end_side"] if src_f else "",
            "start_side": tgt_f["start_side"] if tgt_f else "",
            "in_h7v3plus3": in_h7v3plus3,
            "qa_verdict": qa,
        })

    # Save per-edge
    with OUT_PER_EDGE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_edge[0].keys()))
        w.writeheader()
        w.writerows(per_edge)
    print(f"Wrote {OUT_PER_EDGE} ({len(per_edge)} rows)")

    # Identify strict fires
    strict_fires = [
        e for e in per_edge
        if e["end_d"] and e["start_d"] and e["spatial_jump"]
        and float(e["end_d"]) > DEFAULT_T_D
        and float(e["start_d"]) > DEFAULT_T_D
        and float(e["spatial_jump"]) > DEFAULT_T_J
    ]
    with OUT_FIRES.open("w", newline="") as f:
        if strict_fires:
            w = csv.DictWriter(f, fieldnames=list(strict_fires[0].keys()))
            w.writeheader()
            w.writerows(strict_fires)
    print(f"Wrote {OUT_FIRES} ({len(strict_fires)} strict fires at "
          f"T_d={DEFAULT_T_D}, T_j={DEFAULT_T_J})")
    print()

    # Per-bin counts.  Deduplicate by (stem, src, tgt) because some
    # H17 strict positives are duplicated across 'kind' categories
    # (e.g. 4->8 appears as both e6c_not_in_h7v2 and adj).
    seen_keys = set()
    unique_per_edge = []
    for e in per_edge:
        key = (e["stem"], e["src"], e["tgt"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_per_edge.append(e)

    n_total = len(per_edge)
    n_total_unique = len(unique_per_edge)
    n_fires_default = sum(
        1 for e in per_edge
        if e["end_d"] and e["start_d"] and e["spatial_jump"]
        and float(e["end_d"]) > DEFAULT_T_D
        and float(e["start_d"]) > DEFAULT_T_D
        and float(e["spatial_jump"]) > DEFAULT_T_J
    )
    n_fires_default_unique = sum(
        1 for e in unique_per_edge
        if e["end_d"] and e["start_d"] and e["spatial_jump"]
        and float(e["end_d"]) > DEFAULT_T_D
        and float(e["start_d"]) > DEFAULT_T_D
        and float(e["spatial_jump"]) > DEFAULT_T_J
    )
    n_fires_in_h7v3plus3 = sum(1 for e in strict_fires if e["in_h7v3plus3"])
    n_fires_qa = [e for e in strict_fires if e["qa_verdict"]]
    n_fires_real = sum(1 for e in strict_fires if e["qa_verdict"] == "REAL")
    n_fires_true = sum(1 for e in strict_fires if e["qa_verdict"] in ("REAL", "PARTIAL"))
    n_fires_false = sum(1 for e in strict_fires if e["qa_verdict"] == "FALSE")
    n_fires_unclear = sum(1 for e in strict_fires if e["qa_verdict"] == "UNCLEAR")

    print(f"STRICT FIRES (T_d={DEFAULT_T_D}, T_j={DEFAULT_T_J}):")
    print(f"  Total strict fires: {n_fires_default} of {n_total} raw rows "
          f"({n_fires_default/n_total:.1%})")
    print(f"  Unique strict fires: {n_fires_default_unique} of {n_total_unique} unique edges "
          f"({n_fires_default_unique/n_total_unique:.1%})")
    print(f"  In h7v3plus3: {n_fires_in_h7v3plus3} (0 means no false-positives in chain)")
    print(f"  Visually-QA'd (raw): {len(n_fires_qa)} of {len(H17_QA_VERDICTS)} unique QA verdicts")
    # Unique QA breakdown
    n_fires_qa_unique = set()
    n_fires_qa_unique_real = set()
    n_fires_qa_unique_true = set()
    n_fires_qa_unique_false = set()
    n_fires_qa_unique_unclear = set()
    for e in strict_fires:
        key = (e["stem"], e["src"], e["tgt"])
        if e["qa_verdict"]:
            n_fires_qa_unique.add(key)
            if e["qa_verdict"] == "REAL":
                n_fires_qa_unique_real.add(key)
            if e["qa_verdict"] in ("REAL", "PARTIAL"):
                n_fires_qa_unique_true.add(key)
            if e["qa_verdict"] == "FALSE":
                n_fires_qa_unique_false.add(key)
            if e["qa_verdict"] == "UNCLEAR":
                n_fires_qa_unique_unclear.add(key)
    print(f"  Visually-QA'd (unique): {len(n_fires_qa_unique)} of {len(H17_QA_VERDICTS)}")
    print(f"    REAL: {len(n_fires_qa_unique_real)}")
    print(f"    REAL+PARTIAL: {len(n_fires_qa_unique_true)}")
    print(f"    FALSE: {len(n_fires_qa_unique_false)}")
    print(f"    UNCLEAR: {len(n_fires_qa_unique_unclear)}")
    print()

    # H17 v1 QA tally
    qa_real = sum(1 for v in H17_QA_VERDICTS.values() if v == "REAL")
    qa_true = sum(1 for v in H17_QA_VERDICTS.values() if v in ("REAL", "PARTIAL"))
    qa_false = sum(1 for v in H17_QA_VERDICTS.values() if v == "FALSE")
    qa_unclear = sum(1 for v in H17_QA_VERDICTS.values() if v == "UNCLEAR")
    print(f"H17 v1 visually-QA'd subset (n={len(H17_QA_VERDICTS)} unique edges):")
    print(f"  REAL: {qa_real}, REAL+PARTIAL: {qa_true}, "
          f"FALSE: {qa_false}, UNCLEAR: {qa_unclear}")
    print()

    # Baseline H17 strict pool precision/recall on the 16 visually-QA'd edges
    # Dedupe: each unique (stem, src, tgt) in the pool has 1+ rows.
    n_qa_in_pool = sum(1 for e in unique_per_edge if e["qa_verdict"])
    qa_in_pool_real = sum(1 for e in unique_per_edge if e["qa_verdict"] == "REAL")
    qa_in_pool_true = sum(1 for e in unique_per_edge if e["qa_verdict"] in ("REAL", "PARTIAL"))
    qa_in_pool_false = sum(1 for e in unique_per_edge if e["qa_verdict"] == "FALSE")
    qa_in_pool_unclear = sum(1 for e in unique_per_edge if e["qa_verdict"] == "UNCLEAR")
    print(f"H17 v1 visually-QA'd unique edges in the H17 strict pool: "
          f"{n_qa_in_pool} of {len(H17_QA_VERDICTS)}")
    print(f"  REAL: {qa_in_pool_real}, REAL+PARTIAL: {qa_in_pool_true}, "
          f"FALSE: {qa_in_pool_false}, UNCLEAR: {qa_in_pool_unclear}")
    if n_qa_in_pool:
        print(f"  H17 strict pool precision (REAL+PARTIAL): "
              f"{qa_in_pool_true/n_qa_in_pool:.1%}")
    print()

    # 6x6 threshold sweep.  Use unique edges to avoid double-counting
    # duplicates that exist because H17 has multiple 'kind' categories
    # (v4d_rejected, e6c_not_in_h7v2, adj) per (stem, src, tgt).
    def fires(e, T_d, T_j):
        if not e["end_d"] or not e["start_d"] or not e["spatial_jump"]:
            return False
        return (float(e["end_d"]) > T_d
                and float(e["start_d"]) > T_d
                and float(e["spatial_jump"]) > T_j)

    grid = []
    for T_d in T_D_VALUES:
        for T_j in T_J_VALUES:
            kept = [e for e in unique_per_edge if not fires(e, T_d, T_j)]
            rejected = [e for e in unique_per_edge if fires(e, T_d, T_j)]
            n_kept = len(kept)
            n_rej = len(rejected)
            n_kept_qa = sum(1 for e in kept if e["qa_verdict"])
            n_kept_real = sum(1 for e in kept if e["qa_verdict"] == "REAL")
            n_kept_true = sum(1 for e in kept if e["qa_verdict"] in ("REAL", "PARTIAL"))
            n_kept_false = sum(1 for e in kept if e["qa_verdict"] == "FALSE")
            n_rej_real = sum(1 for e in rejected if e["qa_verdict"] == "REAL")
            n_rej_true = sum(1 for e in rejected if e["qa_verdict"] in ("REAL", "PARTIAL"))
            n_rej_false = sum(1 for e in rejected if e["qa_verdict"] == "FALSE")
            n_rej_in_h7v3plus3 = sum(1 for e in rejected if e["in_h7v3plus3"])
            grid.append({
                "T_d": T_d,
                "T_j": T_j,
                "n_kept": n_kept,
                "n_rejected": n_rej,
                "n_kept_qa": n_kept_qa,
                "n_kept_real": n_kept_real,
                "n_kept_true": n_kept_true,
                "n_kept_false": n_kept_false,
                "n_rej_real": n_rej_real,
                "n_rej_true": n_rej_true,
                "n_rej_false": n_rej_false,
                "n_rej_in_h7v3plus3": n_rej_in_h7v3plus3,
                "precision_kept_true": (n_kept_true / n_kept_qa) if n_kept_qa else 0,
                "precision_rej_real": n_rej_real / n_rej if n_rej else 0,
                "precision_rej_false": n_rej_false / n_rej if n_rej else 0,
                "recall_kept_real": n_kept_real / qa_in_pool_real if qa_in_pool_real else 0,
                "recall_kept_true": n_kept_true / qa_in_pool_true if qa_in_pool_true else 0,
            })

    # Save grid
    with OUT_GRID.open("w", newline="") as f:
        if grid:
            w = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
            w.writeheader()
            w.writerows(grid)
    print(f"Wrote {OUT_GRID} ({len(grid)} cells)")

    # Print grid: sort by precision_kept_true descending
    print()
    print("=" * 70)
    print("H117 threshold grid (sorted by P_kept_TRUE desc, then n_kept desc)")
    print("=" * 70)
    print(f"{'T_d':>5} {'T_j':>5} | {'n_kept':>7} {'n_rej':>5} | "
          f"{'P_kept_TRUE':>13} {'P_rej_REAL':>12} | "
          f"{'R_kept_REAL':>13} {'R_kept_TRUE':>13}")
    print("-" * 80)
    for g in sorted(grid, key=lambda x: (-x["precision_kept_true"], -x["n_kept"])):
        print(f"{g['T_d']:>5} {g['T_j']:>5} | {g['n_kept']:>7} {g['n_rejected']:>5} | "
              f"{g['precision_kept_true']:>13.3f} {g['precision_rej_real']:>12.3f} | "
              f"{g['recall_kept_real']:>13.3f} {g['recall_kept_true']:>13.3f}")

    # Find the best operating point
    # Criterion: max precision_kept_TRUE (REAL+PARTIAL) subject to
    # no REAL caught by the filter (P_rej_REAL = 0)
    safe = [g for g in grid if g["n_rejected"] >= 1 and g["precision_rej_real"] == 0]
    if safe:
        best_safe = max(safe, key=lambda x: (x["precision_kept_true"], x["n_kept"]))
    else:
        best_safe = None

    # Strict operating point (T_d=25, T_j=200)
    strict_cell = next((g for g in grid if g["T_d"] == DEFAULT_T_D and g["T_j"] == DEFAULT_T_J), None)

    print()
    print("=" * 70)
    print("OPTIMAL OPERATING POINTS")
    print("=" * 70)
    if best_safe:
        print(f"Best (catches >=1 FALSE, drops no REAL, max P_kept_TRUE): "
              f"T_d={best_safe['T_d']}, T_j={best_safe['T_j']}")
        print(f"  n_kept={best_safe['n_kept']}, n_rej={best_safe['n_rejected']}, "
              f"P_kept_TRUE={best_safe['precision_kept_true']:.3f}, "
              f"R_kept_TRUE={best_safe['recall_kept_true']:.3f}")
    else:
        print("No threshold catches >=1 FALSE without dropping >=1 REAL.")
    if strict_cell:
        print(f"H117 default (T_d=25, T_j=200): n_kept={strict_cell['n_kept']}, "
              f"n_rej={strict_cell['n_rejected']}, "
              f"P_kept_TRUE={strict_cell['precision_kept_true']:.3f}, "
              f"R_kept_TRUE={strict_cell['recall_kept_true']:.3f}")

    # Build summary JSON
    summary = {
        "h117_date": "2026-08-29",
        "h114_v1_strict_rule": {
            "T_d": DEFAULT_T_D,
            "T_j": DEFAULT_T_J,
            "fires_if": "end_d > 25 AND start_d > 25 AND spatial_jump > 200",
        },
        "pool": "h17_strict_v_shape_positives",
        "n_pool": n_total,
        "n_strict_fires": n_fires_default,
        "n_strict_fires_in_h7v3plus3": n_fires_in_h7v3plus3,
        "n_strict_fires_qa": len(n_fires_qa),
        "n_strict_fires_real": n_fires_real,
        "n_strict_fires_true": n_fires_true,
        "n_strict_fires_false": n_fires_false,
        "n_strict_fires_unclear": n_fires_unclear,
        "h17_v1_qa_subset": {
            "n_qa": len(H17_QA_VERDICTS),
            "n_real": qa_real,
            "n_true": qa_true,
            "n_false": qa_false,
            "n_unclear": qa_unclear,
        },
        "h17_strict_pool_qa_breakdown": {
            "n_qa_in_pool": n_qa_in_pool,
            "n_real": qa_in_pool_real,
            "n_true": qa_in_pool_true,
            "n_false": qa_in_pool_false,
            "n_unclear": qa_in_pool_unclear,
            "baseline_precision_true": (qa_in_pool_true / n_qa_in_pool) if n_qa_in_pool else 0,
        },
        "best_safe_operating_point": best_safe,
        "strict_default_cell": strict_cell,
        "thresholds_swept": {
            "T_d": T_D_VALUES,
            "T_j": T_J_VALUES,
        },
    }
    with OUT_SUMMARY.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
