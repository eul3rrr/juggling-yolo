#!/usr/bin/env python3
"""
H88 — H87 cross-validation on 113 manual review pairs.

H87 adds a ball-detection-based pct_ge3 < 0.20 filter to the H82 v1
stack. This catches the H82 v1 FP at f=685-716 (MANIPULATION,
pct_ge3=0.16 < 0.20) on identical. The H88 question: does H87 also
add any new false positives or false negatives at the 113-pair level?

The 113 pairs map to H70 phases via midpoint frame, just like H77/H85.
For each phase-mapped pair, apply H87 pct_ge3 < 0.20 on top of H82 v1.
"""
from __future__ import annotations

import csv
import json
import os
import glob
from collections import Counter
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

H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20
H74_UNIQUE_LR_THR = 2
H78_MEAN_DIFF_THR = 10
H71_SPEC_CONC_REJECT = 0.10
H87_PCT_GE3_THR = 0.20


def load_tracklet_frames(stem: str) -> dict:
    out = {}
    by_tid = {}
    p = DETECTIONS / NORFAIR_CSV[stem]
    with open(p) as fh:
        for r in csv.DictReader(fh):
            by_tid.setdefault(int(r["track_id"]), []).append(int(r["frame"]))
    for tid, frames in by_tid.items():
        out[tid] = (min(frames), max(frames))
    return out


def load_h85_per_pair() -> list:
    out = []
    p = H1_DATA / "h85_per_pair_eval.csv"
    with open(p) as fh:
        for r in csv.DictReader(fh):
            out.append(r)
    return out


def load_h40v2(stem: str) -> dict:
    out = {}
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    with open(p) as fh:
        for r in csv.DictReader(fh):
            out[int(r["frame"])] = (int(r["L40v2"]), int(r["R40v2"]))
    return out


def load_h70(stem: str) -> list:
    out = []
    p = H1_DATA / f"h70_phases_{stem}.csv"
    with open(p) as fh:
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


def load_h78() -> dict:
    out = {}
    p = H1_DATA / "h78v2_wrist_distance_per_phase.csv"
    with open(p) as fh:
        for r in csv.DictReader(fh):
            key = (r["stem"], int(r["phase_start"]), int(r["phase_end"]))
            out[key] = r
    return out


def load_h87() -> dict:
    out = {}
    p = H1_DATA / "h87_balls_aloft.json"
    with open(p) as fh:
        d = json.load(fh)
    for k, v in d.items():
        # Format: stem_start_end
        parts = k.rsplit("_", 2)
        stem = "_".join(parts[:-2])
        start = int(parts[-2])
        end = int(parts[-1])
        out[(stem, start, end)] = v
    return out


def compute_lr_var_unique(h40v2, start, end):
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


def h82_h87_decision(pattern, conf, spec_conc, lr_var, unique_lr, mean_diff, pct_ge3):
    """H82 v1 + H87 (pct_ge3 < 0.20)"""
    h43 = (conf < H43_CONF_THR) and pattern == "FOUNTAIN_3+"
    h69 = (spec_conc < H69_SPEC_CONC_THR) and pattern == "FOUNTAIN_3+"
    h74v2 = (lr_var < H74_LR_VAR_THR) and (unique_lr <= H74_UNIQUE_LR_THR)
    h78 = (mean_diff > H78_MEAN_DIFF_THR) and pattern == "FOUNTAIN_3+"
    h71 = (spec_conc < H71_SPEC_CONC_REJECT) and pattern.startswith("MIXED_3+")
    h87 = (pct_ge3 < H87_PCT_GE3_THR)
    if pattern == "FOUNTAIN_3+":
        return h43 or h69 or h74v2 or h78 or h87
    elif pattern == "CASCADE_3+":
        return h74v2 or h87
    elif pattern.startswith("MIXED_3+"):
        return h71 or h87
    return False


def find_phase(mid, phases):
    for ph in phases:
        if ph["start"] <= mid <= ph["end"]:
            return ph
    return None


def subset_stats(sub, field):
    n_total = len(sub)
    n_correct = sum(1 for p in sub if p["label"] == "correct")
    n_wrong = sum(1 for p in sub if p["label"] == "wrong")
    TP = sum(1 for p in sub if p["h88_kept"] and p["label"] == "correct")
    FP = sum(1 for p in sub if p["h88_kept"] and p["label"] == "wrong")
    FN = sum(1 for p in sub if not p["h88_kept"] and p["label"] == "correct")
    TN = sum(1 for p in sub if not p["h88_kept"] and p["label"] == "wrong")
    p = TP / max(1, TP + FP)
    r = TP / max(1, n_correct)
    fpr = FP / max(1, n_wrong)
    return {
        "label": field,
        "n_total": n_total,
        "n_correct": n_correct,
        "n_wrong": n_wrong,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": round(p, 4),
        "recall": round(r, 4),
        "FPR": round(fpr, 4),
    }


