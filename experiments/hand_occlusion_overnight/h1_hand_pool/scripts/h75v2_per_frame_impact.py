#!/usr/bin/env python3
"""H75 v2 - per-frame end-to-end impact of H75 stacked FOUNTAIN_3+ post-filter.

Apply the H75 stacked filter to the H50-filtered per-frame pattern data
and measure the impact on per-frame FOUNTAIN_3+ classifications.

Stack: (H43 conf < 0.55) OR (H69 spec_conc < 0.15) OR (H74 LR_var < 0.20)

Compare with H43 alone and H43 + H69.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Thresholds
H43_CONF_THR = 0.55
H69_SPEC_CONC_THR = 0.15
H74_LR_VAR_THR = 0.20

# Per-phase info for the 7 FOUNTAIN_3+ phases (from H65 + H72/H73)
# Tuple: (stem, start, end, conf, spec_conc, lr_var, h65_verdict, label)
PHASE_INFO = []


def load_h69_phases(stem: str) -> dict[tuple[int, int], dict]:
    p = H1_DATA / f"h69_phases_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        s = int(row["phase_start"])
        e = int(row["phase_end"])
        out[(s, e)] = {
            "conf": float(row["mean_confidence"]),
            "spec_conc": float(row["spectral_concentration"]),
        }
    return out


def load_h70_phases(stem: str) -> dict[tuple[int, int], dict]:
    """Load H70 phases (includes CASCADE_3+)."""
    p = H1_DATA / f"h70_phases_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        s = int(row["phase_start"])
        e = int(row["phase_end"])
        out[(s, e)] = {
            "pattern": row["pattern"],
            "conf": float(row["mean_confidence"]),
            "spec_conc": float(row["spectral_concentration"]),
        }
    return out


def load_h40v2(stem: str) -> dict[int, tuple[int, int]]:
    p = H1_DATA / f"h40v2_continuous_{stem}.csv"
    out = {}
    for row in csv.DictReader(open(p)):
        f = int(row["frame"])
        l = int(row["L40v2"])
        r = int(row["R40v2"])
        out[f] = (l, r)
    return out


def compute_lr_var(h40v2: dict[int, tuple[int, int]], start: int, end: int) -> float:
    LR_series = []
    for f in range(start, end + 1):
        if f not in h40v2:
            continue
        l, r = h40v2[f]
        LR_series.append(l + r)
    if len(LR_series) < 2:
        return 0.0
    return statistics.variance(LR_series)


def main() -> None:
    summary = {"videos": {}}
    print("H75 v2 - per-frame end-to-end impact of H75 stacked FOUNTAIN_3+ post-filter")
    print("=" * 80)

    # Per-pattern frame counts (H50-filtered data)
    pattern_counts = defaultdict(lambda: defaultdict(int))

    for stem in STEMS:
        h50_p = H1_DATA / f"pattern_phases_h50_{stem}.csv"
        h69 = load_h69_phases(stem)
        h70 = load_h70_phases(stem)
        h40v2 = load_h40v2(stem)

        # For each phase in H50, compute filter decisions
        per_phase_filter = []
        for row in csv.DictReader(open(h50_p)):
            s = int(row["start_frame"])
            e = int(row["end_frame"])
            n = int(row["n_frames"])
            pattern = row["pattern"]
            conf = float(row["avg_confidence"])

            # Get spec_conc and LR_var for this phase
            if (s, e) in h70:
                spec_conc = h70[(s, e)]["spec_conc"]
            elif (s, e) in h69:
                spec_conc = h69[(s, e)]["spec_conc"]
            else:
                spec_conc = 1.0  # default: high (don't reject)
            lr_var = compute_lr_var(h40v2, s, e)

            h43_rej = conf < H43_CONF_THR
            h69_rej = spec_conc < H69_SPEC_CONC_THR
            h74_rej = lr_var < H74_LR_VAR_THR
            stacked_rej = h43_rej or h69_rej or h74_rej
            h4369_rej = h43_rej or h69_rej  # H43 + H69 (no H74)

            per_phase_filter.append({
                "start": s,
                "end": e,
                "n": n,
                "pattern": pattern,
                "conf": conf,
                "spec_conc": spec_conc,
                "lr_var": lr_var,
                "h43_rej": h43_rej,
                "h69_rej": h69_rej,
                "h74_rej": h74_rej,
                "stacked_rej": stacked_rej,
                "h4369_rej": h4369_rej,
            })
            if pattern == "FOUNTAIN_3+" and stacked_rej:
                print(f"  REJECT: {stem[:15]} f={s}-{e} ({pattern}, n={n}) "
                      f"conf={conf:.3f} conc={spec_conc:.3f} var={lr_var:.3f}")

        # Aggregate per-pattern frame changes
        n_total = 0
        n_h43 = 0
        n_h4369 = 0
        n_stacked = 0
        for pf in per_phase_filter:
            if pf["pattern"] == "FOUNTAIN_3+":
                n_total += pf["n"]
                if pf["h43_rej"]:
                    n_h43 += pf["n"]
                if pf["h4369_rej"]:
                    n_h4369 += pf["n"]
                if pf["stacked_rej"]:
                    n_stacked += pf["n"]

        print(f"\n  {stem}:")
        print(f"    FOUNTAIN_3+ total frames: {n_total}")
        print(f"    H43 reject: {n_h43} ({n_h43/n_total*100:.1f}%)" if n_total else "")
        print(f"    H43+H69 reject: {n_h4369} ({n_h4369/n_total*100:.1f}%)" if n_total else "")
        print(f"    H43+H69+H74 stacked reject: {n_stacked} ({n_stacked/n_total*100:.1f}%)" if n_total else "")

        summary["videos"][stem] = {
            "n_fountain_total": n_total,
            "n_fountain_h43_rejected": n_h43,
            "n_fountain_h4369_rejected": n_h4369,
            "n_fountain_stacked_rejected": n_stacked,
            "per_phase": per_phase_filter,
        }

    out = H1_DATA / "h75v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
