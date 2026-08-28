#!/usr/bin/env python3
"""H77 — Cross-validate H59 (chain-edge precision/recall on 113 review pairs)
with H76 (phase-level precision/recall on 20 H70 substantial phases).

H59 evaluates at the chain-edge level: a review pair is TP if the
h7v3plus3 chain set contains the (source, candidate) edge and the
manual label is "correct". H59 P=0.981 R=0.718 on 113 pairs.

H76 evaluates at the phase level: a substantial phase is TP if H12 v8
labels it the right pattern AND the H75 stack (H43+H69+H74) does not
reject it. H76 P=88% R=93% on 19 phases.

The two evaluations are at different granularities and on different
ground-truth sets. H77 bridges them by:
1. For each of the 113 manual review pairs, find the H70 phase
   containing the (source, candidate) midpoint frame.
2. Apply the H75 stack to that phase.
3. Define H77 decision:
   - KEEP if h7v3plus3 contains the edge AND H75 stack keeps the phase
   - REJECT otherwise
4. Cross-tabulate: H59-only-TP, H77-still-TP, H77-rejected-but-H59-kept,
   etc.
5. Find specific disagreements: review pairs in rejected H70 phases,
   review pairs outside any H70 phase (mid-air).

Outputs:
  - data/h77_per_pair_eval.csv (113 rows, H59 + H77 + phase mapping)
  - data/h77_summary.json
  - report: h77_combined_h59_h76_report.md
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
DETECTIONS = WORKTREE / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

NORFAIR_CSV = {
    "identical_balls_trick_000_018":
        "identical_balls_trick_000_018_norfair_dt50_hc5.csv",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_norfair_dt50_hc5.csv",
}

# H75 / H71 v1 thresholds (from h76_end_to_end_eval.py)
H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20
H71_SPEC_CONC_KEEP = 0.15
H71_SPEC_CONC_REJECT = 0.10


def load_tracklet_frames(stem: str) -> dict[int, tuple[int, int]]:
    """Return {tid: (start_frame, end_frame)} from the norfair CSV."""
    out = {}
    by_tid = defaultdict(list)
    p = DETECTIONS / NORFAIR_CSV[stem]
    with p.open() as fh:
        for r in csv.DictReader(fh):
            by_tid[int(r["track_id"])].append(int(r["frame"]))
    for tid, frames in by_tid.items():
        out[tid] = (min(frames), max(frames))
    return out


def load_h59_per_pair() -> list[dict]:
    """Load H59 per-pair evaluation."""
    out = []
    p = H1_DATA / "h59_per_pair_eval.csv"
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "stem": r["stem"],
                "source": int(r["source"]),
                "candidate": int(r["candidate"]),
                "gap_frames": int(r["gap_frames"]),
                "label": r["label"],
                "in_h7v3plus3": r["in_h7v3plus3"] == "True",
                "in_h1v4d": r["in_h1v4d"] == "True",
                "in_e6c": r["in_e6c"] == "True",
                "edge_type": r["edge_type"],
                "chain_id": (int(r["chain_id"]) if r["chain_id"] != "None" and r["chain_id"] else None),
                "q11": (float(r["q11"]) if r["q11"] != "None" and r["q11"] else None),
                "q11_label": r["q11_label"],
            })
    return out


def load_h70_phases(stem: str) -> list[dict]:
    """Return list of H70 phase dicts sorted by start frame."""
    p = H1_DATA / f"h70_phases_{stem}.csv"
    out = []
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "pattern": r["pattern"],
                "start": int(r["phase_start"]),
                "end": int(r["phase_end"]),
                "n_frames": int(r["n_frames"]),
                "conf": float(r["mean_confidence"]),
                "spec_conc": float(r["spectral_concentration"]),
            })
    return sorted(out, key=lambda x: x["start"])


def load_h40v2(stem: str) -> dict[int, tuple[int, int]]:
    """Return {frame: (L40v2, R40v2)} for LR variance computation."""
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (int(r["L40v2"]), int(r["R40v2"]))
    return out


def compute_lr_var(h40v2: dict, start: int, end: int) -> float:
    series = []
    for f in range(start, end + 1):
        if f in h40v2:
            l, r = h40v2[f]
            series.append(l + r)
    return statistics.variance(series) if len(series) > 1 else 0.0


def filter_decision(pattern: str, conf: float, spec_conc: float, lr_var: float) -> tuple[bool, str]:
    """Returns (is_rejected, reason). Mirrors h76_end_to_end_eval.py logic."""
    if pattern == "FOUNTAIN_3+":
        if conf < H43_CONF_THR:
            return True, "H43"
        if spec_conc < H69_SPEC_CONC_THR:
            return True, "H69"
        if lr_var < H74_LR_VAR_THR:
            return True, "H74"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if lr_var < H74_LR_VAR_THR:
            return True, "H74"
        return False, "KEPT"
    elif pattern == "MIXED_3+":
        if spec_conc < H71_SPEC_CONC_REJECT:
            return True, "H71_REJECT"
        return False, "KEPT"
    elif pattern == "MIXED_3+_UNCONFIRMED":
        if spec_conc < H71_SPEC_CONC_REJECT:
            return True, "H71_REJECT"
        return False, "KEPT"
    return False, "KEPT"


def midpoint_frame(src_start: int, src_end: int, tgt_start: int, tgt_end: int) -> int:
    """Midpoint of the (source_end, target_start) transition window."""
    return (src_end + tgt_start) // 2


def find_phase(mid: int, phases: list[dict]) -> dict | None:
    """Return the H70 phase containing the midpoint frame, or None."""
    for ph in phases:
        if ph["start"] <= mid <= ph["end"]:
            return ph
    return None


def subset_stats(sub: list[dict], field: str) -> dict:
    """Compute TP/FP/FN/TN/precision/recall for a subset of per-pair records.

    A pair is "kept" iff in_h7v3plus3 and the H77 decision is not rejected.
    A pair is "correct" iff label == 'correct'.
    """
    n_total = len(sub)
    n_correct = sum(1 for p in sub if p["label"] == "correct")
    n_wrong = sum(1 for p in sub if p["label"] == "wrong")
    TP = sum(1 for p in sub if p["h77_kept"] and p["label"] == "correct")
    FP = sum(1 for p in sub if p["h77_kept"] and p["label"] == "wrong")
    FN = sum(1 for p in sub if not p["h77_kept"] and p["label"] == "correct")
    TN = sum(1 for p in sub if not p["h77_kept"] and p["label"] == "wrong")
    precision = TP / max(1, TP + FP)
    recall = TP / max(1, n_correct)
    fpr = FP / max(1, n_wrong)
    return {
        "label": field,
        "n_total": n_total,
        "n_correct": n_correct,
        "n_wrong": n_wrong,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "FPR": round(fpr, 4),
    }


def main() -> None:
    print("=" * 80)
    print("H77 — Cross-validate H59 (chain-edge) and H76 (phase-level) precision/recall")
    print("=" * 80)

    # Load all the inputs
    h59_pairs = load_h59_per_pair()
    print(f"Loaded {len(h59_pairs)} H59 review-pair records")

    # Per-video inputs
    tracklet_frames = {stem: load_tracklet_frames(stem) for stem in STEMS}
    h70_phases = {stem: load_h70_phases(stem) for stem in STEMS}
    h40v2 = {stem: load_h40v2(stem) for stem in STEMS}

    for stem in STEMS:
        n_tids = len(tracklet_frames[stem])
        n_ph = len(h70_phases[stem])
        n_h40 = len(h40v2[stem])
        print(f"  {stem}: {n_tids} tracklets, {n_ph} H70 phases, {n_h40} H40v2 frames")

    # For each review pair, compute H77 decision
    per_pair = []
    no_phase_count = 0
    no_tid_count = 0
    for p in h59_pairs:
        stem = p["stem"]
        src = p["source"]
        tgt = p["candidate"]
        # Look up tracklet start/end frames
        if src not in tracklet_frames[stem]:
            no_tid_count += 1
            continue
        if tgt not in tracklet_frames[stem]:
            no_tid_count += 1
            continue
        src_s, src_e = tracklet_frames[stem][src]
        tgt_s, tgt_e = tracklet_frames[stem][tgt]
        mid = midpoint_frame(src_s, src_e, tgt_s, tgt_e)
        # Find the H70 phase containing the midpoint
        ph = find_phase(mid, h70_phases[stem])
        if ph is None:
            no_phase_count += 1
            ph_info = {
                "phase_start": None, "phase_end": None, "pattern": None,
                "conf": None, "spec_conc": None, "lr_var": None,
                "phase_decision": "NO_PHASE", "phase_rejected": False,
            }
        else:
            lr_var = compute_lr_var(h40v2[stem], ph["start"], ph["end"])
            is_rejected, reason = filter_decision(
                ph["pattern"], ph["conf"], ph["spec_conc"], lr_var)
            ph_info = {
                "phase_start": ph["start"],
                "phase_end": ph["end"],
                "pattern": ph["pattern"],
                "conf": ph["conf"],
                "spec_conc": ph["spec_conc"],
                "lr_var": lr_var,
                "phase_decision": reason,
                "phase_rejected": is_rejected,
            }
        # H77 decision: keep iff in h7v3plus3 AND phase is not rejected
        h77_kept = p["in_h7v3plus3"] and not ph_info["phase_rejected"]
        # H77 + chain-quality gate: also require h7v3plus3 edge in a
        # CONFIDENT or UNCERTAIN chain (H59's recommended filter)
        h77_conf_unc = h77_kept and p["q11_label"] in ("CONFIDENT", "UNCERTAIN")

        per_pair.append({
            **p,
            "src_start": src_s, "src_end": src_e,
            "tgt_start": tgt_s, "tgt_end": tgt_e,
            "midpoint_frame": mid,
            **ph_info,
            "h77_kept": h77_kept,
            "h77_conf_or_uncertain": h77_conf_unc,
            # For H59-style comparison
            "h59_kept": p["in_h7v3plus3"],
        })

    print(f"\nFiltered out: no_tid={no_tid_count}, no_phase={no_phase_count}")
    print(f"Per-pair records for H77: {len(per_pair)}")

    # Per-pair classification (correct/wrong × kept/rejected)
    print(f"\n=== Per-pair confusion ===")
    confusions = Counter()
    for p in per_pair:
        key = (p["label"], p["h77_kept"])
        confusions[key] += 1
    for k, v in sorted(confusions.items()):
        print(f"  label={k[0]:<8} h77_kept={str(k[1]):<5} : {v}")

    # === Aggregate metrics ===
    print(f"\n=== H77 aggregate (chain-edge ∩ phase-level) ===")
    full = subset_stats(per_pair, "H77 full (113 pairs)")
    print(f"  {full['label']}: P={full['precision']:.3f} R={full['recall']:.3f} "
          f"FPR={full['FPR']:.3f} (TP={full['TP']} FP={full['FP']} FN={full['FN']} TN={full['TN']})")

    # Per-gap
    by_gap = {}
    for max_gap, label in [(0, "gap=0"), (1, "gap<=1"), (3, "gap<=3"),
                            (10, "gap<=10"), (99, "full")]:
        sub = [p for p in per_pair if p["gap_frames"] <= max_gap]
        s = subset_stats(sub, label)
        s["max_gap"] = max_gap
        by_gap[label] = s
        print(f"  {label}: P={s['precision']:.3f} R={s['recall']:.3f} FPR={s['FPR']:.3f} "
              f"(TP={s['TP']} FP={s['FP']} FN={s['FN']})")

    # Per-stem
    by_stem = {}
    print(f"\n=== Per-stem ===")
    for stem in STEMS:
        sub = [p for p in per_pair if p["stem"] == stem]
        s = subset_stats(sub, stem)
        s["stem"] = stem
        by_stem[stem] = s
        print(f"  {stem}: P={s['precision']:.3f} R={s['recall']:.3f} FPR={s['FPR']:.3f} "
              f"(TP={s['TP']} FP={s['FP']} FN={s['FN']})")

    # Per-pattern (the H70 phase pattern containing the review pair)
    by_pattern = defaultdict(list)
    for p in per_pair:
        by_pattern[p.get("pattern") or "NO_PHASE"].append(p)
    by_pattern_stats = {}
    print(f"\n=== Per-pattern (H70 phase pattern) ===")
    for pat, sub in sorted(by_pattern.items()):
        s = subset_stats(sub, pat)
        s["pattern"] = pat
        by_pattern_stats[pat] = s
        print(f"  {pat:<25}: P={s['precision']:.3f} R={s['recall']:.3f} "
              f"(TP={s['TP']} FP={s['FP']} FN={s['FN']})")

    # === Cross-tabulation: H59 (chain-edge) vs H77 (chain-edge ∩ phase) ===
    print(f"\n=== Cross-tabulation: H59 vs H77 ===")
    cross = Counter()
    for p in per_pair:
        # H59 decision was just in_h7v3plus3 (without phase filter)
        h59_kept = p["h59_kept"]
        h77_kept = p["h77_kept"]
        is_correct = p["label"] == "correct"
        cross[(h59_kept, h77_kept, is_correct)] += 1
    print(f"  H59_kept, H77_kept, is_correct : count")
    for k, v in sorted(cross.items()):
        print(f"  {str(k[0]):<5}  {str(k[1]):<5}  {str(k[2]):<5} : {v}")

    # Specific disagreements
    print(f"\n=== Specific disagreements (H59 says keep, H77 rejects) ===")
    n_disagree = 0
    for p in per_pair:
        if p["h59_kept"] and not p["h77_kept"] and p["label"] == "correct":
            # H59 says TP, H77 downgrades to FN due to phase filter
            print(f"  {p['stem']} s={p['source']} t={p['candidate']} gap={p['gap_frames']} "
                  f"label={p['label']} -> phase=({p['phase_start']}-{p['phase_end']} "
                  f"{p['pattern']}) phase_rejected={p['phase_rejected']} reason={p['phase_decision']}")
            n_disagree += 1
    print(f"  Total: {n_disagree} 'H59-TP downgraded to H77-FN by phase filter'")

    print(f"\n=== Specific disagreements (H59 doesn't keep, H77 keeps) ===")
    n_h77_only = 0
    for p in per_pair:
        if not p["h59_kept"] and p["h77_kept"]:
            # H59 says not in chain, H77 says keep -- shouldn't happen
            # because h77_kept requires in_h7v3plus3
            print(f"  UNEXPECTED: {p['stem']} s={p['source']} t={p['candidate']} "
                  f"label={p['label']}")
            n_h77_only += 1
    if n_h77_only == 0:
        print(f"  None (as expected, since H77 requires in_h7v3plus3)")

    # Filter by chain quality: H77 + (CONFIDENT or UNCERTAIN)
    print(f"\n=== H77 + chain quality gate (CONFIDENT or UNCERTAIN) ===")
    sub_cu = [p for p in per_pair if p["h77_conf_or_uncertain"]]
    s = subset_stats(sub_cu, "H77 + (CONF or UNCER)")
    print(f"  {s['label']}: P={s['precision']:.3f} R={s['recall']:.3f} FPR={s['FPR']:.3f} "
          f"(TP={s['TP']} FP={s['FP']} FN={s['FN']})")

    # === Write outputs ===
    out_csv = H1_DATA / "h77_per_pair_eval.csv"
    with out_csv.open("w") as fh:
        fh.write(
            "stem,source,candidate,gap_frames,label,src_start,src_end,tgt_start,tgt_end,"
            "midpoint_frame,in_h7v3plus3,q11,q11_label,edge_type,"
            "phase_start,phase_end,pattern,phase_conf,phase_spec_conc,phase_lr_var,"
            "phase_decision,phase_rejected,h77_kept,h77_conf_or_uncertain\n"
        )
        for p in per_pair:
            fh.write(
                f"{p['stem']},{p['source']},{p['candidate']},{p['gap_frames']},"
                f"{p['label']},{p['src_start']},{p['src_end']},{p['tgt_start']},{p['tgt_end']},"
                f"{p['midpoint_frame']},"
                f"{p['in_h7v3plus3']},{p['q11'] or ''},{p['q11_label']},{p['edge_type']},"
                f"{p['phase_start'] if p['phase_start'] is not None else ''},"
                f"{p['phase_end'] if p['phase_end'] is not None else ''},"
                f"{p['pattern'] or ''},"
                f"{p['conf'] if p['conf'] is not None else ''},"
                f"{p['spec_conc'] if p['spec_conc'] is not None else ''},"
                f"{p['lr_var'] if p['lr_var'] is not None else ''},"
                f"{p['phase_decision']},{p['phase_rejected']},"
                f"{p['h77_kept']},{p['h77_conf_or_uncertain']}\n"
            )
    print(f"\nWrote: {out_csv}")

    out_json = H1_DATA / "h77_summary.json"
    summary = {
        "n_total": len(per_pair),
        "n_no_tid": no_tid_count,
        "n_no_phase": no_phase_count,
        "full": full,
        "by_gap": by_gap,
        "by_stem": by_stem,
        "by_pattern": by_pattern_stats,
        "confusions": {f"{k[0]}_{k[1]}": v for k, v in confusions.items()},
        "cross_tabulation": {
            f"h59_{k[0]}_h77_{k[1]}_correct_{k[2]}": v
            for k, v in cross.items()
        },
        "h77_plus_quality_gate": s,
    }
    out_json.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Wrote: {out_json}")


if __name__ == "__main__":
    main()
