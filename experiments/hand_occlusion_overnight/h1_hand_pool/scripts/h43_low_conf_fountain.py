#!/usr/bin/env python3
"""H43 - H12 v8 confidence-based FOUNTAIN_3+ filter.

HYPOTHESIS:
  H12 v8 confidence for FOUNTAIN_3+ ranges from 0.463 to 0.844 on
  identical and 0.629-0.649 on YouTube. H39 visual QA found:
  - f=1029-1060 (conf 0.463) is OTHER (2-ball exercise) - REJECT
  - f=977-1011 (conf 0.565) is OTHER (hold trick) - REJECT
  - f=263-312, 411-449, 631-669 (conf 0.7+) are real - KEEP

  Question: does filtering FOUNTAIN_3+ with H12 v8 confidence
  < 0.55 produce a useful precision improvement?

ALGORITHM:
  For each FOUNTAIN_3+ frame with H12 v8 confidence < THRESHOLD,
  mark as FOUNTAIN_LOW_CONF.
  Compare with H39 v2 and H41 v2 results.
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


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H43: H12 v8 confidence-based FOUNTAIN_3+ filter) ===")
        rows = []
        with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                r["frame"] = int(r["frame"])
                r["confidence"] = float(r["confidence"])
                rows.append(r)

        # Count FOUNTAIN_3+ by confidence bin
        n_total = sum(1 for r in rows if r["pattern"] == "FOUNTAIN_3+")
        n_low = sum(1 for r in rows if r["pattern"] == "FOUNTAIN_3+" and r["confidence"] < 0.55)
        n_mid = sum(1 for r in rows if r["pattern"] == "FOUNTAIN_3+" and 0.55 <= r["confidence"] < 0.70)
        n_high = sum(1 for r in rows if r["pattern"] == "FOUNTAIN_3+" and r["confidence"] >= 0.70)
        print(f"  FOUNTAIN_3+ total: {n_total}")
        print(f"  low (<0.55): {n_low}")
        print(f"  mid (0.55-0.70): {n_mid}")
        print(f"  high (>=0.70): {n_high}")

        # Apply filter: reject FOUNTAIN_3+ with conf < 0.55
        out_rows = []
        for r in rows:
            new_r = dict(r)
            if r["pattern"] == "FOUNTAIN_3+" and r["confidence"] < 0.55:
                new_r["h43_pattern"] = "FOUNTAIN_LOW_CONF"
            else:
                new_r["h43_pattern"] = r["pattern"]
            out_rows.append(new_r)

        # Count
        before = defaultdict(int)
        after = defaultdict(int)
        for r in rows:
            before[r["pattern"]] += 1
        for r in out_rows:
            after[r["h43_pattern"]] += 1
        print(f"\n  pattern distribution before:")
        for p, c in sorted(before.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")
        print(f"  pattern distribution after H43 filter (rejects <0.55):")
        for p, c in sorted(after.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")

        # Write outputs
        out_csv = H1_DATA / f"h43_filtered_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(out_rows[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(out_rows)
        print(f"  wrote: {out_csv.name} ({len(out_rows)} rows)")

        summary["videos"][stem] = {
            "n_fountain_total": n_total,
            "n_low_conf": n_low,
            "n_mid_conf": n_mid,
            "n_high_conf": n_high,
            "n_fountain_after": after.get("FOUNTAIN_3+", 0),
            "n_fountain_rejected": after.get("FOUNTAIN_LOW_CONF", 0),
        }

    out = H1_DATA / "h43_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
