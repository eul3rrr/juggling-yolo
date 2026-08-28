#!/usr/bin/env python3
"""H69 v2 - Per-frame end-to-end impact of H43 OR H69 stacked post-filter.

Computes the per-frame pattern distribution change when applying the
H43 OR H69(spec_conc < 0.15) filter to the H50-filtered pattern data.

Mark FOUNTAIN_3+ frames as FOUNTAIN_LOW_CONF if either filter rejects
the phase the frame belongs to.

Output:
  - data/h69v2_per_frame_*.csv (per-frame pattern labels with H69 filter)
  - data/h69v2_pattern_dist_*.json (per-frame pattern distribution)
  - data/h69v2_summary.json
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H43 + H69 thresholds
H43_CONF_THRESHOLD = 0.55
H69_SPEC_CONC_THRESHOLD = 0.15


def load_h69_rejected_phases(stem: str) -> set[tuple[int, int]]:
    """Load phases rejected by H69 (i.e., where H43 OR H69 fires)."""
    p = H1_DATA / f"h69_phases_{stem}.csv"
    rejected = set()
    for row in csv.DictReader(open(p)):
        if row["h69_rejected"] == "True":
            rejected.add((int(row["phase_start"]), int(row["phase_end"])))
    return rejected


def load_h43_rejected_phases(stem: str) -> set[tuple[int, int]]:
    """Load phases rejected by H43 (conf < 0.55)."""
    p = H1_DATA / f"h69_phases_{stem}.csv"
    rejected = set()
    for row in csv.DictReader(open(p)):
        if float(row["mean_confidence"]) < H43_CONF_THRESHOLD:
            rejected.add((int(row["phase_start"]), int(row["phase_end"])))
    return rejected


def main() -> None:
    summary = {"videos": {}}

    for stem in STEMS:
        print(f"\n=== {stem} ===")
        h43_rej = load_h43_rejected_phases(stem)
        h69_rej = load_h69_rejected_phases(stem)
        stacked_rej = h43_rej | h69_rej
        print(f"  H43 rejected phases: {len(h43_rej)}")
        print(f"  H69 rejected phases: {len(h69_rej)}")
        print(f"  H43 OR H69 rejected: {len(stacked_rej)}")

        # Load H50-filtered per-frame data
        pattern_in_path = H1_DATA / f"pattern_inference_h50_{stem}.csv"
        per_frame_out = []
        pattern_counts = defaultdict(int)
        pattern_counts_modified = defaultdict(int)
        n_total = 0
        n_changed = 0
        for row in csv.DictReader(open(pattern_in_path)):
            f = int(row["frame"])
            pattern = row["pattern"]
            conf = float(row["confidence"])
            n_total += 1
            pattern_counts[pattern] += 1

            # Determine if this frame is in a H43-or-H69-rejected phase
            in_rejected = False
            for (ps, pe) in stacked_rej:
                if ps <= f <= pe:
                    in_rejected = True
                    break

            # Determine if frame was FOUNTAIN_3+
            new_pattern = pattern
            if pattern == "FOUNTAIN_3+" and in_rejected:
                new_pattern = "FOUNTAIN_LOW_CONF"
                n_changed += 1
            pattern_counts_modified[new_pattern] += 1

            per_frame_out.append({
                "frame": f,
                "pattern": pattern,
                "confidence": conf,
                "new_pattern": new_pattern,
            })

        # Per-frame CSV
        out_pf = H1_DATA / f"h69v2_per_frame_{stem}.csv"
        with out_pf.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["frame", "pattern", "confidence", "new_pattern"])
            w.writeheader()
            w.writerows(per_frame_out)
        print(f"  wrote: {out_pf.name}")

        # Pattern distribution
        print(f"  per-frame changes: {n_changed}/{n_total} ({100*n_changed/n_total:.1f}%)")
        print(f"  pattern distribution (before):")
        for p, c in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c} ({100*c/n_total:.1f}%)")
        print(f"  pattern distribution (after H43 OR H69):")
        for p, c in sorted(pattern_counts_modified.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c} ({100*c/n_total:.1f}%)")

        # JSON
        summary["videos"][stem] = {
            "n_total": n_total,
            "n_changed": n_changed,
            "pct_changed": round(100 * n_changed / n_total, 3),
            "h43_rejected_phases": sorted(list(h43_rej)),
            "h69_rejected_phases": sorted(list(h69_rej)),
            "stacked_rejected_phases": sorted(list(stacked_rej)),
            "before": dict(pattern_counts),
            "after": dict(pattern_counts_modified),
        }

    summary["methodology"] = {
        "filter": "h69v2: H43 OR H69(spec_conc < 0.15) on H50-filtered pattern data",
        "H43_CONF_THRESHOLD": H43_CONF_THRESHOLD,
        "H69_SPEC_CONC_THRESHOLD": H69_SPEC_CONC_THRESHOLD,
    }
    out = H1_DATA / "h69v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
