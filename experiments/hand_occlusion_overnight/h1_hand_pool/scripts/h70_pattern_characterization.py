#!/usr/bin/env python3
"""H70 - H69 spec_conc characterization across all pattern types.

H69 demonstrated that FFT spectral concentration of the per-frame
A signal discriminates FOUNTAIN_3+ from HOLD/CASCADE on the H65
sample. H70 extends this characterization to ALL pattern types:
- NO_BALL, SINGLE_BALL, TWO_BALL, TWO_BALL_ONE_HAND, MIXED_3+,
- CASCADE_3+, FOUNTAIN_3+, MIXED_3+_UNCONFIRMED.

Question: Is H69 spec_conc a FOUNTAIN-specific signal, or a more
general "pattern coherence" signal?

HYPOTHESIS:
- A pattern with high A-signal coherence (CASCADE, FOUNTAIN,
  MIXED) should have high spec_conc.
- A static / held pattern (SINGLE_BALL, TWO_BALL, NO_BALL) should
  have low spec_conc.
- TWO_BALL_ONE_HAND and MIXED_3+_UNCONFIRMED are ambiguous.

If true, H69 spec_conc could be used as a generic "is this
pattern actually happening or is it noise?" filter.

METHOD:
1. Load H50-filtered per-frame pattern data.
2. For each substantial phase (>= 20 frames) of any pattern,
   compute the A signal and H69 spec_conc.
3. Aggregate spec_conc statistics per pattern type.
4. Cross-tabulate with the 7 H65 ground truth verdicts to
   validate.
5. Check if spec_conc < 0.15 also catches known-misclassified
   CASCADE / MIXED phases.

Output:
  - data/h70_phases_*.csv (per-phase spec_conc per pattern type)
  - data/h70_summary.json
  - reports/h70_report.md
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from h69_periodicity_fountain import (
    load_pose, load_dets, per_frame_A, compute_autocorrelation,
    spectral_concentration,
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

MIN_PHASE_FRAMES = 20
# Stricter: require at least 20 frames of A data (not just phase range)
MIN_A_FRAMES = 20
H65_GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        (631, 669): "FOUNTAIN", (890, 936): "OTHER",
        (977, 1011): "FOUNTAIN", (1029, 1049): "OTHER",
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (339, 374): "FOUNTAIN", (482, 594): "OTHER", (800, 861): "CASCADE",
    },
}


def load_pattern_phases(stem: str) -> list[dict]:
    """Load ALL substantial pattern phases (>= MIN_PHASE_FRAMES)."""
    p = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(p)):
        n = int(row["n_frames"])
        if n >= MIN_PHASE_FRAMES:
            out.append({
                "pattern": row["pattern"],
                "start": int(row["start_frame"]),
                "end": int(row["end_frame"]),
                "n": n,
                "conf": float(row["avg_confidence"]),
            })
    return out


def main() -> None:
    summary = {"videos": {}}
    pattern_conc = defaultdict(list)  # pattern -> list of spec_conc
    pattern_ac_strength = defaultdict(list)

    for stem in STEMS:
        print(f"\n=== {stem} ===")
        pose = load_pose(stem)
        dets = load_dets(stem)
        phases = load_pattern_phases(stem)
        print(f"  {len(phases)} substantial phases (>= {MIN_PHASE_FRAMES} frames)")

        per_phase_records = []
        for ph in phases:
            A = per_frame_A(pose, dets, ph["start"], ph["end"])
            n_real = len(A)
            if n_real < MIN_A_FRAMES:
                continue
            ac = compute_autocorrelation(A)
            max_lag = min(50, n_real // 2)
            search = ac[5:max_lag + 1]
            peak_val = max(search) if search else 0.0
            peak_lag = (5 + search.index(peak_val)) if search else 0
            conc = spectral_concentration(A)
            mean_A = sum(A) / n_real
            max_A = max(A)
            min_A = min(A)

            verdict = H65_GROUND_TRUTH.get(stem, {}).get((ph["start"], ph["end"]), None)

            record = {
                "pattern": ph["pattern"],
                "phase_start": ph["start"],
                "phase_end": ph["end"],
                "n_frames": n_real,
                "mean_confidence": round(ph["conf"], 3),
                "mean_A": round(mean_A, 3),
                "max_A": max_A,
                "min_A": min_A,
                "spectral_concentration": round(conc, 3),
                "ac_peak_value": round(peak_val, 3),
                "ac_peak_lag": peak_lag,
                "h65_verdict": verdict or "N/A",
            }
            per_phase_records.append(record)
            pattern_conc[ph["pattern"]].append(conc)
            pattern_ac_strength[ph["pattern"]].append(peak_val)

            verdict_str = f"h65={verdict}" if verdict else ""
            print(f"  pattern={ph['pattern']:<25} phase f={ph['start']}-{ph['end']} "
                  f"n={n_real} conc={conc:.3f} ac_peak={peak_val:.3f} lag={peak_lag} {verdict_str}")

        # Write per-phase CSV
        out_csv = H1_DATA / f"h70_phases_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_phase_records[0].keys()))
            w.writeheader()
            w.writerows(per_phase_records)
        print(f"  wrote: {out_csv.name}")

        summary["videos"][stem] = {
            "n_phases": len(per_phase_records),
            "phases": per_phase_records,
        }

    # Per-pattern statistics
    print(f"\n=== Per-pattern H69 spec_conc statistics ===")
    pattern_stats = {}
    for pat, concs in sorted(pattern_conc.items()):
        if not concs:
            continue
        n = len(concs)
        mean_c = sum(concs) / n
        median_c = sorted(concs)[n // 2]
        max_c = max(concs)
        min_c = min(concs)
        n_low = sum(1 for c in concs if c < 0.15)
        ac_peaks = pattern_ac_strength[pat]
        mean_ac = sum(ac_peaks) / n
        print(f"  {pat:<25} n={n:2d} spec_conc mean={mean_c:.3f} median={median_c:.3f} "
              f"range=[{min_c:.3f}, {max_c:.3f}] n<0.15={n_low} ac_peak_mean={mean_ac:.3f}")
        pattern_stats[pat] = {
            "n_phases": n,
            "spec_conc_mean": round(mean_c, 4),
            "spec_conc_median": round(median_c, 4),
            "spec_conc_min": round(min_c, 4),
            "spec_conc_max": round(max_c, 4),
            "spec_conc_lt_015": n_low,
            "ac_peak_mean": round(mean_ac, 4),
            "spec_conc_values": [round(c, 3) for c in sorted(concs)],
        }
    summary["pattern_stats"] = pattern_stats
    summary["methodology"] = {
        "filter": "h70: H69 spec_conc characterization across pattern types",
        "MIN_PHASE_FRAMES": MIN_PHASE_FRAMES,
        "MIN_A_FRAMES": MIN_A_FRAMES,
    }
    out = H1_DATA / "h70_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
