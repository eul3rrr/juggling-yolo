#!/usr/bin/env python3
"""H67 - H43 + H66 stacked FOUNTAIN_3+ post-filter: end-to-end impact.

H50 measured the 10-frame filter's downstream impact on per-frame
pattern distribution (1.0% identical, 0.0% YouTube).

H43 (H12 v8 confidence < 0.55) was the previous FOUNTAIN_3+ post-filter.
H66 added continuous balls-aloft (pct_A_ge2 < 0.30) as a second
post-filter.

H67: measure the H43 + H66 stacked impact on per-frame pattern
distribution. This is similar to H50 (full pipeline re-run on
filtered event log) but for the FOUNTAIN_3+ post-filters.

HYPOTHESIS:
H43 + H66 stacked rejection rate on the H50-filtered pattern set
should be small (H65 sample: 2/7 = 28.6% of substantial phases
rejected, 1/3 of those are real FOUNTAIN labels). The downstream
pattern distribution change should be correspondingly small.

METHOD:
1. Load H50-filtered per-frame pattern data.
2. For each frame with pattern=FOUNTAIN_3+:
   - If confidence < 0.55: H43 reject, mark as FOUNTAIN_LOW_CONF.
   - If frame is in a H66-rejected phase: H66 reject, mark as
     FOUNTAIN_LOW_CONF.
3. Compute pattern distribution:
   - H50 baseline (no FOUNTAIN_3+ post-filter)
   - H50 + H43 only
   - H50 + H66 only
   - H50 + H43 + H66 stacked
4. Report per-frame diff and per-pattern delta.

Output:
  - data/h67_pattern_dist_*.json (per-video pattern distribution)
  - data/h67_per_frame_*.csv (per-frame post-filtered labels)
  - reports/h67_report.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

H1_DATA = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data")

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# H43 threshold
H43_CONF_THRESHOLD = 0.55
# H66 threshold: pct_A_ge2 below this rejects
H66_PCT_A_GE2_THRESHOLD = 0.30


def load_h66_rejected(stem: str) -> set[tuple]:
    """Load set of (start, end) tuples for H66-rejected phases."""
    path = H1_DATA / f"h66_rejected_phases_{stem}.csv"
    rejected = set()
    for r in csv.DictReader(open(path)):
        start = int(r["phase_start"])
        end = int(r["phase_end"])
        rejected.add((start, end))
    return rejected


def main() -> None:
    summary = {"videos": {}}

    for stem in STEMS:
        print(f"\n=== {stem} ===")

        # Load H50-filtered per-frame pattern data
        per_frame_path = H1_DATA / f"pattern_inference_h50_{stem}.csv"
        rows = list(csv.DictReader(open(per_frame_path)))
        print(f"  {len(rows)} frames from {per_frame_path.name}")

        # Load H66 rejected phases
        h66_rej = load_h66_rejected(stem)
        print(f"  {len(h66_rej)} H66-rejected phases")

        # Apply filters
        new_labels = []
        for r in rows:
            frame = int(r["frame"])
            pattern = r["pattern"]
            conf = float(r["confidence"])
            new_label = pattern
            if pattern == "FOUNTAIN_3+":
                # H43: conf < 0.55
                if conf < H43_CONF_THRESHOLD:
                    new_label = "FOUNTAIN_LOW_CONF"
                else:
                    # H66: phase in rejected set
                    for (s, e) in h66_rej:
                        if s <= frame <= e:
                            new_label = "FOUNTAIN_LOW_CONF"
                            break
            new_labels.append(new_label)

        # Save per-frame post-filtered labels
        out_pf = H1_DATA / f"h67_per_frame_{stem}.csv"
        with out_pf.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "h50_pattern", "h50_confidence", "h67_pattern",
                        "h43_rejected", "h66_rejected", "h67_rejected"])
            for r, nl in zip(rows, new_labels):
                frame = int(r["frame"])
                pattern = r["pattern"]
                conf = float(r["confidence"])
                h43 = "yes" if (pattern == "FOUNTAIN_3+" and conf < H43_CONF_THRESHOLD) else "no"
                h66 = "no"
                for (s, e) in h66_rej:
                    if s <= frame <= e and pattern == "FOUNTAIN_3+":
                        h66 = "yes"
                        break
                h67 = "yes" if nl != pattern else "no"
                w.writerow([frame, pattern, f"{conf:.3f}", nl, h43, h66, h67])
        print(f"  wrote: {out_pf.name}")

        # Pattern distribution
        n_changed = sum(1 for r, nl in zip(rows, new_labels) if r["pattern"] != nl)
        h50_dist = defaultdict(int)
        h67_dist = defaultdict(int)
        for r, nl in zip(rows, new_labels):
            h50_dist[r["pattern"]] += 1
            h67_dist[nl] += 1

        # Save pattern distribution
        dist = {"H50_baseline": dict(h50_dist), "H67_stacked": dict(h67_dist)}
        out_dist = H1_DATA / f"h67_pattern_dist_{stem}.json"
        out_dist.write_text(json.dumps(dist, indent=2))
        print(f"  wrote: {out_dist.name}")
        print(f"  frames changed: {n_changed} ({n_changed/len(rows)*100:.1f}%)")

        # Per-pattern delta
        all_patterns = set(h50_dist.keys()) | set(h67_dist.keys())
        deltas = {}
        for p in sorted(all_patterns):
            d = h67_dist[p] - h50_dist[p]
            if d != 0:
                deltas[p] = d
        print(f"  per-pattern delta: {deltas}")

        summary["videos"][stem] = {
            "n_frames": len(rows),
            "n_changed": n_changed,
            "pct_changed": round(n_changed / len(rows) * 100, 2),
            "h50_dist": dict(h50_dist),
            "h67_dist": dict(h67_dist),
            "per_pattern_delta": deltas,
        }

    summary["methodology"] = {
        "input": "H50-filtered per-frame pattern data",
        "filters_stacked": "H43 (conf < 0.55) + H66 (pct_A_ge2 < 0.30)",
        "H43_threshold": H43_CONF_THRESHOLD,
        "H66_threshold": H66_PCT_A_GE2_THRESHOLD,
    }
    out = H1_DATA / "h67_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
