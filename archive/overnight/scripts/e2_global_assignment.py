#!/usr/bin/env python3
"""E2: global one-to-one stitch assignment vs greedy rank-1 acceptance.

Builds the source x candidate cost matrix per video from E1 scores, solves
optimal 1-to-1 assignment (Hungarian via scipy, with per-source no-match dummy
columns priced at the gate), and compares against the shipped greedy behavior:

* greedy@G   -- accept a pair iff it is rank-1 for its source AND error <= G.
* global@G   -- min-cost perfect-ish matching; accept assigned pairs cost <= G.

Evaluated on the 113 reviewed labels as an acceptance-decision classifier:
precision/recall/F1 over ``accepted and correct`` plus candidate-conflict counts
for greedy (two sources claiming one candidate).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

BASE = Path(__file__).resolve().parents[1]
OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"

SCORES_PATH = OUT_DIR / "e1_pair_scores.csv"
MODELS = ("cv2", "bal8", "bal12")


def load_rows() -> list[dict]:
    with SCORES_PATH.open(newline="") as fh:
        out = []
        for row in csv.DictReader(fh):
            row["source_tracklet"] = int(row["source_tracklet"])
            row["candidate_tracklet"] = int(row["candidate_tracklet"])
            row["gap_frames"] = int(row["gap_frames"])
            row["original_rank"] = int(row["original_rank"])
            for m in MODELS:
                row[m] = float(row[m]) if row[m] not in ("", None) else None
            out.append(row)
    return out


def solve_global(rows: list[dict], model: str, gate: float) -> set[tuple[int, int]]:
    """Return accepted (source, candidate) pairs under global assignment."""
    sources = sorted({r["source_tracklet"] for r in rows})
    cands = sorted({r["candidate_tracklet"] for r in rows})
    s_idx = {s: i for i, s in enumerate(sources)}
    c_idx = {c: j for j, c in enumerate(cands)}
    n_s, n_c = len(sources), len(cands)
    cost = np.full((n_s, n_c + n_s), 1e9)
    for r in rows:
        v = r[model]
        if v is None or v > gate:
            continue
        cost[s_idx[r["source_tracklet"]], c_idx[r["candidate_tracklet"]]] = v
    # dummy no-match columns priced exactly at the gate
    cost[:, n_c:] = gate
    row_ind, col_ind = linear_sum_assignment(cost)
    accepted = set()
    for ri, ci in zip(row_ind, col_ind):
        if ci < n_c and cost[ri, ci] <= gate:
            accepted.add((sources[ri], cands[ci]))
    return accepted


def greedy_accepted(rows: list[dict], model: str, gate: float) -> set[tuple[int, int]]:
    acc = set()
    by_source = defaultdict(list)
    for r in rows:
        v = r[model]
        if v is not None:
            by_source[r["source_tracklet"]].append(r)
    for s, group in by_source.items():
        group.sort(key=lambda r: (r[model], r["candidate_tracklet"]))
        best = group[0]
        if best[model] <= gate:
            acc.add((best["source_tracklet"], best["candidate_tracklet"]))
    return acc


def conflicts(pairs: set[tuple[int, int]], rows: list[dict]) -> int:
    """Number of candidate tracklets claimed by more than one source."""
    use = defaultdict(int)
    info = {(r["source_tracklet"], r["candidate_tracklet"]): r for r in rows}
    for s, c in pairs:
        _ = info[(s, c)]
        use[c] += 1
    return sum(1 for v in use.values() if v > 1)


def main() -> None:
    rows = load_rows()
    stems = sorted({r["stem"] for r in rows})

    results = {}
    for model in MODELS:
        for stem in stems:
            sub = [r for r in rows if r["stem"] == stem]
            errs = sorted(r[model] for r in sub if r[model] is not None)
            gates = [float(np.percentile(errs, p)) for p in (40, 55, 65, 75, 85, 92)]
            for gi, gate in enumerate(gates):
                for method, fn in (("greedy", greedy_accepted), ("global", solve_global)):
                    acc = fn(sub, model, gate) if method == "greedy" else solve_global(sub, model, gate)
                    tp = sum(
                        1 for r in sub
                        if (r["source_tracklet"], r["candidate_tracklet"]) in acc
                        and r["label"] == "correct"
                    )
                    fp = sum(
                        1 for r in sub
                        if (r["source_tracklet"], r["candidate_tracklet"]) in acc
                        and r["label"] == "wrong"
                    )
                    fn_ = sum(
                        1 for r in sub
                        if (r["source_tracklet"], r["candidate_tracklet"]) not in acc
                        and r["label"] == "correct"
                    )
                    tn = len(sub) - tp - fp - fn_
                    prec = tp / (tp + fp) if tp + fp else None
                    rec = tp / (tp + fn_) if tp + fn_ else None
                    f1 = (
                        2 * prec * rec / (prec + rec)
                        if prec is not None and rec is not None and prec + rec
                        else None
                    )
                    results[f"{model}|{stem}|{method}|g{gi}"] = {
                        "model": model,
                        "stem": stem,
                        "method": method,
                        "gate": round(gate, 1),
                        "tp": tp,
                        "fp": fp,
                        "fn": fn_,
                        "tn": tn,
                        "precision": round(prec, 4) if prec is not None else None,
                        "recall": round(rec, 4) if rec is not None else None,
                        "f1": round(f1, 4) if f1 is not None else None,
                        "conflicts": conflicts(acc, sub) if method == "greedy" else 0,
                        "n_accepted": len(acc),
                    }

    with (OUT_DIR / "e2_sweep.json").open("w") as fh:
        json.dump(results, fh, indent=2)

    lines = [
        "# E2: global vs greedy stitch acceptance (label-based)",
        "",
        "| model | video | method | gate | acc | correct | wrong | prec | rec | F1 | conflicts |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, r in results.items():
        lines.append(
            f"| {r['model']} | {r['stem'][:18]} | {r['method']} | {r['gate']:.0f} | "
            f"{r['n_accepted']} | {r['tp']} | {r['fp']} | {r['precision']} | "
            f"{r['recall']} | {r['f1']} | {r['conflicts']} |"
        )
    report = "\n".join(lines) + "\n"
    (REPORT_DIR / "e2_report.md").write_text(report)

    # compact summary: best F1 per (model, method) pooled over videos
    pooled = defaultdict(lambda: [0, 0, 0])
    for r in results.values():
        k = (r["model"], r["method"])
        pooled[k][0] += r["tp"]
        pooled[k][1] += r["fp"]
        pooled[k][2] += r["fn"]
    print("pooled TP/FP/FN and F1 by (model, method) at each gate setting:")
    print(f"{'model':6} {'method':7} {'gate#':5} {'TP':>4}{'FP':>4}{'FN':>4}   F1")
    for key, r in results.items():
        tp, fp, fn = r["tp"], r["fp"], r["fn"]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        print(f"{r['model']:6} {r['method']:7} {key.split('|g')[-1]:5} {tp:4d}{fp:4d}{fn:4d}   {f1:.3f}"
              f"   conflicts={r['conflicts']}")


if __name__ == "__main__":
    main()
