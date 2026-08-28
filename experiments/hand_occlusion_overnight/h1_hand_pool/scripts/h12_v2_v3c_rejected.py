#!/usr/bin/env python3
"""Visual QA contact sheet for the v3c-rejected links:
- 35 -> 40 on identical (rejected by v4d, low from_slope)
- 15 -> 25 on youtube (rejected by v4d, low from_slope)

If either is a real catch/throw, the v4d threshold may be too strict.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_CS = H1_DIR / "contact_sheets_h12v2"
H1_CS.mkdir(parents=True, exist_ok=True)

# Reuse the existing h7_contact_sheets render_contact_sheet
spec = importlib.util.spec_from_file_location(
    "h7cs", H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

# Load tracklet features
tracklets = {}
with (H1_DIR / "data" / "tracklet_features.csv").open() as fh:
    for r in csv.DictReader(fh):
        tracklets[int(r["tid"])] = r


def render_around(stem, from_tid, to_tid, from_frame, to_frame, label):
    ft = tracklets.get(from_tid)
    tt = tracklets.get(to_tid)
    if ft is None or tt is None:
        print(f"  could not find tracklets {from_tid} or {to_tid}")
        return
    f0 = max(0, from_frame - 5)
    f1 = to_frame + 5
    frames = [f0 + (f1 - f0) * i // 6 for i in range(1, 7)]
    out = H1_CS / f"v3c_rejected_{stem}_t{from_tid}_t{to_tid}_{label}.png"
    h7cs.render_contact_sheet(
        stem=stem,
        frames=frames,
        tracklets_to_show=[(from_tid, (0, 200, 255), f"t{from_tid}"),
                            (to_tid, (255, 100, 0), f"t{to_tid}")],
        title=f"{stem}: v3c {from_tid}->{to_tid} ({label}) rejected by v4d",
        subtitle=f"f={from_frame}-{to_frame}, from_slope=2.31<2.5",
        out_path=out,
    )
    print(f"  wrote: {out.name}")


def main():
    # 35 -> 40 on identical, f=522-549
    render_around("identical_balls_trick_000_018", 35, 40, 522, 549,
                   "identical_low_slope")
    # 15 -> 25 on youtube, f=595-606
    render_around("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
                   15, 25, 595, 606, "youtube_low_slope")


if __name__ == "__main__":
    main()
