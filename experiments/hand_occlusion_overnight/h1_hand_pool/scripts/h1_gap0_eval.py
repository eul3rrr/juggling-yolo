#!/usr/bin/env python3
"""H1 v2 — Hand-relevant evaluation.

The full reviewed-label set is an E6c candidate set, mostly mid-air (gap >= 1).
For H1 (a hand-only extractor), the right evaluation subset is gap=0 pairs
where the source tracklet ends and the candidate tracklet starts on the same
frame; these are the pairs most plausibly involving a hand transition.

We also report on:
  - gap=0 reviewed (the smallest hand-relevant subset)
  - gap<=1 reviewed (gap 0 or 1, may also include near-instant transitions)
  - gap<=2 reviewed (slightly broader)
  - the full set, for context

Output: prints and writes a JSON summary to data/hand_relevant_eval.json.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"


def load_reviewed():
    rows = []
    with (WORKTREE / "detections" / "stitch_review_labels.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["gap_frames"] = int(r["gap_frames"])
            r["source_tracklet"] = int(r["source_tracklet"])
            r["candidate_tracklet"] = int(r["candidate_tracklet"])
            rows.append(r)
    return rows


def load_h1_links():
    rows = []
    with (H1_DATA / "hand_links.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["from_frame"] = int(r["from_frame"])
            r["to_frame"] = int(r["to_frame"])
            r["tok_age_frames"] = int(r["tok_age_frames"]) if r["tok_age_frames"] else None
            rows.append(r)
    return rows


def subset_eval(links, reviewed, max_gap, label):
    sub = [r for r in reviewed if r["gap_frames"] <= max_gap]
    n_correct = sum(1 for r in sub if r["label"] == "correct")
    n_wrong = sum(1 for r in sub if r["label"] == "wrong")
    n_total = len(sub)

    # For each H1 link, find reviewed pairs it could match.
    # A H1 link (a, b) matches a reviewed pair (src, cand) if (a==src and b==cand)
    # OR (b==src and a==cand) — hand-link direction may be inverse.
    matched_correct = 0
    matched_wrong = 0
    matched_pairs = []
    for l in links:
        for r in sub:
            if r["video"] != l["video"].rsplit("/", 1)[-1] and not l["video"].endswith(r["video"].rsplit("/", 1)[-1]):
                # video field formats differ: links have "videos/<stem>.mp4" and reviewed have
                # "videos/<stem>.mp4" too. Normalize.
                pass
            if not l["video"].endswith(r["video"]):
                continue
            if (l["from_tid"] == r["source_tracklet"] and l["to_tid"] == r["candidate_tracklet"]) \
               or (l["from_tid"] == r["candidate_tracklet"] and l["to_tid"] == r["source_tracklet"]):
                if r["label"] == "correct":
                    matched_correct += 1
                else:
                    matched_wrong += 1
                matched_pairs.append((l, r))

    # Counts of H1 links NOT in reviewed (extra proposals)
    extra = len(links) - len(matched_pairs)

    precision = matched_correct / max(1, matched_correct + matched_wrong)
    recall = matched_correct / max(1, n_correct)

    return {
        "label": label,
        "max_gap": max_gap,
        "reviewed_total": n_total,
        "reviewed_correct": n_correct,
        "reviewed_wrong": n_wrong,
        "h1_links_total": len(links),
        "h1_links_matched_correct": matched_correct,
        "h1_links_matched_wrong": matched_wrong,
        "h1_links_extra": extra,
        "precision_hand_link": round(precision, 4),
        "recall_hand_link": round(recall, 4),
    }


def main():
    reviewed = load_reviewed()
    h1_links = load_h1_links()

    print("=" * 72)
    print("H1 v2 — hand-relevant evaluation against reviewed labels")
    print("=" * 72)
    print()
    print(f"Reviewed total: {len(reviewed)}")
    by_video = Counter(r["video"].rsplit("/", 1)[-1] for r in reviewed)
    print(f"  per video: {dict(by_video)}")
    print(f"H1 hand-links total: {len(h1_links)}")
    by_link_video = Counter(l["video"].rsplit("/", 1)[-1] for l in h1_links)
    print(f"  per video: {dict(by_link_video)}")
    print()

    subsets = [(0, "gap=0  (HAND-RELEVANT)"),
               (1, "gap<=1 (near-instant transitions)"),
               (2, "gap<=2 (broad hand-relevant)"),
               (99, "full set (mostly mid-air)")]

    results = []
    for max_gap, label in subsets:
        sub = [r for r in reviewed if r["gap_frames"] <= max_gap]
        h1_sub = [l for l in h1_links
                  if any(l["video"].endswith(rv.rsplit("/", 1)[-1])
                         for rv in {r["video"] for r in sub})]
        ev = subset_eval(h1_sub, sub, max_gap, label)
        results.append(ev)
        print(f"-- {label} --")
        print(f"  reviewed: total={ev['reviewed_total']}, correct={ev['reviewed_correct']}, wrong={ev['reviewed_wrong']}")
        print(f"  H1 links: total={ev['h1_links_total']}, matched correct={ev['h1_links_matched_correct']}, matched wrong={ev['h1_links_matched_wrong']}, extra={ev['h1_links_extra']}")
        print(f"  precision={ev['precision_hand_link']:.3f}, recall={ev['recall_hand_link']:.3f}")
        print()

    out = {
        "h1_version": "v2",
        "subsets": results,
    }
    (H1_DATA / "hand_relevant_eval.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {H1_DATA / 'hand_relevant_eval.json'}")


if __name__ == "__main__":
    main()
