#!/usr/bin/env python3
"""H1 v3 — sensitivity grid + soft catch-context.

Two v3 changes from v2:

1. **Soft catch-context.** v2's `UNCONTEXTED_ENTRY` was a HARD filter
   (the catch was rejected). v3 emits a `POTENTIAL_ENTRY` flag instead
   and still creates a token. Downstream consumers can apply their own
   confidence. The hard `UNCONTEXTED_ENTRY` event is still emitted for
   bookkeeping/QA, but the algorithm no longer rejects the catch.

2. **Sensitivity grid on `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7}.**
   v2 used 3 frames (100 ms). v3 sweeps 3/5/7 to see if a longer
   window catches more real throws (or admits more false positives).

The `WRIST_MOTION_THROW` filter is retained (it never fired in v2 but
is cheap insurance; can be removed in a later v4 if confirmed inert).

Outputs per setting:
- `data/hand_events_v3{label}.csv`
- `data/hand_links_v3{label}.csv`
- `data/summary_v3{label}.json`
- `data/sens_grid.json` (combined grid; per-setting summaries + counters)

The v2 artifacts (hand_events.csv, hand_links.csv) are NOT touched.
This script reads v2 in-place (monkey-patches THROW_LEAVE_WINDOW_FRAMES)
and writes separate v3 artifacts.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Reuse v2 internals
sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1_hand_pool_v2 as h2  # noqa: E402

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"


# ----------------------------------------------------------------------
# Soft catch-context
# ----------------------------------------------------------------------
# v2 emits `UNCONTEXTED_ENTRY` for catches with no prior hand event on
# the same hand. v3 renames this to `POTENTIAL_ENTRY` and still creates
# a token (v2 already created a token; we just rename the event).
# This is the SOFT form: the catch is no longer rejected, but the event
# is tagged so downstream consumers can apply their own confidence.
#
# Note: v2's `UNCONTEXTED_ENTRY` already created a token (see v2 source
# line 437-448). The "hardness" was only the EVENT NAME — the algorithm
# still tracked the catch. v3 simply makes the name softer and the
# inventory accounting unchanged.

def renamer_soft(events: list) -> None:
    """Rename UNCONTEXTED_ENTRY to POTENTIAL_ENTRY in place."""
    for e in events:
        if e.event_type == "UNCONTEXTED_ENTRY":
            e.event_type = "POTENTIAL_ENTRY"


# ----------------------------------------------------------------------
# Per-setting artifact writers
# ----------------------------------------------------------------------
def write_setting_artifacts(label: str, all_runs: list[dict]) -> None:
    """Write per-setting CSVs and summary JSON to H1_DATA."""
    suf = label.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    suf = suf.replace("__", "_").strip("_")
    events_path = H1_DATA / f"hand_events_v3_{suf}.csv"
    links_path = H1_DATA / f"hand_links_v3_{suf}.csv"
    summary_path = H1_DATA / f"summary_v3_{suf}.json"

    # events
    with events_path.open("w", newline="") as fh:
        fields = [
            "event_id", "video", "stem", "frame", "time_seconds",
            "hand", "event_type", "tid",
            "point_x", "point_y", "wrist_x", "wrist_y",
            "dist", "slope", "pre_depth", "pool_depth",
            "identity_ambiguous", "notes",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for ev in run["events"]:
                w.writerow({
                    "event_id": ev.event_id, "video": ev.video, "stem": ev.stem,
                    "frame": ev.frame, "time_seconds": round(ev.time_seconds, 4),
                    "hand": ev.hand, "event_type": ev.event_type,
                    "tid": ev.tid if ev.tid is not None else "",
                    "point_x": round(ev.point_x, 2) if ev.point_x is not None else "",
                    "point_y": round(ev.point_y, 2) if ev.point_y is not None else "",
                    "wrist_x": round(ev.wrist_x, 2) if ev.wrist_x is not None else "",
                    "wrist_y": round(ev.wrist_y, 2) if ev.wrist_y is not None else "",
                    "dist": round(ev.dist, 2) if ev.dist is not None else "",
                    "slope": round(ev.slope, 3) if ev.slope is not None else "",
                    "pre_depth": ev.pre_depth, "pool_depth": ev.pool_depth,
                    "identity_ambiguous": ev.identity_ambiguous,
                    "notes": ev.notes,
                })

    # links
    with links_path.open("w", newline="") as fh:
        fields = [
            "video", "stem", "from_tid", "to_tid", "hand",
            "from_frame", "to_frame",
            "from_dist", "to_dist", "from_slope", "to_slope",
            "identity_ambiguous", "kind", "tok_age_frames",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for l in run["links"]:
                w.writerow({
                    "video": l["video"], "stem": l["stem"],
                    "from_tid": l["from_tid"], "to_tid": l["to_tid"],
                    "hand": l["hand"],
                    "from_frame": l["from_frame"], "to_frame": l["to_frame"],
                    "from_dist": round(l["from_dist"], 2),
                    "to_dist": round(l["to_dist"], 2),
                    "from_slope": round(l["from_slope"], 3),
                    "to_slope": round(l["to_slope"], 3),
                    "identity_ambiguous": l["identity_ambiguous"],
                    "kind": l["kind"],
                    "tok_age_frames": l["tok_age_frames"],
                })

    # summary
    summary = {
        "label": label,
        "throw_leave_window_frames": h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"],
        "soft_catch_context": True,
        "videos": {},
    }
    for run in all_runs:
        reviewed = h2.load_reviewed_pairs(run["video_key"])
        ev_eval = h2.evaluate_against_labels(run, run["video_key"], reviewed)
        n_potential = sum(1 for e in run["events"] if e.event_type == "POTENTIAL_ENTRY")
        n_uncontexted = sum(1 for e in run["events"] if e.event_type == "UNCONTEXTED_ENTRY")
        summary["videos"][run["stem"]] = {
            "video_key": run["video_key"],
            "event_counts": dict(run["counters"]),
            "filtered_counts": dict(run["filtered_stats"]),
            "potential_entry": n_potential,
            "uncontexted_entry": n_uncontexted,
            "n_links": len(run["links"]),
            "n_tracklets": len(run["features"]),
            "predecessor_conflict": run["predecessor_conflict"],
            "successor_conflict": run["successor_conflict"],
            "impossible_states": run["impossible_states"],
            "multi_token_ambiguous": run["multi_token_ambiguous"],
            "evaluation_vs_reviewed": {
                "reviewed_total": ev_eval["reviewed_total"],
                "matched_correct": ev_eval["matched_correct"],
                "matched_wrong": ev_eval["matched_wrong"],
                "missed_correct": ev_eval["missed_correct"],
                "missed_wrong": ev_eval["missed_wrong"],
                "precision_hand_link": ev_eval["precision_hand_link"],
                "recall_hand_link": ev_eval["recall_hand_link"],
            },
            "links": run["links"],  # full link list
        }
    summary_path.write_text(json.dumps(summary, indent=2))


# ----------------------------------------------------------------------
# Run one setting
# ----------------------------------------------------------------------
def run_one_setting(throw_leave_window_frames: int, soft: bool, label: str,
                    write_artifacts: bool = True) -> dict:
    """Run all stems for one (throw_leave, soft) combo and return
    a per-setting summary dict."""
    # Patch the threshold in the v2 module BEFORE the state machine runs
    h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"] = throw_leave_window_frames
    all_runs = []
    for stem, video_key in h2.STEMS.items():
        run = h2.run_for_stem_v2(stem, video_key)
        if soft:
            renamer_soft(run["events"])
        all_runs.append(run)

    if write_artifacts:
        write_setting_artifacts(label, all_runs)

    summary = {
        "throw_leave_window_frames": throw_leave_window_frames,
        "soft_catch_context": soft,
        "label": label,
        "videos": {},
    }
    for run in all_runs:
        reviewed = h2.load_reviewed_pairs(run["video_key"])
        ev = h2.evaluate_against_labels(run, run["video_key"], reviewed)
        n_potential = sum(1 for e in run["events"] if e.event_type == "POTENTIAL_ENTRY")
        n_uncontexted = sum(1 for e in run["events"] if e.event_type == "UNCONTEXTED_ENTRY")
        summary["videos"][run["stem"]] = {
            "video_key": run["video_key"],
            "event_counts": dict(run["counters"]),
            "filtered_counts": dict(run["filtered_stats"]),
            "potential_entry": n_potential,
            "uncontexted_entry": n_uncontexted,
            "n_links": len(run["links"]),
            "n_tracklets": len(run["features"]),
            "evaluation_vs_reviewed": {
                "reviewed_total": ev["reviewed_total"],
                "matched_correct": ev["matched_correct"],
                "matched_wrong": ev["matched_wrong"],
                "missed_correct": ev["missed_correct"],
                "missed_wrong": ev["missed_wrong"],
                "precision_hand_link": ev["precision_hand_link"],
                "recall_hand_link": ev["recall_hand_link"],
            },
        }
    return summary


# ----------------------------------------------------------------------
# Hand-relevant (gap=0) eval, on a per-setting hand_links_v3*.csv
# ----------------------------------------------------------------------
def hand_relevant_eval_for_label(label: str) -> dict:
    """Compute the gap=0 hand-relevant precision/recall from the
    per-setting hand_links_v3*_*.csv files. Mirrors h1_gap0_eval.py
    but for v3 artifacts.
    """
    suf = label.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    suf = suf.replace("__", "_").strip("_")
    links_path = H1_DATA / f"hand_links_v3_{suf}.csv"
    if not links_path.exists():
        return {}
    rows = []
    with links_path.open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["from_frame"] = int(r["from_frame"])
            r["to_frame"] = int(r["to_frame"])
            rows.append(r)

    rev_rows = []
    with (WORKTREE / "detections" / "stitch_review_labels.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["gap_frames"] = int(r["gap_frames"])
            r["source_tracklet"] = int(r["source_tracklet"])
            r["candidate_tracklet"] = int(r["candidate_tracklet"])
            rev_rows.append(r)

    out = {"h1_version": f"v3_{suf}", "subsets": []}
    for max_gap, ll in [(0, "gap=0  (HAND-RELEVANT)"),
                        (1, "gap<=1 (near-instant transitions)"),
                        (2, "gap<=2 (broad hand-relevant)"),
                        (99, "full set (mostly mid-air)")]:
        sub = [r for r in rev_rows if r["gap_frames"] <= max_gap]
        n_correct = sum(1 for r in sub if r["label"] == "correct")
        n_wrong = sum(1 for r in sub if r["label"] == "wrong")
        n_total = len(sub)
        matched_correct = 0
        matched_wrong = 0
        matched_pairs = []
        for l in rows:
            for r in sub:
                if not l["video"].endswith(r["video"]):
                    continue
                if (l["from_tid"] == r["source_tracklet"] and l["to_tid"] == r["candidate_tracklet"]) \
                   or (l["from_tid"] == r["candidate_tracklet"] and l["to_tid"] == r["source_tracklet"]):
                    if r["label"] == "correct":
                        matched_correct += 1
                    else:
                        matched_wrong += 1
                    matched_pairs.append((l, r))
        extra = len(rows) - len(matched_pairs)
        precision = matched_correct / max(1, matched_correct + matched_wrong)
        recall = matched_correct / max(1, n_correct)
        out["subsets"].append({
            "label": ll, "max_gap": max_gap,
            "reviewed_total": n_total, "reviewed_correct": n_correct,
            "reviewed_wrong": n_wrong, "h1_links_total": len(rows),
            "h1_links_matched_correct": matched_correct,
            "h1_links_matched_wrong": matched_wrong,
            "h1_links_extra": extra,
            "precision_hand_link": round(precision, 4),
            "recall_hand_link": round(recall, 4),
        })
    eval_path = H1_DATA / f"hand_relevant_eval_v3_{suf}.json"
    eval_path.write_text(json.dumps(out, indent=2))
    return out


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    print("=" * 72)
    print("H1 v3 — sensitivity grid + soft catch-context")
    print("=" * 72)

    # Settings: (throw_leave_window, soft, label)
    # v2-baseline keeps the v2 hard UNCONTEXTED_ENTRY for direct comparison
    settings = [
        (3, False, "v2_baseline_throw3_hard"),
        (3, True,  "v3a_throw3_soft"),
        (5, True,  "v3b_throw5_soft"),
        (7, True,  "v3c_throw7_soft"),
    ]
    grid = []
    grid_evals = {}
    for throw_w, soft, label in settings:
        print(f"\n-- {label} --")
        h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"] = throw_w
        s = run_one_setting(throw_w, soft, label, write_artifacts=True)
        grid.append(s)
        # Per-setting hand-relevant eval
        ev = hand_relevant_eval_for_label(label)
        grid_evals[label] = ev
        for stem, v in s["videos"].items():
            print(f"  {stem}: n_links={v['n_links']}, "
                  f"ENTRY={v['event_counts']['ENTRY']}, "
                  f"EXIT={v['event_counts']['EXIT']}, "
                  f"AMBIG={v['event_counts']['AMBIGUOUS_POOL_EXIT']}, "
                  f"UNMATCHED={v['event_counts']['UNMATCHED_EXIT']}, "
                  f"NO_LEAVE={v['filtered_counts']['THROW_NO_LEAVE']}, "
                  f"UNCONTEXTED={v['uncontexted_entry']}, "
                  f"POTENTIAL={v['potential_entry']}, "
                  f"P={v['evaluation_vs_reviewed']['precision_hand_link']:.3f}, "
                  f"R={v['evaluation_vs_reviewed']['recall_hand_link']:.3f}")

    out = {"v3_settings": grid, "v3_hand_relevant_evals": grid_evals}
    (H1_DATA / "sens_grid.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {H1_DATA / 'sens_grid.json'}")


if __name__ == "__main__":
    main()
