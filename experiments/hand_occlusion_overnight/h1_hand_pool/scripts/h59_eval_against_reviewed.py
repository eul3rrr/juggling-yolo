#!/usr/bin/env python3
"""H59 — End-to-end precision/recall evaluation of the final operating point
(h7v3plus3 + H10 v11 v3) against the 113 manually reviewed pairs.

This is the first end-to-end evaluation of the FINAL recommended
operating point against the manual reviewed labels that have been
sitting on disk since the original E6c work.

The 113 reviewed pairs are pairs of tracklets that the E6c wide-universe
candidate generator proposed; a human (the project author) manually
labeled each as 'correct' or 'wrong'. These are the project's only
source of ground-truth labels for hand-off detection.

Operating point being evaluated:
  h7v3plus3 chain set = H1 v4d hand-links + E6c air-edges
                       + H22 YouTube 16->21 veto (-> 20->21)
                       + H26 2 identical H24-KEPT edges (7->10, 59->61)
                       + H7 v2 BALLISTIC re-classified as HAND_TRANSITION
                       + H15 v2 V_RECLASSIFIED for h7v3pure

Plus H10 v11 v3 (H56 v1) chain quality = non-linear g_cv penalty with
deadzone=0.5, ramp_end=1.0, w54=0.30, gated on n_arcs_clean >= 3.

For each reviewed pair (source, candidate):
  - Was it accepted by h7v3plus3 (in either direction)?
  - If yes, what was the H10 v11 v3 quality of the chain?

We report:
  - Per-direction matching (since reviewed pairs are ordered but
    h7v3plus3 edges can be either direction)
  - Per-gap-subset precision/recall (gap=0, gap<=1, full set)
  - Per-quality-band precision/recall (CONFIDENT vs UNCERTAIN vs LOW)
  - Per-edge-type precision/recall (HAND_TRANSITION, BALLISTIC, etc.)
  - Confusion matrix: H1 v4d-only vs h7v3plus3 on the same reviewed set

Outputs:
  - data/h59_eval_summary.json
  - data/h59_per_pair_eval.csv
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Video file basename in reviewed labels
REVIEWED_VIDEO_TO_STEM = {
    "identical_balls_trick_000_018.mp4": "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}


def normalize_video_field(s: str) -> str:
    """Convert 'videos/<stem>.mp4' or '<stem>.mp4' to bare stem."""
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


def load_h7v3plus3_edges() -> dict[str, set[tuple[int, int]]]:
    """Load h7v3plus3 chain edges. Returns {stem: {(from_tid, to_tid), ...}}."""
    out = {}
    for stem in STEMS:
        out[stem] = set()
        path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                a, b = int(r["from_tid"]), int(r["to_tid"])
                out[stem].add((a, b))
                out[stem].add((b, a))  # bidirectional for matching
    return out


def load_h1v4d_links() -> dict[str, set[tuple[int, int]]]:
    """Load H1 v4d hand-links (the original H1 output).

    Note: hand_links_v4_v4d_throw7_full.csv is a SINGLE file with
    a 'stem' column, not per-video. Load it once and split by stem.
    """
    out = {stem: set() for stem in STEMS}
    path = H1_DATA / "hand_links_v4_v4d_throw7_full.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            stem = r.get("stem") or normalize_video_field(r.get("video", ""))
            if stem not in out:
                continue
            a, b = int(r["from_tid"]), int(r["to_tid"])
            out[stem].add((a, b))
            out[stem].add((b, a))
    return out


def load_e6c_air_edges() -> dict[str, set[tuple[int, int]]]:
    """Load the original E6c accepted stitches (mid-air edges)."""
    out = {}
    for stem in STEMS:
        out[stem] = set()
        path = DETECTIONS / f"{stem}_norfair_dt50_hc5_accepted_stitches.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                a, b = int(r["source_tracklet"]), int(r["candidate_tracklet"])
                out[stem].add((a, b))
                out[stem].add((b, a))
    return out


def load_h10v11v3_per_chain() -> dict[str, dict[int, tuple[float, str]]]:
    """Load H10 v11 v3 (H56 v1) per-chain quality. Returns {stem: {chain_id: (q11, label)}}."""
    out = {}
    for stem in STEMS:
        out[stem] = {}
        path = H1_DATA / f"h10v11v3_nonlinear_w0.3_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                out[stem][int(r["chain_id"])] = (float(r["q11"]), r["label"])
    return out


def load_h7v3plus3_chain_membership() -> dict[str, dict[int, int]]:
    """Returns {stem: {tid: chain_id}} for the h7v3plus3 chain set."""
    out = {}
    for stem in STEMS:
        out[stem] = {}
        path = H1_DATA / f"h7v3plus3_chains_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                cid = int(r["chain_id"])
                tids = [int(t) for t in r["tids"].split(",") if t.strip()]
                for t in tids:
                    out[stem][t] = cid
    return out


def load_h7v3plus3_edge_type() -> dict[str, dict[tuple[int, int], str]]:
    """Returns {stem: {(from_tid, to_tid): edge_type}}."""
    out = {}
    for stem in STEMS:
        out[stem] = {}
        path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
        if not path.exists():
            continue
        with path.open() as fh:
            for r in csv.DictReader(fh):
                a, b = int(r["from_tid"]), int(r["to_tid"])
                out[stem][(a, b)] = r["edge_type"]
    return out


def evaluate(reviewed: list[dict],
             accepted: dict[str, set[tuple[int, int]]],
             h1v4d: dict[str, set[tuple[int, int]]],
             e6c: dict[str, set[tuple[int, int]]],
             q11: dict[str, dict[int, tuple[float, str]]],
             tid_to_cid: dict[str, dict[int, int]],
             edge_type: dict[str, dict[tuple[int, int], str]]) -> dict:
    """Run the full evaluation."""
    per_pair = []
    for r in reviewed:
        stem = r["stem"]
        pair = (r["source_tracklet"], r["candidate_tracklet"])
        reverse = (r["candidate_tracklet"], r["source_tracklet"])
        in_h7v3plus3 = pair in accepted[stem] or reverse in accepted[stem]
        in_h1v4d = pair in h1v4d[stem] or reverse in h1v4d[stem]
        in_e6c = pair in e6c[stem] or reverse in e6c[stem]
        # Edge type from h7v3plus3 (if any)
        et = edge_type[stem].get(pair) or edge_type[stem].get(reverse) or "NOT_IN_CHAIN"
        # Chain quality: find the chain this pair is in
        src_cid = tid_to_cid[stem].get(r["source_tracklet"])
        tgt_cid = tid_to_cid[stem].get(r["candidate_tracklet"])
        chain_id = src_cid if src_cid == tgt_cid and src_cid is not None else None
        if chain_id is not None and chain_id in q11[stem]:
            q11_val, q11_label = q11[stem][chain_id]
        else:
            q11_val, q11_label = None, "NOT_IN_CHAIN"
        per_pair.append({
            "stem": stem,
            "source": r["source_tracklet"],
            "candidate": r["candidate_tracklet"],
            "gap_frames": r["gap_frames"],
            "label": r["label"],
            "in_h7v3plus3": in_h7v3plus3,
            "in_h1v4d": in_h1v4d,
            "in_e6c": in_e6c,
            "edge_type": et,
            "chain_id": chain_id,
            "q11": q11_val,
            "q11_label": q11_label,
        })

    # Aggregate stats
    n_total = len(per_pair)
    n_correct = sum(1 for p in per_pair if p["label"] == "correct")
    n_wrong = sum(1 for p in per_pair if p["label"] == "wrong")

    # By gap subset
    by_gap = {}
    for max_gap, label in [(0, "gap=0"), (1, "gap<=1"), (3, "gap<=3"),
                            (10, "gap<=10"), (99, "full")]:
        sub = [p for p in per_pair if p["gap_frames"] <= max_gap]
        s = subset_stats(sub, label)
        s["max_gap"] = max_gap
        by_gap[label] = s

    # By stem
    by_stem = {}
    for stem in STEMS:
        sub = [p for p in per_pair if p["stem"] == stem]
        s = subset_stats(sub, stem)
        s["stem"] = stem
        by_stem[stem] = s

    # By quality band, restricted to only CONFIDENT chains
    confident_only = subset_stats(
        [p for p in per_pair if p["in_h7v3plus3"] and p["q11_label"] == "CONFIDENT"],
        "h7v3plus3 + CONFIDENT only")
    confident_or_uncertain = subset_stats(
        [p for p in per_pair if p["in_h7v3plus3"] and p["q11_label"] in ("CONFIDENT", "UNCERTAIN")],
        "h7v3plus3 + (CONFIDENT or UNCERTAIN)")

    # H1 v4d-only at any gap (corrected for the multi-file load)

    # By quality band (H10 v11 v3)
    by_q = defaultdict(lambda: {"TP": 0, "FP": 0, "reviewed_correct": 0, "reviewed_total": 0,
                                 "TP_recovered": 0})
    for p in per_pair:
        if p["in_h7v3plus3"]:
            band = p["q11_label"] or "UNKNOWN"
            if p["label"] == "correct":
                by_q[band]["TP"] += 1
            else:
                by_q[band]["FP"] += 1
        if p["label"] == "correct":
            band2 = p["q11_label"] or "UNKNOWN"
            by_q[band2]["TP_recovered"] += 1
        by_q[p["q11_label"] or "UNKNOWN"]["reviewed_total"] += 1
        if p["label"] == "correct":
            by_q[p["q11_label"] or "UNKNOWN"]["reviewed_correct"] += 1

    # By edge type
    by_et = defaultdict(lambda: {"TP": 0, "FP": 0, "TN": 0, "FN": 0})
    for p in per_pair:
        if p["in_h7v3plus3"]:
            if p["label"] == "correct":
                by_et[p["edge_type"]]["TP"] += 1
            else:
                by_et[p["edge_type"]]["FP"] += 1
        else:
            if p["label"] == "correct":
                by_et[p["edge_type"]]["FN"] += 1
            else:
                by_et[p["edge_type"]]["TN"] += 1

    # H1 v4d alone baseline
    h1v4d_only = subset_stats([p for p in per_pair if p["in_h1v4d"]], "H1 v4d only (gap=any)")
    e6c_only = subset_stats([p for p in per_pair if p["in_e6c"]], "E6c only (gap=any)")
    h7v3plus3_all = subset_stats([p for p in per_pair if p["in_h7v3plus3"]], "h7v3plus3 (gap=any)")

    return {
        "n_total": n_total,
        "n_correct": n_correct,
        "n_wrong": n_wrong,
        "by_gap": by_gap,
        "by_stem": by_stem,
        "by_quality_band": dict(by_q),
        "by_edge_type": dict(by_et),
        "h1v4d_only": h1v4d_only,
        "e6c_only": e6c_only,
        "h7v3plus3_all_gaps": h7v3plus3_all,
        "h7v3plus3_confident_only": confident_only,
        "h7v3plus3_confident_or_uncertain": confident_or_uncertain,
        "per_pair": per_pair,
    }


def subset_stats(sub: list[dict], label: str) -> dict:
    n_total = len(sub)
    n_correct = sum(1 for p in sub if p["label"] == "correct")
    n_wrong = sum(1 for p in sub if p["label"] == "wrong")
    TP = sum(1 for p in sub if p["in_h7v3plus3"] and p["label"] == "correct")
    FP = sum(1 for p in sub if p["in_h7v3plus3"] and p["label"] == "wrong")
    FN = sum(1 for p in sub if not p["in_h7v3plus3"] and p["label"] == "correct")
    precision = TP / max(1, TP + FP)
    recall = TP / max(1, n_correct)
    fpr = FP / max(1, n_wrong)
    return {
        "label": label,
        "n_total": n_total,
        "n_correct": n_correct,
        "n_wrong": n_wrong,
        "TP": TP,
        "FP": FP,
        "FN": FN,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "FPR": round(fpr, 4),
    }


def main() -> None:
    print("=" * 72)
    print("H59 — end-to-end precision/recall of h7v3plus3 + H10 v11 v3")
    print("=" * 72)
    reviewed = load_reviewed()
    h7v3plus3 = load_h7v3plus3_edges()
    h1v4d = load_h1v4d_links()
    e6c = load_e6c_air_edges()
    q11 = load_h10v11v3_per_chain()
    tid_to_cid = load_h7v3plus3_chain_membership()
    edge_type = load_h7v3plus3_edge_type()

    print(f"Reviewed pairs: {len(reviewed)}")
    print(f"  per video: {dict(Counter(r['stem'] for r in reviewed))}")
    print(f"h7v3plus3 edges: {sum(len(s) // 2 for s in h7v3plus3.values())} (bidirectional)")
    print(f"H1 v4d hand-links: {sum(len(s) // 2 for s in h1v4d.values())}")
    print(f"E6c air edges: {sum(len(s) // 2 for s in e6c.values())}")
    print()

    result = evaluate(reviewed, h7v3plus3, h1v4d, e6c, q11, tid_to_cid, edge_type)

    # Print summary
    print("=== Per-gap subset ===")
    for label, s in result["by_gap"].items():
        print(f"  {label}: reviewed={s['n_total']} (correct={s['n_correct']}, wrong={s['n_wrong']}), "
              f"TP={s['TP']}, FP={s['FP']}, FN={s['FN']}, "
              f"precision={s['precision']:.3f}, recall={s['recall']:.3f}, FPR={s['FPR']:.3f}")

    print("\n=== Per-quality-band (H10 v11 v3) ===")
    for band, s in result["by_quality_band"].items():
        if s["reviewed_total"] == 0:
            continue
        if s["TP"] + s["FP"] == 0:
            prec_str = "n/a"
        else:
            prec_str = f"{s['TP'] / (s['TP'] + s['FP']):.3f}"
        print(f"  {band}: reviewed={s['reviewed_total']} (correct={s['reviewed_correct']}), "
              f"TP={s['TP']}, FP={s['FP']}, prec={prec_str}, "
              f"recovered={s['TP_recovered']}")

    print("\n=== Per-edge-type ===")
    for et, s in result["by_edge_type"].items():
        if s["TP"] + s["FP"] + s["FN"] + s["TN"] == 0:
            continue
        if s["TP"] + s["FP"] == 0:
            prec_str = "n/a"
        else:
            prec_str = f"{s['TP'] / (s['TP'] + s['FP']):.3f}"
        print(f"  {et}: TP={s['TP']}, FP={s['FP']}, FN={s['FN']}, TN={s['TN']}, prec={prec_str}")

    print("\n=== Single-method summary (any gap) ===")
    for k in ("h1v4d_only", "e6c_only", "h7v3plus3_all_gaps",
              "h7v3plus3_confident_only", "h7v3plus3_confident_or_uncertain"):
        s = result[k]
        print(f"  {s['label']}: precision={s['precision']:.3f}, recall={s['recall']:.3f}, "
              f"FPR={s['FPR']:.3f} (TP={s['TP']}, FP={s['FP']}, FN={s['FN']})")

    print("\n=== Per-stem (full set) ===")
    for stem, s in result["by_stem"].items():
        print(f"  {stem}: reviewed={s['n_total']} (correct={s['n_correct']}, wrong={s['n_wrong']}), "
              f"precision={s['precision']:.3f}, recall={s['recall']:.3f}, FPR={s['FPR']:.3f}")

    # Write outputs
    (H1_DATA / "h59_per_pair_eval.csv").write_text(
        "stem,source,candidate,gap_frames,label,in_h7v3plus3,in_h1v4d,in_e6c,"
        "edge_type,chain_id,q11,q11_label\n" +
        "\n".join(
            f"{p['stem']},{p['source']},{p['candidate']},{p['gap_frames']},{p['label']},"
            f"{p['in_h7v3plus3']},{p['in_h1v4d']},{p['in_e6c']},"
            f"{p['edge_type']},{p['chain_id']},{p['q11']},{p['q11_label']}"
            for p in result["per_pair"]
        ) + "\n"
    )
    # JSON summary (without per_pair to keep small)
    summary = {k: v for k, v in result.items() if k != "per_pair"}
    (H1_DATA / "h59_eval_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nWrote {H1_DATA / 'h59_eval_summary.json'}")
    print(f"Wrote {H1_DATA / 'h59_per_pair_eval.csv'}")


if __name__ == "__main__":
    main()
