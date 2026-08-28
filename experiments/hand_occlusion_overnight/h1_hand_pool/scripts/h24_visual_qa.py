#!/usr/bin/env python3
"""H24: Visual QA of the H20-KEPT e6c_not_in_h7v2 candidate pool.

Renders contact sheets (done in h24_candidate_qa_at_scale.py) and
records verdicts from manual visual inspection.  This script loads
the 9 contact sheets produced by h24_candidate_qa_at_scale.py and
records the visual verdicts (REAL, PARTIAL, FALSE, UNCLEAR) into a
structured CSV/JSON for downstream analysis.

The visual verdicts come from a prior vision_analyze call on each
contact sheet.  They are recorded here for reproducibility and
to feed into the H24 precision characterization.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
DATA = H1_DIR / "data"
CS = H1_DIR / "contact_sheets_h24"

# Visual QA verdicts (from vision_analyze on the 9 H24 contact sheets).
H24_VERDICTS = [
    {"h24_idx": 1,  "stem": "identical_balls_trick_000_018", "from_tid": 9,  "to_tid": 12, "gap": 6,  "vshape": "V_DEEP",    "hand": "left",  "min_d": 15.43, "verdict": "FALSE",   "reason": "Source 'ball' held at L hand (4 px/frame motion, no descent); target 'ball' high in frame (170 px above L hand) is a stationary or pre-existing different-color ball. Cross-ball artifact."},
    {"h24_idx": 2,  "stem": "identical_balls_trick_000_018", "from_tid": 62, "to_tid": 65, "gap": 8,  "vshape": "V_DEEP",    "hand": "right", "min_d": 32.58, "verdict": "FALSE",   "reason": "Source ball descending to R hand plausibly but catch not completed in source frames. Target ball at +130 px x-displacement, R hand moving down-left (opposite of post-catch rebound). Cross-ball artifact."},
    {"h24_idx": 3,  "stem": "identical_balls_trick_000_018", "from_tid": 10, "to_tid": 11, "gap": 8,  "vshape": "V_DEEP",    "hand": "right", "min_d": 34.72, "verdict": "PARTIAL", "reason": "Source ball near apex drifting horizontally (not descending). Target ball at R wrist. Both events within the 8-frame gap, not visible. min_d=34.7 is plausible but V-shape artifact is not confirmed."},
    {"h24_idx": 4,  "stem": "identical_balls_trick_000_018", "from_tid": 7,  "to_tid": 10, "gap": 8,  "vshape": "V_SHALLOW", "hand": "left",  "min_d": 57.35, "verdict": "REAL",    "reason": "R hand has thrown (blue ball in air), L hand has caught (orange ball adjacent to L wrist in target frames). Hand ownership inverts from R to L. Shallow V-throw consistent with V_SHALLOW."},
    {"h24_idx": 5,  "stem": "identical_balls_trick_000_018", "from_tid": 67, "to_tid": 72, "gap": 9,  "vshape": "V_DEEP",    "hand": "left",  "min_d": 26.14, "verdict": "FALSE",   "reason": "Source ball at high apex y=200 (blue, large). Target ball at y=475 (orange, small). Different colors, 270 px y-jump across 9 frames. The V-apex (705,474) does not match the airborne ball position. Cross-ball artifact."},
    {"h24_idx": 6,  "stem": "identical_balls_trick_000_018", "from_tid": 73, "to_tid": 75, "gap": 10, "vshape": "V_DEEP",    "hand": "left",  "min_d": 35.20, "verdict": "FALSE",   "reason": "Ball held at L wrist in BOTH source and target frames. No throw event between R and L hand visible. Held-ball artifact."},
    {"h24_idx": 7,  "stem": "identical_balls_trick_000_018", "from_tid": 1,  "to_tid": 6,  "gap": 10, "vshape": "V_DEEP",    "hand": "right", "min_d": 41.88, "verdict": "FALSE",   "reason": "Source ball far below R hand (y=680, wrist at y=540). Target ball well above L hand (y=400, wrist at y=490). Hands empty in all frames. No catch+throw event. Cross-ball artifact."},
    {"h24_idx": 8,  "stem": "identical_balls_trick_000_018", "from_tid": 59, "to_tid": 61, "gap": 11, "vshape": "V_DEEP",    "hand": "right", "min_d": 18.94, "verdict": "REAL",    "reason": "Source R hand holds ball, L hand held high (wind-up pose). Target L hand now holds ball, R hand moved away (post-catch pose). Wrist-relative-to-ball configurations invert across the gap. min_d=18.9 is tight. Clear R->L transfer."},
    {"h24_idx": 9,  "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", "from_tid": 10, "to_tid": 11, "gap": 9, "vshape": "V_DEEP", "hand": "right", "min_d": 4.69, "verdict": "PARTIAL", "reason": "Catch visible in source (ball descending to R hand, co-located at f=241). Ball-in-flight-after-throw visible in target (ball high above hands, rising). Throw moment hidden in the 9-frame gap."},
]


def main() -> None:
    out_csv = DATA / "h24_visual_qa_verdicts.csv"
    out_json = DATA / "h24_summary.json"

    # Write CSV
    fieldnames = list(H24_VERDICTS[0].keys())
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in H24_VERDICTS:
            w.writerow(row)
    print(f"Wrote {out_csv} ({len(H24_VERDICTS)} verdicts)")

    # Tally
    n = len(H24_VERDICTS)
    n_real = sum(1 for v in H24_VERDICTS if v["verdict"] == "REAL")
    n_partial = sum(1 for v in H24_VERDICTS if v["verdict"] == "PARTIAL")
    n_false = sum(1 for v in H24_VERDICTS if v["verdict"] == "FALSE")
    n_unclear = sum(1 for v in H24_VERDICTS if v["verdict"] == "UNCLEAR")
    p_partial_tp = (n_real + n_partial) / n
    p_strict = n_real / n

    # Per-stem
    per_stem = {}
    for v in H24_VERDICTS:
        per_stem.setdefault(v["stem"], {"n": 0, "real": 0, "partial": 0, "false": 0, "unclear": 0})
        per_stem[v["stem"]]["n"] += 1
        per_stem[v["stem"]][v["verdict"].lower()] = per_stem[v["stem"]].get(v["verdict"].lower(), 0) + 1

    # Per-hand
    per_hand = {}
    for v in H24_VERDICTS:
        per_hand.setdefault(v["hand"], {"n": 0, "real": 0, "partial": 0, "false": 0, "unclear": 0})
        per_hand[v["hand"]]["n"] += 1
        per_hand[v["hand"]][v["verdict"].lower()] = per_hand[v["hand"]].get(v["verdict"].lower(), 0) + 1

    # Per-vshape
    per_vshape = {}
    for v in H24_VERDICTS:
        per_vshape.setdefault(v["vshape"], {"n": 0, "real": 0, "partial": 0, "false": 0, "unclear": 0})
        per_vshape[v["vshape"]]["n"] += 1
        per_vshape[v["vshape"]][v["verdict"].lower()] = per_vshape[v["vshape"]].get(v["verdict"].lower(), 0) + 1

    summary = {
        "n_qa": n,
        "n_real": n_real,
        "n_partial": n_partial,
        "n_false": n_false,
        "n_unclear": n_unclear,
        "precision_partial_as_tp": round(p_partial_tp, 4),
        "precision_real_only": round(p_strict, 4),
        "per_stem": per_stem,
        "per_hand": per_hand,
        "per_vshape": per_vshape,
        "verdicts": H24_VERDICTS,
    }
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {out_json}")
    print(f"Tally: REAL={n_real}, PARTIAL={n_partial}, FALSE={n_false}, UNCLEAR={n_unclear}")
    print(f"Precision (PARTIAL=TP): {p_partial_tp:.3f}")
    print(f"Precision (REAL only):  {p_strict:.3f}")


if __name__ == "__main__":
    main()
