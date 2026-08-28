#!/usr/bin/env python3
"""H31: visual QA of H20-AND-H30-KEPT intersection candidates.

H30's PARTIAL PASS found that H17+H20+H30 src_above+src_desc admits
15 high-precision candidates (16 if we count the duplicate 54->57/56->57
case). Of these, 5 are already in the known label set (4 REAL + 1 PARTIAL).
The remaining 10 are NEW candidates that need visual QA.

H31 hypothesis: the H20+H30-AND intersection is a precision-optimized pool.
The 10 NEW candidates should have similar or higher REAL precision than
the H20-KEPT-not-in-h7v2 pool (H24: 22% REAL on 9 candidates) and the
H20-KEPT adjacent pool (H28: 17% REAL on 12 candidates).

Strategy: render 10 contact sheets, visually QA each via vision_analyze,
compute precision stats, compare to H20/H24/H28.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h28_candidate_qa_at_scale import contact_sheet
from h20_inhand_rejection import (
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
)

import matplotlib
matplotlib.use("Agg")


WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H31_CS = H1_DIR / "contact_sheets_h31"
H31_CS.mkdir(parents=True, exist_ok=True)


def main():
    print("Generating H31 contact sheets for H20+H30-AND candidates...")

    candidates = list(csv.DictReader(open(H1_DIR / "data" / "h31_h20_h30_kept.csv")))
    print(f"Total H31 candidates: {len(candidates)}")

    # Load H17 strict for apex data
    h17_strict = list(csv.DictReader(open(H1_DIR / "data" / "h17_strict_v_shape_positives.csv")))

    # Select 10 NEW candidates (those not in the known-label set)
    known_keys = {
        (13, 15, "identical"), (6, 15, "identical"), (54, 57, "identical"),
        (56, 57, "identical"), (56, 58, "identical"), (20, 21, "youtube"),
        (7, 10, "identical"), (59, 61, "identical"), (10, 11, "youtube"),
        (29, 33, "identical"), (23, 24, "youtube"),
    }

    new_candidates = []
    for c in candidates:
        stem_kind = "identical" if "identical" in c["stem"] else "youtube"
        key = (int(c["from_tid"]), int(c["to_tid"]), stem_kind)
        if key not in known_keys:
            new_candidates.append(c)

    print(f"NEW (not in known labels): {len(new_candidates)}")

    # Sort by gap ascending, take all 10
    new_candidates.sort(key=lambda r: (int(r["gap"]), float(r["min_hand_dist"])))
    selected = new_candidates[:10]
    print(f"Selected for H31 QA: {len(selected)}")

    # Render contact sheets
    for i, c in enumerate(selected):
        # Find matching H17 strict for apex data
        match = [e for e in h17_strict if e["stem"] == c["stem"]
                 and int(e["from_tid"]) == int(c["from_tid"])
                 and int(e["to_tid"]) == int(c["to_tid"])]
        if not match:
            print(f"  {i+1}. {c['stem'][:25]} {c['from_tid']:>3}->{c['to_tid']:<3} NO H17 MATCH")
            continue
        edge = match[0]
        # Enrich with apex data from H30
        h30_match = [r for r in csv.DictReader(open(H1_DIR / "data" / "h30_direction_metrics.csv"))
                     if r["stem"] == c["stem"]
                     and int(r["from_tid"]) == int(c["from_tid"])
                     and int(r["to_tid"]) == int(c["to_tid"])]
        edge = {
            "stem": edge["stem"],
            "from_tid": int(edge["from_tid"]),
            "to_tid": int(edge["to_tid"]),
            "gap": int(edge["gap"]),
            "vshape": edge["vshape"],
            "min_hand_dist": float(edge["min_hand_dist"]),
            "which_hand": edge["which_hand"],
            "apex_x": float(edge["apex_x"]),
            "apex_y": float(edge["apex_y"]),
        }

        src_dets = load_per_det_tracklet(edge["stem"], edge["from_tid"])
        tgt_dets = load_per_det_tracklet(edge["stem"], edge["to_tid"])
        wf = load_wrist_frames(edge["stem"])
        save_path = H31_CS / f"{edge['stem'][:25]}_{edge['from_tid']:>3d}to{edge['to_tid']:<3d}_H31_{i+1:02d}.png"
        ok = contact_sheet(edge, src_dets, tgt_dets, wf, save_path, "H31_QA")
        if ok:
            print(f"  {i+1:>2d}. {edge['stem'][:25]:25s} {edge['from_tid']:>3d}->{edge['to_tid']:<3d} "
                  f"gap={edge['gap']:>2d} vshape={edge['vshape']:<9} hand={edge['which_hand']:<5} "
                  f"min_d={edge['min_hand_dist']:.1f}  -> {save_path.name}")
        else:
            print(f"  {i+1:>2d}. {edge['stem'][:25]:25s} {edge['from_tid']:>3d}->{edge['to_tid']:<3d} "
                  f"FAILED (insufficient detections)")

    # Save the selected list
    with (H1_DIR / "data" / "h31_selected_candidates.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "h31_idx", "stem", "from_tid", "to_tid", "gap", "vshape", "which_hand",
            "min_hand_dist", "kind", "src_to_apex_dy", "src_descending", "src_above",
        ])
        w.writeheader()
        for i, c in enumerate(selected):
            w.writerow({
                "h31_idx": i + 1,
                "stem": c["stem"],
                "from_tid": int(c["from_tid"]),
                "to_tid": int(c["to_tid"]),
                "gap": int(c["gap"]),
                "vshape": c["vshape"],
                "which_hand": c["which_hand"],
                "min_hand_dist": float(c["min_hand_dist"]),
                "kind": c["kind"],
                "src_to_apex_dy": c["src_to_apex_dy"],
                "src_descending": c["src_descending"],
                "src_above": c["src_above"],
            })


if __name__ == "__main__":
    main()
