#!/usr/bin/env python3
"""H35 contact sheets: visual confirmation of H22's YouTube chain split.

Renders 6-frame contact sheets for:
- YouTube chain 0 (1,9,13,16) — was the 7-tid chain (1,9,13,16,21,29,34)
- YouTube chain 10 (20,21,29,34) — new chain from H22 veto

For each chain, render the edges:
- 1->9, 9->13, 13->16 for chain 0
- 20->21, 21->29, 29->34 for chain 10

Each edge's contact sheet shows:
- Source tail (3 frames) on top
- Target head (3 frames) on bottom
- Wrist positions
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H35_CS = H1_DIR / "contact_sheets_h35"
H35_CS.mkdir(parents=True, exist_ok=True)

YOUTUBE = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"


def load_tracklet_dets(stem: str) -> dict[int, list]:
    """Load per-tracklet detections from the Norfair CSV."""
    out = {}
    path = WORKTREE / "detections" / f"{stem}_norfair_dt50_hc5.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tid = int(r["track_id"])
            out.setdefault(tid, []).append(
                (int(r["frame"]), float(r["center_x"]), float(r["center_y"]), float(r.get("confidence", 0)))
            )
    for tid in out:
        out[tid].sort()
    return out


def load_wrist_at_frame(stem: str) -> dict[int, dict]:
    out = {}
    path = WORKTREE / "detections" / f"{stem}_yolo26s-pose.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            e = out.setdefault(f, {"left": None, "right": None})
            for side in ("left", "right"):
                x = r.get(f"{side}_wrist_x")
                y = r.get(f"{side}_wrist_y")
                c = r.get(f"{side}_wrist_confidence")
                if x and y and c and float(c) > 0.3:
                    e[side] = (float(x), float(y))
    return out


def render_sheet(stem: str, from_tid: int, to_tid: int, edge_type: str,
                  dets: dict, wrists: dict, save_path: Path) -> bool:
    src = dets.get(from_tid, [])
    tgt = dets.get(to_tid, [])
    if len(src) < 3 or len(tgt) < 3:
        return False
    src_tail = src[-3:]
    tgt_head = tgt[:3]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    title = f"{stem[:30]}  {from_tid}->{to_tid}  ({edge_type})"
    fig.suptitle(title, fontsize=14)

    for i, (fr, x, y, c) in enumerate(src_tail):
        ax = axes[0, i]
        ax.set_xlim(0, 1280)
        ax.set_ylim(720, 0)
        ax.set_aspect("equal")
        ax.set_facecolor("black")
        ax.set_title(f"src f={fr}", color="white", fontsize=10)
        w = wrists.get(fr, {})
        if w["left"]:
            ax.add_patch(Circle(w["left"], 25, color="orange", alpha=0.5))
        if w["right"]:
            ax.add_patch(Circle(w["right"], 25, color="blue", alpha=0.5))
        ax.add_patch(Circle((x, y), 8, color="white"))
        ax.scatter([x], [y], c="white", s=50, marker="o", zorder=10)

    for i, (fr, x, y, c) in enumerate(tgt_head):
        ax = axes[1, i]
        ax.set_xlim(0, 1280)
        ax.set_ylim(720, 0)
        ax.set_aspect("equal")
        ax.set_facecolor("black")
        ax.set_title(f"tgt f={fr}", color="white", fontsize=10)
        w = wrists.get(fr, {})
        if w["left"]:
            ax.add_patch(Circle(w["left"], 25, color="orange", alpha=0.5))
        if w["right"]:
            ax.add_patch(Circle(w["right"], 25, color="blue", alpha=0.5))
        ax.add_patch(Circle((x, y), 8, color="white"))
        ax.scatter([x], [y], c="white", s=50, marker="o", zorder=10)

    fig.tight_layout()
    fig.savefig(save_path, dpi=80, facecolor="black")
    plt.close(fig)
    return True


def main() -> None:
    dets = load_tracklet_dets(YOUTUBE)
    wrists = load_wrist_at_frame(YOUTUBE)

    # Load h7v3plus3 edges
    edges = []
    with (H1_DATA / f"h7v3plus3_admitted_edges_{YOUTUBE}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            edges.append(r)

    # Render sheets for chain 0 (1,9,13,16) and chain 10 (20,21,29,34)
    target_edges = [
        (1, 9), (9, 13), (13, 16),  # chain 0
        (20, 21), (21, 29), (29, 34),  # chain 10 (new from H22 veto)
    ]

    for from_tid, to_tid in target_edges:
        edge = next((e for e in edges if e["from_tid"] == from_tid and e["to_tid"] == to_tid), None)
        if edge is None:
            print(f"  WARN: edge {from_tid}->{to_tid} not in h7v3plus3")
            continue
        save_path = H35_CS / f"youtube_{from_tid}_{to_tid}.png"
        if render_sheet(YOUTUBE, from_tid, to_tid, edge["edge_type"], dets, wrists, save_path):
            print(f"  wrote {save_path.name} ({edge['edge_type']})")
        else:
            print(f"  SKIP {from_tid}->{to_tid} (insufficient detections)")


if __name__ == "__main__":
    main()
