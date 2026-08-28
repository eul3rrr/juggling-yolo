#!/usr/bin/env python3
"""H20: Stricter in-hand rejection for H17 strict V-shape positives.

HYPOTHESIS:
  H17's visual QA found 7 FALSE positives in 16 strict positives. The H17
  report (h17_report.md) explicitly notes:

    "all 7 FALSE positives all have a similar failure pattern: the V-apex
     is interpolated as a position 1-10 px from a hand, but the source/
     target tracklets are actually in-hand or stationary detections, not
     airborne catches."

  The current strict filter checks that ONE endpoint is within 108 px of
  the V-apex hand. It does NOT check whether BOTH endpoints are stuck
  in the same hand (held ball continuity) — which is the actual failure
  pattern.

  H20 hypothesis: rejecting candidates where BOTH the source's tail
  frames AND the target's head frames are all within IN_HAND_PX=30 of
  the same hand will eliminate these in-hand held-ball false positives
  WITHOUT rejecting real catch+throw events (where exactly one endpoint
  is in a hand and the other endpoint is rising/falling through the
  air).

  Thresholds (declared from physical geometry, NOT tuned to labels):
  - IN_HAND_PX = 30: 30 px is well inside the 108 px reach radius and
    corresponds to "ball at the hand, not just near the hand"
  - MIN_IN_HAND_FRAMES = 2: of the last/first 3 frames, at least 2 must
    be in-hand (allows for one detection dropout during a held phase)
  - IN_HAND_REJECT_DIST_PX = 30: source and target in-hand checks must
    both be at the same hand (same y-range as the V-apex hand)

  Expected: most of the 7 H17 FPs should be REJECTED, while the 5 REAL
  and 3 PARTIAL positives should be KEPT.

VERIFICATION:
  - Compute in-hand flags for all 151 H17 strict positives.
  - Re-evaluate the 16 contact sheets that H17 visually QA'd.
  - Sensitivity grid on IN_HAND_PX in {20, 30, 40, 50} and
    MIN_IN_HAND_FRAMES in {1, 2, 3}.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H20_OUT = H1_DIR / "data"
H20_CSV = H20_OUT / "h20_strict_v_shape_positives_inhand.csv"
H20_SUMMARY = H20_OUT / "h20_summary.json"

H20_THRESHOLDS = {
    "IN_HAND_PX": 30,                  # px from wrist to count as "in hand"
    "MIN_IN_HAND_FRAMES": 3,           # of last/first 3 frames, >= 3 must be in-hand
    "IN_HAND_REJECT_DIST_PX": 30,      # tolerance for "same hand"
    "TAIL_FRAMES": 3,                  # check last 3 frames of source
    "HEAD_FRAMES": 3,                  # check first 3 frames of target
    "MAX_GAP_VEL_PX_PER_FRAME": 70.0,  # max plausible ball speed across gap
    "APEX_SRC_DIST_REJECT_PX": 20.0,   # V-apex within this many px of source end
}

# The 16 contact sheets that H17 visually QA'd. The visual verdict is
# encoded in h17_report.md's QA table.
H17_QA_VERDICTS = {
    # identical (10 contact sheets)
    ("identical_balls_trick_000_018", 35, 40): "UNCLEAR",       # 1
    ("identical_balls_trick_000_018", 6, 15): "REAL",          # 3
    ("identical_balls_trick_000_018", 4, 8): "FALSE",          # 4 in-hand
    ("identical_balls_trick_000_018", 35, 38): "FALSE",        # 5 source high
    ("identical_balls_trick_000_018", 56, 57): "REAL",         # 6
    ("identical_balls_trick_000_018", 54, 57): "REAL",         # 9
    ("identical_balls_trick_000_018", 66, 68): "FALSE",        # 10 source held, target at hand
    ("identical_balls_trick_000_018", 29, 33): "PARTIAL",      # 13
    ("identical_balls_trick_000_018", 13, 15): "PARTIAL",      # 14
    ("identical_balls_trick_000_018", 56, 58): "REAL",         # 15
    # youtube (6 contact sheets)
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 15, 25): "REAL",  # 2
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 10, 11): "FALSE",  # 7 apex high
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 20, 21): "REAL",  # 8
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 23, 24): "PARTIAL",  # 11
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 1, 10): "FALSE",   # 12 apex at shoulder
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 24, 27): "FALSE",  # 16 apex at torso
}


def load_per_det_tracklet(stem: str, tid: int) -> list[tuple]:
    """Return list of (frame, x, y, conf) for a tracklet from Norfair CSV."""
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if int(r["track_id"]) != tid:
                continue
            try:
                fr = int(r["frame"])
                x = float(r["center_x"])
                y = float(r["center_y"])
                c = float(r["confidence"])
                out.append((fr, x, y, c))
            except (ValueError, KeyError):
                continue
    out.sort()
    return out


def load_wrist_frames(stem: str) -> dict:
    """Load wrist positions keyed by frame."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                fr = int(r["frame"])
                lx = float(r["left_wrist_x"]); ly = float(r["left_wrist_y"])
                rx = float(r["right_wrist_x"]); ry = float(r["right_wrist_y"])
                out[fr] = {"left": (lx, ly), "right": (rx, ry)}
            except (ValueError, KeyError):
                continue
    return out


