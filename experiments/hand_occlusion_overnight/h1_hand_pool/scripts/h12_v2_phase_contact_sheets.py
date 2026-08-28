#!/usr/bin/env python3
"""H12 v2 phase contact sheet - render key frames from selected phases
to enable visual QA of pattern classification.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v2"
H1_CS.mkdir(parents=True, exist_ok=True)

# Reuse the existing h7_contact_sheets render_contact_sheet
spec = importlib.util.spec_from_file_location(
    "h7cs", H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

VIDEOS_DIR = WORKTREE / "videos"

# Selected phases for visual QA. These are the substantial phases
# (n_frames >= 30) from the v2 phase CSV.
SELECTIONS = [
    # (stem, start_frame, end_frame, label, description)
    ("identical_balls_trick_000_018", 411, 450, "MIXED_3+_q0.93",
     "Phase A MIXED_3+ (high conf) — does the juggler actually mix cascade/fountain here?"),
    ("identical_balls_trick_000_018", 549, 578, "MIXED_3+_q0.85",
     "Phase A MIXED_3+ (mid conf) — transition regime?"),
    ("identical_balls_trick_000_018", 890, 936, "FOUNTAIN_3+_q0.63",
     "Phase B FOUNTAIN_3+ (q=0.63) — is this a real fountain?"),
    ("identical_balls_trick_000_018", 977, 1011, "FOUNTAIN_3+_q0.42",
     "Phase B FOUNTAIN_3+ (low conf) — borderline fountain?"),
    ("identical_balls_trick_000_018", 335, 382, "SINGLE_BALL_q0.93",
     "SINGLE_BALL (high conf) — is this a single-ball trick?"),
]


def main():
    for stem, f0, f1, label, desc in SELECTIONS:
        # Pick 4 frames evenly distributed across the phase
        frames = [f0 + (f1 - f0) * i // 5 for i in range(1, 5)]
        video_path = VIDEOS_DIR / f"{stem}.mp4"
        out_path = H1_CS / f"phase_{stem}_f{f0}-{f1}_{label.replace('+','p')}.png"
        h7cs.render_contact_sheet(
            stem=stem,
            frames=frames,
            tracklets_to_show=[],
            title=f"{stem} f={f0}-{f1} [{label}]",
            subtitle=desc,
            out_path=out_path,
        )
        print(f"  wrote: {out_path.name}")


if __name__ == "__main__":
    main()
