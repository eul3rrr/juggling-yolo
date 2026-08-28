#!/usr/bin/env python3
"""H39 - post-filter FOUNTAIN_3+ using H36 hand-occupancy as precision
improvement (analog of H38 for CASCADE_3+).

HYPOTHESIS:
  H37 found that FOUNTAIN_3+ frames on identical have very low
  hand-occupancy support (5/288 = 1.7% have L+R > 0). The H12 v8
  FOUNTAIN_3+ classification is based on event-log density, not on
  hand-occupancy, so when the event log is sparse in the late phase,
  H12 v8 produces sustained FOUNTAIN_3+ blocks (e.g. f=890-1050)
  with NO hand-occupancy evidence. These are likely H12 v8
  misclassifications.

  Question: does rejecting FOUNTAIN_3+ classifications where H36
  has no hand-occupancy evidence improve the pattern classification
  precision on the late phase?

EXPECTED:
  - identical: ~98% of FOUNTAIN_3+ frames have H36 state (0, 0, 3)
    (no hand occupancy). These are mostly sustained late-phase blocks.
  - YouTube: ~85% of FOUNTAIN_3+ frames have H36 state (0, 0, 5)
  - Rejecting these should reduce FOUNTAIN_3+ count substantially,
    but the H12 v8 fundamental CASCADE/FOUNTAIN ambiguity remains.

ALGORITHM:
  1. Load H37 crossref data.
  2. For each FOUNTAIN_3+ frame, check H36 (L, R, A) state.
  3. If state is (0, 0, total) (no hand occupancy) AND pattern is
     FOUNTAIN_3+, mark the frame as FOUNTAIN_REJECTED.
  4. Compare phase distribution and FOUNTAIN phases before/after.
  5. Compare with H38 (CASCADE rejection) to see how the two
     interact (do they overlap?).

OUTPUTS:
  - h39_filtered_<stem>.csv: per-frame pattern with h39_pattern
  - h39_summary.json: counts before/after for both videos
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


def post_filter(rows: list[dict]) -> list[dict]:
    """Reject FOUNTAIN_3+ classifications where H36 has no
    hand-occupancy evidence (L=R=0)."""
    out = []
    for r in rows:
        new_pattern = r["h12_pattern"]
        rejected = False
        if r["h12_pattern"] == "FOUNTAIN_3+" and r["L"] == 0 and r["R"] == 0:
            new_pattern = "FOUNTAIN_REJECTED"
            rejected = True
        new_r = dict(r)
        new_r["h39_pattern"] = new_pattern
        new_r["h39_rejected"] = rejected
        out.append(new_r)
    return out


def count_phases(rows: list[dict], pattern_key: str, pattern: str,
                 min_n: int = 20) -> list[dict]:
    """Find consecutive runs of `pattern` with >= min_n frames."""
    out = []
    in_phase = False
    start = None
    for r in rows:
        matches = (r.get(pattern_key, "") == pattern)
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


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H39: post-filter FOUNTAIN_3+ via H36) ===")
        rows = load_crossref(stem)
        if not rows:
            continue

        # Count FOUNTAIN_3+ by H36 state
        fountain_states = defaultdict(int)
        for r in rows:
            if r["h12_pattern"] == "FOUNTAIN_3+":
                fountain_states[(r["L"], r["R"], r["A"])] += 1
        print(f"  FOUNTAIN_3+ state distribution (before filter):")
        for (L, R, A), c in sorted(fountain_states.items(), key=lambda x: -x[1]):
            print(f"    L={L} R={R} A={A}: {c}")

        # Identify rejected frames (by H36 no-occupancy)
        rejected_no_occ = [r for r in rows if r["h12_pattern"] == "FOUNTAIN_3+"
                           and r["L"] == 0 and r["R"] == 0]
        # Identify kept frames (with hand-occupancy)
        kept_with_occ = [r for r in rows if r["h12_pattern"] == "FOUNTAIN_3+"
                         and (r["L"] > 0 or r["R"] > 0)]
        print(f"  FOUNTAIN_3+ total: {len(rejected_no_occ) + len(kept_with_occ)}")
        print(f"  FOUNTAIN_3+ rejected (no hand occupancy): {len(rejected_no_occ)}")
        print(f"  FOUNTAIN_3+ kept (with hand occupancy): {len(kept_with_occ)}")

        # Apply filter
        filtered = post_filter(rows)

        # Pattern distribution before/after
        before = defaultdict(int)
        after = defaultdict(int)
        for r in rows:
            before[r["h12_pattern"]] += 1
        for r in filtered:
            after[r["h39_pattern"]] += 1
        print(f"  pattern distribution before:")
        for p, c in sorted(before.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")
        print(f"  pattern distribution after H39 filter:")
        for p, c in sorted(after.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")

        # Phase detection
        before_phases = count_phases(rows, "h12_pattern", "FOUNTAIN_3+", min_n=5)
        after_phases = count_phases(filtered, "h39_pattern", "FOUNTAIN_3+", min_n=5)
        print(f"  FOUNTAIN phases (>= 5 frames):")
        print(f"    before: {len(before_phases)} phases")
        for p in before_phases:
            mean_conf = sum(float(r["h12_confidence"]) for r in rows
                            if p["start"] <= r["frame"] <= p["end"]
                            and r["h12_pattern"] == "FOUNTAIN_3+") / p["n"]
            print(f"      f={p['start']}-{p['end']} (n={p['n']}) mean_conf={mean_conf:.3f}")
        print(f"    after:  {len(after_phases)} phases")
        for p in after_phases:
            print(f"      f={p['start']}-{p['end']} (n={p['n']})")

        # Compare with H38 (CASCADE rejection) to see overlap
        cascade_rejected = sum(1 for r in rows if r["h12_pattern"] == "CASCADE_3+"
                               and r["L"] == 0 and r["R"] == 0)
        fountain_rejected = len(rejected_no_occ)
        # In H38 output, CASCADE_REJECTED frames; in H39, FOUNTAIN_REJECTED
        # Do they overlap? (No: pattern is either CASCADE or FOUNTAIN, not both)
        # But check: are any frames BOTH CASCADE_3+ with no-occupancy AND
        # have FOUNTAIN_3+ somewhere nearby? Just curiosity
        print(f"  Cross-check with H38 (CASCADE rejection):")
        print(f"    CASCADE rejected: {cascade_rejected}")
        print(f"    FOUNTAIN rejected: {fountain_rejected}")
        print(f"    Combined rejected: {cascade_rejected + fountain_rejected}")

        # Write outputs
        out_csv = H1_DATA / f"h39_filtered_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(filtered[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(filtered)
        print(f"  wrote: {out_csv.name} ({len(filtered)} rows)")

        summary["videos"][stem] = {
            "n_fountain_before": before.get("FOUNTAIN_3+", 0),
            "n_fountain_rejected": len(rejected_no_occ),
            "n_fountain_kept": len(kept_with_occ),
            "n_fountain_after": after.get("FOUNTAIN_3+", 0),
            "pct_fountain_rejected": round(100 * len(rejected_no_occ) /
                                           max(1, before.get("FOUNTAIN_3+", 0)), 1),
            "n_fountain_phases_before": len(before_phases),
            "n_fountain_phases_after": len(after_phases),
            "n_cascade_rejected": cascade_rejected,
            "n_combined_rejected": cascade_rejected + fountain_rejected,
        }

    out = H1_DATA / "h39_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
