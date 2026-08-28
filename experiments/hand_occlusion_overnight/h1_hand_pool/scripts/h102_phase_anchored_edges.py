#!/usr/bin/env python3
"""H102 — Phase-anchored edge ground truth.

Hypothesis: the H93 corrected ground truth (21 substantial phases, each
labeled JUGGLING / STATIC_HOLD / OTHER_CROSSED_ARM) can be used as a
*phase anchor* for the 113 manually reviewed edges. For each reviewed
pair (source_tracklet, candidate_tracklet), we compute the midgap frame
(source_end + (candidate_start - source_end) / 2) and ask which H93
phase that frame falls into. The H93 verdict for that phase becomes the
*expected* answer to: "is this edge a real catch-throw (JUGGLING) or a
false positive (STATIC_HOLD)?"

This produces a 3-way cross-tabulation:
  reviewed_label x phase_anchor_verdict x h7v3plus3_accepted

Question: do the H93 phase labels agree with the manual review labels,
or do they disagree? Are there any reviewed pairs whose phase anchor
predicts a different answer than the manual reviewer gave?

Question: are the H96 v2 stack's perfect phase-level metrics (17/4/0/0)
preserved when measured at the EDGE level inside each phase?

Question: do the H93 STATIC_HOLD phases contain *any* correct edges
(real ball motion captured during the static phase)?

Smallest reproduction: pure-Python, no video processing, no detector
re-runs. Uses the existing h7v3plus3 chain set, the H93 corrected GT,
and the 113 reviewed pairs. Produces:
  - data/h102_per_pair.csv (per reviewed pair: phase_anchor, verdict, h7v3plus3)
  - data/h102_confusion.json (3-way cross-tabulation)
  - data/h102_per_phase.csv (per phase: edges-in-phase counts)
  - reports/h102_report.md (written by separate report script)

Outputs:
  data/h102_summary.json
  data/h102_per_pair.csv
  data/h102_per_phase.csv
  data/h102_confusion.json
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Map video file basename in review labels to stem
REVIEWED_VIDEO_TO_STEM = {
    "identical_balls_trick_000_018.mp4": "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}


def normalize_video_field(s: str) -> str:
    s = s.rsplit("/", 1)[-1]
    return REVIEWED_VIDEO_TO_STEM.get(s, s.replace(".mp4", ""))


def load_reviewed() -> list[dict]:
    """Load the 113 manually reviewed pairs."""
    out = []
    with (DETECTIONS / "stitch_review_labels.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["source_tracklet"] = int(r["source_tracklet"])
            r["candidate_tracklet"] = int(r["candidate_tracklet"])
            r["gap_frames"] = int(r["gap_frames"])
            r["stem"] = normalize_video_field(r["video"])
            out.append(r)
    return out


def load_stitches() -> dict[str, dict[tuple[int, int], dict]]:
    """Load the E6c stitches. Returns {stem: {(src, tgt): {src_end_frame, cand_start_frame, ...}}}."""
    out = {stem: {} for stem in STEMS}
    for stem in STEMS:
        path = DETECTIONS / f"{stem}_norfair_dt50_hc5_stitches.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                key = (int(r["source_tracklet"]), int(r["candidate_tracklet"]))
                out[stem][key] = {
                    "src_end_frame": int(r["source_end_frame"]),
                    "cand_start_frame": int(r["candidate_start_frame"]),
                    "gap_frames": int(r["gap_frames"]),
                    "prediction_error": float(r["prediction_error"]),
                }
    return out


def load_h93_phases() -> dict[str, list[dict]]:
    """Load the H93 corrected ground truth. Returns {stem: [{start, end, verdict, key}, ...]}."""
    path = H1_DATA / "h93_multi_rater_qa.json"
    with path.open() as fh:
        h93 = json.load(fh)
    gt = h93["corrected_ground_truth"]
    out = {stem: [] for stem in STEMS}
    for k, verdict in gt.items():
        # k = "<stem>_<start>_<end>"
        parts = k.rsplit("_", 2)
        stem, start, end = parts[0], int(parts[1]), int(parts[2])
        if stem not in out:
            continue
        out[stem].append({
            "start": start,
            "end": end,
            "verdict": verdict,
            "key": k,
        })
    # Sort by start
    for stem in out:
        out[stem].sort(key=lambda p: p["start"])
    return out


def load_h7v3plus3_edges() -> dict[str, set[tuple[int, int]]]:
    """Load h7v3plus3 chain edges. Returns {stem: {(from_tid, to_tid), ...}}."""
    out = {stem: set() for stem in STEMS}
    for stem in STEMS:
        path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                a, b = int(r["from_tid"]), int(r["to_tid"])
                out[stem].add((a, b))
                out[stem].add((b, a))  # bidirectional
    return out


def load_h7v3plus3_edge_type() -> dict[str, dict[tuple[int, int], str]]:
    """Returns {stem: {(from_tid, to_tid): edge_type}} (directed)."""
    out = {stem: {} for stem in STEMS}
    for stem in STEMS:
        path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                a, b = int(r["from_tid"]), int(r["to_tid"])
                out[stem][(a, b)] = r["edge_type"]
    return out


def find_phase(midgap: int, phases: list[dict]) -> dict | None:
    """Find the H93 phase containing the midgap frame (inclusive on both ends)."""
    for p in phases:
        if p["start"] <= midgap <= p["end"]:
            return p
    return None


def main() -> None:
    print("=" * 72)
    print("H102 — phase-anchored edge ground truth")
    print("=" * 72)

    reviewed = load_reviewed()
    stitches = load_stitches()
    h93_phases = load_h93_phases()
    h7v3plus3 = load_h7v3plus3_edges()
    edge_type = load_h7v3plus3_edge_type()

    print(f"Reviewed pairs: {len(reviewed)}")
    print(f"  per video: {dict(Counter(r['stem'] for r in reviewed))}")
    for stem in STEMS:
        print(f"H93 phases {stem}: {len(h93_phases[stem])}")
    h7v3plus3_count = sum(len(s) // 2 for s in h7v3plus3.values())
    print(f"h7v3plus3 edges: {h7v3plus3_count} (bidirectional: {h7v3plus3_count * 2})")

    # Per-pair evaluation
    per_pair = []
    n_matched = 0
    n_no_stitch = 0
    n_no_phase = 0
    for r in reviewed:
        stem = r["stem"]
        pair = (r["source_tracklet"], r["candidate_tracklet"])
        reverse = (r["candidate_tracklet"], r["source_tracklet"])
        # Stitch lookup (either direction)
        stitch = stitches[stem].get(pair) or stitches[stem].get(reverse)
        if stitch is None:
            n_no_stitch += 1
            midgap = None
            src_end = None
            cand_start = None
        else:
            n_matched += 1
            src_end = stitch["src_end_frame"]
            cand_start = stitch["cand_start_frame"]
            midgap = (src_end + cand_start) // 2
        # Phase anchor
        if midgap is not None:
            phase = find_phase(midgap, h93_phases[stem])
        else:
            phase = None
        if phase is None:
            n_no_phase += 1
        # h7v3plus3 acceptance (either direction)
        in_h7v3plus3 = pair in h7v3plus3[stem] or reverse in h7v3plus3[stem]
        et = edge_type[stem].get(pair) or edge_type[stem].get(reverse) or "NOT_IN_CHAIN"
        per_pair.append({
            "stem": stem,
            "source": r["source_tracklet"],
            "candidate": r["candidate_tracklet"],
            "gap_frames": r["gap_frames"],
            "label": r["label"],
            "src_end_frame": src_end,
            "cand_start_frame": cand_start,
            "midgap_frame": midgap,
            "phase_key": phase["key"] if phase else None,
            "phase_start": phase["start"] if phase else None,
            "phase_end": phase["end"] if phase else None,
            "phase_verdict": phase["verdict"] if phase else None,
            "phase_anchor": "ANCHORED" if phase else "UNANCHORED",
            "in_h7v3plus3": in_h7v3plus3,
            "edge_type": et,
        })

    print(f"  stitch lookup: {n_matched} matched, {n_no_stitch} not in stitches.csv")
    print(f"  phase anchor: {len(per_pair) - n_no_phase} anchored, {n_no_phase} unanchored")

    # Save per-pair
    out_path = H1_DATA / "h102_per_pair.csv"
    with out_path.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(per_pair[0].keys()))
        wr.writeheader()
        wr.writerows(per_pair)
    print(f"  per-pair CSV: {out_path}")

    # Per-phase aggregation
    per_phase = []
    for stem in STEMS:
        for p in h93_phases[stem]:
            anchored = [pp for pp in per_pair
                        if pp["stem"] == stem and pp["phase_key"] == p["key"]]
            in_chain = [pp for pp in anchored if pp["in_h7v3plus3"]]
            correct = [pp for pp in anchored if pp["label"] == "correct"]
            wrong = [pp for pp in anchored if pp["label"] == "wrong"]
            in_chain_correct = [pp for pp in in_chain if pp["label"] == "correct"]
            in_chain_wrong = [pp for pp in in_chain if pp["label"] == "wrong"]
            per_phase.append({
                "stem": stem,
                "phase_key": p["key"],
                "phase_start": p["start"],
                "phase_end": p["end"],
                "phase_verdict": p["verdict"],
                "n_reviewed_in_phase": len(anchored),
                "n_correct_in_phase": len(correct),
                "n_wrong_in_phase": len(wrong),
                "n_in_h7v3plus3": len(in_chain),
                "n_in_h7v3plus3_correct": len(in_chain_correct),
                "n_in_h7v3plus3_wrong": len(in_chain_wrong),
                "phase_precision": (len(in_chain_correct) / max(1, len(in_chain))),
                "phase_recall": (len(in_chain_correct) / max(1, len(correct))),
            })
    out_path = H1_DATA / "h102_per_phase.csv"
    with out_path.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(per_phase[0].keys()))
        wr.writeheader()
        wr.writerows(per_phase)
    print(f"  per-phase CSV: {out_path}")

    # 3-way confusion: reviewed_label x phase_anchor_verdict x h7v3plus3
    # Restricted to ANCHORED pairs only
    anchored = [pp for pp in per_pair if pp["phase_anchor"] == "ANCHORED"]
    print(f"\n3-way confusion (restricted to {len(anchored)} ANCHORED reviewed pairs):")
    confusion = defaultdict(lambda: defaultdict(int))
    # 3D: (phase_verdict, label, in_h7v3plus3) -> count
    cell3d = defaultdict(int)
    for pp in anchored:
        cell3d[(pp["phase_verdict"], pp["label"], pp["in_h7v3plus3"])] += 1
    # 2D: (phase_verdict, label) -> count
    cell2d = defaultdict(int)
    for pp in anchored:
        cell2d[(pp["phase_verdict"], pp["label"])] += 1
    # Edge-level precision/recall in JUGGLING vs STATIC_HOLD
    by_phase = {}
    for verdict in ("JUGGLING", "STATIC_HOLD", "OTHER_CROSSED_ARM"):
        sub = [pp for pp in anchored if pp["phase_verdict"] == verdict]
        n_total = len(sub)
        n_correct = sum(1 for pp in sub if pp["label"] == "correct")
        n_wrong = sum(1 for pp in sub if pp["label"] == "wrong")
        in_chain = [pp for pp in sub if pp["in_h7v3plus3"]]
        TP = sum(1 for pp in in_chain if pp["label"] == "correct")
        FP = sum(1 for pp in in_chain if pp["label"] == "wrong")
        FN = sum(1 for pp in sub if pp["label"] == "correct" and not pp["in_h7v3plus3"])
        prec = TP / max(1, TP + FP)
        rec = TP / max(1, n_correct)
        by_phase[verdict] = {
            "n_total": n_total,
            "n_correct": n_correct,
            "n_wrong": n_wrong,
            "n_in_h7v3plus3": len(in_chain),
            "TP": TP,
            "FP": FP,
            "FN": FN,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
        }

    # Agreement: do the H93 phase verdict and the manual review label agree?
    n_agree = 0
    n_disagree = 0
    n_agree_per_phase = Counter()
    n_disagree_per_phase = Counter()
    for pp in anchored:
        # Agreement:
        #   phase JUGGLING + label correct = agree (real edge in real phase)
        #   phase STATIC_HOLD + label wrong = agree (false edge in static phase)
        #   phase OTHER + label correct = agree (correct edge in crossed-arm)
        #   phase OTHER + label wrong = ambiguous (crossed-arm is messy)
        is_agree = (
            (pp["phase_verdict"] == "JUGGLING" and pp["label"] == "correct")
            or (pp["phase_verdict"] == "STATIC_HOLD" and pp["label"] == "wrong")
        )
        if is_agree:
            n_agree += 1
            n_agree_per_phase[pp["phase_verdict"]] += 1
        else:
            n_disagree += 1
            n_disagree_per_phase[pp["phase_verdict"]] += 1

    confusion_summary = {
        "n_anchored": len(anchored),
        "n_agree": n_agree,
        "n_disagree": n_disagree,
        "agreement_rate": round(n_agree / max(1, len(anchored)), 4),
        "agree_per_phase": dict(n_agree_per_phase),
        "disagree_per_phase": dict(n_disagree_per_phase),
        "by_phase_anchor": by_phase,
        "cell3d": {f"{p[0]}|{p[1]}|{p[2]}": v for p, v in cell3d.items()},
        "cell2d": {f"{p[0]}|{p[1]}": v for p, v in cell2d.items()},
    }
    out_path = H1_DATA / "h102_confusion.json"
    with out_path.open("w") as fh:
        json.dump(confusion_summary, fh, indent=2)
    print(f"  confusion JSON: {out_path}")

    # Print key results
    print("\n=== Per-phase-verdict (edge-level) ===")
    for verdict, s in by_phase.items():
        print(f"  {verdict}: reviewed={s['n_total']} (correct={s['n_correct']}, wrong={s['n_wrong']}), "
              f"TP={s['TP']}, FP={s['FP']}, FN={s['FN']}, "
              f"precision={s['precision']:.3f}, recall={s['recall']:.3f}")

    print(f"\n=== Agreement: H93 phase verdict vs manual review label ===")
    print(f"  Anchored pairs: {len(anchored)}")
    print(f"  Agree: {n_agree} ({100*n_agree/max(1,len(anchored)):.1f}%)")
    print(f"  Disagree: {n_disagree} ({100*n_disagree/max(1,len(anchored)):.1f}%)")
    print(f"  Agree per phase: {dict(n_agree_per_phase)}")
    print(f"  Disagree per phase: {dict(n_disagree_per_phase)}")

    # Save summary
    summary = {
        "method": "H102: phase-anchored edge ground truth (113 reviewed pairs x 21 H93 phases)",
        "n_reviewed_total": len(reviewed),
        "n_matched_to_stitch": n_matched,
        "n_anchored_to_h93_phase": len(anchored),
        "n_unanchored": n_no_phase,
        "n_h7v3plus3_edges_bidirectional": h7v3plus3_count * 2,
        "agreement": {
            "n_agree": n_agree,
            "n_disagree": n_disagree,
            "agreement_rate": round(n_agree / max(1, len(anchored)), 4),
            "agree_per_phase": dict(n_agree_per_phase),
            "disagree_per_phase": dict(n_disagree_per_phase),
        },
        "by_phase_anchor": by_phase,
        "per_phase": per_phase,
    }
    out_path = H1_DATA / "h102_summary.json"
    with out_path.open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"  summary JSON: {out_path}")
    print()


if __name__ == "__main__":
    main()
