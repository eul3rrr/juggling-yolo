#!/usr/bin/env python3
"""H38 - post-filter CASCADE_3+ using H36 hand-occupancy as precision
improvement.

HYPOTHESIS:
  H37 showed that CASCADE_3+ frames have hand-occupancy support
  (20/22 identical CASCADE_3+ are H36 state (0, 1, 2)). A small
  fraction of CASCADE_3+ frames have NO hand-occupancy (H36 state
  (0, 0, 3)) — these are likely H12 v8 misclassifications.

  Question: does rejecting CASCADE_3+ classifications where H36
  has no hand-occupancy improve the pattern classification
  precision?

EXPECTED:
  - 1-3% of CASCADE_3+ frames on identical have H36 state (0, 0, 3)
  - 12 of 129 CASCADE_3+ frames on YouTube have H36 state (0, 0, 5)
  - Rejecting these should improve precision but may lose some
    valid CASCADE_3+ classifications (because H36 only sees the
    chain events, not the full hand-occupancy picture)

ALGORITHM:
  1. Load H37 crossref data.
  2. For each CASCADE_3+ frame, check H36 (L, R, A) state.
  3. If state is (0, 0, 3) or (0, 0, 5) (no hand occupancy),
     mark the frame as CASCADE_REJECTED.
  4. Compare phase distribution before/after filter.
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


def load_crossref(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h37_crossref_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            r["h12_n_total"] = int(r["h12_n_total"])
            r["h12_confidence"] = float(r["h12_confidence"])
            rows.append(r)
    return rows


def post_filter(rows: list[dict], total_balls: int) -> list[dict]:
    """Reject CASCADE_3+ classifications where H36 has no
    hand-occupancy evidence (L=R=0)."""
    out = []
    for r in rows:
        new_pattern = r["h12_pattern"]
        rejected = False
        if r["h12_pattern"] == "CASCADE_3+" and r["L"] == 0 and r["R"] == 0:
            new_pattern = "CASCADE_REJECTED"
            rejected = True
        new_r = dict(r)
        new_r["h38_pattern"] = new_pattern
        new_r["h38_rejected"] = rejected
        out.append(new_r)
    return out


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H38: post-filter CASCADE_3+ via H36) ===")
        rows = load_crossref(stem)
        if not rows:
            continue

        # Count CASCADE_3+ by H36 state
        cascade_states = defaultdict(int)
        for r in rows:
            if r["h12_pattern"] == "CASCADE_3+":
                cascade_states[(r["L"], r["R"], r["A"])] += 1
        print(f"  CASCADE_3+ state distribution (before filter):")
        for (L, R, A), c in sorted(cascade_states.items(), key=lambda x: -x[1]):
            print(f"    L={L} R={R} A={A}: {c}")

        # Identify rejected frames
        rejected = [r for r in rows if r["h12_pattern"] == "CASCADE_3+"
                    and r["L"] == 0 and r["R"] == 0]
        print(f"  CASCADE_3+ to be rejected: {len(rejected)}")
        for r in rejected:
            print(f"    f={r['frame']} state=({r['L']}, {r['R']}, {r['A']}) "
                  f"h12_conf={r['h12_confidence']:.3f}")

        # Apply filter
        total_balls = max(r["h12_n_total"] for r in rows)
        filtered = post_filter(rows, total_balls)

        # Pattern distribution before/after
        before = defaultdict(int)
        after = defaultdict(int)
        for r in rows:
            before[r["h12_pattern"]] += 1
        for r in filtered:
            after[r["h38_pattern"]] += 1
        print(f"  pattern distribution before:")
        for p, c in sorted(before.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")
        print(f"  pattern distribution after H38 filter:")
        for p, c in sorted(after.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")

        # Phase detection
        # Count CASCADE phases (>= 20 consecutive frames) before/after
        before_cascade_phases = count_phases(rows, "CASCADE_3+")
        after_cascade_phases = count_phases(filtered, "CASCADE_3+")
        print(f"  CASCADE phases (>= 20 frames): "
              f"before={len(before_cascade_phases)}, after={len(after_cascade_phases)}")
        for p in before_cascade_phases:
            print(f"    before: f={p['start']}-{p['end']} n={p['n']}")
        for p in after_cascade_phases:
            print(f"    after:  f={p['start']}-{p['end']} n={p['n']}")

        # Write outputs
        out_csv = H1_DATA / f"h38_filtered_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(filtered[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(filtered)
        print(f"  wrote: {out_csv.name} ({len(filtered)} rows)")

        summary["videos"][stem] = {
            "n_cascade_before": before.get("CASCADE_3+", 0),
            "n_cascade_rejected": len(rejected),
            "n_cascade_after": after.get("CASCADE_3+", 0),
            "pct_rejected": round(100 * len(rejected) /
                                  max(1, before.get("CASCADE_3+", 0)), 1),
            "before_cascade_phases": len(before_cascade_phases),
            "after_cascade_phases": len(after_cascade_phases),
        }

    out = H1_DATA / "h38_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


def count_phases(rows: list[dict], pattern: str, min_n: int = 20) -> list[dict]:
    """Find consecutive runs of `pattern` with >= min_n frames."""
    out = []
    in_phase = False
    start = None
    for r in rows:
        matches = (r.get("h12_pattern", "") == pattern
                   if "h12_pattern" in r
                   else r.get("h38_pattern", "") == pattern)
        if matches and not in_phase:
            in_phase = True
            start = r["frame"]
        elif not matches and in_phase:
            in_phase = False
            n = r["frame"] - start
            if n >= min_n:
                out.append({"start": start, "end": r["frame"] - 1, "n": n})
    if in_phase:
        last = rows[-1]["frame"]
        n = last - start + 1
        if n >= min_n:
            out.append({"start": start, "end": last, "n": n})
    return out


if __name__ == "__main__":
    main()
