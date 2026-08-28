#!/usr/bin/env python3
"""H10 visual QA - render the most/least H10-quality chains
for visual QA. Uses h7_contact_sheets' render_contact_sheet.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h10"
H1_CS.mkdir(parents=True, exist_ok=True)

# Import h7_contact_sheets directly
spec = importlib.util.spec_from_file_location("h7cs",
    H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

VIDEOS = {
    "identical_balls_trick_000_018":
        "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}

# Chosen for visual QA
SELECTIONS = [
    ("identical_balls_trick_000_018", "23", "top_quality_longest",
     "H10 top quality on identical (qual=0.84), 7 tids (H7 longest)"),
    ("identical_balls_trick_000_018", "30", "mid_quality_4hand_edges",
     "H10 mid quality (0.45), 3 hand + 1 air, 1 air violation, 2 H3 confirmed"),
    ("identical_balls_trick_000_018", "13", "low_quality_2violations",
     "H10 low quality (0.30), h3=0, 2 air violations, 4 tids"),
    ("identical_balls_trick_000_018", "38", "low_quality_1violation",
     "H10 low quality (0.35), h3=0, h8=0, 1 air violation, 3 tids"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", "9",
     "youtube_worst_quality",
     "H10 worst multi-edge chain on YouTube (0.51), 5 air edges all H8-violating"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", "6",
     "youtube_top_quality",
     "H10 top quality on YouTube (0.97), the only chain with h3 confirmed"),
]

# Color palette: clearly distinct from orange/blue hand colors
PALETTE = [
    (255, 255, 255),  # white
    (200, 100, 255),  # pink
    (100, 255, 100),  # light green
    (255, 255, 0),    # bright yellow
    (0, 255, 255),    # cyan
    (255, 100, 100),  # light red
    (180, 80, 255),   # purple
    (0, 200, 200),    # teal
    (255, 180, 100),  # peach
]


def get_chain_tids(stem: str, chain_id: str) -> list[int]:
    with (H1_DATA / f"h237_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["chain_id"] == chain_id:
                return [int(t) for t in r["tids"].split(",") if t]
    return []


def get_chain_edges(stem: str, chain_id: str) -> list[dict]:
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        all_edges = list(csv.DictReader(fh))
    tids = get_chain_tids(stem, chain_id)
    out = []
    for i in range(len(tids) - 1):
        a, b = tids[i], tids[i + 1]
        for e in all_edges:
            if int(e["from_tid"]) == a and int(e["to_tid"]) == b:
                out.append({"from_tid": a, "to_tid": b, "edge_type": e["edge_type"]})
                break
    return out


def render_chain(stem: str, tids: list[int], edges: list[dict],
                 out_path: Path, title: str, subtitle: str):
    """Render a contact sheet for a chain using h7cs.render_contact_sheet.

    Choose 4-6 frames from each tracklet: first 2, middle 2, last 2.
    For 2-tid chains, also include 2-3 frames from the gap.
    """
    # Collect frames per tracklet
    frames_by_tid = {tid: [t[0] for t in h7cs.load_tracklet_points(stem, tid)]
                     for tid in tids}
    chosen = []
    for tid in tids:
        fts = sorted(frames_by_tid[tid])
        if not fts:
            continue
        if len(fts) <= 6:
            chosen.extend(fts)
        else:
            chosen.extend([fts[0], fts[1], fts[len(fts) // 2],
                          fts[-2], fts[-1]])
    chosen = sorted(set(chosen))
    if len(chosen) > 30:
        # Subsample evenly
        step = max(1, len(chosen) // 30)
        chosen = chosen[::step]
    # Build tracklets_to_show with distinct colors
    tracklets_to_show = []
    for i, tid in enumerate(tids):
        color = PALETTE[i % len(PALETTE)]
        tracklets_to_show.append((tid, color, f"t{tid}"))
    h7cs.render_contact_sheet(
        stem=stem,
        frames=chosen,
        tracklets_to_show=tracklets_to_show,
        title=title,
        subtitle=subtitle,
        out_path=out_path,
        show_label_xy=False,
    )


def main():
    for stem, chain_id, label, reason in SELECTIONS:
        tids = get_chain_tids(stem, chain_id)
        edges = get_chain_edges(stem, chain_id)
        if not tids:
            print(f"  SKIP: no tids for chain {chain_id} in {stem}")
            continue
        edge_summary = ", ".join(f"{e['from_tid']}->{e['to_tid']}({e['edge_type']})"
                                  for e in edges)
        out_path = H1_CS / f"chain{chain_id}_{label}_{stem[:25]}.png"
        title = (f"H10 chain {chain_id} ({label}) on {stem}")
        subtitle = (f"{reason}\nedges: {edge_summary}")
        try:
            render_chain(stem, tids, edges, out_path, title, subtitle)
            print(f"  rendered: {out_path.name}")
        except Exception as ex:
            print(f"  FAILED: {out_path.name}: {ex}")


if __name__ == "__main__":
    main()