def find_closest_wrist(wrist_frames: dict, frame: int, max_diff: int = 5):
    """Find wrist positions closest to `frame`."""
    if not wrist_frames:
        return None
    if frame in wrist_frames:
        return wrist_frames[frame]
    nearest = None
    nearest_diff = max_diff + 1
    for fr, w in wrist_frames.items():
        d = abs(fr - frame)
        if d <= max_diff and d < nearest_diff:
            nearest_diff = d
            nearest = w
    return nearest


def inhand_check(dets, wrist_frames, side, tail_n, head_n,
                 in_hand_px, min_in_hand_frames, max_diff=5):
    """Check whether a tracklet's tail (last tail_n frames) AND head
    (first head_n frames) are both in the same hand (side).

    Returns dict with:
        src_inhand: bool (last tail_n frames in this hand)
        tgt_inhand: bool (first head_n frames in this hand)
        src_inhand_count: int
        tgt_inhand_count: int
    """
    if not dets:
        return {"src_inhand": False, "tgt_inhand": False,
                "src_inhand_count": 0, "tgt_inhand_count": 0,
                "src_dist_min": None, "tgt_dist_min": None}

    src_tail = dets[:head_n]   # head_n frames from the start
    tgt_head = dets[-tail_n:]  # tail_n frames from the end

    # NOTE: H17 stores from_tid/to_tid with from being source and to being
    # target. We need the LAST frames of source and FIRST frames of target.
    # But here `dets` is a single tracklet's detections. The caller decides
    # which tracklet is which.
    pass


def src_inhand(dets, wrist_frames, side, in_hand_px, min_in_hand_frames, n_tail=3, max_diff=5):
    """For a SOURCE tracklet, check if its LAST n_tail frames are in hand."""
    if not dets:
        return False, 0, None
    tail = dets[-n_tail:]
    count = 0
    min_d = None
    for (fr, x, y, c) in tail:
        w = find_closest_wrist(wrist_frames, fr, max_diff)
        if w is None or side not in w:
            continue
        wx, wy = w[side]
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d <= in_hand_px:
            count += 1
            if min_d is None or d < min_d:
                min_d = d
    return count >= min_in_hand_frames, count, min_d


def tgt_inhand(dets, wrist_frames, side, in_hand_px, min_in_hand_frames, n_head=3, max_diff=5):
    """For a TARGET tracklet, check if its FIRST n_head frames are in hand."""
    if not dets:
        return False, 0, None
    head = dets[:n_head]
    count = 0
    min_d = None
    for (fr, x, y, c) in head:
        w = find_closest_wrist(wrist_frames, fr, max_diff)
        if w is None or side not in w:
            continue
        wx, wy = w[side]
        d = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if d <= in_hand_px:
            count += 1
            if min_d is None or d < min_d:
                min_d = d
    return count >= min_in_hand_frames, count, min_d


