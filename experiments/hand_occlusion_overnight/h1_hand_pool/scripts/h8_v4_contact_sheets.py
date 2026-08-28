#!/usr/bin/env python3
"""H8 v4 contact sheets - render the 3 v4-VIOLATING air edges
on identical (19->20, 51->52, 23->25) and 1 OK for comparison.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h8v4"
H1_CS.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("h7cs",
    H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

STEMS = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}

# Edges to QA on identical
EDGES = [
    # (stem, from_tid, to_tid, label)
    ("identical_balls_trick_000_018", 19, 20, "v4_violating"),
    ("identical_balls_trick_000_018", 51, 52, "v4_violating_chain30"),
    ("identical_balls_trick_000_018", 23, 25, "v4_violating_chain13"),
    # For comparison, the v3-flagged-but-v4-LONG ones
    ("identical_balls_trick_000_018", 5, 6, "v3_violating_now_long"),
    ("identical_balls_trick_000_018", 50, 55, "v3_violating_now_long"),
]


def render_edge(stem: str, from_tid: int, to_tid: int, label: str):
    src_pts = h7cs.load_tracklet_points(stem, from_tid)
    tgt_pts = h7cs.load_tracklet_points(stem, to_tid)
    if not src_pts or not tgt_pts:
        print(f"  SKIP {from_tid}->{to_tid}: missing tracklet points")
        return
    src_frames = [p[0] for p in src_pts]
    tgt_frames = [p[0] for p in tgt_pts]
    # Use last 5 frames of source + first 5 frames of target
    show_frames = sorted(set(src_frames[-5:] + tgt_frames[:5]))
    out_path = H1_CS / f"edge_{from_tid}_{to_tid}_{label}_{stem[:25]}.png"
    title = f"H8 v4: edge {from_tid}->{to_tid} ({label}) on {stem}"
    subtitle = (f"src: n_pts={len(src_pts)} frames={src_frames[0]}..{src_frames[-1]} "
                f"tgt: n_pts={len(tgt_pts)} frames={tgt_frames[0]}..{tgt_frames[-1]}")
    tracklets = [(from_tid, (200, 100, 255), f"t{from_tid}"),
                 (to_tid, (100, 255, 100), f"t{to_tid}")]
    h7cs.render_contact_sheet(
        stem=stem, frames=show_frames, tracklets_to_show=tracklets,
        title=title, subtitle=subtitle, out_path=out_path,
        show_label_xy=True,
    )
    print(f"  rendered: {out_path.name}")


def main():
    for stem, from_tid, to_tid, label in EDGES:
        render_edge(stem, from_tid, to_tid, label)


if __name__ == "__main__":
    main()
