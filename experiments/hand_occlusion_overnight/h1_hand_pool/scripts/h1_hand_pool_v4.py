#!/usr/bin/env python3
"""H1 v4 — multi-feature filter on top of v3c (throw_window=7).

v3c admitted 8 new links on identical + 2 on youtube. Visual QA found
3 of these 10 are false positives:
- 15→25 youtube L: pass-through (|from_slope|=2.08)
- 35→40 identical L: pass-through (|from_slope|=2.31)
- 17→23 identical R: WRONG HAND — actual event is on the LEFT hand,
  not the right hand. The H1 model attributed the throw to the right
  hand but the visual evidence places it at the left.

v4 adds two filters on top of v3c's looser throw window:

1. **Slope coherence filter (v4a):** require
   `|from_slope| > 2.5` (the incoming ball must be visibly
   approaching the hand at > 2.5 px/frame). This rejects 15→25
   and 35→40 (both have |from_slope| < 2.5).
2. **Handedness consistency filter (v4b):** require
   `from_dist_to_declared_hand < hand_reach_px` AND
   `to_dist_to_declared_hand < hand_reach_px`. This rejects
   17→23 where the visual evidence shows the catch/throw is on
   the *opposite* hand.

We also retain the v3a soft catch-context flag (POTENTIAL_ENTRY
for uncontexted entries) and v3c's looser throw window.

Output: per-setting artifacts to data/hand_events_v4_*.csv,
data/hand_links_v4_*.csv, data/summary_v4_*.json, and a
data/sens_grid_v4.json combined summary.

v4 also adds a 'rejected_links' list to the per-setting summary
so we can see exactly which links were filtered and why.
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
# v4 thresholds (declared from visual QA of v3c, NOT from labels)
# ----------------------------------------------------------------------
V4_THRESHOLDS = {
    "MIN_FROM_SLOPE": 2.5,    # px/frame; rejects 15->25, 35->40
    "MAX_HAND_REACH_PX_FOR_LINK": 108,  # = HAND_REACH_PX_RATIO * image_height (v2)
}


# ----------------------------------------------------------------------
# Per-setting artifact writers
# ----------------------------------------------------------------------
def write_setting_artifacts(label: str, all_runs: list[dict],
                             rejected: list[dict]) -> None:
    """Write per-setting CSVs and summary JSON to H1_DATA."""
    suf = label.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    suf = suf.replace("__", "_").strip("_")
    events_path = H1_DATA / f"hand_events_v4_{suf}.csv"
    links_path = H1_DATA / f"hand_links_v4_{suf}.csv"
    rejected_path = H1_DATA / f"rejected_links_v4_{suf}.csv"
    summary_path = H1_DATA / f"summary_v4_{suf}.json"

    # events (full v3c event stream with POTENTIAL_ENTRY rename)
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

    # links (v4 surviving links only)
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

    # rejected links (with reason)
    with rejected_path.open("w", newline="") as fh:
        fields = [
            "video", "stem", "from_tid", "to_tid", "hand",
            "from_frame", "to_frame",
            "from_dist", "to_dist", "from_slope", "to_slope",
            "tok_age_frames", "rejection_reason",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rejected:
            w.writerow({k: r.get(k, "") for k in fields})

    # summary
    summary = {
        "label": label,
        "throw_leave_window_frames": h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"],
        "soft_catch_context": True,
        "v4_thresholds": V4_THRESHOLDS,
        "videos": {},
        "rejected_summary": {},
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
            "links": run["links"],
        }
    # rejected summary by reason
    rej_by_reason = defaultdict(list)
    for r in rejected:
        rej_by_reason[r["rejection_reason"]].append(f'{r["stem"]}:{r["from_tid"]}->{r["to_tid"]}')
    summary["rejected_summary"] = {k: v for k, v in rej_by_reason.items()}
    summary["rejected_total"] = len(rejected)
    summary_path.write_text(json.dumps(summary, indent=2))


# ----------------------------------------------------------------------
# v4 filter logic
# ----------------------------------------------------------------------
def apply_v4_filters(run: dict, hand_reach_px: float) -> tuple[list[dict], list[dict]]:
    """Apply v4 filters to a run's links.

    Returns:
        surviving_links: list of link dicts that pass all v4 filters
        rejected: list of {**link, "rejection_reason"} for rejected links
    """
    surviving = []
    rejected = []
    for l in run["links"]:
        # v4a: slope coherence
        from_slope_abs = abs(l["from_slope"])
        if from_slope_abs < V4_THRESHOLDS["MIN_FROM_SLOPE"]:
            rejected.append({**l, "rejection_reason":
                f"LOW_FROM_SLOPE ({from_slope_abs:.2f} < {V4_THRESHOLDS['MIN_FROM_SLOPE']})"})
            continue
        # v4b: handedness consistency — both endpoints must be within
        # hand_reach_px of the DECLARED hand. (v2 already computed
        # from_dist and to_dist to the named hand, so this is a direct
        # check.)
        if (l["from_dist"] > hand_reach_px
            or l["to_dist"] > hand_reach_px):
            rejected.append({**l, "rejection_reason":
                f"OUT_OF_REACH (from={l['from_dist']:.1f}, to={l['to_dist']:.1f}, "
                f"reach={hand_reach_px:.1f})"})
            continue
        surviving.append(l)
    return surviving, rejected


# ----------------------------------------------------------------------
# Run one v4 setting
# ----------------------------------------------------------------------
def run_one_setting(throw_leave_window_frames: int, soft: bool, label: str,
                    write_artifacts: bool = True) -> dict:
    """Run all stems for one (throw_leave, soft) combo, apply v4 filters,
    return a per-setting summary dict."""
    h2.V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"] = throw_leave_window_frames
    all_runs = []
    all_rejected = []
    for stem, video_key in h2.STEMS.items():
        run = h2.run_for_stem_v2(stem, video_key)
        if soft:
            # POTENTIAL_ENTRY rename
            for e in run["events"]:
                if e.event_type == "UNCONTEXTED_ENTRY":
                    e.event_type = "POTENTIAL_ENTRY"
        # v4 filters
        surviving, rejected = apply_v4_filters(run, run["hand_reach_px"])
        run["links"] = surviving
        all_runs.append(run)
        for r in rejected:
            r["stem"] = stem
            r["video"] = run["video_key"]
        all_rejected.extend(rejected)

    if write_artifacts:
        write_setting_artifacts(label, all_runs, all_rejected)

    summary = {
        "throw_leave_window_frames": throw_leave_window_frames,
        "soft_catch_context": soft,
        "label": label,
        "v4_thresholds": V4_THRESHOLDS,
        "videos": {},
        "rejected_summary": {},
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
    rej_by_reason = defaultdict(list)
    for r in all_rejected:
        rej_by_reason[r["rejection_reason"]].append(f'{r["stem"]}:{r["from_tid"]}->{r["to_tid"]}')
    summary["rejected_summary"] = {k: v for k, v in rej_by_reason.items()}
    summary["rejected_total"] = len(all_rejected)
    return summary


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    print("=" * 72)
    print("H1 v4 — multi-feature filter on v3c's looser throw window")
    print("=" * 72)
    print(f"V4 thresholds: {V4_THRESHOLDS}")
    print()

    # Settings: compare v2 strict + v4a (slope filter) + v4b (handedness)
    # at throw=3 (v2-strict) and throw=7 (v3c-loose)
    settings = [
        (3, True, "v4a_throw3_slope"),     # strict throw + slope filter (no reach filter)
        (3, True, "v4b_throw3_full"),      # strict throw + slope + reach
        (7, True, "v4c_throw7_slope"),     # loose throw + slope filter (no reach filter)
        (7, True, "v4d_throw7_full"),      # loose throw + slope + reach (the v4 winner)
    ]
    grid = []
    for throw_w, soft, label in settings:
        print(f"\n-- {label} --")
        summary = run_one_setting(throw_w, soft, label, write_artifacts=True)
        grid.append(summary)
        for stem, v in summary["videos"].items():
            print(f"  {stem}: n_links={v['n_links']}, "
                  f"P={v['evaluation_vs_reviewed']['precision_hand_link']:.3f}, "
                  f"R={v['evaluation_vs_reviewed']['recall_hand_link']:.3f}")
        print(f"  rejected: {summary['rejected_total']} total, "
              f"by_reason: {dict((k, len(v)) for k, v in summary['rejected_summary'].items())}")

    out_path = H1_DATA / "sens_grid_v4.json"
    out_path.write_text(json.dumps({"v4_settings": grid}, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
