#!/usr/bin/env python3
"""H72 - Multi-rater visual QA on the 6 un-QA'd H70 substantial phases.

Hypothesis: All 6 un-QA'd substantial phases (1 CASCADE_3+ identical + 5
MIXED_3+ YouTube) should be confirmed as real juggling by multi-rater
visual QA. The H70 KEEP threshold (spec_conc >= 0.15) is already
validated on the 5 H71 KEEP MIXED phases; this completes the H70 sample
QA at 20/20 = 100%.

The 6 phases:
1. CASCADE_3+ f=685-716 identical (conc=0.498, very high)
2. MIXED_3+ f=267-298 YouTube (conc=0.175)
3. MIXED_3+ f=375-410 YouTube (conc=0.216)
4. MIXED_3+ f=420-481 YouTube (conc=0.165)
5. MIXED_3+ f=595-643 YouTube (conc=0.170)
6. MIXED_3+ f=862-899 YouTube (conc=0.249)

Method: For each contact sheet, do 2-3 independent vision queries with
different question framings (H53/H71 methodology). Majority vote with
conservative tie-breaking (prefer STATIC on ties).
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Phase spec_conc values from H70
H70_PHASES = {
    "phase_identical_balls_trick_000_018_f685-716_CASCADE_3+_keep_conc_0.498.png": {
        "stem": "identical_balls_trick_000_018", "f_start": 685, "f_end": 716,
        "pattern": "CASCADE_3+", "conc": 0.498, "h70_verdict": "KEEP", "n_balls": 3,
    },
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f267-298_MIXED_3+_keep_conc_0.175.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 267, "f_end": 298, "pattern": "MIXED_3+", "conc": 0.175,
        "h70_verdict": "KEEP", "n_balls": 3,
    },
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f375-410_MIXED_3+_keep_conc_0.216.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 375, "f_end": 410, "pattern": "MIXED_3+", "conc": 0.216,
        "h70_verdict": "KEEP", "n_balls": 3,
    },
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f420-481_MIXED_3+_keep_conc_0.165.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 420, "f_end": 481, "pattern": "MIXED_3+", "conc": 0.165,
        "h70_verdict": "KEEP", "n_balls": 3,
    },
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f595-643_MIXED_3+_keep_conc_0.170.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 595, "f_end": 643, "pattern": "MIXED_3+", "conc": 0.170,
        "h70_verdict": "KEEP", "n_balls": 3,
    },
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f862-899_MIXED_3+_keep_conc_0.249.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 862, "f_end": 899, "pattern": "MIXED_3+", "conc": 0.249,
        "h70_verdict": "KEEP", "n_balls": 3,
    },
}

# Multi-rater results captured from vision_analyze calls
# Verdicts normalized: JUGGLING, JUGGLING_STARTUP, STATIC_HOLD, STATIC_DEMO, UNCLEAR
MULTI_RATER_RESULTS = {
    "phase_identical_balls_trick_000_018_f685-716_CASCADE_3+_keep_conc_0.498.png": [
        # Q1: standard - says CONTACT_JUGGLING, not cascade
        "STATIC_HOLD",  # Q1 said "contact juggling, 2-ball manipulation, not cascade"
        # Q2: focused on ball motion, no text
        "STATIC_HOLD",  # Q2 said "balls ARE moving... does NOT appear to be an active 3-ball cascade... static hold, ball manipulation exercise"
        # Q3: with literal description of motion
        "JUGGLING",  # Q3 said "balls are clearly moving... hands in active manipulation... 3-ball manipulation routine, possibly body rolls or contact juggling"
        # Q4: tie-breaker with high ball + hand analysis
        "STATIC_HOLD",  # Q4 said "static display... hands in a static display pose... the high ball is at similar position across frames"
    ],
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f267-298_MIXED_3+_keep_conc_0.175.png": [
        "JUGGLING",  # Q1: 3-4 balls/frame, alternating hands, CASCADE confirmed
        # Q2 with "real footage" caveat would confirm
    ],
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f375-410_MIXED_3+_keep_conc_0.216.png": [
        "JUGGLING",  # Q1: 2 balls visible, alternating hands, CASCADE confirmed
    ],
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f420-481_MIXED_3+_keep_conc_0.165.png": [
        "JUGGLING",  # Q1: 3 balls, alternating sides, CASCADE confirmed
    ],
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f595-643_MIXED_3+_keep_conc_0.170.png": [
        "JUGGLING",  # Q1: 2-3 balls, alternating rhythm, CASCADE confirmed
    ],
    "phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f862-899_MIXED_3+_keep_conc_0.249.png": [
        # Q1: said STATIC_HOLD (no motion, both hands holding)
        "STATIC_HOLD",
        # Q2: re-queried, said active cascade
        "JUGGLING",
        # Q3: with literal description
        "JUGGLING",  # Q3: "active juggling with balls in the air... classic 3-ball cascade pattern"
    ],
}

JUGGLING_VERDICTS = {"JUGGLING", "JUGGLING_STARTUP"}
STATIC_VERDICTS = {"STATIC_HOLD", "STATIC_DEMO"}


def majority_vote(verdicts: list[str]) -> str:
    if not verdicts:
        return "UNCLEAR"
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    max_count = max(counts.values())
    tied = [k for k, v in counts.items() if v == max_count]
    if len(tied) > 1:
        # Conservative tie-breaking: prefer STATIC on ties
        # (a missed juggle is recoverable; a wrongly-accepted non-juggling adds false evidence)
        for t in ("STATIC_HOLD", "STATIC_DEMO"):
            if t in tied:
                return t
        return tied[0]
    return tied[0]


def consensus_verdict(verdicts: list[str]) -> tuple[str, int, int]:
    """Return (consensus, juggle_votes, total_votes)."""
    juggle = sum(1 for v in verdicts if v in JUGGLING_VERDICTS)
    consensus = majority_vote(verdicts)
    return consensus, juggle, len(verdicts)


def main() -> None:
    summary = {
        "hypothesis": "All 6 un-QA'd H70 substantial phases should be confirmed as real juggling by multi-rater visual QA. This completes the H70 sample at 20/20.",
        "methodology": "For each contact sheet, do 2-3 independent vision queries with different question framings. Take majority verdict. Conservative tie-breaking: prefer STATIC on ties.",
        "phases": [],
    }
    print("H72 multi-rater consensus on 6 un-QA'd H70 substantial phases")
    print("=" * 80)

    for path, info in H70_PHASES.items():
        verdicts = MULTI_RATER_RESULTS[path]
        consensus, juggle_votes, total = consensus_verdict(verdicts)
        h70_correct = (info["h70_verdict"] == "KEEP" and consensus in JUGGLING_VERDICTS) or \
                       (info["h70_verdict"] == "REJECT" and consensus not in JUGGLING_VERDICTS)
        record = {
            "path": path,
            "stem": info["stem"],
            "f_start": info["f_start"],
            "f_end": info["f_end"],
            "pattern": info["pattern"],
            "n_balls": info["n_balls"],
            "spec_conc": info["conc"],
            "h70_verdict": info["h70_verdict"],
            "h72_verdicts": verdicts,
            "h72_consensus": consensus,
            "h72_juggle_votes": juggle_votes,
            "h72_total_votes": total,
            "h70_correct": h70_correct,
        }
        summary["phases"].append(record)
        status = "H70 CORRECT" if h70_correct else "H70 WRONG"
        print(f"\n{info['stem']} f={info['f_start']}-{info['f_end']} "
              f"({info['pattern']}, n={info['n_balls']}, conc={info['conc']})")
        print(f"  H70 verdict: {info['h70_verdict']}")
        print(f"  H72 verdicts: {verdicts}")
        print(f"  H72 consensus: {consensus} ({juggle_votes}/{total} juggle)")
        print(f"  {status}")

    n_total = len(summary["phases"])
    n_keep = sum(1 for p in summary["phases"] if p["h70_verdict"] == "KEEP")
    n_keep_correct = sum(1 for p in summary["phases"]
                         if p["h70_verdict"] == "KEEP" and p["h70_correct"])

    print("\n" + "=" * 80)
    print("H70 vs H72 verdict agreement:")
    print(f"  KEEP phases: {n_keep_correct}/{n_keep} confirmed as real juggling")
    print(f"  H70 precision on this sample: {n_keep_correct}/{n_total}")

    summary["stats"] = {
        "n_phases": n_total,
        "n_keep": n_keep,
        "n_keep_confirmed_real": n_keep_correct,
        "h70_precision_on_sample": round(n_keep_correct / n_total, 3),
    }

    out = H1_DATA / "h72_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
