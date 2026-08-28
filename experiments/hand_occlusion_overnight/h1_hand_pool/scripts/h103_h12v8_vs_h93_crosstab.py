#!/usr/bin/env python3
"""H103 — H12 v8 vs H93 phase verdict cross-tabulation.

Hypothesis: H12 v8 over-classifies STATIC_HOLD phases as FOUNTAIN_3+
because it sees "many balls in air" without checking for actual
juggling motion. H102 found that 3 of the 5 phase-vs-review
disagreements are in H93 STATIC_HOLD phases that H12 v8 calls
FOUNTAIN_3+ (the f=482-594 YouTube phase).

H103 quantifies this over-classification systematically:
- For each H93 phase, compute the H12 v8 per-frame pattern distribution.
- Cross-tabulate H93 phase_verdict x H12 v8 dominant pattern.
- Identify the 3 STATIC_HOLD phases (or similar) that H12 v8 over-classifies.

This is a small, isolated consumer-pass experiment that uses
existing per-frame data (no new runs).

Outputs:
  - data/h103_per_phase.csv (per H93 phase: H12 v8 pattern distribution)
  - data/h103_summary.json (cross-tabulation)
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# H12 v8 pattern hierarchy (from H12 v8 documentation)
# FOUNTAIN_3+ > CASCADE_3+ > MIXED_3+ > MIXED_3+_UNCONFIRMED > MIXED_3+_REJECTED
# > TWO_BALL > SINGLE_BALL > NO_BALL > UNKNOWN
PATTERN_RANK = {
    "FOUNTAIN_3+": 8,
    "CASCADE_3+": 7,
    "MIXED_3+": 6,
    "MIXED_3+_UNCONFIRMED": 5,
    "MIXED_3+_REJECTED": 4,
    "TWO_BALL": 3,
    "SINGLE_BALL": 2,
    "NO_BALL": 1,
    "UNKNOWN": 0,
}


def load_h93_phases() -> dict[str, list[dict]]:
    """Load H93 corrected ground truth."""
    with (H1_DATA / "h93_multi_rater_qa.json").open() as fh:
        h93 = json.load(fh)
    gt = h93["corrected_ground_truth"]
    out = defaultdict(list)
    for k, verdict in gt.items():
        parts = k.rsplit("_", 2)
        stem, start, end = parts[0], int(parts[1]), int(parts[2])
        out[stem].append({
            "start": start,
            "end": end,
            "verdict": verdict,
            "key": k,
        })
    for stem in out:
        out[stem].sort(key=lambda p: p["start"])
    return dict(out)


def load_h67_per_frame() -> dict[str, list[dict]]:
    """Load H67 per-frame pattern labels (H12 v8 + H43/H66/H67 reject flags)."""
    out = {}
    for stem in ("identical_balls_trick_000_018",
                 "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"):
        path = H1_DATA / f"h67_per_frame_{stem}.csv"
        with path.open() as fh:
            rows = list(csv.DictReader(fh))
        out[stem] = rows
    return out


def main() -> None:
    print("=" * 72)
    print("H103 — H12 v8 vs H93 phase verdict cross-tabulation")
    print("=" * 72)

    h93_phases = load_h93_phases()
    h67_per_frame = load_h67_per_frame()

    print(f"H93 phases loaded: {sum(len(v) for v in h93_phases.values())}")

    # Per-phase H12 v8 pattern distribution
    per_phase = []
    cross_tab = defaultdict(lambda: defaultdict(int))
    for stem, phases in h93_phases.items():
        per_frame = h67_per_frame[stem]
        for p in phases:
            rows = [r for r in per_frame
                    if p["start"] <= int(r["frame"]) <= p["end"]]
            n = len(rows)
            c = Counter(r["h67_pattern"] for r in rows)
            # Dominant pattern (most common)
            if c:
                dominant = c.most_common(1)[0][0]
            else:
                dominant = "NONE"
            n_h67_rejected = sum(1 for r in rows if r["h67_rejected"] == "yes")
            per_phase.append({
                "stem": stem,
                "phase_key": p["key"],
                "phase_start": p["start"],
                "phase_end": p["end"],
                "phase_verdict": p["verdict"],
                "n_frames": n,
                "dominant_pattern": dominant,
                "pct_fountain": round(100 * c.get("FOUNTAIN_3+", 0) / max(1, n), 1),
                "pct_cascade": round(100 * c.get("CASCADE_3+", 0) / max(1, n), 1),
                "pct_mixed": round(100 * (c.get("MIXED_3+", 0) + c.get("MIXED_3+_UNCONFIRMED", 0)) / max(1, n), 1),
                "pct_unknown": round(100 * c.get("UNKNOWN", 0) / max(1, n), 1),
                "pct_static": round(100 * (c.get("NO_BALL", 0) + c.get("SINGLE_BALL", 0) + c.get("TWO_BALL", 0)) / max(1, n), 1),
                "n_h67_rejected": n_h67_rejected,
                "pct_h67_rejected": round(100 * n_h67_rejected / max(1, n), 1),
            })
            cross_tab[p["verdict"]][dominant] += 1

    # Save per-phase
    out_path = H1_DATA / "h103_per_phase.csv"
    with out_path.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
        wr.writeheader()
        wr.writerows(per_phase)
    print(f"per-phase CSV: {out_path}")

    # Print per-phase table
    print("\n=== H12 v8 pattern distribution by H93 phase verdict ===")
    print(f"{'phase':<55}  {'verdict':<20}  {'dominant':<25}  {'F%':>4}  {'C%':>4}  {'M%':>4}  {'Unk%':>5}  {'Static%':>8}  {'h67_rej%':>9}")
    for r in per_phase:
        print(f"{r['phase_key'][-50:]:<55}  {r['phase_verdict']:<20}  "
              f"{r['dominant_pattern']:<25}  "
              f"{r['pct_fountain']:>3.0f}  {r['pct_cascade']:>3.0f}  {r['pct_mixed']:>3.0f}  "
              f"{r['pct_unknown']:>4.0f}  {r['pct_static']:>7.0f}  {r['pct_h67_rejected']:>8.0f}")

    # Cross-tabulation
    print("\n=== Cross-tabulation: H93 verdict x H12 v8 dominant pattern ===")
    all_verdicts = sorted({p["phase_verdict"] for p in per_phase})
    all_dominants = sorted({p["dominant_pattern"] for p in per_phase},
                            key=lambda x: -PATTERN_RANK.get(x, 0))
    # Header
    print(f"{'H93 verdict':<22}  ", end="")
    for d in all_dominants:
        print(f"{d[:12]:>13}", end="")
    print(f"  {'total':>6}")
    for v in all_verdicts:
        print(f"{v:<22}  ", end="")
        for d in all_dominants:
            n = cross_tab[v].get(d, 0)
            print(f"{n:>13}", end="")
        print(f"  {sum(cross_tab[v].values()):>6}")

    # Save summary
    summary = {
        "method": "H103: H12 v8 vs H93 phase verdict cross-tabulation (21 phases)",
        "n_phases": len(per_phase),
        "per_phase": per_phase,
        "cross_tab": {v: dict(c) for v, c in cross_tab.items()},
    }
    out_path = H1_DATA / "h103_summary.json"
    with out_path.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nsummary JSON: {out_path}")

    # Key findings
    print("\n=== Key findings ===")
    # 1. STATIC_HOLD phases that H12 v8 calls FOUNTAIN_3+ or CASCADE_3+
    over_classified = [r for r in per_phase
                       if r["phase_verdict"] in ("STATIC_HOLD", "OTHER_CROSSED_ARM")
                       and r["dominant_pattern"] in ("FOUNTAIN_3+", "CASCADE_3+")]
    print(f"Over-classified STATIC/OTHER phases: {len(over_classified)}")
    for r in over_classified:
        print(f"  {r['phase_key']}: H93={r['phase_verdict']}, H12 v8 dominant={r['dominant_pattern']} ({r['pct_fountain'] if r['dominant_pattern'] == 'FOUNTAIN_3+' else r['pct_cascade']}%)")

    # 2. JUGGLING phases that H12 v8 calls FOUNTAIN_3+ (correctly)
    correctly_classified = [r for r in per_phase
                            if r["phase_verdict"] == "JUGGLING"
                            and r["dominant_pattern"] in ("FOUNTAIN_3+", "CASCADE_3+", "MIXED_3+", "MIXED_3+_UNCONFIRMED")]
    print(f"\nJUGGLING phases with active H12 v8 pattern: {len(correctly_classified)}")
    for r in correctly_classified:
        print(f"  {r['phase_key']}: H12 v8 dominant={r['dominant_pattern']}")

    # 3. Total
    n_juggling = sum(1 for r in per_phase if r["phase_verdict"] == "JUGGLING")
    n_static = sum(1 for r in per_phase if r["phase_verdict"] == "STATIC_HOLD")
    n_other = sum(1 for r in per_phase if r["phase_verdict"] == "OTHER_CROSSED_ARM")
    n_h12_active = sum(1 for r in per_phase
                        if r["dominant_pattern"] in ("FOUNTAIN_3+", "CASCADE_3+", "MIXED_3+", "MIXED_3+_UNCONFIRMED"))
    print(f"\nTotal: {len(per_phase)} phases")
    print(f"  JUGGLING: {n_juggling}")
    print(f"  STATIC_HOLD: {n_static}")
    print(f"  OTHER_CROSSED_ARM: {n_other}")
    print(f"  H12 v8 active (FOUNTAIN_3+ or CASCADE_3+ or MIXED): {n_h12_active}")
    print(f"  Over-classified STATIC/OTHER as active: {len(over_classified)}")
    print(f"  JUGGLING correctly classified: {len(correctly_classified)}")


if __name__ == "__main__":
    main()
