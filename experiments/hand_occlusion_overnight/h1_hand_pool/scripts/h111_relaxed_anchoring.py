"""H111: Relaxed edge-to-phase anchoring.

H102 used midgap-only anchoring (midgap frame must fall inside an H93 phase).
H111 tests 3 relaxed anchoring strategies to surface more edge-level evidence:

  S1 midgap:   midgap frame ∈ [phase_start, phase_end]  (H102 baseline)
  S2 union:    midgap OR src_end OR cand_start ∈ phase
  S3 overlap:  the edge [src_end, cand_start] interval overlaps phase

For each strategy, compute per-phase TP/FP/FN/P/R for h7v3plus3 on the
113 review pairs, and identify the strategy that surfaces the most
edge-level signal while remaining interpretable.

The hypothesis: a phase is "this phase is real juggling" only if the
edge HAPPENED DURING the phase. S2 (union) is the most permissive
interpretation; S3 (overlap) is the strictest.

Outputs:
  - data/h111_per_pair.csv: 113 rows with strategy S1/S2/S3 classification
  - data/h111_per_phase.csv: 21 rows with per-phase TP/FP/FN per strategy
  - data/h111_summary.json: aggregate stats per strategy
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
H1_REPORTS = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "reports"

H93_FILE = H1_DATA / "h93_multi_rater_qa.json"
H102_PAIR = H1_DATA / "h102_per_pair.csv"


def load_h93_phases() -> list[tuple[str, int, int, str]]:
    with H93_FILE.open() as f:
        gt = json.load(f)["corrected_ground_truth"]
    out = []
    for pkey, verdict in gt.items():
        parts = pkey.rsplit("_", 2)
        stem, start, end = parts[0], int(parts[1]), int(parts[2])
        out.append((stem, start, end, verdict, pkey))
    return out


def anchor_pair(
    stem: str, src_end: int, tgt_start: int, phases: list
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (S1_pkey, S2_pkey, S3_pkey, midgap_pkey) or None.

    For each strategy, return the matched phase_key or None.
    """
    midgap = (src_end + tgt_start) / 2
    s1 = s2 = s3 = None
    for ps, pstart, pend, _verdict, pkey in phases:
        if ps != stem:
            continue
        # S1: midgap in phase
        if pstart <= midgap <= pend:
            s1 = pkey
        # S2: union (midgap OR src_end OR tgt_start in phase)
        if pstart <= midgap <= pend or pstart <= src_end <= pend or pstart <= tgt_start <= pend:
            s2 = pkey
        # S3: interval overlap (edge spans into phase)
        # [src_end, tgt_start] overlaps [pstart, pend] iff src_end <= pend AND tgt_start >= pstart
        if src_end <= pend and tgt_start >= pstart:
            s3 = pkey
    return s1, s2, s3


