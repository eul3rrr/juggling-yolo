#!/usr/bin/env python3
"""H39 v2 - refined FOUNTAIN_3+ post-filter using H36 timeline events
within a temporal window.

HYPOTHESIS:
  H39 v1 rejected FOUNTAIN_3+ frames where H36 per-frame (L, R, A) state
  was (0, 0, total). Visual QA showed this over-rejected ~50% of
  real FOUNTAIN/MIXED phases because H36 only sees chain events, not
  continuous hand-occupancy.

  H39 v2 hypothesis: rejecting FOUNTAIN_3+ PHASES (not frames) that have
  zero H36 timeline events within ±N frames of any phase frame is a
  better signal. A phase with no chain events is genuinely "floating"
  — neither hands nor chains captured the juggling activity.
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

# Window for H36 events
WINDOW = 0  # frames — check if there's an H36 CATCH/THROW at the phase boundary


def load_crossref(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h37_crossref_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            r["h12_confidence"] = float(r["h12_confidence"])
            rows.append(r)
    return rows


def load_h36_events(stem: str) -> set:
    """Return the set of frames with H36 CATCH/THROW events."""
    fname = (H1_DATA / f"h36_timeline_{stem}.csv")
    events = set()
    with fname.open() as fh:
        for r in csv.DictReader(fh):
            if r["event_type"] in ("CATCH", "THROW"):
                events.add(int(r["frame"]))
    return events


def find_fountain_phases(rows: list[dict], min_n: int = 5) -> list[dict]:
    """Find FOUNTAIN_3+ phases (>= min_n frames)."""
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


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H39 v2: phase-level FOUNTAIN_3+ rejection) ===")
        rows = load_crossref(stem)
        if not rows:
            continue
        events = load_h36_events(stem)
        print(f"  H36 events (CATCH/THROW): {len(events)}")
        phases = find_fountain_phases(rows, min_n=5)
        print(f"  FOUNTAIN_3+ phases (>= 5 frames): {len(phases)}")

        # For each phase, check if any frame in the phase has an H36 event
        # within WINDOW. A phase is rejected if no event is found.
        rejected_phases = []
        kept_phases = []
        for ph in phases:
            has_event = False
            for f in range(ph["start"], ph["end"] + 1):
                for w in range(-WINDOW, WINDOW + 1):
                    if (f + w) in events:
                        has_event = True
                        break
                if has_event:
                    break
            ph["has_h36_event"] = has_event
            if has_event:
                kept_phases.append(ph)
            else:
                rejected_phases.append(ph)

        # Apply phase-level filter: any frame in a rejected phase is
        # marked FOUNTAIN_REJECTED. Frames in kept phases are unchanged.
        rejected_phase_set = set()
        for ph in rejected_phases:
            for f in range(ph["start"], ph["end"] + 1):
                rejected_phase_set.add(f)

        out_rows = []
        for r in rows:
            new_r = dict(r)
            if r["h12_pattern"] == "FOUNTAIN_3+" and r["frame"] in rejected_phase_set:
                new_r["h39v2_pattern"] = "FOUNTAIN_REJECTED"
            else:
                new_r["h39v2_pattern"] = r["h12_pattern"]
            out_rows.append(new_r)

        # Count
        before = defaultdict(int)
        after = defaultdict(int)
        for r in rows:
            before[r["h12_pattern"]] += 1
        for r in out_rows:
            after[r["h39v2_pattern"]] += 1
        print(f"  pattern distribution before:")
        for p, c in sorted(before.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")
        print(f"  pattern distribution after H39 v2 filter:")
        for p, c in sorted(after.items(), key=lambda x: -x[1]):
            print(f"    {p}: {c}")

        print(f"  phase-level summary:")
        print(f"    rejected phases: {len(rejected_phases)} (n_frames={sum(p['n'] for p in rejected_phases)})")
        print(f"    kept phases: {len(kept_phases)} (n_frames={sum(p['n'] for p in kept_phases)})")
        for ph in rejected_phases:
            print(f"      REJECT f={ph['start']}-{ph['end']} n={ph['n']}")
        for ph in kept_phases:
            print(f"      KEEP   f={ph['start']}-{ph['end']} n={ph['n']}")

        # Write outputs
        out_csv = H1_DATA / f"h39v2_filtered_{stem}.csv"
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
            "n_phases_rejected": len(rejected_phases),
            "n_phases_kept": len(kept_phases),
            "rejected_phases": [
                {"start": p["start"], "end": p["end"], "n": p["n"]}
                for p in rejected_phases
            ],
            "kept_phases": [
                {"start": p["start"], "end": p["end"], "n": p["n"]}
                for p in kept_phases
            ],
        }

    out = H1_DATA / "h39v2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
