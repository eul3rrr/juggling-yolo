#!/usr/bin/env python3
"""H41 - FOUNTAIN_3+ post-filter using H40 v2 sustained hand-occupancy.

HYPOTHESIS:
  H39 v1/v2 over-rejected real FOUNTAIN_3+ because H36 chain-driven
  state is too sparse. H40 v2 provides continuous sustained hand-
  occupancy. Question: does H40 v2-based FOUNTAIN_3+ post-filter
  produce better precision than H39 v1/v2?

ALGORITHM:
  For each FOUNTAIN_3+ phase (>= 5 frames):
  - If H40 v2 shows <50% sustained hand-occupancy in the phase,
    mark as FOUNTAIN_REJECTED.
  - Also: if H40 v2 shows >50% BOTH-hands-occupied in the phase,
    mark as FOUNTAIN_REJECTED (FOUNTAIN = single-hand dominant,
    not both-hands).
  - Combine both criteria.

EXPECTED:
  Better precision than H39 v1 (20%) and H39 v2 (50%).
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

# H41 thresholds
MIN_OCC_RATE = 0.20  # need at least 20% sustained occupancy
MAX_BOTH_HANDS_RATE = 0.50  # need at most 50% both-hands-occupied


def find_fountain_phases(rows: list[dict], min_n: int = 5) -> list[dict]:
    """Find FOUNTAIN_3+ phases (>= min_n frames) from h40v2 data."""
    phases = []
    cur_start = None
    for r in rows:
        p = r["h12_pattern"]
        if p == "FOUNTAIN_3+":
            if cur_start is None:
                cur_start = r["frame"]
        else:
            if cur_start is not None:
                n = r["frame"] - cur_start
                if n >= min_n:
                    phases.append({"start": cur_start, "end": r["frame"] - 1,
                                   "n": n})
                cur_start = None
    if cur_start is not None:
        n = rows[-1]["frame"] - cur_start + 1
        if n >= min_n:
            phases.append({"start": cur_start, "end": rows[-1]["frame"],
                           "n": n})
    return phases


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H41: FOUNTAIN_3+ post-filter via H40 v2) ===")
        rows = []
        with (H1_DATA / f"h40v2_continuous_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                r["frame"] = int(r["frame"])
                r["L40v2"] = int(r["L40v2"])
                r["R40v2"] = int(r["R40v2"])
                rows.append(r)
        if not rows:
            continue

        phases = find_fountain_phases(rows, min_n=5)
        print(f"  FOUNTAIN_3+ phases (>=5 frames): {len(phases)}")

        # For each phase, compute occ_rate and both_hands_rate
        rejected = []
        kept = []
        for ph in phases:
            n_occ = 0
            n_both = 0
            n_total = 0
            for r in rows:
                if ph["start"] <= r["frame"] <= ph["end"] and r["h12_pattern"] == "FOUNTAIN_3+":
                    n_total += 1
                    if r["L40v2"] > 0 or r["R40v2"] > 0:
                        n_occ += 1
                    if r["L40v2"] > 0 and r["R40v2"] > 0:
                        n_both += 1
            if n_total == 0:
                continue
            occ_rate = n_occ / n_total
            both_rate = n_both / n_total
            ph["occ_rate"] = occ_rate
            ph["both_rate"] = both_rate
            # H41 rejection criteria
            if occ_rate < MIN_OCC_RATE:
                ph["reject_reason"] = f"low_occ_rate={occ_rate:.2f}"
                rejected.append(ph)
            elif both_rate > MAX_BOTH_HANDS_RATE:
                ph["reject_reason"] = f"high_both_rate={both_rate:.2f}"
                rejected.append(ph)
            else:
                ph["reject_reason"] = None
                kept.append(ph)

        print(f"  Rejected: {len(rejected)} phases")
        for ph in rejected:
            print(f"    REJECT f={ph['start']}-{ph['end']} n={ph['n']} "
                  f"occ={ph['occ_rate']:.2f} both={ph['both_rate']:.2f} "
                  f"reason={ph['reject_reason']}")
        print(f"  Kept: {len(kept)} phases")
        for ph in kept:
            print(f"    KEEP   f={ph['start']}-{ph['end']} n={ph['n']} "
                  f"occ={ph['occ_rate']:.2f} both={ph['both_rate']:.2f}")

        # Apply to per-frame data
        rejected_phase_set = set()
        for ph in rejected:
            for f in range(ph["start"], ph["end"] + 1):
                rejected_phase_set.add(f)
        out_rows = []
        for r in rows:
            new_r = dict(r)
            if r["h12_pattern"] == "FOUNTAIN_3+" and r["frame"] in rejected_phase_set:
                new_r["h41_pattern"] = "FOUNTAIN_REJECTED"
            else:
                new_r["h41_pattern"] = r["h12_pattern"]
            out_rows.append(new_r)

        # Count
        before = defaultdict(int)
        after = defaultdict(int)
        for r in rows:
            before[r["h12_pattern"]] += 1
        for r in out_rows:
            after[r["h41_pattern"]] += 1
        print(f"\n  pattern distribution before:")
        for p, c in sorted(before.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")
        print(f"  pattern distribution after H41 filter:")
        for p, c in sorted(after.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")

        # Write outputs
        out_csv = H1_DATA / f"h41_filtered_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(out_rows[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(out_rows)
        print(f"  wrote: {out_csv.name} ({len(out_rows)} rows)")

        summary["videos"][stem] = {
            "n_fountain_before": before.get("FOUNTAIN_3+", 0),
            "n_fountain_rejected": after.get("FOUNTAIN_REJECTED", 0),
            "n_fountain_kept": after.get("FOUNTAIN_3+", 0),
            "n_phases_total": len(phases),
            "n_phases_rejected": len(rejected),
            "n_phases_kept": len(kept),
            "rejected_phases": [
                {"start": p["start"], "end": p["end"], "n": p["n"],
                 "occ_rate": round(p["occ_rate"], 2),
                 "both_rate": round(p["both_rate"], 2),
                 "reason": p["reject_reason"]}
                for p in rejected
            ],
            "kept_phases": [
                {"start": p["start"], "end": p["end"], "n": p["n"],
                 "occ_rate": round(p["occ_rate"], 2),
                 "both_rate": round(p["both_rate"], 2)}
                for p in kept
            ],
        }

    out = H1_DATA / "h41_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
