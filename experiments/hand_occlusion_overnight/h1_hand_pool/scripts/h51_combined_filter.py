#!/usr/bin/env python3
"""H51: H12 v8 + H50 10-frame filter + H43 FOUNTAIN confidence filter.

HYPOTHESIS:
  H50 closes H49's negative result: 10-frame filter has real
  downstream impact of 1.0% identical / 0.0% YouTube pattern label
  changes. H43 is a separate filter that rejects FOUNTAIN_3+
  classifications where H12 v8 confidence < 0.55 (precision 100%
  on H39 visual QA, 9.1% of FOUNTAIN_3+ frames on identical).

  Question: do H50 (event-log filter) and H43 (confidence filter)
  compose cleanly? Specifically:
  - Does the H50-filtered event log change the H12 v8 confidences
    for the FOUNTAIN_3+ frames that H43 would reject?
  - Does the H50 + H43 combined filter reject more or fewer
    FOUNTAIN_3+ frames than H43 alone?
  - Does the H50 + H43 combination break any substantial phases?

  The expected answer: H50 changes 1.0% of identical frames and
  0% of YouTube frames, so the H50 + H43 combination should be
  very similar to H43 alone, possibly with small improvements
  in cases where H50's pattern change happens to push a borderline
  FOUNTAIN_3+ frame into MIXED_3+ (where H43 wouldn't apply).

METHOD:
  1. Load H50 filtered pattern_inference (H12 v8 + 10-frame filter).
  2. Apply H43's confidence < 0.55 filter to FOUNTAIN_3+ frames.
  3. Compare to:
     - H12 v8 unfiltered + H43 (baseline: just H43)
     - H50 filtered + H43 (new: H50 + H43)
  4. Report per-pattern distribution and per-phase changes.

THRESHOLDS (from H43 and H50, not tuned to labels):
  - H50: MIN_FLIGHT_TIME = 10 frames
  - H43: H12 v8 confidence < 0.55 -> FOUNTAIN_LOW_CONF
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

# H43 threshold
H43_FOUNTAIN_CONF_THRESHOLD = 0.55
# H50 threshold (for documentation; applied upstream)
H50_MIN_FLIGHT_TIME = 10


def load_patterns(stem: str, filtered: bool) -> list[dict]:
    """Load pattern_inference CSV (filtered or unfiltered)."""
    suffix = "h50" if filtered else "h50_unfiltered"
    rows = []
    with (H1_DATA / f"pattern_inference_{suffix}_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["confidence"] = float(r["confidence"])
            rows.append(r)
    return rows


def apply_h43(rows: list[dict]) -> list[dict]:
    """Apply H43 filter: FOUNTAIN_3+ with conf < 0.55 -> FOUNTAIN_LOW_CONF."""
    out = []
    for r in rows:
        new_r = dict(r)
        if r["pattern"] == "FOUNTAIN_3+" and r["confidence"] < H43_FOUNTAIN_CONF_THRESHOLD:
            new_r["h51_pattern"] = "FOUNTAIN_LOW_CONF"
        else:
            new_r["h51_pattern"] = r["pattern"]
        out.append(new_r)
    return out


def detect_phase_boundaries(results: list[dict]) -> list[dict]:
    if not results:
        return []
    phases = []
    current = None
    start = None
    confs = []
    for r in results:
        if r["h51_pattern"] != current:
            if current is not None:
                phases.append({
                    "start_frame": start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current,
                    "n_frames": r["frame"] - start,
                    "avg_confidence": round(sum(confs) / len(confs), 3),
                })
            current = r["h51_pattern"]
            start = r["frame"]
            confs = [r["confidence"]]
        else:
            confs.append(r["confidence"])
    if current is not None:
        phases.append({
            "start_frame": start,
            "end_frame": results[-1]["frame"],
            "pattern": current,
            "n_frames": results[-1]["frame"] - start + 1,
            "avg_confidence": round(sum(confs) / len(confs), 3),
        })
    return phases


def main():
    summary = {
        "config": {
            "H50_MIN_FLIGHT_TIME": H50_MIN_FLIGHT_TIME,
            "H43_FOUNTAIN_CONF_THRESHOLD": H43_FOUNTAIN_CONF_THRESHOLD,
        },
        "videos": {},
    }
    for stem in STEMS:
        print(f"\n=== {stem} (H51: H12 v8 + H50 + H43) ===")

        # Load both unfiltered (baseline) and filtered (H50) pattern inference
        rows_unf = load_patterns(stem, filtered=False)
        rows_f = load_patterns(stem, filtered=True)

        # Apply H43 to both
        rows_unf_h43 = apply_h43(rows_unf)
        rows_f_h43 = apply_h43(rows_f)

        # Compute pattern distribution
        def dist(rows):
            d = defaultdict(int)
            for r in rows:
                d[r["h51_pattern"]] += 1
            return d

        dist_unf = dist(rows_unf_h43)
        dist_f = dist(rows_f_h43)
        n = len(rows_unf)

        print(f"  Pattern distribution (H43 only / H50+H43):")
        all_pats = set(dist_unf) | set(dist_f)
        for pat in sorted(all_pats, key=lambda p: -dist_f.get(p, 0)):
            u = dist_unf.get(pat, 0)
            f = dist_f.get(pat, 0)
            d = f - u
            arrow = " <--" if abs(d) > 0 else ""
            u_pct = round(100 * u / n, 1)
            f_pct = round(100 * f / n, 1)
            print(f"    {pat}: {u_pct:5.1f}% -> {f_pct:5.1f}%  ({d:+d}f){arrow}")

        # Compare FOUNTAIN_LOW_CONF counts
        n_fountain_unf = dist_unf.get("FOUNTAIN_LOW_CONF", 0)
        n_fountain_f = dist_f.get("FOUNTAIN_LOW_CONF", 0)
        n_fountain_kept_unf = dist_unf.get("FOUNTAIN_3+", 0)
        n_fountain_kept_f = dist_f.get("FOUNTAIN_3+", 0)
        print(f"  FOUNTAIN_LOW_CONF: {n_fountain_unf} (H43) -> {n_fountain_f} (H50+H43)")
        print(f"  FOUNTAIN_3+ kept: {n_fountain_kept_unf} (H43) -> {n_fountain_kept_f} (H50+H43)")

        # Per-frame diff (H50+H43 vs H43 only)
        f_by_frame = {r["frame"]: r for r in rows_f_h43}
        diff_count = 0
        diff_examples = []
        for r in rows_unf_h43:
            f = r["frame"]
            if f in f_by_frame:
                if r["h51_pattern"] != f_by_frame[f]["h51_pattern"]:
                    diff_count += 1
                    if len(diff_examples) < 10:
                        diff_examples.append({
                            "frame": f,
                            "h43_only": r["h51_pattern"],
                            "h50_h43": f_by_frame[f]["h51_pattern"],
                            "h43_only_conf": r["confidence"],
                            "h50_h43_conf": f_by_frame[f]["confidence"],
                        })
        pct_diff = round(100 * diff_count / max(1, n), 1)
        print(f"  Per-frame pattern diff (H50+H43 vs H43 only): "
              f"{diff_count}/{n} ({pct_diff}%)")
        if diff_examples:
            print(f"  First 5 diff examples:")
            for ex in diff_examples[:5]:
                print(f"    f={ex['frame']}: {ex['h43_only']} -> {ex['h50_h43']} "
                      f"(conf {ex['h43_only_conf']} -> {ex['h50_h43_conf']})")

        # Substantial phases
        phases_f = detect_phase_boundaries(rows_f_h43)
        sub_phases_f = [p for p in phases_f if p["n_frames"] >= 20]
        phases_unf = detect_phase_boundaries(rows_unf_h43)
        sub_phases_unf = [p for p in phases_unf if p["n_frames"] >= 20]
        print(f"  Substantial phases (n_frames >= 20):")
        print(f"    H43 only: {len(sub_phases_unf)}")
        print(f"    H50+H43:  {len(sub_phases_f)}")

        # Save outputs
        out_csv = H1_DATA / f"h51_filtered_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_f_h43[0].keys()))
            w.writeheader()
            w.writerows(rows_f_h43)
        print(f"  Wrote: {out_csv.name}")
        out_phases = H1_DATA / f"h51_phases_{stem}.csv"
        with out_phases.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(phases_f[0].keys()))
            w.writeheader()
            w.writerows(phases_f)
        print(f"  Wrote: {out_phases.name}")

        summary["videos"][stem] = {
            "n_total_frames": n,
            "h43_only_pattern_counts": dict(dist_unf),
            "h50_h43_pattern_counts": dict(dist_f),
            "n_fountain_low_conf_h43_only": n_fountain_unf,
            "n_fountain_low_conf_h50_h43": n_fountain_f,
            "n_fountain_kept_h43_only": n_fountain_kept_unf,
            "n_fountain_kept_h50_h43": n_fountain_kept_f,
            "n_per_frame_diff": diff_count,
            "pct_per_frame_diff": pct_diff,
            "diff_examples": diff_examples,
            "h43_only_substantial_phases": sub_phases_unf,
            "h50_h43_substantial_phases": sub_phases_f,
        }

    out_summary = H1_DATA / "h51_combined_filter_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out_summary}")


if __name__ == "__main__":
    main()