def evaluate_h17_strict(strict_positives, in_hand_px, min_in_hand_frames,
                         max_gap_vel=None, apex_src_dist_reject=None):
    """For each H17 strict positive, compute in-hand flags for both endpoints
    at the V-apex hand. Return a list of dicts with all fields plus
    in-hand flags and a final reject decision.

    Three rejection rules:
    1. INHAND: BOTH source's last 3 frames AND target's first 3 frames are
       in the V-apex hand (held ball, not a catch+throw).
    2. VEL_JUMP (optional): end-to-start gap velocity exceeds the max
       plausible ball speed (ball teleportation, not physical motion).
    3. APEX_AT_SRC (optional): the V-apex is within apex_src_dist_reject px
       of the source's last frame position AND the source is in the hand
       (no real catch+throw; the V-apex is just the source's last position).
    """
    rows = []
    cache = {}  # (stem, side) -> wrist_frames

    for edge in strict_positives:
        stem = edge["stem"]
        side = edge["which_hand"]
        if (stem, side) not in cache:
            cache[(stem, side)] = load_wrist_frames(stem)
        wf = cache[(stem, side)]

        src_dets = load_per_det_tracklet(stem, edge["from_tid"])
        tgt_dets = load_per_det_tracklet(stem, edge["to_tid"])

        src_inhand_flag, src_count, src_min_d = src_inhand(
            src_dets, wf, side, in_hand_px, min_in_hand_frames)
        tgt_inhand_flag, tgt_count, tgt_min_d = tgt_inhand(
            tgt_dets, wf, side, in_hand_px, min_in_hand_frames)

        # Compute gap velocity (end-of-source to start-of-target)
        gap_dist = None
        gap_vel = None
        if src_dets and tgt_dets:
            sx, sy = src_dets[-1][1], src_dets[-1][2]
            tx, ty = tgt_dets[0][1], tgt_dets[0][2]
            gap_dist = ((sx - tx) ** 2 + (sy - ty) ** 2) ** 0.5
            gap_frames = tgt_dets[0][0] - src_dets[-1][0]
            if gap_frames > 0:
                gap_vel = gap_dist / gap_frames

        # Compute apex-to-source-end distance
        apex_x = edge.get("apex_x", 0)
        apex_y = edge.get("apex_y", 0)
        apex_src_dist = None
        if src_dets:
            sx, sy = src_dets[-1][1], src_dets[-1][2]
            apex_src_dist = ((apex_x - sx) ** 2 + (apex_y - sy) ** 2) ** 0.5

        # REJECTION RULES
        rejected_inhand = src_inhand_flag and tgt_inhand_flag
        rejected_vel = (max_gap_vel is not None
                        and gap_vel is not None
                        and gap_vel > max_gap_vel)
        rejected_apex = (apex_src_dist_reject is not None
                         and apex_src_dist is not None
                         and apex_src_dist < apex_src_dist_reject
                         and src_inhand_flag)
        rejected = rejected_inhand or rejected_vel or rejected_apex

        row = dict(edge)
        row["src_inhand"] = src_inhand_flag
        row["src_inhand_count"] = src_count
        row["src_inhand_min_d"] = round(src_min_d, 2) if src_min_d is not None else None
        row["tgt_inhand"] = tgt_inhand_flag
        row["tgt_inhand_count"] = tgt_count
        row["tgt_inhand_min_d"] = round(tgt_min_d, 2) if tgt_min_d is not None else None
        row["in_hand_px"] = in_hand_px
        row["min_in_hand_frames"] = min_in_hand_frames
        row["gap_dist"] = round(gap_dist, 2) if gap_dist is not None else None
        row["gap_vel"] = round(gap_vel, 2) if gap_vel is not None else None
        row["apex_src_dist"] = round(apex_src_dist, 2) if apex_src_dist is not None else None
        row["rejected_inhand"] = rejected_inhand
        row["rejected_vel"] = rejected_vel
        row["rejected_apex"] = rejected_apex
        row["h20_reject_inhand"] = rejected
        row["h20_keep"] = not rejected
        if max_gap_vel is not None:
            row["max_gap_vel"] = max_gap_vel
        if apex_src_dist_reject is not None:
            row["apex_src_dist_reject"] = apex_src_dist_reject
        rows.append(row)

    return rows


