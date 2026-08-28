#!/usr/bin/env python3
"""H24: H20-KEPT e6c_not_in_h7v2 candidate review at scale.

Renders contact sheets for the H20-KEPT e6c_not_in_h7v2 candidates
that were NOT visually QA'd in the H20 episode. This is a scale-up
of the H20 contact-sheet QA to characterize the precision of the
26-candidate pool.

Strategy: select 12 candidates (8 identical + 4 YouTube) not in the
original 16-edge H17 QA set, with preference for:
1. Short gap (≤15) — most likely to be real catch+throws
2. Low min_d (<30) — strong V-shape evidence
3. Reasonable ratio (≥3) — clear V-shape
4. Mix of left/right hands
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h20_inhand_rejection import (
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
    H20_THRESHOLDS, evaluate_h17_strict,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H24_CS = H1_DIR / "contact_sheets_h24"
H24_CS.mkdir(parents=True, exist_ok=True)


def load_h17_strict_positives() -> list[dict]:
    out = []
    with (H1_DIR / "data" / "h17_strict_v_shape_positives.csv").open() as fh:
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


def contact_sheet(edge, src_dets, tgt_dets, wf, save_path, kind_label):
    src_tail = src_dets[-3:] if src_dets else []
    tgt_head = tgt_dets[:3] if tgt_dets else []
    if len(src_tail) < 3 or len(tgt_head) < 3:
        return False
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(f"{edge['stem'][:30]}  {edge['from_tid']}->{edge['to_tid']}  "
                 f"({kind_label}, gap={edge['gap']}, V={edge['vshape']}, "
                 f"min_d={edge['min_hand_dist']:.1f})",
                 fontsize=14)
    for i, (fr, x, y, c) in enumerate(src_tail):
        ax = axes[0, i]
        ax.set_xlim(0, 1280)
        ax.set_ylim(720, 0)
        ax.set_aspect("equal")
        w = find_closest_wrist(wf, fr, max_diff=5)
        if w is not None:
            if "left" in w:
                lx, ly = w["left"]
                ax.add_patch(Circle((lx, ly), 30, color="orange", fill=False, linewidth=2))
                ax.plot(lx, ly, "+", color="orange", markersize=10)
            if "right" in w:
                rx, ry = w["right"]
                ax.add_patch(Circle((rx, ry), 30, color="blue", fill=False, linewidth=2))
                ax.plot(rx, ry, "+", color="blue", markersize=10)
        ax.plot(x, y, "o", color="blue", markersize=8)
        ax.set_title(f"SRC f={fr} ({x:.0f},{y:.0f})")
        ax.grid(True, alpha=0.3)
    for i, (fr, x, y, c) in enumerate(tgt_head):
        ax = axes[1, i]
        ax.set_xlim(0, 1280)
        ax.set_ylim(720, 0)
        ax.set_aspect("equal")
        w = find_closest_wrist(wf, fr, max_diff=5)
        if w is not None:
            if "left" in w:
                lx, ly = w["left"]
                ax.add_patch(Circle((lx, ly), 30, color="orange", fill=False, linewidth=2))
                ax.plot(lx, ly, "+", color="orange", markersize=10)
            if "right" in w:
                rx, ry = w["right"]
                ax.add_patch(Circle((rx, ry), 30, color="blue", fill=False, linewidth=2))
                ax.plot(rx, ry, "+", color="blue", markersize=10)
        ax.plot(x, y, "o", color="orange", markersize=8)
        ax.set_title(f"TGT f={fr} ({x:.0f},{y:.0f})")
        ax.grid(True, alpha=0.3)
    apex_x = edge["apex_x"]
    apex_y = edge["apex_y"]
    side = edge["which_hand"]
    fig.text(0.5, 0.02,
             f"V-apex ({apex_x:.0f}, {apex_y:.0f}) hand={side} "
             f"min_d={edge['min_hand_dist']:.1f}",
             ha="center", fontsize=10)
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(save_path, dpi=100, bbox_inches="tight")
    plt.close()
    return True


def main():
    print("Generating H24 contact sheets for H20-KEPT e6c_not_in_h7v2 candidates...")

    # Load H17 strict positives
    strict = load_h17_strict_positives()

    # The 8 already-QA'd H20-KEPT-not-in-h7v2 candidates (from H20 visual QA)
    h20_qa_done = {
        ("identical_balls_trick_000_018", 6, 15): "REAL",
        ("identical_balls_trick_000_018", 54, 57): "REAL",
        ("identical_balls_trick_000_018", 56, 57): "REAL",
        ("identical_balls_trick_000_018", 56, 58): "REAL",
        ("identical_balls_trick_000_018", 29, 33): "PARTIAL",
        ("identical_balls_trick_000_018", 13, 15): "PARTIAL",
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 20, 21): "REAL",
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 23, 24): "PARTIAL",
    }

    # Filter to H20-KEPT e6c_not_in_h7v2 candidates NOT already QA'd
    h20 = list(csv.DictReader(open(H1_DIR / "data" / "h20_strict_v_shape_positives_inhand.csv")))
    h24_candidates = [r for r in h20
                      if r["kind"] == "e6c_not_in_h7v2"
                      and r["h20_keep"] == "True"
                      and (r["stem"], int(r["from_tid"]), int(r["to_tid"])) not in h20_qa_done]
    print(f"  H20-KEPT e6c_not_in_h7v2 candidates NOT yet QA'd: {len(h24_candidates)}")

    # Selection strategy: 12 candidates with short gap, low min_d, good ratio
    # Sort by gap (ascending) then min_d (ascending)
    h24_candidates.sort(key=lambda r: (int(r["gap"]), float(r["min_hand_dist"])))

    # Take 8 identical + 4 youtube (matches the 8/8 split from H20)
    sel_identical = [r for r in h24_candidates if r["stem"].startswith("identical")][:8]
    sel_youtube = [r for r in h24_candidates if r["stem"].startswith("youtube")][:4]
    selected = sel_identical + sel_youtube
    print(f"  Selected for H24 QA: {len(selected)} (8 identical + 4 youtube)")

    # Render contact sheets
    for i, r in enumerate(selected):
        edge = next(e for e in strict if e["stem"] == r["stem"]
                    and e["from_tid"] == int(r["from_tid"])
                    and e["to_tid"] == int(r["to_tid"]))
        src_dets = load_per_det_tracklet(edge["stem"], edge["from_tid"])
        tgt_dets = load_per_det_tracklet(edge["stem"], edge["to_tid"])
        wf = load_wrist_frames(edge["stem"])
        save_path = H24_CS / f"{edge['stem'][:25]}_{edge['from_tid']:>3d}to{edge['to_tid']:<3d}_H24_{i+1:02d}.png"
        ok = contact_sheet(edge, src_dets, tgt_dets, wf, save_path, "H24_QA")
        if ok:
            print(f"  {i+1:>2d}. {edge['stem'][:25]:25s} {edge['from_tid']:>3d}->{edge['to_tid']:<3d} "
                  f"gap={edge['gap']:>2d} vshape={edge['vshape']} hand={edge['which_hand']:<5} "
                  f"min_d={edge['min_hand_dist']:.1f}  -> {save_path.name}")
        else:
            print(f"  {i+1:>2d}. {edge['stem'][:25]:25s} {edge['from_tid']:>3d}->{edge['to_tid']:<3d} "
                  f"FAILED (insufficient detections)")

    # Save the selected list for reference
    with (H1_DIR / "data" / "h24_selected_candidates.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "h24_idx", "stem", "from_tid", "to_tid", "gap", "vshape", "which_hand",
            "min_hand_dist", "ratio", "gap_vel", "apex_src_dist"])
        w.writeheader()
        for i, r in enumerate(selected):
            w.writerow({
                "h24_idx": i + 1,
                "stem": r["stem"],
                "from_tid": int(r["from_tid"]),
                "to_tid": int(r["to_tid"]),
                "gap": int(r["gap"]),
                "vshape": r["vshape"],
                "which_hand": r["which_hand"],
                "min_hand_dist": float(r["min_hand_dist"]),
                "ratio": float(r["ratio"]),
                "gap_vel": r["gap_vel"],
                "apex_src_dist": r["apex_src_dist"],
            })


if __name__ == "__main__":
    main()
