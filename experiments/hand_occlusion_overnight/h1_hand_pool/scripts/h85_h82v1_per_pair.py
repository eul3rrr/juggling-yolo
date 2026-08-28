#!/usr/bin/env python3
"""
H85 — H82 v1 (H75v2 + H78 mean_diff>10) cross-validation on the
113 manual review pairs.

H77 already evaluated H75v1 + H78 mean_diff>10 on the 113 review pairs
and achieved P=0.979 R=0.648. H82 v1 (which uses H75v2 instead of H75v1
+ H78) achieved 89.5% on the H70 phase sample (vs H77's 84.2%).

The H85 question: does H82 v1 also improve over H77 on the 113 review
pairs? Specifically, does H74v2 (var<0.20 AND unique_LR<=2) vs H74v1
(var<0.20) catch any new false positives on the chain-edge level?

This script:
1. Loads the 113 review pairs from H77_per_pair_eval.csv
2. For each pair, finds the H70 phase containing the midpoint frame
3. Applies H82 v1 stack: H43 OR H69 OR H74v2 OR H78 mean_diff>10 (FOUNTAIN_3+)
                         H74v2 (CASCADE_3+)
                         H71 spec_conc<0.10 (MIXED_3+)
4. Computes per-pair precision/recall for H82 v1 stack
5. Compares with H77 baseline (H75v1 + H78)
"""
from __future__ import annotations

import csv
import json
import os
import glob
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

# H82 v1 thresholds (H75v2 + H78)
H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20
H74_UNIQUE_LR_THR = 2
H78_MEAN_DIFF_THR = 10
H71_SPEC_CONC_REJECT = 0.10


def load_tracklet_frames(stem: str) -> dict[int, tuple[int, int]]:
    out = {}
    by_tid = defaultdict(list)
    p = DETECTIONS / NORFAIR_CSV[stem]
    with p.open() as fh:
        for r in csv.DictReader(fh):
            by_tid[int(r["track_id"])].append(int(r["frame"]))
    for tid, frames in by_tid.items():
        out[tid] = (min(frames), max(frames))
    return out


def load_h77_per_pair() -> list[dict]:
    out = []
    p = H1_DATA / "h77_per_pair_eval.csv"
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out.append(r)
    return out


def load_h70_phases(stem: str) -> list[dict]:
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
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (int(r["L40v2"]), int(r["R40v2"]))
    return out


def load_h78() -> dict[tuple, dict]:
    p = H1_DATA / "h78v2_wrist_distance_per_phase.csv"
    out = {}
    with p.open() as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = r
    return out


def compute_lr_var_unique(h40v2: dict, start: int, end: int) -> tuple[float, int]:
    """Returns (LR variance, count of unique L+R states rounded to 2 dp)."""
    lrs = []
    for f in range(start, end + 1):
        if f in h40v2:
            l, r = h40v2[f]
            lrs.append(l + r)
    if not lrs:
        return 0.0, 0
    n = len(lrs)
    mean = sum(lrs) / n
    var = sum((v - mean) ** 2 for v in lrs) / n
    unique_lr = len(set(round(v, 2) for v in lrs))
    return var, unique_lr


def h82_decision(pattern: str, conf: float, spec_conc: float, lr_var: float,
                 unique_lr: int, mean_diff: float) -> tuple[bool, str]:
    """H82 v1 decision logic. Returns (rejected, reason)."""
    if pattern == "FOUNTAIN_3+":
        if conf < H43_CONF_THR:
            return True, "H43"
        if spec_conc < H69_SPEC_CONC_THR:
            return True, "H69"
        if lr_var < H74_LR_VAR_THR and unique_lr <= H74_UNIQUE_LR_THR:
            return True, "H74v2"
        if mean_diff > H78_MEAN_DIFF_THR:
            return True, "H78"
        return False, "KEPT"
    elif pattern == "CASCADE_3+":
        if lr_var < H74_LR_VAR_THR and unique_lr <= H74_UNIQUE_LR_THR:
            return True, "H74v2"
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


def find_phase(mid: int, phases: list[dict]) -> dict | None:
    for ph in phases:
        if ph["start"] <= mid <= ph["end"]:
            return ph
    return None


