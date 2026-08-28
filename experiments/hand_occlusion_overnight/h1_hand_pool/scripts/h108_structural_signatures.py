#!/usr/bin/env python3
"""H108 — Structural per-frame signature catalog of all 4 TNs.

Hypothesis (from H107 NEGATIVE): the H96 v2 stack achieves PERFECT 17/4/0/0
on the 21 H93 phases because it has FOUR independent per-TN signals:
- TN1: f=685-716 identical (CASCADE_3+ STATIC_HOLD) — caught by H87+max_aloft
- TN2: f=890-936 identical (FOUNTAIN_3+ OTHER_CROSSED_ARM) — caught by H78
- TN3: f=482-594 YouTube (FOUNTAIN_3+ STATIC_HOLD) — caught by H90 NEW
- TN4: f=2-71 YouTube (MIXED_3+_UNCONFIRMED STATIC_HOLD) — caught by H12 v8
  UNCONFIRMED label itself (no extra signal)

A truly complete alternative stack would have an EXPLICIT R4 signal for
f=2-71, so the system doesn't rely on H12 v8's UNCONFIRMED label.

This experiment catalogs the per-frame structural signatures of all 4 TNs
across multiple signals to identify an R4 that could catch f=2-71 without
regressing the 17 JUGGLING TPs.

H108 v1 computes per-phase aggregates for all 21 phases, focusing on:
- max_A: maximum balls aloft (H36/H40 chain)
- n_total: chain-derived total balls
- n_window_events: K=4 events_window count
- h87_pct_ge3: H87 balls-aloft signal
- conf: H12 v8 confidence
- spec_conc: H69 spectral concentration
- avg_quality: H11 chain quality average
- mean_vy, std_vy: per-frame y-velocity stats (if we have raw data)

Goal: identify a (max_A, n_window_events, conf) triple that uniquely
identifies f=2-71.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_h93_gt():
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        return json.load(fh)["corrected_ground_truth"]


def load_per_phase_features():
    """Load H106 per-phase CSV which has the most comprehensive features."""
    out = {}
    with (H1_DATA / "h106_per_phase.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["phase_key"]] = r
    return out


def load_h12_v7_per_frame(stem):
    """Load H12 v7 per-frame data which has n_in_air, n_in_hand, n_total, pattern, confidence."""
    fname = H1_DATA / f"pattern_inference_v7_{stem}.csv"
    if not fname.exists():
        return {}
    out = {}
    with fname.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "frame": f,
                "n_in_air": int(float(r.get("n_in_air", 0))),
                "n_in_hand_left": int(float(r.get("n_in_hand_left", 0))),
                "n_in_hand_right": int(float(r.get("n_in_hand_right", 0))),
                "n_total": int(float(r.get("n_total", 0))),
                "pattern": r.get("pattern", ""),
                "confidence": float(r.get("confidence", 0) or 0),
                "avg_quality": float(r.get("avg_quality", 0) or 0),
                "n_window_events": int(float(r.get("n_window_events", 0))),
            }
    return out


def load_h70_phases(stem):
    """Load H70 per-phase CSV which has A, conf, spectral_concentration."""
    fname = H1_DATA / f"h70_phases_{stem}.csv"
    out = {}
    if not fname.exists():
        return out
    with fname.open() as fh:
        for r in csv.DictReader(fh):
            ps = int(r["phase_start"])
            pe = int(r["phase_end"])
            key = f"{stem}_{ps}_{pe}"
            out[key] = {
                "phase_pattern": r.get("pattern", ""),
                "mean_A": float(r.get("mean_A", 0) or 0),
                "max_A": int(float(r.get("max_A", 0) or 0)),
                "min_A": int(float(r.get("min_A", 0) or 0)),
                "spectral_concentration": float(r.get("spectral_concentration", 0) or 0),
                "mean_confidence": float(r.get("mean_confidence", 0) or 0),
            }
    return out


def compute_per_phase_structural(per_frame, gt, h70, h106):
    """For each H93 phase, compute per-frame structural aggregates."""
    results = []
    for pkey, verdict in gt.items():
        stem = pkey.rsplit("_", 3)[0]
        parts = pkey.rsplit("_", 2)
        s, e = int(parts[1]), int(parts[2])

        # Per-frame aggregates from H12 v7
        frames = [per_frame[f] for f in range(s, e + 1) if f in per_frame]
        n_frames = len(frames)
        if n_frames == 0:
            continue
        max_A = max(f["n_in_air"] for f in frames)
        min_A = min(f["n_in_air"] for f in frames)
        mean_A = sum(f["n_in_air"] for f in frames) / n_frames
        max_events = max(f["n_window_events"] for f in frames)
        min_events = min(f["n_window_events"] for f in frames)
        mean_events = sum(f["n_window_events"] for f in frames) / n_frames
        max_conf = max(f["confidence"] for f in frames)
        min_conf = min(f["confidence"] for f in frames)
        mean_conf = sum(f["confidence"] for f in frames) / n_frames
        n_unconf = sum(1 for f in frames if "UNCONFIRMED" in f["pattern"])
        unconf_frac = n_unconf / n_frames
        max_total = max(f["n_total"] for f in frames)
        min_total = min(f["n_total"] for f in frames)
        n_total_ge3 = sum(1 for f in frames if f["n_total"] >= 3)
        frac_total_ge3 = n_total_ge3 / n_frames

        # H70 features
        h70f = h70.get(pkey, {})

        # H106 features
        h106f = h106.get(pkey, {})

        results.append({
            "phase_key": pkey,
            "stem": stem,
            "verdict": verdict,
            "n_frames": n_frames,
            "max_A": max_A,
            "min_A": min_A,
            "mean_A": round(mean_A, 2),
            "max_events": max_events,
            "min_events": min_events,
            "mean_events": round(mean_events, 2),
            "max_conf": round(max_conf, 3),
            "min_conf": round(min_conf, 3),
            "mean_conf": round(mean_conf, 3),
            "n_unconf": n_unconf,
            "unconf_frac": round(unconf_frac, 3),
            "max_total": max_total,
            "min_total": min_total,
            "frac_total_ge3": round(frac_total_ge3, 3),
            "h70_pattern": h70f.get("phase_pattern", ""),
            "h70_spec_conc": h70f.get("spectral_concentration", ""),
            "h70_max_A": h70f.get("max_A", ""),
            "h106_h87_pct_ge3": h106f.get("h87_pct_ge3", ""),
            "h106_h87_max_aloft": h106f.get("h87_max_aloft", ""),
            "h106_h90_c40_pct_ge3": h106f.get("h90_c40_pct_ge3", ""),
            "h106_h78_mean_diff": h106f.get("lr_mean_diff", ""),
            "h106_lr_var": h106f.get("lr_var", ""),
            "h106_signals_fired": h106f.get("signals_fired", ""),
        })
    return results


def test_r4_candidates(results):
    """For each (max_A, max_events, conf) candidate rule, check if it
    uniquely identifies f=2-71 without false-rejecting any JUGGLING.

    Returns dict[r4_name -> (n_caught_tns, n_false_reject_juggling, list_of_phases_caught)]
    """
    rules = {}

    # R4 candidates based on f=2-71's signature:
    # - max_A=3 (some JUGGLING phases also have max_A=3)
    # - max_events=0 (UNIQUE to f=2-71?)
    # - mean_conf=0.332 (lowest of all H93 phases)
    # - unconf_frac=1.0 (only f=2-71 has 100% UNCONFIRMED)

    # R4a: max_events == 0 (catches only f=2-71)
    caught = [r["phase_key"] for r in results if r["max_events"] == 0]
    rules["R4a_max_events_eq_0"] = caught

    # R4b: unconf_frac == 1.0 (catches only f=2-71)
    caught = [r["phase_key"] for r in results if r["unconf_frac"] == 1.0]
    rules["R4b_unconf_frac_eq_1"] = caught

    # R4c: mean_conf < 0.4 (catches f=2-71 and possibly others)
    caught = [r["phase_key"] for r in results if r["mean_conf"] < 0.4]
    rules["R4c_mean_conf_lt_0.4"] = caught

    # R4d: max_A >= 3 AND max_events == 0
    caught = [r["phase_key"] for r in results if r["max_A"] >= 3 and r["max_events"] == 0]
    rules["R4d_maxA_ge3_AND_maxEvents_eq0"] = caught

    # R4e: max_A >= 3 AND mean_conf < 0.5
    caught = [r["phase_key"] for r in results if r["max_A"] >= 3 and r["mean_conf"] < 0.5]
    rules["R4e_maxA_ge3_AND_meanConf_lt0.5"] = caught

    # R4f: n_unconf / n_frames >= 0.95 AND max_A >= 3
    caught = [r["phase_key"] for r in results if r["unconf_frac"] >= 0.95 and r["max_A"] >= 3]
    rules["R4f_unconf95_AND_maxA3"] = caught

    return rules


def evaluate_r4(rules, gt):
    """For each R4 candidate, count TNs caught and TPs (JUGGLING) false-rejected."""
    eval_results = []
    for rule_name, caught in rules.items():
        n_tn = 0
        n_fp = 0
        caught_tns = []
        caught_fps = []
        for pkey in caught:
            verdict = gt.get(pkey, "")
            if verdict in ("STATIC_HOLD", "OTHER_CROSSED_ARM"):
                n_tn += 1
                caught_tns.append(pkey)
            elif verdict == "JUGGLING":
                n_fp += 1
                caught_fps.append(pkey)
        # Total TNs in GT
        total_tns = sum(1 for v in gt.values() if v != "JUGGLING")
        total_tps = sum(1 for v in gt.values() if v == "JUGGLING")
        eval_results.append({
            "rule": rule_name,
            "n_caught": len(caught),
            "n_tn_caught": n_tn,
            "n_fp": n_fp,
            "total_tns": total_tns,
            "total_tps": total_tps,
            "caught_tns": caught_tns,
            "caught_fps": caught_fps,
        })
    return eval_results


def main():
    print("=" * 80)
    print("H108 — Structural per-frame signature catalog of all 4 TNs")
    print("=" * 80)

    gt = load_h93_gt()
    h106 = load_per_phase_features()
    h70 = {}
    for stem in STEMS:
        h70.update(load_h70_phases(stem))

    # Pre-load per-frame data per stem, then compute per-phase aggregates
    # directly per phase.
    per_stem_per_frame = {stem: load_h12_v7_per_frame(stem) for stem in STEMS}
    all_results = []
    for pkey, verdict in gt.items():
        # Match stem by checking if pkey starts with stem + "_<digits>_<digits>$"
        # GT keys are like "{stem}_{start}_{end}" with stem being one of STEMS.
        stem = None
        for s in STEMS:
            if pkey.startswith(s + "_"):
                # Verify the suffix is exactly two underscore-separated integers
                suffix = pkey[len(s) + 1:]
                if suffix.count("_") == 1 and all(part.isdigit() for part in suffix.split("_")):
                    stem = s
                    break
        if stem is None:
            continue
        per_frame = per_stem_per_frame.get(stem, {})
        # Parse s, e from pkey = "{stem}_{s}_{e}"
        suffix = pkey[len(stem) + 1:]
        s, e = (int(x) for x in suffix.split("_"))

        # Per-frame aggregates from H12 v7
        frames = [per_frame[f] for f in range(s, e + 1) if f in per_frame]
        n_frames = len(frames)
        if n_frames == 0:
            continue
        max_A = max(f["n_in_air"] for f in frames)
        min_A = min(f["n_in_air"] for f in frames)
        mean_A = sum(f["n_in_air"] for f in frames) / n_frames
        max_events = max(f["n_window_events"] for f in frames)
        min_events = min(f["n_window_events"] for f in frames)
        mean_events = sum(f["n_window_events"] for f in frames) / n_frames
        max_conf = max(f["confidence"] for f in frames)
        min_conf = min(f["confidence"] for f in frames)
        mean_conf = sum(f["confidence"] for f in frames) / n_frames
        n_unconf = sum(1 for f in frames if "UNCONFIRMED" in f["pattern"])
        unconf_frac = n_unconf / n_frames
        max_total = max(f["n_total"] for f in frames)
        min_total = min(f["n_total"] for f in frames)
        n_total_ge3 = sum(1 for f in frames if f["n_total"] >= 3)
        frac_total_ge3 = n_total_ge3 / n_frames

        # H70 features
        h70f = h70.get(pkey, {})

        # H106 features
        h106f = h106.get(pkey, {})

        all_results.append({
            "phase_key": pkey,
            "stem": stem,
            "verdict": verdict,
            "n_frames": n_frames,
            "max_A": max_A,
            "min_A": min_A,
            "mean_A": round(mean_A, 2),
            "max_events": max_events,
            "min_events": min_events,
            "mean_events": round(mean_events, 2),
            "max_conf": round(max_conf, 3),
            "min_conf": round(min_conf, 3),
            "mean_conf": round(mean_conf, 3),
            "n_unconf": n_unconf,
            "unconf_frac": round(unconf_frac, 3),
            "max_total": max_total,
            "min_total": min_total,
            "frac_total_ge3": round(frac_total_ge3, 3),
            "h70_pattern": h70f.get("phase_pattern", ""),
            "h70_spec_conc": h70f.get("spectral_concentration", ""),
            "h70_max_A": h70f.get("max_A", ""),
            "h106_h87_pct_ge3": h106f.get("h87_pct_ge3", ""),
            "h106_h87_max_aloft": h106f.get("h87_max_aloft", ""),
            "h106_h90_c40_pct_ge3": h106f.get("h90_c40_pct_ge3", ""),
            "h106_h78_mean_diff": h106f.get("lr_mean_diff", ""),
            "h106_lr_var": h106f.get("lr_var", ""),
            "h106_signals_fired": h106f.get("signals_fired", ""),
        })

    # Per-phase summary table
    print("\n=== Per-phase structural signature (all 21 H93 phases) ===")
    print(f"{'phase_key':<60} {'verdict':<22} {'maxA':>4} {'maxE':>4} {'meanC':>6} {'unconf':>6} {'signals_fired':<30}")
    for r in sorted(all_results, key=lambda r: (r["stem"], -1 if r["verdict"] == "JUGGLING" else 0)):
        if r["verdict"] != "JUGGLING" or r["phase_key"].endswith("_2_71") or r["phase_key"].endswith("_890_936"):
            print(f"  {r['phase_key'][-50:]:<50} {r['verdict']:<22} "
                  f"{r['max_A']:>4} {r['max_events']:>4} {r['mean_conf']:>6.3f} "
                  f"{r['unconf_frac']:>6.2f} {r['h106_signals_fired']:<30}")

    # TN-specific analysis: 4 TNs side-by-side
    print("\n=== 4 TNs side-by-side ===")
    tns = [r for r in all_results if r["verdict"] in ("STATIC_HOLD", "OTHER_CROSSED_ARM")]
    print(f"{'phase_key':<60} {'maxA':>4} {'maxE':>4} {'meanC':>6} {'unconf':>6} {'n_total_max':>10} {'n_total_min':>10}")
    for r in tns:
        print(f"  {r['phase_key'][-50:]:<50} {r['max_A']:>4} {r['max_events']:>4} "
              f"{r['mean_conf']:>6.3f} {r['unconf_frac']:>6.2f} {r['max_total']:>10} {r['min_total']:>10}")

    # R4 candidates
    print("\n=== R4 candidate evaluation ===")
    rules = test_r4_candidates(all_results)
    eval_results = evaluate_r4(rules, gt)
    print(f"{'rule':<30} {'caught':>6} {'TN':>3} {'FP':>3} {'caught_tns':<60} {'caught_fps':<30}")
    for ev in eval_results:
        tns_s = ",".join([p[-20:] for p in ev["caught_tns"]])
        fps_s = ",".join([p[-15:] for p in ev["caught_fps"]])
        print(f"  {ev['rule']:<30} {ev['n_caught']:>6} {ev['n_tn_caught']:>3} {ev['n_fp']:>3} {tns_s:<60} {fps_s:<30}")

    # Identify the R4 that uniquely catches f=2-71 without false-rejecting
    print("\n=== Recommended R4 (catches f=2-71, no FPs) ===")
    best_rules = [ev for ev in eval_results if ev["n_tn_caught"] >= 1 and ev["n_fp"] == 0]
    for ev in best_rules:
        print(f"  {ev['rule']}: catches {ev['n_tn_caught']}/{ev['total_tns']} TNs, 0 FPs")
        for tn in ev["caught_tns"]:
            print(f"    - {tn}")

    # Save outputs
    out_csv = H1_DATA / "h108_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(all_results[0].keys()))
        wr.writeheader()
        wr.writerows(all_results)
    print(f"\nPer-phase CSV: {out_csv}")

    # Summary
    summary = {
        "method": "H108: per-phase structural signature catalog of all 21 H93 phases + R4 candidate search",
        "n_phases": len(all_results),
        "n_tns": len(tns),
        "r4_candidates": eval_results,
    }
    out = H1_DATA / "h108_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Summary: {out}")


if __name__ == "__main__":
    main()
