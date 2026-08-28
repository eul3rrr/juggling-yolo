#!/usr/bin/env python3
"""H8 v5 / H10 v5 contact sheets - render the chains whose rank
moved significantly in H10 v5 (vs v3).
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h10v5"
H1_CS.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("h7cs",
    H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

# Load H10 v5 deltas
import json
deltas = json.load(open(H1_DATA / "h10v5_chain_quality_summary.json"))["videos"]["identical_balls_trick_000_018"]["deltas"]

# Pick chains with biggest movement
movers = sorted(deltas, key=lambda d: -abs(d["rank_change"]))[:6]
print("Movers:")
for m in movers:
    print(f"  chain {m['chain_id']}: rank {m['v3_rank']}->{m['v5_rank']} (delta={m['rank_change']:+d})")

# Render contact sheet for each
def get_chain_tids(stem: str, chain_id: str) -> list[int]:
    with (H1_DATA / f"h237_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["chain_id"] == chain_id:
                return [int(t) for t in r["tids"].split(",") if t]
    return []


PALETTE = [
    (255, 255, 255), (200, 100, 255), (100, 255, 100),
    (255, 255, 0), (0, 255, 255), (255, 100, 100),
    (180, 80, 255), (0, 200, 200), (255, 180, 100),
]


def render_chain(stem: str, tids: list[int], out_path: Path, title: str, subtitle: str):
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
            chosen.extend([fts[0], fts[1], fts[len(fts) // 2], fts[-2], fts[-1]])
    chosen = sorted(set(chosen))
    if len(chosen) > 30:
        step = max(1, len(chosen) // 30)
        chosen = chosen[::step]
    tracklets = [(tid, PALETTE[i % len(PALETTE)], f"t{tid}")
                 for i, tid in enumerate(tids)]
    h7cs.render_contact_sheet(
        stem=stem, frames=chosen, tracklets_to_show=tracklets,
        title=title, subtitle=subtitle, out_path=out_path, show_label_xy=False,
    )


for m in movers:
    stem = "identical_balls_trick_000_018"
    cid = m["chain_id"]
    tids = get_chain_tids(stem, cid)
    out_path = H1_CS / f"chain{cid}_v3rank{m['v3_rank']}_v5rank{m['v5_rank']}.png"
    title = f"H10 v5: chain {cid} rank {m['v3_rank']} -> {m['v5_rank']}"
    subtitle = f"v3 quality={m['v3_quality']:.3f}, v5 quality={m['v5_quality']:.3f}, tids={tids}"
    try:
        render_chain(stem, tids, out_path, title, subtitle)
        print(f"  rendered: {out_path.name}")
    except Exception as ex:
        print(f"  FAILED chain {cid}: {ex}")