def main():
    phases = load_h93_phases()
    rows = list(csv.DictReader(H102_PAIR.open()))

    # Extend each row with S1/S2/S3
    out_rows = []
    for r in rows:
        stem = r["stem"]
        src_end = int(r["src_end_frame"])
        tgt_start = int(r["cand_start_frame"])
        s1, s2, s3 = anchor_pair(stem, src_end, tgt_start, phases)
        new = dict(r)
        new["h111_s1_pkey"] = s1 or ""
        new["h111_s2_pkey"] = s2 or ""
        new["h111_s3_pkey"] = s3 or ""
        out_rows.append(new)

    # Save per-pair CSV
    out_csv = H1_DATA / "h111_per_pair.csv"
    fieldnames = list(out_rows[0].keys())
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote {out_csv}")

    # Per-phase aggregation per strategy
    per_phase = {}
    for pkey, _, _, _, _ in [(p[4], p[1], p[2], p[3], p[0]) for p in phases]:
        per_phase[pkey] = {
            "S1": {"n": 0, "correct": 0, "wrong": 0, "TP": 0, "FP": 0, "FN": 0},
            "S2": {"n": 0, "correct": 0, "wrong": 0, "TP": 0, "FP": 0, "FN": 0},
            "S3": {"n": 0, "correct": 0, "wrong": 0, "TP": 0, "FP": 0, "FN": 0},
        }

    for r in out_rows:
        for sname, key in [("S1", "h111_s1_pkey"), ("S2", "h111_s2_pkey"), ("S3", "h111_s3_pkey")]:
            pkey = r[key]
            if not pkey:
                continue
            d = per_phase[pkey][sname]
            d["n"] += 1
            label = r["label"]
            in_chain = r["in_h7v3plus3"] == "True"
            if label == "correct":
                d["correct"] += 1
                if in_chain:
                    d["TP"] += 1
            else:
                d["wrong"] += 1
                if in_chain:
                    d["FP"] += 1
            if not in_chain and label == "correct":
                d["FN"] += 1

    # Save per-phase CSV
    out_ppcsv = H1_DATA / "h111_per_phase.csv"
    with out_ppcsv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phase_key", "verdict", "strategy", "n", "correct", "wrong", "TP", "FP", "FN", "precision", "recall"])
        for pkey in sorted(per_phase):
            for sname in ["S1", "S2", "S3"]:
                d = per_phase[pkey][sname]
                if d["n"] == 0:
                    continue
                P = d["TP"] / (d["TP"] + d["FP"]) if (d["TP"] + d["FP"]) else 0.0
                R = d["TP"] / (d["TP"] + d["FN"]) if (d["TP"] + d["FN"]) else 0.0
                verdict = next(p[3] for p in phases if p[4] == pkey)
                w.writerow([pkey, verdict, sname, d["n"], d["correct"], d["wrong"], d["TP"], d["FP"], d["FN"], f"{P:.3f}", f"{R:.3f}"])
    print(f"Wrote {out_ppcsv}")

    # Aggregate summary
    summary = {"strategies": {}}
    for sname in ["S1", "S2", "S3"]:
        tot_n = tot_corr = tot_TP = tot_FP = tot_FN = 0
        n_phases = 0
        for pkey, sd in per_phase.items():
            d = sd[sname]
            if d["n"] == 0:
                continue
            n_phases += 1
            tot_n += d["n"]
            tot_corr += d["correct"]
            tot_TP += d["TP"]
            tot_FP += d["FP"]
            tot_FN += d["FN"]
        P = tot_TP / (tot_TP + tot_FP) if (tot_TP + tot_FP) else 0.0
        R = tot_TP / (tot_TP + tot_FN) if (tot_TP + tot_FN) else 0.0
        acc = (tot_TP + (tot_corr - tot_TP)) / tot_n if tot_n else 0.0  # TN = correct-not-in-chain
        summary["strategies"][sname] = {
            "n_phases_with_anchors": n_phases,
            "n_pairs": tot_n,
            "n_correct": tot_corr,
            "n_wrong": tot_n - tot_corr,
            "TP": tot_TP, "FP": tot_FP, "FN": tot_FN,
            "precision": round(P, 4),
            "recall": round(R, 4),
            "accuracy": round(acc, 4),
        }

    # Compare with H102 baseline
    summary["h102_baseline"] = {
        "n_anchored": 15,
        "n_correct": 13,
        "n_wrong": 2,
        "TP": 11, "FP": 0, "FN": 2,
        "precision": 1.0,
        "recall": 0.846,
    }

    with (H1_DATA / "h111_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {H1_DATA / 'h111_summary.json'}")

    # Pretty print
    print()
    print("H111 anchoring strategy comparison:")
    print(f"{'Strategy':<12} {'#phases':>8} {'#pairs':>7} {'corr':>5} {'wr':>4} {'TP':>4} {'FP':>4} {'FN':>4} {'P':>7} {'R':>7} {'acc':>7}")
    for sname in ["S1", "S2", "S3"]:
        d = summary["strategies"][sname]
        print(f"{sname:<12} {d['n_phases_with_anchors']:>8} {d['n_pairs']:>7} {d['n_correct']:>5} {d['n_wrong']:>4} {d['TP']:>4} {d['FP']:>4} {d['FN']:>4} {d['precision']:>7.3f} {d['recall']:>7.3f} {d['accuracy']:>7.3f}")
    print(f"{'H102':<12} {15:>8} {15:>7} {13:>5} {2:>4} {11:>4} {0:>4} {2:>4} {1.0:>7.3f} {0.846:>7.3f} {0.929:>7.3f}")

    # Find NEW edges surfaced by S2 that S1 misses
    new_s2 = []
    for r in out_rows:
        s1 = r["h111_s1_pkey"]
        s2 = r["h111_s2_pkey"]
        if s1 != s2 and s2:
            new_s2.append({
                "src": r["source"], "tgt": r["candidate"], "label": r["label"],
                "in_chain": r["in_h7v3plus3"], "src_end": r["src_end_frame"],
                "tgt_start": r["cand_start_frame"], "s2_pkey": s2,
            })
    print(f"\nNEW S2 anchors (not in S1): {len(new_s2)}")
    print(f"  in_chain: {sum(1 for x in new_s2 if x['in_chain']=='True')}")
    print(f"  correct: {sum(1 for x in new_s2 if x['label']=='correct')}")
    print(f"  wrong: {sum(1 for x in new_s2 if x['label']=='wrong')}")
    if new_s2:
        print("  Sample entries:")
        for x in new_s2[:10]:
            print(f"    {x['src']:>2}->{x['tgt']:<2} {x['label']:<7} in_chain={x['in_chain']:<5} src_end={x['src_end']:>4} tgt_start={x['tgt_start']:>4} -> {x['s2_pkey'][-30:]}")

    # Phase-level verdict comparison: does S2 vs S1 change the phase_verdict quality?
    print("\nPer-phase S1 vs S2 precision/recall diff:")
    for pkey in sorted(per_phase):
        s1d = per_phase[pkey]["S1"]
        s2d = per_phase[pkey]["S2"]
        if s1d["n"] == 0 and s2d["n"] == 0:
            continue
        s1p = s1d["TP"]/(s1d["TP"]+s1d["FP"]) if (s1d["TP"]+s1d["FP"]) else 0
        s2p = s2d["TP"]/(s2d["TP"]+s2d["FP"]) if (s2d["TP"]+s2d["FP"]) else 0
        s1r = s1d["TP"]/(s1d["TP"]+s1d["FN"]) if (s1d["TP"]+s1d["FN"]) else 0
        s2r = s2d["TP"]/(s2d["TP"]+s2d["FN"]) if (s2d["TP"]+s2d["FN"]) else 0
        if s2d["n"] != s1d["n"] or s1p != s2p or s1r != s2r:
            print(f"  {pkey[-30:]:<30} S1: {s1d['n']}p P={s1p:.3f} R={s1r:.3f}  S2: {s2d['n']}p P={s2p:.3f} R={s2r:.3f}")


if __name__ == "__main__":
    main()
