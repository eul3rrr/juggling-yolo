#!/usr/bin/env python3
"""H11 visual QA — render contact sheets for the chains that H11
classified as CONFIDENT (q >= 0.7) and that have hand-edges.

For each such chain, show all tracklets in the chain with a
single-color overlay (one color per chain = "one physical ball"),
plus the hand positions and frame numbers.

We also render the two long UNCERTAIN chains (30, 31) for
contrast — these chains have many hand-edges but are
UNCERTAIN due to identity switches; visual QA can confirm
whether the catch/throw events are real or just FIFO
bookkeeping.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h11"
H1_CS.mkdir(parents=True, exist_ok=True)

# Reuse the h7_contact_sheets module for rendering helpers.
spec = importlib.util.spec_from_file_location(
    "h7cs", H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)


PALETTE = [
    (255, 255, 255), (200, 100, 255), (100, 255, 100),
    (255, 255, 0), (0, 255, 255), (255, 100, 100),
    (180, 80, 255), (0, 200, 200), (255, 180, 100),
    (100, 200, 255), (255, 200, 100), (200, 255, 100),
    (255, 100, 200), (100, 100, 255), (200, 200, 100),
]


def get_chain_tids(stem: str, chain_id: str) -> list[int]:
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["chain_id"] == chain_id:
                return [int(t) for t in r["tids"].split(",") if t]
    return []


def get_chain_quality(stem: str, chain_id: str) -> tuple[float, int, int]:
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["chain_id"] == chain_id:
                return (float(r["h10_v5_quality"]),
                        int(r["n_tracklets"]),
                        int(r["n_hand_edges"]))
    return (0.0, 0, 0)


def get_chain_edges(stem: str, tids: list[int]) -> dict:
    out = {}
    with (H1_DATA / f"h237_unified_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            key = (int(r["from_tid"]), int(r["to_tid"]))
            if key[0] in tids and key[1] in tids:
                out[key] = r["edge_type"]
    return out


def render_chain(stem: str, tids: list[int], ball_id: str, out_path: Path,
                 title: str, subtitle: str, show_label_xy: bool = False,
                 frames_per_tid: int = 4):
    """Render a contact sheet for one chain, all tracklets in
    the same color (one color = one physical ball)."""
    if not tids:
        return
    # Single color for the chain
    color = PALETTE[hash(ball_id) % len(PALETTE)]
    tracklets = [(tid, color, f"t{tid}") for tid in tids]
    # Pick frames
    chosen = []
    for tid in tids:
        fts = sorted([t[0] for t in h7cs.load_tracklet_points(stem, tid)])
        if not fts:
            continue
        if len(fts) <= frames_per_tid:
            chosen.extend(fts)
        else:
            # First, last, and 2 middle
            chosen.extend([fts[0], fts[len(fts) // 3],
                          fts[2 * len(fts) // 3], fts[-1]])
    chosen = sorted(set(chosen))
    if len(chosen) > 24:
        step = max(1, len(chosen) // 24)
        chosen = chosen[::step]
    h7cs.render_contact_sheet(
        stem=stem, frames=chosen, tracklets_to_show=tracklets,
        title=title, subtitle=subtitle, out_path=out_path,
        show_label_xy=show_label_xy,
    )


def main():
    stem = "identical_balls_trick_000_018"

    # 1. Render all CONFIDENT chains with hand-edges (the "trustworthy" ones)
    print("=== CONFIDENT chains (q >= 0.7) with hand-edges ===")
    confident_chains = []
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            q = float(r["h10_v5_quality"])
            nh = int(r["n_hand_edges"])
            if q >= 0.7 and nh >= 1:
                confident_chains.append({
                    "chain_id": r["chain_id"],
                    "tids": r["tids"],
                    "quality": q,
                    "n_hand": nh,
                })
    for c in confident_chains:
        tids = [int(t) for t in c["tids"].split(",") if t]
        ball_id = f"chain{c['chain_id']}_ball0"
        out = H1_CS / f"chain{c['chain_id']}_CONFIDENT_hand.png"
        title = f"H11: chain {c['chain_id']} = {ball_id} (CONFIDENT q={c['quality']:.3f})"
        subtitle = f"tids={tids}, n_hand={c['n_hand']}, n_air=0"
        try:
            render_chain(stem, tids, ball_id, out, title, subtitle,
                         show_label_xy=True, frames_per_tid=4)
            print(f"  rendered: {out.name}")
        except Exception as ex:
            print(f"  FAILED: {ex}")

    # 2. Render UNCERTAIN chains with hand-edges (the "use with caution" ones)
    print("\n=== UNCERTAIN chains (0.4 <= q < 0.7) with hand-edges ===")
    uncertain_chains = []
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            q = float(r["h10_v5_quality"])
            nh = int(r["n_hand_edges"])
            if 0.4 <= q < 0.7 and nh >= 1:
                uncertain_chains.append({
                    "chain_id": r["chain_id"],
                    "tids": r["tids"],
                    "quality": q,
                    "n_hand": nh,
                })
    for c in uncertain_chains:
        tids = [int(t) for t in c["tids"].split(",") if t]
        ball_id = f"chain{c['chain_id']}_ball0"
        out = H1_CS / f"chain{c['chain_id']}_UNCERTAIN_hand.png"
        title = f"H11: chain {c['chain_id']} = {ball_id} (UNCERTAIN q={c['quality']:.3f})"
        subtitle = f"tids={tids}, n_hand={c['n_hand']}"
        try:
            render_chain(stem, tids, ball_id, out, title, subtitle,
                         show_label_xy=True, frames_per_tid=3)
            print(f"  rendered: {out.name}")
        except Exception as ex:
            print(f"  FAILED: {ex}")

    # 3. Render the YouTube CONFIDENT chain
    print("\n=== YouTube CONFIDENT chain ===")
    stem_yt = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"
    with (H1_DATA / f"h237v5_unified_chains_{stem_yt}.csv").open() as fh:
        for r in csv.DictReader(fh):
            q = float(r["h10_v5_quality"])
            nh = int(r["n_hand_edges"])
            if q >= 0.7 and nh >= 1:
                tids = [int(t) for t in r["tids"].split(",") if t]
                ball_id = f"chain{r['chain_id']}_ball0"
                out = H1_CS / f"yt_chain{r['chain_id']}_CONFIDENT_hand.png"
                title = f"H11 (YouTube): chain {r['chain_id']} = {ball_id} (CONFIDENT q={q:.3f})"
                subtitle = f"tids={tids}, n_hand={nh}"
                try:
                    render_chain(stem_yt, tids, ball_id, out, title, subtitle,
                                 show_label_xy=True, frames_per_tid=3)
                    print(f"  rendered: {out.name}")
                except Exception as ex:
                    print(f"  FAILED: {ex}")


if __name__ == "__main__":
    main()
