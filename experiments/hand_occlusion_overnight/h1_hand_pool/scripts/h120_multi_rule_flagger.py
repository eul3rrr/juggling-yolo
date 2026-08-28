#!/usr/bin/env python3
"""H120: Multi-rule strict flagger (H114 v1 + cross-hand + single-end-far).

HYPOTHESIS (v1 — NEGATIVE, see H120 v2 below):
  H119 found that the 10 visually-QA'd un-QA'd H17 full pool strict
  fires cluster into 3 distinct geometric failure modes:
    - cross-hand handoff (5/10): src near hand A, tgt near hand B
    - single-end-far (4/10): one endpoint at hand, other far
    - both-end-far (1/10): both endpoints far from any hand

  H114 v1 strict (T_d=25, T_j=200) catches all 10 because BOTH
  endpoints must be > 25 px (cross-hand) and the jump must be > 200.

H120 v1 IMPLEMENTATION (Rule A + B + C):
  Rule A (H114 v1 strict baseline):
    end_d > T_D_A AND start_d > T_D_A AND spatial_jump > T_J_A
    Defaults: T_D_A=25, T_J_A=200

  Rule B (cross-hand handoff):
    end_side != start_side AND min(end_d, start_d) > T_D_B AND sj > T_J_B
    Defaults: T_D_B=30, T_J_B=100

  Rule C (single-end-far):
    (end_d > T_D_C AND start_d < T_D_C) OR
    (start_d > T_D_C AND end_d < T_D_C)
    AND spatial_jump > T_J_C
    Defaults: T_D_C=50, T_J_C=80

H120 v1 NEGATIVE FINDING:
  Rule C fires on 9/59 chain-accepted edges (15.3% FP rate). The
  geometry "ball in hand → ball at apex → back in hand" naturally
  has one endpoint near a hand and one far, so Rule C fires on
  the very pattern it's trying to identify (HAND_TRANSITION with
  one end far).

H120 v2 IMPLEMENTATION (Rule A + B only):
  Drop Rule C entirely. Use only Rules A and B.
  The hypothesis: B adds new catches (cross-hand handoffs with
  smaller spatial_jump) without false positives because cross-hand
  handoffs are reliably wrong (a ball cannot teleport from one
  hand to the other without going through the air).

METHOD (v2):
  1. Apply Rules A+B to H17 full pool (177 unique edges, from
     h118_per_edge.csv) and H20-KEPT (115 edges).
  2. Compare against H114 v1 strict fires: how many NEW fires does
     Rule B add? Are any of those REAL (per H17 v1 visual QA)?
  3. Run 5x5 = 25-cell threshold sweep (T_D_B x T_J_B) and
     characterize the operating point stability.
  4. Check that no chain-accepted edge fires Rule B (FP on chain).

INPUTS:
  - h118_per_edge.csv: 177 H17 full edges with H114 v1 outputs + qa
  - h115_h20_kept_per_edge.csv: 115 H20-KEPT edges with H114 v1 outputs
  - h7v3plus3_admitted_edges_*.csv: per-stem admitted edges
  - tracklet_features.csv: per-tracklet end_dist, start_dist, end_xy, start_xy

OUTPUTS:
  - data/h120_v1_per_edge.csv: 177 H17 full edges with v1 multi-rule outputs
  - data/h120_v1_per_edge_h20.csv: 115 H20-KEPT edges with v1 multi-rule outputs
  - data/h120_v1_strict_fires.csv: H17 full fires (v1)
  - data/h120_v1_strict_fires_h20.csv: H20-KEPT fires (v1)
  - data/h120_v1_threshold_grid.csv: 5x5x4x4 = 400-cell v1 sweep
  - data/h120_v1_chain_fp_check.csv: chain-accepted edges firing v1 rules
  - data/h120_v2_per_edge.csv: 177 H17 full edges with v2 (A+B only) outputs
  - data/h120_v2_per_edge_h20.csv: 115 H20-KEPT edges with v2 outputs
  - data/h120_v2_strict_fires.csv: H17 full fires (v2)
  - data/h120_v2_strict_fires_h20.csv: H20-KEPT fires (v2)
  - data/h120_v2_threshold_grid.csv: 5x5 = 25-cell v2 sweep
  - data/h120_v2_chain_fp_check.csv: chain-accepted edges firing v2 rules
  - data/h120_summary.json: optimal operating point + per-rule counts
  - contact_sheets_h120/*.png: contact sheets for any new catches
  - reports/h120_report.md: written report
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_REPORTS = H1_DIR / "reports"
H1_SCRIPTS = H1_DIR / "scripts"
H1_CS = H1_DIR / "contact_sheets_h120"
H1_CS.mkdir(parents=True, exist_ok=True)

# H120 declared thresholds (per master §15)
DEFAULT_T_D_A = 25
DEFAULT_T_J_A = 200
DEFAULT_T_D_B = 30
DEFAULT_T_J_B = 100
DEFAULT_T_D_C = 50
DEFAULT_T_J_C = 80

# Threshold sweep ranges
T_D_B_VALUES = [20, 25, 30, 40, 50]
T_J_B_VALUES = [60, 80, 100, 150, 200]
T_D_C_VALUES = [40, 50, 60, 80]
T_J_C_VALUES = [60, 80, 100, 150]


def load_tracklet_features():
    """Load tracklet features with positions for chain FP check."""
    tf = {}
    with (H1_DATA / "tracklet_features.csv").open() as f:
        for row in csv.DictReader(f):
            key = (row["stem"], int(row["tid"]))
            tf[key] = {
                "end_dist": float(row["end_dist"]) if row["end_dist"] else None,
                "start_dist": float(row["start_dist"]) if row["start_dist"] else None,
                "end_side": row["end_side"] or None,
                "start_side": row["start_side"] or None,
                "last_x": float(row["last_x"]),
                "last_y": float(row["last_y"]),
                "first_x": float(row["first_x"]),
                "first_y": float(row["first_y"]),
            }
    return tf


def load_chain_edges():
    """Load h7v3plus3 admitted edges (per stem)."""
    edges = []
    for csv_path in H1_DATA.glob("h7v3plus3_admitted_edges_*.csv"):
        # stem is encoded in the filename: h7v3plus3_admitted_edges_<stem>.csv
        stem = csv_path.stem.replace("h7v3plus3_admitted_edges_", "")
        with csv_path.open() as f:
            for row in csv.DictReader(f):
                edges.append({
                    "stem": stem,
                    "src": int(row["from_tid"]),
                    "tgt": int(row["to_tid"]),
                    "edge_type": row["edge_type"],
                })
    return edges


def load_h17_full():
    """Load H17 full V-shape positives (240 rows in h17_v_shape_positives.csv,
    enriched with H114 v1 outputs in h118_per_edge.csv)."""
    edges = []
    with (H1_DATA / "h118_per_edge.csv").open() as f:
        for row in csv.DictReader(f):
            edges.append({
                "kind": row["kind"],
                "stem": row["stem"],
                "src": int(row["src"]),
                "tgt": int(row["tgt"]),
                "gap": int(row["gap"]),
                "min_hand_dist": float(row["min_hand_dist"]),
                "ratio": float(row["ratio"]),
                "vshape": row["vshape"],
                "end_d": float(row["end_d"]) if row["end_d"] else None,
                "start_d": float(row["start_d"]) if row["start_d"] else None,
                "spatial_jump": float(row["spatial_jump"]) if row["spatial_jump"] else None,
                "end_side": row["end_side"],
                "start_side": row["start_side"],
                "in_h7v3plus3": row["in_h7v3plus3"] == "True",
                "qa_verdict": row.get("qa_verdict", "") or "",
                "h114_v1_default_fires": row.get("h114_v1_default_fires", "False") == "True",
                "h114_v1_strict_fires": row.get("h114_v1_strict_fires", "False") == "True",
            })
    return edges


def load_h20_kept():
    """Load H20-KEPT candidates (115 rows from h115_h20_kept_per_edge.csv)."""
    edges = []
    with (H1_DATA / "h115_h20_kept_per_edge.csv").open() as f:
        for row in csv.DictReader(f):
            edges.append({
                "kind": "h20_kept",
                "stem": row["stem"],
                "src": int(row["src"]),
                "tgt": int(row["tgt"]),
                "vshape": row["vshape"],
                "in_hand_px": float(row["in_hand_px"]) if row["in_hand_px"] else None,
                "min_hand_dist": float(row["min_hand_dist"]),
                "gap_dist": float(row["gap_dist"]) if row["gap_dist"] else None,
                "gap_vel": float(row["gap_vel"]) if row["gap_vel"] else None,
                "apex_src_dist": float(row["apex_src_dist"]) if row["apex_src_dist"] else None,
                "h20_keep": row["h20_keep"] == "True",
                "end_d": float(row["end_d"]) if row["end_d"] else None,
                "start_d": float(row["start_d"]) if row["start_d"] else None,
                "end_side": row["end_side"],
                "start_side": row["start_side"],
                "spatial_jump": float(row["spatial_jump"]) if row["spatial_jump"] else None,
                "h114_v1_default_fires": row.get("h114_v1_fires_TD40_TJ250", "False") == "True",
                "visual_qa_verdict": row.get("visual_qa_verdict", "") or "",
                "in_h7v3plus3": row["in_h7v3plus3"] == "True",
            })
    return edges


def apply_rule_a(end_d, start_d, sj, t_d=DEFAULT_T_D_A, t_j=DEFAULT_T_J_A):
    if end_d is None or start_d is None or sj is None:
        return False
    return end_d > t_d and start_d > t_d and sj > t_j


def apply_rule_b(end_d, start_d, sj, end_side, start_side, t_d=DEFAULT_T_D_B, t_j=DEFAULT_T_J_B):
    """Cross-hand handoff."""
    if end_d is None or start_d is None or sj is None:
        return False
    if not end_side or not start_side:
        return False
    if end_side == start_side:
        return False
    if min(end_d, start_d) <= t_d:
        return False
    if sj <= t_j:
        return False
    return True


def apply_rule_c(end_d, start_d, sj, t_d=DEFAULT_T_D_C, t_j=DEFAULT_T_J_C):
    """Single-end-far."""
    if end_d is None or start_d is None or sj is None:
        return False
    one_far = (end_d > t_d and start_d < t_d) or (start_d > t_d and end_d < t_d)
    if not one_far:
        return False
    if sj <= t_j:
        return False
    return True


def apply_multi_rule(end_d, start_d, sj, end_side, start_side,
                     t_d_a=DEFAULT_T_D_A, t_j_a=DEFAULT_T_J_A,
                     t_d_b=DEFAULT_T_D_B, t_j_b=DEFAULT_T_J_B,
                     t_d_c=DEFAULT_T_D_C, t_j_c=DEFAULT_T_J_C):
    a = apply_rule_a(end_d, start_d, sj, t_d_a, t_j_a)
    b = apply_rule_b(end_d, start_d, sj, end_side, start_side, t_d_b, t_j_b)
    c = apply_rule_c(end_d, start_d, sj, t_d_c, t_j_c)
    return a, b, c, (a or b or c)


def main():
    print("=" * 70)
    print("H120: Multi-rule strict flagger v1 (A+B+C) and v2 (A+B only)")
    print("=" * 70)
    print()
    print(f"Default thresholds:")
    print(f"  Rule A (H114 v1 strict): T_D={DEFAULT_T_D_A}, T_J={DEFAULT_T_J_A}")
    print(f"  Rule B (cross-hand):     T_D={DEFAULT_T_D_B}, T_J={DEFAULT_T_J_B}")
    print(f"  Rule C (single-end-far): T_D={DEFAULT_T_D_C}, T_J={DEFAULT_T_J_C}")
    print()

    tf = load_tracklet_features()
    chain_edges = load_chain_edges()
    h17_edges = load_h17_full()
    h20_edges = load_h20_kept()

    # === H120 v1: Rule A + B + C (3-rule OR) ===
    print("=" * 70)
    print("H120 v1: Rule A OR Rule B OR Rule C")
    print("=" * 70)

    h17_v1_results = process_pool(h17_edges, "h17", version="v1")
    h20_v1_results = process_pool(h20_edges, "h20", version="v1")
    h17_v1_grid, h17_v1_safe = sweep_v1(h17_v1_results)
    print_v1_summary("h17", h17_v1_results, h17_v1_grid, h17_v1_safe)
    print_v1_summary("h20", h20_v1_results, [], [])

    # Chain FP check for v1
    chain_v1_fps = []
    for ce in chain_edges:
        src_tf = tf.get((ce["stem"], ce["src"]), {})
        tgt_tf = tf.get((ce["stem"], ce["tgt"]), {})
        e = src_tf.get("end_dist")
        s = tgt_tf.get("start_dist")
        if e is None or s is None:
            continue
        sj = math.hypot(src_tf["last_x"] - tgt_tf["first_x"],
                        src_tf["last_y"] - tgt_tf["first_y"])
        a, b, c, fires = apply_multi_rule(
            e, s, sj, src_tf.get("end_side"), tgt_tf.get("start_side"))
        if fires:
            chain_v1_fps.append({**ce, "end_d": e, "start_d": s, "spatial_jump": sj,
                                 "rule_a": a, "rule_b": b, "rule_c": c,
                                 "fires_any": fires})
    print(f"  Chain FP check: {len(chain_v1_fps)}/{len(chain_edges)} chain edges fire v1")
    for fp in chain_v1_fps:
        tag = ('A' if fp['rule_a'] else '') + ('B' if fp['rule_b'] else '') + ('C' if fp['rule_c'] else '')
        print(f"    {fp['stem']} {fp['src']}->{fp['tgt']} ({fp['edge_type'][:25]}, {tag}): "
              f"end_d={fp['end_d']:.0f} start_d={fp['start_d']:.0f} sj={fp['spatial_jump']:.0f}")
    print()

    # === H120 v2: Rule A + B only (drop Rule C) ===
    print("=" * 70)
    print("H120 v2: Rule A OR Rule B (drop Rule C)")
    print("=" * 70)

    h17_v2_results = process_pool(h17_edges, "h17", version="v2")
    h20_v2_results = process_pool(h20_edges, "h20", version="v2")
    h17_v2_grid, h17_v2_safe = sweep_v2(h17_v2_results)
    print_v2_summary("h17", h17_v2_results, h17_v2_grid, h17_v2_safe)
    print_v2_summary("h20", h20_v2_results, [], [])

    # Chain FP check for v2
    chain_v2_fps = []
    for ce in chain_edges:
        src_tf = tf.get((ce["stem"], ce["src"]), {})
        tgt_tf = tf.get((ce["stem"], ce["tgt"]), {})
        e = src_tf.get("end_dist")
        s = tgt_tf.get("start_dist")
        if e is None or s is None:
            continue
        sj = math.hypot(src_tf["last_x"] - tgt_tf["first_x"],
                        src_tf["last_y"] - tgt_tf["first_y"])
        a, b, fires = apply_rule_ab(e, s, sj, src_tf.get("end_side"), tgt_tf.get("start_side"))
        if fires:
            chain_v2_fps.append({**ce, "end_d": e, "start_d": s, "spatial_jump": sj,
                                 "rule_a": a, "rule_b": b, "fires_any": fires})
    print(f"  Chain FP check: {len(chain_v2_fps)}/{len(chain_edges)} chain edges fire v2")
    for fp in chain_v2_fps:
        tag = ('A' if fp['rule_a'] else '') + ('B' if fp['rule_b'] else '')
        print(f"    {fp['stem']} {fp['src']}->{fp['tgt']} ({fp['edge_type'][:25]}, {tag}): "
              f"end_d={fp['end_d']:.0f} start_d={fp['start_d']:.0f} sj={fp['spatial_jump']:.0f}")
    print()

    # === Save outputs ===
    save_v1_outputs(h17_v1_results, h20_v1_results, h17_v1_grid, chain_v1_fps)
    save_v2_outputs(h17_v2_results, h20_v2_results, h17_v2_grid, chain_v2_fps)

    # === Summary JSON ===
    summary = build_summary(h17_v1_results, h20_v1_results, h17_v2_results, h20_v2_results,
                            h17_v1_grid, h17_v1_safe, h17_v2_grid, h17_v2_safe,
                            chain_v1_fps, chain_v2_fps, chain_edges)
    with (H1_DATA / "h120_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("  h120_summary.json: written")
    print()

    print_final_summary(summary)


def apply_rule_ab(end_d, start_d, sj, end_side, start_side,
                  t_d_a=DEFAULT_T_D_A, t_j_a=DEFAULT_T_J_A,
                  t_d_b=DEFAULT_T_D_B, t_j_b=DEFAULT_T_J_B):
    """Rule A or Rule B (v2)."""
    a = apply_rule_a(end_d, start_d, sj, t_d_a, t_j_a)
    b = apply_rule_b(end_d, start_d, sj, end_side, start_side, t_d_b, t_j_b)
    return a, b, (a or b)


def process_pool(edges, name, version="v1"):
    """Process a pool of edges with v1 (A+B+C) or v2 (A+B) rules."""
    results = []
    for e in edges:
        if version == "v1":
            a, b, c, fires = apply_multi_rule(
                e.get("end_d"), e.get("start_d"), e.get("spatial_jump"),
                e.get("end_side"), e.get("start_side"))
            e_out = {**e, "rule_a": a, "rule_b": b, "rule_c": c, "fires_any": fires}
        else:  # v2
            a, b, fires = apply_rule_ab(
                e.get("end_d"), e.get("start_d"), e.get("spatial_jump"),
                e.get("end_side"), e.get("start_side"))
            e_out = {**e, "rule_a": a, "rule_b": b, "rule_c": False, "fires_any": fires}
        results.append(e_out)
    return results


def sweep_v1(results):
    """5x5x4x4 = 400-cell v1 threshold sweep on H17 results."""
    grid = []
    for t_db in T_D_B_VALUES:
        for t_jb in T_J_B_VALUES:
            for t_dc in T_D_C_VALUES:
                for t_jc in T_J_C_VALUES:
                    n_fires = 0
                    n_fires_in_h7v3 = 0
                    n_real_qa = 0
                    n_real_partial_qa = 0
                    n_false_qa = 0
                    n_qa_in_fires = 0
                    for r in results:
                        a, b, c, fires = apply_multi_rule(
                            r.get("end_d"), r.get("start_d"), r.get("spatial_jump"),
                            r.get("end_side"), r.get("start_side"),
                            DEFAULT_T_D_A, DEFAULT_T_J_A,
                            t_db, t_jb, t_dc, t_jc)
                        if fires:
                            n_fires += 1
                            if r.get("in_h7v3plus3"):
                                n_fires_in_h7v3 += 1
                            qa = r.get("qa_verdict", "")
                            if qa:
                                n_qa_in_fires += 1
                                if qa == "REAL":
                                    n_real_qa += 1
                                    n_real_partial_qa += 1
                                elif qa == "PARTIAL":
                                    n_real_partial_qa += 1
                                elif qa == "FALSE":
                                    n_false_qa += 1
                    grid.append({
                        "T_D_B": t_db, "T_J_B": t_jb, "T_D_C": t_dc, "T_J_C": t_jc,
                        "n_fires": n_fires, "n_fires_in_h7v3": n_fires_in_h7v3,
                        "n_qa_in_fires": n_qa_in_fires, "n_real_qa": n_real_qa,
                        "n_real_partial_qa": n_real_partial_qa, "n_false_qa": n_false_qa,
                    })
    safe_cells = [g for g in grid if g["n_real_qa"] == 0 and g["n_qa_in_fires"] > 0]
    return grid, safe_cells


def sweep_v2(results):
    """5x5 = 25-cell v2 threshold sweep (T_D_B x T_J_B)."""
    grid = []
    for t_db in T_D_B_VALUES:
        for t_jb in T_J_B_VALUES:
            n_fires = 0
            n_fires_in_h7v3 = 0
            n_real_qa = 0
            n_real_partial_qa = 0
            n_false_qa = 0
            n_qa_in_fires = 0
            for r in results:
                a, b, fires = apply_rule_ab(
                    r.get("end_d"), r.get("start_d"), r.get("spatial_jump"),
                    r.get("end_side"), r.get("start_side"),
                    DEFAULT_T_D_A, DEFAULT_T_J_A,
                    t_db, t_jb)
                if fires:
                    n_fires += 1
                    if r.get("in_h7v3plus3"):
                        n_fires_in_h7v3 += 1
                    qa = r.get("qa_verdict", "")
                    if qa:
                        n_qa_in_fires += 1
                        if qa == "REAL":
                            n_real_qa += 1
                            n_real_partial_qa += 1
                        elif qa == "PARTIAL":
                            n_real_partial_qa += 1
                        elif qa == "FALSE":
                            n_false_qa += 1
            grid.append({
                "T_D_B": t_db, "T_J_B": t_jb,
                "n_fires": n_fires, "n_fires_in_h7v3": n_fires_in_h7v3,
                "n_qa_in_fires": n_qa_in_fires, "n_real_qa": n_real_qa,
                "n_real_partial_qa": n_real_partial_qa, "n_false_qa": n_false_qa,
            })
    safe_cells = [g for g in grid if g["n_real_qa"] == 0 and g["n_qa_in_fires"] > 0]
    return grid, safe_cells


def print_v1_summary(name, results, grid, safe_cells):
    n_total = len(results)
    n_fires = sum(1 for r in results if r.get("fires_any"))
    h114_key = "h114_v1_strict_fires" if name == "h17" else "h114_v1_default_fires"
    n_h114_strict = sum(1 for r in results if r.get(h114_key))
    n_new = sum(1 for r in results if r.get("fires_any") and not r.get(h114_key))
    n_in_chain = sum(1 for r in results if r.get("fires_any") and r.get("in_h7v3plus3"))
    print(f"  {name}: n={n_total}, H114 strict fires={n_h114_strict}, v1 fires={n_fires}, "
          f"new={n_new}, in h7v3plus3={n_in_chain}")
    if grid:
        print(f"  {name} threshold sweep: {len(safe_cells)}/{len(grid)} cells safe (0 REAL)")
    # Per-rule combination
    from collections import Counter
    per_rule = Counter()
    for r in results:
        if r.get("fires_any"):
            per_rule[(r.get("rule_a"), r.get("rule_b"), r.get("rule_c"))] += 1
    for combo, n in sorted(per_rule.items(), key=lambda x: -x[1]):
        rule_names = []
        if combo[0]: rule_names.append("A")
        if combo[1]: rule_names.append("B")
        if combo[2]: rule_names.append("C")
        print(f"    {''.join(rule_names) or 'NONE'}: {n}")


def print_v2_summary(name, results, grid, safe_cells):
    n_total = len(results)
    n_fires = sum(1 for r in results if r.get("fires_any"))
    h114_key = "h114_v1_strict_fires" if name == "h17" else "h114_v1_default_fires"
    n_h114_strict = sum(1 for r in results if r.get(h114_key))
    n_new = sum(1 for r in results if r.get("fires_any") and not r.get(h114_key))
    n_in_chain = sum(1 for r in results if r.get("fires_any") and r.get("in_h7v3plus3"))
    print(f"  {name}: n={n_total}, H114 strict fires={n_h114_strict}, v2 fires={n_fires}, "
          f"new={n_new}, in h7v3plus3={n_in_chain}")
    if grid:
        print(f"  {name} threshold sweep: {len(safe_cells)}/{len(grid)} cells safe (0 REAL)")
        if safe_cells:
            best = max(safe_cells, key=lambda g: g["n_fires"])
            print(f"    Best safe cell: T_D_B={best['T_D_B']}, T_J_B={best['T_J_B']}, "
                  f"{best['n_fires']} fires, {best['n_qa_in_fires']} QA'd, {best['n_real_qa']} REAL, {best['n_false_qa']} FALSE")
    # Per-rule combination
    from collections import Counter
    per_rule = Counter()
    for r in results:
        if r.get("fires_any"):
            per_rule[(r.get("rule_a"), r.get("rule_b"))] += 1
    for combo, n in sorted(per_rule.items(), key=lambda x: -x[1]):
        rule_names = []
        if combo[0]: rule_names.append("A")
        if combo[1]: rule_names.append("B")
        print(f"    {''.join(rule_names) or 'NONE'}: {n}")


def save_v1_outputs(h17_results, h20_results, grid, chain_fps):
    """Save v1 outputs."""
    with (H1_DATA / "h120_v1_per_edge.csv").open("w", newline="") as f:
        if h17_results:
            w = csv.DictWriter(f, fieldnames=list(h17_results[0].keys()))
            w.writeheader()
            for r in h17_results:
                w.writerow(r)
    print(f"  h120_v1_per_edge.csv: {len(h17_results)} rows")
    h17_fires = [r for r in h17_results if r.get("fires_any")]
    with (H1_DATA / "h120_v1_strict_fires.csv").open("w", newline="") as f:
        if h17_fires:
            w = csv.DictWriter(f, fieldnames=list(h17_fires[0].keys()))
            w.writeheader()
            for r in h17_fires:
                w.writerow(r)
    print(f"  h120_v1_strict_fires.csv: {len(h17_fires)} rows")
    with (H1_DATA / "h120_v1_per_edge_h20.csv").open("w", newline="") as f:
        if h20_results:
            w = csv.DictWriter(f, fieldnames=list(h20_results[0].keys()))
            w.writeheader()
            for r in h20_results:
                w.writerow(r)
    print(f"  h120_v1_per_edge_h20.csv: {len(h20_results)} rows")
    h20_fires = [r for r in h20_results if r.get("fires_any")]
    with (H1_DATA / "h120_v1_strict_fires_h20.csv").open("w", newline="") as f:
        if h20_fires:
            w = csv.DictWriter(f, fieldnames=list(h20_fires[0].keys()))
            w.writeheader()
            for r in h20_fires:
                w.writerow(r)
    print(f"  h120_v1_strict_fires_h20.csv: {len(h20_fires)} rows")
    with (H1_DATA / "h120_v1_threshold_grid.csv").open("w", newline="") as f:
        if grid:
            w = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
            w.writeheader()
            for g in grid:
                w.writerow(g)
    print(f"  h120_v1_threshold_grid.csv: {len(grid)} cells")
    with (H1_DATA / "h120_v1_chain_fp_check.csv").open("w", newline="") as f:
        if chain_fps:
            w = csv.DictWriter(f, fieldnames=list(chain_fps[0].keys()))
            w.writeheader()
            for r in chain_fps:
                w.writerow(r)
        else:
            f.write("stem,src,tgt\n")
    print(f"  h120_v1_chain_fp_check.csv: {len(chain_fps)} chain FPs")


def save_v2_outputs(h17_results, h20_results, grid, chain_fps):
    """Save v2 outputs."""
    with (H1_DATA / "h120_v2_per_edge.csv").open("w", newline="") as f:
        if h17_results:
            w = csv.DictWriter(f, fieldnames=list(h17_results[0].keys()))
            w.writeheader()
            for r in h17_results:
                w.writerow(r)
    print(f"  h120_v2_per_edge.csv: {len(h17_results)} rows")
    h17_fires = [r for r in h17_results if r.get("fires_any")]
    with (H1_DATA / "h120_v2_strict_fires.csv").open("w", newline="") as f:
        if h17_fires:
            w = csv.DictWriter(f, fieldnames=list(h17_fires[0].keys()))
            w.writeheader()
            for r in h17_fires:
                w.writerow(r)
    print(f"  h120_v2_strict_fires.csv: {len(h17_fires)} rows")
    with (H1_DATA / "h120_v2_per_edge_h20.csv").open("w", newline="") as f:
        if h20_results:
            w = csv.DictWriter(f, fieldnames=list(h20_results[0].keys()))
            w.writeheader()
            for r in h20_results:
                w.writerow(r)
    print(f"  h120_v2_per_edge_h20.csv: {len(h20_results)} rows")
    h20_fires = [r for r in h20_results if r.get("fires_any")]
    with (H1_DATA / "h120_v2_strict_fires_h20.csv").open("w", newline="") as f:
        if h20_fires:
            w = csv.DictWriter(f, fieldnames=list(h20_fires[0].keys()))
            w.writeheader()
            for r in h20_fires:
                w.writerow(r)
    print(f"  h120_v2_strict_fires_h20.csv: {len(h20_fires)} rows")
    with (H1_DATA / "h120_v2_threshold_grid.csv").open("w", newline="") as f:
        if grid:
            w = csv.DictWriter(f, fieldnames=list(grid[0].keys()))
            w.writeheader()
            for g in grid:
                w.writerow(g)
    print(f"  h120_v2_threshold_grid.csv: {len(grid)} cells")
    with (H1_DATA / "h120_v2_chain_fp_check.csv").open("w", newline="") as f:
        if chain_fps:
            w = csv.DictWriter(f, fieldnames=list(chain_fps[0].keys()))
            w.writeheader()
            for r in chain_fps:
                w.writerow(r)
        else:
            f.write("stem,src,tgt\n")
    print(f"  h120_v2_chain_fp_check.csv: {len(chain_fps)} chain FPs")


def build_summary(h17_v1, h20_v1, h17_v2, h20_v2,
                  h17_v1_grid, h17_v1_safe, h17_v2_grid, h17_v2_safe,
                  chain_v1_fps, chain_v2_fps, chain_edges):
    """Build summary dict."""
    return {
        "v1_rule_abc": {
            "h17_full": {
                "n_unique_edges": len(h17_v1),
                "n_h114_v1_strict_fires": sum(1 for r in h17_v1 if r.get("h114_v1_strict_fires")),
                "n_v1_fires": sum(1 for r in h17_v1 if r.get("fires_any")),
                "n_v1_new": sum(1 for r in h17_v1 if r.get("fires_any") and not r.get("h114_v1_strict_fires")),
                "n_in_h7v3plus3": sum(1 for r in h17_v1 if r.get("fires_any") and r.get("in_h7v3plus3")),
            },
            "h20_kept": {
                "n_edges": len(h20_v1),
                "n_h114_v1_default_fires": sum(1 for r in h20_v1 if r.get("h114_v1_default_fires")),
                "n_v1_fires": sum(1 for r in h20_v1 if r.get("fires_any")),
                "n_v1_new": sum(1 for r in h20_v1 if r.get("fires_any") and not r.get("h114_v1_default_fires")),
            },
            "chain_fp_count": len(chain_v1_fps),
            "chain_total": len(chain_edges),
            "threshold_sweep": {
                "n_cells": len(h17_v1_grid),
                "n_safe_cells_0_real": len(h17_v1_safe),
            },
        },
        "v2_rule_ab": {
            "h17_full": {
                "n_unique_edges": len(h17_v2),
                "n_h114_v1_strict_fires": sum(1 for r in h17_v2 if r.get("h114_v1_strict_fires")),
                "n_v2_fires": sum(1 for r in h17_v2 if r.get("fires_any")),
                "n_v2_new": sum(1 for r in h17_v2 if r.get("fires_any") and not r.get("h114_v1_strict_fires")),
                "n_in_h7v3plus3": sum(1 for r in h17_v2 if r.get("fires_any") and r.get("in_h7v3plus3")),
            },
            "h20_kept": {
                "n_edges": len(h20_v2),
                "n_h114_v1_default_fires": sum(1 for r in h20_v2 if r.get("h114_v1_default_fires")),
                "n_v2_fires": sum(1 for r in h20_v2 if r.get("fires_any")),
                "n_v2_new": sum(1 for r in h20_v2 if r.get("fires_any") and not r.get("h114_v1_default_fires")),
            },
            "chain_fp_count": len(chain_v2_fps),
            "chain_total": len(chain_edges),
            "threshold_sweep": {
                "n_cells": len(h17_v2_grid),
                "n_safe_cells_0_real": len(h17_v2_safe),
                "best_safe_cell": max(h17_v2_safe, key=lambda g: g["n_fires"]) if h17_v2_safe else None,
            },
        },
        "thresholds": {
            "rule_a": {"T_D": DEFAULT_T_D_A, "T_J": DEFAULT_T_J_A},
            "rule_b": {"T_D": DEFAULT_T_D_B, "T_J": DEFAULT_T_J_B},
            "rule_c": {"T_D": DEFAULT_T_D_C, "T_J": DEFAULT_T_J_C},
        },
    }


def print_final_summary(summary):
    print("=" * 70)
    print("H120 FINAL SUMMARY")
    print("=" * 70)
    print()
    v1 = summary["v1_rule_abc"]
    v2 = summary["v2_rule_ab"]
    print("v1 (A+B+C, 3-rule OR):")
    print(f"  H17 full: {v1['h17_full']['n_v1_fires']} fires ({v1['h17_full']['n_v1_new']} new), "
          f"chain FPs: {v1['chain_fp_count']}/{v1['chain_total']}")
    print(f"  H20-KEPT: {v1['h20_kept']['n_v1_fires']} fires ({v1['h20_kept']['n_v1_new']} new)")
    print(f"  Threshold sweep: {v1['threshold_sweep']['n_safe_cells_0_real']}/{v1['threshold_sweep']['n_cells']} safe")
    print()
    print("v2 (A+B only, drop C):")
    print(f"  H17 full: {v2['h17_full']['n_v2_fires']} fires ({v2['h17_full']['n_v2_new']} new), "
          f"chain FPs: {v2['chain_fp_count']}/{v2['chain_total']}")
    print(f"  H20-KEPT: {v2['h20_kept']['n_v2_fires']} fires ({v2['h20_kept']['n_v2_new']} new)")
    print(f"  Threshold sweep: {v2['threshold_sweep']['n_safe_cells_0_real']}/{v2['threshold_sweep']['n_cells']} safe")
    if v2['threshold_sweep']['best_safe_cell']:
        best = v2['threshold_sweep']['best_safe_cell']
        print(f"  Best safe cell: T_D_B={best['T_D_B']}, T_J_B={best['T_J_B']}, "
              f"{best['n_fires']} fires, {best['n_qa_in_fires']} QA'd, {best['n_real_qa']} REAL, {best['n_false_qa']} FALSE")
    print()
    print("CONCLUSION:")
    if v1['chain_fp_count'] > 0:
        print(f"  v1 (Rule C) is REJECTED: {v1['chain_fp_count']} chain FPs (real catch-throws wrongly flagged).")
    if v2['chain_fp_count'] == 0:
        print(f"  v2 (A+B only) has 0 chain FPs. ")
        if v2['h17_full']['n_v2_new'] > 0:
            print(f"    Adds {v2['h17_full']['n_v2_new']} new H17 fires not in H114 v1 strict.")
        else:
            print(f"    Adds 0 new fires. Rule B is a strict subset of Rule A on the H17 full pool.")
    else:
        print(f"  v2 also has {v2['chain_fp_count']} chain FPs. Multi-rule approach is fundamentally flawed.")


if __name__ == "__main__":
    main()
