#!/usr/bin/env python3
"""H11 v2 contact sheets — render CONFIDENT identity-merge
candidates as side-by-side contact sheets, so visual QA can
confirm whether two chains are actually the same physical ball
(a missed merge) or genuinely different balls.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h11"
H1_CS.mkdir(parents=True, exist_ok=True)

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


def get_chain_quality(stem: str, chain_id: str) -> float:
    with (H1_DATA / f"h237v5_unified_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["chain_id"] == chain_id:
                return float(r["h10_v5_quality"])
    return 0.0


def render_two_chain_merge(stem: str, chain_a: int, chain_b: int,
                            out_path: Path, title: str,
                            subtitle: str, qa: float):
    """Render two chains side by side (overlapping frames) so
    we can visually check whether they represent the same
    physical ball or genuinely different ones."""
    tids_a = get_chain_tids(stem, str(chain_a))
    tids_b = get_chain_tids(stem, str(chain_b))
    if not tids_a or not tids_b:
        return
    # Two distinct colors
    color_a = PALETTE[chain_a % len(PALETTE)]
    color_b = PALETTE[chain_b % len(PALETTE)]
    tracklets = (
        [(tid, color_a, f"a_t{tid}") for tid in tids_a] +
        [(tid, color_b, f"b_t{tid}") for tid in tids_b]
    )
    # Pick frames from the union of frame ranges
    a_frames = set()
    b_frames = set()
    for tid in tids_a:
        for f, _, _ in h7cs.load_tracklet_points(stem, tid):
            a_frames.add(f)
    for tid in tids_b:
        for f, _, _ in h7cs.load_tracklet_points(stem, tid):
            b_frames.add(f)
    overlap = sorted(a_frames & b_frames)
    if not overlap:
        # No overlap; use a 30-frame window around the event
        # Pick a_frames and b_frames around their closest endpoints
        a_last = max(a_frames)
        b_first = min(b_frames)
        if b_first > a_last:
            chosen = sorted(list(a_frames)[-10:] + list(b_frames)[:10])
        else:
            chosen = sorted(list(a_frames)[:10] + list(b_frames)[-10:])
    else:
        # Use overlap frames + 5 frames on each side
        lo = max(0, min(overlap) - 5)
        hi = max(overlap) + 5
        chosen = sorted(f for f in a_frames | b_frames if lo <= f <= hi)
    if len(chosen) > 30:
        step = max(1, len(chosen) // 30)
        chosen = chosen[::step]
    h7cs.render_contact_sheet(
        stem=stem, frames=chosen, tracklets_to_show=tracklets,
        title=title, subtitle=subtitle, out_path=out_path,
        show_label_xy=True,
    )


def main():
    stem = "identical_balls_trick_000_018"
    # The 1 CONFIDENT merge candidate: chain36 -> chain30
    # (also chain30 -> chain36 from the other direction)
    print("=== Identity merge candidates (CONFIDENT only) ===")
    print("  - chain36 <-> chain30 (h3=True, right hand, -4 frames)")

    render_two_chain_merge(
        stem, 36, 30,
        H1_CS / "merge_chain36_chain30.png",
        title="H11 v2: chain 36 (CONFIDENT q=0.94) <-> chain 30 (UNCERTAIN q=0.45)",
        subtitle=("t62,t66 (chain 36) overlap with t62,t63 of chain 30. "
                  "Visual QA: is this a missed merge (same physical ball) "
                  "or genuinely different balls?"),
        qa=0.94,
    )


if __name__ == "__main__":
    main()
