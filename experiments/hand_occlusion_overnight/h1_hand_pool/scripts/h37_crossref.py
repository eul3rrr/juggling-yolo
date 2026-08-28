#!/usr/bin/env python3
"""H37 - cross-reference H36 (L, R, A) state with H12 v8 pattern labels.

HYPOTHESIS:
  H36 produces a per-frame (L, R, A) state from a hand-occupancy
  state machine. H12 v8 produces per-frame pattern labels
  (CASCADE_3+, FOUNTAIN_3+, etc.) using a different signal
  (per-frame ball count + recent event log). The two should
  agree on which frames have a ball in a hand.

  Cross-referencing the two signals answers:
  1. Do H36 and H12 v8 agree on (L, R, A) at each frame?
  2. Does the (L, R, A) state help disambiguate CASCADE_3+ vs
     FOUNTAIN_3+ on the late phase where H12 v8 fails?
  3. Is H36's per-frame state a useful input to a v9 of H12?

EXPECTED:
  - High agreement on ball count (L+R+A should equal
    n_in_hand_left + n_in_hand_right + n_in_air from H12 v8)
  - Disagreement on pattern labels where H36's (L, R, A) state
    gives a clearer signal than H12 v8's heuristic

ALGORITHM:
  1. Load H36 per_frame and H12 v8 pattern_inference per-frame.
  2. Merge on frame number.
  3. Compute (L+R+A) vs (n_in_hand_left + n_in_hand_right +
     n_in_air) agreement.
  4. For frames where H12 v8 says CASCADE_3+ or FOUNTAIN_3+,
     check if H36's (L, R, A) state is consistent.
  5. Visualize agreement/disagreement on a contact sheet.
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


def load_h36(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / f"h36_per_frame_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "L": int(r["L"]),
                "R": int(r["R"]),
                "A": int(r["A"]),
                "event_type": r["event_type"],
            }
    return out


def load_h12(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "n_in_air": int(r["n_in_air"]),
                "n_in_hand_left": int(r["n_in_hand_left"]),
                "n_in_hand_right": int(r["n_in_hand_right"]),
                "n_total": int(r["n_total"]),
                "pattern": r["pattern"],
                "confidence": float(r["confidence"]),
            }
    return out


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H37: H36 + H12 v8 cross-reference) ===")
        h36 = load_h36(stem)
        h12 = load_h12(stem)

        common = sorted(set(h36.keys()) & set(h12.keys()))
        print(f"  common frames: {len(common)}")
        if not common:
            continue

        # Agreement on (L, R, A) ball count
        # H12 v8 reports n_in_hand_left as number of chains with
        # a left-hand event in the same frame, not number of
        # balls. So H12's n_in_hand_left can be > 1 (multiple
        # chains with hand events). H36's L should be 0 or 1 for
        # 3-ball/5-ball patterns. We compare L <= H12.n_in_hand_left.

        n_agree = 0
        n_disagree_l = 0
        n_disagree_r = 0
        n_l_missing = 0  # H12 says L=0, H36 says L=1
        n_l_extra = 0    # H12 says L=1+, H36 says L=0
        for f in common:
            h36_L, h36_R, h36_A = h36[f]["L"], h36[f]["R"], h36[f]["A"]
            h12_l = h12[f]["n_in_hand_left"]
            h12_r = h12[f]["n_in_hand_right"]
            h12_a = h12[f]["n_in_air"]
            # H36 should be subset of H12 (H12 counts chains, not balls)
            l_ok = h36_L <= h12_l
            r_ok = h36_R <= h12_r
            a_ok = (h36_A == h12_a) or (h12_a - h12_l - h12_r == h36_A)  # H12 may double-count

            if l_ok and r_ok:
                n_agree += 1
            else:
                if not l_ok:
                    n_disagree_l += 1
                    if h36_L > h12_l:
                        n_l_extra += 1
                    else:
                        n_l_missing += 1
                if not r_ok:
                    n_disagree_r += 1

        n_total = len(common)
        print(f"  agreement: {n_agree}/{n_total} = {100*n_agree/n_total:.1f}%")
        print(f"  L disagreement: {n_disagree_l} (L_extra={n_l_extra}, L_missing={n_l_missing})")
        print(f"  R disagreement: {n_disagree_r}")

        # Pattern vs state for n_total >= 3 frames
        pattern_state = defaultdict(int)
        for f in common:
            if h12[f]["n_total"] < 3:
                continue
            p = h12[f]["pattern"]
            state_key = (h36[f]["L"], h36[f]["R"], h36[f]["A"])
            pattern_state[(p, state_key)] += 1
        print(f"  pattern x (L, R, A) for n_total>=3 frames:")
        for (p, (L, R, A)), c in sorted(pattern_state.items(),
                                          key=lambda x: -x[1])[:15]:
            print(f"    {p:25s} L={L} R={R} A={A}: {c}")

        # Specifically: late-phase FOUNTAIN_3+ on identical
        if "identical" in stem:
            late_fountain = [(f, h36[f], h12[f]) for f in common
                             if 800 <= f <= 1050
                             and h12[f]["pattern"] == "FOUNTAIN_3+"]
            print(f"  late-phase identical FOUNTAIN_3+ frames: {len(late_fountain)}")
            if late_fountain:
                fountain_states = defaultdict(int)
                for f, h36f, h12f in late_fountain:
                    fountain_states[(h36f["L"], h36f["R"], h36f["A"])] += 1
                for (L, R, A), c in sorted(fountain_states.items(),
                                            key=lambda x: -x[1]):
                    print(f"    FOUNTAIN_3+ x L={L} R={R} A={A}: {c}")

        # Write merged per-frame output
        out_csv = H1_DATA / f"h37_crossref_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = [
                "frame", "L", "R", "A", "h36_event_type",
                "h12_n_air", "h12_n_l", "h12_n_r", "h12_n_total",
                "h12_pattern", "h12_confidence",
                "h36_l_le_h12_l", "h36_r_le_h12_r", "agree",
            ]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for f in common:
                h36f, h12f = h36[f], h12[f]
                l_ok = h36f["L"] <= h12f["n_in_hand_left"]
                r_ok = h36f["R"] <= h12f["n_in_hand_right"]
                w.writerow({
                    "frame": f,
                    "L": h36f["L"], "R": h36f["R"], "A": h36f["A"],
                    "h36_event_type": h36f["event_type"],
                    "h12_n_air": h12f["n_in_air"],
                    "h12_n_l": h12f["n_in_hand_left"],
                    "h12_n_r": h12f["n_in_hand_right"],
                    "h12_n_total": h12f["n_total"],
                    "h12_pattern": h12f["pattern"],
                    "h12_confidence": h12f["confidence"],
                    "h36_l_le_h12_l": l_ok,
                    "h36_r_le_h12_r": r_ok,
                    "agree": l_ok and r_ok,
                })
        print(f"  wrote: {out_csv.name} ({len(common)} frames)")

        summary["videos"][stem] = {
            "n_common_frames": n_total,
            "n_agree": n_agree,
            "n_l_disagree": n_disagree_l,
            "n_r_disagree": n_disagree_r,
            "n_l_extra": n_l_extra,
            "n_l_missing": n_l_missing,
            "pct_agreement": round(100 * n_agree / n_total, 1)
                if n_total > 0 else 0,
        }

    out = H1_DATA / "h37_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