def load_h17_strict_positives() -> list[dict]:
    """Load H17 strict V-shape positives from h17_strict_v_shape_positives.csv."""
    path = H1_DATA / "h17_strict_v_shape_positives.csv"
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "kind": r["kind"],
                "stem": r["stem"],
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "gap": int(r["gap"]),
                "vshape": r["vshape"],
                "min_hand_dist": float(r["min_hand_dist"]),
                "ratio": float(r["ratio"]),
                "which_hand": r["which_hand"],
                "in_h7v2": r["in_h7v2"] == "True",
                "apex_frame": int(r["apex_frame"]),
                "apex_x": float(r["apex_x"]),
                "apex_y": float(r["apex_y"]),
            })
    return out


def write_csv(rows: list[dict], path: Path):
    """Write results to CSV."""
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def eval_qa(rows, qa_verdicts):
    """Compare H20's keep/reject decisions against the 16 H17 visual QA."""
    n_total = 0
    n_rejected = 0
    n_rejected_real = 0
    n_rejected_partial = 0
    n_rejected_false = 0
    n_rejected_unclear = 0
    n_kept = 0
    n_kept_real = 0
    n_kept_partial = 0
    n_kept_false = 0
    n_kept_unclear = 0

    rows_by_key = {(r["stem"], r["from_tid"], r["to_tid"]): r for r in rows}
    for (stem, frm, to), verdict in qa_verdicts.items():
        r = rows_by_key.get((stem, frm, to))
        if r is None:
            continue
        n_total += 1
        if r["h20_reject_inhand"]:
            n_rejected += 1
            if verdict == "REAL": n_rejected_real += 1
            elif verdict == "PARTIAL": n_rejected_partial += 1
            elif verdict == "FALSE": n_rejected_false += 1
            elif verdict == "UNCLEAR": n_rejected_unclear += 1
        else:
            n_kept += 1
            if verdict == "REAL": n_kept_real += 1
            elif verdict == "PARTIAL": n_kept_partial += 1
            elif verdict == "FALSE": n_kept_false += 1
            elif verdict == "UNCLEAR": n_kept_unclear += 1

    return {
        "qa_n_total": n_total,
        "qa_n_rejected": n_rejected,
        "qa_n_rejected_real": n_rejected_real,
        "qa_n_rejected_partial": n_rejected_partial,
        "qa_n_rejected_false": n_rejected_false,
        "qa_n_rejected_unclear": n_rejected_unclear,
        "qa_n_kept": n_kept,
        "qa_n_kept_real": n_kept_real,
        "qa_n_kept_partial": n_kept_partial,
        "qa_n_kept_false": n_kept_false,
        "qa_n_kept_unclear": n_kept_unclear,
        # Precision: REAL+PARTIAL in kept / total kept (PARTIAL=TP)
        "qa_precision_partial_as_tp": (
            (n_kept_real + n_kept_partial) / n_kept if n_kept > 0 else 0
        ),
        # Recall: REAL+PARTIAL rejected is BAD; REAL+PARTIAL kept is GOOD
        "qa_recall_partial_as_tp": (
            (n_kept_real + n_kept_partial) / n_total if n_total > 0 else 0
        ),
        # FPR: FALSE rejected is GOOD (precision gain)
        "qa_fpr_drop": (
            n_rejected_false / (n_rejected_false + n_kept_false)
            if (n_rejected_false + n_kept_false) > 0 else 0
        ),
    }


