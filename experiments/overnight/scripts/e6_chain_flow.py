#!/usr/bin/env python3
"""E6: chain-level global stitching (assignment/DAG formulation).

Each tracklet may have at most one successor and one predecessor; eligible
edges (gap<=10) cost balN prediction error. Successor assignment via Hungarian
on an N x (N+N) matrix (dummy no-successor columns at cost 0) yields disjoint
paths because eligibility edges strictly increase time (DAG, cycle-free).

Compared methods per video and gate:
* greedy-rank1 : accept rank-1 link iff its error <= gate, then follow links.
* global       : Hungarian successor assignment, keep assigned edges <= gate.

Evaluated:
* pairwise acceptance vs labels (TP/FP/F1) as in E2;
* chain-level: labeled correct pairs connected in the same chain vs wrong pairs
  connected (higher separation is better);
* conflict counts and chain statistics.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

BASE = Path(__file__).resolve().parents[1]
LEGACY = BASE / "data" / "legacy_csv"
SHIPPED = BASE.parents[1] / "detections"
OUT_DIR = BASE / "data"
REPORT_DIR = BASE / "reports"

SCORES_PATH = OUT_DIR / "e1_pair_scores.csv"
MODELS = ("bal8", "bal12", "cv2")
MAX_GAP = 10


def load_rows() -> list[dict]:
    with SCORES_PATH.open(newline="") as fh:
        out = []
        for row in csv.DictReader(fh):
            row["source_tracklet"] = int(row["source_tracklet"])
            row["candidate_tracklet"] = int(row["candidate_tracklet"])
            for m in MODELS:
                row[m] = float(row[m]) if row[m] not in ("", None) else None
            out.append(row)
    return out


def load_all_tracklets(stem: str) -> list[int]:
    path = LEGACY / f"{stem}.csv"
    ids = set()
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            ids.add(int(row["track_id"]))
    return sorted(ids)


def load_labels() -> dict[tuple[str, int, int], str]:
    labels = {}
    with (SHIPPED / "stitch_review_labels.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            labels[(row["video"], int(row["source_tracklet"]), int(row["candidate_tracklet"]))] = (
                row["label"]
            )
    return labels


def greedy_links(sub: list[dict], model: str, gate: float) -> set[tuple[int, int]]:
    by_source = defaultdict(list)
    for r in sub:
        v = r[model]
        if v is not None:
            by_source[r["source_tracklet"]].append(r)
    links = set()
    for s, group in by_source.items():
        group.sort(key=lambda r: (r[model], r["candidate_tracklet"]))
        best = group[0]
        if best[model] <= gate:
            links.add((s, best["candidate_tracklet"]))
    return links


def global_links(
    sub: list[dict], model: str, gate: float, all_ids: list[int]
) -> set[tuple[int, int]]:
    n = len(all_ids)
    idx = {t: i for i, t in enumerate(all_ids)}
    big = 1e9
    # Real-edge block initialised to big; dummy block priced AT THE GATE so that
    # assigning an edge with cost v < gate yields a net saving of (gate - v).
    cost = np.full((n, 2 * n), big)
    cost[:, n:] = gate
    for r in sub:
        v = r[model]
        if v is None or v >= gate:
            continue
        si = idx[r["source_tracklet"]]
        ci = idx[r["candidate_tracklet"]]
        if cost[si, ci] > v:
            cost[si, ci] = v
    rows_i, cols_i = linear_sum_assignment(cost)
    links = set()
    for ri, ci in zip(rows_i, cols_i):
        if ci < n and cost[ri, ci] < gate:
            links.add((all_ids[ri], all_ids[ci]))
    return links


def chains_from(links: set[tuple[int, int]]) -> dict[int, list[int]]:
    """Decompose directed links into chains; returns root -> members."""
    succ = {s: c for s, c in links}
    preds = {c for _, c in links}
    chains = {}
    visited = set()
    for start in sorted(succ.keys()):
        if start in preds or start in visited:
            continue
        chain = [start]
        visited.add(start)
        cur = succ.get(start)
        while cur is not None and cur not in visited:
            chain.append(cur)
            visited.add(cur)
            cur = succ.get(cur)
        chains[start] = chain
    return chains


def connected_pairs(links: set[tuple[int, int]], pairs: list[tuple[int, int]]) -> int:
    """Count pairs whose endpoints are transitively linked."""
    parent = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s, c in links:
        rs, rc = find(s), find(c)
        if rs != rc:
            parent[rs] = rc
    return sum(1 for a, b in pairs if find(a) == find(b))


def main() -> None:
    rows = load_rows()
    labels = load_labels()
    results = []
    for stem_key in sorted({r["stem"] for r in rows}):
        video_key = next(r["video"] for r in rows if r["stem"] == stem_key)
        sub = [r for r in rows if r["stem"] == stem_key]
        all_ids = load_all_tracklets(stem_key)

        labeled_correct = [
            (r["source_tracklet"], r["candidate_tracklet"])
            for r in sub if labels.get((video_key, r["source_tracklet"], r["candidate_tracklet"])) == "correct"
        ]
        labeled_wrong = [
            (r["source_tracklet"], r["candidate_tracklet"])
            for r in sub if labels.get((video_key, r["source_tracklet"], r["candidate_tracklet"])) == "wrong"
        ]

        errs = sorted(r["bal8"] for r in sub if r["bal8"] is not None)
        gates = [float(np.percentile(errs, p)) for p in (40, 55, 65, 75, 85, 92)]
        for gi, gate in enumerate(gates):
            for method in ("greedy", "global"):
                if method == "greedy":
                    links = greedy_links(sub, "bal8", gate)
                else:
                    links = global_links(sub, "bal8", gate, all_ids)
                tp = len(links & set(labeled_correct))
                fp = len(links & set(labeled_wrong))
                conf = len(links) - len({c for _, c in links})
                chains = chains_from(links)
                lens = [len(c) for c in chains.values()]
                results.append({
                    "stem": stem_key,
                    "method": method,
                    "gate_idx": gi,
                    "gate": round(gate, 1),
                    "n_links": len(links),
                    "tp": tp,
                    "fp": fp,
                    "conflicts": conf,
                    "n_chains": len(chains),
                    "max_chain": max(lens) if lens else 0,
                    "mean_chain": round(float(np.mean(lens)), 2) if lens else 0.0,
                    "correct_connected": connected_pairs(links, labeled_correct),
                    "wrong_connected": connected_pairs(links, labeled_wrong),
                    "n_labeled_correct": len(labeled_correct),
                    "n_labeled_wrong": len(labeled_wrong),
                })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "e6_chains.json").write_text(json.dumps(results, indent=2))

    lines = [
        "# E6: chain-level global stitching vs greedy",
        "",
        "| video | method | g# | gate | links | TP | FP | confl | chains | max | mean | corrConn | wrongConn |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['stem'][:18]} | {r['method']} | {r['gate_idx']} | {r['gate']:.0f} | "
            f"{r['n_links']} | {r['tp']} | {r['fp']} | {r['conflicts']} | "
            f"{r['n_chains']} | {r['max_chain']} | {r['mean_chain']} | "
            f"{r['correct_connected']}/{r['n_labeled_correct']} | "
            f"{r['wrong_connected']}/{r['n_labeled_wrong']} |"
        )
    (REPORT_DIR / "e6_report.md").write_text("\n".join(lines) + "\n")
    print(f"{len(results)} configurations; summary:")
    print(f"{'video':18} {'method':7} {'g#':3} {'links':>5} {'TP':>3}{'FP':>3} {'confl':>5} {'corrConn':>8} {'wrongConn':>9}")
    for r in results:
        print(
            f"{r['stem'][:18]:18} {r['method']:7} {r['gate_idx']:3d} {r['n_links']:5d} "
            f"{r['tp']:3d}{r['fp']:3d} {r['conflicts']:5d} "
            f"{r['correct_connected']:3d}/{r['n_labeled_correct']:<4d} "
            f"{r['wrong_connected']:3d}/{r['n_labeled_wrong']:<4d}"
        )


if __name__ == "__main__":
    main()
