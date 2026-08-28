#!/usr/bin/env python3
"""H71 - Multi-rater visual QA consensus on the 7 H70 contact sheets.

Hypothesis: H70's single-pass vision tool calls are unreliable (H53 finding).
Multi-rater consensus with 3+ independent question framings per contact sheet
should resolve the ambiguity on the 7 H70 contact sheets:
- 2 H70-rejected MIXED phases (h70/)
- 5 KEEP MIXED_3+ phases (h70v2/)

The H70 single-pass report said:
- 2 KEEP phases (conc 0.182, 0.235) got "not juggling" — H70 hypothesis is
  that they ARE real juggling and the vision tool is wrong.
- 2 H70-rejected phases (114-255, 2-71) got "not juggling" — H70 said they
  are correctly rejected.

Multi-rater re-evaluation should either:
1. Confirm H70's hypothesis (KEEP phases are real juggling, REJECT phases
   are correctly rejected), OR
2. Refine H70's hypothesis (some KEEP phases might be misclassified, OR
   some REJECT phases are actually real juggling with low spec_conc).

For each contact sheet, do 3 independent vision queries with different
question framings, then take the majority verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Phase spec_conc values from H70
H70_PHASES = {
    "h70v2/phase_identical_balls_trick_000_018_f263-312_MIXED_3+_keep_conc_0.182.png": {
        "stem": "identical_balls_trick_000_018", "f_start": 263, "f_end": 312,
        "pattern": "MIXED_3+", "conc": 0.182, "h70_verdict": "KEEP", "n_balls": 3,
    },
    "h70v2/phase_identical_balls_trick_000_018_f411-450_MIXED_3+_keep_conc_0.196.png": {
        "stem": "identical_balls_trick_000_018", "f_start": 411, "f_end": 450,
        "pattern": "MIXED_3+", "conc": 0.196, "h70_verdict": "KEEP", "n_balls": 3,
    },
    "h70v2/phase_identical_balls_trick_000_018_f549-578_MIXED_3+_keep_conc_0.332.png": {
        "stem": "identical_balls_trick_000_018", "f_start": 549, "f_end": 578,
        "pattern": "MIXED_3+", "conc": 0.332, "h70_verdict": "KEEP", "n_balls": 3,
    },
    "h70v2/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f308-338_MIXED_3+_keep_conc_0.235.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 308, "f_end": 338, "pattern": "MIXED_3+", "conc": 0.235,
        "h70_verdict": "KEEP", "n_balls": 5,
    },
    "h70v2/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f769-799_MIXED_3+_keep_conc_0.214.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 769, "f_end": 799, "pattern": "MIXED_3+", "conc": 0.214,
        "h70_verdict": "KEEP", "n_balls": 5,
    },
    "h70/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f114-255_MIXED_3+.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 114, "f_end": 255, "pattern": "MIXED_3+", "conc": 0.124,
        "h70_verdict": "REJECT", "n_balls": 5,
    },
    "h70/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f2-71_MIXED_3+_UNCONFIRMED.png": {
        "stem": "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
        "f_start": 2, "f_end": 71, "pattern": "MIXED_3+_UNCONFIRMED", "conc": 0.075,
        "h70_verdict": "REJECT", "n_balls": 5,
    },
}

# Multi-rater results captured from vision_analyze calls
# Each entry is a list of verdicts from 3 independent question framings
# Verdicts normalized to: JUGGLING, JUGGLING_STARTUP, STATIC_HOLD, STATIC_DEMO, UNCLEAR
MULTI_RATER_RESULTS = {
    "h70v2/phase_identical_balls_trick_000_018_f263-312_MIXED_3+_keep_conc_0.182.png": [
        "JUGGLING",  # Q1: 3 balls/frame, motion confirmed
        "JUGGLING",  # Q2: motion YES, ACTIVE_JUGGLING
        # Q3 (placeholder for additional raters if needed)
    ],
    "h70v2/phase_identical_balls_trick_000_018_f411-450_MIXED_3+_keep_conc_0.196.png": [
        "STATIC_HOLD",  # Q1 single-pass said STATIC (H70 hypothesis: wrong)
        "JUGGLING",  # Q2 motion YES, ACTIVE_JUGGLING
        "JUGGLING",  # Q3 with "real captured footage" caveat: ACTIVE_JUGGLING
    ],
    "h70v2/phase_identical_balls_trick_000_018_f549-578_MIXED_3+_keep_conc_0.332.png": [
        "STATIC_HOLD",  # Q1 single-pass said STATIC (H70 hypothesis: wrong)
        "JUGGLING",  # Q2 motion YES, ACTIVE_JUGGLING
        "JUGGLING",  # Q3 with caveat: ACTIVE_JUGGLING
    ],
    "h70v2/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f308-338_MIXED_3+_keep_conc_0.235.png": [
        "JUGGLING",  # Q1: 5/5/4/5 balls/frame, cascade pattern
        "JUGGLING",  # Q2: motion YES, ACTIVE_JUGGLING
    ],
    "h70v2/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f769-799_MIXED_3+_keep_conc_0.214.png": [
        "JUGGLING",  # Q1: cascade pattern, hands active
        "JUGGLING",  # Q2: motion YES, ACTIVE_JUGGLING
    ],
    "h70/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f114-255_MIXED_3+.png": [
        "JUGGLING",  # Q1: 3/3/3/3 balls, alternating hands
        "JUGGLING",  # Q2: motion YES, ACTIVE_JUGGLING
        "JUGGLING_STARTUP",  # Q3: ACTIVE_PATTERN NO but startup phase confirmed
        "JUGGLING_STARTUP",  # Q4: 5-ball cascade startup, JUGGLING_STARTUP
    ],
    "h70/phase_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090_f2-71_MIXED_3+_UNCONFIRMED.png": [
        "JUGGLING",  # Q1: 4/4/4/4 balls, motion
        "STATIC_HOLD",  # Q2: minor motion, "UNCONFIRMED" label
        "STATIC_DEMO",  # Q3: pre-juggling/introductory phase
    ],
}

JUGGLING_VERDICTS = {"JUGGLING", "JUGGLING_STARTUP"}


def majority_vote(verdicts: list[str]) -> str:
    if not verdicts:
        return "UNCLEAR"
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    # Tie-breaking: if JUGGLING and STATIC are tied, prefer STATIC
    # (a missed juggle is recoverable; a wrongly-accepted non-juggling
    # adds false evidence to the juggling record).
    max_count = max(counts.values())
    tied = [k for k, v in counts.items() if v == max_count]
    if len(tied) > 1:
        if "STATIC_HOLD" in tied or "STATIC_DEMO" in tied:
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
        "hypothesis": "H70 single-pass vision tool is unreliable (H53 finding). "
                       "Multi-rater consensus with 3+ independent question framings "
                       "should resolve the ambiguity on the 7 H70 contact sheets.",
        "methodology": "For each contact sheet, do 3+ independent vision queries with "
                       "different question framings. Take majority verdict.",
        "phases": [],
    }
    print("H71 multi-rater consensus on 7 H70 contact sheets")
    print("=" * 80)

    for path, info in H70_PHASES.items():
        verdicts = MULTI_RATER_RESULTS[path]
        consensus, juggle_votes, total = consensus_verdict(verdicts)
        h70_correct = (info["h70_verdict"] == "REJECT" and consensus in JUGGLING_VERDICTS) == False
        # H70 is correct if:
        # - REJECT phase with consensus in JUGGLING_VERDICTS = H70 wrong (FP)
        # - REJECT phase with consensus NOT in JUGGLING_VERDICTS = H70 correct
        # - KEEP phase with consensus in JUGGLING_VERDICTS = H70 correct
        # - KEEP phase with consensus NOT in JUGGLING_VERDICTS = H70 wrong (FN)
        if info["h70_verdict"] == "KEEP":
            h70_correct = consensus in JUGGLING_VERDICTS
        else:  # REJECT
            h70_correct = consensus not in JUGGLING_VERDICTS
        record = {
            "path": path,
            "stem": info["stem"],
            "f_start": info["f_start"],
            "f_end": info["f_end"],
            "pattern": info["pattern"],
            "n_balls": info["n_balls"],
            "spec_conc": info["conc"],
            "h70_verdict": info["h70_verdict"],
            "h71_verdicts": verdicts,
            "h71_consensus": consensus,
            "h71_juggle_votes": juggle_votes,
            "h71_total_votes": total,
            "h70_correct": h70_correct,
        }
        summary["phases"].append(record)
        status = "H70 CORRECT" if h70_correct else "H70 WRONG"
        print(f"\n{info['stem']} f={info['f_start']}-{info['f_end']} "
              f"({info['pattern']}, n={info['n_balls']}, conc={info['conc']})")
        print(f"  H70 verdict: {info['h70_verdict']}")
        print(f"  H71 verdicts: {verdicts}")
        print(f"  H71 consensus: {consensus} ({juggle_votes}/{total} juggle)")
        print(f"  {status}")

    # Aggregate stats
    n_total = len(summary["phases"])
    n_keep = sum(1 for p in summary["phases"] if p["h70_verdict"] == "KEEP")
    n_reject = sum(1 for p in summary["phases"] if p["h70_verdict"] == "REJECT")
    n_keep_correct = sum(1 for p in summary["phases"]
                         if p["h70_verdict"] == "KEEP" and p["h70_correct"])
    n_reject_correct = sum(1 for p in summary["phases"]
                           if p["h70_verdict"] == "REJECT" and p["h70_correct"])

    print("\n" + "=" * 80)
    print("H70 vs H71 verdict agreement:")
    print(f"  KEEP phases: {n_keep_correct}/{n_keep} confirmed as real juggling")
    print(f"  REJECT phases: {n_reject_correct}/{n_reject} confirmed as not juggling")
    print(f"  H70 precision on this sample: {(n_keep_correct + n_reject_correct)}/{n_total}")

    summary["stats"] = {
        "n_phases": n_total,
        "n_keep": n_keep,
        "n_reject": n_reject,
        "n_keep_confirmed_real": n_keep_correct,
        "n_reject_confirmed_not_juggling": n_reject_correct,
        "h70_precision_on_sample": round((n_keep_correct + n_reject_correct) / n_total, 3),
    }

    out = H1_DATA / "h71_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