def main():
    print("=" * 70)
    print("H20: In-hand rejection filter for H17 strict V-shape positives")
    print("=" * 70)

    strict_positives = load_h17_strict_positives()
    print(f"\nLoaded {len(strict_positives)} H17 strict V-shape positives")

    # Run at default thresholds
    in_hand_px = H20_THRESHOLDS["IN_HAND_PX"]
    min_in_hand_frames = H20_THRESHOLDS["MIN_IN_HAND_FRAMES"]
    max_gap_vel = H20_THRESHOLDS["MAX_GAP_VEL_PX_PER_FRAME"]
    apex_src_dist_reject = H20_THRESHOLDS["APEX_SRC_DIST_REJECT_PX"]
    print(f"\nDefault thresholds: IN_HAND_PX={in_hand_px}, MIN_IN_HAND_FRAMES={min_in_hand_frames}, "
          f"MAX_GAP_VEL={max_gap_vel}, APEX_SRC_DIST={apex_src_dist_reject}")

    rows = evaluate_h17_strict(strict_positives, in_hand_px, min_in_hand_frames,
                              max_gap_vel=max_gap_vel,
                              apex_src_dist_reject=apex_src_dist_reject)
    write_csv(rows, H20_CSV)
    print(f"Wrote {H20_CSV}")

    # Summarize
    n_total = len(rows)
    n_rejected = sum(1 for r in rows if r["h20_reject_inhand"])
    n_rejected_inhand = sum(1 for r in rows if r["rejected_inhand"])
    n_rejected_vel = sum(1 for r in rows if r["rejected_vel"])
    n_rejected_apex = sum(1 for r in rows if r["rejected_apex"])
    n_kept = n_total - n_rejected
    n_in_h7v2 = sum(1 for r in rows if r["in_h7v2"])
    n_in_h7v2_kept = sum(1 for r in rows if r["in_h7v2"] and r["h20_keep"])

    print(f"\n=== Default (IN_HAND_PX={in_hand_px}, MIN={min_in_hand_frames}, "
          f"MAX_VEL={max_gap_vel}, APEX_DIST={apex_src_dist_reject}) ===")
    print(f"Total H17 strict positives: {n_total}")
    print(f"  Rejected by H20: {n_rejected} ({100*n_rejected/n_total:.1f}%)")
    print(f"    - by in-hand rule:  {n_rejected_inhand}")
    print(f"    - by vel-jump rule: {n_rejected_vel}")
    print(f"    - by apex rule:     {n_rejected_apex}")
    print(f"  Kept by H20:     {n_kept} ({100*n_kept/n_total:.1f}%)")
    print(f"Of {n_in_h7v2} already in h7v2, H20 keeps: {n_in_h7v2_kept}")

    # Visual QA evaluation
    qa = eval_qa(rows, H17_QA_VERDICTS)
    print(f"\n=== Visual QA evaluation (n=16) ===")
    print(f"Kept: REAL={qa['qa_n_kept_real']} PARTIAL={qa['qa_n_kept_partial']} "
          f"FALSE={qa['qa_n_kept_false']} UNCLEAR={qa['qa_n_kept_unclear']}")
    print(f"Rejected: REAL={qa['qa_n_rejected_real']} PARTIAL={qa['qa_n_rejected_partial']} "
          f"FALSE={qa['qa_n_rejected_false']} UNCLEAR={qa['qa_n_rejected_unclear']}")
    print(f"Precision (PARTIAL=TP): {qa['qa_precision_partial_as_tp']:.3f}")
    print(f"Recall (PARTIAL=TP):    {qa['qa_recall_partial_as_tp']:.3f}")
    print(f"FALSE-rejection rate:   {qa['qa_fpr_drop']:.3f}")

    # Sensitivity grid
    print(f"\n=== Sensitivity grid (IN_HAND_PX x MIN x MAX_VEL x APEX_DIST) ===")
    print(f"{'in_h':>5s} {'min':>4s} {'vel':>5s} {'apx':>5s} {'rej%':>5s} {'kept_R':>7s} {'kept_P':>7s} {'kept_F':>7s} {'kept_U':>7s} {'rej_R':>5s} {'rej_P':>5s} {'rej_F':>5s} {'prec':>5s} {'rec':>5s} {'fpr':>5s}")
    grid_results = []
    for ihp in (30,):
        for mif in (2, 3):
            for mgv in (None, 50.0, 70.0, 100.0):
                for asr in (None, 20.0, 40.0):
                    r = evaluate_h17_strict(strict_positives, ihp, mif,
                                           max_gap_vel=mgv,
                                           apex_src_dist_reject=asr)
                    n_rej = sum(1 for x in r if x["h20_reject_inhand"])
                    qa_g = eval_qa(r, H17_QA_VERDICTS)
                    mgv_str = f"{mgv:>3.0f}" if mgv is not None else " inf"
                    asr_str = f"{asr:>3.0f}" if asr is not None else " inf"
                    grid_results.append({
                        "in_hand_px": ihp, "min_in_hand_frames": mif,
                        "max_gap_vel": mgv, "apex_src_dist_reject": asr,
                        "n_rejected": n_rej, "n_total": len(r),
                        "pct_rejected": n_rej / len(r),
                        **qa_g,
                    })
                    print(f"{ihp:>5d} {mif:>4d} {mgv_str:>5s} {asr_str:>5s} "
                          f"{100*n_rej/len(r):>4.0f}% "
                          f"{qa_g['qa_n_kept_real']:>7d} {qa_g['qa_n_kept_partial']:>7d} {qa_g['qa_n_kept_false']:>7d} {qa_g['qa_n_kept_unclear']:>7d} "
                          f"{qa_g['qa_n_rejected_real']:>5d} {qa_g['qa_n_rejected_partial']:>5d} {qa_g['qa_n_rejected_false']:>5d} "
                          f"{qa_g['qa_precision_partial_as_tp']:>5.2f} {qa_g['qa_recall_partial_as_tp']:>5.2f} {qa_g['qa_fpr_drop']:>5.2f}")

    # Find best (max precision, max recall, max fpr_drop)
    print(f"\n=== Best operating points (QA n=16) ===")
    # Pareto front: high precision, high recall
    grid_sorted = sorted(grid_results,
                         key=lambda g: (g["qa_precision_partial_as_tp"],
                                        g["qa_recall_partial_as_tp"],
                                        g["qa_fpr_drop"]),
                         reverse=True)
    for g in grid_sorted[:5]:
        mgv = g.get("max_gap_vel")
        asr = g.get("apex_src_dist_reject")
        mgv_str = f"{mgv:.0f}" if mgv is not None else "inf"
        asr_str = f"{asr:.0f}" if asr is not None else "inf"
        print(f"  IN_HAND_PX={g['in_hand_px']:3d} MIN={g['min_in_hand_frames']} "
              f"MAX_VEL={mgv_str:>4s} APEX_DIST={asr_str:>4s} "
              f"reject={100*g['pct_rejected']:.1f}% "
              f"prec={g['qa_precision_partial_as_tp']:.3f} "
              f"recall={g['qa_recall_partial_as_tp']:.3f} "
              f"fpr_drop={g['qa_fpr_drop']:.3f}")

    # Per-source breakdown
    print(f"\n=== Per-source breakdown (default thresholds) ===")
    by_kind = defaultdict(lambda: {"n": 0, "rejected": 0, "kept": 0})
    for r in rows:
        by_kind[r["kind"]]["n"] += 1
        if r["h20_reject_inhand"]:
            by_kind[r["kind"]]["rejected"] += 1
        else:
            by_kind[r["kind"]]["kept"] += 1
    for k, v in sorted(by_kind.items()):
        print(f"  {k}: total={v['n']}, rejected={v['rejected']} ({100*v['rejected']/v['n']:.1f}%), "
              f"kept={v['kept']} ({100*v['kept']/v['n']:.1f}%)")

    # Per-stem breakdown
    print(f"\n=== Per-stem breakdown (default thresholds) ===")
    by_stem = defaultdict(lambda: {"n": 0, "rejected": 0, "kept": 0})
    for r in rows:
        by_stem[r["stem"]]["n"] += 1
        if r["h20_reject_inhand"]:
            by_stem[r["stem"]]["rejected"] += 1
        else:
            by_stem[r["stem"]]["kept"] += 1
    for k, v in sorted(by_stem.items()):
        print(f"  {k}: total={v['n']}, rejected={v['rejected']} ({100*v['rejected']/v['n']:.1f}%), "
              f"kept={v['kept']} ({100*v['kept']/v['n']:.1f}%)")

    # Save summary
    summary = {
        "thresholds": H20_THRESHOLDS,
        "n_strict_positives": n_total,
        "n_rejected_default": n_rejected,
        "n_kept_default": n_kept,
        "n_in_h7v2": n_in_h7v2,
        "n_in_h7v2_kept": n_in_h7v2_kept,
        "qa_default": qa,
        "grid": grid_results,
        "by_kind": dict(by_kind),
        "by_stem": dict(by_stem),
    }
    with H20_SUMMARY.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nWrote {H20_SUMMARY}")


if __name__ == "__main__":
    main()
