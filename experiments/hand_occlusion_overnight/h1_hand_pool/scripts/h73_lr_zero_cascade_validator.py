#!/usr/bin/env python3
"""H73 - H40 v2 sustained-occupancy + H12 v8 CASCADE_3+ / FOUNTAIN_3+ validator.

Hypothesis (REVISED): H12 v8's CASCADE_3+ / FOUNTAIN_3+ classifications
are unreliable when the H40 v2 sustained-occupancy pattern is inconsistent
with the pattern class.

For a true 3-ball FOUNTAIN, BOTH hands should be occupied for nearly all
frames (each hand holds 1 ball at a time). For a true 3-ball CASCADE,
hands alternate rapidly, so the L+R total should be ~1-2 most of the
time but L=R=0 should be rare (no moment when both hands are empty).

The H72 finding on identical f=685-716:
- H12 v8 says: CASCADE_3+
- H72 vision QA: 3-ball manipulation trick (body rolls / contact juggling),
  NOT a true cascade
- H40 v2: L=0.84 R=0.62 (both hands occupied heavily)

The H40 v2 data is consistent with EITHER a real cascade OR a static
display of balls in each hand. It does NOT distinguish them.

H73 measures: for every substantial CASCADE_3+ / FOUNTAIN_3+ phase,
compute H40 v2 hand-occupancy statistics and compare to expected
pattern values. Look for anomalous patterns (e.g., L=0 or R=0
throughout, which would be inconsistent with a real juggling pattern
of that class).

Cross-reference with H65 ground truth (3 real FOUNTAIN, 4 misclassified
FOUNTAIN_3+ on the H65 sample).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

MIN_PHASE_FRAMES = 20

# Target pattern classes
TARGET_PATTERNS = {"CASCADE_3+", "FOUNTAIN_3+"}

# H65 ground truth verdicts (from h70_summary.json)
H65_GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        (631, 669): "FOUNTAIN", (890, 936): "OTHER",
        (977, 1011): "FOUNTAIN", (1029, 1049): "OTHER",
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {
        (339, 374): "FOUNTAIN", (482, 594): "OTHER", (800, 861): "CASCADE",
    },
}

# H72 ground truth verdicts (the 1 CASCADE_3+ misclassification)
H72_GROUND_TRUTH = {
    "identical_balls_trick_000_018": {
        (685, 716): "MANIPULATION_TRICK_NOT_CASCADE",
    },
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": {},
}


def load_h40v2(stem: str) -> dict[int, tuple[int, int]]:
    """Load H40 v2 sustained-occupancy as frame -> (L40v2, R40v2)."""
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        f = int(row["frame"])
        l = int(row["L40v2"])
        r = int(row["R40v2"])
        out[f] = (l, r)
    return out


def load_pattern_phases(stem: str) -> list[dict]:
    """Load all substantial pattern phases from H50-filtered data."""
    p = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(p)):
        n = int(row["n_frames"])
        if n >= MIN_PHASE_FRAMES:
            out.append({
                "start": int(row["start_frame"]),
                "end": int(row["end_frame"]),
                "n": n,
                "pattern": row["pattern"],
                "conf": float(row["avg_confidence"]),
            })
    return out


def main() -> None:
    summary = {"videos": {}}
    print("H73 - H40 v2 sustained-occupancy as CASCADE_3+ / FOUNTAIN_3+ validator")
    print("=" * 80)

    all_phases = []
    for stem in STEMS:
        h40v2 = load_h40v2(stem)
        phases = load_pattern_phases(stem)
        print(f"\n=== {stem} ===")
        print(f"  H40v2 loaded: {len(h40v2)} frames")
        print(f"  Substantial phases: {len(phases)}")

        per_phase_records = []
        for ph in phases:
            if ph["pattern"] not in TARGET_PATTERNS:
                continue
            n_total = 0
            n_lr_both_pos = 0  # both hands occupied
            n_lr_one_pos = 0   # one hand occupied
            n_lr_both_zero = 0 # both hands empty
            sumL = 0
            sumR = 0
            for f in range(ph["start"], ph["end"] + 1):
                if f not in h40v2:
                    continue
                l, r = h40v2[f]
                n_total += 1
                sumL += l
                sumR += r
                if l > 0 and r > 0:
                    n_lr_both_pos += 1
                elif l > 0 or r > 0:
                    n_lr_one_pos += 1
                else:
                    n_lr_both_zero += 1
            if n_total == 0:
                continue
            meanL = sumL / n_total
            meanR = sumR / n_total
            meanLR = meanL + meanR
            pct_both_pos = n_lr_both_pos / n_total
            pct_one_pos = n_lr_one_pos / n_total
            pct_both_zero = n_lr_both_zero / n_total
            h65_v = H65_GROUND_TRUTH.get(stem, {}).get((ph["start"], ph["end"]), "N/A")
            h72_v = H72_GROUND_TRUTH.get(stem, {}).get((ph["start"], ph["end"]), "N/A")

            # Anomaly detection
            anomalies = []
            if meanL < 0.3:
                anomalies.append(f"LOW_L={meanL:.2f}")
            if meanR < 0.3:
                anomalies.append(f"LOW_R={meanR:.2f}")
            if meanLR < 0.5:
                anomalies.append(f"LOW_LR={meanLR:.2f}")
            if pct_both_zero > 0.2:
                anomalies.append(f"OFTTEN_BOTH_EMPTY={pct_both_zero:.2f}")

            record = {
                "stem": stem,
                "start": ph["start"],
                "end": ph["end"],
                "pattern": ph["pattern"],
                "n_frames": n_total,
                "mean_L40v2": round(meanL, 3),
                "mean_R40v2": round(meanR, 3),
                "mean_LR40v2": round(meanLR, 3),
                "pct_both_pos": round(pct_both_pos, 3),
                "pct_one_pos": round(pct_one_pos, 3),
                "pct_both_zero": round(pct_both_zero, 3),
                "conf": round(ph["conf"], 3),
                "h65_verdict": h65_v,
                "h72_verdict": h72_v,
                "anomalies": anomalies,
            }
            per_phase_records.append(record)
            all_phases.append(record)
            anom_str = " [" + ", ".join(anomalies) + "]" if anomalies else ""
            print(f"  {ph['pattern']:<13} f={ph['start']}-{ph['end']} "
                  f"n={n_total:3d} L={meanL:.2f} R={meanR:.2f} LR={meanLR:.2f} "
                  f"both+={pct_both_pos:.2f} both0={pct_both_zero:.2f} "
                  f"h65={h65_v} h72={h72_v}{anom_str}")
        summary["videos"][stem] = {
            "n_target_phases": len(per_phase_records),
            "phases": per_phase_records,
        }

    # Aggregate stats: compare H40v2 to H12 v8 verdicts
    print(f"\n=== Summary across both videos ===")
    n_total = len(all_phases)
    n_h40v2_anomalies = sum(1 for r in all_phases if r["anomalies"])
    print(f"  Total substantial CASCADE_3+ / FOUNTAIN_3+ phases: {n_total}")
    print(f"  Phases with H40v2 anomalies: {n_h40v2_anomalies}")
    # Compute H12 v8 accuracy on the H65 ground truth subset
    n_h12_correct = 0
    for r in all_phases:
        if r["h65_verdict"] in ("FOUNTAIN", "CASCADE"):
            # H12 v8 was correct if pattern matches
            if r["pattern"] == ("FOUNTAIN_3+" if r["h65_verdict"] == "FOUNTAIN" else "CASCADE_3+"):
                n_h12_correct += 1
    print(f"  H12 v8 correct (CASCADE_3+ / FOUNTAIN_3+ matching h65 ground truth): {n_h12_correct}")

    summary["all_phases"] = all_phases
    summary["stats"] = {
        "n_target_phases": n_total,
        "n_h40v2_anomalies": n_h40v2_anomalies,
        "h12_v8_correct_on_h65_sample": n_h12_correct,
    }
    out = H1_DATA / "h73_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
