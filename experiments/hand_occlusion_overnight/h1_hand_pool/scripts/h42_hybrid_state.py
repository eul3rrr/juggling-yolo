#!/usr/bin/env python3
"""H42 - H40 v2 enrichment of H36 (L, R, A) state.

HYPOTHESIS:
  H36 only emits hand-occupancy state at chain events; H40 v2
  detects 3-4x more hand-occupancy. A HYBRID state machine that
  uses H36 chain events where available and H40 v2 sustained-
  occupancy otherwise would give a more complete hand-occupancy
  picture.

ALGORITHM:
  For each frame f:
  1. If H36 has a non-HOLD state at f, use H36 (chain-driven)
  2. Else if H40 v2 has sustained occupancy, use H40 v2
  3. Else, use H36 HOLD state

EXPECTED:
  - Hybrid state has higher hand-occupancy coverage than H36
    alone (closer to H40 v2)
  - Hybrid state has higher chain-event accuracy than H40 v2
    alone (uses H36 where available)
  - Hybrid state may not be a better FOUNTAIN_3+ discriminator
    (we tested H41 — it doesn't help)

OUTPUT:
  - h42_hybrid_<stem>.csv: per-frame (L, R, A) with H36, H40, and
    hybrid state
  - h42_summary.json: aggregate stats
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
        print(f"\n=== {stem} (H42: H36 + H40 v2 hybrid state) ===")

        # Load H36 per-frame state
        h36 = {}
        with (H1_DATA / f"h36_per_frame_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                h36[int(r["frame"])] = (int(r["L"]), int(r["R"]), int(r["A"]))

        # Load H40 v2 per-frame state
        h40 = {}
        with (H1_DATA / f"h40v2_continuous_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                h40[int(r["frame"])] = (int(r["L40v2"]), int(r["R40v2"]))

        # Load H12 v8 pattern (for downstream analysis)
        h12 = {}
        with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                h12[int(r["frame"])] = (r["pattern"], float(r["confidence"]))

        # Compute hybrid state
        all_frames = sorted(set(h36.keys()) | set(h40.keys()))
        hybrid = {}
        n_h36_used = 0
        n_h40_used = 0
        n_hold = 0
        for f in all_frames:
            L36, R36, A36 = h36.get(f, (0, 0, 0))
            L40, R40 = h40.get(f, (0, 0))
            # Heuristic: if H36 has a non-zero L+R, use H36 (chain-driven)
            # Else if H40 has non-zero L+R, use H40 (continuous)
            # Else: HOLD (0, 0, A)
            if L36 > 0 or R36 > 0:
                # Use H36
                hybrid[f] = (L36, R36, A36, "h36")
                n_h36_used += 1
            elif L40 > 0 or R40 > 0:
                # Use H40 (continuous)
                L42 = L40
                R42 = R40
                A42 = max(0, (L36 + R36 + A36) - L42 - R42)  # total stays same
                hybrid[f] = (L42, R42, A42, "h40")
                n_h40_used += 1
            else:
                # HOLD
                hybrid[f] = (L36, R36, A36, "hold")
                n_hold += 1

        n_total = len(all_frames)
        print(f"  total frames: {n_total}")
        print(f"  used H36: {n_h36_used} ({n_h36_used*100/n_total:.1f}%)")
        print(f"  used H40: {n_h40_used} ({n_h40_used*100/n_total:.1f}%)")
        print(f"  HOLD: {n_hold} ({n_hold*100/n_total:.1f}%)")

        # Hybrid state distribution by H12 v8 pattern
        n_by_pattern = defaultdict(int)
        n_by_pattern_with_l = defaultdict(int)
        n_by_pattern_with_r = defaultdict(int)
        n_by_pattern_with_both = defaultdict(int)
        for f in all_frames:
            p = h12.get(f, (None, 0))[0]
            if p:
                n_by_pattern[p] += 1
                L, R, A, src = hybrid[f]
                if L > 0:
                    n_by_pattern_with_l[p] += 1
                if R > 0:
                    n_by_pattern_with_r[p] += 1
                if L > 0 and R > 0:
                    n_by_pattern_with_both[p] += 1
        print(f"\n  Hybrid state hand-occupancy by H12 v8 pattern:")
        for p, n in sorted(n_by_pattern.items(), key=lambda x: -x[1]):
            if n > 0:
                l_rate = n_by_pattern_with_l[p] * 100 / n
                r_rate = n_by_pattern_with_r[p] * 100 / n
                both_rate = n_by_pattern_with_both[p] * 100 / n
                print(f"    {p}: L={l_rate:.1f}%, R={r_rate:.1f}%, both={both_rate:.1f}%")

        # Write per-frame output
        out_csv = H1_DATA / f"h42_hybrid_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = ["frame", "L42", "R42", "A42", "source", "L36", "R36", "A36",
                          "L40v2", "R40v2", "h12_pattern", "h12_conf"]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for f in all_frames:
                L42, R42, A42, src = hybrid[f]
                L36, R36, A36 = h36.get(f, (0, 0, 0))
                L40v2, R40v2 = h40.get(f, (0, 0))
                pat, conf = h12.get(f, ("", 0.0))
                w.writerow({"frame": f, "L42": L42, "R42": R42, "A42": A42,
                            "source": src, "L36": L36, "R36": R36, "A36": A36,
                            "L40v2": L40v2, "R40v2": R40v2,
                            "h12_pattern": pat, "h12_conf": conf})
        print(f"  wrote: {out_csv.name} ({len(all_frames)} rows)")

        summary["videos"][stem] = {
            "n_total": n_total,
            "n_h36_used": n_h36_used,
            "n_h40_used": n_h40_used,
            "n_hold": n_hold,
            "pct_h36_used": round(n_h36_used * 100 / n_total, 1),
            "pct_h40_used": round(n_h40_used * 100 / n_total, 1),
            "pct_hold": round(n_hold * 100 / n_total, 1),
            "pattern_hand_occupancy": {
                p: {
                    "L_pct": round(n_by_pattern_with_l[p] * 100 / max(1, n), 1),
                    "R_pct": round(n_by_pattern_with_r[p] * 100 / max(1, n), 1),
                    "both_pct": round(n_by_pattern_with_both[p] * 100 / max(1, n), 1),
                }
                for p, n in n_by_pattern.items()
            },
        }

    out = H1_DATA / "h42_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
