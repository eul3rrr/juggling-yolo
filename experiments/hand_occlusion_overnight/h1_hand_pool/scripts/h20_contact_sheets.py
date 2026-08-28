#!/usr/bin/env python3
"""H20 contact sheets: visual confirmation of kept vs rejected edges.

For the H20 default thresholds (IN_HAND_PX=30, MIN=3, MAX_VEL=70, APEX_DIST=20),
generate contact sheets for:
  1. The 3 H17 visual QA FPs that H20 correctly REJECTS (4->8, 35->38, 66->68,
     1->10, 24->27)
  2. The H17 visual QA REALs that H20 keeps (5-6 of them)
  3. A few H20-REJECTED candidates that were NOT in the H17 QA set
     (to spot-check the vel-jump rule)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h20_inhand_rejection import (
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
    H20_THRESHOLDS, evaluate_h17_strict, H17_QA_VERDICTS, eval_qa,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H20_CS = H1_DIR / "contact_sheets_h20"
H20_CS.mkdir(parents=True, exist_ok=True)

# H17 QA verdicts
H17_QA = H17_QA_VERDICTS

# Load H17 strict positives
strict = []
with (H1_DIR / "data" / "h17_strict_v_shape_positives.csv").open() as fh:
    for r in csv.DictReader(fh):
        strict.append({
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


def contact_sheet(edge, src_dets, tgt_dets, wf, save_path, kind_label):
    """Render a 6-frame contact sheet for the edge.
    Top row: 3 frames of source tail; bottom row: 3 frames of target head.
    Plus V-apex annotation."""
    src_tail = src_dets[-3:] if src_dets else []
    tgt_head = tgt_dets[:3] if tgt_dets else []

    if len(src_tail) < 3 or len(tgt_head) < 3:
        return False

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(f"{edge['stem'][:30]}  {edge['from_tid']}->{edge['to_tid']}  "
                 f"({kind_label}, gap={edge['gap']}, V={edge['vshape']}, "
                 f"min_d={edge['min_hand_dist']:.1f})",
                 fontsize=14)

    # Render source tail
    for i, (fr, x, y, c) in enumerate(src_tail):
        ax = axes[0, i]
        ax.set_xlim(0, 1280)
        ax.set_ylim(720, 0)
        ax.set_aspect("equal")
        # wrists
        w = find_closest_wrist(wf, fr, max_diff=5)
        if w is not None:
            if "left" in w:
                lx, ly = w["left"]
                ax.add_patch(Circle((lx, ly), 30, color="orange", fill=False, linewidth=2, label="L wrist"))
                ax.plot(lx, ly, "+", color="orange", markersize=10)
            if "right" in w:
                rx, ry = w["right"]
                ax.add_patch(Circle((rx, ry), 30, color="blue", fill=False, linewidth=2, label="R wrist"))
                ax.plot(rx, ry, "+", color="blue", markersize=10)
        # source (blue) and target (orange) detections
        ax.plot(x, y, "o", color="blue", markersize=8, label=f"src f={fr}")
        # mark V-apex if it falls in this frame's window
        ax.set_title(f"SRC f={fr} ({x:.0f},{y:.0f})")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=7)

    # Render target head
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
        ax.plot(x, y, "o", color="orange", markersize=8, label=f"tgt f={fr}")
        ax.set_title(f"TGT f={fr} ({x:.0f},{y:.0f})")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=7)

    # Add apex annotation in title area
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
    print("Generating H20 contact sheets...")

    # Run H20 with default thresholds
    rows = evaluate_h17_strict(strict,
                              H20_THRESHOLDS["IN_HAND_PX"],
                              H20_THRESHOLDS["MIN_IN_HAND_FRAMES"],
                              max_gap_vel=H20_THRESHOLDS["MAX_GAP_VEL_PX_PER_FRAME"],
                              apex_src_dist_reject=H20_THRESHOLDS["APEX_SRC_DIST_REJECT_PX"])

    rows_by_key = {(r["stem"], r["from_tid"], r["to_tid"]): r for r in rows}

    # Generate for QA'd edges (priority)
    qa_kept_count = 0
    qa_rejected_count = 0
    for (stem, frm, to), verdict in H17_QA.items():
        r = rows_by_key.get((stem, frm, to))
        if r is None:
            continue
        edge = next(e for e in strict if e["stem"] == stem
                    and e["from_tid"] == frm and e["to_tid"] == to)
        src_dets = load_per_det_tracklet(stem, frm)
        tgt_dets = load_per_det_tracklet(stem, to)
        wf = load_wrist_frames(stem)
        if r["h20_reject_inhand"]:
            qa_rejected_count += 1
            tag = "H20_REJ"
        else:
            qa_kept_count += 1
            tag = "H20_KEEP"
        save_path = H20_CS / f"{stem[:25]}_{frm:>3}to{to:<3}_{verdict}_{tag}.png"
        ok = contact_sheet(edge, src_dets, tgt_dets, wf, save_path,
                          f"H17_{verdict}_{tag}")
        if ok:
            print(f"  Saved {save_path.name}")

    print(f"\nQA edges: {qa_kept_count} H20-KEPT, {qa_rejected_count} H20-REJECTED")

    # Spot-check 4 random H20-rejected (NOT in QA) to characterize vel-jump FPs
    print("\nSpot-checking 4 H20-REJECTED edges (not in QA set):")
    spot_checked = 0
    for r in rows:
        if r["h20_reject_inhand"]:
            key = (r["stem"], r["from_tid"], r["to_tid"])
            if key in H17_QA:
                continue
            if spot_checked >= 4:
                break
            edge = r
            src_dets = load_per_det_tracklet(edge["stem"], edge["from_tid"])
            tgt_dets = load_per_det_tracklet(edge["stem"], edge["to_tid"])
            wf = load_wrist_frames(edge["stem"])
            save_path = H20_CS / f"{edge['stem'][:25]}_{edge['from_tid']:>3}to{edge['to_tid']:<3}_REJ_{edge.get('rejected_vel', False) and 'vel' or ''}{edge.get('rejected_apex', False) and 'apex' or ''}{edge.get('rejected_inhand', False) and 'inh' or ''}.png"
            ok = contact_sheet(edge, src_dets, tgt_dets, wf, save_path, "H20_REJ")
            if ok:
                spot_checked += 1
                print(f"  Saved {save_path.name}  gap_vel={edge.get('gap_vel')}, apex_dist={edge.get('apex_src_dist')}")


if __name__ == "__main__":
    main()