def subset_stats(sub: list[dict], field: str) -> dict:
    n_total = len(sub)
    n_correct = sum(1 for p in sub if p["label"] == "correct")
    n_wrong = sum(1 for p in sub if p["label"] == "wrong")
    TP = sum(1 for p in sub if p["h85_kept"] and p["label"] == "correct")
    FP = sum(1 for p in sub if p["h85_kept"] and p["label"] == "wrong")
    FN = sum(1 for p in sub if not p["h85_kept"] and p["label"] == "correct")
    TN = sum(1 for p in sub if not p["h85_kept"] and p["label"] == "wrong")
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
    print("H85 — H82 v1 cross-validation on 113 manual review pairs")
    print("=" * 80)

    h77_pairs = load_h77_per_pair()
    print(f"Loaded {len(h77_pairs)} H77 review-pair records")

    tracklet_frames = {stem: load_tracklet_frames(stem) for stem in STEMS}
    h70_phases = {stem: load_h70_phases(stem) for stem in STEMS}
    h40v2 = {stem: load_h40v2(stem) for stem in STEMS}
    h78_data = load_h78()  # dict is keyed by (stem, start, end)

    for stem in STEMS:
        n_tids = len(tracklet_frames[stem])
        n_ph = len(h70_phases[stem])
        n_h40 = len(h40v2[stem])
        print(f"  {stem}: {n_tids} tracklets, {n_ph} H70 phases, {n_h40} H40v2 frames")

    # For each review pair, compute H85 decision
    per_pair = []
    no_phase_count = 0
    no_tid_count = 0
    for p in h77_pairs:
        stem = p["stem"]
        src = int(p["source"])
        tgt = int(p["candidate"])
        if src not in tracklet_frames[stem]:
            no_tid_count += 1
            continue
        if tgt not in tracklet_frames[stem]:
            no_tid_count += 1
            continue
        src_s, src_e = tracklet_frames[stem][src]
        tgt_s, tgt_e = tracklet_frames[stem][tgt]
        mid = (src_e + tgt_s) // 2
        ph = find_phase(mid, h70_phases[stem])
        if ph is None:
            no_phase_count += 1
            ph_info = {
                "phase_start": None, "phase_end": None, "pattern": None,
                "conf": None, "spec_conc": None, "lr_var": None,
                "unique_lr": None, "mean_diff": None,
                "h85_decision": "NO_PHASE", "h85_rejected": False,
            }
        else:
            lr_var, unique_lr = compute_lr_var_unique(h40v2[stem], ph["start"], ph["end"])
            h78_row = h78_data.get((stem, ph["start"], ph["end"]), {})
            mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0
            is_rejected, reason = h82_decision(
                ph["pattern"], ph["conf"], ph["spec_conc"], lr_var, unique_lr, mean_diff)
            ph_info = {
                "phase_start": ph["start"],
                "phase_end": ph["end"],
                "pattern": ph["pattern"],
                "conf": ph["conf"],
                "spec_conc": ph["spec_conc"],
                "lr_var": round(lr_var, 4),
                "unique_lr": unique_lr,
                "mean_diff": round(mean_diff, 4),
                "h85_decision": reason,
                "h85_rejected": is_rejected,
            }
        # H85 decision: keep iff in h7v3plus3 AND H85 not rejected
        h85_kept = (p["in_h7v3plus3"] == "True") and not ph_info["h85_rejected"]
        h85_conf_unc = h85_kept and p["q11_label"] in ("CONFIDENT", "UNCERTAIN")

        per_pair.append({
            "stem": p["stem"],
            "source": src,
            "candidate": tgt,
            "gap_frames": int(p["gap_frames"]),
            "label": p["label"],
            "in_h7v3plus3": p["in_h7v3plus3"] == "True",
            "q11": p["q11"],
            "q11_label": p["q11_label"],
            "edge_type": p["edge_type"],
            "midpoint_frame": mid,
            **ph_info,
            "h85_kept": h85_kept,
            "h85_conf_or_uncertain": h85_conf_unc,
        })

    print(f"\nFiltered out: no_tid={no_tid_count}, no_phase={no_phase_count}")
    print(f"Per-pair records for H85: {len(per_pair)}")

    # Per-pair classification
    print(f"\n=== Per-pair confusion (H85 = H82 v1 stack) ===")
    confusions = Counter()
    for p in per_pair:
        key = (p["label"], p["h85_kept"])
        confusions[key] += 1
    for k, v in sorted(confusions.items()):
        print(f"  label={k[0]:<8} h85_kept={str(k[1]):<5} : {v}")

    # Aggregate metrics
    print(f"\n=== H85 aggregate (chain-edge ∩ H82 v1 phase filter) ===")
    full = subset_stats(per_pair, "H85 full (113 pairs)")
    print(f"  {full['label']}: P={full['precision']:.3f} R={full['recall']:.3f} "
          f"FPR={full['FPR']:.3f} (TP={full['TP']} FP={full['FP']} FN={full['FN']} TN={full['TN']})")

    # Per-gap
    print(f"\n=== Per-gap subset ===")
    by_gap = {}
    for gap_thr in [0, 1, 3, 10]:
        sub = [p for p in per_pair if p["gap_frames"] <= gap_thr]
        if not sub:
            continue
        st = subset_stats(sub, f"gap<={gap_thr}")
        by_gap[f"gap<={gap_thr}"] = st
        print(f"  {st['label']}: P={st['precision']:.3f} R={st['recall']:.3f} "
              f"FPR={st['FPR']:.3f} (TP={st['TP']} FP={st['FP']} FN={st['FN']} TN={st['TN']})")

    # Per-stem
    print(f"\n=== Per-stem ===")
    for stem in STEMS:
        sub = [p for p in per_pair if p["stem"] == stem]
        if not sub:
            continue
        st = subset_stats(sub, stem[:5])
        print(f"  {st['label']}: P={st['precision']:.3f} R={st['recall']:.3f} "
              f"FPR={st['FPR']:.3f} (TP={st['TP']} FP={st['FP']} FN={st['FN']} TN={st['TN']})")

    # Conf-or-uncertain gate
    print(f"\n=== H85 + (CONF or UNCER) gate ===")
    sub = [p for p in per_pair if p["h85_conf_or_uncertain"]]
    if sub:
        st = subset_stats(sub, "H85 + (CONF or UNCER)")
        print(f"  {st['label']}: P={st['precision']:.3f} R={st['recall']:.3f} "
              f"FPR={st['FPR']:.3f} (TP={st['TP']} FP={st['FP']} FN={st['FN']} TN={st['TN']})")

    # Disagreements: H77 vs H85
    print(f"\n=== H77 vs H85 disagreements ===")
    h77_kept = {(p["stem"], p["source"], p["candidate"]): p.get("h77_kept", False)
                for p in per_pair}
    n_h77_keep = sum(1 for p in per_pair if p.get("h77_kept", False))
    n_h85_keep = sum(1 for p in per_pair if p["h85_kept"])
    print(f"  H77 kept: {n_h77_keep} / H85 kept: {n_h85_keep}")

    # Pairs that H77 keeps but H85 rejects (new FN)
    new_fn = []
    for p in per_pair:
        if p.get("h77_kept", False) and not p["h85_kept"]:
            new_fn.append(p)
    print(f"  H77 kept but H85 rejects: {len(new_fn)}")
    for p in new_fn:
        print(f"    {p['stem'][:5]} s={p['source']} t={p['candidate']} "
              f"label={p['label']} ph={p['h85_decision']} edge={p['edge_type']}")

    # Pairs that H85 keeps but H77 rejects (new TP)
    new_tp = []
    for p in per_pair:
        if not p.get("h77_kept", False) and p["h85_kept"]:
            new_tp.append(p)
    print(f"  H85 keeps but H77 rejects: {len(new_tp)}")
    for p in new_tp:
        print(f"    {p['stem'][:5]} s={p['source']} t={p['candidate']} "
              f"label={p['label']} ph={p['h85_decision']} edge={p['edge_type']}")

    # Write per-pair CSV
    with (H1_DATA / "h85_per_pair_eval.csv").open("w", newline="") as fh:
        cols = list(per_pair[0].keys())
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for p in per_pair:
            w.writerow(p)
    print(f"\nWrote {H1_DATA / 'h85_per_pair_eval.csv'}")

    # Write summary JSON
    summary = {
        "n_total": len(per_pair),
        "n_no_tid": no_tid_count,
        "n_no_phase": no_phase_count,
        "full": full,
        "by_gap": by_gap,
        "per_stem": {stem[:5]: subset_stats([p for p in per_pair if p["stem"] == stem], stem[:5])
                     for stem in STEMS if any(p["stem"] == stem for p in per_pair)},
        "disagreements": {
            "h77_kept_but_h85_rejects": len(new_fn),
            "h85_keeps_but_h77_rejects": len(new_tp),
            "new_fn": [(p["stem"], p["source"], p["candidate"], p["label"], p["h85_decision"])
                       for p in new_fn],
            "new_tp": [(p["stem"], p["source"], p["candidate"], p["label"], p["h85_decision"])
                       for p in new_tp],
        },
    }
    with (H1_DATA / "h85_summary.json").open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Wrote {H1_DATA / 'h85_summary.json'}")


if __name__ == "__main__":
    main()