def main():
    print("=" * 80)
    print("H88 — H87 cross-validation on 113 manual review pairs")
    print("=" * 80)

    h85_pairs = load_h85_per_pair()
    print(f"Loaded {len(h85_pairs)} H85 review-pair records")

    tracklet_frames = {stem: load_tracklet_frames(stem) for stem in STEMS}
    h70_phases = {stem: load_h70(stem) for stem in STEMS}
    h40v2 = {stem: load_h40v2(stem) for stem in STEMS}
    h78_data = load_h78()
    h87_data = load_h87()

    # For each review pair, compute H88 decision
    per_pair = []
    no_phase_count = 0
    for p in h85_pairs:
        stem = p["stem"]
        src = int(p["source"])
        tgt = int(p["candidate"])
        if src not in tracklet_frames[stem]:
            continue
        if tgt not in tracklet_frames[stem]:
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
                "unique_lr": None, "mean_diff": None, "pct_ge3": None,
                "h88_decision": "NO_PHASE", "h88_rejected": False,
            }
        else:
            lr_var, unique_lr = compute_lr_var_unique(h40v2[stem], ph["start"], ph["end"])
            h78_row = h78_data.get((stem, ph["start"], ph["end"]), {})
            mean_diff = float(h78_row.get("mean_diff_per_frame", 0)) if h78_row else 0
            h87_row = h87_data.get((stem, ph["start"], ph["end"]), {})
            pct_ge3 = h87_row.get("pct_ge3", 0) if h87_row else 0
            is_rejected = h82_h87_decision(
                ph["pattern"], ph["conf"], ph["spec_conc"],
                lr_var, unique_lr, mean_diff, pct_ge3)
            ph_info = {
                "phase_start": ph["start"],
                "phase_end": ph["end"],
                "pattern": ph["pattern"],
                "conf": ph["conf"],
                "spec_conc": ph["spec_conc"],
                "lr_var": round(lr_var, 4),
                "unique_lr": unique_lr,
                "mean_diff": round(mean_diff, 4),
                "pct_ge3": pct_ge3,
                "h88_decision": "H87" if is_rejected and pct_ge3 < H87_PCT_GE3_THR else (
                    "H82v1" if is_rejected else "KEPT"),
                "h88_rejected": is_rejected,
            }
        h88_kept = (p["in_h7v3plus3"] == "True") and not ph_info["h88_rejected"]
        h88_conf_unc = h88_kept and p["q11_label"] in ("CONFIDENT", "UNCERTAIN")

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
            "h88_kept": h88_kept,
            "h88_conf_or_uncertain": h88_conf_unc,
        })

    print(f"\nFiltered out: no_phase={no_phase_count}")
    print(f"Per-pair records for H88: {len(per_pair)}")

    # Per-pair classification
    print(f"\n=== Per-pair confusion (H88 = H82 v1 + H87) ===")
    confusions = Counter()
    for p in per_pair:
        key = (p["label"], p["h88_kept"])
        confusions[key] += 1
    for k, v in sorted(confusions.items()):
        print(f"  label={k[0]:<8} h88_kept={str(k[1]):<5} : {v}")

    # Aggregate metrics
    print(f"\n=== H88 aggregate (chain-edge ∩ H82 v1 + H87 phase filter) ===")
    full = subset_stats(per_pair, "H88 full (113 pairs)")
    print(f"  {full['label']}: P={full['precision']:.3f} R={full['recall']:.3f} "
          f"FPR={full['FPR']:.3f} (TP={full['TP']} FP={full['FP']} FN={full['FN']} TN={full['TN']})")

    # Per-gap
    print(f"\n=== Per-gap subset ===")
    for gap_thr in [0, 1, 3, 10]:
        sub = [p for p in per_pair if p["gap_frames"] <= gap_thr]
        if not sub:
            continue
        st = subset_stats(sub, f"gap<={gap_thr}")
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
    print(f"\n=== H88 + (CONF or UNCER) gate ===")
    sub = [p for p in per_pair if p["h88_conf_or_uncertain"]]
    if sub:
        st = subset_stats(sub, "H88 + (CONF or UNCER)")
        print(f"  {st['label']}: P={st['precision']:.3f} R={st['recall']:.3f} "
              f"FPR={st['FPR']:.3f} (TP={st['TP']} FP={st['FP']} FN={st['FN']} TN={st['TN']})")

    # H85 vs H88 disagreements
    h85_kept = {(p["stem"], p["source"], p["candidate"]): p.get("h85_kept", False)
                for p in per_pair}
    n_h85_keep = sum(1 for p in per_pair if p.get("h85_kept", False))
    n_h88_keep = sum(1 for p in per_pair if p["h88_kept"])
    print(f"\n=== H85 vs H88 disagreements ===")
    print(f"  H85 kept: {n_h85_keep} / H88 kept: {n_h88_keep}")

    # Pairs that H85 keeps but H88 rejects (new FN)
    new_fn = []
    for p in per_pair:
        if p.get("h85_kept", False) and not p["h88_kept"]:
            new_fn.append(p)
    print(f"  H85 kept but H88 rejects: {len(new_fn)}")
    for p in new_fn:
        print(f"    {p['stem'][:5]} s={p['source']} t={p['candidate']} "
              f"label={p['label']} ph={p['h88_decision']} edge={p['edge_type']} pct_ge3={p.get('pct_ge3')}")

    # Pairs that H88 keeps but H85 rejects (new TP)
    new_tp = []
    for p in per_pair:
        if not p.get("h85_kept", False) and p["h88_kept"]:
            new_tp.append(p)
    print(f"  H88 keeps but H85 rejects: {len(new_tp)}")
    for p in new_tp:
        print(f"    {p['stem'][:5]} s={p['source']} t={p['candidate']} "
              f"label={p['label']} ph={p['h88_decision']} edge={p['edge_type']}")

    # Write per-pair CSV
    with open(f"{H1_DATA}/h88_per_pair_eval.csv", "w", newline="") as fh:
        cols = list(per_pair[0].keys())
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for p in per_pair:
            w.writerow(p)
    print(f"\nWrote {H1_DATA}/h88_per_pair_eval.csv")

    # Write summary JSON
    summary = {
        "n_total": len(per_pair),
        "n_no_phase": no_phase_count,
        "full": full,
        "disagreements": {
            "h85_kept_but_h88_rejects": len(new_fn),
            "h88_keeps_but_h85_rejects": len(new_tp),
        },
    }
    with open(f"{H1_DATA}/h88_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Wrote {H1_DATA}/h88_summary.json")


if __name__ == "__main__":
    main()
